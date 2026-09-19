"""Readable Telegram HTML, escaped at the boundary; no fake countdowns."""
from html import escape
from urllib.parse import urlsplit


def format_editorial(article, *, html=True):
    report = (article.ai_impact or {}).get('editorial', {})
    d = report.get('draft', {})
    if not d:
        return None
    e = escape if html else str
    def label(text):
        return f'<b>{e(text)}</b>' if html else text
    parts = [label(d['headline']), e(d['lead'])]
    parts.append('\n'.join('• ' + e(f['claim']) for f in d['facts']))
    for title, key in [('Как это работает', 'technical_detail'), ('Зачем это нужно', 'why_it_matters'),
                       ('Мой вывод', 'take'), ('Где границы', 'caveat'), ('Что проверить', 'practical_step')]:
        parts.append(label(title) + '\n' + e(d[key]))
    host = urlsplit(article.url).hostname or article.source_id
    source = f'<a href="{escape(article.url, quote=True)}">{escape(host)}</a>' if html else article.url
    parts.append('Источник: ' + source)
    return '\n\n'.join(parts)
