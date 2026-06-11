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
    <title>AI Агенты Смита</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            background: #0a0a0f; 
            color: #e0e0e0; 
            font-family: 'Segoe UI', system-ui, sans-serif;
            line-height: 1.6;
        }}
        .container {{ max-width: 900px; margin: 0 auto; padding: 20px; }}
        header {{ 
            background: linear-gradient(135deg, #0d1117, #161b22);
            border-bottom: 1px solid #30363d;
            padding: 40px 0;
            text-align: center;
            margin-bottom: 40px;
        }}
        h1 {{ color: #58a6ff; font-size: 2.5em; margin-bottom: 10px; }}
        .subtitle {{ color: #8b949e; font-size: 1.1em; }}
        nav {{ 
            display: flex; 
            justify-content: center; 
            gap: 30px; 
            margin: 30px 0;
            border-bottom: 1px solid #30363d;
            padding-bottom: 20px;
        }}
        nav a {{ 
            color: #58a6ff; 
            text-decoration: none; 
            font-size: 1.1em;
            padding: 10px 20px;
            border-radius: 6px;
            transition: background 0.2s;
        }}
        nav a:hover, nav a.active {{ background: #21262d; }}
        .card {{ 
            background: #161b22; 
            border: 1px solid #30363d; 
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .card:hover {{ transform: translateY(-2px); border-color: #58a6ff; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .card-title {{ color: #f0f6fc; font-size: 1.4em; font-weight: 600; }}
        .card-date {{ color: #8b949e; font-size: 0.85em; }}
        .card-source {{ 
            background: #388bfd26; 
            color: #58a6ff; 
            padding: 4px 12px; 
            border-radius: 20px;
            font-size: 0.8em;
        }}
        .card-content {{ color: #c9d1d9; margin: 16px 0; }}
        .card-sections {{ margin-top: 16px; }}
        .section {{ margin-bottom: 12px; }}
        .section-title {{ color: #f78166; font-weight: 600; margin-bottom: 6px; }}
        .section-content {{ color: #c9d1d9; padding-left: 12px; border-left: 2px solid #30363d; }}
        .card-footer {{ margin-top: 20px; padding-top: 16px; border-top: 1px solid #30363d; }}
        .card-link {{ 
            color: #58a6ff; 
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .card-link:hover {{ text-decoration: underline; }}
        .agi-bar {{ 
            background: #21262d; 
            border-radius: 8px; 
            padding: 12px 16px;
            margin-top: 16px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .agi-label {{ color: #8b949e; font-size: 0.85em; }}
        .agi-progress {{ 
            flex: 1; 
            height: 8px; 
            background: #30363d; 
            border-radius: 4px;
            overflow: hidden;
        }}
        .agi-fill {{ height: 100%; background: linear-gradient(90deg, #238636, #2ea043); border-radius: 4px; }}
        .agi-percent {{ color: #2ea043; font-weight: 600; font-size: 0.85em; }}
        .footer {{ text-align: center; padding: 40px 0; color: #8b949e; font-size: 0.9em; }}
        @media (max-width: 600px) {{ 
            h1 {{ font-size: 1.8em; }}
            .container {{ padding: 15px; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="container">
            <h1>🤖 AI Агенты Смита</h1>
            <p class="subtitle">Новости и аналитика искусственного интеллекта</p>
            <nav>
                <a href="index.html" class="active">📰 Лента</a>
                <a href="articles.html">📖 Статьи</a>
                <a href="rss.xml">📡 RSS</a>
            </nav>
        </div>
    </header>
    <main class="container">
        {content}
    </main>
    <footer class="footer">
        <p>AI Агенты Смита • Обновлено {updated}</p>
    </footer>
</body>
</html>"""

def load_json(filename):
    # Try multiple paths for compatibility with CI
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
    """Преобразует дату в читаемый формат"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y')
    except:
        return date_str

def get_agi_info():
    """Получает данные AGI счётчика"""
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    if queue and 'agi_counter' in queue:
        counter = queue['agi_counter']
        days = counter.get('current_days', 0)
        base = counter.get('base_days', 1460)
        pct = int((1 - days/base) * 100) if base > 0 else 0
        return days, pct
    return 0, 0

def generate_agi_bar(days, percent):
    """Генерирует HTML AGI бара"""
    return f'''
    <div class="agi-bar">
        <span class="agi-label">⏰ ДО AGI: ~{days} дней</span>
        <div class="agi-progress">
            <div class="agi-fill" style="width: {percent}%"></div>
        </div>
        <span class="agi-percent">{percent}%</span>
    </div>'''

def card_html(post, is_article=False):
    """Генерирует HTML карточки поста"""
    title = post.get('title', 'Без названия')
    source = post.get('source', 'Unknown')
    date = format_date(post.get('date', post.get('added_at', '')))
    url = post.get('url', '#')
    summary = post.get('summary', '')
    days, pct = get_agi_info()
    
    content_sections = ''
    if is_article and summary:
        # Для статей — развёрнутый контент
        content_sections = f'<div class="card-sections">{summary}</div>'
    elif summary:
        content_sections = f'<div class="card-content">{summary}</div>'
    
    link_text = 'Читать полностью →' if is_article else 'Подробнее →'
    
    return f'''
    <article class="card">
        <div class="card-header">
            <h2 class="card-title">{title}</h2>
            <span class="card-date">{date}</span>
        </div>
        <span class="card-source">{source}</span>
        {content_sections}
        {generate_agi_bar(days, pct)}
        <div class="card-footer">
            <a href="{url}" class="card-link" target="_blank" rel="noopener">{link_text}</a>
        </div>
    </article>'''

def generate_lenta():
    """Генерирует страницу ленты"""
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    posts = queue.get('pending', []) if queue else []
    
    if not posts:
        content = '<p style="color: #8b949e; text-align: center;">Постов пока нет</p>'
    else:
        cards = [card_html(p) for p in posts]
        content = '\n'.join(cards)
    
    html = TEMPLATE_INDEX.format(content=content, updated=datetime.now().strftime('%d.%m.%Y %H:%M'))
    
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Lenta: {len(posts)} постов")

def generate_articles():
    """Генерирует страницу статей"""
    selection = load_json('../telegram-ai-channel/selection_queue.json')
    articles = selection.get('articles', []) if selection else []
    
    # Фильтруем только опубликованные (для глубокого анализа)
    published = [a for a in articles if a.get('status') == 'published']
    
    if not published:
        content = '<p style="color: #8b949e; text-align: center;">Статей пока нет</p>'
    else:
        cards = [card_html(a, is_article=True) for a in published]
        content = '\n'.join(cards)
    
    html = TEMPLATE_INDEX.format(content=content, updated=datetime.now().strftime('%d.%m.%Y %H:%M'))
    
    with open(OUTPUT_DIR / 'articles.html', 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ Articles: {len(published)} статей")

def generate_rss():
    """Генерирует RSS ленту для Яндекс Дзен"""
    queue = load_json('../telegram-ai-channel/pending_queue.json')
    selection = load_json('../telegram-ai-channel/selection_queue.json')
    
    items = []
    
    # Берём посты из pending
    if queue:
        for post in queue.get('pending', [])[:20]:
            items.append({
                'title': post.get('title', 'Без названия'),
                'link': post.get('url', '#'),
                'description': post.get('summary', ''),
                'pubDate': post.get('date', ''),
                'source': post.get('source', 'AI Агенты Смита')
            })
    
    # И статьи из selection
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