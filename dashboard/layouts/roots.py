"""
dashboard/layouts/roots.py

Root Word Explorer tab layout.

The user picks a root word (e.g. "عدل" justice) from the dropdown.
The callbacks in root_callbacks.py fill in:
  - Distribution bar chart (occurrences per surah)
  - Meccan vs Medinan split donut
  - Chronological timeline (revelation order)
  - Top verses containing that root
"""

from dash import html
from dash import dcc


def build_roots_layout(root_options: list):
    return html.Div([
        # ── Header
        html.Div([
            html.H2("Root Word Explorer", className="section-title"),
            html.P(
                "Arabic root words (الجذور) are the semantic building blocks of the Quran. "
                "Select a root to trace its distribution, chronological evolution, and key Ayaat.",
                className="section-subtitle"
            ),
        ]),

        # ── Root selector
        html.Div([
            html.Label("Select a Root Word  |  اختر جذراً", className="control-label"),
            dcc.Dropdown(
                id="root-dropdown",
                options=root_options,
                value=root_options[0]["value"] if root_options else None,
                placeholder="Search root words...",
                clearable=False,
                style={"color": "#4a3e28"},
            ),
        ], className="control-group card"),

        # ── Stats row for selected root
        html.Div(id="root-stats-row"),

        # ── Charts row
        html.Div([
            # Distribution by surah
            html.Div([
                html.Div("Distribution Across Surahs", className="card-title"),
                dcc.Graph(
                    id="root-surah-chart",
                    config={"displayModeBar": False},
                    style={"overflowY": "auto"},
                ),
            ], className="chart-container"),

            # Meccan vs Medinan
            html.Div([
                html.Div("Meccan vs. Medinan Split", className="card-title"),
                dcc.Graph(
                    id="root-revelation-chart",
                    config={"displayModeBar": False},
                    style={"height": "340px", "overflow": "hidden"},
                ),
            ], className="chart-container", style={"overflow": "hidden"}),
        ], className="two-col"),

        # ── Chronological timeline
        html.Div([
            html.Div(
                "Chronological Timeline (Revelation Order)",
                className="card-title"
            ),
            dcc.Graph(
                id="root-timeline-chart",
                config={"displayModeBar": False},
                style={"height": "260px"},
            ),
        ], className="chart-container"),

        # ── Sample verses
       html.Div([
        html.Div(id="root-verses-card-title",
             children="Sample Ayaat Containing This Root",
             className="card-title"),
        html.Div(id="root-verses-list"),
    ], className="card"),

    ])
