"""
dashboard/layouts/narrative.py

Version 3 — 40 preset topics across 7 categories.
"""

from dash import dcc, html


# 7 categories with topics listed under each
CATEGORIES = {
    "Theology & Faith": [
        "mercy and forgiveness",
        "day of judgment",
        "repentance",
        "guidance and misguidance",
        "covenant and promise",
        "trust and hypocrisy",
        "remembrance of god",
        "divine oneness",
    ],
    "Human Character": [
        "patience and hardship",
        "gratitude",
        "justice and oppression",
        "the heart",
        "satan and temptation",
        "arrogance and pride",
    ],
    "Society & Law": [
        "women and rights",
        "children and orphans",
        "family and community",
        "trade and honesty",
        "wealth and charity",
        "food and lawful eating",
        "unity and division",
    ],
    "Worship & Prophethood": [
        "prayer and worship",
        "knowledge and wisdom",
        "prophets and messengers",
        "fasting and self-discipline",
        "pilgrimage and sacred places",
        "supplication and prayer",
    ],
    "Eschatology & Unseen": [
        "paradise",
        "hellfire and punishment",
        "death and dying",
        "angels",
        "prayer for the dead",
        "signs and miracles",
    ],
    "Nature & Creation": [
        "nature and creation",
        "water and rain",
        "creation of humans",
        "animals and living creatures",
        "time and history",
    ],
    "Conflict, Test & Struggle": [
        "patience under trial",
        "war and peace",
        "forgiveness between people",
        "migration and exile",
        "oppressed and vulnerable",
        "striving and effort",
        "accountability and reckoning",
    ],
}

# Flat list for index-based callback lookup
SUGGESTED_TOPICS = [
    topic
    for topics in CATEGORIES.values()
    for topic in topics
]


def make_topic_button(topic, global_index):
    return html.Button(
        topic,
        id={"type": "topic-suggestion", "index": global_index},
        n_clicks=0,
        style={
            "background":   "#1a1814",
            "color":        "#a89a7a",
            "border":       "1px solid #2e2a22",
            "borderRadius": "3px",
            "padding":      "3px 10px",
            "fontSize":     "11px",
            "cursor":       "pointer",
            "margin":       "2px",
            "whiteSpace":   "nowrap",
        }
    )


def build_narrative_layout():
    # Build index map: topic -> global index in SUGGESTED_TOPICS
    topic_index = {topic: i for i, topic in enumerate(SUGGESTED_TOPICS)}

    # Build category rows
    category_rows = []
    for cat_name, topics in CATEGORIES.items():
        row = html.Div([
            html.Span(
                f"{cat_name}  —  ",
                style={
                    "fontSize":     "10px",
                    "color":        "#c9a84c",
                    "fontWeight":   "700",
                    "letterSpacing":"0.5px",
                    "textTransform":"uppercase",
                    "marginRight":  "4px",
                    "whiteSpace":   "nowrap",
                    "alignSelf":    "center",
                }
            ),
        ] + [
            make_topic_button(topic, topic_index[topic])
            for topic in topics
        ], style={
            "display":     "flex",
            "flexWrap":    "wrap",
            "alignItems":  "center",
            "marginBottom":"8px",
            "paddingBottom":"8px",
            "borderBottom":"1px solid #1e1c18",
        })
        category_rows.append(row)

    return html.Div([

        # ── Header
        html.Div([
            html.H2("Narrative Thread", className="section-title"),
            html.P(
                "Search any topic and trace how it unfolds chronologically "
                "through the Quran — from early Meccan revelation to Medinan guidance. "
                "40 preset topics across 7 categories with Thematic Overview.",
                className="section-subtitle"
            ),
        ]),

        # ── Search box card
        html.Div([
            html.Div("TOPIC SEARCH  |  البحث الموضوعي", className="card-title"),

            html.P(
                "Type any concept in English or Arabic and press Enter or click Search. "
                "Click any preset topic below for instant results with Thematic Overview.",
                style={
                    "fontSize":    "13px",
                    "color":       "#a89a7a",
                    "fontStyle":   "italic",
                    "marginBottom":"16px",
                }
            ),

            # Input + Search button
            html.Div([
                dcc.Input(
                    id="narrative-topic-input",
                    type="text",
                    placeholder='e.g. "mercy", "day of judgment", "الصبر"',
                    debounce=True,
                    n_submit=0,
                    style={"flex": "1"},
                ),
                html.Button(
                    "Search",
                    id="narrative-search-btn",
                    n_clicks=0,
                    style={"marginLeft": "10px", "whiteSpace": "nowrap"},
                ),
            ], style={"display": "flex", "alignItems": "center",
                      "marginBottom": "16px"}),

            # Result count
            html.Div([
                html.Label("Show", className="control-label",
                           style={"marginRight": "12px", "marginBottom": "0"}),
                dcc.RadioItems(
                    id="narrative-result-count",
                    options=[
                        {"label": "Top 10 Ayaat", "value": 10},
                        {"label": "Top 20 Ayaat", "value": 20},
                        {"label": "All Ayaat",    "value": 999},
                    ],
                    value=10,
                    labelStyle={"display": "inline-block", "marginRight": "20px",
                                "color": "#a89a7a", "fontSize": "13px"},
                    inputStyle={"marginRight": "6px", "accentColor": "#c9a84c"},
                ),
            ], style={"display": "flex", "alignItems": "center",
                      "marginBottom": "20px"}),

            # ── Category rows
            html.Div(
                "PRESET TOPICS WITH COMMENTARY",
                style={
                    "fontSize":     "10px",
                    "color":        "#6b6050",
                    "fontWeight":   "700",
                    "letterSpacing":"1px",
                    "marginBottom": "12px",
                }
            ),
            html.Div(category_rows),

        ], className="card"),

        # ── Status line
        html.Div(id="narrative-status", style={"marginBottom": "10px"}),

        # ── Thematic Overview
        html.Div(id="narrative-overview-section"),

        # ── Ayaat results + stats
        html.Div(
            id="narrative-results",
            children=html.P(
                "Enter a topic above to begin.",
                className="loading-text",
            )
        ),

    ])