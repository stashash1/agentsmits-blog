"""Daily summary CLI - collects yesterday's published articles, formats a
Telegram-ready digest, sends via direct_api (urllib HTTPS, bypasses broken
OpenClaw gateway), logs to events. No-LLM version: aggregate + top-N highlight.

Replaces the legacy `pipeline/daily_summary.py` (which required fcntl + openclaw CLI).
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

from agentsblog.config import Settings


log = logging.getLogger(__name__)


# ─── Pure-DB helpers (no LLM, stdlib only) ───────────────────────────────


def _articles_published_in_range(
    conn: sqlite3.Connection, start_iso: str, end_iso: str
) -> list[dict[str, Any]]:
    """Articles with status=published whose published_at is in [start_iso, end_iso).

    start/end are inclusive lower / exclusive upper (UTC ISO-8601).
    """
    rows = conn.execute(
        """
        SELECT id, source_id, title, url, importance,
               is_breakthrough, breakthrough_score,
               published_at, translated_title, summary,
               agent_impact, business_impact, it_impact,
               date
        FROM articles
        WHERE status='published'
          AND published_at >= ?
          AND published_at <  ?
        ORDER BY importance DESC,
                 is_breakthrough DESC,
                 breakthrough_score DESC,
                 published_at DESC
        """,
        (start_iso, end_iso),
    ).fetchall()
    return [dict(r) for r in rows]


def _format_digest(
    target_date: str,
    articles: list[dict[str, Any]],
    agi_days: int,
    agi_pct: int,
) -> str:
    """Telegram-friendly Markdown digest. No emoji headers, just inline emoji."""
    total = len(articles)
    bt_count = sum(1 for a in articles if a.get("is_breakthrough"))
    sources = Counter(a["source_id"] for a in articles)

    lines: list[str] = [
        f"## Daily digest — {target_date}",
        "",
        f"Published: **{total}** articles · Breakthroughs: **{bt_count}**",
        f"Days to AGI: ~**{agi_days}** · progress ~**{agi_pct}%**",
        "",
        "### By source",
        "",
    ]
    for src, n in sorted(sources.items(), key=lambda x: -x[1]):
        lines.append(f"- `{src}`: {n}")
    lines.append("")

    bts = [a for a in articles if a.get("is_breakthrough")]
    if bts:
        lines += ["### Breakthroughs", ""]
        for a in bts[:5]:
            title = (a.get("translated_title") or a.get("title") or "").strip()[:140]
            score = a.get("breakthrough_score") or 0
            imp = a.get("importance") or 0
            lines.append(
                f"- **[{imp}|score {score}]** {title} — [link]({a['url']})"
            )
        lines.append("")

    lines += ["### Top by importance", ""]
    for a in articles[:7]:
        title = (a.get("translated_title") or a.get("title") or "").strip()[:140]
        imp = a.get("importance") or 0
        lines.append(f"- **[{imp}]** {title} — [link]({a['url']})")
    lines.append("")

    lines += [
        "---",
        f"_agentsblog {datetime.now(timezone.utc).isoformat()}_",
    ]
    return "\n".join(lines)


# ─── AGI formatting (legacy-compatible) ───────────────────────────────


def _compute_agi_target(target_date: str) -> tuple[int, int]:
    """Legacy-compatible AGI formatting (elapsed since 2026-01-01)."""
    base = 1460
    start = datetime(2026, 1, 1, tzinfo=timezone.utc).date()
    target = datetime.strptime(target_date, "%Y-%m-%d").date()
    elapsed = (target - start).days
    agi_days = max(0, base - elapsed)
    agi_pct = max(2, min(98, round(elapsed / base * 100)))
    return agi_days, agi_pct


# ─── Sending + logging ─────────────────────────────────────────────────


def _log_event(conn: sqlite3.Connection, *, action: str, details: dict[str, Any]) -> None:
    """Append to events table (mirrors the legacy events.log behavior)."""
    from agentsblog.db import append_event
    run_id = f"daily_summary:{datetime.now(timezone.utc).isoformat()}"
    append_event(
        conn,
        run_id=run_id,
        script="daily_summary",
        event=action,
        details=details,
    )


def _send_digest(text: str, settings: Settings) -> dict[str, Any]:
    """Send via direct_api.send_from_env (urllib HTTPS, bypasses OpenClaw CLI).

    Returns the DirectSendResult as a dict (with ok/msg_id/duration/error/reason).
    """
    from agentsblog.publishing.direct_api import send_from_env
    res = send_from_env(text, settings, parse_mode=None)
    return {
        "ok": res.ok,
        "msg_id": res.msg_id,
        "duration_ms": res.duration_ms,
        "reason": res.reason,
        "error": res.error,
    }


# ─── CLI subcommand ────────────────────────────────────────────────────


def daily_summary_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Generate and (optionally) publish the daily summary.

    Default target_date is YESTERDAY (UTC) - matches the 21:00 MSK cron that
    runs after the day's publish cycle.

    Env requirements for actual send (bypasses 'no Chat_ID' / 'no Token' via
    DirectSendResult.reason):
      AGENTSBLOG_BOT_TOKEN_FILE=path  (file with the bot token, 1 line)
      AGENTSBLOG_TELEGRAM_CHAT_ID=-100xxx (numeric chat_id)
    """
    from agentsblog.db import connect, init_schema

    target_date = args.date
    if not target_date:
        target_date = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

    next_day = (
        datetime.strptime(target_date, "%Y-%m-%d").date() + timedelta(days=1)
    ).isoformat()

    conn = connect(settings.db_path)
    init_schema(conn)

    articles = _articles_published_in_range(
        conn,
        f"{target_date}T00:00:00+00:00",
        f"{next_day}T00:00:00+00:00",
    )

    if not articles and not args.allow_empty:
        log.info("no published articles for %s", target_date)
        _log_event(
            conn,
            action="skipped_no_articles",
            details={"date": target_date},
        )
        return 0

    agi_days, agi_pct = _compute_agi_target(target_date)
    text = _format_digest(target_date, articles, agi_days, agi_pct)

    if args.dry_run:
        print(f"[dry-run] {len(text)} chars for {target_date} ({len(articles)} articles)")
        print("-" * 40)
        print(text)
        print("-" * 40)
        return 0

    send = _send_digest(text, settings)

    details = {
        "date": target_date,
        "article_count": len(articles),
        "send": send,
        "text_length": len(text),
    }
    if send.get("ok"):
        _log_event(conn, action="sent", details=details)
        log.info(
            "daily_summary sent: msg_id=%s date=%s articles=%d",
            send.get("msg_id"),
            target_date,
            len(articles),
        )
        return 0
    _log_event(conn, action="failed", details=details)
    log.error("daily_summary send failed: %s", send)
    return 1


def add_subparser(subparsers) -> None:
    p = subparsers.add_parser(
        "daily-summary",
        help="Publish daily digest (yesterday by default) to Telegram via direct_api.",
    )
    p.add_argument(
        "--date",
        default=None,
        metavar="YYYY-MM-DD",
        help="Target date (default: yesterday UTC)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print digest without sending",
    )
    p.add_argument(
        "--allow-empty",
        action="store_true",
        help="Send digest even when zero articles",
    )
    p.set_defaults(func=daily_summary_cmd)
