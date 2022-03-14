"""
dashboard/callbacks/narrative_callbacks.py

Version 6 — Custom search enhancement:
  - Preset topics: curated QUERY_EXPANSIONS + TOPIC_KEYWORDS (unchanged)
  - Custom search: auto-expansion via CUSTOM_QUERY_EXPANSIONS map
  - Custom search: keyword list derived from query words + synonyms
  - Adaptive threshold k=0.45 for custom (less aggressive than preset k=0.55)
  - Thematic overview only shown for preset topics, not custom search
  - 100+ common Islamic/English terms in CUSTOM_QUERY_EXPANSIONS
  - All commentaries use "Allah" not "God"
  - 40 preset topics across 7 categories
"""

import os
import re
import sys
import json
import numpy as np

from dash import html, callback_context
from dash.dependencies import Input, Output, State, ALL
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.app import app, DB_PATH, EMBEDDINGS_PATH, query_df

_embeddings_cache = None
_verse_ids_cache  = None
_model_cache      = None
_embeddings_mtime = 0   # track file modification time


# ── Keyword sets per topic ─────────────────────────────────────────────────────
# These words are matched against the English translation to boost relevance.
# Each keyword found adds a small bonus to the hybrid score.
TOPIC_KEYWORDS = {
    "mercy and forgiveness": [
        "mercy", "merciful", "compassion", "forgive", "forgiveness", "pardon",
        "relent", "gracious", "rahma", "maghfira", "forgave", "oft-forgiving",
        "most merciful", "pardons", "compassionate", "amnesty", "absolve",
    ],
    "day of judgment": [
        "day", "judgment", "judgement", "resurrection", "reckoning", "account",
        "hereafter", "qiyama", "hour", "rising", "weighing", "deeds", "record",
        "balance", "scales", "assembled", "gathered", "standing", "trumpet",
    ],
    "repentance": [
        "repent", "repentance", "tawba", "turn", "return", "seek forgiveness",
        "forgive", "turned back", "relented", "accept repentance", "regret",
        "remorse", "atone", "atonement", "sincerely",
    ],
    "guidance and misguidance": [
        "guide", "guidance", "guided", "astray", "straight path", "path",
        "right path", "huda", "misguide", "misguided", "wrong path", "error",
        "straying", "lost", "truth", "led astray", "clear path",
    ],
    "covenant and promise": [
        "covenant", "promise", "pledge", "oath", "ahd", "agreement", "bound",
        "treaty", "compact", "undertook", "fulfilled", "broke", "contract",
        "obligation", "commitments", "confirmed",
    ],
    "trust and hypocrisy": [
        "hypocrite", "hypocrisy", "munafiq", "nifaq", "two-faced", "insincere",
        "deceive", "false belief", "conceal", "pretend", "disguise",
        "double-hearted", "disease in heart", "disbelieve", "secretly",
    ],
    "remembrance of god": [
        "remember", "remembrance", "dhikr", "mention", "glorify", "hearts",
        "rest", "tranquility", "peace", "consciousness", "mindful", "aware",
        "glorification", "praise", "hearts find rest", "invoke",
    ],
    "divine oneness": [
        "one", "alone", "only", "tawhid", "associate", "partner", "none",
        "no god but", "monotheism", "lord", "unique", "singular", "no equals",
        "worship him alone", "nothing like him", "he is one",
    ],
    "patience and hardship": [
        "patient", "patience", "sabr", "endure", "hardship", "trial",
        "persevere", "steadfast", "difficulty", "affliction", "bear",
        "perseverance", "endurance", "tribulation", "persist",
    ],
    "gratitude": [
        "grateful", "gratitude", "thankful", "thank", "shukr", "bounty",
        "blessings", "bless", "increase", "acknowledge", "appreciate",
        "ingratitude", "ungrateful", "gifts", "favour",
    ],
    "justice and oppression": [
        "justice", "just", "adl", "oppression", "oppress", "wrongdoer",
        "injustice", "zulm", "equity", "fair", "rights", "wrongdoing",
        "unjust", "transgress", "tyranny", "equal", "witness fairly",
    ],
    "the heart": [
        "heart", "hearts", "qalb", "sealed", "hardened", "blind", "diseased",
        "contented", "trembles", "inner", "soul", "inclined", "softened",
        "convinced", "chest", "breast", "expands", "doubting",
    ],
    "satan and temptation": [
        "satan", "iblis", "devil", "whisper", "temptation", "waswas",
        "evil", "misled", "lure", "astray", "disobey", "refuse", "arrogant",
        "shaitan", "jinn", "enemies", "adorned", "beautified",
    ],
    "arrogance and pride": [
        "arrogant", "arrogance", "pride", "proud", "kibr", "haughty",
        "disdain", "boast", "iblis refused", "turn away", "scorn",
        "insolent", "overbearing", "self-righteous", "vain", "refuse",
    ],
    "women and rights": [
        "women", "woman", "wife", "wives", "female", "mother", "daughter",
        "rights", "marry", "marriage", "divorce", "inheritance", "dowry",
        "consort", "mahr", "dower", "widow", "nursing", "breastfeed",
    ],
    "children and orphans": [
        "orphan", "orphans", "yatim", "child", "children", "guardian",
        "property of orphan", "care", "ward", "minor", "sons", "daughters",
        "protection", "nurture", "raise", "upbringing",
    ],
    "family and community": [
        "family", "kin", "kinship", "relatives", "community", "ties",
        "parents", "honor", "brotherhood", "bonds", "together", "neighbor",
        "household", "womb", "relationships", "lineage",
    ],
    "trade and honesty": [
        "trade", "honest", "honesty", "contract", "agreement", "weight",
        "measure", "commerce", "deal", "fair", "deceive", "defraud",
        "transaction", "scales", "witness", "debt", "creditor", "loan",
    ],
    "wealth and charity": [
        "wealth", "spend", "charity", "zakat", "poor", "needy", "give",
        "sadaqa", "generous", "hoard", "miserly", "righteous", "gold",
        "silver", "riches", "property", "mal", "alms",
    ],
    "food and lawful eating": [
        "eat", "food", "lawful", "unlawful", "forbidden", "halal", "haram",
        "slaughter", "pork", "blood", "carrion", "permitted", "prohibited",
        "provision", "nourishment", "game", "seafood",
    ],
    "unity and division": [
        "unity", "united", "divided", "division", "together", "hold fast",
        "rope", "fragmented", "sects", "factions", "discord", "quarrel",
        "ummah", "brotherhood", "split", "dispute", "reconcile",
    ],
    "prayer and worship": [
        "prayer", "pray", "salah", "worship", "prostrate", "bow", "stand",
        "remembrance", "devotion", "congregation", "Friday", "call",
        "establish prayer", "qibla", "salat", "fajr", "asr",
    ],
    "knowledge and wisdom": [
        "know", "knowledge", "wisdom", "learn", "understand", "ilm",
        "reflect", "ponder", "think", "reason", "intellect", "scholars",
        "aware", "informed", "taught", "hikma", "comprehend",
    ],
    "prophets and messengers": [
        "prophet", "messenger", "apostle", "ibrahim", "musa", "isa",
        "nuh", "dawud", "sulayman", "yahya", "idris", "revelation",
        "sent", "prophethood", "message", "noah", "moses", "jesus",
    ],
    "fasting and self-discipline": [
        "fast", "fasting", "sawm", "ramadan", "abstain", "refrain",
        "self-discipline", "taqwa", "month", "sunrise", "sunset",
        "iftar", "suhoor", "night of power", "laylat al-qadr",
    ],
    "pilgrimage and sacred places": [
        "hajj", "pilgrimage", "makkah", "kaaba", "sanctuary", "sacred",
        "ibrahim", "ismail", "masjid", "haram", "safa", "marwa",
        "tawaf", "circumambulation", "station", "arafah", "ihram",
    ],
    "supplication and prayer": [
        "supplicate", "dua", "call upon", "invoke", "ask", "beg",
        "seek help", "appeal", "prayer", "lord hear", "answer",
        "call to", "respond", "plead", "beseech", "cry",
    ],
    "paradise": [
        "paradise", "jannah", "garden", "rivers", "reward", "bliss",
        "eternal", "blessed", "companions", "peace", "therein",
        "righteous", "abode", "delight", "felicity", "shade",
    ],
    "hellfire and punishment": [
        "hell", "hellfire", "fire", "jahannam", "punishment", "torment",
        "blaze", "burn", "painful", "chastisement", "penalty",
        "abide therein", "disbelievers", "warning", "wrath",
    ],
    "death and dying": [
        "death", "die", "dead", "dying", "mawt", "soul", "taken",
        "appointed time", "angel of death", "perish", "return",
        "afterlife", "taste death", "every soul", "deceased",
    ],
    "angels": [
        "angel", "angels", "malaika", "jibreel", "gabriel", "mikail",
        "spirit", "descend", "revelation", "wings", "messengers",
        "beings", "prostrate", "recording", "guardian",
    ],
    "prayer for the dead": [
        "funeral", "deceased", "burial", "prayer for", "dead", "passed",
        "departed", "shroud", "grave", "loss", "grief", "mercy upon",
        "forgive him", "forgive her", "intercede",
    ],
    "signs and miracles": [
        "sign", "signs", "miracle", "ayat", "proof", "evidence",
        "wonders", "portent", "staff", "split", "raise dead",
        "observe", "creation", "surely in that", "for those who reflect",
    ],
    "nature and creation": [
        "heaven", "earth", "sky", "sun", "moon", "stars", "mountains",
        "creation", "create", "created", "universe", "signs", "winds",
        "seas", "rivers", "clouds", "day", "night",
    ],
    "water and rain": [
        "water", "rain", "river", "sea", "ocean", "spring", "cloud",
        "pour", "descend from sky", "streams", "flood", "wells",
        "living water", "drink", "irrigation", "moisture",
    ],
    "creation of humans": [
        "human", "mankind", "man", "created you", "clay", "dust",
        "drop", "clot", "khalq", "vicegerent", "origin", "khalifa",
        "formed", "fashioned", "breathed", "nature",
    ],
    "animals and living creatures": [
        "cattle", "animal", "beast", "bird", "camel", "horse", "donkey",
        "ant", "bee", "fly", "fish", "creature", "livestock", "created",
        "slaughter", "ride", "benefit", "stewardship",
    ],
    "time and history": [
        "time", "age", "era", "history", "nations", "before you",
        "destroyed", "civilizations", "past", "lesson", "example",
        "generation", "centuries", "asr", "ages", "warning to",
    ],
    "patience under trial": [
        "trial", "test", "tested", "tribulation", "affliction",
        "ibtila", "patience", "calamity", "hardship", "difficulty",
        "burden", "loss", "earthquake", "fear", "hunger",
    ],
    "war and peace": [
        "fight", "war", "battle", "peace", "qital", "enemy", "aggression",
        "permission", "defense", "cease", "treaty", "warfare",
        "hostilities", "armed", "combatant", "surrender",
    ],
    "forgiveness between people": [
        "forgive", "pardon", "afw", "overlook", "excuse", "reconcile",
        "let go", "between people", "wronged", "release", "settle",
        "turn away", "graciously", "peace", "reconciliation",
    ],
    "migration and exile": [
        "migrate", "migration", "hijra", "emigrate", "exile", "leave home",
        "muhajir", "abandoned", "path of allah", "refuge", "shelter",
        "displaced", "journey", "fled", "settled",
    ],
    "oppressed and vulnerable": [
        "oppressed", "weak", "vulnerable", "mustadafin", "poor",
        "helpless", "slave", "enslaved", "downtrodden", "defend",
        "protection", "save", "rescue", "wronged", "cry", "refuge",
    ],
    "striving and effort": [
        "strive", "striving", "jihad", "effort", "struggle", "path of allah",
        "sacrifice", "exert", "fight", "cause", "devoted", "persevere",
        "wealth and lives", "spending", "give all",
    ],
    "accountability and reckoning": [
        "account", "reckoning", "hisab", "deeds", "record", "book",
        "judgment", "weigh", "scales", "every soul", "reward",
        "punish", "consequence", "return", "nothing hidden",
    ],
}


# ── Richer query expansions ───────────────────────────────────────────────────
QUERY_EXPANSIONS = {
    "mercy and forgiveness":
        "Allah mercy compassion forgiveness pardon rahma maghfira raheem "
        "oft-forgiving most merciful believers sins repent relent gracious",
    "day of judgment":
        "day resurrection reckoning qiyama judgment accountability souls deeds "
        "scales weighing assembled trumpet hour hereafter record standing",
    "repentance":
        "repentance tawba return Allah forgiveness turning back sins regret "
        "accept repentance relented remorse seek forgiveness atone sincere",
    "guidance and misguidance":
        "guidance huda straight path misguidance dalal truth led astray "
        "right path error straying blind deaf sealed hearts clear path",
    "covenant and promise":
        "covenant ahd promise pledge oath agreement fulfilled broke obligation "
        "committed contract bond treaty undertook compact bound",
    "trust and hypocrisy":
        "hypocrisy nifaq munafiqun false belief deception insincere two-faced "
        "conceal pretend disease heart disbelieve secretly double-hearted",
    "remembrance of god":
        "dhikr remembrance Allah consciousness presence heart peace tranquility "
        "rest mention glorify mindful aware invoke hearts find rest praise",
    "divine oneness":
        "oneness tawhid monotheism Allah one no partner worship alone unique "
        "singular nothing like him associate no god but allah he is one",
    "patience and hardship":
        "patience sabr endurance hardship trial persecution believers steadfast "
        "persevere difficulty affliction bear tribulation endure persist",
    "gratitude":
        "gratitude shukr thankfulness blessings Allah bounty giving appreciate "
        "ungrateful acknowledge favour increase gifts grateful",
    "justice and oppression":
        "justice adl oppression injustice zulm rights equity wrongdoing "
        "unjust tyranny transgress fair witness equal wrongdoer",
    "the heart":
        "heart qalb soul inner consciousness faith sealed hardened blind "
        "diseased contented trembles softened breast chest convinced",
    "satan and temptation":
        "satan iblis devil whisper temptation waswas evil disobedience "
        "misled lure astray shaitan refuse arrogant beautified adorned",
    "arrogance and pride":
        "arrogance kibr pride humility submission ego iblis refused disdain "
        "boast scorn haughty overbearing insolent vain self-righteous",
    "women and rights":
        "women rights marriage divorce inheritance equality dignity wife "
        "mother daughter dowry mahr dower widow breastfeed nursing",
    "children and orphans":
        "orphans yatim protection care rights vulnerability guardian property "
        "children ward minor sons daughters nurture upbringing raise",
    "family and community":
        "family marriage kinship relatives community ties parents honor "
        "brotherhood bonds together neighbor household womb lineage",
    "trade and honesty":
        "trade honesty contracts fairness weights commerce truthfulness "
        "defraud scales measure debt witness transaction agreement",
    "wealth and charity":
        "wealth mal charity zakat spending poor giving generosity sadaqa "
        "hoard miserly gold silver riches property alms needy",
    "food and lawful eating":
        "food halal lawful eating prohibited permitted slaughter pork blood "
        "carrion forbidden provision nourishment game seafood",
    "unity and division":
        "unity community ummah division factionalism brotherhood together "
        "hold fast rope fragmented sects discord quarrel dispute reconcile",
    "prayer and worship":
        "prayer salah worship prostration remembrance Allah devotion "
        "congregation Friday bow stand establish salat fajr asr",
    "knowledge and wisdom":
        "knowledge ilm wisdom understanding learning intellect reflect ponder "
        "think reason scholars informed hikma comprehend aware",
    "prophets and messengers":
        "prophets messengers revelation prophethood Muhammad Ibrahim Musa Isa "
        "Nuh Dawud Sulayman sent Noah Moses Jesus message",
    "fasting and self-discipline":
        "fasting sawm Ramadan self-discipline abstention taqwa month sunrise "
        "sunset iftar suhoor night of power laylat al-qadr",
    "pilgrimage and sacred places":
        "pilgrimage hajj Makkah Kaaba sacred Ibrahim Ismail sanctuary "
        "masjid haram safa marwa tawaf arafah ihram",
    "supplication and prayer":
        "supplication dua calling Allah prayer asking mercy help invoke "
        "appeal plead beseech answer respond lord hear cry seek",
    "paradise":
        "paradise jannah garden rivers reward believers afterlife blessings "
        "bliss eternal righteous abode delight shade felicity companions",
    "hellfire and punishment":
        "hellfire jahannam punishment torment sinners warning disbelief fire "
        "blaze burn painful chastisement penalty wrath abide therein",
    "death and dying":
        "death dying mawt soul afterlife appointed time perish angel of death "
        "every soul taste death return deceased taken",
    "angels":
        "angels malaika revelation messengers divine beings Jibreel Gabriel "
        "Mikail spirit descend wings recording guardian prostrate",
    "prayer for the dead":
        "prayer funeral deceased burial departed shroud grave loss grief "
        "mercy forgive intercede passed passed away",
    "signs and miracles":
        "signs ayat miracles creation evidence proof messengers wonders "
        "portent staff split raise dead observe surely in that reflect",
    "nature and creation":
        "nature creation sky earth signs ayat universe mountains rivers "
        "sun moon stars winds seas clouds day night",
    "water and rain":
        "water rain rivers seas springs clouds pour descend sky streams "
        "flood wells living drink irrigation moisture",
    "creation of humans":
        "human creation clay dust khalq origin dignity vicegerent formed "
        "fashioned breathed drop clot nature mankind",
    "animals and living creatures":
        "animals creatures birds cattle camel horse donkey ant bee fly fish "
        "livestock created ride benefit stewardship slaughter",
    "time and history":
        "time history nations past civilizations lesson warning example "
        "generation destroyed centuries ages asr before you",
    "patience under trial":
        "trial ibtila test hardship patience endurance believers affliction "
        "tribulation calamity burden loss earthquake fear hunger",
    "war and peace":
        "war peace fighting qital justice aggression defense permission "
        "treaty warfare hostilities combatant surrender cease enemy",
    "forgiveness between people":
        "forgiveness pardon afw people relations reconciliation mercy overlook "
        "excuse release settle graciously between people wronged",
    "migration and exile":
        "migration hijra exile sacrifice leaving home Allah path muhajir "
        "emigrate abandoned refuge shelter displaced journey fled",
    "oppressed and vulnerable":
        "oppressed vulnerable weak mustadafin poor helpless slave downtrodden "
        "defend rescue save protection wronged cry refuge",
    "striving and effort":
        "striving jihad effort sacrifice path Allah struggle exert devoted "
        "persevere wealth and lives spending fight cause",
    "accountability and reckoning":
        "accountability reckoning hisab deeds judgment reward punishment "
        "record book weigh scales every soul return nothing hidden",
    "creation of humans":
        "human creation clay dust khalq origin dignity vicegerent khalifa "
        "formed fashioned breathed nature mankind drop clot",
    "prayer for the dead":
        "funeral deceased burial prayer departed shroud grave loss grief "
        "mercy upon forgive intercede passed away",
}


# ── Custom query expansion map ────────────────────────────────────────────────
# Used when the user types a free-text query (not a preset topic).
# Maps single English words/phrases → richer semantic expansion strings.
# Covers the most common things a user might type in the search box.

CUSTOM_QUERY_EXPANSIONS = {
    # Core theology
    "allah":        "Allah God Lord creator sustainer worship praise",
    "god":          "Allah God Lord creator sustainer worship praise",
    "mercy":        "mercy merciful compassion forgive forgiveness rahma gracious pardon",
    "forgiveness":  "forgiveness forgive pardon mercy relent repent absolve gracious",
    "repentance":   "repentance repent tawba turn return forgive regret remorse atone",
    "faith":        "faith belief trust iman believe certainty conviction reliance",
    "belief":       "belief faith iman believe trust certainty conviction",
    "prayer":       "prayer salah worship prostrate bow remember glorify devotion",
    "worship":      "worship prayer salah prostrate bow devotion glorify serve",
    "charity":      "charity zakat sadaqa spend give poor needy wealth generous",
    "fasting":      "fasting sawm ramadan abstain restrain taqwa discipline month",
    "pilgrimage":   "pilgrimage hajj makkah kaaba ibrahim sanctuary sacred rites",
    "zakat":        "zakat charity purification alms spend give poor obligatory",
    "hajj":         "hajj pilgrimage makkah kaaba ibrahim sanctuary sacred rites",

    # Character & ethics
    "patience":     "patient patience sabr endure hardship trial steadfast persevere bear",
    "sabr":         "patient patience sabr endure hardship trial steadfast persevere bear",
    "gratitude":    "grateful gratitude thankful shukr blessings bounty acknowledge",
    "thankfulness": "grateful gratitude thankful shukr blessings bounty acknowledge",
    "justice":      "justice adl equity fair rights equal wrongdoing oppression",
    "oppression":   "oppression injustice zulm wrongdoer tyranny transgress unjust",
    "arrogance":    "arrogance pride kibr haughty iblis refuse submit disdain boast",
    "pride":        "arrogance pride kibr haughty iblis refuse submit disdain boast",
    "humility":     "humility humble modest submit bow servant worship lowly",
    "honesty":      "honesty truthful sincere trust faithful covenant promise",
    "hypocrisy":    "hypocrisy hypocrite munafiq two-faced insincere conceal pretend",
    "envy":         "envy jealousy hasad covet desire hatred wish ill",
    "anger":        "anger wrath fury restrain forgive control nafs soul",
    "greed":        "greed miserly hoard wealth stingy withhold spend poor",
    "generosity":   "generous give spend charity sadaqa wealth poor needy righteous",
    "lying":        "lying lie falsehood kdhib deceive false truth sincerity",
    "truth":        "truth truthful sincere honest righteous faithful covenant",

    # Spiritual & inner life
    "heart":        "heart qalb soul inner sealed hardened softened consciousness",
    "soul":         "soul nafs self person spirit heart inner life death",
    "spirit":       "spirit soul ruh heart inner life divine breath",
    "tawakkul":     "trust reliance tawakkul rely depend Allah suffices guardian",
    "trust":        "trust reliance tawakkul rely depend Allah suffices guardian",
    "dhikr":        "remembrance dhikr mention glorify consciousness heart peace",
    "remembrance":  "remembrance dhikr mention glorify Allah consciousness heart peace",
    "taqwa":        "taqwa piety consciousness fear Allah righteous mindful aware",
    "piety":        "taqwa piety consciousness fear Allah righteous mindful aware",
    "sincerity":    "sincerity ikhlas pure intention heart worship",
    "purification": "purification tahara clean purity ritual wash prayer",
    "fear":         "fear awe khashya taqwa consciousness Allah dread reverence",
    "hope":         "hope raja mercy forgiveness trust Allah good expectation",
    "love":         "love beloved wud merciful kind compassion affection",
    "contentment":  "contentment satisfaction tranquility sakina heart peace trust",
    "heedlessness": "heedless ghafla negligent forget remember consciousness heart",
    "success":      "success falah prosper righteous believers paradise achieve",

    # Afterlife & eschatology
    "paradise":     "paradise jannah garden reward rivers bliss eternal righteous",
    "jannah":       "paradise jannah garden reward rivers bliss eternal righteous",
    "hellfire":     "hellfire jahannam punishment torment fire blaze warning sinners",
    "hell":         "hellfire jahannam punishment torment fire blaze warning sinners",
    "death":        "death dying mawt soul afterlife appointed time every soul taste",
    "resurrection": "resurrection qiyama raising dead day judgment assembled",
    "judgment":     "judgment day reckoning qiyama account deeds scales weighing",
    "reckoning":    "reckoning hisab account judgment deeds record weighing scales",
    "hereafter":    "hereafter afterlife akhira resurrection judgment paradise hell",
    "akhira":       "hereafter afterlife akhira resurrection judgment paradise hell",
    "intercession": "intercession shafaa intercede permission day judgment Allah",
    "angels":       "angels malaika gabriel jibreel revelation wings worship record",
    "signs":        "signs ayat creation proof evidence observe reflect creation",
    "miracles":     "miracle signs proof messenger staff sea fire resurrection",

    # Prophets & revelation
    "prophet":      "prophet messenger revelation sent guidance Muhammad Ibrahim Musa",
    "messenger":    "messenger prophet rasul sent revelation guidance Muhammad",
    "muhammad":     "Muhammad prophet messenger seal Islam revelation Quran",
    "ibrahim":      "Ibrahim Abraham prophet fire monotheism hajj kaaba submission",
    "musa":         "Musa Moses pharaoh Bani Israel Torah miracles staff sea",
    "isa":          "Isa Jesus prophet miracle Mary Maryam disciples gospel",
    "noah":         "Noah Nuh flood ark people disbelief saved",
    "quran":        "Quran recitation revelation book guidance light clear",
    "revelation":   "revelation wahy quran book guidance prophet sent",
    "guidance":     "guidance huda path straight truth light quran messenger",
    "scripture":    "scripture book quran torah injeel revelation guidance",
    "knowledge":    "knowledge ilm learn understand wisdom scholars aware informed",
    "wisdom":       "wisdom hikma knowledge understanding intellect reflect ponder",

    # Society & law
    "marriage":     "marriage nikah spouse wife husband family relationship consent",
    "divorce":      "divorce talaq separation marriage wife husband iddah",
    "orphan":       "orphan yatim protect care property guardian rights vulnerable",
    "parents":      "parents mother father honor obey kindness respect filial",
    "family":       "family marriage children parents kinship ties household kin",
    "children":     "children sons daughters offspring family raise nurture",
    "women":        "women wife mother daughter rights dignity marriage inheritance",
    "wealth":       "wealth property mal spend charity zakat poor give hoard",
    "money":        "wealth property money spend charity zakat poor give hoard",
    "trade":        "trade commerce honest contract fair weights measure debt",
    "usury":        "usury riba interest forbidden trade commerce transaction",
    "food":         "food eat lawful halal forbidden haram slaughter permitted",
    "inheritance":  "inheritance wealth property orphan parents spouse rights",
    "unity":        "unity together ummah brotherhood divide factions rope hold fast",

    # Nature
    "water":        "water rain river sea spring cloud pour life resurrection",
    "rain":         "rain water cloud pour sky earth vegetation life mercy",
    "creation":     "creation created heavens earth signs universe mankind khalq",
    "nature":       "nature creation signs sky earth sun moon stars mountains",
    "animals":      "animals cattle birds creatures creation stewardship signs",
    "sun":          "sun moon stars signs creation light day night universe",
    "earth":        "earth land creation signs mountains rivers valleys",
    "sky":          "sky heavens creation signs stars universe firmament",
    "night":        "night day alternation signs creation darkness light",

    # Conflict & struggle
    "jihad":        "jihad striving effort struggle path Allah sacrifice wealth life",
    "war":          "war battle fighting qital defense aggression peace justice",
    "peace":        "peace salam submission reconcile treaty cease hostility",
    "migration":    "migration hijra exile sacrifice home path Allah muhajir",
    "oppressed":    "oppressed weak poor vulnerable mustadafin protect save rescue",
    "trial":        "trial test ibtila hardship patience endurance believers affliction",
    "striving":     "strive effort jihad path Allah sacrifice persist struggle",

    # Covenant & promise
    "covenant":     "covenant promise pledge ahd agreement fulfill broke obligation",
    "promise":      "promise covenant ahd pledge fulfill broke trust agreement",
    "accountability": "accountability reckoning hisab deeds judgment reward punish",
}


# ── Commentaries (unchanged from v4, retained in full) ───────────────────────
STATIC_COMMENTARIES = {
    "mercy and forgiveness": """
The concept of mercy (رحمة) is arguably the most pervasive theme in the Quran, introduced in the very first verse of Al-Fatiha and repeated in the opening of 113 of the 114 surahs. It is not merely an attribute of Allah — it is the lens through which the entire revelation is framed.

In the early Meccan surahs, mercy appears as a deeply personal and intimate divine quality. The short, intense surahs of this period emphasize Allah's mercy toward the vulnerable — orphans, the poor, the oppressed — and warn those who deny it. The tone is urgent, almost intimate, speaking directly to individual conscience.

By the Medinan period, mercy expands into a communal and legal framework. Forgiveness becomes tied to repentance (توبة), to community relations, and to specific conditions. The Quran in Madinah addresses not just individual hearts but a society being built — and mercy becomes the ethical foundation of its laws, its treatment of enemies, and its internal relations.
    """.strip(),

    "day of judgment": """
The Day of Judgment (يوم القيامة) is one of the most central themes of Quranic revelation, with the early Meccan surahs dedicated almost entirely to its vivid and urgent depiction. The short, powerful surahs of the first Meccan period — Al-Qari'ah, At-Takwir, Al-Infitar — paint the Day in dramatic cosmic terms: mountains moved, seas boiled, souls held to account before Allah.

The Meccan treatment serves a theological purpose: to shake the conscience of a society that denied accountability. The imagery is visceral and personal — every soul standing alone before Allah, no tribe or wealth to intercede.

In the Medinan period, the Day of Judgment recedes slightly from center stage but deepens in legal and communal significance. The focus shifts to preparation — prayer, charity, just conduct — as the means of standing well before Allah on that Day. The urgency remains but is channeled into practical guidance for a community living in history, not just awaiting its end.
    """.strip(),

    "repentance": """
Repentance (التوبة) in the Quran is not a peripheral theme — it is one of the most theologically central, touching on the nature of Allah, the nature of the human being, and the relationship between them. The Quran's treatment of repentance is notably generous and psychologically sophisticated.

In the Meccan period, repentance appears primarily as an urgent invitation to those who have rejected the message. The early surahs call on the Quraysh to turn back to Allah before punishment comes — repentance here is presented as a door still open, a mercy still available. The tone is urgent but genuinely hopeful.

In Madinah, repentance becomes more institutionalized — tied to specific acts of expiation (كفارة), to community reconciliation, and to the ongoing life of a believing community that inevitably falls short. The famous ninth surah, At-Tawbah, addresses both the communal and individual dimensions of turning back to Allah after failure.
    """.strip(),

    "guidance and misguidance": """
Guidance (الهدى) and its opposite, misguidance (الضلال), constitute one of the central polarities of Quranic discourse — the axis around which the entire narrative of human existence turns. The Quran's treatment of this theme is theologically subtle, refusing both pure determinism and pure human autonomy.

In the Meccan period, guidance appears as the primary gift the revelation offers — a light in darkness, a clear path in confusion. The early Meccan Ayaat present the Quran itself as guidance (هدى للمتقين) and describe those who reject it as having sealed their own hearts against Allah's light.

The Medinan period engages with guidance in more communal and historical terms. The guided community has responsibilities — to maintain justice, to call others to the path of Allah, to embody the guidance they have received. The Medinan Ayaat on misguidance are often specific — particular groups, particular historical moments, particular forms of deviation from the straight path.
    """.strip(),

    "covenant and promise": """
The concept of covenant (العهد) runs through the Quran as one of its most structurally significant themes — the covenant between Allah and humanity, between Allah and the prophets, between Allah and the Children of Israel, and between believers and their Lord.

In the Meccan period, covenant appears primarily in its primordial form — the original covenant in which all of humanity acknowledged Allah's lordship before entering the world. This pre-existence covenant is the theological ground of human accountability: every human being has already acknowledged Allah, and life is the test of that acknowledgment.

In Madinah, covenant becomes historical and legal — the covenants made with the Children of Israel and their breaking, the covenants made with the Muslims of Madinah, the treaty obligations toward non-Muslims. The Medinan revelation is intensely concerned with covenant-keeping as the foundation of a functional society built on trust in Allah.
    """.strip(),

    "trust and hypocrisy": """
The phenomenon of hypocrisy (النفاق) is almost exclusively a Medinan concern — it barely appears in the Meccan revelation, for the simple reason that in Makkah, professing Islam brought persecution rather than advantage. It was only in Madinah, when the Muslim community became a political and social force, that insincere profession of faith before Allah became a significant challenge.

The Meccan treatment of what might be called proto-hypocrisy focuses on the general human tendency toward self-deception — claiming belief while the heart is absent from Allah, performing worship for show rather than sincerity. These are universal warnings rather than descriptions of a specific group.

The Medinan revelation dedicates entire passages — most famously the long sections of Surah At-Tawbah — to describing, diagnosing, and warning against hypocrisy. The Quran's response is remarkable: it describes the hypocrites' psychology with extraordinary accuracy while holding open the door of genuine repentance and return to Allah even for the most committed among them.
    """.strip(),

    "remembrance of god": """
Remembrance of Allah (ذكر الله) occupies a place in Quranic spirituality that is difficult to overstate — it is presented not merely as one devotional practice among many but as the very substance of the believing life, the activity that gives all other activities their meaning and orientation toward Allah.

In the Meccan surahs, remembrance appears as the antidote to the heedlessness (غفلة) that characterizes those who turn away from Allah. The early Meccan Ayaat on remembrance are concentrated and powerful: "Verily, in the remembrance of Allah do hearts find rest" encapsulates the Meccan understanding — remembrance is not just religious obligation but psychological necessity.

The Medinan revelation institutionalizes remembrance — the prayer times, the formulas to be said in specific circumstances, the remembrance to be performed after prayer. But it also expands the concept: remembrance of Allah infuses the whole of life. The believer who conducts trade, raises children, and governs a community — all while maintaining consciousness of Allah — embodies the Medinan understanding of remembrance as the quality that makes all action sacred.
    """.strip(),

    "divine oneness": """
The doctrine of divine oneness (التوحيد) is the theological core of the Quran — the idea that Allah is one, without partner, without equal, without offspring, without intermediary. Every other Quranic theme flows from or returns to this central claim about the nature of Allah.

The Meccan revelation is almost entirely devoted to establishing and defending tawhid against the polytheism of the Quraysh. The arguments are varied and sustained — cosmological (who created the heavens and earth?), moral (can those who associate partners with Allah be equal to those who do not?), historical (every prophet taught the same message of Allah's oneness).

The Medinan period assumes tawhid rather than arguing for it — the community of believers has accepted the premise and now lives out its implications. Tawhid in Madinah expresses itself in the rejection of all competing loyalties that might rival Allah's claim, in the understanding that all legislation belongs to Allah alone, and in the communal practices of prayer and worship that enact the community's submission to the One.
    """.strip(),

    "patience and hardship": """
Patience (صبر) is one of the most frequently commanded virtues in the Quran, appearing in contexts of personal trial, communal conflict, and spiritual growth. Its treatment across the revelation timeline shows a remarkable evolution from intimate personal command to communal principle — always grounded in trust in Allah.

In the early Meccan surahs — revealed during a period of intense persecution — patience is a survival command. The believers are few, vulnerable, and pressured to abandon their faith. The Quran speaks directly: hold firm, endure, Allah is with those who are patient. The tone is deeply personal and urgent.

As the community grows and moves to Madinah, patience expands in meaning. It becomes tied to governance, to warfare, to community disputes, and to the long patience required in building a just society pleasing to Allah. The Medinan Ayaat on patience are less about enduring oppression and more about the sustained patience of a people responsible for each other and for justice before Allah.
    """.strip(),

    "gratitude": """
Gratitude (الشكر) in the Quran is not merely a social virtue but a theological stance — the appropriate response of the creature to Allah the Creator, the recognition that all good ultimately comes from Him. The Quran's treatment of gratitude is consistent across the revelation while varying in emphasis and context.

In the Meccan period, gratitude appears as one of the defining characteristics of the believer — as opposed to the ingratitude (كفر, which also means disbelief) of those who reject the message of Allah. The early Meccan Ayaat on gratitude are embedded in the broader argument for monotheism: if Allah has given you everything, how can you direct your worship to other than Him?

The Medinan treatment of gratitude expands into specific domains — gratitude for the gift of the Quran from Allah, gratitude expressed through using wealth justly, gratitude for victory expressed through increased worship. The famous verse "If you are grateful, I will increase you" becomes in the Medinan context a principle of communal as well as individual life before Allah.
    """.strip(),

    "justice and oppression": """
Justice (عدل) and its opposite, oppression (ظلم), form one of the great moral axes of Quranic teaching. What is striking is how consistently the Quran frames injustice not merely as a social problem but as a theological one — oppression is ultimately directed against Allah's order.

In the Meccan period, justice appears primarily in its absence — the Quran condemns the oppression of the weak, the denial of rights to orphans and the poor, the arrogance of the powerful before Allah. The tone is prophetic and confrontational, addressed to a society the Quran is challenging root and branch.

In Madinah, justice becomes constructive. The revelation now addresses a community with the power to implement the justice of Allah — in family law, in trade, in governance, in warfare. The Medinan Ayaat on justice are detailed, specific, and practical. The shift from condemning injustice to building just institutions is one of the most significant thematic developments across the full Quranic timeline.
    """.strip(),

    "the heart": """
The heart (القلب) in the Quran is not merely a physical organ but the seat of moral and spiritual consciousness — the locus of faith in Allah, intention, perception, and accountability. The Quran's treatment of the heart constitutes a complete psychology of the spiritual life.

In the Meccan period, the heart appears primarily in its capacity for openness or closure to the divine message from Allah. Hearts that are sealed, hearts that are hardened, hearts that are diseased — these characterizations of those who reject the message are among the most distinctive features of the Meccan psychological vocabulary.

The Medinan treatment of the heart expands into the territory of communal and moral psychology. Hearts that harbor grudges, hearts that incline toward the hypocrites, hearts that are moved by the recitation of Allah's words — these are the hearts of a community managing the full complexity of collective life. The Medinan Quran is intensely interested in the hidden motivations of community members, knowing that a community's justice before Allah depends as much on its members' hearts as on the quality of its laws.
    """.strip(),

    "satan and temptation": """
The Quran's portrayal of Iblis (Satan) and the phenomenon of temptation (الوسوسة) is one of the most psychologically sophisticated threads in the entire text. Unlike a simple good-versus-evil narrative, the Quran presents the Satanic challenge as fundamentally about the human capacity for self-deception and turning away from Allah.

The story of Iblis's refusal to prostrate before Adam — told multiple times in the Meccan surahs — is the Quran's foundational account of how pride and arrogance corrupt even a being of immense worship of Allah. Iblis's sin is not strength but a subtle form of self-righteousness: "I am better than him." The Meccan repetition of this story warns all humans that the same error of turning from Allah is always available to them.

In Madinah, the treatment of Satanic temptation becomes more practical and communal. The Quran warns against the whispers that divide communities, the temptations that corrupt financial dealings, the pride that prevents reconciliation. Satan in Madinah is less the cosmic rebel of the Meccan narratives and more the quiet voice that justifies injustice and sows discord among those who should be united before Allah.
    """.strip(),

    "arrogance and pride": """
Arrogance (الكبر) occupies a unique place in the Quranic moral taxonomy — it is not merely one sin among many but the root from which most other sins grow, and the fundamental attitude that prevents submission to Allah. The Quran's treatment of arrogance is consistent and uncompromising across the entire revelation.

The Meccan period identifies arrogance as the fundamental reason for rejection of the prophetic message from Allah. The Quraysh did not merely disbelieve — they considered belief beneath them. The early Meccan Ayaat on arrogance are pointed and devastating: those who turn away from Allah's signs out of pride are promised the worst of outcomes. Iblis himself is presented as the prototype of the arrogant: his sin was not ignorance but the refusal to submit to Allah's command.

In Madinah, arrogance appears in more specific social forms — the arrogance of those who use their wealth to oppress, the arrogance of tribal leaders who resist the leveling implications of Islamic community before Allah, the arrogance of hypocrites who consider themselves above accountability. The Medinan treatment of arrogance is more sociological, diagnosing its specific manifestations in a community navigating the transition from tribal hierarchy to divine law.
    """.strip(),

    "women and rights": """
The Quran's address to women and its establishment of their rights represents one of the most significant aspects of the Medinan revelation, coming into a society where women had minimal legal standing before Allah or man. The Quranic treatment is not uniform across the revelation — it develops progressively as the community gains the capacity to implement change.

In the Meccan period, women appear primarily in theological and moral contexts. The Quran condemns the burying of infant daughters as one of the gravest crimes before Allah, establishes the equal spiritual accountability of men and women before Him, and presents women — Mary, the wife of Pharaoh — as models of faith in Allah. The early Meccan treatment is fundamentally about the equal spiritual dignity of women before Allah.

The Medinan revelation translates this spiritual equality into legal rights — the right to own property, to inherit, to consent to marriage, to initiate divorce, to receive financial support. These were not abstract principles but enforceable legal changes to existing Arabian custom. The famous verse "and women have rights similar to those over them in kindness" encapsulates the Medinan approach: grounding women's rights in the same ethical framework of justice before Allah that governs all human relations.
    """.strip(),

    "children and orphans": """
The protection of children, and especially orphans (اليتامى), is one of the most persistent and emotionally charged themes across the entire Quran. It appears from the earliest Meccan surahs to the final Medinan legislation, suggesting its centrality to the Quranic moral vision of justice before Allah.

In the Meccan period, the treatment of orphans is used as a moral litmus test — the measure by which the sincerity of religious claim before Allah is judged. The devastating short surah Al-Ma'un opens: "Have you seen the one who denies the religion? That is the one who drives away the orphan." Faith in Allah that does not protect the vulnerable is, the Quran insists, no faith at all.

In Madinah, orphan protection becomes legally detailed. The Quran legislates how orphans' property must be managed, warns against consuming it unjustly before Allah, establishes guardianship rules, and creates inheritance protections. The shift from moral condemnation to legal protection mirrors the broader Medinan pattern — the Quran moves from naming wrongs to building institutions that prevent them.
    """.strip(),

    "family and community": """
Family and community relations occupy a substantial portion of the Medinan revelation, reflecting the Quran's understanding that faith in Allah is not merely private but is expressed and tested in the web of human relationships.

The Meccan Ayaat on family focus on its most fundamental ethical claims before Allah — honoring parents, protecting orphans, maintaining ties of kinship. These are presented as moral absolutes, violations of which are among the gravest sins before Allah. The Meccan treatment is ethical and absolute.

The Medinan revelation addresses family in extraordinary detail — marriage, divorce, inheritance, the rights of women, the treatment of orphans' property, the obligations between spouses. What is remarkable is the consistency of the underlying principle: the family is the primary site of justice or injustice before Allah, and the Quran legislates it with the same seriousness as it legislates governance and trade.
    """.strip(),

    "trade and honesty": """
The Quran's engagement with trade and commercial life is far more extensive than is commonly recognized — reflecting the mercantile culture of seventh-century Arabia and the Quran's insistence that economic relations are a domain of accountability before Allah, not merely human convention.

In the Meccan period, commercial dishonesty — particularly short-weighting in trade — is condemned in terms that link it directly to disbelief in the Day of Judgment before Allah. The surah Al-Mutaffifin opens with a devastating portrait of the dishonest trader, framing his dishonesty as rooted in his denial of accountability before Allah. The Meccan treatment ties commercial ethics directly to theological conviction.

The Medinan period legislates commercial life in detail — contracts must be written, witnesses must be present, debts must be honored, usury is prohibited by Allah. The famous "debt verse" (2:282), the longest verse in the Quran, is entirely concerned with the proper documentation of financial transactions as a duty before Allah. The Quran's move from condemning dishonest traders to legislating honest commerce reflects the transition from a prophetic community to a governing one.
    """.strip(),

    "wealth and charity": """
The Quran's treatment of wealth (المال) occupies a carefully calibrated middle position that acknowledges wealth as a gift from Allah while insisting on its social obligations. This theme is among the most practically significant in the revelation.

In the Meccan period, the condemnation of wealth misused is sharp and uncompromising. The short Meccan surahs targeting the hoarding of wealth — Al-Humazah, At-Takathur, Al-Ma'un — are among the most rhetorically powerful in the Quran. They condemn not wealth itself but the attitude that wealth is a private achievement rather than a trust from Allah.

In Madinah, the treatment of wealth becomes legislative and institutional. Zakat is formally mandated by Allah, inheritance laws are detailed, the prohibition of riba (usury) is established, and charitable spending is tied to specific rewards and consequences. The shift from prophetic condemnation to legal regulation reflects the Quran's movement from challenging a corrupt order to building a just one pleasing to Allah.
    """.strip(),

    "food and lawful eating": """
The Quranic legislation around food (الطعام) and what is lawful (الحلال) before Allah to eat is one of the clearest examples of the revelation's movement from broad ethical principles to specific legal rulings — and of its concern with every dimension of human life as an act of worship of Allah.

In the Meccan period, food appears primarily in the context of theological argument. The Quraysh had imposed various food taboos — certain animals forbidden, certain foods reserved for idols — that the Quran challenges as baseless human invention against the freedom Allah has given. The Meccan treatment is liberatory: Allah has created good things for you, and the fabrication of additional prohibitions is a form of associating partners with Allah in legislation.

The Medinan period introduces specific divine legislation around food — the prohibition of carrion, blood, pork, and animals slaughtered in the name of other than Allah. This legislation is not a contradiction of the Meccan liberatory tone but its completion: Allah's own legislation replaces the arbitrary human taboos the Quran condemned in Makkah.
    """.strip(),

    "unity and division": """
Unity (الوحدة) and the danger of division (الفرقة) are themes with direct relevance to the lived situation of the early Muslim community — and the Quran's treatment of them is both spiritually profound and practically urgent, rooted in submission to Allah alone.

The Meccan surahs ground unity theologically — monotheism (توحيد) is not just a statement about Allah but a template for human community. The community that worships Allah alone, acknowledges one truth, and submits to one authority has a coherence that polytheism cannot achieve. The Meccan treatment of unity is fundamentally theological.

In Madinah, unity becomes a community management challenge. The Quran addresses factionalism, the danger of following multiple leaders, the damage done by rumor and suspicion, the necessity of reconciliation between believers who quarrel. The famous command "Hold fast to the rope of Allah all together and do not be divided" is addressed to a community actively experiencing the centrifugal forces of tribal loyalty and personality disputes.
    """.strip(),

    "prayer and worship": """
Prayer (الصلاة) occupies a unique place in the Quran — it is both a specific ritual practice and a symbol of the entire relationship between the human and Allah. Its treatment across the revelation reflects both the gradual formation of Islamic practice and the deepening of its spiritual meaning as connection to Allah.

In the early Meccan period, prayer appears in its most intimate and urgent form. Before the formal five daily prayers were legislated, the believers are commanded to pray at night, to remember Allah constantly, to turn toward Him amid persecution. These early references to prayer are about orientation — the heart turned toward Allah in a hostile world.

In Madinah, prayer becomes a fully legislated communal institution with specific times, directions, conditions, and congregational requirements. Yet even in Madinah, the Quran never loses sight of the inner dimension — prayer that is performed without presence of heart before Allah is condemned as ostentatious and hollow.
    """.strip(),

    "knowledge and wisdom": """
Knowledge (علم) is among the most frequently occurring concepts in the Quran, appearing in hundreds of forms across the full corpus. This is not accidental — the very first word revealed by Allah was "Read" (اقرأ), framing the entire revelation as an act of knowing Allah and His creation.

In the Meccan period, knowledge appears primarily as a divine attribute of Allah and as the criterion between those who see and those who are blind. Allah's knowledge is unlimited; human knowledge is derivative and humble. The Meccan Ayaat challenge the Quraysh's false confidence with the claim that true knowledge belongs to Allah alone.

The Medinan period adds a practical and communal dimension to knowledge. Knowledge of divine law, of one's obligations before Allah, of the rights of others — this is the knowledge Madinah requires. The Quran in this period frequently invokes knowledge in the context of legal rulings: "those who know are not equal to those who do not know." Wisdom becomes not just theological insight but the lived ability to act justly before Allah in a complex community.
    """.strip(),

    "prophets and messengers": """
The Quran's treatment of the prophets (الأنبياء) is one of its most extended and carefully developed themes, spanning the entire revelation. The prophets serve simultaneously as historical examples, theological arguments, and personal models of submission to Allah.

In the Meccan period, the stories of the prophets serve a primary consolation function. Muhammad ﷺ and his small community faced rejection, mockery, and persecution — and the Quran responds by showing them that every prophet sent by Allah faced the same. Noah was mocked, Ibrahim was cast into fire, Musa was opposed by Pharaoh. The repetition of these narratives is deliberate: you are not alone, this is the pattern of those who carry Allah's message.

In Madinah, the prophet narratives take on legislative and communal dimensions. The story of Ibrahim becomes the basis of Hajj and the Qibla. The story of Dawud and Sulayman speaks to governance and justice. The Medinan treatment of prophethood is less about emotional consolation and more about establishing prophetic authority as the source of law and community order from Allah.
    """.strip(),

    "fasting and self-discipline": """
Fasting (الصيام) in the Quran is presented as far more than a physical abstention — it is a comprehensive discipline of the self, a training of the will, and a communal act of solidarity and worship of Allah that levels all social distinctions.

The Meccan period establishes the spiritual logic of fasting before its legal forms are detailed — self-restraint, consciousness of Allah, and the development of inner discipline appear throughout the Meccan surahs in connection with prayer and night vigil. The Meccan believer was being formed in habits of self-control before Allah that would later find institutional expression.

The Medinan legislation of Ramadan fasting (2:183-187) is among the most carefully worded legal passages in the Quran. The famous verse "O you who believe, fasting has been prescribed for you as it was prescribed for those before you, so that you may become conscious of Allah" places the legislation in historical continuity with previous revelations and grounds it explicitly in its spiritual purpose: not the hunger itself but the taqwa — the consciousness of Allah — it cultivates.
    """.strip(),

    "pilgrimage and sacred places": """
The pilgrimage (الحج) and the sacred places of Makkah — the Kaaba, the Masjid al-Haram, the hills of Safa and Marwa — occupy a distinctive place in the Quran that connects theology, history, law, and identity in their relation to Allah in ways that no other theme quite does.

In the Meccan period, the sacred character of Makkah is asserted theologically — it is the site of the primordial sanctuary (البيت الحرام), established by Ibrahim and Ismail as the house of Allah's worship, the center toward which worship of Allah is directed. The Meccan Ayaat on the sacred sites are primarily theological, establishing their significance as the house of Allah rather than legislating their rituals.

The Medinan revelation legislates the pilgrimage in considerable detail — its timing, its rites, its conditions, its spiritual intentions as worship of Allah. The transformation of what had been a pre-Islamic Arabian pilgrimage into an Islamic institution is one of the most striking examples of the Quran's approach to existing cultural practice: retaining the form, purifying the content, and infusing the whole with the meaning of submission to Allah alone.
    """.strip(),

    "supplication and prayer": """
Supplication (الدعاء) — direct personal address to Allah — is one of the most intimate dimensions of Quranic spirituality, and its treatment reveals much about the Quran's understanding of the human-divine relationship with Allah.

In the Meccan period, supplication appears primarily in its most urgent and elemental form — the cry of the desperate to Allah, the prayer of those with nowhere else to turn. The Quran notes with characteristic irony that even those who deny Allah call upon Him when they are in danger at sea — and forget Him when they reach safety. The Meccan treatment of supplication is about the fundamental human dependency on Allah that polytheism obscures but crisis reveals.

The Medinan revelation provides the community with specific formulas of supplication to Allah — after prayer, at the beginning and end of actions, in situations of fear or need. The famous supplication of Ibrahim in Surah Ibrahim and the supplication at the end of Al-Baqarah are among the most beloved passages in the Quran precisely because they model the posture of complete dependence on and trust in Allah that the Quran cultivates throughout.
    """.strip(),

    "paradise": """
Paradise (الجنة) in the Quran is far more than a reward — it is a statement about the ultimate nature of existence and the character of Allah. Its Quranic treatment moves between the vivid and sensory to the profoundly spiritual encounter with Allah.

The Meccan surahs describe paradise in rich, sensory detail — gardens, flowing rivers, companions, shade, peace given by Allah. This was deliberate: speaking to a desert people who knew the harshness of thirst and heat, the Quran paints the ultimate fulfillment of every human longing as a gift from Allah. The early Meccan descriptions are among the most beautiful passages in Arabic literature.

The Medinan period adds ethical and communal depth to paradise. Entry becomes tied not just to belief in Allah but to specific conduct — justice, charity, fulfilling covenants, maintaining family ties. Paradise in Madinah is earned through a life lived in a community pleasing to Allah, not just a heart that believed. The two treatments together form a complete picture: paradise as both the deepest human fulfillment and the ultimate fruit of righteous living before Allah.
    """.strip(),

    "hellfire and punishment": """
The Quran's treatment of hellfire (النار, جهنم) is among its most vivid and sustained themes, serving theological, moral, and pastoral functions that vary significantly across the Meccan and Medinan periods — always in the context of Allah's perfect justice.

The Meccan surahs describe hellfire in visceral, immediate terms — its heat, its depths, its inhabitants, its contrast with the paradise Allah has prepared. This vividness served a specific theological purpose: to make real to a society that denied the afterlife the consequences of that denial before Allah. The Meccan treatment of hellfire is inseparable from the Meccan treatment of the Day of Judgment — both function as arguments for moral accountability before Allah.

In Madinah, the treatment of hellfire becomes more nuanced and legally grounded. Specific sins are linked to specific punishments; the conditions for its avoidance through obedience to Allah are spelled out; and the theme of Allah's mercy tempering His justice becomes more prominent. The Medinan revelation also introduces the concept of intercession — the possibility of Allah's mercy intervening in the process of judgment.
    """.strip(),

    "death and dying": """
Death (الموت) in the Quran is not treated as an ending but as a threshold — the most significant transition in existence, the moment when the veil between the seen and unseen world of Allah is lifted.

In the Meccan surahs, death is predominantly eschatological — the gateway to the Day of Judgment before Allah, the moment of reckoning that the Quraysh denied and the Quran insisted upon. The early Meccan treatment is confrontational: you will die, you will be raised, you will stand in account before Allah. Every soul will taste death — this universality is stated as both theological fact and moral equalizer before Allah.

In Madinah, the treatment of death deepens into pastoral and communal territory. Death in battle for the cause of Allah, the death of loved ones, the question of those who die before accepting the message — these specific circumstances arise in the Medinan context and the Quran addresses them with both theological clarity and genuine pastoral tenderness. The famous consolation "We belong to Allah and to Him we return" becomes in Madinah not just a theological statement but a liturgical formula for grief.
    """.strip(),

    "angels": """
Angels (الملائكة) occupy a distinctive place in Quranic theology — they are not merely supernatural beings but theological statements about the nature of the relationship between Allah and His creation, the mechanics of revelation, and the administration of the cosmos and the afterlife.

In the Meccan period, angels appear primarily in their cosmological and revelatory roles. They carry the divine revelation of Allah, they witness human deeds, they will be present at the Day of Judgment. The early Meccan Ayaat establish angels as the intermediaries between the transcendent Allah and the created order.

The Medinan period adds narrative and legal dimensions to the treatment of angels. The angels who visited Ibrahim and Lut as messengers of Allah, the angelic support of the believers at Badr, the angels assigned to record human deeds — these appear in greater narrative detail in the Medinan revelation. The angels also appear in the context of prophetic protection and divine support from Allah for the emerging Muslim community.
    """.strip(),

    "prayer for the dead": """
The Quran's treatment of death, burial, and prayer for those who have passed reflects a community actively navigating the pastoral challenges of loss — and the theological questions that death raises about Allah's mercy, human accountability, and the fate of those who die before or outside the message.

The early Meccan treatment focuses on the universality of death as a theological equalizer before Allah — all will die, all will be raised, all will be judged by Allah. The pastoral dimension is less prominent because the Meccan community was small and focused primarily on the theological argument for the afterlife against those who denied it entirely.

The Medinan revelation addresses the pastoral and legal dimensions of death in considerable detail — the treatment of the body, the prayer for the deceased asking Allah's mercy, the question of praying for hypocrites, the fate of those who died before the revelation reached them. The famous prohibition on praying for the hypocrites and its contrast with the prayer for sincere believers shows how deeply the Quran engaged with the specific pastoral challenges of the Medinan community.
    """.strip(),

    "signs and miracles": """
The concept of signs (آيات) — both natural signs and miraculous events — is one of the most structurally important in the Quran, because the word used for a verse of scripture is the same word used for a sign of Allah in the natural world. The Quran presents itself as one sign among many, the verbal parallel of the signs written by Allah in creation.

In the Meccan period, the argument from signs of Allah is central to the theological case for monotheism. The sun, moon, rain, human birth, the alternation of night and day — all are presented as signs pointing toward Allah the one Creator. The Meccan Ayaat on signs are an extended invitation to observation and reflection as paths to faith in Allah: why do you not look at what is around you and recognize its Author?

The Medinan treatment of signs includes the miraculous signs given to prophets by Allah — the staff of Moses, the healing of Jesus, the miracles of Ibrahim — in the context of establishing prophetic authority. The Medinan community needed to understand not just that Allah exists but that specific prophets were genuinely sent by Him — and the signs given to prophets are the Quranic evidence for that claim.
    """.strip(),

    "nature and creation": """
The natural world occupies an extraordinary place in the Quran — not as mere backdrop but as an active sign (آية) of Allah pointing toward the divine. The same word used for a verse of the Quran is used for a sign of Allah in nature: both are ayaat, manifestations of the same reality of Allah.

The Meccan surahs are saturated with natural imagery: the sun and moon in their courses by the command of Allah, the alternation of night and day, rain bringing dead earth to life, the creation of the human being from humble origins. This is theology through observation — the Quran invites its audience to look at what Allah has created around them and recognize the fingerprints of the divine.

In Madinah, natural signs of Allah continue to appear but increasingly in the context of human responsibility toward the created world, toward the poor, and toward stewardship. The theological use of nature shifts slightly toward the ethical — the same Allah who sends rain and grows crops is the Allah who commands justice toward those who depend on that rain and those crops.
    """.strip(),

    "water and rain": """
Water (الماء) in the Quran is one of the most richly symbolic natural elements — simultaneously a physical necessity from Allah, a sign of His power, and a metaphor for life, mercy, and resurrection.

In the Meccan surahs, water appears primarily as a sign of Allah — the rain that falls from the sky by Allah's command and brings dead earth to life is presented as evidence of Allah's power and as a prefiguration of the resurrection of the dead. The analogy is made explicit repeatedly: just as Allah revives dead earth with rain, so will He revive the dead on the Day of Judgment.

In Madinah, water retains its theological significance as a sign of Allah but also takes on narrative depth — the water of the rivers of paradise that Allah has prepared, the water withheld as punishment from destroyed nations, the water of the covenant. The Medinan treatment of water is richer in narrative specificity, connecting the natural sign of Allah to historical stories and eschatological promise.
    """.strip(),

    "creation of humans": """
The Quran's account of human creation (خلق الإنسان) by Allah is one of its most theologically rich themes, touching on the origin, nature, purpose, and dignity of the human being before Allah. The Quran does not give a single linear account of creation but returns to it repeatedly, each time emphasizing a different aspect.

In the Meccan period, the creation of the human being from humble origins by Allah — dust, clay, a clinging clot — is used primarily as an argument against human arrogance. The Quraysh who prided themselves on lineage, wealth, and power are reminded of what Allah made them from. The Meccan treatment of human creation is fundamentally humbling — corrective of the arrogance that forgets its own contingency before Allah.

In Madinah, human creation by Allah is treated in the context of human dignity and responsibility. The human being was created by Allah to be His vicegerent (خليفة) on earth — a being of unique dignity and unique accountability before Allah. The Medinan treatment balances the Meccan humility with a profound affirmation of human significance: small in origin, great in purpose, accountable in the end before Allah.
    """.strip(),

    "animals and living creatures": """
The Quran's treatment of animals and living creatures reflects a consistent theological conviction: all of creation worships Allah, and the human relationship to animals is one of stewardship and accountability before Allah, not absolute dominion.

In the Meccan period, animals appear primarily as signs (آيات) of Allah's power and wisdom — the camel, the bee, the ant, the bird held aloft in the sky by the command of Allah. The Meccan Ayaat on animals invite contemplation: look at these creatures of Allah and recognize the wisdom and power of their Creator. The Quran also gives animals a dignity unusual for its time, most famously in the story of the She-Camel of Thamud whose killing as a challenge to Allah triggers divine punishment.

The Medinan revelation adds legal and ethical dimensions to the human relationship with animals. The rules of lawful slaughter in the name of Allah, the prohibition of specific animals for food, and the general principle that animals may be used for human benefit but not abused reflect a legal framework that takes animal welfare seriously as a religious obligation before Allah. The Quran presents the human being as accountable to Allah not just for how they treat other humans but for how they treat the whole of creation entrusted to them.
    """.strip(),

    "time and history": """
The Quran's engagement with time (الزمان) and historical process is distinctive and profound — it presents history not as random or cyclical but as purposeful and directed by Allah, an arena in which divine will works through human choice toward an inevitable conclusion.

In the Meccan surahs, time appears in two primary registers: the cosmic scale of Allah's creation and the personal scale of human life. The alternation of day and night by Allah's command, the passage of seasons, the brevity of human existence — all are deployed as arguments for reflection and as reminders of human finitude before Allah. The famous oath "By Time" (وَالْعَصْرِ) that opens Surah Al-Asr compresses the entire Quranic philosophy of time into three verses.

The Medinan treatment of time is more historical — the Quran in Madinah is intensely interested in the histories of previous communities, drawing lessons from the rise and fall of nations under Allah's governance, the fate of those who accepted and rejected prophets of Allah, the patterns that repeat across human civilizations. History in the Medinan Quran is not merely narrative but argument: look at what happened to those before you, and understand the laws by which Allah governs human communities.
    """.strip(),

    "patience under trial": """
Trial (الابتلاء) is one of the most theologically significant concepts in the Quran — the Quran presents the entire human experience as a test from Allah, and hardship specifically as a form of divine attention rather than divine abandonment. This reframing of suffering is one of the Quran's most pastorally powerful contributions.

In the Meccan period, trial is experienced directly and immediately by the small believing community. The Quran's response to persecution is not to promise its immediate end but to reframe it: you are being tested by Allah, as every believing community before you was tested. The Meccan Ayaat on trial are characterized by a kind of dignified endurance — the suffering is real, the test from Allah is real, and Allah is watching.

The Medinan revelation develops a more complex theology of trial — distinguishing between the trial of hardship and the trial of ease, warning that prosperity can test a community's faithfulness before Allah as severely as persecution can. The Medinan community, as it grew in power and wealth, needed to understand that success was itself a test from Allah: would they maintain justice and gratitude when they no longer needed to endure?
    """.strip(),

    "war and peace": """
The Quran's engagement with warfare (القتال) in the path of Allah and peace (السلام) is one of its most contextually specific yet theologically coherent themes — the Ayaat on this subject were revealed in response to specific historical circumstances while articulating principles of lasting significance.

The Meccan period is characterized by a deliberate restraint regarding warfare — the believers are commanded to endure, not to retaliate, to respond to aggression with patience before Allah. This is not weakness but a theological position: the early Meccan community lacked the capacity for organized resistance, and the Quran's command to endure was appropriate to that reality while simultaneously forming the character needed for what would come.

The Medinan revelation permits and then regulates warfare in the cause of Allah in considerable detail. The famous permission verse (22:39-40) — "Permission is given to those who fight because they have been wronged" — represents a theological turning point. The Medinan Ayaat on warfare are concerned above all with justice before Allah: who may be fought, how warfare must be conducted, what protections non-combatants retain, and when peace must be pursued. The overall Quranic vision is of warfare as a last resort in the service of justice and Allah's order, never as an end in itself.
    """.strip(),

    "forgiveness between people": """
The Quran's teaching on human forgiveness (العفو) — the forgiveness that people extend to one another as an act pleasing to Allah — is distinct from its teaching on divine forgiveness, and represents one of its most psychologically sophisticated ethical contributions.

In the Meccan period, human forgiveness appears primarily as a response to persecution. The believers are encouraged to respond to the hostility of the Quraysh with forgiveness and overlooking — not because the wrong done to them is unimportant before Allah but because the moral high ground of forgiveness is itself a form of strength and worship of Allah. The early Meccan teaching on forgiveness is countercultural and demanding.

The Medinan revelation adds legal and communal texture to the teaching on forgiveness. The right to retaliate (قصاص) is established by Allah — justice requires that wrongs have consequences — but forgiveness is consistently presented as superior and more pleasing to Allah: "And if you forgive, it is closer to righteousness." The Medinan treatment of forgiveness navigates the tension between the legitimate demands of justice before Allah and the transformative power of mercy.
    """.strip(),

    "migration and exile": """
Migration (الهجرة) for the sake of Allah occupies a place in the Quran that goes far beyond its historical reference to the emigration from Makkah to Madinah — it becomes a theological category, a model of the willingness to sacrifice worldly security for obedience to Allah.

In the Meccan period, migration for the sake of Allah is anticipated rather than legislated — the Quran describes the qualities of those who leave their homes for Allah's sake, and the stories of prophets who were forced from their communities function as models: Ibrahim leaving his people, Musa leaving Egypt. The Meccan treatment of migration is typological, preparing the community to understand their own coming displacement as part of a pattern with deep prophetic roots in service to Allah.

The Medinan revelation engages with migration for the sake of Allah as a concrete, legally significant act. Those who migrated (المهاجرون) have a specific status in the community; their sacrifice for Allah is acknowledged and rewarded; and the principle that one must leave situations of persecution when possible is established as an obligation before Allah. The Medinan teaching on migration is both a recognition of the historical sacrifice made and a universal principle: where Allah's commands cannot be fulfilled, the believer must seek a place where they can be.
    """.strip(),

    "oppressed and vulnerable": """
The Quran's sustained attention to the oppressed and vulnerable — the weak (المستضعفين), the poor, the enslaved, the stranger — is one of its most consistent ethical commitments, rooted in the justice of Allah, present from the earliest Meccan surahs to the final Medinan legislation.

In the Meccan period, the defense of the vulnerable is one of the primary moral charges laid against the Quraysh before Allah. The early short surahs — Al-Fajr, Al-Balad, Ad-Duha, Al-Ma'un — paint a devastating portrait of a society that has abandoned its weakest members while pursuing wealth and status. The Meccan treatment is prophetic and confrontational: Allah is on the side of the oppressed, and those who oppress them are warned of terrible consequences before Him.

The Medinan revelation translates this prophetic solidarity into legal protections. The rights of slaves are expanded and pathways to manumission are multiplied; the poor have legal claims on the wealth of the community through zakat; the stranger and the traveler have rights of hospitality and protection. The Medinan treatment channels the Meccan passion into institutions — a society that genuinely protects its most vulnerable members is, for the Quran, one of the primary marks of a community that has truly submitted to Allah.
    """.strip(),

    "striving and effort": """
The concept of striving (الجهاد) in the path of Allah in the Quran is far broader than its most controversial application — it encompasses the full range of effort expended for Allah's cause, from the internal struggle against the ego to the external struggle for justice in the world.

The Meccan period establishes the internal and spiritual dimensions of striving for Allah. The believers are commanded to strive against their own desires, to endure persecution without retaliation, to persist in worship and remembrance of Allah despite discouragement. This inner jihad — the struggle to maintain faith and moral integrity before Allah under pressure — is the foundation upon which all other forms of striving rest. The Meccan treatment of striving is primarily about character formation before Allah.

The Medinan revelation adds the communal and external dimensions — striving with one's wealth and person in the path of Allah, which in specific historical contexts included armed resistance to aggression. The Medinan Ayaat on striving in the path of Allah are carefully regulated and ethically bounded: striving is legitimate only in response to aggression, must observe specific rules of conduct, and must be oriented toward the restoration of peace and justice before Allah rather than conquest for its own sake.
    """.strip(),

    "accountability and reckoning": """
Accountability (الحساب) before Allah — the divine reckoning of every human deed — is one of the Quran's most insistently repeated themes, functioning as both theological claim and moral motivation. The Quran presents comprehensive divine accountability before Allah not as a threat but as a justice guarantee: nothing is lost before Allah, nothing is hidden from Him, every wrong will be addressed by Him.

In the Meccan period, accountability before Allah appears as the central claim that the Quraysh denied and the Quran insisted upon. The denial of the Day of Reckoning before Allah is, for the Quran, the root of the Quraysh's moral failures — those who believe they will never be called to account before Allah feel free to oppress the weak, hoard wealth, and deny the rights of others. The Meccan argument for accountability before Allah is fundamentally an argument for ethics.

The Medinan treatment of accountability before Allah is more nuanced — the community is taught how to prepare for the reckoning, how to minimize it through specific practices of charity and repentance before Allah, and how to understand the relationship between Allah's perfect justice and His boundless mercy in the final accounting. The Medinan revelation also engages with the question of how Allah will account for those who did not receive the message clearly, reflecting the community's encounter with genuine theological questions arising from their diverse Medinan context.
    """.strip(),
}


# ─────────────────────────────────────────────────────────────────────────────
#  CORE SEARCH ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def load_embeddings():
    global _embeddings_cache, _verse_ids_cache
    print(f"DEBUG load_embeddings called, cache is None: {_embeddings_cache is None}")
    print(f"DEBUG EMBEDDINGS_PATH = {EMBEDDINGS_PATH}")
    if _embeddings_cache is not None:
        return _embeddings_cache, _verse_ids_cache
    
    # Always reload if file changed since last load
    ids_path = EMBEDDINGS_PATH.replace(".npy", "_verse_ids.txt")
    if not os.path.exists(EMBEDDINGS_PATH) or not os.path.exists(ids_path):
        return None, None

    current_mtime = os.path.getmtime(EMBEDDINGS_PATH)
    if _embeddings_cache is not None:
        if hasattr(load_embeddings, '_mtime') and load_embeddings._mtime == current_mtime:
            return _embeddings_cache, _verse_ids_cache

    print(f"  [embeddings] Loading {EMBEDDINGS_PATH}")
    _embeddings_cache = np.load(EMBEDDINGS_PATH)
    with open(ids_path, "r", encoding="utf-8") as f:
        _verse_ids_cache = [line.strip() for line in f if line.strip()]
    load_embeddings._mtime = current_mtime
    print(f"  [embeddings] Loaded {_embeddings_cache.shape}, std={_embeddings_cache.std():.4f}")
    return _embeddings_cache, _verse_ids_cache


def encode_query(query_text):
    global _model_cache
    if _model_cache is None:
        from sentence_transformers import SentenceTransformer
        _model_cache = SentenceTransformer("paraphrase-multilingual-mpnet-base-v2")
    return _model_cache.encode([query_text], normalize_embeddings=True)[0]


def keyword_score(text, keywords):
    """
    Returns a boost score in [0, 1] based on keyword presence in English text.
    Case-insensitive whole-word matching.
    """
    if not keywords or not text:
        return 0.0
    text_lower = text.lower()
    hits = 0
    for kw in keywords:
        pattern = r'\b' + re.escape(kw.lower()) + r'\b'
        if re.search(pattern, text_lower):
            hits += 1
    return min(hits / max(len(keywords) * 0.15, 5), 1.0)


def extract_custom_keywords(query_text):
    """
    For a free-text custom query, derive a keyword list by:
    1. Using the query words themselves
    2. Adding synonyms/expansions from CUSTOM_QUERY_EXPANSIONS for each word
    Returns a flat deduplicated keyword list for use in keyword_score().
    """
    words    = re.findall(r'\b\w+\b', query_text.lower())
    keywords = set(words)

    for word in words:
        expansion = CUSTOM_QUERY_EXPANSIONS.get(word, "")
        if expansion:
            keywords.update(expansion.lower().split())

    # Also check full phrase match
    full = CUSTOM_QUERY_EXPANSIONS.get(query_text.lower().strip(), "")
    if full:
        keywords.update(full.lower().split())

    # Remove short stop words
    stop = {"the", "a", "an", "in", "of", "to", "and", "or", "is",
            "it", "at", "by", "as", "be", "do", "on", "up"}
    keywords -= stop
    return list(keywords)


def expand_custom_query(query_text):
    """
    Build a richer semantic query string for free-text input by combining
    the original query with expansions from CUSTOM_QUERY_EXPANSIONS.
    """
    words    = re.findall(r'\b\w+\b', query_text.lower())
    expanded = [query_text]

    for word in words:
        expansion = CUSTOM_QUERY_EXPANSIONS.get(word)
        if expansion:
            expanded.append(expansion)

    full = CUSTOM_QUERY_EXPANSIONS.get(query_text.lower().strip())
    if full:
        expanded.append(full)

    return " ".join(expanded)


def compute_hybrid_scores(semantic_scores, verse_ids, english_texts,
                          topic_key, custom_keywords=None):
    """
    Hybrid score = 0.65 * semantic_score_normalised
                 + 0.35 * keyword_score

    For preset topics:  uses TOPIC_KEYWORDS[topic_key]
    For custom queries: uses custom_keywords derived from query + expansions
    """
    if custom_keywords is not None:
        keywords = custom_keywords
    else:
        keywords = TOPIC_KEYWORDS.get(topic_key, [])

    s_max    = semantic_scores.max() if semantic_scores.max() > 0 else 1.0
    s_min    = semantic_scores.min()
    s_range  = (s_max - s_min) if (s_max - s_min) > 0 else 1.0
    sem_norm = (semantic_scores - s_min) / s_range

    hybrid = np.zeros(len(semantic_scores))
    for i, (vid, eng) in enumerate(zip(verse_ids, english_texts)):
        kw_boost  = keyword_score(eng or "", keywords)
        hybrid[i] = 0.85 * sem_norm[i] + 0.15 * kw_boost

    return hybrid


def adaptive_threshold(scores, k=0.55):
    """
    Return mean + k * std of scores.
    This adapts to each query's score distribution instead of using a
    fixed global cut-off, which varies wildly across topics for mBERT.
    """
    if len(scores) == 0:
        return 0.0
    return float(np.mean(scores) + k * np.std(scores))


def search_topic(query_text, top_n=10):
    embeddings, verse_ids = load_embeddings()
    if embeddings is None:
        return pd.DataFrame()

    topic_key  = query_text.lower().strip()
    is_preset  = topic_key in QUERY_EXPANSIONS

    if is_preset:
        # Preset topic: use curated expansion + TOPIC_KEYWORDS
        expanded        = QUERY_EXPANSIONS[topic_key]
        custom_keywords = None
    else:
        # Custom query: auto-expand and derive keywords from query + synonyms
        expanded        = expand_custom_query(query_text)
        custom_keywords = extract_custom_keywords(query_text)

    query_vec = encode_query(expanded)

    # Step 1: semantic similarity over all Ayaat
    sem_scores = np.dot(embeddings, query_vec)

    # Step 2: fetch all Ayaat English text for keyword scoring
    df_all = query_df(
        """SELECT vf.verse_id, vf.arabic_text, vf.english_text,
                  vf.name_english, vf.name_arabic, vf.revelation_type,
                  vf.revelation_order, vf.surah_number, vf.verse_number
           FROM v_verses_full vf""",
        ()
    )
    vid_to_row = {row["verse_id"]: row for _, row in df_all.iterrows()}
    eng_texts  = [
        vid_to_row.get(vid, {}).get("english_text", "") or ""
        for vid in verse_ids
    ]

    # Step 3: hybrid scores
    hybrid = compute_hybrid_scores(
        sem_scores, verse_ids, eng_texts,
        topic_key, custom_keywords
    )

    # Step 4: adaptive threshold — tighter to reduce noise
    k         = 1.20 if is_preset else 1.00
    threshold = adaptive_threshold(hybrid, k=k)

    # Step 4b: ALSO require minimum raw semantic score
    # This prevents keyword boost alone from surfacing irrelevant Ayaat
    # Normalised semantic scores: require top 40% of semantic distribution
    sem_norm = (sem_scores - sem_scores.min()) / (sem_scores.max() - sem_scores.min())
    min_semantic = float(np.percentile(sem_norm, 60))

    # Step 5: filter — must pass BOTH hybrid threshold AND minimum semantic
    mask         = (hybrid >= threshold) & (sem_norm >= min_semantic)
    filtered_idx = np.where(mask)[0]

    # Fallback: if too aggressive, take top 5 by hybrid score
    if len(filtered_idx) < 5:
        filtered_idx = np.argsort(hybrid)[::-1][:5]

    filtered_hybrid = hybrid[filtered_idx]
    order           = np.argsort(filtered_hybrid)[::-1]
    top_idx         = filtered_idx[order]

    if top_n < 999:
        top_idx = top_idx[:top_n]

    selected_vids   = [verse_ids[i] for i in top_idx]
    selected_hybrid = [float(hybrid[i]) for i in top_idx]

    # Step 6: build result DataFrame
    rows = [vid_to_row[v] for v in selected_vids if v in vid_to_row]
    if not rows:
        return pd.DataFrame()

    df             = pd.DataFrame(rows)
    score_map      = dict(zip(selected_vids, selected_hybrid))
    df["similarity"] = df["verse_id"].map(score_map)
    df = df.sort_values(
        ["revelation_order", "verse_number"]
    ).reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────────────────────────
#  UI BUILDERS  (unchanged from v4)
# ─────────────────────────────────────────────────────────────────────────────

def build_thematic_overview(query):
    commentary = STATIC_COMMENTARIES.get(query.lower().strip())
    if not commentary:
        return html.Div()
    paragraphs = [p.strip() for p in commentary.split("\n\n") if p.strip()]
    return html.Div([
        html.Div([
            html.Span("📖  ", style={"fontSize": "16px"}),
            html.Span(
                f'Thematic Overview — "{query}"',
                style={"fontSize": "14px", "fontWeight": "700",
                       "color": "#c9a84c", "letterSpacing": "0.5px"},
            ),
        ], style={"marginBottom": "14px"}),
        html.Div([
            html.P(para, style={"fontSize": "14px", "color": "#a89a7a",
                                "lineHeight": "1.9", "marginBottom": "12px"})
            for para in paragraphs
        ]),
    ], style={
        "background":   "#1a1814",
        "border":       "1px solid #c9a84c",
        "borderLeft":   "3px solid #c9a84c",
        "borderRadius": "4px",
        "padding":      "20px",
        "marginBottom": "24px",
    })


def build_stats_summary(query, df):
    if df.empty:
        return html.Div()
    meccan_df   = df[df["revelation_type"] == "Meccan"]
    medinan_df  = df[df["revelation_type"] == "Medinan"]
    total       = len(df)
    meccan_pct  = int(len(meccan_df) / total * 100) if total else 0
    medinan_pct = 100 - meccan_pct
    surah_counts = df.groupby("name_english")["verse_id"].count().sort_values(ascending=False)
    top_surah    = surah_counts.index[0]     if not surah_counts.empty else "—"
    top_surah_ct = int(surah_counts.iloc[0]) if not surah_counts.empty else 0
    rev_min  = int(df["revelation_order"].min())
    rev_max  = int(df["revelation_order"].max())
    avg_sim  = float(df["similarity"].mean())
    meccan_surahs  = ", ".join(meccan_df["name_english"].unique()[:5])
    medinan_surahs = ", ".join(medinan_df["name_english"].unique()[:5])

    def stat_row(label, value, color="#e8e0d0"):
        return html.Div([
            html.Span(label, style={"color": "#6b6050", "fontSize": "12px",
                                    "minWidth": "200px", "display": "inline-block"}),
            html.Span(value, style={"color": color, "fontSize": "13px",
                                    "fontFamily": "'Source Code Pro', monospace"}),
        ], style={"marginBottom": "8px"})

    return html.Div([
        html.Div([
            html.Span("📊  ", style={"fontSize": "16px"}),
            html.Span(
                f'Statistical Summary — "{query}"',
                style={"fontSize": "14px", "fontWeight": "700",
                       "color": "#a89a7a", "letterSpacing": "0.5px"},
            ),
        ], style={"marginBottom": "14px"}),
        html.Div([
            stat_row("Total Ayaat found",    f"{total}"),
            stat_row("Meccan Ayaat",         f"{len(meccan_df)}  ({meccan_pct}%)",   "#e8943a"),
            stat_row("Medinan Ayaat",        f"{len(medinan_df)}  ({medinan_pct}%)", "#4a9fd4"),
            stat_row("Most frequent Surah",  f"{top_surah}  ({top_surah_ct} Ayaat)"),
            stat_row("Revelation span",      f"Order {rev_min} → {rev_max}"),
            stat_row("Avg. relevance score", f"{avg_sim:.3f}"),
            stat_row("Meccan Surahs",
                     meccan_surahs  + ("..." if len(meccan_df["name_english"].unique())  > 5 else ""),
                     "#e8943a") if meccan_surahs  else html.Div(),
            stat_row("Medinan Surahs",
                     medinan_surahs + ("..." if len(medinan_df["name_english"].unique()) > 5 else ""),
                     "#4a9fd4") if medinan_surahs else html.Div(),
        ]),
    ], style={
        "background":   "#1a1814",
        "border":       "1px solid #2e2a22",
        "borderLeft":   "3px solid #a89a7a",
        "borderRadius": "4px",
        "padding":      "20px",
        "marginTop":    "24px",
    })


def run_search(query_text, top_n):
    if not query_text or not query_text.strip():
        return (html.P("Please enter a topic.", className="loading-text"),
                html.Div(), html.Div())
    query_text = query_text.strip()
    if not os.path.exists(EMBEDDINGS_PATH):
        return (
            html.Div([
                html.P("Embeddings not found.",
                       style={"color": "#e8943a", "fontSize": "13px"}),
                html.P("Run: python3 embeddings/generate_embeddings.py",
                       style={"fontFamily": "'Source Code Pro', monospace",
                              "fontSize": "12px", "color": "#c9a84c",
                              "background": "#1a1814", "padding": "8px 12px",
                              "borderRadius": "4px", "marginTop": "8px"}),
            ]), html.Div(), html.Div())
    try:
        df = search_topic(query_text, top_n=top_n or 10)
    except Exception as e:
        return (html.P(f"Search error: {e}",
                       style={"color": "#e8943a", "fontSize": "13px"}),
                html.Div(), html.Div())
    if df.empty:
        return (html.P(
            "No relevant Ayaat found. Try a different topic or broader search term.",
            className="loading-text"), html.Div(), html.Div())

    is_preset     = query_text.lower().strip() in QUERY_EXPANSIONS
    meccan_count  = len(df[df["revelation_type"] == "Meccan"])
    medinan_count = len(df[df["revelation_type"] == "Medinan"])

    status = html.Div([
        html.Span(f'Showing {len(df)} Ayaat related to "{query_text}" ',
                  style={"color": "#a89a7a", "fontSize": "13px"}),
        html.Span(f"— {meccan_count} Meccan, {medinan_count} Medinan",
                  style={"color": "#6b6050", "fontSize": "12px"}),
        html.Span(" · hybrid relevance · chronological order",
                  style={"color": "#6b6050", "fontSize": "12px",
                         "fontStyle": "italic"}),
    ], style={"marginBottom": "16px"})

    # Thematic overview only for preset topics (has scholarly commentary)
    overview = build_thematic_overview(query_text) if is_preset else html.Div()

    items       = []
    prev_period = None

    for _, row in df.iterrows():
        period = row["revelation_type"]
        if period != prev_period:
            items.append(html.Div([
                html.Span(
                    f"— {period} Period",
                    style={
                        "fontSize":      "11px",
                        "fontWeight":    "700",
                        "textTransform": "uppercase",
                        "letterSpacing": "1px",
                        "color":    "#e8943a" if period == "Meccan" else "#4a9fd4",
                        "background": "#1a1814",
                        "padding":   "3px 10px",
                        "borderRadius": "3px",
                        "border": f"1px solid {'#4a2e12' if period == 'Meccan' else '#1a3a5c'}",
                    }
                ),
            ], style={"margin": "20px 0 14px 0"}))
            prev_period = period

        sim = float(row["similarity"])
        items.append(html.Div([
            html.Div([
                html.Span(row["verse_id"], className="verse-id"),
                html.Span(
                    f"Rev. order {int(row['revelation_order'])}",
                    style={"fontSize": "10px", "color": "#6b6050",
                           "fontFamily": "'Source Code Pro', monospace",
                           "marginLeft": "8px"},
                ),
                html.Span(row["name_english"],
                          style={"fontSize": "10px", "color": "#6b6050",
                                 "marginLeft": "8px"}),
                html.Span(row["name_arabic"],
                          style={"fontSize": "13px", "color": "#6b6050",
                                 "marginLeft": "6px",
                                 "fontFamily": "'Amiri', serif"}),
                html.Div([
                    html.Div(style={
                        "height": "3px",
                        "width":  f"{sim * 100:.0f}%",
                        "background": "#c9a84c",
                        "borderRadius": "2px",
                    }),
                ], style={"flex": "1", "background": "#2e2a22",
                          "borderRadius": "2px", "height": "3px",
                          "marginLeft": "12px", "minWidth": "60px",
                          "maxWidth": "120px", "alignSelf": "center"}),
                html.Span(f"{sim:.2f}",
                          style={"fontSize": "10px", "color": "#6b6050",
                                 "fontFamily": "'Source Code Pro', monospace",
                                 "marginLeft": "6px"}),
            ], style={"display": "flex", "alignItems": "center",
                      "flexWrap": "wrap"}),
            html.Div(row["arabic_text"], className="verse-arabic"),
            html.Div(
                row["english_text"] or "",
                className="verse-english",
                style={"fontSize": "14px", "color": "#a89a7a",
                       "fontStyle": "italic", "lineHeight": "1.8",
                       "marginTop": "8px", "paddingTop": "8px",
                       "borderTop": "1px solid #2e2a22", "display": "block"},
            ),
        ], className="verse-card",
           style={"marginBottom": "12px",
                  "borderLeftColor": "#e8943a" if period == "Meccan" else "#4a9fd4"}))

    items.append(build_stats_summary(query_text, df))
    overview_section = overview if overview.children else html.Div()
    return html.Div(items, className="narrative-timeline"), status, overview_section


# ─────────────────────────────────────────────────────────────────────────────
#  CALLBACK
# ─────────────────────────────────────────────────────────────────────────────

@app.callback(
    [Output("narrative-results",          "children"),
     Output("narrative-status",           "children"),
     Output("narrative-overview-section", "children"),
     Output("narrative-topic-input",      "value")],
    [
        Input({"type": "topic-suggestion", "index": ALL}, "n_clicks"),
        Input("narrative-search-btn",   "n_clicks"),
        Input("narrative-topic-input",  "n_submit"),
        Input("narrative-result-count", "value"),
    ],
    [State("narrative-topic-input", "value")],
    prevent_initial_call=True,
)
def handle_search(topic_btn_clicks, search_btn_clicks, enter_presses,
                  top_n, current_input):
    from dashboard.layouts.narrative import SUGGESTED_TOPICS
    ctx = callback_context
    if not ctx.triggered:
        return html.Div(), html.Div(), html.Div(), current_input or ""
    triggered_id = ctx.triggered[0]["prop_id"]
    if "topic-suggestion" in triggered_id:
        try:
            id_dict = json.loads(triggered_id.replace(".n_clicks", ""))
            query   = SUGGESTED_TOPICS[id_dict["index"]]
        except Exception:
            return html.Div(), html.Div(), html.Div(), current_input or ""
        results, status, overview = run_search(query, top_n or 10)
        return results, status, overview, query
    query = current_input or ""
    results, status, overview = run_search(query, top_n or 10)
    return results, status, overview, query


# ─────────────────────────────────────────────────────────────────────────────
#  WARMUP
# ─────────────────────────────────────────────────────────────────────────────

import threading

def _warmup():
    print("Warming up paraphrase-multilingual-mpnet-base-v2 model...")
    encode_query("mercy allah forgiveness compassion")
    print("  Model ready.")

threading.Thread(target=_warmup, daemon=True).start()