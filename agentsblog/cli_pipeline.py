"""Pipeline command stubs — implemented in stages 2-4.

These are placeholders that route to the actual implementations once those
modules land. For now they print a friendly 'coming soon' so the CLI works.
"""
from __future__ import annotations

import argparse

from agentsblog.config import Settings


def scan_cmd(args: argparse.Namespace, settings: Settings) -> int:
    print("scan: implementation lands in stage 2 (sources/)", file=__import__("sys").stderr)
    return 1


def publish_cmd(args: argparse.Namespace, settings: Settings) -> int:
    print("publish: implementation lands in stage 4 (publishing/)", file=__import__("sys").stderr)
    return 1


def publish_article_cmd(args: argparse.Namespace, settings: Settings) -> int:
    print("publish-article: implementation lands in stage 4", file=__import__("sys").stderr)
    return 1


def add_manual_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """Add a manual news item — THE feature the user asked for.

    Auto-registers the source if it doesn't exist yet (tier 3, manual entry).
    """
    from agentsblog.db import connect, init_schema, upsert_article, upsert_source
    from agentsblog.models import Article, ArticleStatus, Source, SourceKind

    conn = connect(settings.db_path)
    init_schema(conn)

    # Auto-register source if missing (manual = tier 3 by default)
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

    # Stable id from source + url hash
    import hashlib
    aid = f"{args.source}-{hashlib.md5(args.url.encode()).hexdigest()[:12]}"
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]

    article = Article(
        id=aid,
        source_id=args.source,
        title=args.title,
        url=args.url,
        date="",  # unknown
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