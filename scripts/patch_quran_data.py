"""
scripts/patch_quran_data.py

After running extract_root_forms.py, run this to automatically
patch the verified forms into data/quran_data.py.

Usage:
    python3 scripts/patch_quran_data.py

What it does:
    1. Reads data/verified_root_forms.json
    2. Reads data/quran_data.py
    3. Replaces the "forms": [...] list for each root with the
       verified forms from the JSON
    4. Writes the patched file back to data/quran_data.py
    5. Also fixes duplicate root keys in COMMON_ROOTS
"""

import os
import sys
import json
import re

FORMS_JSON   = "data/verified_root_forms.json"
QURAN_DATA   = "data/quran_data.py"
BACKUP_PATH  = "data/quran_data_backup.py"


def load_forms(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def patch_quran_data(forms_data, source_path, backup_path):
    # Backup original
    with open(source_path, "r", encoding="utf-8") as f:
        original = f.read()
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(original)
    print(f"  Backed up original to {backup_path}")

    patched = original

    # For each root in the forms data, find the "forms": [...] entry
    # under that root's dict and replace it
    patch_count = 0
    for root_key, data in forms_data.items():
        forms = data.get("forms", [])
        if not forms:
            continue

        # Build replacement forms list as Python code
        forms_repr = "[" + ", ".join(f'"{f}"' for f in forms) + "]"

        # Pattern: find the root key entry and its "forms": [...] line
        # We look for the root key (as dict key) followed by its forms list
        # Use a pattern that matches  "forms": [...],  (possibly multiline)
        # within the block for this root

        # Strategy: find the root key string in the file, then find the
        # next "forms": [...] after it, and replace just that forms list
        root_pattern = re.escape(f'"{root_key}"') + r'\s*:\s*\{'
        root_match = re.search(root_pattern, patched)
        if not root_match:
            # Try without quotes (bare key)
            root_pattern2 = re.escape(root_key) + r'\s*:\s*\{'
            root_match = re.search(root_pattern2, patched)

        if not root_match:
            print(f"  WARNING: root key '{root_key}' not found in quran_data.py — skipping")
            continue

        # Find "forms": [...] starting after this root's opening brace
        start_pos = root_match.end()
        # Find the closing } of this root's dict
        # Count braces to find the matching close
        depth = 1
        pos = start_pos
        while pos < len(patched) and depth > 0:
            if patched[pos] == '{':
                depth += 1
            elif patched[pos] == '}':
                depth -= 1
            pos += 1
        block_end = pos

        block = patched[start_pos:block_end]

        # Replace "forms": [...] within this block
        # Match the forms list — could be single line or multi-line
        forms_in_block = re.search(
            r'"forms"\s*:\s*\[.*?\]',
            block,
            re.DOTALL
        )
        if not forms_in_block:
            print(f"  WARNING: no 'forms' key found for root '{root_key}' — skipping")
            continue

        new_block = (
            block[:forms_in_block.start()]
            + f'"forms": {forms_repr}'
            + block[forms_in_block.end():]
        )
        patched = patched[:start_pos] + new_block + patched[block_end:]
        patch_count += 1

    print(f"  Patched {patch_count} roots.")
    return patched


def fix_duplicates(patched):
    """
    Remove duplicate root entries from COMMON_ROOTS.
    Keeps the first occurrence of each root key.
    """
    # Find duplicate keys — Python dicts in source will silently overwrite,
    # but we want to clean them up for clarity.
    seen = set()
    lines = patched.split('\n')
    cleaned = []
    in_roots = False
    skip_block = False
    depth = 0

    for line in lines:
        if 'COMMON_ROOTS' in line and '=' in line:
            in_roots = True

        if in_roots:
            # Detect root key lines like:  "رحم": {
            key_match = re.match(r'\s*"([^"]+)"\s*:\s*\{', line)
            if key_match:
                key = key_match.group(1)
                if key in seen:
                    skip_block = True
                    depth = 1
                    print(f"  Removing duplicate root key: {key}")
                    continue
                else:
                    seen.add(key)

            if skip_block:
                for ch in line:
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                if depth <= 0:
                    skip_block = False
                continue

        cleaned.append(line)

    return '\n'.join(cleaned)


def main():
    if not os.path.exists(FORMS_JSON):
        print(f"ERROR: {FORMS_JSON} not found.")
        print("Run first:  python3 scripts/extract_root_forms.py")
        sys.exit(1)

    if not os.path.exists(QURAN_DATA):
        print(f"ERROR: {QURAN_DATA} not found.")
        sys.exit(1)

    print("Loading verified forms...")
    forms_data = load_forms(FORMS_JSON)
    print(f"  {len(forms_data)} roots loaded from JSON.")

    print("Patching quran_data.py...")
    patched = patch_quran_data(forms_data, QURAN_DATA, BACKUP_PATH)

    print("Fixing duplicate root keys...")
    patched = fix_duplicates(patched)

    with open(QURAN_DATA, "w", encoding="utf-8") as f:
        f.write(patched)
    print(f"  Written to {QURAN_DATA}")

    print("\nDone. Next steps:")
    print("  python3 db/seed.py          ← rebuild database")
    print("  python3 dashboard/server.py ← restart dashboard")


if __name__ == "__main__":
    main()