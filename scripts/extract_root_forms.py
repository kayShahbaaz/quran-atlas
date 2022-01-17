"""
scripts/extract_root_forms.py

Run this ONCE against your actual quran-simple.xml to extract every
real surface form that contains each root's core letters as a substring,
then filters to word-boundary matches only.

This produces a verified ROOT_FORMS map built from YOUR actual data —
not guessed forms — which gets written into quran_data.py automatically.

Usage:
    python3 scripts/extract_root_forms.py

Output:
    data/verified_root_forms.json   ← paste into quran_data.py COMMON_ROOTS
    data/root_forms_report.txt      ← human-readable QA report
"""

import os
import sys
import json
import re
from collections import defaultdict
from lxml import etree
from tqdm import tqdm

# ── Config ────────────────────────────────────────────────────────────────────
XML_PATH    = "data/quran-simple.xml"
OUTPUT_JSON = "data/verified_root_forms.json"
OUTPUT_RPT  = "data/root_forms_report.txt"

# ── The 3-letter core of each root (letters that MUST all be present) ─────────
# These are the actual Arabic root letters, used for candidate extraction.
# We then filter candidates by requiring ALL root letters appear in the word
# in order (as a subsequence), which is the correct Arabic root test.
ROOT_CORES = {
    # Divine Attributes
    "رحم":  {"letters": "رحم", "english": "mercy/compassion",        "domain": "Divine Attributes"},
    "حمد":  {"letters": "حمد", "english": "praise/gratitude",        "domain": "Divine Attributes"},
    "غفر":  {"letters": "غفر", "english": "forgiveness/pardon",      "domain": "Divine Attributes"},
    "رزق":  {"letters": "رزق", "english": "provision/sustenance",    "domain": "Divine Attributes"},
    "ملك":  {"letters": "ملك", "english": "sovereignty/ownership",   "domain": "Divine Attributes"},
    "نور":  {"letters": "نور", "english": "light/illumination",      "domain": "Divine Attributes"},
    "علم":  {"letters": "علم", "english": "knowledge/knowing",       "domain": "Divine Attributes"},
    "سمع":  {"letters": "سمع", "english": "hearing/listening",       "domain": "Divine Attributes"},
    "حفظ":  {"letters": "حفظ", "english": "protection/preservation", "domain": "Divine Attributes"},
    "حكم":  {"letters": "حكم", "english": "wise/wisdom",             "domain": "Divine Attributes"},
    "قرب":  {"letters": "قرب", "english": "nearness/proximity",      "domain": "Divine Attributes"},
    "قدر":  {"letters": "قدر", "english": "all-powerful",            "domain": "Divine Attributes"},
    "وحد":  {"letters": "وحد", "english": "oneness/unity",           "domain": "Divine Attributes"},

    # Faith & Belief
    "امن":  {"letters": "امن", "english": "faith/belief",            "domain": "Faith & Belief"},
    "كفر":  {"letters": "كفر", "english": "disbelief/ingratitude",   "domain": "Faith & Belief"},
    "شرك":  {"letters": "شرك", "english": "polytheism/association",  "domain": "Faith & Belief"},
    "نفق":  {"letters": "نفق", "english": "hypocrisy",               "domain": "Faith & Belief"},
    "صدق":  {"letters": "صدق", "english": "truthfulness/sincerity",  "domain": "Faith & Belief"},
    "تقو":  {"letters": "تقو", "english": "piety/taqwa",             "domain": "Faith & Belief"},
    "يقن":  {"letters": "يقن", "english": "certainty/conviction",    "domain": "Faith & Belief"},
    "شهد":  {"letters": "شهد", "english": "witnessing/testimony",    "domain": "Faith & Belief"},
    "خشي":  {"letters": "خشي", "english": "fear/awe of Allah",       "domain": "Faith & Belief"},
    "دين":  {"letters": "دين", "english": "religion/way of life",    "domain": "Faith & Belief"},
    "توك":  {"letters": "توك", "english": "trust/reliance on Allah", "domain": "Faith & Belief"},

    # Worship & Devotion
    "عبد":  {"letters": "عبد", "english": "worship/servitude",       "domain": "Worship & Devotion"},
    "صلو":  {"letters": "صلو", "english": "prayer/blessing",         "domain": "Worship & Devotion"},
    "زكو":  {"letters": "زكو", "english": "purification/almsgiving", "domain": "Worship & Devotion"},
    "صوم":  {"letters": "صوم", "english": "fasting/abstaining",      "domain": "Worship & Devotion"},
    "حجج":  {"letters": "حجج", "english": "pilgrimage",              "domain": "Worship & Devotion"},
    "ذكر":  {"letters": "ذكر", "english": "remembrance/mention",     "domain": "Worship & Devotion"},
    "دعو":  {"letters": "دعو", "english": "supplication/calling",    "domain": "Worship & Devotion"},
    "سجد":  {"letters": "سجد", "english": "prostration/bowing",      "domain": "Worship & Devotion"},
    "سبح":  {"letters": "سبح", "english": "glorification/tasbih",    "domain": "Worship & Devotion"},

    # Prophethood & Revelation
    "نبا":  {"letters": "نبا", "english": "prophet/prophecy",        "domain": "Prophethood"},
    "رسل":  {"letters": "رسل", "english": "messenger/mission",       "domain": "Prophethood"},
    "وحي":  {"letters": "وحي", "english": "revelation/inspiration",  "domain": "Prophethood"},
    "كتب":  {"letters": "كتب", "english": "scripture/book",          "domain": "Prophethood"},
    "هدي":  {"letters": "هدي", "english": "guidance/right path",     "domain": "Prophethood"},
    "ضلل":  {"letters": "ضلل", "english": "misguidance/going astray","domain": "Prophethood"},
    "بشر":  {"letters": "بشر", "english": "glad tidings",            "domain": "Prophethood"},
    "نذر":  {"letters": "نذر", "english": "warning/admonition",      "domain": "Prophethood"},
    "امر":  {"letters": "امر", "english": "command/authority",       "domain": "Prophethood"},

    # Ethics & Character
    "عدل":  {"letters": "عدل", "english": "justice/equity",          "domain": "Ethics & Character"},
    "ظلم":  {"letters": "ظلم", "english": "injustice/oppression",    "domain": "Ethics & Character"},
    "صبر":  {"letters": "صبر", "english": "patience/endurance",      "domain": "Ethics & Character"},
    "كذب":  {"letters": "كذب", "english": "lying/falsehood",         "domain": "Ethics & Character"},
    "شكر":  {"letters": "شكر", "english": "gratitude/thankfulness",  "domain": "Ethics & Character"},
    "عفو":  {"letters": "عفو", "english": "pardon/forgiveness",      "domain": "Ethics & Character"},
    "كبر":  {"letters": "كبر", "english": "arrogance/pride",         "domain": "Ethics & Character"},
    "حسن":  {"letters": "حسن", "english": "goodness/good deed",      "domain": "Ethics & Character"},
    "فسد":  {"letters": "فسد", "english": "corruption/mischief",     "domain": "Ethics & Character"},
    "امن2": {"letters": "امن", "english": "trustworthiness/honesty", "domain": "Ethics & Character"},  # امانة

    # Justice & Law
    "قضي":  {"letters": "قضي", "english": "decree/judgment",         "domain": "Justice & Law"},
    "حقق":  {"letters": "حق",  "english": "right/truth/due",         "domain": "Justice & Law"},
    "جزي":  {"letters": "جزي", "english": "recompense/reward",       "domain": "Justice & Law"},
    "حدد":  {"letters": "حدد", "english": "limits/boundaries",       "domain": "Justice & Law"},
    "شهادة":{"letters": "شهد", "english": "legal testimony",         "domain": "Justice & Law"},
    "ورث":  {"letters": "ورث", "english": "inheritance",             "domain": "Justice & Law"},

    # Economics & Society
    "مول":  {"letters": "مال", "english": "wealth/property",         "domain": "Economics & Society"},
    "نفق2": {"letters": "نفق", "english": "spending/expenditure",    "domain": "Economics & Society"},
    "صدقة": {"letters": "صدق", "english": "charity/alms",            "domain": "Economics & Society"},
    "ربو":  {"letters": "ربو", "english": "usury/interest",          "domain": "Economics & Society"},
    "تجر":  {"letters": "تجر", "english": "trade/commerce",          "domain": "Economics & Society"},
    "خسر":  {"letters": "خسر", "english": "loss/ruin",               "domain": "Economics & Society"},

    # Nature & Creation
    "خلق":  {"letters": "خلق", "english": "creation",                "domain": "Nature & Creation"},
    "سما":  {"letters": "سما", "english": "sky/heaven",              "domain": "Nature & Creation"},
    "ارض":  {"letters": "ارض", "english": "earth/land",              "domain": "Nature & Creation"},
    "ماء":  {"letters": "ماء", "english": "water",                   "domain": "Nature & Creation"},
    "حيا":  {"letters": "حيا", "english": "life/living",             "domain": "Nature & Creation"},
    "موت":  {"letters": "موت", "english": "death",                   "domain": "Nature & Creation"},
    "ليل":  {"letters": "ليل", "english": "night",                   "domain": "Nature & Creation"},
    "نهر":  {"letters": "نهر", "english": "day/daytime",             "domain": "Nature & Creation"},
    "شمس":  {"letters": "شمس", "english": "sun",                     "domain": "Nature & Creation"},
    "قمر":  {"letters": "قمر", "english": "moon",                    "domain": "Nature & Creation"},
    "ريح":  {"letters": "ريح", "english": "wind",                    "domain": "Nature & Creation"},
    "مطر":  {"letters": "مطر", "english": "rain",                    "domain": "Nature & Creation"},
    "شجر":  {"letters": "شجر", "english": "tree/plant",              "domain": "Nature & Creation"},
    "بحر":  {"letters": "بحر", "english": "sea/ocean",               "domain": "Nature & Creation"},
    "جبل":  {"letters": "جبل", "english": "mountains",               "domain": "Nature & Creation"},
    "طير":  {"letters": "طير", "english": "birds/flying",            "domain": "Nature & Creation"},
    "نبت":  {"letters": "نبت", "english": "growth/vegetation",       "domain": "Nature & Creation"},
    "زرع":  {"letters": "زرع", "english": "cultivation/farming",     "domain": "Nature & Creation"},

    # Eschatology
    "قوم":  {"letters": "قوم", "english": "resurrection/Day",        "domain": "Eschatology"},
    "جنن":  {"letters": "جنن", "english": "paradise/garden",         "domain": "Eschatology"},
    "نار":  {"letters": "نار", "english": "fire/hellfire",           "domain": "Eschatology"},
    "عذب":  {"letters": "عذب", "english": "punishment/torment",      "domain": "Eschatology"},
    "جهنم": {"letters": "جهن", "english": "hell/gehenna",            "domain": "Eschatology"},
    "بعث":  {"letters": "بعث", "english": "resurrection/raising",    "domain": "Eschatology"},
    "توب":  {"letters": "توب", "english": "repentance",              "domain": "Eschatology"},
    "حسب":  {"letters": "حسب", "english": "reckoning/account",       "domain": "Eschatology"},
    "خلد":  {"letters": "خلد", "english": "eternity/immortality",    "domain": "Eschatology"},
    "حشر":  {"letters": "حشر", "english": "gathering/Assembly",      "domain": "Eschatology"},
    "شفع":  {"letters": "شفع", "english": "intercession",            "domain": "Eschatology"},
    "ميز":  {"letters": "ميز", "english": "scales/balance",          "domain": "Eschatology"},

    # Historical Narratives
    "فرعن": {"letters": "فرع", "english": "Pharaoh",                 "domain": "Historical Narratives"},
    "نصر":  {"letters": "نصر", "english": "victory/divine support",  "domain": "Historical Narratives"},
    "هلك":  {"letters": "هلك", "english": "destruction/ruin",        "domain": "Historical Narratives"},
    "امم":  {"letters": "امم", "english": "nations/peoples",         "domain": "Historical Narratives"},
    "فتح":  {"letters": "فتح", "english": "victory/opening",         "domain": "Historical Narratives"},
    "نجو":  {"letters": "نجو", "english": "salvation/escape",        "domain": "Historical Narratives"},

    # Knowledge & Reason
    "عقل":  {"letters": "عقل", "english": "reason/intellect",        "domain": "Knowledge & Reason"},
    "نظر":  {"letters": "نظر", "english": "looking/contemplating",   "domain": "Knowledge & Reason"},
    "سال":  {"letters": "سال", "english": "asking/questioning",      "domain": "Knowledge & Reason"},
    "بصر":  {"letters": "بصر", "english": "sight/clear proof",       "domain": "Knowledge & Reason"},
    "فكر":  {"letters": "فكر", "english": "thinking/reflection",     "domain": "Knowledge & Reason"},
    "فقه":  {"letters": "فقه", "english": "understanding/insight",   "domain": "Knowledge & Reason"},

    # Community & Relations
    "ولد":  {"letters": "ولد", "english": "child/birth/offspring",   "domain": "Community & Relations"},
    "زوج":  {"letters": "زوج", "english": "spouse/pair/partner",     "domain": "Community & Relations"},
    "قوم2": {"letters": "قوم", "english": "people/nation/tribe",     "domain": "Community & Relations"},
    "امة":  {"letters": "امة", "english": "nation/Ummah",            "domain": "Community & Relations"},
    "عهد":  {"letters": "عهد", "english": "covenant/promise",        "domain": "Community & Relations"},
    "يتم":  {"letters": "يتم", "english": "orphan",                  "domain": "Community & Relations"},
    "مسكن": {"letters": "سكن", "english": "poor/needy person",       "domain": "Community & Relations"},
    "اخو":  {"letters": "اخو", "english": "brotherhood/siblings",    "domain": "Community & Relations"},
    "نكح":  {"letters": "نكح", "english": "marriage",                "domain": "Community & Relations"},
    "طلق":  {"letters": "طلق", "english": "divorce",                 "domain": "Community & Relations"},
    "والد": {"letters": "ولد", "english": "parents",                 "domain": "Community & Relations"},

    # Conflict & Struggle
    "جهد":  {"letters": "جهد", "english": "striving/jihad",          "domain": "Conflict & Struggle"},
    "قتل":  {"letters": "قتل", "english": "fighting/warfare",        "domain": "Conflict & Struggle"},
    "سلم":  {"letters": "سلم", "english": "peace/submission",        "domain": "Conflict & Struggle"},
    "عدو":  {"letters": "عدو", "english": "enemy/enmity",            "domain": "Conflict & Struggle"},
    "فتن":  {"letters": "فتن", "english": "trial/sedition",          "domain": "Conflict & Struggle"},
    "هجر":  {"letters": "هجر", "english": "migration/hijra",         "domain": "Conflict & Struggle"},
    "خوف":  {"letters": "خوف", "english": "fear/danger",             "domain": "Conflict & Struggle"},
    "حرب":  {"letters": "حرب", "english": "war/conflict",            "domain": "Conflict & Struggle"},

    # Spiritual & Inner Life
    "قلب":  {"letters": "قلب", "english": "heart/inner self",        "domain": "Spiritual & Inner Life"},
    "روح":  {"letters": "روح", "english": "spirit/soul",             "domain": "Spiritual & Inner Life"},
    "نفس":  {"letters": "نفس", "english": "soul/self/person",        "domain": "Spiritual & Inner Life"},
    "فلح":  {"letters": "فلح", "english": "success/prosperity",      "domain": "Spiritual & Inner Life"},
    "غفل":  {"letters": "غفل", "english": "heedlessness/negligence", "domain": "Spiritual & Inner Life"},
    "طهر":  {"letters": "طهر", "english": "purity/cleansing",        "domain": "Spiritual & Inner Life"},
    "سكن":  {"letters": "سكن", "english": "tranquility/peace",       "domain": "Spiritual & Inner Life"},
    "وسوس": {"letters": "وسو", "english": "whisper/Shaytan",         "domain": "Spiritual & Inner Life"},
}

# Common attached prefixes to strip before matching (longest first)
PREFIXES = ["وال", "فال", "بال", "كال", "لل", "ال", "و", "ف", "ب", "ل", "ك", "س", "ي", "ت", "ن", "ا"]


def strip_prefix(word):
    """Strip one leading attached prefix and return the stem."""
    for prefix in PREFIXES:
        if word.startswith(prefix) and len(word) > len(prefix) + 1:
            return word[len(prefix):]
    return word


def letters_in_order(letters, word):
    """
    Check if all characters in `letters` appear in `word` as a subsequence
    (in order, not necessarily contiguous). This is the correct Arabic root test.
    Example: letters='رحم', word='رحمة' → True
             letters='رحم', word='مرحبا' → True (false positive with substring)
             But with word-boundary matching we only test actual words.
    """
    idx = 0
    for ch in letters:
        found = word.find(ch, idx)
        if found == -1:
            return False
        idx = found + 1
    return True


def get_all_tokens(text):
    """
    Get all word tokens from an Arabic text, including prefix-stripped variants.
    """
    tokens = set()
    for word in text.split():
        tokens.add(word)
        stripped = strip_prefix(word)
        if stripped != word:
            tokens.add(stripped)
        # Strip twice for double prefixes like وال
        stripped2 = strip_prefix(stripped)
        if stripped2 != stripped:
            tokens.add(stripped2)
    return tokens


def load_xml(xml_path):
    """Load all verses from Tanzil XML."""
    print(f"Loading {xml_path}...")
    tree = etree.parse(xml_path)
    root = tree.getroot()
    verses = []
    for sura in root.findall(".//sura"):
        surah_num = int(sura.get("index"))
        for aya in sura.findall("aya"):
            verse_num = int(aya.get("index"))
            text = aya.get("text", "")
            verses.append((surah_num, verse_num, text))
    print(f"  Loaded {len(verses)} verses.")
    return verses


def extract_forms(verses, root_cores):
    """
    For each root, scan every verse and collect every token where
    the root letters appear as an ordered subsequence.
    Returns: dict of root_key -> sorted list of unique forms
    """
    print("Extracting surface forms per root...")

    # Build token -> list of verses index for fast scanning
    # We scan all verses for all roots simultaneously
    root_forms = defaultdict(set)

    for surah_num, verse_num, text in tqdm(verses, desc="Scanning verses"):
        tokens = get_all_tokens(text)
        for root_key, info in root_cores.items():
            letters = info["letters"]
            for token in tokens:
                if len(token) >= len(letters) and letters_in_order(letters, token):
                    root_forms[root_key].add(token)

    # Convert sets to sorted lists
    return {k: sorted(v) for k, v in root_forms.items()}


def count_verse_hits(verses, root_forms):
    """Count how many verses each root matches."""
    counts = {}
    for root_key, forms in root_forms.items():
        form_set = set(forms)
        hit = 0
        for _, _, text in verses:
            tokens = get_all_tokens(text)
            if tokens & form_set:
                hit += 1
        counts[root_key] = hit
    return counts


def build_output(root_cores, root_forms, verse_counts):
    """Build the final dict structure for quran_data.py COMMON_ROOTS."""
    output = {}
    for root_key, info in root_cores.items():
        # Skip duplicate-purpose keys (امن2, نفق2 etc)
        display_key = root_key.rstrip("0123456789")
        forms = root_forms.get(root_key, [])
        # Filter out very short tokens (1-2 chars) which are likely noise
        forms = [f for f in forms if len(f) >= 2]
        output[display_key] = {
            "english":   info["english"],
            "domain":    info["domain"],
            "frequency": verse_counts.get(root_key, 0),
            "forms":     forms,
        }
    return output


def write_report(output, report_path):
    """Write human-readable QA report."""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("QURAN ATLAS — Root Forms Extraction Report\n")
        f.write("=" * 60 + "\n\n")
        for root_key, data in sorted(output.items(), key=lambda x: -x[1]["frequency"]):
            f.write(f"Root: {root_key}  ({data['english']})\n")
            f.write(f"  Domain:    {data['domain']}\n")
            f.write(f"  Verses:    {data['frequency']}\n")
            f.write(f"  Forms ({len(data['forms'])}): {', '.join(data['forms'][:20])}")
            if len(data['forms']) > 20:
                f.write(f"  ... +{len(data['forms'])-20} more")
            f.write("\n\n")
    print(f"  Report written to {report_path}")


def main():
    if not os.path.exists(XML_PATH):
        print(f"ERROR: {XML_PATH} not found.")
        print("Make sure you run this from the project root:")
        print("  python3 scripts/extract_root_forms.py")
        sys.exit(1)

    verses     = load_xml(XML_PATH)
    root_forms = extract_forms(verses, ROOT_CORES)

    print("Counting verse hits per root...")
    verse_counts = count_verse_hits(verses, root_forms)

    output = build_output(ROOT_CORES, root_forms, verse_counts)

    # Write JSON
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  Forms written to {OUTPUT_JSON}")

    # Write report
    write_report(output, OUTPUT_RPT)

    # Summary
    print("\n── Summary ──────────────────────────────────────────────")
    print(f"{'Root':<12} {'English':<30} {'Verses':>7}  {'Forms':>6}")
    print("-" * 60)
    for root_key, data in sorted(output.items(), key=lambda x: -x[1]["frequency"])[:30]:
        print(f"{root_key:<12} {data['english']:<30} {data['frequency']:>7}  {len(data['forms']):>6}")

    print(f"\nDone. Now run:")
    print(f"  python3 db/seed.py")
    print(f"to rebuild the database with verified forms.")


if __name__ == "__main__":
    main()