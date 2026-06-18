"""
dashboard/app.py

Main entry point for the Quran Analytics Dashboard.
Built with Plotly Dash.

Run:
    python dashboard/app.py

Then open http://127.0.0.1:8050 in your browser.
"""

import os
import sys
import sqlite3

from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from dotenv import load_dotenv
from dashboard.layouts.narrative import build_narrative_layout

# Project root on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ── Import app instance from server.py (avoids circular imports) ──────────────
from dashboard.server import app, server  # noqa

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH         = os.getenv("DB_PATH",         "./db/quran.db")
EMBEDDINGS_PATH = os.getenv("EMBEDDINGS_PATH", "./embeddings/verse_embeddings.npy")
UMAP_2D_PATH    = "./embeddings/umap_2d.npy"
DASH_HOST       = os.getenv("DASH_HOST",       "127.0.0.1")
DASH_PORT       = int(os.getenv("DASH_PORT",   "8050"))
DASH_DEBUG      = os.getenv("DASH_DEBUG",      "False").lower() == "true"


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def query_df(sql, params=()):
    with get_db() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ── Data loading (cached at startup) ─────────────────────────────────────────
def load_overview_stats():
    return query_df("SELECT * FROM v_verses_full")


def load_root_options():
    df = query_df("SELECT root_arabic, root_english, domain, total_occurrences FROM root_words WHERE total_occurrences >= 2 ORDER BY total_occurrences DESC")
    options = [
        {
            "label": f"{r['root_arabic']} — {r['root_english']} ({r['total_occurrences']} Ayaat)",
            "value": r["root_arabic"],
        }
        for _, r in df.iterrows()
    ]
    return options


def load_themes():
    return query_df("SELECT * FROM themes ORDER BY cluster_id")


def load_umap_data():
    npz_path = UMAP_2D_PATH.replace(".npy", "_with_ids.npz")
    if not os.path.exists(npz_path):
        return None

    data      = np.load(npz_path, allow_pickle=True)
    coords    = data["coords"]
    verse_ids = [str(v) for v in data["verse_ids"]]

    verse_df = query_df("""
        SELECT vf.verse_id, vf.surah_number, vf.name_english, vf.revelation_type,
               vf.arabic_text, vf.english_text, vt.cluster_id, t.label_english, t.color_hex
        FROM v_verses_full vf
        LEFT JOIN verse_themes vt ON vf.verse_id = vt.verse_id
        LEFT JOIN themes t ON vt.cluster_id = t.cluster_id
    """)

    verse_dict = {row["verse_id"]: dict(row) for _, row in verse_df.iterrows()}

    records = []
    for i, vid in enumerate(verse_ids):
        info = verse_dict.get(vid, {})
        records.append({
            "verse_id":   vid,
            "x":          float(coords[i, 0]),
            "y":          float(coords[i, 1]),
            "surah":      info.get("surah_number", 0),
            "surah_name": info.get("name_english", ""),
            "revelation": info.get("revelation_type", ""),
            "arabic":     info.get("arabic_text", ""),
            "english":    (info.get("english_text", "") or "")[:120] + "...",
            "theme":      info.get("label_english", "Unclustered"),
            "color":      info.get("color_hex", "#888888"),
        })

    return pd.DataFrame(records)


# ── Load data at startup ──────────────────────────────────────────────────────
print("Loading data...")
OVERVIEW_DF  = load_overview_stats()
ROOT_OPTIONS = load_root_options()
THEMES_DF    = load_themes()
UMAP_DF      = load_umap_data()
print(f"  Loaded {len(OVERVIEW_DF)} verses, {len(ROOT_OPTIONS)} roots, {len(THEMES_DF)} themes")


# ── Layout imports ────────────────────────────────────────────────────────────
from dashboard.layouts.overview import build_overview_layout
from dashboard.layouts.roots    import build_roots_layout
from dashboard.layouts.themes   import build_themes_layout
from dashboard.layouts.search   import build_search_layout

# ── Callback imports ──────────────────────────────────────────────────────────
import dashboard.callbacks.root_callbacks    # noqa
import dashboard.callbacks.theme_callbacks   # noqa
import dashboard.callbacks.search_callbacks  # noqa
import dashboard.callbacks.narrative_callbacks

# ── Main layout ───────────────────────────────────────────────────────────────
app.layout = html.Div([

    # Header
    html.Div([
    # Left — title
    html.Div([
        html.Img(
            src="/assets/LQ_logo.png",
            style={
                "height":      "45px",
                "width":       "auto",
                "marginRight": "1px",
                "verticalAlign": "middle",
             }
        ),
        html.H1("Qur'ān Atlas", className="header-title-en"),
        html.H1("أطلس القرآن", className="header-title-ar"),
    ], className="header-titles", style={"display": "flex", "alignItems": "center"}),

    # Center — Arabic phrase
    html.P(
        "ٱلْحَمْدُ لِلَّهِ رَبِّ ٱلْعَالَمِينَ وَٱلصَّلَاةُ وَٱلسَّلَامُ عَلَىٰ سَيِّدِ ٱلْأَنْبِيَاءِ وَٱلْمُرْسَلِينَ وَعَلَىٰ آلِهِ وَصَحْبِهِ أَجْمَعِينَ",
        style={
            "fontFamily": "'Amiri', serif",
            "fontSize": "14px",
            "color": "#c9a84c",
            "direction": "rtl",
            "lineHeight": "2",
            "textAlign": "center",
            "flex": "1",
            "margin": "0 40px",
        }
    ),

    # Right — subtitle
    html.P(
        "Quranic Semantic Themes across all 6236 Ayaat | المواضيع الدلالية عبر جميع الآيات",
        className="header-subtitle",
        style={
            "textAlign": "right",
            "margin": "0",
            "whiteSpace": "nowrap",
            "fontSize": "11px",
        }
    ),

], className="header", style={
    "display": "flex",
    "alignItems": "center",
    "justifyContent": "space-between",
}),

    # Navigation tabs
    dcc.Tabs(
        id="main-tabs",
        value="overview",
        className="main-tabs",
        children=[
            dcc.Tab(label="Overview  |  نظرة عامة",        value="overview",   className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Root Explorer  |  الجذور",       value="roots",      className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Ayah Search  |  البحث",          value="search",     className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Narrative Thread  |  السياق",    value="narrative",  className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Theme Map  |  خريطة المواضيع",   value="themes",     className="tab", selected_className="tab--selected"),
        ],
    ),

    # All tab contents pre-rendered and shown/hidden
    html.Div([
        html.Div(build_overview_layout(OVERVIEW_DF, THEMES_DF), id="tab-overview", style={"display": "block"}),
        html.Div(build_roots_layout(ROOT_OPTIONS),               id="tab-roots",    style={"display": "none"}),
        html.Div(build_themes_layout(UMAP_DF, THEMES_DF),        id="tab-themes",   style={"display": "none"}),
        html.Div(build_search_layout(),                          id="tab-search",   style={"display": "none"}),
        html.Div(build_narrative_layout(),                       id="narrative-content", style={"display": "none"}),
    ], id="tab-content", className="tab-content"),

    # Footer
    html.Div([
    html.P([
        "A LearnQuran Academy Project | ",
        html.A(
            "YouTube",
            href="https://www.youtube.com/@LearnQuran_iqra",
            target="_blank",
            style={
                "color": "#c9a84c",
                "textDecoration": "none",
            }
        ),
    ]),
    html.P("Quran text from Tanzil.net · Translation: Sahih International"),
    html.P([
        html.A(
            "Contact",
            href="mailto:learnquran.iqra@gmail.com",
            style={
                "color": "#c9a84c",
                "textDecoration": "none",
            }
        ),
    ]),
    html.P(
        "© 2019-2022 LearnQuran Academy. All Rights Reserved.",
        style={
            "marginTop": "10px",
            "fontSize": "11px",
            "color": "#6b6050",
        }
    ),
], className="footer"),

], className="app-container")


# ── Tab routing callback ──────────────────────────────────────────────────────
@app.callback(
    [Output("tab-overview",      "style"),
     Output("tab-roots",         "style"),
     Output("tab-themes",        "style"),
     Output("tab-search",        "style"),
     Output("narrative-content", "style")],
    [Input("main-tabs", "value")]
)

def render_tab(tab):
    hidden = {"display": "none"}
    shown  = {"display": "block"}
    return (
        shown if tab == "overview"  else hidden,
        shown if tab == "roots"     else hidden,
        shown if tab == "themes"    else hidden,
        shown if tab == "search"    else hidden,
        shown if tab == "narrative" else hidden,
    )


if __name__ == "__main__":
    print(f"\nStarting Quran Atlas Dashboard")
    print(f"  URL: http://{DASH_HOST}:{DASH_PORT}")
    print(f"  DB:  {DB_PATH}\n")

    app.run(
        host=DASH_HOST,
        port=DASH_PORT,
        debug=DASH_DEBUG,
    )