"""Scan orchestrator — drives all source scanners + persists results.

One function call (`run_scan()`) does everything:
  - registers all known sources in the DB
  - for each source: fetch + parse + dedup + upsert
  - records source health + emits events
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from agentsblog.db import (
    append_event,
    connect,
    init_schema,
    is_url_known,
    record_source_check,
    upsert_article,
    upsert_source,
)
from agentsblog.models import Article, ArticleStatus
from agentsblog.sources import all_scanners, get_meta


log = logging.getLogger(__name__)


def run_scan(settings, *, limit_sources: list[str] | None = None,
             dry_run: bool = False, max_items_per_source: int | None = None,
             ) -> dict:
    """Run scan over all enabled (or filtered) sources.

    Returns a summary dict for tests / observability.
    """
    from agentsblog.sources import register_all
    register_all()

    conn = connect(settings.db_path)
    init_schema(conn)

    run_id = f"scan:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
    append_event(conn, run_id=run_id, script="scan", event="started")

    # Register all sources (idempotent)
    for source_id, meta, _scanner in all_scanners():
        upsert_source(conn, meta)

    summary: dict = {
        "run_id": run_id,
        "sources_scanned": 0,
        "sources_failed": 0,
        "new_pending": 0,
        "skipped_dups": 0,
        "by_source": {},
    }

    for source_id, meta, scanner_cls in all_scanners():
        if limit_sources and source_id not in limit_sources:
            continue
        enabled = conn.execute(
            "SELECT enabled FROM sources WHERE id = ?", (source_id,)
        ).fetchone()
        if not enabled or not enabled["enabled"]:
            continue

        scanner = scanner_cls(meta)
        try:
            articles = scanner.scan()
            last_fetch = getattr(scanner, "last_fetch", None)
            err = getattr(last_fetch, "error", "")[:200] if last_fetch else ""
            ok = not err
        except Exception as e:
            log.exception("scanner %s raised", source_id)
            articles = []
            ok = False
            err = str(e)[:200]

        last_fetch = getattr(scanner, "last_fetch", None)
        record_source_check(
            conn, source_id,
            ok=ok, items_found=len(articles),
            fetch_ms=last_fetch.fetch_ms if last_fetch else 0,
            error=err,
        )
        if not ok:
            summary["sources_failed"] += 1
            continue
        summary["sources_scanned"] += 1

        # Dedup + upsert
        new_count = 0
        dup_count = 0
        if max_items_per_source:
            articles = articles[:max_items_per_source]
        for art in articles:
            if is_url_known(conn, art.url):
                dup_count += 1
                continue
            if not dry_run:
                upsert_article(conn, art)
            new_count += 1
        summary["by_source"][source_id] = {
            "total": len(articles), "new": new_count, "dup": dup_count,
        }
        summary["new_pending"] += new_count
        summary["skipped_dups"] += dup_count

    append_event(conn, run_id=run_id, script="scan", event="completed",
                 details=summary)
    return summary


def print_scan_summary(summary: dict) -> None:
    print(f"Scan {summary['run_id']} complete:")
    print(f"  sources scanned: {summary['sources_scanned']}")
    print(f"  sources failed:  {summary['sources_failed']}")
    print(f"  new pending:     {summary['new_pending']}")
    print(f"  dups skipped:    {summary['skipped_dups']}")
    print()
    for src_id, counts in summary["by_source"].items():
        if counts["new"] or counts["dup"]:
            print(f"  {src_id:<20} total={counts['total']:<3} "
                  f"new={counts['new']:<3} dup={counts['dup']}")
