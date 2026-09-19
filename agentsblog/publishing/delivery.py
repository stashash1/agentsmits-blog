"""Durable claims shared by CLI, API and scheduled publishers.

An interrupted or ambiguous send stays blocked until explicitly reconciled.
Telegram sendMessage has no idempotency key: automatic retry is unsafe then.
"""
from __future__ import annotations

import hashlib
from contextlib import closing
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit, urlunsplit

from agentsblog.db import connect, init_schema, mark_published


def delivery_key(article, settings):
    parts = urlsplit(article.url)
    url = urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip('/'), parts.query, parts.fragment))
    target = settings.telegram_chat_id or settings.telegram_target
    return hashlib.sha256((target + '\n' + url).encode()).hexdigest()


def reserve(article, settings, *, dry_run=False):
    key = delivery_key(article, settings)
    with closing(connect(settings.db_path)) as conn:
        init_schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT * FROM deliveries WHERE delivery_key=?", (key,)).fetchone()
        if row and row['state'] == 'sent':
            conn.execute("ROLLBACK")
            return {"ok": True, "reason": "dedup", "msg_id": row['message_id']}
        if row and row['state'] in ('sending', 'unknown'):
            conn.execute("ROLLBACK")
            return {"ok": False, "reason": "delivery_needs_review"}
        now = datetime.now(timezone.utc)
        if settings.editorial_required:
            import re
            from difflib import SequenceMatcher
            title = ' '.join(re.findall(r'\w+', article.title.casefold()))
            for recent in conn.execute("SELECT title FROM articles WHERE status='published' AND published_at>=? AND id<>?",
                                       ((now-timedelta(days=7)).isoformat(), article.id)):
                previous = ' '.join(re.findall(r'\w+', recent['title'].casefold()))
                if len(title) >= 25 and re.findall(r'\d+', title) == re.findall(r'\d+', previous) and SequenceMatcher(None, title, previous).ratio() >= .90:
                    conn.execute('ROLLBACK')
                    return {'ok': False, 'reason': 'recent_topic'}
        # Failed deliveries cool down instead of being retried by every scheduler tick.
        if row and row['finished_at'] and datetime.fromisoformat(row['finished_at']) > now-timedelta(minutes=30):
            conn.execute("ROLLBACK")
            return {"ok": False, "reason": "delivery_backoff"}
        if settings.editorial_required:
            tz = timezone(timedelta(hours=settings.tz_offset))
            midnight = now.astimezone(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()
            # Reservations also consume a slot; competing processes cannot overshoot.
            count = conn.execute("""SELECT COUNT(*) FROM deliveries d LEFT JOIN articles a ON a.id=d.article_id
                WHERE d.started_at>=? AND d.state IN ('sent','sending','unknown')
                AND (d.state!='sent' OR a.status IS NULL OR a.status!='published')""", (midnight,)).fetchone()[0]
            count += conn.execute("""SELECT COUNT(DISTINCT CASE WHEN message_id>0 THEN 'msg:'||message_id ELSE id END)
                FROM articles WHERE status='published' AND published_at>=?""", (midnight,)).fetchone()[0]
            last = conn.execute("SELECT MAX(started_at) FROM deliveries WHERE state IN ('sent','sending','unknown')").fetchone()[0]
            last_published = conn.execute("SELECT MAX(published_at) FROM articles WHERE status='published'").fetchone()[0]
            last = max(filter(None, (last, last_published)), default=None)
            if count >= settings.editorial_max_daily_posts:
                conn.execute("ROLLBACK")
                return {"ok": False, "reason": "daily_limit"}
            if last and datetime.fromisoformat(last) > now-timedelta(minutes=settings.editorial_min_interval_minutes):
                conn.execute("ROLLBACK")
                return {"ok": False, "reason": "minimum_interval"}
        if dry_run:
            conn.execute('ROLLBACK')
            return None
        conn.execute("""INSERT INTO deliveries(delivery_key,article_id,state,started_at)
            VALUES(?,?,'sending',?) ON CONFLICT(delivery_key) DO UPDATE SET
            state='sending',started_at=excluded.started_at,finished_at=NULL,error=''""", (key, article.id, now.isoformat()))
        conn.execute("COMMIT")
    return None


def finish(article, settings, result):
    confirmed = result.ok and result.msg_id > 0
    ambiguous = result.reason in ('unknown', 'timeout', 'sent_no_msgid', 'state_migration_warning') or (result.ok and not confirmed)
    state = 'sent' if confirmed else 'unknown' if ambiguous else 'failed'
    with closing(connect(settings.db_path)) as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("UPDATE deliveries SET state=?,finished_at=?,message_id=?,error=? WHERE delivery_key=?",
                     (state, datetime.now(timezone.utc).isoformat(), result.msg_id,
                      result.error[:300], delivery_key(article, settings)))
        if confirmed:
            mark_published(conn, article.id, result.msg_id)
        conn.execute('COMMIT')
    return state
