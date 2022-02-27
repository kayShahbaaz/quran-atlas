"""
dashboard/callbacks/search_callbacks.py

Callbacks for the Ayah Search tab.
Handles:
  - Ayah lookup by reference (e.g. "2:255")
  - Semantic similarity results
  - Populating narrative dropdown (kept for compatibility)
"""

import sys
import os

from dash import html, dcc
from dash.dependencies import Input, Output
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.app import app, DB_PATH, EMBEDDINGS_PATH, ROOT_OPTIONS, query_df


# ── Ayah lookup ───────────────────────────────────────────────────────────────
@app.callback(
    Output("verse-lookup-result", "children"),
    [Input("verse-lookup-input", "value")],
)
def lookup_verse(verse_ref):
    if not verse_ref or ":" not in verse_ref:
        return html.P(
            "Enter a reference like  2:255  or  36:40",
            style={"color": "#6b6050", "fontSize": "13px", "fontStyle": "italic"},
        )

    verse_ref = verse_ref.strip()

    row = query_df(
        """SELECT vf.verse_id, vf.arabic_text, vf.english_text,
                  vf.name_english, vf.name_arabic, vf.revelation_type,
                  vf.surah_number, vf.verse_number, vf.revelation_order,
                  t.label_english, t.color_hex
           FROM v_verses_full vf
           LEFT JOIN verse_themes vt ON vf.verse_id = vt.verse_id
           LEFT JOIN themes t ON vt.cluster_id = t.cluster_id
           WHERE vf.verse_id = ?""",
        (verse_ref,)
    )

    if row.empty:
        return html.P(
            f'Ayah "{verse_ref}" not found. Check the format (e.g. 2:255).',
            style={"color": "#e8943a", "fontSize": "13px"},
        )

    r = row.iloc[0]
    return _verse_card_full(r)


# ── Semantic similarity ───────────────────────────────────────────────────────
@app.callback(
    Output("similar-verses-list", "children"),
    [Input("verse-lookup-input", "value")],
)
def update_similar_verses(verse_ref):
    if not verse_ref or ":" not in verse_ref:
        return html.P("Load an Ayah above to find similar ones.",
                      className="loading-text")

    verse_ref = verse_ref.strip()

    npy_path = EMBEDDINGS_PATH
    ids_path = npy_path.replace(".npy", "_verse_ids.txt")

    if not os.path.exists(npy_path) or not os.path.exists(ids_path):
        return html.Div([
            html.P(
                "Semantic similarity requires embeddings.",
                style={"color": "#a89a7a", "fontSize": "13px"},
            ),
            html.P(
                "Run:  python3 embeddings/generate_embeddings.py",
                style={"fontFamily": "'Source Code Pro', monospace",
                       "fontSize": "12px", "color": "#c9a84c",
                       "background": "#1a1814", "padding": "8px 12px",
                       "borderRadius": "4px", "marginTop": "8px"},
            ),
        ])

    try:
        from embeddings.similarity_search import find_similar_verses
        results = find_similar_verses(
            query_verse_id=verse_ref,
            db_path=DB_PATH,
            npy_path=npy_path,
            top_k=6,
        )
    except Exception as e:
        return html.P(f"Similarity search error: {e}",
                      style={"color": "#e8943a", "fontSize": "13px"})

    if not results:
        return html.P(
            "No similar Ayaat found (Ayah may not be embedded yet).",
            className="loading-text"
        )

    cards = []
    for r in results:
        sim = r["similarity"]
        rev_class = "badge-meccan" if r["revelation_type"] == "Meccan" else "badge-medinan"
        cards.append(html.Div([
            html.Div([
                html.Span(r["verse_id"], className="verse-id"),
                html.Span(r["revelation_type"], className=f"badge {rev_class}"),
                html.Span(r["surah_name_en"],
                          style={"fontSize": "11px", "color": "#6b6050",
                                 "marginLeft": "8px"}),
            ]),
            html.Div(r["arabic_text"],  className="verse-arabic"),
            html.Div(
                r["english_text"] or "",
                className="verse-english",
                style={
                    "fontSize":   "14px",
                    "color":      "#a89a7a",
                    "fontStyle":  "italic",
                    "lineHeight": "1.8",
                    "marginTop":  "8px",
                    "paddingTop": "8px",
                    "borderTop":  "1px solid #2e2a22",
                    "display":    "block",
                }
            ),
            # Similarity bar
            html.Div([
                html.Div([
                    html.Div(style={
                        "height": "3px",
                        "width":  f"{sim * 100:.0f}%",
                        "background": "#c9a84c",
                        "borderRadius": "2px",
                        "flex": "1",
                    }),
                ], style={"flex": "1", "background": "#2e2a22",
                          "borderRadius": "2px", "height": "3px"}),
                html.Span(f"{sim:.2f}", className="similarity-label"),
            ], className="similarity-bar"),
        ], className="verse-card"))

    return html.Div(cards)


# ── Helper: full verse card ───────────────────────────────────────────────────
def _verse_card_full(r):
    rev_class   = "badge-meccan" if r["revelation_type"] == "Meccan" else "badge-medinan"
    theme_color = (r["color_hex"]
                   if pd.notna(r.get("color_hex")) and r["color_hex"]
                   else "#4a7c59")

    return html.Div([
       html.Div([
            html.Span(r["verse_id"], className="verse-id"),
            html.Span(r["revelation_type"], className=f"badge {rev_class}"),
            html.Span(r["name_english"],
                style={"fontSize": "11px", "color": "#6b6050",
                        "marginLeft": "8px"}),
        html.Span(r["name_arabic"],
              style={"fontFamily": "'Amiri', serif", "fontSize": "13px",
                     "color": "#6b6050", "marginLeft": "8px"}),
        html.Span(
            "(1:1 is the Basmalah per Tanzil standard numbering — Alhamdulillah is 1:2)",
            style={"fontSize": "10px", "color": "#6b6050",
                "fontStyle": "italic", "display": "block",
                "marginTop": "4px"}
            ) if r["verse_id"] == "1:1" else html.Span(),
        ]),

        html.Div(r["arabic_text"],  className="verse-arabic"),
        html.Div(
            r["english_text"] or "",
            className="verse-english",
            style={
                "fontSize":   "14px",
                "color":      "#a89a7a",
                "fontStyle":  "italic",
                "lineHeight": "1.8",
                "marginTop":  "8px",
                "paddingTop": "8px",
                "borderTop":  "1px solid #2e2a22",
                "display":    "block",
            }
        ),
        html.Div([
            html.Span(
                r["label_english"] or "Unclustered",
                className="badge badge-theme",
                style={"borderColor": theme_color, "color": theme_color},
            ),
            html.Span(
                f"Surah {int(r['surah_number'])}, Ayah {int(r['verse_number'])}",
                style={"fontSize": "11px", "color": "#6b6050", "marginLeft": "10px"},
            ),
        ], style={"marginTop": "10px"}),
    ], className="verse-card",
       style={"margin": "0", "borderLeftColor": theme_color})