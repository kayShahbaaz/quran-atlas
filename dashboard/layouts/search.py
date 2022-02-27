"""
dashboard/layouts/search.py

Verse Search tab — two search modes:
  1. Verse lookup by reference (e.g. "2:255")
  2. Semantic similarity search (find verses similar to selected one)

Also includes the "Narrative Thread" feature:
  - Enter a concept → see how it appears chronologically
    across Meccan and Medinan verses
"""

from dash import html
from dash import dcc


def build_search_layout():
    return html.Div([
        # ── Header
        html.Div([
            html.H2("Ayah Search & Exploration", className="section-title"),
            html.P(
                "Look up any Ayah by reference, find semantically similar Ayaat, "
                "or trace a concept chronologically across the full Quran.",
                className="section-subtitle"
            ),
        ]),

        # ── Two search panels
        html.Div([

            # Left: verse lookup
            html.Div([
                html.Div([
                    html.Div("Ayah Lookup  |  البحث عن الآية", className="card-title"),
                    html.Label("Enter reference (e.g. 2:255, 36:1)", className="control-label"),
                    html.Div([
                        dcc.Input(
                            id="verse-lookup-input",
                            type="text",
                            placeholder="Surah:Ayah  —  e.g. 2:255",
                            debounce=False,
                            n_submit=0,
                            style={"flex": "1"},
                        ),
                        html.Button(
                            "Search",
                            id="verse-lookup-btn",
                            n_clicks=0,
                            style={
                                "padding": "8px 20px",
                                "background": "#c9a84c",
                                "border": "none",
                                "borderRadius": "4px",
                                "color": "#1a1814",
                                "cursor": "pointer",
                                "fontWeight": "700",
                                "fontSize": "13px",
                            }
                        ),
                    ], style={"display": "flex", "gap": "10px"}),

                    html.Div(id="verse-lookup-result",
                             style={"marginTop": "16px"}),
                ], className="card"),

                # Similar verses panel (shown after a verse is loaded)
                html.Div([
                    html.Div("Semantically Similar Ayaat", className="card-title"),
                    html.P(
                        "Based on mBERT semantic embeddings — not keyword matching.",
                        style={"fontSize": "12px", "color": "#6b6050",
                               "fontStyle": "italic", "marginBottom": "14px"},
                    ),
                    html.Div(id="similar-verses-list",
                             children=html.P("Load an Ayah above to find similar ones.",
                                             className="loading-text")),
                ], className="card"),
            ]),

        ]),
    ])