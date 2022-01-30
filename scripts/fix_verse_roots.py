"""
scripts/fix_verse_roots.py

Diagnoses and fixes the verse_roots table where denormalized columns
(surah_number, revelation_type, revelation_order) may be wrong or missing,
causing surahs to appear in Ayaat list but not in the Distribution chart.

Run from project root:
    python3 scripts/fix_verse_roots.py
"""

import os
import sys
import sqlite3

DB_PATH = "db/quran.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def diagnose(conn):
    cur = conn.cursor()
    print("── Diagnosis ────────────────────────────────────────────")

    # 1. Total rows in verse_roots
    cur.execute("SELECT COUNT(*) FROM verse_roots")
    print(f"  verse_roots total rows      : {cur.fetchone()[0]}")

    # 2. Check Al-Fatiha specifically for رحم
    cur.execute("""
        SELECT verse_id, surah_number, revelation_type, revelation_order
        FROM verse_roots
        WHERE root_arabic = 'رحم'
        AND verse_id LIKE '1:%'
    """)
    rows = cur.fetchall()
    print(f"\n  verse_roots for رحم in Surah 1 (Al-Fatiha):")
    if rows:
        for r in rows:
            print(f"    {dict(r)}")
    else:
        print(f"    NONE FOUND")

    # 3. Check if surah_number is correctly set
    cur.execute("""
        SELECT vr.verse_id, vr.surah_number AS vr_surah,
               v.surah_number AS v_surah,
               vr.revelation_type AS vr_rev,
               s.revelation_type AS s_rev,
               vr.revelation_order AS vr_order,
               s.revelation_order AS s_order
        FROM verse_roots vr
        JOIN verses v  ON vr.verse_id = v.verse_id
        JOIN surahs s  ON v.surah_number = s.surah_number
        WHERE vr.surah_number != v.surah_number
           OR vr.revelation_type != s.revelation_type
           OR vr.revelation_order != s.revelation_order
        LIMIT 10
    """)
    mismatches = cur.fetchall()
    print(f"\n  Mismatched denormalized columns: {len(mismatches)}")
    for r in mismatches[:5]:
        print(f"    {dict(r)}")

    # 4. Check nulls
    cur.execute("""
        SELECT COUNT(*) FROM verse_roots
        WHERE surah_number IS NULL
           OR revelation_type IS NULL
           OR revelation_order IS NULL
    """)
    nulls = cur.fetchone()[0]
    print(f"\n  Rows with NULL denormalized cols: {nulls}")

    # 5. Check v_root_distribution for Al-Fatiha
    cur.execute("""
        SELECT * FROM v_root_distribution
        WHERE root_arabic = 'رحم'
        AND surah_number = 1
    """)
    dist_rows = cur.fetchall()
    print(f"\n  v_root_distribution for رحم, Surah 1:")
    if dist_rows:
        for r in dist_rows:
            print(f"    {dict(r)}")
    else:
        print(f"    NONE — this is why Al-Fatiha is missing from chart")

    # 6. Check what surah_numbers verse_roots has for رحم
    cur.execute("""
        SELECT surah_number, COUNT(*) as cnt
        FROM verse_roots
        WHERE root_arabic = 'رحم'
        GROUP BY surah_number
        ORDER BY surah_number
        LIMIT 10
    """)
    print(f"\n  verse_roots surah distribution for رحم (first 10):")
    for r in cur.fetchall():
        print(f"    Surah {r[0]}: {r[1]} rows")

    return len(mismatches), nulls


def fix_denormalized_columns(conn):
    """
    Update all denormalized columns in verse_roots to match
    the authoritative values from verses + surahs tables.
    """
    cur = conn.cursor()
    print("\n── Fixing denormalized columns ──────────────────────────")

    cur.execute("""
        UPDATE verse_roots
        SET
            surah_number     = (
                SELECT v.surah_number
                FROM verses v
                WHERE v.verse_id = verse_roots.verse_id
            ),
            revelation_type  = (
                SELECT s.revelation_type
                FROM verses v
                JOIN surahs s ON v.surah_number = s.surah_number
                WHERE v.verse_id = verse_roots.verse_id
            ),
            revelation_order = (
                SELECT s.revelation_order
                FROM verses v
                JOIN surahs s ON v.surah_number = s.surah_number
                WHERE v.verse_id = verse_roots.verse_id
            )
        WHERE EXISTS (
            SELECT 1 FROM verses v WHERE v.verse_id = verse_roots.verse_id
        )
    """)
    updated = conn.total_changes
    conn.commit()
    print(f"  Updated {updated} rows.")
    return updated


def verify_fix(conn):
    cur = conn.cursor()
    print("\n── Verification ─────────────────────────────────────────")

    cur.execute("""
        SELECT * FROM v_root_distribution
        WHERE root_arabic = 'رحم'
        AND surah_number = 1
    """)
    rows = cur.fetchall()
    if rows:
        for r in rows:
            print(f"  ✓ Al-Fatiha now in distribution: {dict(r)}")
    else:
        print("  ✗ Al-Fatiha still missing — deeper issue in seed.py")

    # Check total surah count for رحم
    cur.execute("""
        SELECT COUNT(DISTINCT surah_number) as surahs,
               COUNT(*) as verses
        FROM verse_roots
        WHERE root_arabic = 'رحم'
    """)
    r = cur.fetchone()
    print(f"  رحم now covers {r[0]} surahs, {r[1]} Ayaat")

    # Also update root_words.total_occurrences
    cur.execute("""
        UPDATE root_words
        SET total_occurrences = (
            SELECT COUNT(*)
            FROM verse_roots vr
            WHERE vr.root_arabic = root_words.root_arabic
        )
    """)
    conn.commit()
    print(f"  ✓ Updated total_occurrences in root_words table")


def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        sys.exit(1)

    conn = get_conn()

    mismatches, nulls = diagnose(conn)

    if mismatches > 0 or nulls > 0:
        print(f"\n  Found {mismatches} mismatches and {nulls} nulls — fixing...")
        fix_denormalized_columns(conn)
        verify_fix(conn)
    else:
        # Even if no mismatches detected, force a refresh anyway
        print(f"\n  No mismatches found but forcing refresh of denormalized cols...")
        fix_denormalized_columns(conn)
        verify_fix(conn)

    conn.close()
    print("\n── Done ─────────────────────────────────────────────────")
    print("  Restart the dashboard:")
    print("  python3 dashboard/server.py")


if __name__ == "__main__":
    main()