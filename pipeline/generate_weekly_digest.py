from _config import ARTICLES_QUEUE, PENDING_QUEUE
#!/usr/bin/env python3
"""
Генератор еженедельного дайджеста AI-новостей.
Формат: заголовок-тезис + главные события + тренд + риск/возможность + мысль недели.
БЕЗ подсчёта новостей по компаниям.
Запуск: вручную или по cron (вс вечером / пн утро).
"""
import json
import os
import sys
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from metrics import log_event

PENDING_QUEUE   = Path(__file__).parent.parent / "pending_queue.json"
ARTICLES_QUEUE = Path(__file__).parent.parent / "articles_queue.json"
WEEKLY_TEMPLATE = """Ты — главный редактор Telegram-канала "Агенты Смита" (об AI-агентах и автономных системах).

Напиши итоговый дайджест за {week_num}-ю неделю июня 2026.

СТРУКТУРА:
1. Заголовок-тезис (одно предложение — главный вывод недели)
2. Главные события (3-5 штук, каждое 2-3 предложения — ЧТО произошло и ПОЧЕМУ это важно для AI-агентов)
3. Тренд недели (куда движется отрасль)
4. Риск и возможность (один конкретный)
5. Мысль недели (одна фраза)

ПРАВИЛА:
- Пиши на русском, живо, с характером
- Будь direct: говори что думаешь
- Фокус на AI-агентах: разработка, внедрение, рынок автономных систем
- Без markdown-разметки
- 400-700 символов всего
- НЕ считай новости по компаниям — пиши о событиях и трендах

КЛЮЧЕВЫЕ СОБЫТИЯ НЕДЕЛИ:
{articles_text}

Напиши дайджест."""


def get_week_articles():
    """Берёт посты за последние 7 дней."""
    with open(PENDING_QUEUE) as f:
        queue = json.load(f)

    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    week_posts = []
    for p in queue.get("published", []):
        try:
            pub_at = datetime.fromisoformat(p["published_at"].replace("Z", "+00:00"))
            if pub_at >= week_ago:
                week_posts.append(p)
        except:
            pass

    week_posts.sort(key=lambda x: -x.get("importance", 4))
    return week_posts[:25]


def build_articles_text(posts):
    lines = []
    for i, p in enumerate(posts, 1):
        a = p.get("analysis", {})
        title = a.get("translated_title") or p.get("title", "")
        source = p.get("source", "")
        date = p.get("date", "")
        agent = a.get("agent_impact", "")[:200]
        lines.append(f"{i}. [{date}] {source}: {title}")
        if agent:
            lines.append(f"   -> {agent}")
    return "\n".join(lines)


def call_llm(prompt, timeout=120):
    result = subprocess.run(
        ["openclaw", "infer", "model", "run", "--prompt", prompt],
        capture_output=True, text=True, timeout=timeout
    )
    if result.returncode == 0:
        return result.stdout
    return None


def main():
    now = datetime.now(timezone.utc)
    week_num = now.isocalendar()[1]

    week_posts = get_week_articles()
    if not week_posts:
        print("Нет постов за неделю.")
        log_event("weekly_digest", "no_posts", {})
        return

    print(f"Найдено {len(week_posts)} постов за неделю")

    articles_text = build_articles_text(week_posts)
    prompt = WEEKLY_TEMPLATE.format(week_num=week_num, articles_text=articles_text)

    print("Генерация дайджеста через LLM...")
    raw = call_llm(prompt)

    if raw:
        try:
            data = json.loads(raw)
            digest_text = data.get("outputs", [{}])[0].get("text", "") if isinstance(data, dict) else str(data)
        except:
            digest_text = raw
        # Clean markdown
        import re
        digest_text = re.sub(r'\*\*(.*?)\*\*', r'\1', digest_text)
        digest_text = re.sub(r'\*(.*?)\*', r'\1', digest_text)
    else:
        digest_text = "Ошибка генерации дайджеста."
        log_event("weekly_digest", "llm_failed", {})

    article_id = f"weekly-digest-{now.strftime('%Y-W%W')}"

    article = {
        "id": article_id,
        "type": "weekly_digest",
        "title": f"📊 Еженедельный дайджест — неделя {week_num}",
        "content": digest_text,
        "source": "AI Агенты Смита",
        "date": now.strftime("%Y-%m-%d"),
        "published_at": now.isoformat(),
        "week_posts_count": len(week_posts),
        "status": "draft"
    }

    with open(ARTICLES_QUEUE) as f:
        data = json.load(f)

    # Не создавать дубликат
    existing = [a for a in data.get("articles", []) if a.get("id") == article_id]
    if existing:
        print(f"Дайджест за неделю {week_num} уже существует.")
        return

    data["articles"].insert(0, article)
    with open(ARTICLES_QUEUE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Дайджест создан: {article_id}")
    print(f"   Статей в очереди: {len(data['articles'])}")
    log_event("weekly_digest", "created", {"article_id": article_id, "posts": len(week_posts)})


if __name__ == "__main__":
    main()
