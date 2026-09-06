#!/usr/bin/env python3
"""
Storage Manager for AI Агенты Смита
- add_post: сохраняет опубликованный пост в current.json
- rotate: перемещает посты старше 7 дней в archive.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta

BOT_DIR = Path(__file__).parent.parent
DATA_DIR = BOT_DIR / "data"
CURRENT_FILE = DATA_DIR / "current.json"
ARCHIVE_FILE = DATA_DIR / "archive.json"

WEEK_START_MONDAY = True  # неделя начинается с понедельника


def get_week_start():
    today = datetime.now().date()
    days_since_monday = today.weekday()
    monday = today - timedelta(days=days_since_monday)
    return monday.isoformat()


def load_json(path):
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_files():
    """Инициализирует файлы если их нет"""
    DATA_DIR.mkdir(exist_ok=True)
    if not CURRENT_FILE.exists():
        save_json(CURRENT_FILE, {"week_start": get_week_start(), "posts": []})
    if not ARCHIVE_FILE.exists():
        save_json(ARCHIVE_FILE, {"archive": []})


def add_post(post_id, source, title, url, formatted_content, date=None,
              is_breakthrough=False, breakthrough_score=None, breakthrough_reasons=None):
    """
    Сохраняет опубликованный пост в current.json.
    formatted_content — полный отформатированный текст поста (с секциями).
    BT: is_breakthrough / breakthrough_score / breakthrough_reasons — флаги прорыва
        (используются для бейджа 🔥 ПРОРЫВ на сайте).
    """
    current = load_json(CURRENT_FILE) or {"week_start": get_week_start(), "posts": []}

    # Проверка week_start — если новая неделя, запускаем ротацию
    week_start = get_week_start()
    if current.get("week_start") != week_start:
        rotate()
        current = load_json(CURRENT_FILE) or {"week_start": week_start, "posts": []}

    # Не добавлять дубли
    existing_ids = [p['id'] for p in current.get('posts', [])]
    if post_id in existing_ids:
        print(f"Пост {post_id} уже в current.json")
        return

    post_entry = {
        "id": post_id,
        "source": source,
        "title": title,
        "url": url,
        "content": formatted_content,
        "published_at": date or datetime.now().isoformat(),
        "added_to_site_at": datetime.now().isoformat(),
    }
    # BT: добавляем breakthrough-флаги только если они есть
    if is_breakthrough:
        post_entry["is_breakthrough"] = True
    if breakthrough_score is not None:
        post_entry["breakthrough_score"] = breakthrough_score
    if breakthrough_reasons:
        post_entry["breakthrough_reasons"] = breakthrough_reasons

    current['posts'].insert(0, post_entry)
    save_json(CURRENT_FILE, current)
    print(f"✅ Пост '{title[:50]}' добавлен в current.json")


def rotate():
    """
    Перемещает посты старше 7 дней из current.json в archive.json.
    """
    current = load_json(CURRENT_FILE)
    if not current:
        return

    archive = load_json(ARCHIVE_FILE) or {"archive": []}

    cutoff = datetime.now() - timedelta(days=7)
    old_posts = []
    new_posts = []

    for post in current.get('posts', []):
        try:
            pub_date = datetime.fromisoformat(post['published_at'].replace('Z', '+00:00'))
            if pub_date < cutoff:
                old_posts.append(post)
            else:
                new_posts.append(post)
        except Exception:
            new_posts.append(post)

    if old_posts:
        archive['archive'] = old_posts + archive['archive']
        save_json(ARCHIVE_FILE, archive)
        print(f"📦 {len(old_posts)} постов перемещено в archive.json")

    current['posts'] = new_posts
    current['week_start'] = get_week_start()
    save_json(CURRENT_FILE, current)
    print(f"🔄 Ротация завершена. В current.json: {len(new_posts)} постов")


def get_posts():
    """Возвращает посты для сайта: current + архив"""
    current = load_json(CURRENT_FILE) or {"posts": []}
    archive = load_json(ARCHIVE_FILE) or {"archive": []}
    return {
        "current": current.get('posts', []),
        "archive": archive.get('archive', [])
    }


if __name__ == '__main__':
    init_files()

    if len(sys.argv) < 2:
        print("Usage: storage_manager.py [add|rotate|get]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'add' and len(sys.argv) >= 3:
        # add <post_json>
        post_data = json.loads(sys.argv[2])
        add_post(
            post_id=post_data['id'],
            source=post_data['source'],
            title=post_data['title'],
            url=post_data['url'],
            formatted_content=post_data.get('content', post_data.get('summary', '')),
            date=post_data.get('published_at'),
            is_breakthrough=bool(post_data.get('is_breakthrough')),
            breakthrough_score=post_data.get('breakthrough_score'),
            breakthrough_reasons=post_data.get('breakthrough_reasons'),
        )
    elif cmd == 'rotate':
        rotate()
    elif cmd == 'get':
        posts = get_posts()
        print(json.dumps(posts, ensure_ascii=False, indent=2))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
