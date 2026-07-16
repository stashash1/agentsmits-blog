#!/usr/bin/env python3
"""
Публикатор статей/дайджестов в Telegram.
Публикует статьи из articles_queue.json.
"""
import json
import os
import sys
import subprocess
import re
import fcntl
import shutil
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from metrics import log_event, log_published

TELEGRAM_QUEUE = Path(__file__).parent.parent / "articles_queue.json"
BLOG_DIR = Path("/home/stas/.openclaw/workspace/projects/ai-blog")

SCRIPT_NAME = "publish_article"


def load_articles():
    with open(TELEGRAM_QUEUE) as f:
        return json.load(f)


def save_articles(d):
    with open(TELEGRAM_QUEUE, "w") as f:
        json.dump(d, f, indent=2, ensure_ascii=False)


def send_telegram(text, retries=3, delay=5):
    cmd = [
        "openclaw", "message", "send",
        "--channel", "telegram",
        "--account", "agentsmits",
        "--target", "@agentsSmits",
        "--message", text
    ]
    for attempt in range(retries):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                match = re.search(r"Message ID:\s*(\d+)", result.stdout)
                if match:
                    return int(match.group(1))
                if "Sent via telegram" in result.stdout:
                    return 0
            if result.returncode != 0 and "Sent via telegram" in result.stdout:
                match = re.search(r"Message ID:\s*(\d+)", result.stdout)
                return int(match.group(1)) if match else 0
        except subprocess.TimeoutExpired:
            print(f"Timeout on attempt {attempt+1}/{retries}", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
        if attempt < retries - 1:
            import time
            time.sleep(delay)
    return None


def sync_to_blog():
    """Синхронизирует articles_queue.json в блог и запускает деплой."""
    blog_dir = Path("/home/stas/.openclaw/workspace/projects/ai-blog")
    tg_dir = Path(__file__).parent.parent

    # Копируем queues
    for fname in ["pending_queue.json", "selection_queue.json", "articles_queue.json"]:
        src = tg_dir / fname
        dst = blog_dir / fname
        if src.exists():
            shutil.copy2(src, dst)

    result = subprocess.run(
        ["bash", str(blog_dir / "sync_and_deploy.sh")],
        capture_output=True, text=True, timeout=300
    )
    return result.returncode, result.stdout, result.stderr


def format_article(article, agi_days, agi_percent):
    months_ru = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    days_ru = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]

    date_str = article.get("date", "")
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            date_fmt = f"{days_ru[dt.weekday()]}, {dt.day} {months_ru[dt.month]} {dt.year} г."
        except:
            now = datetime.now(timezone.utc)
            date_fmt = f"{days_ru[now.weekday()]}, {now.day} {months_ru[now.month]} {now.year} г."
    else:
        now = datetime.now(timezone.utc)
        date_fmt = f"{days_ru[now.weekday()]}, {now.day} {months_ru[now.month]} {now.year} г."

    emoji = "📖" if article.get("type") == "article" else "📊"
    title = article.get("title", "Без названия")
    content = article.get("content", "")

    return f"""{emoji} Статья — Агенты Смита
{date_fmt}

📌 {title}

{content}

⏰ ДО AGI: ~{agi_days} дней [░░░░░░░░░░] ~{agi_percent}%

🚀 Полетели.
→ https://stashash1.github.io/agentsmits-blog"""


def main():
    run_ts = datetime.now(timezone.utc).isoformat()
    log_event(SCRIPT_NAME, "started", {"run_ts": run_ts})

    lock_path = str(TELEGRAM_QUEUE) + ".lock"
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Already running, exiting.")
        log_event(SCRIPT_NAME, "skipped", {"reason": "already_running"})
        return

    try:
        data = load_articles()
        articles = data.get("articles", [])
        published_ids = {a["id"] for a in articles if a.get("status") == "published"}

        # Только draft
        to_publish = [a for a in articles if a.get("status") == "draft"]

        if not to_publish:
            print("No articles to publish.")
            log_event(SCRIPT_NAME, "completed", {"reason": "nothing_to_publish", "run_ts": run_ts})
            return

        # AGI counter
        q = json.load(open(Path(__file__).parent.parent / "pending_queue.json"))
        agi = q.get("agi_counter", {})
        base_days = agi.get("base_days", 1460)
        start_date = agi.get("start_date", "2026-01-01")
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            now_dt = datetime.now()
            elapsed = (now_dt - start_dt).days
            agi_days = max(0, base_days - elapsed)
            agi_percent = max(2, min(98, round(elapsed / base_days * 100)))
        except:
            agi_days = agi.get("current_days", base_days)
            agi_percent = max(2, min(98, round((base_days - agi_days) / base_days * 100)))

        published_count = 0
        for article in to_publish:
            text = format_article(article, agi_days, agi_percent)
            msg_id = send_telegram(text)

            if msg_id:
                article["status"] = "published"
                article["published_at"] = datetime.now(timezone.utc).isoformat()
                article["message_id"] = msg_id
                published_count += 1
                print(f"Published: {article['id']} -> msg #{msg_id}")
                log_published(article["id"], article.get("source", ""), article.get("title", ""), msg_id, 5)
            else:
                print(f"Failed: {article['id']}")

        if published_count > 0:
            save_articles(data)
            rc, out, err = sync_to_blog()
            if rc == 0:
                print("🌐 Blog synced & deployed.")
            else:
                print(f"⚠️ Blog sync failed: {err[-200:]}")

        print(f"Done. {published_count} articles published.")
        log_event(SCRIPT_NAME, "completed", {
            "run_ts": run_ts,
            "published": published_count,
            "pending": len([a for a in data["articles"] if a.get("status") == "draft"])
        })

    except Exception as e:
        log_error(SCRIPT_NAME, str(e), {"run_ts": run_ts})
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            try:
                os.unlink(lock_path)
            except:
                pass


if __name__ == "__main__":
    main()
