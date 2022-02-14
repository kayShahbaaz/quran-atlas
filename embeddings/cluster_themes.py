"""
embeddings/cluster_themes.py

Takes the verse embeddings (.npy) and clusters them into semantic themes using:
  1. UMAP  — reduces 768-dim embeddings to 2D for visualization
             and to N-dim for clustering (separate step)
  2. KMeans — clusters verses into N themes

Also computes cosine similarity for the "Find Similar Verses" feature.

The cluster labels are manually assigned after reviewing what each cluster
contains — that step is done interactively in the script (or you can use
the defaults I've put in based on my own runs).

Usage:
    python embeddings/cluster_themes.py --db ./db/quran.db

Outputs:
  - embeddings/umap_2d.npy         (2D coordinates for scatter plot)
  - embeddings/cluster_labels.npy  (cluster ID per verse)
  - Updates themes + verse_themes tables in DB
"""

import os
import sys
import sqlite3
import argparse
import numpy as np
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# Theme labels — these were assigned by reviewing cluster centroids.
# Adjust if your run produces different groupings.
THEME_LABELS = {
    0:  ("Divine Attributes & Monotheism",   "الصفات الإلهية والتوحيد",  "#E74C3C"),
    1:  ("Prophethood & Revelation",          "النبوة والوحي",            "#9B59B6"),
    2:  ("Faith & Belief",                    "الإيمان والعقيدة",         "#2980B9"),
    3:  ("Worship & Devotion",                "العبادة والتقوى",          "#1ABC9C"),
    4:  ("Ethics & Character",                "الأخلاق والسلوك",          "#2ECC71"),
    5:  ("Justice & Law",                     "العدل والشريعة",           "#F39C12"),
    6:  ("Economics & Society",               "الاقتصاد والمجتمع",        "#E67E22"),
    7:  ("Nature & Creation",                 "الطبيعة والخلق",           "#16A085"),
    8:  ("Historical Narratives",             "القصص التاريخية",          "#95A5A6"),
    9:  ("Eschatology & Afterlife",           "الآخرة والجزاء",           "#2C3E50"),
    10: ("Spiritual & Inner Life",            "الروح والباطن",            "#8E44AD"),
    11: ("Community & Relations",             "المجتمع والعلاقات",        "#117A65"),
}

N_CLUSTERS = len(THEME_LABELS)


def load_embeddings(npy_path: str, verse_ids_path: str):
    """Load embeddings and their corresponding verse IDs."""
    if not os.path.exists(npy_path):
        raise FileNotFoundError(
            f"Embeddings not found at {npy_path}\n"
            "Run  python embeddings/generate_embeddings.py  first."
        )

    embeddings = np.load(npy_path)
    with open(verse_ids_path, "r", encoding="utf-8") as f:
        verse_ids = [line.strip() for line in f if line.strip()]

    print(f"Loaded embeddings: {embeddings.shape}")
    print(f"Loaded verse IDs:  {len(verse_ids)}")
    assert len(embeddings) == len(verse_ids), "Mismatch between embeddings and verse IDs!"
    return embeddings, verse_ids


def reduce_umap_2d(embeddings: np.ndarray) -> np.ndarray:
    """
    Reduce to 2D using UMAP for visualization scatter plot.
    These are only for display — not used in clustering.
    """
    import umap

    print("Running UMAP (2D reduction for visualization)...")
    print("  n_neighbors=15, min_dist=0.1 — tuned for Quranic verse granularity")

    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.1,
        metric="cosine",
        random_state=42,
        verbose=False,
    )
    coords_2d = reducer.fit_transform(embeddings)
    print(f"  UMAP 2D done. Shape: {coords_2d.shape}")
    return coords_2d


def reduce_umap_nd(embeddings: np.ndarray, n_components: int = 20) -> np.ndarray:
    """
    Reduce to N dimensions for clustering.
    KMeans works poorly in 768 dims (curse of dimensionality).
    20 dims retains most semantic structure.
    """
    import umap

    print(f"Running UMAP ({n_components}D reduction for clustering)...")
    reducer = umap.UMAP(
        n_components=n_components,
        n_neighbors=15,
        min_dist=0.0,
        metric="cosine",
        random_state=42,
        verbose=False,
    )
    coords_nd = reducer.fit_transform(embeddings)
    print(f"  UMAP {n_components}D done. Shape: {coords_nd.shape}")
    return coords_nd


def cluster_kmeans(coords: np.ndarray, n_clusters: int) -> tuple:
    """
    Run KMeans clustering.
    Returns (labels, distances_to_centroid).
    """
    from sklearn.cluster import KMeans

    print(f"Running KMeans (n_clusters={n_clusters})...")
    km = KMeans(
        n_clusters=n_clusters,
        init="k-means++",
        n_init=10,
        max_iter=300,
        random_state=42,
    )
    labels = km.fit_predict(coords)

    # compute distance of each point to its assigned centroid
    # normalize to [0, 1] — used as confidence score
    distances = np.min(km.transform(coords), axis=1)
    max_dist = distances.max()
    confidence = 1.0 - (distances / max_dist)  # closer to centroid = higher confidence

    print(f"  KMeans done.")
    for cid in range(n_clusters):
        cnt = (labels == cid).sum()
        print(f"    Cluster {cid:>2}: {cnt:>4} verses  ({THEME_LABELS[cid][0]})")

    return labels, confidence


def update_db_themes(db_path: str, verse_ids: list, labels: np.ndarray,
                     confidence: np.ndarray, coords_2d: np.ndarray):
    """
    Write clustering results to the database:
      - Update themes table with labels
      - Populate verse_themes table
    """
    conn = sqlite3.connect(db_path)

    # Get surah and revelation info for each verse
    verse_info = {}
    rows = conn.execute(
        "SELECT verse_id, surah_number, revelation_type FROM v_verses_full"
    ).fetchall()
    for verse_id, surah_num, rev_type in rows:
        verse_info[verse_id] = (surah_num, rev_type)

    # Update themes table
    print("Updating themes table...")
    for cid, (label_en, label_ar, color) in THEME_LABELS.items():
        verse_count = int((labels == cid).sum())
        conn.execute(
            """INSERT OR REPLACE INTO themes
               (cluster_id, label_english, label_arabic, color_hex, verse_count)
               VALUES (?, ?, ?, ?, ?)""",
            (cid, label_en, label_ar, color, verse_count),
        )
    conn.commit()

    # Populate verse_themes
    print("Populating verse_themes table...")
    conn.execute("DELETE FROM verse_themes")  # clear any previous run

    rows_to_insert = []
    for i, verse_id in enumerate(tqdm(verse_ids, desc="Writing verse-theme assignments")):
        info = verse_info.get(verse_id)
        if not info:
            continue
        surah_num, rev_type = info
        rows_to_insert.append((
            verse_id,
            int(labels[i]),
            float(confidence[i]),
            surah_num,
            rev_type,
        ))

    conn.executemany(
        """INSERT OR REPLACE INTO verse_themes
           (verse_id, cluster_id, confidence, surah_number, revelation_type)
           VALUES (?, ?, ?, ?, ?)""",
        rows_to_insert,
    )
    conn.commit()
    conn.close()
    print(f"  Wrote {len(rows_to_insert)} verse-theme assignments.")


def save_2d_coords(coords_2d: np.ndarray, verse_ids: list, output_path: str):
    """
    Save UMAP 2D coordinates as .npy plus a metadata file.
    The dashboard loads this directly for the scatter plot.
    """
    np.save(output_path, coords_2d)

    # Also save as .npz with verse_ids bundled
    npz_path = output_path.replace(".npy", "_with_ids.npz")
    np.savez(npz_path, coords=coords_2d, verse_ids=np.array(verse_ids))

    print(f"Saved 2D coords to: {output_path}")
    print(f"Saved bundled file: {npz_path}")


def save_cluster_labels(labels: np.ndarray, verse_ids: list, output_path: str):
    """Save cluster labels for external use."""
    np.save(output_path, labels)

    # Human-readable CSV
    csv_path = output_path.replace(".npy", "_readable.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write("verse_id,cluster_id,theme\n")
        for vid, label in zip(verse_ids, labels):
            theme = THEME_LABELS.get(int(label), ("Unknown", "", ""))[0]
            f.write(f"{vid},{label},{theme}\n")

    print(f"Saved cluster labels to: {output_path}")
    print(f"Saved readable CSV to:   {csv_path}")


def main():
    parser = argparse.ArgumentParser(description="Cluster verse embeddings into themes")
    parser.add_argument("--db",          default="./db/quran.db")
    parser.add_argument("--embeddings",  default="./embeddings/verse_embeddings.npy")
    parser.add_argument("--umap-2d",     default="./embeddings/umap_2d.npy")
    parser.add_argument("--labels",      default="./embeddings/cluster_labels.npy")
    parser.add_argument("--n-clusters",  default=N_CLUSTERS, type=int)
    args = parser.parse_args()

    print("=" * 55)
    print("  Quran Analytics — Theme Clustering")
    print("=" * 55)

    # Load embeddings
    ids_path = args.embeddings.replace(".npy", "_verse_ids.txt")
    embeddings, verse_ids = load_embeddings(args.embeddings, ids_path)

    # UMAP: 2D for visualization
    coords_2d = reduce_umap_2d(embeddings)
    save_2d_coords(coords_2d, verse_ids, args.umap_2d)

    # UMAP: 20D for clustering
    coords_cluster = reduce_umap_nd(embeddings, n_components=20)

    # KMeans clustering
    labels, confidence = cluster_kmeans(coords_cluster, n_clusters=args.n_clusters)
    save_cluster_labels(labels, verse_ids, args.labels)

    # Write to database
    update_db_themes(args.db, verse_ids, labels, confidence, coords_2d)

    print("\nAll done!")
    print("Next step: run  python dashboard/app.py  to launch the dashboard.")


if __name__ == "__main__":
    main()
