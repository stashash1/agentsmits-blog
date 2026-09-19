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
from agentsblog.publishing.dedup import record_sent, was_recently_sent
from agentsblog.publishing.decay import apply_decay_to_pending
from agentsblog.publishing.formatter import (
    compute_agi,
    format_breakthrough,
    format_industry_digest,
    format_release_digest,
    format_standard,
)
from agentsblog.publishing.telegram import send as tg_send
from agentsblog.publishing.telegram import SendResult
from agentsblog.editorial import eligibility
from agentsblog.publishing import delivery
from agentsblog.publishing.editorial_format import format_editorial
from agentsblog.scoring.breakthrough import detect_breakthrough
from agentsblog.scoring.impact import is_release_item


log = logging.getLogger(__name__)


def _is_quiet_now(settings: Settings) -> bool:
    from agentsblog.utils.time import is_quiet_hours, local_now
    return is_quiet_hours(
        local_now(settings.tz_offset),
        start_hour=settings.quiet_hours_start,
        end_hour=settings.quiet_hours_end,
    )


def _group_releases_by_source(
    items: list, window_days: int,
) -> dict[str, list]:
    """Group release-type items by source_id, only within the window.

    Items that don't look like a release are skipped.
    """
    from datetime import timedelta
    from agentsblog.utils.time import parse_iso_date

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    groups: dict[str, list] = {}
    for art in items:
        if not is_release_item(art):
            continue
        # Skip items too old for the window
        d = parse_iso_date(getattr(art, "date", "") or "")
        if d and d < cutoff:
            continue
        sid = getattr(art, "source_id", "") or "unknown"
        groups.setdefault(sid, []).append(art)
    return groups


def _trigger_site_rebuild(settings: Settings) -> tuple[int, str]:
    """Run `agentsblog build-site`. Returns (rc, stderr_tail)."""
    python = sys.executable
    try:
        result = subprocess.run(
            [python, "-m", "agentsblog", "--root", str(settings.root), "build-site"],
            capture_output=True, text=True, timeout=300,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
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
    allow_during_quiet: bool = False,
    dry_run: bool = False,
) -> dict:
    """Format + send one article. Returns a result dict for tests / observability."""
    reasons = eligibility(article, settings)
    if reasons:
        return {"ok": False, "reason": "editorial_gate", "issues": reasons, "article_id": article.id}
    breakthrough = detect_breakthrough(article)
    fmt = format_breakthrough if (force_breakthrough or breakthrough.is_breakthrough) else format_standard
    text = fmt(article, agi_days=agi_days, agi_percent=agi_percent)
    if settings.editorial_required:
        text = format_editorial(article)
        settings = settings.model_copy(update={"telegram_parse_mode": "HTML"})
    if text is None:
        return {"ok": False, "reason": "no_analysis", "article_id": article.id}
    import html
    import re
    visible = html.unescape(re.sub(r'<[^>]*>', '', text))
    if len(visible.encode('utf-16-le')) // 2 > settings.telegram_max_len:
        return {"ok": False, "reason": "post_too_long", "article_id": article.id}

    # Quiet hours check
    if not allow_during_quiet and _is_quiet_now(settings):
        return {"ok": False, "reason": "quiet_hours", "article_id": article.id}

    # Text-level dedup
    prev = was_recently_sent(text, settings) if not settings.editorial_required else False
    if prev is not False:
        return {"ok": True, "reason": "dedup", "msg_id": prev if isinstance(prev, int) else 0,
                "article_id": article.id}

    if dry_run:
        blocked = delivery.reserve(article, settings, dry_run=True)
        if blocked is not None:
            return {**blocked, 'article_id': article.id}
        return {"ok": True, "reason": "dry_run", "msg_id": 0,
                "article_id": article.id}

    reserved = delivery.reserve(article, settings)
    if reserved is not None:
        return {**reserved, "article_id": article.id}
    try:
        result = tg_send(text, settings)
    except Exception as exc:
        result = SendResult(ok=False, reason="unknown", error=type(exc).__name__)
    delivery_state = delivery.finish(article, settings, result)
    if delivery_state == "sent":
        record_sent(text, result.msg_id, settings)
    return {
        "ok": delivery_state == "sent",
        "reason": "delivery_needs_review" if delivery_state == "unknown" else result.reason,
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

    # Pick candidates: pending, importance >= settings.min_publish_importance
    min_imp = settings.min_publish_importance
    candidates = list_pending(conn, min_importance=min_imp, limit=None)
    candidates = apply_decay_to_pending(candidates)

    # Drop anything we can already see in DB-published
    # (defensive: in case list_pending returned a stale status row)
    pending = []
    blocked = {}
    for art in candidates:
        if art.status is not ArticleStatus.PENDING:
            continue
        if not art.is_publishable:
            log.info("skipping %s (no analysis)", art.id)
            continue
        reasons = eligibility(art, settings)
        if reasons:
            blocked[art.id] = reasons
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
        if settings.editorial_required:
            return (-a.ai_impact['editorial']['score'], -a.decayed_importance)
        bt = detect_breakthrough(a)
        return (
            0 if bt.is_breakthrough else 1,
            -a.decayed_importance,
            -a.importance,
            a.date,
        )
    pending.sort(key=_sort_key)
    if settings.editorial_required:
        counts = {}
        diverse = []
        for article in pending:
            count = counts.get(article.source_id, 0)
            if count < settings.max_per_source_per_run:
                diverse.append(article)
                counts[article.source_id] = count + 1
        pending = diverse
    pending = pending[: (limit if limit is not None else settings.max_publish_per_run)]

    # ---- Group release-type items by source into digest posts ----
    release_groups = _group_releases_by_source(
        pending, settings.release_group_window_days
    ) if not settings.editorial_required else {}
    # Track which items got absorbed into a digest (skip in standalone loop)
    digested_ids: set[str] = set()

    summary = {
        "run_id": run_id,
        "published": 0, "failed": 0, "skipped": 0,
        "published_ids": [],
        "agi_days": agi_days, "agi_percent": agi_percent,
        "editorial_blocked": blocked,
    }

    # Emit digests first (one per source with 2+ releases)
    for src_id, group in release_groups.items():
        group = group[:5]  # formatter lists at most five releases
        if len(group) < 2:
            continue  # single release → publish as standalone below
        text = format_release_digest(
            group, source_name=src_id,
            agi_days=agi_days, agi_percent=agi_percent,
        )
        if text is None:
            continue
        if dry_run:
            digested_ids.update(it.id for it in group)
            summary["would_publish"] = summary.get("would_publish", 0) + 1
            summary.setdefault("would_publish_ids", []).extend(it.id for it in group)
            continue
        # Dedup against recently-sent
        prev = was_recently_sent(text, settings)
        if prev is not False:
            for it in group:
                digested_ids.add(it.id)
            continue
        if _is_quiet_now(settings) and not allow_during_quiet:
            log.info("quiet hours: skipping release digest for %s", src_id)
            for it in group:
                digested_ids.add(it.id)
            summary["skipped"] += 1
            continue
        result = tg_send(text, settings)
        if result.ok:
            record_sent(text, result.msg_id, settings)
            for it in group:
                digested_ids.add(it.id)
                if not dry_run:
                    mark_published(conn, it.id, result.msg_id)
            summary["published"] += 1
            log.info("release digest %s: %d items -> msg_id=%s", src_id, len(group), result.msg_id)
            append_event(conn, run_id=run_id, script="publish", event="release_digest",
                         details={"source_id": src_id, "items": [it.id for it in group],
                                 "msg_id": result.msg_id})
        else:
            log.warning("release digest %s failed: %s", src_id, result.error)
            summary["failed"] += 1

    # ---- Standalone posts (cap per source) ----
    per_source_count: dict[str, int] = {}
    for art in pending:
        if art.id in digested_ids:
            continue
        sid = getattr(art, "source_id", "") or "unknown"
        if per_source_count.get(sid, 0) >= settings.max_per_source_per_run:
            log.info("per-source cap reached for %s, skipping %s", sid, art.id)
            summary["skipped"] += 1
            continue
        result = publish_one(
            art, settings, agi_days=agi_days, agi_percent=agi_percent,
            allow_during_quiet=allow_during_quiet, dry_run=dry_run,
        )
        if result["reason"] == "dry_run":
            summary["would_publish"] = summary.get("would_publish", 0) + 1
            summary.setdefault("would_publish_ids", []).append(art.id)
            per_source_count[sid] = per_source_count.get(sid, 0) + 1
            if settings.editorial_required and settings.editorial_min_interval_minutes > 0:
                break
            continue
        if result["reason"] in {"daily_limit", "minimum_interval", "delivery_backoff", "delivery_needs_review", "editorial_gate", "post_too_long", "recent_topic"}:
            summary["skipped"] += 1
            summary.setdefault("deferred_reasons", {})[art.id] = result["reason"]
            if result['reason'] == 'delivery_needs_review':
                summary['needs_review'] = summary.get('needs_review', 0) + 1
            if result["reason"] in {"daily_limit", "minimum_interval"}:
                break
            continue
        if result["reason"] == "quiet_hours":
            summary["skipped"] += 1
            continue
        if not result["ok"]:
            log.warning("publish failed for %s: %s", art.id, result.get("error"))
            summary["failed"] += 1
            continue
        msg_id = result.get("msg_id") or 0
        if dry_run:
            summary["skipped"] += 1
            continue
        if not dry_run:
            mark_published(conn, art.id, msg_id)
            append_event(conn, run_id=run_id, script="publish",
                         event="article_published",
                         details={"article_id": art.id, "msg_id": msg_id,
                                 "reason": result["reason"]})
        summary["published"] += 1
        per_source_count[sid] = per_source_count.get(sid, 0) + 1
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
    if "would_publish" in summary:
        print(f"  would publish: {summary['would_publish']}")
    print(f"  failed:    {summary['failed']}")
    print(f"  skipped:   {summary.get('skipped', 0)}")
    if "quiet_deferred" in summary:
        print(f"  quiet deferred: {summary['quiet_deferred']}")
    print(f"  editorial blocked: {len(summary.get('editorial_blocked', {}))}")
