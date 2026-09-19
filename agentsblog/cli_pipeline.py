"""Pipeline CLI commands — scan, publish, publish-article, add-manual."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from agentsblog.config import Settings


def scan_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Scan all (or filtered) sources, dedup against DB, upsert new items."""
    from agentsblog.scanner import print_scan_summary, run_scan

    summary = run_scan(
        settings,
        limit_sources=args.source or None,
        dry_run=args.dry_run,
        max_items_per_source=args.limit,
    )
    print_scan_summary(summary)
    return 1 if summary["sources_scanned"] == 0 and summary["sources_failed"] else 0


def publish_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Publish pending items to Telegram."""
    from agentsblog.publishing.publisher import print_summary, run_publish
    summary = run_publish(
        settings,
        limit=args.limit,
        allow_during_quiet=args.allow_during_quiet,
        dry_run=args.dry_run,
    )
    print_summary(summary)
    return 1 if summary["failed"] or summary.get('needs_review') else 0


def publish_article_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Publish a specific draft article by id."""
    from agentsblog.db import connect, get_article, init_schema, mark_published
    from agentsblog.models import ArticleStatus
    from agentsblog.publishing.formatter import compute_agi
    from agentsblog.publishing.publisher import publish_one

    conn = connect(settings.db_path)
    init_schema(conn)
    art = get_article(conn, args.id)
    if art is None:
        print(f"Article not found: {args.id}", file=__import__("sys").stderr)
        return 2
    if art.status is not ArticleStatus.PENDING:
        print(f"Article is not pending: {art.id} ({art.status.value})", file=__import__("sys").stderr)
        return 2
    agi_days, agi_percent = compute_agi(settings)
    result = publish_one(art, settings, agi_days=agi_days, agi_percent=agi_percent, dry_run=args.dry_run)
    if result["ok"] and not args.dry_run:
        mark_published(conn, art.id, result.get("msg_id") or 0)
    print(f"publish-article {art.id}: {result}")
    return 0 if result["ok"] else 1


def add_manual_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Add a manual news item — THE feature the user asked for.

    Auto-registers the source if it doesn't exist yet (tier 3, manual entry).
    """
    from agentsblog.db import connect, get_article, init_schema, upsert_article, upsert_source
    from agentsblog.models import Article, ArticleStatus, Source, SourceKind

    conn = connect(settings.db_path)
    init_schema(conn)

    existing = conn.execute("SELECT id FROM sources WHERE id = ?", (args.source,)).fetchone()
    if not existing:
        upsert_source(
            conn,
            Source(
                id=args.source, name=args.source.title(),
                url="(manual)", kind=SourceKind.HTML, tier=3,
                notes="auto-created from add-manual",
            ),
        )

    import hashlib
    aid = f"{args.source}-{hashlib.md5(args.url.encode()).hexdigest()[:12]}"
    existing_article = get_article(conn, aid)
    if existing_article and existing_article.status is not ArticleStatus.PENDING:
        print(f"Article already processed: {aid} ({existing_article.status.value})")
        return 2
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    article = Article(
        id=aid,
        source_id=args.source,
        title=args.title,
        url=args.url,
        date=datetime.now(timezone.utc).date().isoformat(),
        summary=args.summary,
        importance=args.importance,
        agent_impact=args.agent_impact,
        business_impact=args.business_impact,
        it_impact=args.it_impact,
        tags=tags,
        status=ArticleStatus.PENDING,
    )
    new = upsert_article(conn, article)
    print(f"[OK] {'Created' if new else 'Updated'}: {aid}")
    if args.publish:
        from agentsblog.db import mark_published
        from agentsblog.publishing.formatter import compute_agi
        from agentsblog.publishing.publisher import publish_one

        agi_days, agi_percent = compute_agi(settings)
        result = publish_one(article, settings,
                             agi_days=agi_days, agi_percent=agi_percent)
        if not result["ok"]:
            print(f"Publish failed: {result['reason']} {result.get('error', '')}")
            return 1
        if result["reason"] != "dedup":
            mark_published(conn, aid, result.get("msg_id") or 0)
        print(f"Publish result: {result['reason']}")
    return 0
