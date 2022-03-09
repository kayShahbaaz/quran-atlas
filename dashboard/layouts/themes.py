"""
dashboard/layouts/themes.py

Theme Map tab — UMAP scatter plot of all 6236 verses,
colored by semantic theme cluster.

Also includes:
  - Theme legend with verse counts
  - Filter by revelation period
  - Click a dot → see that verse
"""

from dash import html
from dash import dcc
import plotly.graph_objects as go
import pandas as pd


CHART_CONFIG = {"displayModeBar": True, "scrollZoom": True}
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Libre Baskerville, serif", color="#a89a7a", size=12),
)


def build_themes_layout(umap_df, themes_df: pd.DataFrame):
    has_umap = umap_df is not None and len(umap_df) > 0

    return html.Div([
        # ── Header
        html.Div([
            html.H2("Semantic Theme Map", className="section-title"),
            html.P(
                "Every Ayah embedded as a point in 2D space using UMAP. "
                "Ayaat close together share semantic meaning. Colors represent thematic clusters.",
                className="section-subtitle"
            ),
        ]),

        # ── Controls row
        html.Div([
            html.Div([
                html.Label("Filter by Revelation Period", className="control-label"),
                dcc.RadioItems(
                    id="theme-revelation-filter",
                    options=[
                        {"label": "All Ayaat", "value": "all"},
                        {"label": "Meccan Only", "value": "Meccan"},
                        {"label": "Medinan Only", "value": "Medinan"},
                    ],
                    value="all",
                    labelStyle={"display": "inline-block", "marginRight": "20px",
                                "color": "#a89a7a", "fontSize": "13px", "cursor": "pointer"},
                    inputStyle={"marginRight": "6px", "accentColor": "#c9a84c"},
                ),
            ]),

            html.Div([
                html.Label("Filter by Theme", className="control-label"),
                dcc.Dropdown(
                    id="theme-cluster-filter",
                    options=[{"label": "All Themes", "value": "all"}] + (
                        [{"label": row["label_english"], "value": str(row["cluster_id"])}
                         for _, row in themes_df.iterrows()]
                        if not themes_df.empty else []
                    ),
                    value="all",
                    clearable=False,
                    style={"color": "#4a3e28"},
                ),
            ]),
        ], style={"display": "flex", "gap": "40px", "alignItems": "flex-start",
                  "marginBottom": "20px", "flexWrap": "wrap"}),

        # ── Main UMAP scatter
        html.Div([
            html.Div("Semantic Space — 6,236 Ayaat", className="card-title"),
            dcc.Graph(
                id="umap-scatter",
                figure=make_umap_figure(umap_df) if has_umap else make_placeholder_figure(),
                config={**CHART_CONFIG, "displaylogo": False},
                style={"height": "580px"},
            ),
            html.P(
                "Tip: Scroll to zoom · Click a point to see the Ayah · "
                "Double-click to reset view",
                style={"fontSize": "11px", "color": "#6b6050", "marginTop": "8px",
                       "fontStyle": "italic"},
            ),
        ], className="chart-container"),

        # ── Clicked verse detail
        html.Div([
            html.Div("Selected Ayah", className="card-title"),
            html.Div(
                id="theme-verse-detail",
                children=html.P(
                    "Click any point on the map to view the Ayah here.",
                    className="loading-text",
                ),
            ),
        ], className="card"),

        # ── Theme legend
        html.Div([
            html.Div("Theme Legend", className="card-title"),
            html.Div(
                build_theme_legend(themes_df),
                style={"display": "grid",
                       "gridTemplateColumns": "repeat(auto-fill, minmax(260px, 1fr))",
                       "gap": "10px"},
            ),
        ], className="card") if not themes_df.empty else html.Div(),

    ])


def make_umap_figure(umap_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()

    themes = umap_df["theme"].unique()
    colors = umap_df.drop_duplicates("theme").set_index("theme")["color"]

    for theme in themes:
        mask = umap_df["theme"] == theme
        sub = umap_df[mask]
        color = colors.get(theme, "#888888")

        fig.add_trace(go.Scattergl(
            x=sub["x"],
            y=sub["y"],
            mode="markers",
            name=theme,
            marker=dict(
                color=color,
                size=4,
                opacity=0.65,
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
            bgcolor="rgba(26,24,20,0.9)",
            bordercolor="#2e2a22",
            borderwidth=1,
            font=dict(size=11, color="#a89a7a"),
            itemsizing="constant",
        ),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        margin=dict(l=0, r=10, t=10, b=0),
        hovermode="closest",
        dragmode="pan",
    )
    return fig


def make_placeholder_figure() -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=(
            "UMAP embeddings not yet generated.<br>"
            "Run: <b>python embeddings/generate_embeddings.py</b><br>"
            "then: <b>python embeddings/cluster_themes.py</b>"
        ),
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color="#6b6050"),
        align="center",
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    )
    return fig


def build_theme_legend(themes_df: pd.DataFrame) -> list:
    items = []
    for _, row in themes_df.iterrows():
        color = row.get("color_hex", "#888888")
        count = int(row.get("verse_count", 0))
        label_en = row.get("label_english", "")
        label_ar = row.get("label_arabic", "")

        items.append(html.Div([
            html.Div(style={
                "width": "12px", "height": "12px",
                "borderRadius": "2px",
                "backgroundColor": color,
                "flexShrink": "0",
                "marginTop": "3px",
            }),
            html.Div([
                html.Span(label_en, style={"color": "#e8e0d0", "fontSize": "13px"}),
                html.Span(f"  {label_ar}" if label_ar else "",
                          style={"color": "#a89a7a", "fontFamily": "'Amiri', serif",
                                 "fontSize": "13px", "marginLeft": "6px"}),
                html.Div(f"{count} Ayaat", style={"fontSize": "11px", "color": "#6b6050"}),
            ]),
        ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start",
                  "padding": "8px", "borderRadius": "4px",
                  "background": "#1a1814", "border": "1px solid #2e2a22"}))

    return items
