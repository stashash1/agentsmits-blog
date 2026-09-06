"""Publisher orchestrator — picks pending items, formats, sends, marks published.

The legacy `pipeline/publish_post.py` was 700+ lines doing all of:
- decay
- breakthrough detection
- narrative clustering
- 3-level dedup
- release + industry grouping
- 3 formatters
- Telegram send
- site rebuild
- metrics
- alert logging

This module orchestrates those, but each step is its own importable function.
The orchestrator itself stays under 250 lines.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Iterable

from agentsblog.config import Settings
from agentsblog.db import (
    append_event,
    connect,
    init_schema,
    is_url_known,
    list_pending,
    mark_published,
)
from agentsblog.models import Article, ArticleStatus
from agentsblog.publishing.dedup import was_recently_sent
from agentsblog.publishing.decay import apply_decay_to_pending
from agentsblog.publishing.formatter import (
    compute_agi,
    format_breakthrough,
    format_industry_digest,
    format_release_digest,
    format_standard,
)
from agentsblog.publishing.telegram import send as tg_send
from agentsblog.scoring.breakthrough import detect_breakthrough


log = logging.getLogger(__name__)


def _is_quiet_now(settings: Settings) -> bool:
    from agentsblog.utils.time import is_quiet_hours, local_now
    return is_quiet_hours(
        local_now(settings.tz_offset),
        start_hour=settings.quiet_hours_start,
        end_hour=settings.quiet_hours_end,
    )


def _trigger_site_rebuild(settings: Settings) -> tuple[int, str]:
    """Run `agentsblog build-site`. Returns (rc, stderr_tail)."""
    python = sys.executable
    try:
        result = subprocess.run(
            [python, "-m", "agentsblog", "--root", str(settings.root), "build-site"],
            capture_output=True, text=True, timeout=300,
        )
        return result.returncode, (result.stderr or "")[-200:]
    except subprocess.TimeoutExpired:
        return 124, "build-site timeout"
    except Exception as e:
        return 1, str(e)[:200]


def publish_one(
    article: Article, settings: Settings, *,
    agi_days: int, agi_percent: int,
    force_breakthrough: bool = False,
) -> dict:
    """Format + send one article. Returns a result dict for tests / observability."""
    breakthrough = detect_breakthrough(article)
    fmt = format_breakthrough if (force_breakthrough or breakthrough.is_breakthrough) else format_standard
    text = fmt(article, agi_days=agi_days, agi_percent=agi_percent)
    if text is None:
        return {"ok": False, "reason": "no_analysis", "article_id": article.id}

    # Quiet hours check
    if _is_quiet_now(settings):
        return {"ok": False, "reason": "quiet_hours", "article_id": article.id}

    # Text-level dedup
    prev = was_recently_sent(text, settings)
    if prev is not False:
        return {"ok": True, "reason": "dedup", "msg_id": prev if isinstance(prev, int) else 0,
                "article_id": article.id}

    result = tg_send(text, settings)
    return {
        "ok": result.ok,
        "reason": result.reason,
        "msg_id": result.msg_id,
        "duration_ms": result.duration_ms,
        "error": result.error,
        "article_id": article.id,
    }


def run_publish(settings: Settings, *,
                limit: int | None = None,
                allow_during_quiet: bool = False,
                dry_run: bool = False) -> dict:
    """Top-level publish run. Returns summary."""
    conn = connect(settings.db_path)
    init_schema(conn)
    run_id = f"publish:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    append_event(conn, run_id=run_id, script="publish", event="started")

    agi_days, agi_percent = compute_agi(settings)

    # Pick candidates: pending, importance >= 3, ordered by bt / decayed / imp / date
    max_importance = 3
    candidates = list_pending(conn, min_importance=max_importance, limit=None)
    apply_decay_to_pending(candidates)

    # Drop anything we can already see in DB-published
    # (defensive: in case list_pending returned a stale status row)
    pending = []
    for art in candidates:
        if art.status is not ArticleStatus.PENDING:
            continue
        if not art.is_publishable:
            log.info("skipping %s (no analysis)", art.id)
            continue
        pending.append(art)

    # Apply quiet-hours short-circuit unless override
    if _is_quiet_now(settings) and not allow_during_quiet:
        log.info("quiet hours: deferring %d items", len(pending))
        append_event(conn, run_id=run_id, script="publish", event="completed",
                     details={"deferred": len(pending), "reason": "quiet_hours"})
        return {
            "run_id": run_id, "published": 0, "failed": 0,
            "quiet_deferred": len(pending),
            "agi_days": agi_days, "agi_percent": agi_percent,
        }

    # Sort: breakthrough first, then by decayed importance desc
    def _sort_key(a: Article):
        bt = detect_breakthrough(a)
        return (
            0 if bt.is_breakthrough else 1,
            -a.decayed_importance,
            -a.importance,
            a.date,
        )
    pending.sort(key=_sort_key)
    pending = pending[: (limit or settings.max_publish_per_run)]

    summary = {
        "run_id": run_id,
        "published": 0, "failed": 0, "skipped": 0,
        "published_ids": [],
        "agi_days": agi_days, "agi_percent": agi_percent,
    }

    for art in pending:
        result = publish_one(art, settings, agi_days=agi_days, agi_percent=agi_percent)
        if result["reason"] == "quiet_hours":
            summary["skipped"] += 1
            continue
        if not result["ok"]:
            log.warning("publish failed for %s: %s", art.id, result.get("error"))
            summary["failed"] += 1
            continue
        msg_id = result.get("msg_id") or 0
        if not dry_run:
            mark_published(conn, art.id, msg_id)
            append_event(conn, run_id=run_id, script="publish",
                         event="article_published",
                         details={"article_id": art.id, "msg_id": msg_id,
                                 "reason": result["reason"]})
        summary["published"] += 1
        summary["published_ids"].append(art.id)

    # Rebuild site if anything was published
    if summary["published"] > 0 and not dry_run:
        rc, err = _trigger_site_rebuild(settings)
        summary["site_rebuild_rc"] = rc
        if rc != 0:
            summary["site_rebuild_error"] = err

    append_event(conn, run_id=run_id, script="publish", event="completed",
                 details=summary)
    return summary


def print_summary(summary: dict) -> None:
    print(f"Publish {summary['run_id']} complete:")
    print(f"  published: {summary['published']}")
    print(f"  failed:    {summary['failed']}")
    print(f"  skipped:   {summary.get('skipped', 0)}")
    if "quiet_deferred" in summary:
        print(f"  quiet deferred: {summary['quiet_deferred']}")
    print(f"  AGI: {summary['agi_days']} days ({summary['agi_percent']}%)")