#!/usr/bin/env python3
"""
Центральная система метрик и логирования для AI-канала.
Все скрипты логируют сюда — единая точка для отладки и мониторинга.
"""
import json
import os
import sys
import fcntl
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

METRICS_PATH = os.path.expanduser("~/.openclaw/workspace/projects/telegram-ai-channel/metrics.json")
LOG_PATH = os.path.expanduser("~/.openclaw/workspace/projects/telegram-ai-channel/events.log")
SENT_DEDUP_PATH = os.path.expanduser("~/.openclaw/workspace/projects/telegram-ai-channel/recently_sent.json")
TELEGRAM_AUDIT_PATH = os.path.expanduser("~/.openclaw/workspace/projects/telegram-ai-channel/telegram_audit.log")

# Quiet hours: don't publish new content to the channel during this window (Moscow time).
# Configurable via env: QUITE_HOURS_START=23 QUITE_HOURS_END=8
QUIET_HOURS_START = int(os.environ.get("QUIET_HOURS_START", "23"))  # 23:00 MSK
QUIET_HOURS_END = int(os.environ.get("QUIET_HOURS_END", "8"))      # 08:00 MSK
MSK = timezone(timedelta(hours=3))


def is_quiet_hours(now=None):
    """True if now (MSK) is in quiet hours — don't publish new content."""
    if now is None:
        now = datetime.now(MSK)
    h = now.hour
    if QUIET_HOURS_START > QUIET_HOURS_END:
        # window crosses midnight (e.g. 23..8)
        return h >= QUIET_HOURS_START or h < QUIET_HOURS_END
    return QUIET_HOURS_START <= h < QUIET_HOURS_END


def text_fingerprint(text):
    """Stable hash of the first 400 chars — used to detect duplicate sends."""
    return hashlib.sha256((text or "")[:400].encode("utf-8")).hexdigest()[:16]


def _load_recent():
    try:
        with open(SENT_DEDUP_PATH) as f:
            return json.load(f)
    except Exception:
        return {"items": []}


def _save_recent(d):
    try:
        with open(SENT_DEDUP_PATH, "w") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[DEDUP ERROR] save failed: {e}", file=sys.stderr)


def was_recently_sent(text, within_seconds=86400):
    """True if the same text was recorded as sent within the last N seconds.
    Used to detect duplicates after CLI timeout-on-send.

    Default window is 24h (was 5 min) to also catch the case where
    cron-analyze-publish picks up the same article after our run finished
    but the queue was rewritten in between.
    """
    fp = text_fingerprint(text)
    now_ts = datetime.now(timezone.utc).timestamp()
    d = _load_recent()
    for it in d.get("items", []):
        if it.get("fp") == fp:
            ts = it.get("ts", 0)
            if now_ts - ts < within_seconds:
                return it.get("msg_id") or True
    return False


def record_sent(text, msg_id):
    """Record that we sent a message. Keep last 200 items, drop older than 7 days."""
    fp = text_fingerprint(text)
    now_ts = datetime.now(timezone.utc).timestamp()
    d = _load_recent()
    d["items"].insert(0, {"fp": fp, "ts": now_ts, "msg_id": msg_id, "text_head": (text or "")[:80]})
    cutoff = now_ts - 7 * 86400  # 7 days
    d["items"] = [it for it in d["items"] if it.get("ts", 0) >= cutoff][:200]
    _save_recent(d)

def _load_metrics():
    try:
        with open(METRICS_PATH) as f:
            d = json.load(f)
        # Make sure new top-level keys exist (back-compat for old metrics.json)
        for k in ("article_funnel", "source_health", "blog_sync", "hourly_publish",
                  "telegram_audit", "alerts", "run_correlation"):
            d.setdefault(k, {} if k in ("article_funnel", "source_health", "blog_sync",
                                         "hourly_publish", "run_correlation") else [])
        return d
    except:
        return {
            "runs": {
                "scan": [],
                "analyze": [],
                "publish": [],
                "daily_summary": [],
                "telegram_send": [],
                "blog_sync": []
            },
            "published": [],
            "errors": [],
            "dedup_log": [],
            "article_funnel": {},
            "source_health": {},
            "blog_sync": {},
            "hourly_publish": {},
            "telegram_audit": [],
            "alerts": [],
            "run_correlation": {},
            "start_time": datetime.now(timezone.utc).isoformat()
        }

def _save_metrics(m):
    try:
        with open(METRICS_PATH, 'w') as f:
            json.dump(m, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[METRICS ERROR] Failed to save: {e}", file=sys.stderr)

def _acquire_lock(lock_path, suffix=""):
    """Acquire file lock, return fd or None if already locked."""
    try:
        lock_fd = os.open(lock_path + suffix + ".lock", os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_fd
    except BlockingIOError:
        return None

def _release_lock(lock_fd, lock_path, suffix=""):
    if lock_fd is not None:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            os.unlink(lock_path + suffix + ".lock")
        except:
            pass

def log_event(event_type, action, details=None):
    """
    Логирует событие в events.log и metrics.json.
    event_type: scan | analyze | publish | daily_summary | error | dedup
    action: started | completed | failed | skipped | duplicate
    details: dict с дополнительной информацией
    """
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "ts": ts,
        "type": event_type,
        "action": action,
        "details": details or {}
    }
    
    # 1. Write to events.log (append)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[METRICS ERROR] Cannot write to log: {e}", file=sys.stderr)
    
    # 2. Update metrics.json (bounded)
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return  # Couldn't get lock, skip metrics update
    try:
        m = _load_metrics()
        
        if event_type in m["runs"]:
            m["runs"][event_type].insert(0, {
                "ts": ts,
                "action": action,
                "details": details
            })
            # Keep last 100 entries per type
            m["runs"][event_type] = m["runs"][event_type][:100]
        
        if event_type == "error":
            m["errors"].insert(0, entry)
            m["errors"] = m["errors"][:100]
        
        if event_type == "dedup":
            m["dedup_log"].insert(0, entry)
            m["dedup_log"] = m["dedup_log"][:100]
        
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)

def log_published(article_id, source, title, msg_id, importance):
    """Логирует успешную публикацию."""
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        m["published"].insert(0, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "article_id": article_id,
            "source": source,
            "title": title[:100],
            "msg_id": msg_id,
            "importance": importance
        })
        # Track by date for daily stats
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if "daily_counts" not in m:
            m["daily_counts"] = {}
        m["daily_counts"][today] = m["daily_counts"].get(today, 0) + 1
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)

def log_error(script, error_msg, details=None):
    """Логирует ошибку."""
    log_event("error", "failed", {
        "script": script,
        "error": error_msg,
        **(details or {})
    })


# ============================================================================
# Telegram publish audit trail (every CLI send → telegram_audit.log + metrics)
# ============================================================================

def log_telegram_send(article_id, source, title, msg_id, account, duration_ms,
                      result, error=None, retried=0):
    """Каждый openclaw message send → append в telegram_audit.log + metrics.json.

    result: 'sent' | 'timeout' | 'error' | 'dedup_skip' | 'quiet_skip'
    Используется для forensics: если дубликат пришёл из канала — смотрим сюда.
    """
    ts = datetime.now(timezone.utc).isoformat()
    entry = {
        "ts": ts,
        "article_id": article_id,
        "source": source,
        "title": (title or "")[:80],
        "msg_id": msg_id,
        "account": account,
        "duration_ms": duration_ms,
        "result": result,
        "retried": retried,
        "error": error,
    }
    # Append-only audit log (JSONL)
    try:
        with open(TELEGRAM_AUDIT_PATH, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[AUDIT ERROR] {e}", file=sys.stderr)
    # Rotate: keep last 200 entries in metrics
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        m["telegram_audit"].insert(0, entry)
        m["telegram_audit"] = m["telegram_audit"][:200]
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


def patch_audit_article(msg_id, article_id, source=None, title=None):
    """Patch the most recent audit entry matching this msg_id with the real article_id.

    send_telegram() doesn't know article_id (called with just text).
    Caller (publish_post.main) calls this after successful send to enrich audit log.
    """
    if not msg_id:
        return
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        for e in m.get("telegram_audit", []):
            if e.get("msg_id") == msg_id and e.get("article_id") in ("(unknown)", ""):
                e["article_id"] = article_id
                if source:
                    e["source"] = source
                if title:
                    e["title"] = title[:80]
                break
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)
    # Same for telegram_audit.log
    try:
        with open(TELEGRAM_AUDIT_PATH) as f:
            lines = f.readlines()
        new_lines = []
        patched = False
        for line in lines:
            if not patched:
                try:
                    e = json.loads(line)
                    if e.get("msg_id") == msg_id and e.get("article_id") in ("(unknown)", ""):
                        e["article_id"] = article_id
                        if source:
                            e["source"] = source
                        if title:
                            e["title"] = title[:80]
                        patched = True
                        new_lines.append(json.dumps(e, ensure_ascii=False) + "\n")
                        continue
                except Exception:
                    pass
            new_lines.append(line)
        with open(TELEGRAM_AUDIT_PATH, "w") as f:
            f.writelines(new_lines)
    except Exception as ex:
        print(f"[AUDIT PATCH ERROR] {ex}", file=sys.stderr)


# ============================================================================
# Per-article funnel (enqueued → analyzed → published → blog_synced)
# ============================================================================

def funnel_set(article_id, stage, **details):
    """Track per-article lifecycle: enqueued | analyzed | published | blog_synced.

    funnel = {
        "arxiv-2607.02509": {
            "enqueued": {"ts": "..."},
            "analyzed": {"ts": "...", "duration_ms": ...},
            "published": {"ts": "...", "msg_id": 817, "duration_ms": ...},
            "blog_synced": {"ts": "..."}
        }
    }
    """
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        funnel = m.setdefault("article_funnel", {})
        f = funnel.setdefault(article_id, {})
        f[stage] = {"ts": datetime.now(timezone.utc).isoformat(), **details}
        # Keep last 500 articles in funnel
        if len(funnel) > 500:
            for old_key in list(funnel.keys())[:len(funnel) - 500]:
                del funnel[old_key]
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


# ============================================================================
# Source health (RSS/sitemap per-source fail tracking)
# ============================================================================

def log_source_health(source, ok, fetch_ms=None, items_found=None, error=None):
    """Track per-source health: ok / fail with timestamps and fail streaks.

    source_health = {
        "anthropic": {"last_ok_ts": "...", "last_fail_ts": null,
                      "fail_streak": 0, "last_items": 5},
        "openai":    {"last_ok_ts": "...", "fail_streak": 2, ...}
    }
    """
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        sh = m.setdefault("source_health", {})
        s = sh.setdefault(source, {"fail_streak": 0})
        ts = datetime.now(timezone.utc).isoformat()
        if ok:
            s["last_ok_ts"] = ts
            s["fail_streak"] = 0
            if items_found is not None:
                s["last_items"] = items_found
            if fetch_ms is not None:
                s["last_fetch_ms"] = fetch_ms
        else:
            s["last_fail_ts"] = ts
            s["fail_streak"] = s.get("fail_streak", 0) + 1
            s["last_error"] = (error or "")[:200]
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


# ============================================================================
# Blog sync
# ============================================================================

def log_blog_sync(article_ids, ok, duration_ms=None, error=None):
    """Track blog deploy outcome."""
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        bs = m.setdefault("blog_sync", {})
        key = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
        bs[key] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "ok": ok,
            "duration_ms": duration_ms,
            "article_ids": article_ids,
            "error": (error or "")[:300] if not ok else None,
        }
        # Keep last 100 sync events
        if len(bs) > 100:
            for old in list(bs.keys())[:len(bs) - 100]:
                del bs[old]
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


# ============================================================================
# Run correlation (link scan→analyze→publish by run_id)
# ============================================================================

def log_run_event(run_id, script, action, details=None):
    """Логирует событие pipeline-run с correlation id.

    run_id = scan:20260713T100000
    script = scan | analyze | publish | blog_sync | telegram_send
    action = started | completed | failed | skipped | guard_hit | error
    """
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        rc = m.setdefault("run_correlation", {})
        r = rc.setdefault(run_id, [])
        r.append({
            "ts": datetime.now(timezone.utc).isoformat(),
            "script": script,
            "action": action,
            "details": details or {},
        })
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


# ============================================================================
# Alerts (anomalies: source_unhealthy, dedup_spike, llm_overload)
# ============================================================================

def log_alert(alert_type, message, severity="warn", details=None):
    """Auto-alerts: source_unhealthy, dedup_spike, llm_overload, telegram_conflict."""
    lock_fd = _acquire_lock(METRICS_PATH)
    if lock_fd is None:
        return
    try:
        m = _load_metrics()
        m.setdefault("alerts", []).insert(0, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": alert_type,
            "severity": severity,
            "message": message,
            "details": details or {},
        })
        m["alerts"] = m["alerts"][:100]
        _save_metrics(m)
    finally:
        _release_lock(lock_fd, METRICS_PATH)


# ============================================================================
# Skill heartbeat — detect if disabled skill somehow runs again
# ============================================================================

def log_skill_publish_attempt(skill_name, article_id, account, msg_id=None, blocked=True):
    """Если увидели публикацию из не-agentsmits account — пишем сюда.
    Используется как warning: либо skill жив, либо кто-то вручную дублирует.
    """
    log_alert(
        alert_type="skill_publish_attempt",
        message=f"Skill '{skill_name}' attempted publish (account={account}, blocked={blocked})",
        severity="error",
        details={
            "skill": skill_name,
            "article_id": article_id,
            "account": account,
            "msg_id": msg_id,
            "blocked": blocked,
        }
    )

def get_status():
    """Возвращает текущий статус системы для отладки."""
    m = _load_metrics()
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc).replace(hour=0, minute=0, second=0) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Count today's and yesterday's publishes
    today_published = sum(1 for p in m["published"] if p.get("ts", "").startswith(today))
    yesterday_published = sum(1 for p in m["published"] if p.get("ts", "").startswith(yesterday))
    
    # Recent errors
    recent_errors = m["errors"][:5]
    
    # Last run times
    last_runs = {}
    for script in ["scan", "analyze", "publish", "daily_summary"]:
        runs = m["runs"].get(script, [])
        if runs:
            last_runs[script] = runs[0]["ts"]
    
    # Check for duplicates today
    msg_ids_today = {}
    dup_count = 0
    for p in m["published"]:
        if p.get("ts", "").startswith(today):
            mid = p.get("msg_id")
            if mid:
                if mid in msg_ids_today:
                    dup_count += 1
                msg_ids_today[mid] = p
    
    return {
        "today_published": today_published,
        "yesterday_published": yesterday_published,
        "today_dupes": dup_count,
        "recent_errors": recent_errors,
        "last_runs": last_runs,
        "daily_counts": m.get("daily_counts", {})
    }

def print_status():
    """Печатает человекочитаемый статус."""
    s = get_status()
    print("=" * 50)
    print("📊 СТАТУС AI-КАНАЛА")
    print("=" * 50)
    print(f"📅 Сегодня опубликовано: {s['today_published']}")
    print(f"📅 Вчера опубликовано: {s['yesterday_published']}")
    print(f"🔄 Сегодня дубликатов: {s['today_dupes']}")
    print()
    print("⏱ Последние запуски:")
    for script, ts in s["last_runs"].items():
        print(f"  {script}: {ts}")
    print()
    if s["recent_errors"]:
        print("⚠️ Последние ошибки:")
        for e in s["recent_errors"]:
            print(f"  [{e['ts']}] {e['details'].get('script')}: {e['details'].get('error')}")
    else:
        print("✅ Ошибок нет")
    print()
    print("📈 Опубликовано по дням (последние 7):")
    for day, count in list(s["daily_counts"].items())[-7:]:
        print(f"  {day}: {count}")
    print("=" * 50)

if __name__ == "__main__":
    print_status()
