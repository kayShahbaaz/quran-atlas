"""
scripts/export_report.py

Exports analytics data from the database to CSV files.
Useful for sharing data with researchers, or loading into Excel/Sheets
for additional analysis outside the dashboard.

Outputs (in ./exports/):
  - verses_full.csv          All 6236 verses with metadata
  - root_distribution.csv    Root word frequency per surah
  - theme_summary.csv        Theme label + verse count
  - meccan_medinan_roots.csv  Root breakdown by revelation period

Usage:
    python scripts/export_report.py --db ./db/quran.db --out ./exports
"""

import os
import sys
import argparse
import sqlite3
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def export_table(conn, query, output_path, label):
    df = pd.read_sql_query(query, conn)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel Arabic support
    print(f"  Exported {len(df):>6} rows  →  {output_path}  ({label})")
    return df


def main():
    parser = argparse.ArgumentParser(description="Export Quran Analytics data to CSV")
    parser.add_argument("--db",  default="./db/quran.db",  help="SQLite database path")
    parser.add_argument("--out", default="./exports",      help="Output directory")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)
    conn = sqlite3.connect(args.db)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    print("=" * 55)
    print("  Quran Analytics — CSV Exporter")
    print("=" * 55)

    # 1. All verses
    export_table(
        conn,
        "SELECT * FROM v_verses_full ORDER BY surah_number, verse_number",
        os.path.join(args.out, f"verses_full_{timestamp}.csv"),
        "All verses"
    )

    # 2. Root word distribution
    export_table(
        conn,
        """SELECT root_arabic, root_english, domain,
                  surah_number, surah_name_en, revelation_type,
                  revelation_order, occurrences
           FROM v_root_distribution
           ORDER BY root_arabic, revelation_order""",
        os.path.join(args.out, f"root_distribution_{timestamp}.csv"),
        "Root distribution"
    )

    # 3. Root summary (total occurrences)
    export_table(
        conn,
        """SELECT root_arabic, root_english, domain, total_occurrences
           FROM root_words
           ORDER BY total_occurrences DESC""",
        os.path.join(args.out, f"root_summary_{timestamp}.csv"),
        "Root summary"
    )

    # 4. Meccan vs Medinan root breakdown
    export_table(
        conn,
        """SELECT rw.root_arabic, rw.root_english, rw.domain,
                  SUM(CASE WHEN vr.revelation_type = 'Meccan'  THEN 1 ELSE 0 END) AS meccan_count,
                  SUM(CASE WHEN vr.revelation_type = 'Medinan' THEN 1 ELSE 0 END) AS medinan_count,
                  COUNT(*) AS total
           FROM verse_roots vr
           JOIN root_words rw ON vr.root_arabic = rw.root_arabic
           GROUP BY rw.root_arabic
           ORDER BY total DESC""",
        os.path.join(args.out, f"meccan_medinan_roots_{timestamp}.csv"),
        "Meccan/Medinan root breakdown"
    )

    # 5. Theme summary
    export_table(
        conn,
        """SELECT t.cluster_id, t.label_english, t.label_arabic,
                  t.verse_count,
                  SUM(CASE WHEN vt.revelation_type='Meccan'  THEN 1 ELSE 0 END) AS meccan_verses,
                  SUM(CASE WHEN vt.revelation_type='Medinan' THEN 1 ELSE 0 END) AS medinan_verses
           FROM themes t
           LEFT JOIN verse_themes vt ON t.cluster_id = vt.cluster_id
           GROUP BY t.cluster_id
           ORDER BY t.verse_count DESC""",
        os.path.join(args.out, f"theme_summary_{timestamp}.csv"),
        "Theme summary"
    )

    # 6. Per-verse theme assignments
    export_table(
        conn,
        """SELECT vf.verse_id, vf.surah_number, vf.name_english,
                  vf.revelation_type, vf.arabic_text, vf.english_text,
                  t.label_english AS theme
           FROM v_verses_full vf
           LEFT JOIN verse_themes vt ON vf.verse_id = vt.verse_id
           LEFT JOIN themes t        ON vt.cluster_id = t.cluster_id
           ORDER BY vf.surah_number, vf.verse_number""",
        os.path.join(args.out, f"verses_with_themes_{timestamp}.csv"),
        "Verses + themes"
    )

    conn.close()
    print(f"\nAll exports saved to: {args.out}/")
    print("Note: CSV files use UTF-8 with BOM for Arabic compatibility in Excel.")


if __name__ == "__main__":
    main()
