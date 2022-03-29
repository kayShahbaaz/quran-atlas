"""
tests/test_pipeline.py

Basic tests for the data pipeline.

Run with:
    python -m pytest tests/ -v

These tests use a small synthetic dataset so they don't need
the real Tanzil XML or internet access to run.
"""

import os
import sys
import sqlite3
import tempfile
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def sample_arabic_df():
    """A tiny synthetic Arabic verse DataFrame."""
    return pd.DataFrame([
        {"surah_number": 1, "verse_number": 1, "arabic_text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ"},
        {"surah_number": 1, "verse_number": 2, "arabic_text": "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ"},
        {"surah_number": 1, "verse_number": 3, "arabic_text": "الرَّحْمَٰنِ الرَّحِيمِ"},
        {"surah_number": 2, "verse_number": 1, "arabic_text": "الم"},
        {"surah_number": 2, "verse_number": 255, "arabic_text": "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ الْحَيُّ الْقَيُّومُ"},
    ])


@pytest.fixture
def sample_english_df():
    """A tiny synthetic English translation DataFrame."""
    return pd.DataFrame([
        {"surah_number": 1, "verse_number": 1, "english_text": "In the name of Allah, the Entirely Merciful, the Especially Merciful."},
        {"surah_number": 1, "verse_number": 2, "english_text": "All praise is due to Allah, Lord of the worlds."},
        {"surah_number": 1, "verse_number": 3, "english_text": "The Entirely Merciful, the Especially Merciful."},
        {"surah_number": 2, "verse_number": 1, "english_text": "Alif, Lam, Meem."},
        {"surah_number": 2, "verse_number": 255, "english_text": "Allah - there is no deity except Him, the Ever-Living, the Sustainer of existence."},
    ])


@pytest.fixture
def temp_db(tmp_path):
    """Create a temp SQLite DB from schema.sql."""
    db_path = str(tmp_path / "test.db")
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "db", "schema.sql"
    )
    conn = sqlite3.connect(db_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    return db_path


# ── Data loading tests ────────────────────────────────────────────────────────
class TestDataMerge:
    def test_merge_basic(self, sample_arabic_df, sample_english_df):
        from data.quran_data import merge_quran_data
        merged = merge_quran_data(sample_arabic_df, sample_english_df)

        assert len(merged) == 5
        assert "verse_id" in merged.columns
        assert "arabic_text" in merged.columns
        assert "english_text" in merged.columns
        assert "revelation_type" in merged.columns

    def test_verse_id_format(self, sample_arabic_df, sample_english_df):
        from data.quran_data import merge_quran_data
        merged = merge_quran_data(sample_arabic_df, sample_english_df)

        assert "1:1" in merged["verse_id"].values
        assert "2:255" in merged["verse_id"].values

    def test_revelation_type_assigned(self, sample_arabic_df, sample_english_df):
        from data.quran_data import merge_quran_data
        merged = merge_quran_data(sample_arabic_df, sample_english_df)

        surah1 = merged[merged["surah_number"] == 1]
        assert surah1["revelation_type"].iloc[0] == "Meccan"

        surah2 = merged[merged["surah_number"] == 2]
        assert surah2["revelation_type"].iloc[0] == "Medinan"

    def test_no_missing_verse_ids(self, sample_arabic_df, sample_english_df):
        from data.quran_data import merge_quran_data
        merged = merge_quran_data(sample_arabic_df, sample_english_df)
        assert merged["verse_id"].isna().sum() == 0


class TestRootDetection:
    def test_root_found_in_text(self):
        from data.quran_data import get_root_word_occurrences
        import pandas as pd

        df = pd.DataFrame([{
            "verse_id": "1:1",
            "surah_number": 1,
            "verse_number": 1,
            "arabic_text": "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
            "revelation": "Meccan",
            "revelation_order": 5,
        }])
        results = get_root_word_occurrences(df)
        # رحم root should appear in Al-Fatiha verse 1
        assert "رحم" in results["root"].values

    def test_returns_dataframe(self):
        from data.quran_data import get_root_word_occurrences
        import pandas as pd

        empty_df = pd.DataFrame(columns=[
            "verse_id", "surah_number", "verse_number",
            "arabic_text", "revelation", "revelation_order"
        ])
        result = get_root_word_occurrences(empty_df)
        assert isinstance(result, pd.DataFrame)


# ── Database tests ────────────────────────────────────────────────────────────
class TestDatabase:
    def test_schema_creates_tables(self, temp_db):
        conn = sqlite3.connect(temp_db)
        tables = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        conn.close()

        expected = ["surahs", "verses", "root_words", "verse_roots",
                    "themes", "verse_themes", "embeddings_meta"]
        for t in expected:
            assert t in tables, f"Table '{t}' missing from schema"

    def test_schema_creates_views(self, temp_db):
        conn = sqlite3.connect(temp_db)
        views = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='view'"
        ).fetchall()]
        conn.close()

        expected = ["v_verses_full", "v_root_distribution", "v_theme_by_revelation"]
        for v in expected:
            assert v in views, f"View '{v}' missing from schema"

    def test_insert_surah(self, temp_db):
        conn = sqlite3.connect(temp_db)
        conn.execute(
            """INSERT INTO surahs
               (surah_number, name_arabic, name_english, revelation_type,
                revelation_order, total_verses)
               VALUES (1, 'الفاتحة', 'Al-Fatiha', 'Meccan', 5, 7)"""
        )
        conn.commit()
        count = conn.execute("SELECT COUNT(*) FROM surahs").fetchone()[0]
        conn.close()
        assert count == 1

    def test_insert_verse(self, temp_db):
        conn = sqlite3.connect(temp_db)
        # Insert surah first (FK)
        conn.execute(
            """INSERT INTO surahs
               (surah_number, name_arabic, name_english, revelation_type,
                revelation_order, total_verses)
               VALUES (1, 'الفاتحة', 'Al-Fatiha', 'Meccan', 5, 7)"""
        )
        conn.execute(
            """INSERT INTO verses
               (verse_id, surah_number, verse_number, arabic_text, english_text)
               VALUES ('1:1', 1, 1, 'بِسْمِ اللَّهِ', 'In the name of Allah')"""
        )
        conn.commit()
        row = conn.execute("SELECT * FROM verses WHERE verse_id = '1:1'").fetchone()
        conn.close()
        assert row is not None
        assert row[2] == 1  # surah_number

    def test_revelation_type_constraint(self, temp_db):
        conn = sqlite3.connect(temp_db)
        with pytest.raises(Exception):
            conn.execute(
                """INSERT INTO surahs
                   (surah_number, name_arabic, name_english, revelation_type,
                    revelation_order, total_verses)
                   VALUES (200, 'test', 'test', 'INVALID_TYPE', 1, 1)"""
            )
            conn.commit()
        conn.close()


# ── SURAH_METADATA tests ──────────────────────────────────────────────────────
class TestSurahMetadata:
    def test_all_114_surahs_present(self):
        from data.quran_data import SURAH_METADATA
        assert len(SURAH_METADATA) == 114

    def test_all_have_required_fields(self):
        from data.quran_data import SURAH_METADATA
        required = ["name_ar", "name_en", "revelation", "revelation_order", "verses"]
        for num, meta in SURAH_METADATA.items():
            for field in required:
                assert field in meta, f"Surah {num} missing '{field}'"

    def test_revelation_values_valid(self):
        from data.quran_data import SURAH_METADATA
        valid = {"Meccan", "Medinan"}
        for num, meta in SURAH_METADATA.items():
            assert meta["revelation"] in valid, \
                f"Surah {num} has invalid revelation: {meta['revelation']}"

    def test_revelation_orders_unique(self):
        from data.quran_data import SURAH_METADATA
        orders = [m["revelation_order"] for m in SURAH_METADATA.values()]
        assert len(orders) == len(set(orders)), "Revelation orders are not unique"

    def test_surah_1_is_fatiha(self):
        from data.quran_data import SURAH_METADATA
        assert SURAH_METADATA[1]["name_en"] == "Al-Fatiha"
        assert SURAH_METADATA[1]["revelation"] == "Meccan"
        assert SURAH_METADATA[1]["verses"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
