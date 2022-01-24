"""
scripts/fix_duplicates.py

Fixes two problems:
1. Duplicate root keys in COMMON_ROOTS (causes duplicate dropdown entries)
2. Diagnoses whether db/seed.py needs to be rerun

Run from project root:
    python3 scripts/fix_duplicates.py

This edits data/quran_data.py in-place, backing up the original.
"""

import os
import re
import sys
import sqlite3

QURAN_DATA  = "data/quran_data.py"
BACKUP_PATH = "data/quran_data_pre_dedup.py"
DB_PATH     = "db/quran.db"


def check_db_state():
    """Report what's currently in the DB so we know if seed.py has been run."""
    print("\n── DB Diagnostic ─────────────────────────────────────────")
    if not os.path.exists(DB_PATH):
        print(f"  ERROR: {DB_PATH} not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Check verse_roots table
    cur.execute("SELECT COUNT(*) FROM verse_roots")
    total = cur.fetchone()[0]
    print(f"  verse_roots total rows : {total}")

    # Check if Al-Fatiha is in verse_roots for رحم
    cur.execute("""
        SELECT verse_id, root_arabic
        FROM verse_roots
        WHERE root_arabic = 'رحم'
        AND verse_id LIKE '1:%'
        ORDER BY verse_id
    """)
    fatiha_rows = cur.fetchall()
    if fatiha_rows:
        print(f"  Al-Fatiha rows for رحم : {fatiha_rows}  ← GOOD, seed.py was run")
    else:
        print(f"  Al-Fatiha rows for رحم : NONE ← seed.py NOT run with new code yet")

    # Check for duplicate root_arabic values in root_words table
    cur.execute("""
        SELECT root_arabic, COUNT(*) as cnt
        FROM root_words
        GROUP BY root_arabic
        HAVING cnt > 1
        ORDER BY cnt DESC
    """)
    dups = cur.fetchall()
    if dups:
        print(f"  Duplicate roots in root_words table: {dups}")
    else:
        print(f"  No duplicate roots in root_words table.")

    conn.close()


def find_duplicate_keys_in_file(filepath):
    """Find all root keys that appear more than once in COMMON_ROOTS."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find the COMMON_ROOTS block
    start = content.find("COMMON_ROOTS = {")
    end   = content.find("\ndef ", start)
    if end == -1:
        end = len(content)
    block = content[start:end]

    # Extract all keys
    key_pattern = re.compile(r'^\s*"([^"]+)"\s*:\s*\{', re.MULTILINE)
    keys = key_pattern.findall(block)

    seen = {}
    duplicates = []
    for key in keys:
        if key in seen:
            duplicates.append(key)
        else:
            seen[key] = True

    return keys, duplicates


def remove_duplicate_keys(filepath, backup_path):
    """Remove duplicate root entries, keeping only the first occurrence."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Backup
    with open(backup_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Backed up to {backup_path}")

    # Find COMMON_ROOTS block boundaries
    start_idx = content.find("COMMON_ROOTS = {")
    # Find the matching closing brace
    depth = 0
    end_idx = start_idx
    for i, ch in enumerate(content[start_idx:], start_idx):
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    before = content[:start_idx]
    block  = content[start_idx:end_idx]
    after  = content[end_idx:]

    # Parse individual root entries within the block
    # Each entry is: "key": { ... },
    # We'll reconstruct the block keeping only first occurrences

    # Split on the pattern that starts a new root entry
    # Pattern: newline + optional spaces + "key": {
    entry_pattern = re.compile(
        r'(\n\s*#[^\n]*\n|\n\s*"[^"]+"\s*:\s*\{)',
    )

    parts  = entry_pattern.split(block)
    seen   = set()
    result = parts[0]  # "COMMON_ROOTS = {"

    i = 1
    removed = []
    while i < len(parts):
        separator = parts[i]     # the matched pattern (comment or key line)
        body      = parts[i+1] if i+1 < len(parts) else ""
        i += 2

        # Check if this separator is a root key line
        key_match = re.match(r'\n\s*"([^"]+)"\s*:\s*\{', separator)
        if key_match:
            key = key_match.group(1)
            if key in seen:
                removed.append(key)
                continue   # skip this duplicate entry
            seen.add(key)

        result += separator + body

    # Reconstruct full content
    new_content = before + result + after

    return new_content, removed


def main():
    print("── Duplicate Root Key Fixer ─────────────────────────────")

    if not os.path.exists(QURAN_DATA):
        print(f"ERROR: {QURAN_DATA} not found. Run from project root.")
        sys.exit(1)

    # Step 1: Find duplicates
    keys, duplicates = find_duplicate_keys_in_file(QURAN_DATA)
    print(f"  Total root entries : {len(keys)}")
    print(f"  Unique keys        : {len(set(keys))}")
    if duplicates:
        print(f"  Duplicate keys     : {duplicates}")
    else:
        print(f"  No duplicates found in quran_data.py.")

    # Step 2: Check DB state
    check_db_state()

    # Step 3: Remove duplicates if any
    if duplicates:
        print(f"\n  Removing {len(duplicates)} duplicate(s)...")
        new_content, removed = remove_duplicate_keys(QURAN_DATA, BACKUP_PATH)
        with open(QURAN_DATA, "w", encoding="utf-8") as f:
            f.write(new_content)
        print(f"  Removed: {removed}")
        print(f"  Saved to {QURAN_DATA}")
    else:
        print(f"\n  Nothing to remove.")

    print("\n── What to do next ──────────────────────────────────────")
    print("  The DB diagnostic above tells you whether seed.py needs")
    print("  to be run. If Al-Fatiha rows for رحم show NONE, run:")
    print()
    print("    python3 db/seed.py")
    print("    python3 dashboard/server.py")
    print()
    print("  This will fix BOTH issues:")
    print("    ✓ Duplicate dropdown entries (fixed by dedup above)")
    print("    ✓ Missing Al-Fatiha and other famous Ayaat (fixed by seed.py)")


if __name__ == "__main__":
    main()