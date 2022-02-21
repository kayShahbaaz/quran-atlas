import dash

app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    meta_tags=[
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"charset": "UTF-8"},
    ],
)
app.title = "Quran Atlas | أطلس القرآن"
server = app.server