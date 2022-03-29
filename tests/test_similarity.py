"""
tests/test_similarity.py

Tests for the similarity search module.
Uses synthetic numpy arrays so no real embeddings are needed.

Run with:
    python -m pytest tests/test_similarity.py -v
"""

import os
import sys
import sqlite3
import tempfile
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Fixtures ──────────────────────────────────────────────────────────────────
@pytest.fixture
def tiny_embeddings(tmp_path):
    """
    Create a tiny synthetic embedding set (10 verses, 768 dims).
    Verse IDs: 1:1 through 1:7 and 2:1, 2:2, 2:255.
    Normalized so cosine similarity = dot product.
    """
    verse_ids = ["1:1", "1:2", "1:3", "1:4", "1:5", "1:6", "1:7",
                 "2:1", "2:2", "2:255"]
    n = len(verse_ids)
    dim = 768

    np.random.seed(42)
    raw = np.random.randn(n, dim).astype(np.float32)
    # L2 normalize
    norms = np.linalg.norm(raw, axis=1, keepdims=True)
    embeddings = raw / norms

    npy_path = str(tmp_path / "test_embeddings.npy")
    ids_path  = str(tmp_path / "test_embeddings_verse_ids.txt")

    np.save(npy_path, embeddings)
    with open(ids_path, "w") as f:
        f.write("\n".join(verse_ids))

    return npy_path, ids_path, embeddings, verse_ids


@pytest.fixture
def tiny_db(tmp_path):
    """SQLite DB with the 10 synthetic verses."""
    db_path = str(tmp_path / "test_sim.db")
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "db", "schema.sql"
    )
    conn = sqlite3.connect(db_path)
    with open(schema_path, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    # Insert surahs
    conn.execute("""
        INSERT INTO surahs (surah_number, name_arabic, name_english,
                            revelation_type, revelation_order, total_verses)
        VALUES (1, 'الفاتحة', 'Al-Fatiha', 'Meccan', 5, 7)
    """)
    conn.execute("""
        INSERT INTO surahs (surah_number, name_arabic, name_english,
                            revelation_type, revelation_order, total_verses)
        VALUES (2, 'البقرة', 'Al-Baqarah', 'Medinan', 87, 286)
    """)

    # Insert verses
    verses = [
        ("1:1",  1, 1,   "بِسْمِ اللَّهِ",                  "In the name of Allah"),
        ("1:2",  1, 2,   "الْحَمْدُ لِلَّهِ",                "All praise is due to Allah"),
        ("1:3",  1, 3,   "الرَّحْمَٰنِ الرَّحِيمِ",           "The Entirely Merciful"),
        ("1:4",  1, 4,   "مَالِكِ يَوْمِ الدِّينِ",           "Sovereign of the Day of Recompense"),
        ("1:5",  1, 5,   "إِيَّاكَ نَعْبُدُ",                 "It is You we worship"),
        ("1:6",  1, 6,   "اهْدِنَا الصِّرَاطَ الْمُسْتَقِيمَ","Guide us to the straight path"),
        ("1:7",  1, 7,   "صِرَاطَ الَّذِينَ أَنْعَمْتَ",     "The path of those upon whom"),
        ("2:1",  2, 1,   "الم",                              "Alif, Lam, Meem"),
        ("2:2",  2, 2,   "ذَٰلِكَ الْكِتَابُ",               "This is the Book"),
        ("2:255",2, 255, "اللَّهُ لَا إِلَٰهَ إِلَّا هُوَ", "Allah - there is no deity"),
    ]
    conn.executemany(
        "INSERT INTO verses (verse_id, surah_number, verse_number, arabic_text, english_text) VALUES (?,?,?,?,?)",
        verses
    )
    conn.commit()
    conn.close()
    return db_path


# ── Cache reset helper ────────────────────────────────────────────────────────
def reset_cache():
    """Clear module-level cache between tests."""
    import embeddings.similarity_search as ss
    ss._embeddings_cache = None
    ss._verse_ids_cache  = None


# ── Tests ─────────────────────────────────────────────────────────────────────
class TestFindSimilarVerses:
    def test_returns_list(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("1:1", db_path=tiny_db, npy_path=npy_path, top_k=3)
        assert isinstance(results, list)

    def test_returns_correct_count(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("1:1", db_path=tiny_db, npy_path=npy_path, top_k=3)
        assert len(results) <= 3

    def test_excludes_self(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("2:255", db_path=tiny_db, npy_path=npy_path, top_k=5)
        verse_ids = [r["verse_id"] for r in results]
        assert "2:255" not in verse_ids

    def test_similarity_scores_in_range(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("1:1", db_path=tiny_db, npy_path=npy_path, top_k=5)
        for r in results:
            assert -1.0 <= r["similarity"] <= 1.0

    def test_result_has_required_fields(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("1:1", db_path=tiny_db, npy_path=npy_path, top_k=3)
        if results:
            required = ["verse_id", "arabic_text", "english_text",
                        "surah_number", "surah_name_en", "similarity"]
            for field in required:
                assert field in results[0], f"Missing field '{field}' in result"

    def test_nonexistent_verse_returns_empty(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses("99:99", db_path=tiny_db, npy_path=npy_path, top_k=3)
        assert results == []

    def test_missing_npy_returns_empty(self, tiny_db):
        reset_cache()
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses(
            "1:1",
            db_path=tiny_db,
            npy_path="/nonexistent/path/embeddings.npy",
            top_k=3,
        )
        assert results == []

    def test_caching_works(self, tiny_embeddings, tiny_db):
        """Second call should use cache, not reload from disk."""
        reset_cache()
        npy_path, _, embeddings, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses, _embeddings_cache

        find_similar_verses("1:1", db_path=tiny_db, npy_path=npy_path, top_k=2)

        import embeddings.similarity_search as ss
        assert ss._embeddings_cache is not None
        assert ss._embeddings_cache.shape == embeddings.shape

    def test_exclude_same_surah(self, tiny_embeddings, tiny_db):
        reset_cache()
        npy_path, _, _, _ = tiny_embeddings
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses(
            "1:1",
            db_path=tiny_db,
            npy_path=npy_path,
            top_k=9,
            exclude_same_surah=True,
        )
        surah_ids = [r["surah_number"] for r in results]
        assert 1 not in surah_ids


class TestEmbeddingMath:
    def test_normalized_embeddings_dot_product_leq_1(self):
        """Verify that L2-normalized vectors have cosine sim <= 1."""
        np.random.seed(7)
        vecs = np.random.randn(20, 768).astype(np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        vecs = vecs / norms
        scores = np.dot(vecs, vecs[0])
        assert np.all(scores <= 1.001)   # small float tolerance
        assert np.all(scores >= -1.001)

    def test_self_similarity_is_one(self):
        """A verse compared to itself should have similarity ~1.0."""
        vec = np.random.randn(768).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        score = float(np.dot(vec, vec))
        assert abs(score - 1.0) < 1e-5

    def test_umap_output_shape(self):
        """UMAP 2D output should have shape (n, 2)."""
        try:
            import umap
        except ImportError:
            pytest.skip("umap-learn not installed")

        np.random.seed(0)
        data = np.random.randn(50, 20).astype(np.float32)
        reducer = umap.UMAP(n_components=2, n_neighbors=5, random_state=42)
        out = reducer.fit_transform(data)
        assert out.shape == (50, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
