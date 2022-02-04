"""
embeddings/generate_embeddings.py

Generates semantic embeddings for all Quran verses using
paraphrase-multilingual-mpnet-base-v2 via sentence-transformers.

Why paraphrase-multilingual-mpnet-base-v2 over mBERT?
  - mBERT was designed for classification/NER, NOT semantic similarity
  - paraphrase-multilingual-mpnet-base-v2 was trained specifically on
    50M+ sentence pairs for semantic similarity tasks (released 2021)
  - Produces 768-dim embeddings, same shape as mBERT — zero code changes
  - Dramatically better cosine similarity scores for thematic search
  - Still multilingual — handles Arabic context in combined mode

The embeddings are saved as a NumPy .npy file because:
  - Fast to load (~0.1s vs minutes for re-inference)
  - SQLite BLOBs for 6236 x 768 floats = 145MB — too heavy
  - .npy keeps it simple and portable

Usage:
    python3 embeddings/generate_embeddings.py --db ./db/quran.db

This takes ~20-40 minutes on CPU. On GPU, around 3-5 minutes.
Don't interrupt it — if it crashes, just re-run.
"""

import os
import sys
import sqlite3
import argparse
import numpy as np
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Model config ──────────────────────────────────────────────────────────────
MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
# First run downloads ~1.1GB — one time only, cached in ~/.cache/torch
# Same sentence-transformers library, no new installs needed


def load_verses_from_db(db_path: str):
    """
    Load all verses from the database.
    Returns list of (verse_id, arabic_text, english_text) tuples.
    """
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT verse_id, arabic_text, english_text FROM verses ORDER BY surah_number, verse_number"
    ).fetchall()
    conn.close()
    return rows


def build_input_texts(rows, mode: str = "combined") -> list:
    """
    Build the list of strings to embed.

    mode options:
      "arabic"   — embed Arabic text only
      "english"  — embed English translation only
      "combined" — embed "arabic | english" together (best results)

    "combined" is strongly recommended with this model because:
      - The model was trained primarily on European languages
      - Including the English translation anchors the semantic meaning
      - Arabic morphological variation is handled via the English side
    """
    texts = []
    for verse_id, arabic, english in rows:
        arabic  = arabic  or ""
        english = english or ""

        if mode == "arabic":
            texts.append(arabic)
        elif mode == "english":
            texts.append(english)
        else:  # combined — default and recommended
            texts.append(f"{arabic} | {english}")

    return texts


def generate_embeddings(texts: list, batch_size: int = 32) -> np.ndarray:
    """
    Generate embeddings using sentence-transformers.

    Returns: np.ndarray of shape (n_verses, 768)
    """
    from sentence_transformers import SentenceTransformer

    print(f"Loading model: {MODEL_NAME}")
    print("  (First run downloads ~1.1GB — one time only, cached after that)")

    model = SentenceTransformer(MODEL_NAME)

    print(f"Generating embeddings for {len(texts)} verses (batch_size={batch_size})...")
    print("  Estimated time: ~20-40 min on CPU, ~3-5 min on GPU.")

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,  # L2 normalize — cosine similarity = dot product
    )

    print(f"  Done. Embeddings shape: {embeddings.shape}")
    return embeddings


def save_embeddings(embeddings: np.ndarray, output_path: str, verse_ids: list):
    """
    Save embeddings as .npy and verse_ids as a companion .txt file.
    """
    os.makedirs(
        os.path.dirname(output_path) if os.path.dirname(output_path) else ".",
        exist_ok=True
    )

    np.save(output_path, embeddings)

    ids_path = output_path.replace(".npy", "_verse_ids.txt")
    with open(ids_path, "w", encoding="utf-8") as f:
        f.write("\n".join(verse_ids))

    print(f"Saved embeddings to : {output_path}")
    print(f"Saved verse IDs to  : {ids_path}")
    print(f"  Shape: {embeddings.shape}  |  Dtype: {embeddings.dtype}"
          f"  |  Size: {embeddings.nbytes / 1e6:.1f} MB")


def mark_verses_embedded(db_path: str, verse_ids: list):
    """Update the has_embedding flag in the database."""
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "UPDATE verses SET has_embedding = 1 WHERE verse_id = ?",
        [(vid,) for vid in verse_ids],
    )
    conn.commit()
    embedded_count = conn.execute(
        "SELECT COUNT(*) FROM verses WHERE has_embedding = 1"
    ).fetchone()[0]
    conn.close()
    print(f"  Marked {embedded_count} verses as embedded in DB.")


def register_embedding_run(db_path: str, model_name: str, dim: int,
                           count: int, npy_path: str):
    """Log this embedding run to embeddings_meta table."""
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO embeddings_meta
               (model_name, embedding_dim, total_verses, npy_path, notes)
           VALUES (?, ?, ?, ?, ?)""",
        (model_name, dim, count, npy_path,
         "combined arabic+english input — paraphrase-multilingual-mpnet-base-v2"),
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Generate verse embeddings")
    parser.add_argument("--db",
                        default="./db/quran.db",
                        help="SQLite database path")
    parser.add_argument("--output",
                        default="./embeddings/verse_embeddings.npy",
                        help="Output .npy path")
    parser.add_argument("--batch-size",
                        default=32, type=int,
                        help="Encoding batch size")
    parser.add_argument("--mode",
                        default="combined",
                        choices=["arabic", "english", "combined"],
                        help="Which text to embed (combined recommended)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Quran Atlas — Embedding Generator")
    print(f"  Model: {MODEL_NAME}")
    print("=" * 60)

    # Load verses
    print(f"\nLoading verses from {args.db}...")
    rows = load_verses_from_db(args.db)
    if not rows:
        print("  No verses found. Run db/seed.py first.")
        sys.exit(1)
    print(f"  Loaded {len(rows)} verses.")

    verse_ids  = [r[0] for r in rows]
    texts      = build_input_texts(rows, mode=args.mode)

    # Generate
    embeddings = generate_embeddings(texts, batch_size=args.batch_size)

    # Save
    save_embeddings(embeddings, args.output, verse_ids)

    # Update DB
    mark_verses_embedded(args.db, verse_ids)
    register_embedding_run(
        args.db,
        model_name=MODEL_NAME,
        dim=embeddings.shape[1],
        count=len(verse_ids),
        npy_path=args.output,
    )

    print("\n✓ Done! Restart the dashboard:")
    print("  python3 dashboard/server.py")


if __name__ == "__main__":
    main()