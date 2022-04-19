# Technical Architecture: Quran Atlas

## System Overview

```
DATA PIPELINE
─────────────────────────────────────────────────────────
Tanzil XML ──► quran_data.py ──► seed.py ──► quran.db
                    │
             Sahih International (auto-downloaded)


NLP PIPELINE
─────────────────────────────────────────────────────────
quran.db ──► generate_embeddings.py ──► verse_embeddings.npy
                        │
                        ▼
              cluster_themes.py
              (UMAP 2D + UMAP 20D + KMeans)
                   │              │
                   ▼              ▼
            umap_2d.npy    quran.db (themes + verse_themes)


DASHBOARD
─────────────────────────────────────────────────────────
app.py ──► layouts/       HTML structure per tab
       ──► callbacks/     Plotly figures and Ayah cards
       ──► quran.db       SQL queries via pandas
       ──► umap_2d.npy    scatter plot coordinates
       ──► verse_embeddings.npy    similarity search
```

---

## Database Design

### Why SQLite

For 6,236 Ayaat, SQLite is more than sufficient. The largest table (verse_roots) has approximately 20,000 rows. All queries at runtime are read-only. SQLite makes the project self-contained with no server setup, no credentials, and no external services. WAL mode is enabled for concurrent reads during development.

If the project is ever scaled to serve multiple simultaneous users or extended with tafsir corpora, the schema is PostgreSQL-compatible with minimal changes: remove AUTOINCREMENT, use SERIAL, remove PRAGMA statements.

### Schema Design

The schema is normalized to third normal form with strategic denormalization for performance:

revelation_type and revelation_order are stored in both the surahs table and denormalized into verse_roots and verse_themes. This is intentional. Dashboard queries that filter by revelation period do not need to join to surahs, which reduces query complexity and improves response time for the most common filter operations.

Three pre-joined views handle the most common query patterns:

- v_verses_full: joins verses and surahs, used by all Ayah display callbacks
- v_root_distribution: aggregates verse_roots by Surah for the Root Explorer charts
- v_theme_by_revelation: aggregates verse_themes grouped by revelation period for the Overview

All WHERE clause columns are indexed: surah_number, revelation_type, revelation_order, root_arabic, cluster_id.

### Denormalized Column Integrity

The denormalized columns in verse_roots (surah_number, revelation_type, revelation_order) must match the authoritative values in the surahs table. The scripts/fix_verse_roots.py script provides an UPDATE statement that refreshes all denormalized columns by joining back to the authoritative sources, and should be run if the database is ever rebuilt with schema changes.

---

## Embedding Pipeline

### Model

paraphrase-multilingual-mpnet-base-v2 produces 768-dimensional dense vectors. The model was trained specifically for semantic similarity on over 50 million sentence pairs, making it substantially more appropriate for thematic search than general-purpose masked language models.

Embeddings are L2-normalized at generation time:
- Cosine similarity equals dot product, faster to compute
- All vectors have unit length
- np.dot(embeddings, query_vec) returns similarity scores in the range [-1, 1]
- No FAISS or approximate nearest neighbor library is needed for 6,236 vectors

Input mode is English-only (the English translation of each Ayah). This was found to produce better semantic separation than combined Arabic-English input, because the model has stronger English semantic representations and the translation provides unambiguous thematic grounding.

### UMAP Parameters

Two separate UMAP reductions are run on the same embedding matrix.

For visualization:

```python
umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1, metric="cosine")
```

min_dist=0.1 allows spread within clusters so individual points are visible and distinguishable on the scatter plot. Tighter values collapse clusters into dots that obscure internal structure.

For clustering:

```python
umap.UMAP(n_components=20, n_neighbors=15, min_dist=0.0, metric="cosine")
```

min_dist=0.0 packs points tightly within their natural clusters, which produces more coherent KMeans assignments. 20 dimensions retains the majority of the semantic structure present in the 768-dimensional space while avoiding the curse of dimensionality that degrades KMeans performance at high dimensionality. This 20-dimensional representation is internal to the clustering pipeline and is not stored or exposed to the dashboard.

### KMeans: Choosing K=12

K=12 was selected by running KMeans for K from 8 to 16 and examining both the inertia elbow curve and the semantic coherence of the clusters at each value of K. K=12 produced groupings that corresponded naturally to the standard academic divisions of Quranic content recognized in the uloom al-Quran tradition: tawhid, prophethood, worship, ethics, law, economics, nature, history, eschatology, spiritual life, community, and faith.

The cluster labels in THEME_LABELS were assigned by reviewing the 20 highest-confidence Ayaat in each cluster and identifying the dominant thematic content. Labels are subjective and should be treated as organizational heuristics.

---

## Dashboard Architecture

### Tab Structure

All five tab layouts are pre-rendered at startup and shown or hidden via CSS display property controlled by the render_tab callback. This avoids re-rendering layout functions on every tab switch, which would be expensive for the UMAP scatter plot.

```
main-tabs Input: value
    └─► render_tab callback
            ├─ tab-overview     build_overview_layout()
            ├─ tab-roots        build_roots_layout()
            ├─ tab-themes       build_themes_layout()
            ├─ tab-search       build_search_layout()
            └─ narrative-content build_narrative_layout()
```

### Data Loading Strategy

Three categories of data are handled differently based on their size, query frequency, and whether they change during a session.

Static at startup: OVERVIEW_DF, ROOT_OPTIONS, THEMES_DF. Loaded once when app.py initializes. These do not change during a session. OVERVIEW_DF is approximately 5MB in memory.

Query on demand: verse lookups, root distributions, Ayah search results. These hit SQLite via query_df() on each callback invocation. SQLite with WAL mode handles concurrent reads without blocking. Typical query time is 5 to 50 milliseconds.

Memory cached: embeddings and UMAP coordinates. Loaded once on first use and held in module-level variables. The embeddings array is approximately 19MB (6236 x 768 float32). The _embeddings_cache global is checked on every call to load_embeddings(), which also verifies the file modification time to detect if embeddings have been regenerated.

### Callback Organization

Each tab's callbacks are in a separate file in dashboard/callbacks/:

- root_callbacks.py: four callbacks for the Root Explorer (stats row, bar chart, donut chart, timeline, Ayah list)
- theme_callbacks.py: scatter plot filter and Ayah detail click handler
- search_callbacks.py: Ayah lookup and similarity search
- narrative_callbacks.py: topic search with hybrid scoring, preset topic buttons, result count radio

All callbacks use suppress_callback_exceptions=True to allow callbacks to reference components that may not be present in the initial layout.

---

## Root Word Detection

### Original Approach (Removed)

The initial implementation used raw Python substring matching:

```python
if root in arabic_text:
    record_occurrence()
```

This produced significant false positives. In Arabic, the three consonants of a root may appear as a coincidental sequence within words that belong to entirely different roots. For example, the root rahm (r-h-m) as a substring would match words containing those three letters in sequence even when they are not etymologically related.

### Current Approach

Root detection now uses word-boundary aware surface form matching. Each root has a curated list of actual word forms present in the Tanzil Simple Clean text, extracted by the scripts/extract_root_forms.py script. This script scans all 6,236 Ayaat and collects every token for which the root's consonants appear as an ordered subsequence (not a contiguous substring), after stripping common attached clitics (wa, fa, bi, li, al, and their combinations).

At detection time, the Arabic text of each Ayah is tokenized by splitting on whitespace. Each token is checked against the root's form set using a set intersection operation. A single database row is written per root-Ayah match, with the verse_id and root_arabic as the unique key.

This approach achieves high precision. It may miss rare conjugations or unusual morphological patterns not represented in the extracted form lists, but eliminates the false positives that made the original substring approach unusable.

---

## Similarity Search

At 6,236 Ayaat with 768 dimensions, the embedding matrix contains approximately 19 million float32 values (19MB in memory). A brute-force matrix-vector dot product:

```python
scores = np.dot(embeddings, query_vector)
```

runs in approximately 2 to 5 milliseconds on a modern CPU. This is fast enough for interactive use without requiring FAISS, ScaNN, or any approximate nearest neighbor library. The module-level cache ensures the matrix is loaded from disk only once per server session.

For the Narrative Thread, the query vector is the embedding of the expanded query text. For the Ayah Search similarity feature, the query vector is the pre-computed embedding of the reference Ayah looked up by verse_id.

---

## Performance Reference

| Operation | Typical Duration | Notes |
|---|---|---|
| Database seed | 2 to 5 minutes | Includes translation download on first run |
| Embedding generation | 20 to 40 minutes on CPU | 3 to 5 minutes with GPU |
| UMAP 2D reduction | 3 to 8 minutes | Single-threaded |
| UMAP 20D + KMeans | 5 to 15 minutes | |
| Dashboard startup | Under 3 seconds | Static data loaded at initialization |
| Tab switch | Under 500 milliseconds | Layouts pre-rendered, CSS show/hide |
| Root Explorer callback | 50 to 200 milliseconds | SQLite query plus Plotly figure render |
| Narrative Thread search | 200 to 800 milliseconds | Embedding encode plus matrix dot product |
| Ayah similarity search | 10 to 30 milliseconds | Matrix dot product only, no encode |

---

## Extending the Project

**Adding root words.** Edit COMMON_ROOTS in data/quran_data.py, run scripts/extract_root_forms.py to extract verified surface forms, then re-run db/seed.py. The dashboard picks up new roots automatically via the root_words table.

**Adding tafsir commentary.** Add a tafsir_notes table to schema.sql with verse_id as a foreign key. Populate it from any structured tafsir source. Display notes in the verse cards in search_callbacks.py and narrative_callbacks.py.

**Replacing morphological analysis.** Replace get_root_word_occurrences() in data/quran_data.py with a call to CAMeL Tools or Farasa. The rest of the pipeline (database schema, callbacks, charts) does not need to change.

**Public deployment.** The Dash app exposes a standard WSGI server object. Deploy with gunicorn:

```bash
gunicorn "dashboard.app:server" -b 0.0.0.0:8050 -w 1
```

Single worker is recommended because the embedding cache and Dash callback state are process-local. For multi-worker deployment, move the embedding cache to a shared memory solution or load embeddings at worker startup.

The project includes ready-to-use deployment configuration for Render (render.yaml, Procfile) and Hugging Face Spaces (Dockerfile, app_hf.py). See deployment_guide.md in the project root for full step-by-step instructions for both platforms.

---

A LearnQuran Academy Project. 2019-2022 LearnQuran Academy. All Rights Reserved.

---

**kayShahbaaz خ شهباز**