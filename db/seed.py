"""
db/seed.py

Creates the SQLite database from schema.sql, then seeds it with:
  - Surah metadata
  - All verses (Arabic + English)
  - Root word definitions
  - Verse-root associations

Run this AFTER generating embeddings if you want theme data too,
or run it standalone first to get the base database working.

Usage:
    python db/seed.py --xml ./data/quran-simple.xml --db ./db/quran.db
"""

import os
import sys
import sqlite3
import argparse

# make sure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.quran_data import (
    parse_tanzil_xml,
    load_sahih_international,
    merge_quran_data,
    get_root_word_occurrences,
    SURAH_METADATA,
    COMMON_ROOTS,
)


def create_database(db_path: str, schema_path: str) -> sqlite3.Connection:
    """Initialize the database using schema.sql."""
    print(f"Creating database at: {db_path}")
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # SQLite doesn't support executescript with parameterized queries,
    # so we split on semicolons and run each statement
    conn.executescript(schema_sql)
    conn.commit()
    print("  Schema applied.")
    return conn


def seed_surahs(conn: sqlite3.Connection):
    """Insert surah metadata."""
    print("Seeding surahs...")

    # Juz boundaries (which surah each juz starts in — approximate)
    JUZ_MAP = {
        1: 1, 2: 2, 3: 2, 4: 3, 5: 4, 6: 4, 7: 5, 8: 6, 9: 7, 10: 8,
        11: 9, 12: 10, 13: 12, 14: 15, 15: 17, 16: 18, 17: 21, 18: 23,
        19: 25, 20: 27, 21: 29, 22: 33, 23: 36, 24: 39, 25: 41, 26: 46,
        27: 51, 28: 58, 29: 67, 30: 78
    }
    # build reverse map: surah -> juz
    surah_to_juz = {}
    for juz, start_surah in JUZ_MAP.items():
        for s in range(start_surah, 115):
            if s not in surah_to_juz:
                surah_to_juz[s] = juz

    rows = []
    for surah_num, meta in SURAH_METADATA.items():
        rows.append((
            surah_num,
            meta["name_ar"],
            meta["name_en"],
            meta["revelation"],
            meta["revelation_order"],
            meta["verses"],
            surah_to_juz.get(surah_num, 1),
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO surahs
           (surah_number, name_arabic, name_english, revelation_type,
            revelation_order, total_verses, juz_start)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} surahs.")


def seed_verses(conn: sqlite3.Connection, merged_df):
    """Insert all verses."""
    print("Seeding verses...")

    rows = []
    for _, row in merged_df.iterrows():
        arabic = row.get("arabic_text", "") or ""
        english = row.get("english_text", "") or ""
        # rough word count: split on spaces
        word_count = len(arabic.split()) if arabic else 0
        char_count = len(arabic.replace(" ", "")) if arabic else 0

        rows.append((
            row["verse_id"],
            int(row["surah_number"]),
            int(row["verse_number"]),
            arabic,
            english,
            word_count,
            char_count,
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO verses
           (verse_id, surah_number, verse_number, arabic_text, english_text,
            word_count_ar, char_count_ar)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} verses.")


def seed_root_words(conn: sqlite3.Connection):
    """Insert root word definitions with Leeds corpus frequency."""
    print("Seeding root words...")

    rows = [
        (root, info["english"], info["domain"], info.get("frequency", 0))
        for root, info in COMMON_ROOTS.items()
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO root_words
           (root_arabic, root_english, domain, total_occurrences)
           VALUES (?, ?, ?, ?)""",
        rows,
    )
    conn.commit()
    print(f"  Inserted {len(rows)} root words.")


def seed_verse_roots(conn: sqlite3.Connection, roots_df):
    """Insert verse-root associations."""
    print("Seeding verse-root associations...")

    rows = []
    for _, row in roots_df.iterrows():
        rows.append((
            row["verse_id"],
            row["root"],
            int(row["surah_number"]),
            row["revelation"],
            int(row["revelation_order"]),
        ))

    conn.executemany(
        """INSERT OR IGNORE INTO verse_roots
           (verse_id, root_arabic, surah_number, revelation_type, revelation_order)
           VALUES (?, ?, ?, ?, ?)""",
        rows,
    )
    conn.commit()

    # Update total_occurrences in root_words
    conn.execute("""
        UPDATE root_words
        SET total_occurrences = (
            SELECT COUNT(*) FROM verse_roots
            WHERE verse_roots.root_arabic = root_words.root_arabic
        )
    """)
    conn.commit()
    print(f"  Inserted {len(rows)} verse-root pairs.")


def seed_default_themes(conn: sqlite3.Connection):
    """
    Insert placeholder themes.
    These get replaced when cluster_themes.py runs,
    but having defaults means the dashboard won't crash on first load.
    """
    print("Seeding default placeholder themes...")

    default_themes = [
        (0,  "Divine Attributes & Monotheism",   "الصفات الإلهية والتوحيد",  "#C0392B"),
        (1,  "Prophethood & Revelation",          "النبوة والوحي",            "#8E44AD"),
        (2,  "Faith & Belief",                    "الإيمان والعقيدة",         "#2980B9"),
        (3,  "Worship & Devotion",                "العبادة والتقوى",          "#1ABC9C"),
        (4,  "Ethics & Character",                "الأخلاق والسلوك",          "#27AE60"),
        (5,  "Justice & Law",                     "العدل والشريعة",           "#F39C12"),
        (6,  "Economics & Society",               "الاقتصاد والمجتمع",        "#D35400"),
        (7,  "Nature & Creation",                 "الطبيعة والخلق",           "#16A085"),
        (8,  "Historical Narratives",             "القصص التاريخية",          "#7F8C8D"),
        (9,  "Eschatology & Afterlife",           "الآخرة والجزاء",           "#2C3E50"),
        (10, "Spiritual & Inner Life",            "الروح والباطن",            "#6C3483"),
        (11, "Community & Relations",             "المجتمع والعلاقات",        "#117A65"),
    ]

    conn.executemany(
        """INSERT OR REPLACE INTO themes
           (cluster_id, label_english, label_arabic, color_hex)
           VALUES (?, ?, ?, ?)""",
        default_themes,
    )
    conn.commit()
    print(f"  Inserted {len(default_themes)} default themes.")


def print_summary(conn: sqlite3.Connection):
    """Print a quick summary of what was seeded."""
    print("\n── Database Summary ─────────────────────────────────")
    for table in ["surahs", "verses", "root_words", "verse_roots", "themes"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<20} {count:>6} rows")

    print("\n── Root Word Top 10 by Occurrence ───────────────────")
    rows = conn.execute("""
        SELECT root_arabic, root_english, total_occurrences
        FROM root_words
        ORDER BY total_occurrences DESC
        LIMIT 10
    """).fetchall()
    for r in rows:
        print(f"  {r[0]:<10} ({r[1]:<30}) — {r[2]} verses")
    print("─────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(description="Seed the Quran Analytics database")
    parser.add_argument("--xml",    default="./data/quran-simple.xml", help="Path to Tanzil XML file")
    parser.add_argument("--trans",  default=None,                      help="Path to Sahih International CSV (optional)")
    parser.add_argument("--db",     default="./db/quran.db",           help="Output SQLite database path")
    parser.add_argument("--schema", default="./db/schema.sql",         help="Path to schema.sql")
    args = parser.parse_args()

    print("=" * 55)
    print("  Quran Analytics — Database Seeder")
    print("=" * 55)

    # 1. Create database
    conn = create_database(args.db, args.schema)

    # 2. Load and parse data
    arabic_df  = parse_tanzil_xml(args.xml)
    english_df = load_sahih_international(args.trans)
    merged_df  = merge_quran_data(arabic_df, english_df)
    roots_df   = get_root_word_occurrences(merged_df)

    # 3. Seed all tables
    seed_surahs(conn, )
    seed_root_words(conn)
    seed_verses(conn, merged_df)
    seed_verse_roots(conn, roots_df)
    seed_default_themes(conn)

    # 4. Summary
    print_summary(conn)
    conn.close()

    print(f"Done! Database saved to: {args.db}")
    print("Next step: run  python embeddings/generate_embeddings.py  to add semantic embeddings.")


if __name__ == "__main__":
    main()
