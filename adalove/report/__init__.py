"""Module report: the single place that turns raw Adalove activities into
what the student reads — the per-week summary, sprint calendar, project
artifacts, exam (Prova) material and ponderadas.

    model.py     activities → plain, structured data (no presentation)
    markdown.py  structured data → the .md exports
    common.py    small shared rules (dates, link classification, scopes)

writers/html.py renders the same structured data as the dashboard and embeds
the Markdown exports, so every output format comes from one source.
"""
