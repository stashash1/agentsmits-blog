#!/usr/bin/env python3
"""
Генератор блога AI Агенты Смита
- Читает из storage: data/current.json (актуальные посты) + data/archive.json (архив)
- Генерирует: public/index.html (лента + архив), public/articles.html, public/rss.xml
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

BLOG_DIR = Path(__file__).parent
OUTPUT_DIR = BLOG_DIR / "public"
DATA_DIR = BLOG_DIR / "data"
STORAGE_CURRENT = DATA_DIR / "current.json"
STORAGE_ARCHIVE = DATA_DIR / "archive.json"

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

        .telegram-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 16px;
            background: #229ED9;
            color: #fff;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 600;
            margin-left: 8px;
            transition: all 0.2s;
        }}
        .telegram-btn:hover {{ background: #1B8AB9; color: #fff; transform: translateY(-1px); }}

        /* ── Page shell ── */
        .page-wrapper {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 24px;
        }}

        /* ── Section ── */
        .section {{
            padding: 48px 0;
            border-bottom: 1px solid var(--border);
        }}

        .section:last-child {{ border-bottom: none; }}

        .section-label {{
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.15em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}

        .section-label::before {{
            content: '';
            display: block;
            width: 32px;
            height: 2px;
            background: var(--accent);
        }}

        /* ── Subscribe banner ── */
        .subscribe-banner {{
            background: linear-gradient(135deg, #229ED9 0%, #1B8AB9 100%);
            border-radius: 16px;
            padding: 28px 32px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            margin: 32px 0 48px;
            flex-wrap: wrap;
        }}
        .subscribe-banner-text {{
            color: #fff;
        }}
        .subscribe-banner-title {{
            font-family: var(--font-serif);
            font-size: 1.3rem;
            font-weight: 700;
            margin-bottom: 4px;
        }}
        .subscribe-banner-sub {{
            font-size: 0.88rem;
            opacity: 0.85;
        }}
        .subscribe-banner-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: #fff;
            color: #229ED9;
            padding: 12px 24px;
            border-radius: 10px;
            font-weight: 700;
            font-size: 0.95rem;
            transition: all 0.2s;
            white-space: nowrap;
        }}
        .subscribe-banner-btn:hover {{
            background: #f0f8ff;
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.2);
        }}

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

        /* ── Hero card ── */
        .hero-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 32px;
            display: flex;
            flex-direction: column;
            gap: 16px;
            transition: all 0.3s;
        }}

        .hero-card:hover {{
            border-color: var(--border-light);
            transform: translateY(-2px);
        }}

        .hero-card + .hero-card {{ margin-top: 16px; }}

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
            display: inline-block;
        }}

        .card-title {{
            font-family: var(--font-serif);
            font-size: 1.5rem;
            font-weight: 700;
            line-height: 1.3;
            color: var(--text-primary);
        }}

        .card-date {{
            font-size: 0.78rem;
            color: var(--text-muted);
        }}

        /* ── Formatted content (from Telegram template) ── */
        .post-content {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .post-content pre {{
            font-family: var(--font-sans);
            font-size: 0.92rem;
            line-height: 1.7;
            color: var(--text-secondary);
            white-space: pre-wrap;
            word-break: break-word;
        }}

        .post-section {{
            padding: 12px 16px;
            background: var(--bg-card-hover);
            border-left: 3px solid var(--accent);
            border-radius: 0 8px 8px 0;
        }}

        .post-section-label {{
            font-family: var(--font-mono);
            font-size: 0.72rem;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: var(--accent);
            margin-bottom: 6px;
        }}

        .post-section-content {{
            font-size: 0.9rem;
            color: var(--text-secondary);
            line-height: 1.65;
        }}

        .post-total {{
            background: rgba(232,160,68,0.08);
            border: 1px solid rgba(232,160,68,0.2);
            border-radius: 8px;
            padding: 12px 16px;
            font-size: 0.9rem;
            color: var(--text-primary);
        }}

        .post-footer {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-wrap: wrap;
            gap: 12px;
            padding-top: 12px;
            border-top: 1px solid var(--border);
        }}

        .card-link {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--accent-blue);
            transition: gap 0.2s;
        }}

        .card-link:hover {{ gap: 10px; color: var(--accent-blue); }}

        /* ── AGI Bar ── */
        .agi-bar {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px 20px;
            display: flex;
            align-items: center;
            gap: 16px;
            margin: 48px 0;
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
        }}

        .agi-pct {{
            font-family: var(--font-mono);
            font-size: 0.85rem;
            font-weight: 500;
            color: var(--accent-green);
        }}

        /* ── Archive section ── */
        .archive-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
        }}

        .archive-card {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.25s;
        }}

        .archive-card:hover {{
            border-color: var(--border-light);
            background: var(--bg-card-hover);
        }}

        .archive-card-title {{
            font-family: var(--font-serif);
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
            line-height: 1.35;
        }}

        .archive-card-meta {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
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
            padding: 60px 0;
            color: var(--text-muted);
        }}

        .empty-state-icon {{ font-size: 2.5rem; margin-bottom: 12px; opacity: 0.3; }}

        /* ── Responsive ── */
        @media (max-width: 900px) {{
            .archive-grid {{ grid-template-columns: 1fr; }}
        }}

        @media (max-width: 600px) {{
            .header-inner {{ height: 60px; }}
            .logo-sub {{ display: none; }}
            .main-nav {{ gap: 0; }}
            .nav-link {{ padding: 6px 12px; font-size: 0.82rem; }}
            .card-title {{ font-size: 1.2rem; }}
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
                <a href="https://t.me/agentsSmits" class="telegram-btn" target="_blank" rel="noopener">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
                    Telegram
                </a>
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

TEMPLATE_SECTION_CURRENT = """
<section class="section">
    <div class="section-label">Эта неделя</div>
    <div class="section-header">
        <h2 class="section-title">Актуальные новости</h2>
        <span class="section-count">{count} публикаций</span>
    </div>
    {posts}
</section>"""

SUBSCRIBE_BANNER = """
<div class="subscribe-banner">
    <div class="subscribe-banner-text">
        <div class="subscribe-banner-title">📢 Подпишись на канал Агенты Смита</div>
        <div class="subscribe-banner-sub">Ежедневные новости и аналитика AI в Telegram</div>
    </div>
    <a href="https://t.me/agentsSmits" class="subscribe-banner-btn" target="_blank" rel="noopener">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z"/></svg>
        @agentsSmits
    </a>
</div>"""

TEMPLATE_SECTION_ARCHIVE = """
<section class="section">
    <div class="section-label">Архив</div>
    <div class="section-header">
        <h2 class="section-title">Статьи прошлых недель</h2>
        <span class="section-count">{count} статей</span>
    </div>
    <div class="archive-grid">
        {cards}
    </div>
</section>"""

TEMPLATE_ARCHIVE_CARD = """
<article class="archive-card">
    <div class="archive-card-title">{title}</div>
    <div class="archive-card-meta">
        <span class="card-source">{source}</span>
        <span class="card-date">{date}</span>
    </div>
    <a href="{url}" class="card-link" target="_blank" rel="noopener" style="margin-top:10px; display:inline-flex;">Читать →</a>
</article>"""


def load_json(path):
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


def parse_formatted_content(content):
    """
    Парсит отформатированный контент поста (текст из Telegram-шаблона)
    и возвращает HTML-секции.
    """
    if not content:
        return ""

    # Экранируем HTML
    def esc(s):
        return str(s).replace('&', '&').replace('<', '<').replace('>', '>')

    lines = content.split('\n')
    html_parts = []
    current_section = None
    section_buffer = []

    def flush_section():
        nonlocal current_section, section_buffer
        if current_section and section_buffer:
            label = current_section.replace('📊', '').replace('💼', '').replace('🖥', '').strip()
            content_text = ' '.join(section_buffer).strip()
            if content_text:
                html_parts.append(
                    f'<div class="post-section">'
                    f'<div class="post-section-label">{esc(label)}</div>'
                    f'<div class="post-section-content">{esc(content_text)}</div>'
                    f'</div>'
                )
        current_section = None
        section_buffer = []

    for line in lines:
        line = line.rstrip()
        if not line:
            continue

        # Секции начинаются с эмодзи + текст
        section_match = re.match(r'^([📊💼🖥📔✅⏰🚀👉🔗📰]+)\s*(.+)', line)
        if section_match and any(c in line for c in ['📊', '💼', '🖥', '📔', '✅']):
            flush_section()
            current_section = section_match.group(1).strip() + ' ' + section_match.group(2).strip()
            continue

        if current_section:
            section_buffer.append(line)
        else:
            # Свободный текст — итого, вводная часть
            if any(kw in line for kw in ['Итого', 'Итого:', 'Полетели', '🚀']):
                html_parts.append(f'<div class="post-total">{esc(line)}</div>')
            elif line.startswith('🤖') or line.startswith('📰') or line.startswith('🔗'):
                continue  # пропускаем шапку
            else:
                html_parts.append(f'<pre>{esc(line)}</pre>')

    flush_section()
    return '\n'.join(html_parts)


def format_post_card(post):
    """Формирует HTML-карточку поста с отформатированным контентом"""
    title = post.get('title', 'Без названия')
    source = post.get('source', 'Unknown')
    url = post.get('url', '#')
    date = format_date(post.get('published_at', post.get('added_at', '')))
    content = post.get('content', post.get('summary', ''))

    content_html = parse_formatted_content(content)

    return f'''
    <article class="hero-card">
        <div>
            <span class="card-source">{source}</span>
            <span class="card-date" style="margin-left:10px">{date}</span>
        </div>
        <h2 class="card-title">{title}</h2>
        <div class="post-content">
            {content_html}
        </div>
        <div class="post-footer">
            <a href="{url}" class="card-link" target="_blank" rel="noopener">Источник →</a>
        </div>
    </article>'''


def format_archive_card(post):
    """Карточка архива — компактная"""
    title = post.get('title', 'Без названия')
    source = post.get('source', 'Unknown')
    url = post.get('url', '#')
    date = format_date(post.get('published_at', ''))
    return TEMPLATE_ARCHIVE_CARD.format(
        title=title, source=source, url=url, date=date
    )


def get_agi_info():
    """Читает AGI-счётчик из pending_queue.json"""
    queue_path = Path('/home/stas/.openclaw/workspace/projects/telegram-ai-channel/pending_queue.json')
    queue = load_json(queue_path)
    if queue and 'agi_counter' in queue:
        counter = queue['agi_counter']
        days = counter.get('current_days', 0)
        base = counter.get('base_days', 1460)
        pct = int((1 - days / base) * 100) if base > 0 else 0
        return days, pct
    return 0, 0


def generate_agi_bar():
    days, pct = get_agi_info()
    return f'''
    <div class="agi-bar">
        <div class="agi-icon">⏰</div>
        <div class="agi-info">
            <div class="agi-label">ДО AGI: <strong>~{days} дней</strong></div>
            <div class="agi-track"><div class="agi-fill" style="width: {pct}%"></div></div>
        </div>
        <div class="agi-pct">{pct}%</div>
    </div>'''


def generate_lenta():
    """Генерирует главную страницу с актуальными постами и архивом"""
    current_data = load_json(STORAGE_CURRENT)
    archive_data = load_json(STORAGE_ARCHIVE)

    current_posts = current_data.get('posts', []) if current_data else []
    archive_posts = archive_data.get('archive', []) if archive_data else []

    # Актуальные посты
    if current_posts:
        posts_html = '\n'.join(format_post_card(p) for p in current_posts)
        current_section = TEMPLATE_SECTION_CURRENT.format(
            count=len(current_posts),
            posts=posts_html
        )
    else:
        current_section = '''
        <section class="section">
            <div class="section-label">Эта неделя</div>
            <div class="empty-state">
                <div class="empty-state-icon">📭</div>
                <p>Постов этой недели пока нет</p>
            </div>
        </section>'''

    # Архив
    if archive_posts:
        cards_html = '\n'.join(format_archive_card(p) for p in archive_posts)
        archive_section = TEMPLATE_SECTION_ARCHIVE.format(
            count=len(archive_posts),
            cards=cards_html
        )
    else:
        archive_section = ''

    content = SUBSCRIBE_BANNER + current_section + archive_section + generate_agi_bar()

    html = TEMPLATE_INDEX.format(
        content=content,
        title='AI Агенты Смита — Лента новостей',
        updated=datetime.now().strftime('%d.%m.%Y %H:%M')
    )
    with open(OUTPUT_DIR / 'index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Lenta: {len(current_posts)} актуальных, {len(archive_posts)} в архиве")


def generate_articles():
    """Генерирует страницу статей (только актуальные, без архива)"""
    current_data = load_json(STORAGE_CURRENT)
    posts = current_data.get('posts', []) if current_data else []

    if posts:
        posts_html = '\n'.join(format_post_card(p) for p in posts)
        content = TEMPLATE_SECTION_CURRENT.format(
            count=len(posts),
            posts=posts_html
        ) + generate_agi_bar()
    else:
        content = '''
        <section class="section">
            <div class="empty-state">
                <div class="empty-state-icon">📝</div>
                <p>Статей пока нет</p>
            </div>
        </section>'''

    html = TEMPLATE_INDEX.format(
        content=content,
        title='AI Агенты Смита — Статьи',
        updated=datetime.now().strftime('%d.%m.%Y %H:%M')
    )
    with open(OUTPUT_DIR / 'articles.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"✅ Articles: {len(posts)} статей")


def generate_rss():
    """Генерирует RSS из current.json"""
    current_data = load_json(STORAGE_CURRENT)
    posts = current_data.get('posts', []) if current_data else []

    items_xml = []
    for post in posts[:20]:
        pub_date = ''
        if post.get('published_at'):
            try:
                dt = datetime.fromisoformat(post['published_at'].replace('Z', '+00:00'))
                pub_date = dt.strftime('%a, %d %b %Y %H:%M:%S +0300')
            except:
                pub_date = 'Thu, 01 Jan 2026 00:00:00 +0300'

        items_xml.append(f'''
        <item>
            <title>{post.get('title', 'Без названия')}</title>
            <link>{post.get('url', '#')}</link>
            <description><![CDATA[{post.get('content', post.get('summary', ''))}]]></description>
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
    print(f"✅ RSS: {len(items_xml)} записей")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    generate_lenta()
    generate_articles()
    generate_rss()
    print(f"🎉 Блог сгенерирован в {OUTPUT_DIR}")

if __name__ == '__main__':
    main()
