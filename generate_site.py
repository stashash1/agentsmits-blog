#!/usr/bin/env python3
"""
Генератор блога AI Агенты Смита
- Lenta: краткие посты из pending_queue
- Articles: развёрнутые статьи из selection_queue
- RSS для Яндекс Дзен
"""

import json
import os
from datetime import datetime
from pathlib import Path

BLOG_DIR = Path(__file__).parent
OUTPUT_DIR = BLOG_DIR / "public"
POSTS_DIR = BLOG_DIR / "posts"

TEMPLATE_INDEX = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;900&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --bg-primary: #08080c;
            --bg-secondary: #0f0f14;
            --bg-card: #13131a;
            --bg-card-hover: #18181f;
            --border: #1e1e28;
            --border-light: #2a2a38;
            --text-primary: #e8e6e1;
            --text-secondary: #8a8a9a;
            --text-muted: #5a5a6a;
            --accent: #e8a044;
            --accent-dim: #a87230;
            --accent-blue: #5b8af0;
            --accent-red: #e85555;
            --accent-green: #4aba7a;
            --font-serif: 'Playfair Display', Georgia, serif;
            --font-sans: 'Inter', system-ui, sans-serif;
            --font-mono: 'JetBrains Mono', monospace;
        }}

        body {{
            background: var(--bg-primary);
            color: var(--text-primary);
            font-family: var(--font-sans);
            line-height: 1.7;
            min-height: 100vh;
        }}

        a {{ color: inherit; text-decoration: none; }}
        a:hover {{ color: var(--accent); }}

        /* ── Header ── */
        .site-header {{
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            position: sticky;
            top: 0;
            z-index: 100;
            backdrop-filter: blur(12px);
        }}

        .header-inner {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            height: 72px;
        }}

        .site-logo {{
            display: flex;
            align-items: center;
            gap: 14px;
        }}

        .logo-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--accent), var(--accent-dim));
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
            flex-shrink: 0;
        }}

        .logo-text {{
            font-family: var(--font-serif);
            font-size: 1.35rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: var(--text-primary);
        }}

        .logo-sub {{
            font-size: 0.7rem;
            color: var(--text-muted);
            font-family: var(--font-mono);
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-top: 2px;
        }}

        .main-nav {{
            display: flex;
            gap: 4px;
        }}

        .nav-link {{
            padding: 8px 18px;
            border-radius: 8px;
            font-size: 0.88rem;
            font-weight: 500;
            color: var(--text-secondary);
            transition: all 0.2s;
            letter-spacing: 0.01em;
        }}

        .nav-link:hover {{ background: var(--border); color: var(--text-primary); }}
        .nav-link.active {{ background: var(--border-light); color: var(--accent); }}

        /* ── Page shell ── */
        .page-wrapper {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        /* ── Hero ── */
        .hero {{
            padding: 56px 0 48px;
            border-bottom: 1px solid var(--border);
            margin-bottom: 48px;
        }}

        .hero-label {{
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .hero-label::before {{
            content: '';
            display: block;
            width: 32px;
            height: 2px;
            background: var(--accent);
        }}

        .hero-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 32px;
        }}

        .hero-main {{ grid-column: 1 / -1; }}

        .hero-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            overflow: hidden;
            transition: all 0.3s;
            display: flex;
            flex-direction: column;
        }}

        .hero-card:hover {{
            border-color: var(--border-light);
            transform: translateY(-3px);
            box-shadow: 0 20px 60px rgba(0,0,0,0.4);
        }}

        .hero-card-featured {{
            flex-direction: row;
            min-height: 280px;
        }}

        .hero-card-featured .card-body {{
            padding: 36px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .card-body {{
            padding: 28px;
            flex: 1;
        }}

        .card-meta {{
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 14px;
            flex-wrap: wrap;
        }}

        .card-source {{
            font-family: var(--font-mono);
            font-size: 0.7rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--accent);
            background: rgba(232,160,68,0.1);
            padding: 3px 10px;
            border-radius: 4px;
            border: 1px solid rgba(232,160,68,0.2);
        }}

        .card-date {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        .card-title {{
            font-family: var(--font-serif);
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.3;
            margin-bottom: 14px;
        }}

        .hero-card-featured .card-title {{ font-size: 1.9rem; }}
        .card-title-lg {{ font-size: 1.5rem; }}
        .card-title-md {{ font-size: 1.2rem; }}

        .card-summary {{
            font-size: 0.92rem;
            color: var(--text-secondary);
            line-height: 1.7;
        }}

        .card-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            margin-top: 20px;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--accent-blue);
            transition: gap 0.2s;
        }}

        .card-link:hover {{ gap: 10px; color: var(--accent-blue); }}

        /* ── Section header ── */
        .section-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 28px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }}

        .section-title {{
            font-family: var(--font-serif);
            font-size: 1.4rem;
            font-weight: 700;
        }}

        .section-count {{
            font-family: var(--font-mono);
            font-size: 0.75rem;
            color: var(--text-muted);
            background: var(--bg-card);
            padding: 4px 12px;
            border-radius: 20px;
            border: 1px solid var(--border);
        }}

        /* ── Cards grid ── */
        .cards-grid {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 64px;
        }}

        .cards-grid-2col {{
            grid-template-columns: repeat(2, 1fr);
        }}

        /* ── Card (regular) ── */
        .card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 24px;
            display: flex;
            flex-direction: column;
            transition: all 0.25s;
        }}

        .card:hover {{
            border-color: var(--border-light);
            background: var(--bg-card-hover);
            transform: translateY(-2px);
        }}

        .card-top {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
        }}

        .card-title-sm {{
            font-family: var(--font-serif);
            font-size: 1.05rem;
            font-weight: 600;
            line-height: 1.35;
            color: var(--text-primary);
            margin-bottom: 10px;
        }}

        .card-summary-sm {{
            font-size: 0.86rem;
            color: var(--text-secondary);
            line-height: 1.65;
            flex: 1;
        }}

        .card-tags {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
            margin-top: 14px;
        }}

        .tag {{
            font-family: var(--font-mono);
            font-size: 0.65rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 2px 8px;
            border-radius: 4px;
            background: var(--border);
            color: var(--text-muted);
        }}

        /* ── AGI Bar ── */
        .agi-bar {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin-bottom: 64px;
        }}

        .agi-icon {{ font-size: 1.2rem; }}

        .agi-info {{ flex: 1; }}

        .agi-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}

        .agi-label strong {{ color: var(--text-primary); }}

        .agi-track {{
            height: 6px;
            background: var(--border);
            border-radius: 3px;
            overflow: hidden;
        }}

        .agi-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent-green), #6dcea0);
            border-radius: 3px;
            transition: width 1s ease;
        }}

        .agi-pct {{
            font-family: var(--font-mono);
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--accent-green);
        }}

        /* ── Footer ── */
        .site-footer {{
            border-top: 1px solid var(--border);
            padding: 40px 0;
            text-align: center;
        }}

        .footer-inner {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        .footer-brand {{
            font-family: var(--font-serif);
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}

        .footer-meta {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        .footer-meta a {{ color: var(--accent); }}

        /* ── Empty state ── */
        .empty-state {{
            text-align: center;
            padding: 80px 0;
            color: var(--text-muted);
        }}

        .empty-state-icon {{ font-size: 3rem; margin-bottom: 16px; opacity: 0.3; }}
        .empty-state p {{ font-size: 1rem; }}

        /* ── Responsive ── */
        @media (max-width: 900px) {{
            .hero-grid {{ grid-template-columns: 1fr; }}
            .hero-card-featured {{ flex-direction: column; min-height: auto; }}
            .cards-grid {{ grid-template-columns: 1fr 1fr; }}
        }}

        @media (max-width: 600px) {{
            .header-inner {{ height: 60px; }}
            .logo-sub {{ display: none; }}
            .main-nav {{ gap: 0; }}
            .nav-link {{ padding: 6px 12px; font-size: 0.82rem; }}
            .cards-grid {{ grid-template-columns: 1fr; }}
            .hero {{ padding: 32px 0 32px; }}
            .hero-card-featured .card-title {{ font-size: 1.4rem; }}
        }}
    </style>
</head>
<body>
    <header class="site-header">
        <div class="header-inner">
            <a href="/" class="site-logo">
                <div class="logo-icon">🤖</div>
                <div>
                    <div class="logo-text">AI Агенты Смита</div>
                    <div class="logo-sub">AGI Countdown</div>
                </div>
            </a>
            <nav class="main-nav">
                <a href="index.html" class="nav-link active">📰 Лента</a>
                <a href="articles.html" class="nav-link">📖 Статьи</a>
                <a href="rss.xml" class="nav-link" target="_blank">📡 RSS</a>
            </nav>
        </div>
    </header>

    <div class="page-wrapper">
        {content}
    </div>

    <footer class="site-footer">
        <div class="footer-inner">
            <div class="footer-brand">🤖 AI Агенты Смита</div>
            <div class="footer-meta">
                Новости и аналитика искусственного интеллекта · Обновлено {updated}<br>
                <a href="https://t.me/agentsSmits" target="_blank">@agentsSmits</a> · <a href="rss.xml">RSS</a>
            </div>
        </div>
    </footer>
</body>
</html>"""

TEMPLATE_LENTA = """<section class="hero">
    <div class="hero-label">Последние новости</div>
    <div class="hero-grid">
        {hero}
    </div>
</section>

<section>
    <div class="section-header">
        <h2 class="section-title">Все посты</h2>
        <span class="section-count">{total} публикаций</span>
    </div>
    <div class="cards-grid">
        {cards}
    </div>
</section>

{agi_bar}"""

TEMPLATE_ARTICLES = """<section class="hero">
    <div class="hero-label">Глубокий анализ</div>
    <div class="hero-grid">
        {hero}
    </div>
</section>

<section>
    <div class="section-header">
        <h2 class="section-title">Архив статей</h2>
        <span class="section-count">{total} статей</span>
    </div>
    <div class="cards-grid cards-grid-2col">
        {cards}
    </div>
</section>

{agi_bar}"""

def load_json(filename):
    paths_to_try = [
        BLOG_DIR / filename,
        BLOG_DIR.parent / 'telegram-ai-channel' / filename,
        Path(os.environ.get('DATA_DIR', BLOG_DIR.parent)) / filename,
    ]
    for path in paths_to_try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    return None

def format_date(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y')
    except:
        return date_str

def get_agi_info():
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    if queue and 'agi_counter' in queue:
        counter = queue['agi_counter']
        days = counter.get('current_days', 0)
        base = counter.get('base_days', 1460)
        pct = int((1 - days/base) * 100) if base > 0 else 0
        return days, pct
    return 0, 0

def generate_agi_bar():
    days, pct = get_agi_info()
    return f'''
<section>
    <div class="agi-bar">
        <div class="agi-icon">⏰</div>
        <div class="agi-info">
            <div class="agi-label">ДО AGI: <strong>~{days} дней</strong></div>
            <div class="agi-track"><div class="agi-fill" style="width: {pct}%"></div></div>
        </div>
        <div class="agi-pct">{pct}%</div>
    </div>
</section>'''

def card_hero(post):
    title = post.get('title', 'Без названия')
    source = post.get('source', 'Unknown')
    date = format_date(post.get('date', post.get('added_at', '')))
    url = post.get('url', '#')
    summary = post.get('summary', '')
    return f'''
        <article class="hero-card hero-card-featured">
            <div class="card-body">
                <div class="card-meta">
                    <span class="card-source">{source}</span>
                    <span class="card-date">{date}</span>
                </div>
                <h2 class="card-title">{title}</h2>
                <p class="card-summary">{summary}</p>
                <a href="{url}" class="card-link" target="_blank" rel="noopener">Читать полностью →</a>
            </div>
        </article>'''

def card_regular(post, size='md'):
    title = post.get('title', 'Без названия')
    source = post.get('source', 'Unknown')
    date = format_date(post.get('date', post.get('added_at', '')))
    url = post.get('url', '#')
    summary = post.get('summary', '')
    title_class = 'card-title-sm'
    return f'''
        <article class="card">
            <div class="card-top">
                <span class="card-source">{source}</span>
                <span class="card-date">{date}</span>
            </div>
            <h3 class="{title_class}">{title}</h3>
            <p class="card-summary-sm">{summary}</p>
            <a href="{url}" class="card-link" target="_blank" rel="noopener">Подробнее →</a>
        </article>'''

def generate_lenta():
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    posts = queue.get('pending', []) if queue else []

    if not posts:
        content = '''
        <section>
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Постов пока нет</p>
            </div>
        </section>'''
    else:
        hero = card_hero(posts[0])
        cards = '\n'.join(card_regular(p, 'md') for p in posts[1:7])
        content = TEMPLATE_LENTA.format(
            hero=hero,
            cards=cards,
            total=len(posts),
            agi_bar=generate_agi_bar()
        )

    html = TEMPLATE_INDEX.format(
        content=content,
        title='AI Агенты Смита — Лента новостей',
        updated=datetime.now().strftime('%d.%m.%Y %H:%M')
    )
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Lenta: {len(posts) if posts else 0} постов")

def generate_articles():
    selection = load_json('../telegram-ai-channel/selection_queue.json')
    articles = selection.get('articles', []) if selection else []
    published = [a for a in articles if a.get('status') == 'published']

    if not published:
        content = '''
        <section>
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <p>Статей пока нет</p>
            </div>
        </section>'''
    else:
        hero = card_hero(published[0])
        cards = '\n'.join(card_regular(a, 'md') for a in published[1:])
        content = TEMPLATE_ARTICLES.format(
            hero=hero,
            cards=cards,
            total=len(published),
            agi_bar=generate_agi_bar()
        )

    html = TEMPLATE_INDEX.format(
        content=content,
        title='AI Агенты Смита — Статьи',
        updated=datetime.now().strftime('%d.%m.%Y %H:%M')
    )
    with open(OUTPUT_DIR / 'articles.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Articles: {len(published)} статей")

def generate_rss():
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    selection = load_json('../telegram-ai-channel/selection_queue.json')

    items = []
    if queue:
        for post in queue.get('pending', [])[:20]:
            items.append({
                'title': post.get('title', 'Без названия'),
                'link': post.get('url', '#'),
                'description': post.get('summary', ''),
                'pubDate': post.get('date', ''),
                'source': post.get('source', 'AI Агенты Смита')
            })
    if selection:
        for article in selection.get('articles', []):
            if article.get('status') == 'published':
                items.append({
                    'title': article.get('title', 'Без названия'),
                    'link': article.get('url', '#'),
                    'description': article.get('summary', ''),
                    'pubDate': article.get('date', ''),
                    'source': article.get('source', 'AI Агенты Смита')
                })

    items_xml = []
    for item in items:
        pub_date = ''
        if item['pubDate']:
            try:
                dt = datetime.fromisoformat(item['pubDate'].replace('Z', '+00:00'))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0300')
            except:
                pub_date = 'Thu, 01 Jan 2026 00:00:00 +0300'
        items_xml.append(f'''
        <item>
            <title>{item['title']}</title>
            <link>{item['link']}</link>
            <description><![CDATA[{item['description']}]]></description>
            <pubDate>{pub_date}</pubDate>
            <author>AI Агенты Смита</author>
        </item>''')

    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:yandex="http://news.yandex.ru">
    <channel>
        <title>AI Агенты Смита</title>
        <link>https://agentsmits.ru</link>
        <description>Новости и аналитика искусственного интеллекта</description>
        <language>ru</language>
        {''.join(items_xml)}
    </channel>
</rss>'''
    with open(OUTPUT_DIR / 'rss.xml', 'w', encoding='utf-8') as f:
        f.write(rss)
    print(f"✅ RSS: {len(items)} записей")

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    generate_lenta()
    generate_articles()
    generate_rss()
    print(f"🎉 Блог сгенерирован в {OUTPUT_DIR}")

if __name__ == '__main__':
    main()
