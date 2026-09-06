"""Pipeline CLI commands — scan, publish, publish-article, add-manual."""
from __future__ import annotations

import argparse

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
    return 0


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
    return 0


def publish_article_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Publish a specific draft article by id."""
    from agentsblog.db import connect, get_article, init_schema, mark_published
    from agentsblog.publishing.formatter import compute_agi
    from agentsblog.publishing.publisher import publish_one

    conn = connect(settings.db_path)
    init_schema(conn)
    art = get_article(conn, args.id)
    if art is None:
        print(f"Article not found: {args.id}", file=__import__("sys").stderr)
        return 2
    agi_days, agi_percent = compute_agi(settings)
    if args.dry_run:
        print(f"[dry-run] would publish article {art.id}")
        return 0
    result = publish_one(art, settings, agi_days=agi_days, agi_percent=agi_percent)
    if result["ok"] and result["reason"] != "dedup":
        mark_published(conn, art.id, result.get("msg_id") or 0)
    print(f"publish-article {art.id}: {result}")
    return 0 if result["ok"] else 1


def add_manual_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Add a manual news item — THE feature the user asked for.

    Auto-registers the source if it doesn't exist yet (tier 3, manual entry).
    """
    from agentsblog.db import connect, init_schema, upsert_article, upsert_source
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
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    article = Article(
        id=aid,
        source_id=args.source,
        title=args.title,
        url=args.url,
        date="",
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
        print("Auto-publish: not yet wired — run `agentsblog publish --allow-during-quiet`")
    return 0