"""
dashboard/callbacks/root_callbacks.py

Version 2 — fixes:
  - Removed duplicate update_root_verses callback (was causing Dash conflict)
  - Chart now shows ALL surahs (no LIMIT 30)
  - Dynamic chart height so all surahs visible
  - Sort ASC so low-count surahs (Al-Fatiha etc) appear at top
  - Single clean update_root_verses with click-to-filter support
"""

import sys
import os

from dash import html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dashboard.server import app
from dashboard.app import DB_PATH, query_df

CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Libre Baskerville, serif", color="#a89a7a", size=12),
    margin=dict(l=10, r=10, t=20, b=20),
)


# ── Stats row ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("root-stats-row", "children"),
    [Input("root-dropdown", "value")],
)
def update_root_stats(root_arabic):
    if not root_arabic:
        return html.Div()

    df = query_df(
        "SELECT * FROM v_root_distribution WHERE root_arabic = ?",
        (root_arabic,)
    )
    root_info = query_df(
        "SELECT * FROM root_words WHERE root_arabic = ?",
        (root_arabic,)
    )

    if df.empty or root_info.empty:
        return html.Div("No data found for this root.", className="loading-text")

    total       = int(df["occurrences"].sum())
    surah_count = df["surah_number"].nunique()
    meccan      = int(df[df["revelation_type"] == "Meccan"]["occurrences"].sum())
    medinan     = total - meccan
    domain      = root_info.iloc[0]["domain"]

    return html.Div([
        html.Div([
            html.Div(root_arabic, className="stat-number",
                     style={"fontFamily": "'Amiri', serif", "fontSize": "38px"}),
            html.Div("Root", className="stat-label"),
        ], className="stat-card"),
        html.Div([
            html.Div(str(total), className="stat-number"),
            html.Div("Total Occurrences", className="stat-label"),
        ], className="stat-card"),
        html.Div([
            html.Div(str(surah_count), className="stat-number"),
            html.Div("Surahs", className="stat-label"),
        ], className="stat-card"),
        html.Div([
            html.Div(str(meccan), className="stat-number",
                     style={"color": "#e8943a"}),
            html.Div("Meccan Ayaat", className="stat-label"),
        ], className="stat-card"),
        html.Div([
            html.Div(str(medinan), className="stat-number",
                     style={"color": "#4a9fd4"}),
            html.Div("Medinan Ayaat", className="stat-label"),
        ], className="stat-card"),
        html.Div([
            html.Div(domain, className="stat-number",
                     style={"fontSize": "16px", "lineHeight": "1.3"}),
            html.Div("Semantic Domain", className="stat-label"),
        ], className="stat-card"),
    ], className="stats-grid", style={"marginBottom": "20px"})


# ── Distribution bar chart ────────────────────────────────────────────────────

@app.callback(
    Output("root-surah-chart", "figure"),
    [Input("root-dropdown", "value")],
)
def update_root_surah_chart(root_arabic):
    if not root_arabic:
        return go.Figure()

    df = query_df(
        """SELECT surah_number, surah_name_en, revelation_type, occurrences
           FROM v_root_distribution
           WHERE root_arabic = ?
           ORDER BY occurrences ASC""",
        (root_arabic,)
    )
    if df.empty:
        return _empty_fig("No occurrences found")

    colors = df["revelation_type"].map(
        {"Meccan": "#e8943a", "Medinan": "#4a9fd4"}
    ).tolist()

    fig = go.Figure(go.Bar(
        y=df["surah_name_en"],
        x=df["occurrences"],
        orientation="h",
        marker=dict(color=colors, line=dict(color="#0f0e0c", width=0.5)),
        text=df["occurrences"],
        textposition="outside",
        textfont=dict(color="#a89a7a", size=11),
        hovertemplate="<b>%{y}</b><br>Occurrences: %{x}<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        xaxis=dict(title="Occurrences", gridcolor="#2e2a22", zeroline=False),
        yaxis=dict(gridcolor="rgba(0,0,0,0)", zeroline=False, automargin=True),
        height=max(400, len(df) * 26),
    )
    fig.update_layout(margin=dict(l=140, r=60, t=20, b=20))
    return fig


# ── Meccan vs Medinan donut ───────────────────────────────────────────────────

@app.callback(
    Output("root-revelation-chart", "figure"),
    [Input("root-dropdown", "value")],
)
def update_root_revelation_chart(root_arabic):
    if not root_arabic:
        return go.Figure()

    df = query_df(
        """SELECT revelation_type, SUM(occurrences) as total
           FROM v_root_distribution
           WHERE root_arabic = ?
           GROUP BY revelation_type""",
        (root_arabic,)
    )
    if df.empty:
        return _empty_fig("No data")

    fig = go.Figure(go.Pie(
        labels=df["revelation_type"].tolist(),
        values=df["total"].tolist(),
        hole=0.55,
        marker=dict(
            colors=["#e8943a" if r == "Meccan" else "#4a9fd4"
                    for r in df["revelation_type"]],
            line=dict(color="#0f0e0c", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=13, color="#e8e0d0"),
        hovertemplate=(
            "<b>%{label}</b><br>%{value} occurrences (%{percent})<extra></extra>"
        ),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Libre Baskerville, serif", color="#a89a7a", size=12),
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    return fig


# ── Chronological timeline ────────────────────────────────────────────────────

@app.callback(
    Output("root-timeline-chart", "figure"),
    [Input("root-dropdown", "value")],
)
def update_root_timeline(root_arabic):
    if not root_arabic:
        return go.Figure()

    df = query_df(
        """SELECT revelation_order, surah_number, surah_name_en,
                  revelation_type, occurrences
           FROM v_root_distribution
           WHERE root_arabic = ?
           ORDER BY revelation_order""",
        (root_arabic,)
    )
    if df.empty:
        return _empty_fig("No timeline data")

    colors = df["revelation_type"].map(
        {"Meccan": "#e8943a", "Medinan": "#4a9fd4"}
    ).tolist()

    fig = go.Figure()
    fig.add_shape(
        type="line", x0=0, x1=114, y0=0, y1=0,
        line=dict(color="#2e2a22", width=1)
    )
    fig.add_trace(go.Bar(
        x=df["revelation_order"],
        y=df["occurrences"],
        marker=dict(color=colors, line=dict(color="#0f0e0c", width=0.3)),
        customdata=df[["surah_name_en", "revelation_type"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Revelation order: %{x}<br>"
            "Occurrences: %{y}<br>"
            "%{customdata[1]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        xaxis=dict(
            title="Chronological Revelation Order →",
            range=[0, 115],
            gridcolor="#2e2a22",
            zeroline=False,
        ),
        yaxis=dict(title="Occurrences", gridcolor="#2e2a22", zeroline=False),
        bargap=0.15,
    )
    return fig


# ── Ayaat list (with click-to-filter by surah) ───────────────────────────────

@app.callback(
    [Output("root-verses-list",       "children"),
     Output("root-verses-card-title", "children")],
    [Input("root-dropdown",    "value"),
     Input("root-surah-chart", "clickData")],
)
def update_root_verses(root_arabic, click_data):
    if not root_arabic:
        return (
            html.P("Select a root word to see Ayaat.", className="loading-text"),
            "Sample Ayaat Containing This Root",
        )

    # Determine if a bar was clicked to filter by surah
    surah_name = None
    if click_data:
        try:
            surah_name = click_data["points"][0]["y"]
        except Exception:
            pass

    if surah_name:
        df = query_df(
            """SELECT vf.verse_id, vf.arabic_text, vf.english_text,
                      vf.name_english, vf.name_arabic, vf.revelation_type,
                      vf.verse_number, vf.surah_number
               FROM v_verses_full vf
               JOIN verse_roots vr ON vf.verse_id = vr.verse_id
               WHERE vr.root_arabic = ?
               AND vf.name_english = ?
               ORDER BY vf.verse_number""",
            (root_arabic, surah_name)
        )
        title = f"Ayaat in {surah_name} containing this root ({len(df)} found)"
    else:
        df = query_df(
            """SELECT vf.verse_id, vf.arabic_text, vf.english_text,
                      vf.name_english, vf.name_arabic, vf.revelation_type,
                      vf.verse_number, vf.surah_number
               FROM v_verses_full vf
               JOIN verse_roots vr ON vf.verse_id = vr.verse_id
               WHERE vr.root_arabic = ?
               ORDER BY vf.surah_number, vf.verse_number
               LIMIT 8""",
            (root_arabic,)
        )
        title = "Sample Ayaat Containing This Root (click a bar to filter by Surah)"

    if df.empty:
        return html.P("No Ayaat found.", className="loading-text"), title

    cards = []
    for _, row in df.iterrows():
        rev_class = (
            "badge-meccan" if row["revelation_type"] == "Meccan"
            else "badge-medinan"
        )
        cards.append(html.Div([
            html.Div([
                html.Span(row["verse_id"], className="verse-id"),
                html.Span(
                    row["revelation_type"],
                    className=f"badge {rev_class}",
                    style={"marginLeft": "8px"},
                ),
                html.Span(
                    row["name_english"],
                    style={"fontSize": "11px", "color": "#6b6050",
                           "marginLeft": "8px"},
                ),
                html.Span(
                    row["name_arabic"],
                    style={"fontSize": "13px", "color": "#6b6050",
                           "marginLeft": "6px",
                           "fontFamily": "'Amiri', serif"},
                ),
            ]),
            html.Div(row["arabic_text"], className="verse-arabic"),
            html.Div(
                row["english_text"] or "",
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
                },
            ),
        ], className="verse-card"))

    return html.Div(cards), title


# ── Empty figure helper ───────────────────────────────────────────────────────

def _empty_fig(msg=""):
    fig = go.Figure()
    if msg:
        fig.add_annotation(
            text=msg, xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(color="#6b6050", size=13),
        )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig