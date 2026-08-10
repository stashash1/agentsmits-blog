#!/usr/bin/env python3
"""
Ежедневный итог для Telegram-канала "Агенты Смита".
Собирает все опубликованные за день статьи, генерирует LLM-анализ,
публикует в Telegram.
Все операции логируются в центральную систему метрик.
"""
from _config import DAILY_SUMMARIES, PENDING_QUEUE

import json
import os
import sys
import subprocess
import re
import fcntl
import time
from datetime import datetime, timezone
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(__file__))
from metrics import log_event, log_error, is_quiet_hours, was_recently_sent, record_sent
from narrative_store import load_narratives  # Stage 2: группировка по narratives


SCRIPT_NAME = "daily_summary"

SUMMARY_PROMPT_TEMPLATE = """Ты — главный редактор Telegram-канала "Агенты Смита" (об AI-агентах и автономных системах).

Сегодня {date} — твой день. Тебе нужно написать один сильный итоговый пост.

СТРУКТУРА ПОСТА:
1. Заголовок-тезис (одно предложение — главный вывод дня)
2. Цифры дня (сколько статей, от каких источников)
3. ГЛАВНЫЕ НАРРАТИВЫ ДНЯ — структура (заголовок нарратива, что объединяет, ключевые факты). Это самая важная часть. Если есть нарратив с 3+ событиями — он заслуживает отдельного абзаца.
4. Что это значит для нас (конкретно, не абстрактно)
5. Риск или возможность (один конкретный)
6. Одна мысль, которую стоит запомнить

ПРАВИЛА:
- Пиши на русском, живым языком
- Будь direct — говори что думаешь, а не "возможно, вероятно"
- Цифры важны — если 14 статей от OpenAI, напиши об этом
- НАРРАТИВЫ важнее списка отдельных статей — если 5 событий одного сюжета, не делай 5 пунктов, делай один сюжет
- Связывай с агент-темой: как это влияет на разработку, внедрение, рынок агентов
- Не используй markdown-разметку (никаких *, #, >)
- Тон: уверенный, аналитичный, с характером

ИСХОДНЫЕ ДАННЫЕ ЗА ДЕНЬ:

Статей опубликовано: {total}
Источники: {sources}

{articles}

Напиши пост."""

def load_queue():
    with open(PENDING_QUEUE) as f:
        return json.load(f)

def get_today_articles(queue):
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    published = queue.get('published', [])
    today_posts = [p for p in published if p.get('published_at', '').startswith(today)]
    today_posts.sort(key=lambda x: x.get('published_at', ''))
    return today_posts

def build_articles_text(posts):
    """Stage 2 (quality-news-analyst, 2026-08-10): группируем по narratives.
    Сначала multi-item narratives (с заголовком), потом — singletons.
    """
    narr_data = load_narratives()
    narratives_by_id = {n['id']: n for n in narr_data.get('narratives', [])}

    # Группируем posts по narrative_id
    grouped: dict[str | None, list[dict]] = defaultdict(list)
    for p in posts:
        nid = p.get('narrative_id')
        grouped[nid].append(p)

    lines = []
    article_idx = 0

    # Сначала — нарративы с size ≥ 2 (multi-item stories)
    multi_narratives = sorted(
        [n for n in narr_data.get('narratives', [])
         if n['id'] in grouped and len(grouped[n['id']]) >= 2],
        key=lambda n: -len(grouped[n['id']]),
    )
    for n in multi_narratives:
        narr_posts = grouped[n['id']]
        article_idx += 1
        lines.append(f"=== НАРРАТИВ #{article_idx}: {n.get('title','')[:80]} ===")
        lines.append(f"Связанные entities: {', '.join(n.get('entities', [])[:8])}")
        lines.append(f"Событий: {len(narr_posts)}")
        lines.append("")
        for sub_i, p in enumerate(narr_posts, 1):
            title = p.get('title', 'Без названия')
            source = p.get('source', 'Unknown')
            url = p.get('url', '')
            analysis = p.get('analysis', {})
            summary = analysis.get('summary', p.get('summary', ''))
            lines.append(f"  {sub_i}. [{source}] {title}")
            if summary:
                lines.append(f"     {summary[:200]}")
            lines.append(f"     {url}")
        lines.append("")

    # Потом — singletons
    singletons = grouped.get(None, [])
    if singletons:
        lines.append("=== ОТДЕЛЬНЫЕ СОБЫТИЯ ===")
        for p in singletons:
            article_idx += 1
            title = p.get('title', 'Без названия')
            source = p.get('source', 'Unknown')
            url = p.get('url', '')
            analysis = p.get('analysis', {})
            summary = analysis.get('summary', p.get('summary', ''))
            agent_impact = analysis.get('agent_impact', '')
            business_impact = analysis.get('business_impact', '')
            lines.append(f"--- {article_idx}. {source} ---")
            lines.append(f"Заголовок: {title}")
            if summary:
                lines.append(f"Кратко: {summary}")
            if agent_impact:
                lines.append(f"Влияние на агентов: {agent_impact}")
            if business_impact:
                lines.append(f"Влияние на бизнес: {business_impact}")
            lines.append(f"URL: {url}")
            lines.append("")

    # Если narratives.json нет вообще — fallback на плоский список (старый код)
    if not narr_data.get('narratives') and not singletons:
        lines.append("(legacy: narratives.json не заполнен, плоский вывод)")
        for i, p in enumerate(posts, 1):
            title = p.get('title', 'Без названия')
            source = p.get('source', 'Unknown')
            url = p.get('url', '')
            analysis = p.get('analysis', {})
            summary = analysis.get('summary', p.get('summary', ''))
            agent_impact = analysis.get('agent_impact', '')
            business_impact = analysis.get('business_impact', '')
            it_impact = analysis.get('it_impact', '')
            lines.append(f"--- {i}. {source} ---")
            lines.append(f"Заголовок: {title}")
            if summary:
                lines.append(f"Кратко: {summary}")
            if agent_impact:
                lines.append(f"Влияние на агентов: {agent_impact}")
            if business_impact:
                lines.append(f"Влияние на бизнес: {business_impact}")
            if it_impact:
                lines.append(f"Влияние на IT: {it_impact}")
            lines.append(f"URL: {url}")
            lines.append("")

    return "\n".join(lines)

def call_llm(prompt, timeout=90):
    cmd = ['openclaw', 'infer', 'model', 'run', '--prompt', prompt, '--json']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if result.returncode == 0:
            return result.stdout
    except subprocess.TimeoutExpired:
        print(f"LLM timeout", file=sys.stderr)
    except Exception as e:
        print(f"LLM error: {e}", file=sys.stderr)
    return None

def send_telegram(text, retries=3, delay=8):
    """Send via openclaw CLI. Returns message_id or None.

    - Skips send during quiet hours (returns -1 sentinel).
    - Tracks sent messages via was_recently_sent / record_sent to avoid
      duplicate sends after a gateway timeout.
    """
    if is_quiet_hours():
        print("🌙 Quiet hours: daily summary send skipped")
        return -1

    prev = was_recently_sent(text, within_seconds=600)
    if prev is not False and prev is not True:
        print(f"Recent daily-summary duplicate detected (prev msg_id={prev}); skipping")
        return prev if isinstance(prev, int) else 0
    elif prev is True:
        print("Recent daily-summary duplicate detected; skipping")
        return 0

    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--account', 'agentsmits',
        '--target', '@agentsSmits',
        '--message', text
    ]
    for attempt in range(retries):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                match = re.search(r'Message ID:\s*(\d+)', result.stdout)
                if match:
                    mid = int(match.group(1))
                    record_sent(text, mid)
                    return mid
                if 'Sent via telegram' in result.stdout:
                    record_sent(text, 0)
                    return 0
            if result.returncode != 0 and 'Sent via telegram' in result.stdout:
                match = re.search(r'Message ID:\s*(\d+)', result.stdout)
                if match:
                    mid = int(match.group(1))
                    record_sent(text, mid)
                    return mid
                record_sent(text, 0)
                return 0
        except subprocess.TimeoutExpired:
            print(f"Timeout on attempt {attempt+1}, retrying...", file=sys.stderr)
            time.sleep(delay)
        except Exception as e:
            print(f"Telegram error: {e}", file=sys.stderr)
    return None

def main():
    run_ts = datetime.now(timezone.utc).isoformat()
    log_event(SCRIPT_NAME, "started", {"run_ts": run_ts})
    
    lock_path = str(PENDING_QUEUE) + '.daily_lock'
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Daily summary already running, exiting.")
        log_event(SCRIPT_NAME, "skipped", {"reason": "already_running"})
        return
    
    try:
        queue = load_queue()
        today_posts = get_today_articles(queue)
        
        if not today_posts:
            print("No articles published today. Skipping summary.")
            log_event(SCRIPT_NAME, "completed", {
                "run_ts": run_ts,
                "articles_count": 0,
                "status": "skipped_no_articles"
            })
            return
        
        date_str = datetime.now(timezone.utc).strftime('%d.%m.%Y')
        total = len(today_posts)
        
        # Stats
        sources = Counter(p['source'] for p in today_posts)
        sources_str = ", ".join([f"{k} ({v})" for k, v in sources.most_common()])
        
        # Build articles text
        articles_text = build_articles_text(today_posts)
        
        # Build prompt
        prompt = SUMMARY_PROMPT_TEMPLATE.format(
            date=date_str,
            total=total,
            sources=sources_str,
            articles=articles_text
        )
        
        print(f"Generating daily summary for {date_str} ({total} articles)...")
        log_event(SCRIPT_NAME, "llm_called", {
            "run_ts": run_ts,
            "articles_count": total,
            "sources": dict(sources)
        })
        
        # Call LLM
        raw_output = call_llm(prompt)
        
        if raw_output:
            try:
                data = json.loads(raw_output)
                if 'outputs' in data:
                    summary_text = data['outputs'][0]['text']
                else:
                    summary_text = str(data)
            except:
                summary_text = raw_output
            
            # Clean any markdown
            summary_text = re.sub(r'\*\*(.*?)\*\*', r'\1', summary_text)
            summary_text = re.sub(r'\*(.*?)\*', r'\1', summary_text)
            summary_text = re.sub(r'## (.*)', r'\1', summary_text)
            summary_text = re.sub(r'# (.*)', r'\1', summary_text)
            
            log_event(SCRIPT_NAME, "llm_generated", {
                "run_ts": run_ts,
                "summary_length": len(summary_text)
            })
        else:
            summary_text = f"Ошибка генерации. {total} статей за день, источники: {sources_str}"
            log_error(SCRIPT_NAME, "LLM returned no output", {
                "run_ts": run_ts,
                "articles_count": total
            })
        
        # Add header — Russian date
        months_ru = ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
        days_ru = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
        now = datetime.now(timezone.utc)
        date_display = f"{days_ru[now.weekday()]}, {now.day} {months_ru[now.month]} {now.year} г."
        header = f"🤖 Итог дня — {date_display}\n\n"
        
        final_text = header + summary_text
        
        # Send to Telegram
        msg_id = send_telegram(final_text)
        if msg_id == -1:
            # Quiet hours: don't send, but still save the summary text
            # locally so the morning run / human review can use it.
            print("🌙 Quiet hours: Telegram send skipped; summary saved locally only.")
            log_event(SCRIPT_NAME, "quiet_hours", {
                "run_ts": run_ts,
                "articles_count": total,
                "sources": dict(sources),
                "summary_length": len(final_text)
            })
        elif msg_id:
            print(f"Daily summary sent: msg #{msg_id}")
            log_event(SCRIPT_NAME, "sent", {
                "run_ts": run_ts,
                "msg_id": msg_id,
                "articles_count": total,
                "sources": dict(sources)
            })
        else:
            print(f"Daily summary (no Telegram send):")
            print(final_text)
            log_error(SCRIPT_NAME, "send_telegram returned None", {
                "run_ts": run_ts,
                "msg_id": msg_id
            })
        
        # Also save to file
        summaries = []
        try:
            with open(DAILY_SUMMARIES) as f:
                summaries = json.load(f)
        except:
            pass
        
        summaries.insert(0, {
            'date': date_str,
            'text': final_text,
            'articles_count': total,
            'sources': dict(sources),
            'message_id': msg_id,
            'run_ts': run_ts
        })
        
        # Keep last 30 summaries
        summaries = summaries[:30]
        
        with open(DAILY_SUMMARIES, 'w') as f:
            json.dump(summaries, f, indent=2, ensure_ascii=False)
        
        log_event(SCRIPT_NAME, "completed", {
            "run_ts": run_ts,
            "msg_id": msg_id,
            "articles_count": total,
            "sources": dict(sources),
            "sources_count": len(sources),
            "status": "success"
        })
        
        print(f"Summary saved. {total} articles, {len(sources)} sources.")
    
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

if __name__ == '__main__':
    main()
