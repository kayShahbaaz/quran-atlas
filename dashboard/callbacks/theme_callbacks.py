"""
dashboard/callbacks/theme_callbacks.py
"""

import sys
import os

from dash import html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.server import app
from dashboard.app import DB_PATH, query_df, UMAP_DF, THEMES_DF

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Libre Baskerville, serif", color="#a89a7a", size=12),
)


@app.callback(
    Output("umap-scatter", "figure"),
    [
        Input("theme-revelation-filter", "value"),
        Input("theme-cluster-filter",    "value"),
    ],
)
def update_umap_scatter(revelation_filter, cluster_filter):
    if UMAP_DF is None or UMAP_DF.empty:
        return _placeholder_fig()

    df = UMAP_DF.copy()

    if revelation_filter and revelation_filter != "all":
        df = df[df["revelation"] == revelation_filter]

    if cluster_filter and cluster_filter != "all":
        if not THEMES_DF.empty:
            match = THEMES_DF[THEMES_DF["cluster_id"] == int(cluster_filter)]
            if not match.empty:
                label = match.iloc[0]["label_english"]
                df = df[df["theme"] == label]

    if df.empty:
        return _placeholder_fig("No verses match the selected filters.")

    fig = go.Figure()
    color_map = {}
    if not THEMES_DF.empty:
        for _, row in THEMES_DF.iterrows():
            color_map[row["label_english"]] = row["color_hex"]

    for theme in df["theme"].unique():
        sub     = df[df["theme"] == theme]
        color   = color_map.get(theme, "#888888")
        opacity = 0.70 if cluster_filter == "all" else 0.75

        fig.add_trace(go.Scattergl(
            x=sub["x"],
            y=sub["y"],
            mode="markers",
            name=theme,
            marker=dict(
                color=color,
                size=4 if cluster_filter == "all" else 6,
                opacity=opacity,
                line=dict(width=0),
            ),
            customdata=sub[["verse_id", "surah_name", "revelation", "english"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b> · %{customdata[1]}<br>"
                "<i>%{customdata[2]}</i><br>"
                "%{customdata[3]}<extra></extra>"
            ),
            text=sub["verse_id"],
        ))

    fig.update_layout(
        **CHART_LAYOUT,
        showlegend=True,
        legend=dict(
            bgcolor="rgba(26,24,20,0.9)", bordercolor="#2e2a22", borderwidth=1,
            font=dict(size=10, color="#a89a7a"), itemsizing="constant",
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=0, r=10, t=10, b=0),
        hovermode="closest",
        dragmode="pan",
    )
    return fig


@app.callback(
    Output("theme-verse-detail", "children"),
    [Input("umap-scatter", "clickData")],
)
def show_clicked_verse(click_data):
    if not click_data:
        return html.P("Click any point on the map to view the Ayah here.",
                      className="loading-text")

    points = click_data.get("points", [])
    if not points:
        return html.P("Could not read click data.", className="loading-text")

    verse_id = points[0].get("text", "")
    if not verse_id:
        return html.P("No verse ID found.", className="loading-text")

    row = query_df(
        """SELECT vf.verse_id, vf.arabic_text, vf.english_text,
                  vf.name_english, vf.name_arabic, vf.revelation_type,
                  vf.surah_number, vf.verse_number, t.label_english, t.color_hex
           FROM v_verses_full vf
           LEFT JOIN verse_themes vt ON vf.verse_id = vt.verse_id
           LEFT JOIN themes t ON vt.cluster_id = t.cluster_id
           WHERE vf.verse_id = ?""",
        (verse_id,)
    )

    if row.empty:
        return html.P(f"Verse {verse_id} not found.", className="loading-text")

    r           = row.iloc[0]
    rev_class   = "badge-meccan" if r["revelation_type"] == "Meccan" else "badge-medinan"
    theme_color = r["color_hex"] if r["color_hex"] else "#4a7c59"

    return html.Div([
        html.Div([
            html.Span(r["verse_id"], className="verse-id"),
            html.Span(r["revelation_type"], className=f"badge {rev_class}"),
            html.Span(r["name_english"], style={"fontSize": "11px", "color": "#6b6050", "marginLeft": "8px"}),
            html.Span(r["name_arabic"],  style={"fontSize": "13px", "color": "#6b6050", "marginLeft": "6px",
                                                "fontFamily": "'Amiri', serif", "direction": "rtl"}),
            html.Span(r["name_arabic"],
                      style={"fontSize": "13px", "color": "#6b6050",
                             "fontFamily": "'Amiri', serif", "marginLeft": "8px"}),
        ]),
        html.Div(r["arabic_text"],  className="verse-arabic"),
        html.Div(r["english_text"] or "", className="verse-english"),
        html.Div([
            html.Span(r["label_english"] or "Unclustered", className="badge badge-theme",
                      style={"borderColor": theme_color, "color": theme_color}),
        ], style={"marginTop": "10px"}),
    ], className="verse-card", style={"margin": "0", "borderLeftColor": theme_color})


def _placeholder_fig(msg="Embeddings not yet generated. Run the pipeline first."):
    fig = go.Figure()
    fig.add_annotation(text=msg, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=13, color="#6b6050"), align="center")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig