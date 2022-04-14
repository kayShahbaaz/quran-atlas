# ============================================================
# Quran Analytics — Makefile
# Shortcuts for common pipeline commands
#
# Usage:
#   make check      → verify setup
#   make seed       → build database
#   make embed      → generate embeddings
#   make cluster    → cluster themes
#   make run        → launch dashboard
#   make pipeline   → run everything (seed → embed → cluster → run)
#   make test       → run tests
#   make export     → export CSVs
#   make clean      → remove generated files
# ============================================================

PYTHON = python
DB     = ./db/quran.db
XML    = ./data/quran-simple.xml
EMB    = ./embeddings/verse_embeddings.npy

.PHONY: check seed embed cluster run pipeline test export clean help

help:
	@echo ""
	@echo "  Quran Analytics — Available Commands"
	@echo "  ────────────────────────────────────"
	@echo "  make check     Verify environment and dependencies"
	@echo "  make seed      Parse XML + build SQLite database"
	@echo "  make embed     Generate mBERT verse embeddings (~20-30 min CPU)"
	@echo "  make cluster   Run UMAP + KMeans theme clustering"
	@echo "  make run       Launch the Dash dashboard"
	@echo "  make pipeline  Run full pipeline end-to-end"
	@echo "  make test      Run pytest test suite"
	@echo "  make export    Export analytics CSVs to ./exports/"
	@echo "  make clean     Remove generated DB, embeddings, exports"
	@echo ""

check:
	$(PYTHON) scripts/check_setup.py

seed:
	$(PYTHON) db/seed.py --xml $(XML) --db $(DB)

embed:
	$(PYTHON) embeddings/generate_embeddings.py --db $(DB) --output $(EMB)

cluster:
	$(PYTHON) embeddings/cluster_themes.py --db $(DB) --embeddings $(EMB)

run:
	$(PYTHON) dashboard/app.py

pipeline: seed embed cluster run

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

export:
	$(PYTHON) scripts/export_report.py --db $(DB) --out ./exports

clean:
	@echo "Removing generated files..."
	rm -f  $(DB)
	rm -f  ./embeddings/*.npy
	rm -f  ./embeddings/*.txt
	rm -f  ./embeddings/*.npz
	rm -f  ./embeddings/*.csv
	rm -rf ./exports/
	rm -rf __pycache__ */__pycache__ */*/__pycache__
	rm -rf .pytest_cache
	@echo "Done."
