"""
embeddings/similarity_search.py

Fast cosine similarity search over verse embeddings.
Used by the dashboard "Find Similar Verses" feature.

Since we L2-normalized the embeddings during generation,
cosine_similarity = dot product — so we just use np.dot.

No FAISS needed for 6236 verses — numpy is fast enough (< 10ms per query).
"""

import os
import sys
import numpy as np
import sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Module-level cache so we don't reload every query
_embeddings_cache = None
_verse_ids_cache = None


def load_embeddings_cached(npy_path: str, ids_path: str):
    """Load embeddings once and keep in memory."""
    global _embeddings_cache, _verse_ids_cache

    if _embeddings_cache is None:
        if not os.path.exists(npy_path):
            return None, None

        _embeddings_cache = np.load(npy_path)
        with open(ids_path, "r", encoding="utf-8") as f:
            _verse_ids_cache = [line.strip() for line in f if line.strip()]

    return _embeddings_cache, _verse_ids_cache


def find_similar_verses(
    query_verse_id: str,
    db_path: str,
    npy_path: str = "./embeddings/verse_embeddings.npy",
    top_k: int = 10,
    exclude_same_surah: bool = False,
) -> list:
    """
    Find the top-k most semantically similar verses to a given verse.

    Returns a list of dicts:
        [{"verse_id": "2:255", "similarity": 0.92, "arabic": "...", "english": "...", ...}, ...]

    The returned list excludes the query verse itself.
    """
    ids_path = npy_path.replace(".npy", "_verse_ids.txt")
    embeddings, verse_ids = load_embeddings_cached(npy_path, ids_path)

    if embeddings is None:
        return []

    # Find index of query verse
    if query_verse_id not in verse_ids:
        return []

    query_idx = verse_ids.index(query_verse_id)
    query_vec = embeddings[query_idx]

    # Cosine similarity = dot product (embeddings are L2-normalized)
    scores = np.dot(embeddings, query_vec)  # shape: (n_verses,)
    scores[query_idx] = -1  # exclude self

    # Get top-k indices
    top_indices = np.argsort(scores)[::-1][:top_k + 20]  # grab extra in case we filter

    # Fetch verse details from DB
    conn = sqlite3.connect(db_path)
    results = []

    for idx in top_indices:
        if len(results) >= top_k:
            break

        vid = verse_ids[idx]
        row = conn.execute(
            """SELECT verse_id, arabic_text, english_text,
                      surah_number, name_english, revelation_type, verse_number
               FROM v_verses_full
               WHERE verse_id = ?""",
            (vid,)
        ).fetchone()

        if not row:
            continue

        if exclude_same_surah:
            query_surah = int(query_verse_id.split(":")[0])
            if row[3] == query_surah:
                continue

        results.append({
            "verse_id":       row[0],
            "arabic_text":    row[1],
            "english_text":   row[2],
            "surah_number":   row[3],
            "surah_name_en":  row[4],
            "revelation_type": row[5],
            "verse_number":   row[6],
            "similarity":     float(scores[idx]),
        })

    conn.close()
    return results


def search_by_text(
    query_text: str,
    db_path: str,
    npy_path: str = "./embeddings/verse_embeddings.npy",
    top_k: int = 10,
) -> list:
    """
    Semantic search: given a free-text query (Arabic or English),
    find the most relevant verses.

    This requires encoding the query with the same model.
    Falls back to empty list if sentence_transformers not available.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers not installed — text search unavailable")
        return []

    ids_path = npy_path.replace(".npy", "_verse_ids.txt")
    embeddings, verse_ids = load_embeddings_cached(npy_path, ids_path)
    if embeddings is None:
        return []

    print(f"Encoding query: '{query_text}'")
    model = SentenceTransformer("bert-base-multilingual-cased")
    query_vec = model.encode([query_text], normalize_embeddings=True)[0]

    scores = np.dot(embeddings, query_vec)
    top_indices = np.argsort(scores)[::-1][:top_k]

    conn = sqlite3.connect(db_path)
    results = []

    for idx in top_indices:
        vid = verse_ids[idx]
        row = conn.execute(
            """SELECT verse_id, arabic_text, english_text,
                      surah_number, name_english, revelation_type, verse_number
               FROM v_verses_full WHERE verse_id = ?""",
            (vid,)
        ).fetchone()

        if row:
            results.append({
                "verse_id":       row[0],
                "arabic_text":    row[1],
                "english_text":   row[2],
                "surah_number":   row[3],
                "surah_name_en":  row[4],
                "revelation_type": row[5],
                "verse_number":   row[6],
                "similarity":     float(scores[idx]),
            })

    conn.close()
    return results


if __name__ == "__main__":
    # quick test
    results = find_similar_verses(
        query_verse_id="2:255",  # Ayat al-Kursi
        db_path="./db/quran.db",
        top_k=5,
    )
    print(f"\nVerses most similar to 2:255 (Ayat al-Kursi):")
    for r in results:
        print(f"  {r['verse_id']:<8} ({r['surah_name_en']:<20}) sim={r['similarity']:.3f}")
        print(f"  {r['english_text'][:100]}...")
        print()
