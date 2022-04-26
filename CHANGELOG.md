# Changelog

All notable changes to Quran Atlas. Follows Keep a Changelog format.

---

## [1.0.0] — Full dashboard release

### Added

- Narrative Thread tab with 40 preset topics across 7 categories
- Full scholarly commentary (3-paragraph thematic overview) for all 40 preset topics
- 7 topic categories: Theology and Faith, Human Character, Society and Law, Worship and Prophethood, Eschatology and Unseen, Nature and Creation, Conflict Test and Struggle
- Hybrid semantic scoring: 85 percent semantic similarity plus 15 percent keyword presence boost
- Adaptive threshold using mean plus k times standard deviation per query, replacing fixed 0.25 cutoff
- CUSTOM_QUERY_EXPANSIONS map with 100+ common Islamic and English terms for free-text search
- Auto-expansion of custom search queries using curated Islamic vocabulary synonyms
- Query expansion map (QUERY_EXPANSIONS) with rich multi-word expansions per preset topic
- TOPIC_KEYWORDS dictionary with 15 to 20 curated keywords per topic for keyword boost scoring
- Background model warmup thread at server startup
- Enter key and Search button both trigger search
- Preset topic buttons trigger search instantly without requiring Search click
- Top 10, Top 20, All Ayaat radio buttons update results instantly
- Statistical summary box showing Meccan and Medinan counts, most frequent Surah, revelation span
- Thematic overview shown for preset topics only, not custom searches
- Switched embedding model from bert-base-multilingual-cased to paraphrase-multilingual-mpnet-base-v2 for dramatically improved semantic similarity
- Regenerated all embeddings in English-only mode for better semantic separation
- Root Explorer: removed LIMIT 30 from distribution chart, all Surahs now shown including Al-Fatiha
- Root Explorer: dynamic chart height scales with number of Surahs per root
- Root Explorer: distribution chart sorted ascending so low-count Surahs appear at top
- Root Explorer: removed duplicate update_root_verses callback that was causing Dash conflict
- Root Explorer: click a bar to filter Ayaat by that Surah
- Word-boundary aware Arabic surface form matching replacing naive substring search
- scripts/extract_root_forms.py: extracts verified surface forms per root from Tanzil XML
- scripts/add_missing_roots.py: adds roots present in JSON but missing from COMMON_ROOTS
- scripts/fix_duplicates.py: removes duplicate root keys from COMMON_ROOTS
- scripts/fix_verse_roots.py: repairs denormalized columns in verse_roots table
- scripts/patch_quran_data.py: patches verified forms from JSON into quran_data.py
- 160 roots with curated surface form lists extracted from actual Tanzil XML
- Theme Map tab: scholarly research note explaining cluster quality and future directions
- Theme Map: note in legend clarifying cluster labels are approximate
- Removed from Theme Map: fixed height container that was clipping chart
- Theme Map moved to last tab position after Narrative Thread
- Staged commit messages for GitHub portfolio presentation

### Changed

- Embedding model changed from bert-base-multilingual-cased to paraphrase-multilingual-mpnet-base-v2
- Embedding input mode changed from combined Arabic and English to English-only for better semantic separation
- Root detection changed from substring matching to word-boundary surface form matching
- Hybrid score weights changed to 0.85 semantic plus 0.15 keyword from 0.65 plus 0.35
- Adaptive threshold k raised to 1.20 for preset topics and 1.00 for custom queries
- Dashboard tab order: Overview, Root Explorer, Ayah Search, Narrative Thread, Theme Map

### Fixed

- Al-Fatiha and other low-occurrence Surahs missing from Root Explorer distribution chart due to LIMIT 30
- Duplicate root entries in dropdown (كتب and كتاب both appearing) removed from COMMON_ROOTS
- verse_roots denormalized columns (surah_number, revelation_type, revelation_order) refreshed to match authoritative surahs table
- Embeddings cache loading stale mBERT embeddings after regeneration due to module-level cache not invalidating
- Wrong model (bert-base-multilingual-cased) being used to encode queries while embeddings were generated with paraphrase-multilingual-mpnet-base-v2, producing incompatible vector spaces
- Broken import at top of app.py (from layouts.narrative) replaced with correct dashboard.layouts.narrative path
- Gap between tab bar and Overview content caused by broken import creating silent layout failure

---

## [0.3.0] — Theme clustering and full dashboard

### Added

- embeddings/cluster_themes.py: UMAP 2D and 20D reduction and KMeans clustering pipeline
- embeddings/similarity_search.py: cosine similarity with module-level embedding cache
- Theme Map tab: UMAP scatter plot with per-theme coloring and click-to-read Ayah
- Ayah Search tab: Ayah lookup by reference and semantic similarity results
- Narrative Thread feature: chronological trace of a concept across revelation order
- dashboard/assets/style.css: full dark scholarly aesthetic with gold accents
- scripts/export_report.py: CSV export with UTF-8 BOM encoding for Arabic in Excel
- docs/REPORT.md: research methodology documentation
- docs/ARCHITECTURE.md: technical architecture notes
- tests/test_similarity.py: embedding mathematics and similarity search tests

### Changed

- Switched embedding input from Arabic-only to bilingual Arabic and English after Arabic-only clusters showed higher noise with mBERT

### Fixed

- UMAP scatter tooltip was showing verse index instead of verse_id
- Similarity search was including the query Ayah itself in its own results

---

## [0.2.0] — Embedding pipeline and Root Explorer

### Added

- embeddings/generate_embeddings.py: mBERT inference with batch encoding
- Root Word Explorer tab: distribution charts, Meccan and Medinan split donut, chronological timeline
- db/schema.sql: views for root distribution and theme by revelation period
- scripts/check_setup.py: pre-flight environment checker
- Makefile with pipeline shortcuts (seed, embed, cluster, run, pipeline, test, export)

### Changed

- Dropped AraBERT in favour of bert-base-multilingual-cased for pre-2021 packaging compatibility
- Root detection switched from character-class regex to direct substring matching

### Fixed

- merge_quran_data() was silently dropping Ayaat when English translation had mismatched Surah and Ayah numbering: replaced with explicit left join and logging

---

## [0.1.0] — Data pipeline and database

### Added

- data/quran_data.py: Tanzil XML parser, Sahih International loader, root word scanner
- db/schema.sql: full relational schema with tables surahs, verses, root_words, verse_roots, themes, verse_themes, embeddings_meta, plus indexes and views
- db/seed.py: database population from parsed data
- dashboard/app.py: Dash app scaffold with 5 tab routing
- dashboard/layouts/overview.py: stat cards, revelation donut chart, Surah bar chart
- tests/test_pipeline.py: data loading, merge, and database schema tests
- requirements.txt: all packages pinned to 2021 versions
- .env.example and .gitignore

### Notes

- First working end-to-end run: 6,236 Ayaat loaded, 30 root words, database seeded in approximately 3 minutes
- Overview tab renders correctly with placeholder themes

---

## Commit sequence for GitHub

```
git commit -m "init: project structure and requirements"
git commit -m "data: Tanzil XML parser and surah metadata"
git commit -m "db: relational schema with views and indexes"
git commit -m "db: seed script with root word detection"
git commit -m "dashboard: Dash app scaffold with tab routing"
git commit -m "dashboard: overview tab with stats and charts"
git commit -m "embeddings: mBERT inference pipeline"
git commit -m "embeddings: UMAP and KMeans theme clustering"
git commit -m "embeddings: cosine similarity search module"
git commit -m "dashboard: root explorer tab and callbacks"
git commit -m "dashboard: semantic theme map with UMAP scatter"
git commit -m "dashboard: ayah search and narrative thread"
git commit -m "dashboard: dark scholarly CSS aesthetic"
git commit -m "scripts: setup checker and CSV exporter"
git commit -m "tests: pipeline and similarity search tests"
git commit -m "fix: root word substring matching replaced with surface form matching"
git commit -m "fix: verse_roots denormalized columns repaired"
git commit -m "feat: narrative thread 40 preset topics with scholarly commentary"
git commit -m "feat: hybrid semantic scoring with adaptive threshold"
git commit -m "feat: switched to paraphrase-multilingual-mpnet-base-v2 embeddings"
git commit -m "feat: custom search auto-expansion and keyword boost"
git commit -m "fix: root explorer distribution chart limit removed"
git commit -m "fix: duplicate root dropdown entries removed"
git commit -m "fix: broken import causing layout gap"
git commit -m "docs: architecture notes and research report rewritten"
git commit -m "docs: readme combining project overview methodology and setup"
git commit -m "release: Quran Atlas v1.0.0"
```

---

**kayShahbaaz خ شهباز**