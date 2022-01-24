"""
scripts/add_missing_roots.py

Reads data/verified_root_forms.json and adds any root that is
NOT already in COMMON_ROOTS in data/quran_data.py.

Also patches the "forms" list for roots that DO exist but were skipped
by patch_quran_data.py because the key names didn't match.

Run from project root:
    python3 scripts/add_missing_roots.py

Then:
    python3 db/seed.py
    python3 dashboard/server.py
"""

import os
import sys
import json
import re

FORMS_JSON  = "data/verified_root_forms.json"
QURAN_DATA  = "data/quran_data.py"
BACKUP_PATH = "data/quran_data_pre_add.py"

# Map from extract_root_forms.py key  →  the actual key used in quran_data.py
# (where they differ due to naming conventions)
KEY_ALIASES = {
    "امن2":    "امن",
    "نفق2":    "نفق",
    "قوم2":    "قوم",
    "حققq":    "حقق",
    "مول":     "مال",
    "شهادة":   "شهد",
    "صدقة":    "صدق",
    "فرعن":    "فرعون",
    "امة":     "امة",
    "والد":    "ولد",
    "مسكن":    "مسكين",
}

# For roots that are genuinely new (not in quran_data.py at all),
# map them to display keys and metadata
NEW_ROOT_META = {
    "حفظ":  {"display": "حفظ",  "english": "protection/preservation",  "domain": "Divine Attributes",     "frequency": 44},
    "حكم":  {"display": "حكم",  "english": "wise/wisdom",               "domain": "Divine Attributes",     "frequency": 210},
    "قرب":  {"display": "قرب",  "english": "nearness/proximity",        "domain": "Divine Attributes",     "frequency": 96},
    "قدر":  {"display": "قدر",  "english": "all-powerful/decree",       "domain": "Divine Attributes",     "frequency": 132},
    "وحد":  {"display": "وحد",  "english": "oneness/unity",             "domain": "Divine Attributes",     "frequency": 25},
    "يقن":  {"display": "يقن",  "english": "certainty/conviction",      "domain": "Faith & Belief",        "frequency": 28},
    "خشي":  {"display": "خشي",  "english": "fear/awe of Allah",         "domain": "Faith & Belief",        "frequency": 48},
    "دين":  {"display": "دين",  "english": "religion/way of life",      "domain": "Faith & Belief",        "frequency": 103},
    "توك":  {"display": "توك",  "english": "trust/reliance on Allah",   "domain": "Faith & Belief",        "frequency": 39},
    "صلو":  {"display": "صلو",  "english": "prayer/blessing",           "domain": "Worship & Devotion",    "frequency": 99},
    "صوم":  {"display": "صوم",  "english": "fasting/abstaining",        "domain": "Worship & Devotion",    "frequency": 14},
    "حجج":  {"display": "حجج",  "english": "pilgrimage",                "domain": "Worship & Devotion",    "frequency": 9},
    "بشر":  {"display": "بشر",  "english": "glad tidings",              "domain": "Prophethood",           "frequency": 40},
    "نذر":  {"display": "نذر",  "english": "warning/admonition",        "domain": "Prophethood",           "frequency": 50},
    "امر":  {"display": "امر",  "english": "command/authority",         "domain": "Prophethood",           "frequency": 166},
    "حسن":  {"display": "حسن",  "english": "goodness/good deed",        "domain": "Ethics & Character",    "frequency": 194},
    "فسد":  {"display": "فسد",  "english": "corruption/mischief",       "domain": "Ethics & Character",    "frequency": 50},
    "جزي":  {"display": "جزي",  "english": "recompense/reward",         "domain": "Justice & Law",         "frequency": 55},
    "حدد":  {"display": "حدد",  "english": "limits/boundaries by Allah","domain": "Justice & Law",         "frequency": 14},
    "ورث":  {"display": "ورث",  "english": "inheritance",               "domain": "Justice & Law",         "frequency": 35},
    "ربو":  {"display": "ربو",  "english": "usury/interest",            "domain": "Economics & Society",   "frequency": 8},
    "تجر":  {"display": "تجر",  "english": "trade/commerce",            "domain": "Economics & Society",   "frequency": 9},
    "خسر":  {"display": "خسر",  "english": "loss/ruin",                 "domain": "Economics & Society",   "frequency": 65},
    "ريح":  {"display": "ريح",  "english": "wind",                      "domain": "Nature & Creation",     "frequency": 29},
    "مطر":  {"display": "مطر",  "english": "rain",                      "domain": "Nature & Creation",     "frequency": 10},
    "شجر":  {"display": "شجر",  "english": "tree/plant",                "domain": "Nature & Creation",     "frequency": 26},
    "بحر":  {"display": "بحر",  "english": "sea/ocean",                 "domain": "Nature & Creation",     "frequency": 41},
    "جبل":  {"display": "جبل",  "english": "mountains",                 "domain": "Nature & Creation",     "frequency": 39},
    "طير":  {"display": "طير",  "english": "birds/flying",              "domain": "Nature & Creation",     "frequency": 22},
    "نبت":  {"display": "نبت",  "english": "growth/vegetation",         "domain": "Nature & Creation",     "frequency": 15},
    "زرع":  {"display": "زرع",  "english": "cultivation/farming",       "domain": "Nature & Creation",     "frequency": 22},
    "حسب":  {"display": "حسب",  "english": "reckoning/account",         "domain": "Eschatology",           "frequency": 50},
    "خلد":  {"display": "خلد",  "english": "eternity/immortality",      "domain": "Eschatology",           "frequency": 35},
    "حشر":  {"display": "حشر",  "english": "gathering/Day of Assembly", "domain": "Eschatology",           "frequency": 43},
    "شفع":  {"display": "شفع",  "english": "intercession",              "domain": "Eschatology",           "frequency": 30},
    "ميز":  {"display": "ميز",  "english": "scales/balance of deeds",   "domain": "Eschatology",           "frequency": 9},
    "فتح":  {"display": "فتح",  "english": "victory/opening",           "domain": "Historical Narratives", "frequency": 38},
    "نجو":  {"display": "نجو",  "english": "salvation/escape",          "domain": "Historical Narratives", "frequency": 63},
    "فكر":  {"display": "فكر",  "english": "thinking/reflection",       "domain": "Knowledge & Reason",    "frequency": 18},
    "فقه":  {"display": "فقه",  "english": "understanding/insight",     "domain": "Knowledge & Reason",    "frequency": 20},
    "اخو":  {"display": "اخو",  "english": "brotherhood/siblings",      "domain": "Community & Relations", "frequency": 52},
    "نكح":  {"display": "نكح",  "english": "marriage",                  "domain": "Community & Relations", "frequency": 22},
    "طلق":  {"display": "طلق",  "english": "divorce",                   "domain": "Community & Relations", "frequency": 7},
    "خوف":  {"display": "خوف",  "english": "fear/danger",               "domain": "Conflict & Struggle",   "frequency": 124},
    "حرب":  {"display": "حرب",  "english": "war/conflict",              "domain": "Conflict & Struggle",   "frequency": 6},
    "طهر":  {"display": "طهر",  "english": "purity/cleansing",          "domain": "Spiritual & Inner Life","frequency": 31},
    "سكن":  {"display": "سكن",  "english": "tranquility/peace of heart","domain": "Spiritual & Inner Life","frequency": 70},
    "وسوس": {"display": "وسوس", "english": "whisper/temptation/Shaytan","domain": "Spiritual & Inner Life","frequency": 4},
    # صدقة uses صدق forms — handled via alias
    # شهادة uses شهد forms — handled via alias
    # والد  uses ولد forms — handled via alias
    # مسكن  uses سكن forms — handled via alias
    # امن2, نفق2, قوم2 are aliases handled above
}


def load_forms(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_existing_keys(filepath):
    """Extract all root keys currently in COMMON_ROOTS."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    start = content.find("COMMON_ROOTS = {")
    end   = content.find("\ndef ", start)
    block = content[start:end if end != -1 else len(content)]
    pattern = re.compile(r'^\s*"([^"]+)"\s*:\s*\{', re.MULTILINE)
    return set(pattern.findall(block))


def build_new_entry(display_key, meta, forms):
    """Build a Python dict entry string for a new root."""
    forms_repr = '[\n            ' + ',\n            '.join(
        f'"{f}"' for f in forms
    ) + '\n        ]'
    freq = meta.get("frequency", len(forms))
    return (
        f'    "{display_key}": {{\n'
        f'        "english":   "{meta["english"]}",\n'
        f'        "domain":    "{meta["domain"]}",\n'
        f'        "frequency": {freq},\n'
        f'        "forms":     {forms_repr},\n'
        f'    }},\n'
    )


def patch_existing_forms(content, key, forms):
    """Replace the forms list for an existing key in the content."""
    forms_repr = "[" + ", ".join(f'"{f}"' for f in forms) + "]"

    # Find the key block
    key_pattern = re.compile(re.escape(f'"{key}"') + r'\s*:\s*\{')
    m = key_pattern.search(content)
    if not m:
        return content, False

    start_pos = m.end()
    # Find block end
    depth = 1
    pos = start_pos
    while pos < len(content) and depth > 0:
        if content[pos] == '{':
            depth += 1
        elif content[pos] == '}':
            depth -= 1
        pos += 1
    block_end = pos

    block = content[start_pos:block_end]
    forms_match = re.search(r'"forms"\s*:\s*\[.*?\]', block, re.DOTALL)
    if not forms_match:
        return content, False

    new_block = (
        block[:forms_match.start()]
        + f'"forms": {forms_repr}'
        + block[forms_match.end():]
    )
    return content[:start_pos] + new_block + content[block_end:], True


def main():
    print("── Add Missing Roots ────────────────────────────────────")

    if not os.path.exists(FORMS_JSON):
        print(f"ERROR: {FORMS_JSON} not found.")
        print("Run: python3 scripts/extract_root_forms.py")
        sys.exit(1)

    forms_data     = load_forms(FORMS_JSON)
    existing_keys  = get_existing_keys(QURAN_DATA)

    print(f"  Roots in verified_root_forms.json : {len(forms_data)}")
    print(f"  Roots currently in quran_data.py  : {len(existing_keys)}")

    with open(QURAN_DATA, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup
    with open(BACKUP_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Backed up to {BACKUP_PATH}")

    patched_count = 0
    added_count   = 0
    new_entries   = []

    for json_key, data in forms_data.items():
        forms = data.get("forms", [])
        if not forms:
            continue

        # Resolve alias
        target_key = KEY_ALIASES.get(json_key, json_key)

        if target_key in existing_keys:
            # Patch the existing entry's forms list
            content, ok = patch_existing_forms(content, target_key, forms)
            if ok:
                patched_count += 1
            else:
                print(f"  WARNING: could not patch forms for '{target_key}'")
        elif json_key in NEW_ROOT_META:
            # Build a new entry to append
            meta        = NEW_ROOT_META[json_key]
            display_key = meta["display"]
            if display_key not in existing_keys:
                new_entries.append(build_new_entry(display_key, meta, forms))
                existing_keys.add(display_key)
                added_count += 1
        else:
            # Skip alias-only keys (امن2 etc) or unknown keys
            pass

    # Insert new entries before the closing } of COMMON_ROOTS
    if new_entries:
        # Group by domain for clean insertion
        domain_sections = {}
        for json_key, meta in NEW_ROOT_META.items():
            dom = meta["domain"]
            if dom not in domain_sections:
                domain_sections[dom] = []
            forms = forms_data.get(json_key, {}).get("forms", [])
            if forms and json_key not in KEY_ALIASES:
                display_key = meta["display"]
                domain_sections[dom].append(
                    build_new_entry(display_key, meta, forms)
                )

        insertion = "\n"
        for domain, entries in domain_sections.items():
            if entries:
                insertion += f"    # ── {domain} (added) ──\n"
                insertion += "".join(entries)

        # Insert before the closing } of COMMON_ROOTS
        close_idx = content.rfind("\n}")
        # Find the COMMON_ROOTS closing brace more precisely
        roots_start = content.find("COMMON_ROOTS = {")
        depth = 0
        pos   = roots_start
        for i, ch in enumerate(content[roots_start:], roots_start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    close_idx = i
                    break

        content = content[:close_idx] + insertion + content[close_idx:]

    with open(QURAN_DATA, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n  ✓ Patched existing roots : {patched_count}")
    print(f"  ✓ Added new roots        : {added_count}")
    print(f"\n  Saved to {QURAN_DATA}")
    print("\n── Next steps ───────────────────────────────────────────")
    print("  python3 db/seed.py")
    print("  python3 dashboard/server.py")


if __name__ == "__main__":
    main()