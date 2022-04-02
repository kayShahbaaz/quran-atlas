"""
scripts/check_setup.py

Verifies your environment before running the full pipeline.
Run this first — it'll tell you exactly what's missing.

Usage:
    python scripts/check_setup.py

Checks:
  - Python version (needs 3.8+)
  - All required packages installed
  - Tanzil XML file present
  - Database exists and has expected tables/rows
  - Embeddings file present
"""

import sys
import os

# ── Colors for terminal output ────────────────────────────────────────────────
try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    OK   = Fore.GREEN  + "  ✓  " + Style.RESET_ALL
    WARN = Fore.YELLOW + "  ⚠  " + Style.RESET_ALL
    FAIL = Fore.RED    + "  ✗  " + Style.RESET_ALL
except ImportError:
    OK   = "  OK   "
    WARN = "  WARN "
    FAIL = "  FAIL "


def section(title):
    print(f"\n── {title} {'─' * (50 - len(title))}")


def check(condition, ok_msg, fail_msg, warning=False):
    if condition:
        print(f"{OK}{ok_msg}")
        return True
    else:
        sym = WARN if warning else FAIL
        print(f"{sym}{fail_msg}")
        return False


def main():
    print("=" * 58)
    print("  Quran Analytics — Setup Checker")
    print("=" * 58)

    all_ok = True

    # ── Python version
    section("Python")
    v = sys.version_info
    ok = check(
        v >= (3, 8),
        f"Python {v.major}.{v.minor}.{v.micro}",
        f"Python 3.8+ required (you have {v.major}.{v.minor}.{v.micro})"
    )
    all_ok = all_ok and ok

    # ── Packages
    section("Required Packages")
    packages = {
        "pandas":               "1.1.3",
        "numpy":                "1.19.2",
        "lxml":                 "4.5.2",
        "sklearn":              "0.23.2",
        "sentence_transformers":"0.3.9",
        "umap":                 "0.4.6",
        "dash":                 "1.16.3",
        "plotly":               "4.12.0",
        "tqdm":                 "4.51.0",
        "dotenv":               "0.15.0",
        "requests":             "2.25.0",
    }

    # map import name -> display name
    import_names = {
        "sklearn":  "scikit-learn",
        "dotenv":   "python-dotenv",
        "umap":     "umap-learn",
    }

    for pkg, min_ver in packages.items():
        try:
            if pkg == "sklearn":
                import sklearn
                ver = sklearn.__version__
            elif pkg == "dotenv":
                import dotenv
                ver = dotenv.__version__
            elif pkg == "umap":
                import umap
                ver = getattr(umap, "__version__", "installed")
            elif pkg == "sentence_transformers":
                import sentence_transformers
                ver = sentence_transformers.__version__
            else:
                mod = __import__(pkg)
                ver = getattr(mod, "__version__", "installed")

            display = import_names.get(pkg, pkg)
            check(True, f"{display:<28} {ver}", "")
        except ImportError:
            display = import_names.get(pkg, pkg)
            check(False, "", f"{display} not installed  →  pip install {display}=={min_ver}")
            all_ok = False

    # ── Data files
    section("Data Files")

    xml_paths = [
        os.getenv("TANZIL_XML_PATH", ""),
        "./data/quran-simple.xml",
        "./data/quran-uthmani.xml",
        "./data/quran.xml",
    ]
    xml_found = any(os.path.exists(p) for p in xml_paths if p)
    check(
        xml_found,
        "Tanzil XML file found",
        "Tanzil XML not found  →  Download from https://tanzil.net/download/\n"
        "           Save as ./data/quran-simple.xml",
    )
    if not xml_found:
        all_ok = False

    # ── Database
    section("Database")
    db_path = os.getenv("DB_PATH", "./db/quran.db")
    db_exists = os.path.exists(db_path)
    check(db_exists, f"Database found: {db_path}",
          f"Database not found  →  Run: python db/seed.py", warning=True)

    if db_exists:
        import sqlite3
        try:
            conn = sqlite3.connect(db_path)
            verse_count = conn.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
            root_count  = conn.execute("SELECT COUNT(*) FROM root_words").fetchone()[0]
            theme_count = conn.execute("SELECT COUNT(*) FROM themes").fetchone()[0]
            embedded    = conn.execute("SELECT COUNT(*) FROM verses WHERE has_embedding=1").fetchone()[0]
            conn.close()

            check(verse_count >= 6000, f"{verse_count} verses in DB",
                  f"Only {verse_count} verses — re-run db/seed.py", warning=verse_count > 0)
            check(root_count  > 0,     f"{root_count} root words",
                  "No root words — re-run db/seed.py")
            check(theme_count > 0,     f"{theme_count} themes defined",
                  "No themes — run embeddings/cluster_themes.py", warning=True)
            check(embedded > 0, f"{embedded} verses with embeddings",
                  "No embeddings yet  →  Run: python embeddings/generate_embeddings.py",
                  warning=True)
        except Exception as e:
            check(False, "", f"DB error: {e}")

    # ── Embeddings
    section("Embeddings")
    emb_path = os.getenv("EMBEDDINGS_PATH", "./embeddings/verse_embeddings.npy")
    emb_exists = os.path.exists(emb_path)
    check(emb_exists, f"Embeddings found: {emb_path}",
          "Embeddings not generated yet  →  Run: python embeddings/generate_embeddings.py",
          warning=True)

    if emb_exists:
        import numpy as np
        emb = np.load(emb_path)
        check(emb.shape[0] >= 6000, f"Shape: {emb.shape}",
              f"Unexpected shape: {emb.shape}", warning=True)

    umap_path = "./embeddings/umap_2d.npy"
    check(os.path.exists(umap_path), "UMAP 2D coords found",
          "UMAP not generated  →  Run: python embeddings/cluster_themes.py",
          warning=True)

    # ── Summary
    print("\n" + "=" * 58)
    if all_ok:
        print(f"{OK}Everything looks good! You can run the full pipeline.")
        print("\n  Next steps:")
        print("    1.  python db/seed.py")
        print("    2.  python embeddings/generate_embeddings.py")
        print("    3.  python embeddings/cluster_themes.py")
        print("    4.  python dashboard/app.py")
    else:
        print(f"{FAIL}Some issues found — fix them before running the pipeline.")
        print("  Warnings (⚠) are non-blocking; errors (✗) must be fixed first.")
    print("=" * 58 + "\n")


if __name__ == "__main__":
    main()
