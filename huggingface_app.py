"""
app_hf.py — Entry point for Hugging Face Spaces deployment.

Hugging Face Spaces expects the app to run on port 7860.
This file wraps the existing dashboard for Spaces deployment.

On Spaces, place this file as app.py in the root of the Space repo.
"""

import os
import sys

# Point to project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set paths relative to repo root
os.environ.setdefault("DB_PATH",         "./db/quran.db")
os.environ.setdefault("EMBEDDINGS_PATH", "./embeddings/verse_embeddings.npy")
os.environ.setdefault("DASH_HOST",       "0.0.0.0")
os.environ.setdefault("DASH_PORT",       "7860")
os.environ.setdefault("DASH_DEBUG",      "False")

# Import the app — this runs all layout and callback registration
from dashboard.server import app, server  # noqa
import dashboard.app  # noqa — registers layout and callbacks

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=7860,
        debug=False,
    )
