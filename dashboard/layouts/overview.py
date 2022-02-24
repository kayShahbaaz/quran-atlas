"""
dashboard/layouts/overview.py

Overview tab — high-level stats and Quran-wide visualizations.

Shows:
  - 6 stat cards (verses, surahs, Meccan/Medinan counts, etc.)
  - Meccan vs Medinan donut chart
  - Verse length distribution (word count histogram)
  - Theme distribution bar chart
  - Root word domain breakdown
"""

from dash import html
from dash import dcc
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Shared chart config
CHART_CONFIG = {"displayModeBar": False}
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Libre Baskerville, serif", color="#a89a7a", size=12),
    margin=dict(l=10, r=10, t=30, b=10),
)


def build_overview_layout(overview_df: pd.DataFrame, themes_df: pd.DataFrame):
    total_verses  = len(overview_df)
    total_surahs  = overview_df["surah_number"].nunique()
    meccan_verses = len(overview_df[overview_df["revelation_type"] == "Meccan"])
    medinan_verses = total_verses - meccan_verses
    meccan_surahs  = overview_df[overview_df["revelation_type"] == "Meccan"]["surah_number"].nunique()
    medinan_surahs = total_surahs - meccan_surahs
    avg_words = overview_df["word_count_ar"].mean() if "word_count_ar" in overview_df.columns else 0

    return html.Div([
        # ── Section header
        html.Div([
            html.H2("Overview", className="section-title"),
            html.P(
                "A bird's-eye view of the Quran's structure, revelation periods, and thematic composition.",
                className="section-subtitle"
            ),
        ]),

        # ── Stat cards
        html.Div([
            stat_card(str(total_verses),   "Total Ayaat",     "الآيات"),
            stat_card(str(total_surahs),   "Surah",           "السور"),
            stat_card(str(meccan_surahs),  "Meccan Surah",    "المكية"),
            stat_card(str(medinan_surahs), "Medinan Surah",   "المدنية"),
            stat_card(str(meccan_verses),  "Meccan Ayaat",    "آيات مكية"),
            stat_card(f"{avg_words:.1f}", "Avg Words/Ayah",  "متوسط الكلمات"),
        ], className="stats-grid"),

        # ── Row 1: Donut + Histogram
        html.Div([
            html.Div([
                html.Div("Revelation Period Breakdown", className="card-title"),
                dcc.Graph(
                    figure=make_revelation_donut(overview_df),
                    config=CHART_CONFIG,
                    style={"height": "320px"},
                ),
            ], className="chart-container"),

            html.Div([
                html.Div("Ayah Length Distribution (Arabic words)", className="card-title"),
                dcc.Graph(
                    figure=make_word_count_histogram(overview_df),
                    config=CHART_CONFIG,
                    style={"height": "320px"},
                ),
            ], className="chart-container"),
        ], className="two-col"),

        # ── Row 2: Theme distribution
        html.Div([
            html.Div("Thematic Distribution", className="card-title"),
            dcc.Graph(
                figure=make_theme_bar(themes_df),
                config=CHART_CONFIG,
                style={"height": "360px"},
            ),
        ], className="chart-container") if not themes_df.empty else html.Div(),

        # ── Row 3: Verses per surah heatmap
        html.Div([
            html.Div("Ayah Count per Surah (Revelation Order)", className="card-title"),
            dcc.Graph(
                figure=make_surah_verses_bar(overview_df),
                config=CHART_CONFIG,
                style={"height": "380px"},
            ),
        ], className="chart-container"),

    ])


def stat_card(number, label_en, label_ar):
    return html.Div([
        html.Div(number, className="stat-number"),
        html.Div(label_en, className="stat-label"),
        html.Div(label_ar, className="stat-label-ar"),
    ], className="stat-card")


def make_revelation_donut(df: pd.DataFrame) -> go.Figure:
    counts = df["revelation_type"].value_counts()
    fig = go.Figure(go.Pie(
        labels=counts.index.tolist(),
        values=counts.values.tolist(),
        hole=0.55,
        marker=dict(
            colors=["#e8943a", "#4a9fd4"],
            line=dict(color="#0f0e0c", width=2),
        ),
        textinfo="label+percent",
        textfont=dict(size=13, color="#e8e0d0"),
        hovertemplate="<b>%{label}</b><br>%{value} Ayaat<br>%{percent}<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        showlegend=False,
        annotations=[dict(
            text=f"{len(df)}<br><span style='font-size:11px'>Ayaat</span>",
            x=0.5, y=0.5,
            font=dict(size=20, color="#c9a84c"),
            showarrow=False,
        )],
    )
    return fig


def make_word_count_histogram(df: pd.DataFrame) -> go.Figure:
    if "word_count_ar" not in df.columns:
        return go.Figure()

    words = df["word_count_ar"].dropna()
    fig = go.Figure(go.Histogram(
        x=words,
        nbinsx=50,
        marker=dict(
            color="#c9a84c",
            line=dict(color="#0f0e0c", width=0.5),
        ),
        hovertemplate="Words: %{x}<br>Count: %{y}<extra></extra>",
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        xaxis=dict(title="Word Count", gridcolor="#2e2a22", zeroline=False),
        yaxis=dict(title="Number of Ayaat", gridcolor="#2e2a22", zeroline=False),
        bargap=0.05,
    )
    return fig


def make_theme_bar(themes_df: pd.DataFrame) -> go.Figure:
    if themes_df.empty or "verse_count" not in themes_df.columns:
        return go.Figure()

    df = themes_df[themes_df["verse_count"] > 0].sort_values("verse_count", ascending=True)

    fig = go.Figure(go.Bar(
        x=df["verse_count"],
        y=df["label_english"],
        orientation="h",
        marker=dict(
            color=df["color_hex"].tolist() if "color_hex" in df.columns else "#c9a84c",
            line=dict(color="#0f0e0c", width=0.5),
        ),
        text=df["verse_count"],
        textposition="outside",
        textfont=dict(color="#a89a7a", size=11),
        hovertemplate="<b>%{y}</b><br>%{x} Ayaat<extra></extra>",
    ))
    fig.update_layout(
    **CHART_LAYOUT,
    xaxis=dict(title="Ayah Count", gridcolor="#2e2a22", zeroline=False),
    yaxis=dict(gridcolor="#2e2a22", zeroline=False),
    )
    fig.update_layout(margin=dict(l=220, r=60, t=20, b=30))
    return fig


def make_surah_verses_bar(df: pd.DataFrame) -> go.Figure:
    # Group by surah, sort by revelation order
    grouped = (
        df.groupby(["surah_number", "name_english", "revelation_type", "revelation_order"])
        .size()
        .reset_index(name="verse_count")
        .sort_values("revelation_order")
    )

    colors = grouped["revelation_type"].map(
        {"Meccan": "#e8943a", "Medinan": "#4a9fd4"}
    ).tolist()

    fig = go.Figure(go.Bar(
        x=grouped["revelation_order"],
        y=grouped["verse_count"],
        marker=dict(color=colors, line=dict(color="#0f0e0c", width=0.3)),
        customdata=grouped[["name_english", "revelation_type", "surah_number"]].values,
        hovertemplate=(
            "<b>%{customdata[0]}</b> (Surah %{customdata[2]})<br>"
            "Revelation order: %{x}<br>"
            "Ayaat: %{y}<br>"
            "Period: %{customdata[1]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        **CHART_LAYOUT,
        xaxis=dict(title="Chronological Revelation Order →", gridcolor="#2e2a22", zeroline=False),
        yaxis=dict(title="Ayah Count", gridcolor="#2e2a22", zeroline=False),
        bargap=0.1,
    )
    return fig
