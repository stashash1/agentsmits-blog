"""One-shot import from legacy JSON files into SQLite.

Order matters: sources → articles (FK to sources) → narratives (FK to articles).
Safe to re-run — all inserts are upserts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentsblog.models import Article, ArticleStatus
from agentsblog.scoring.impact import get_source_tier


def migrate_all(conn, data_dir: Path) -> dict[str, int]:
    """Run all migrations in dependency order. Returns count per stage."""
    counts = {}
    counts["sources_imported"] = _migrate_sources(conn, data_dir)
    # Second pass: any source names found in articles that weren't in
    # pending_queue.json:sources[]. Articles reference many more source
    # names than the curated list, so we synthesize missing ones.
    counts["sources_backfilled"] = _backfill_sources_from_articles(conn, data_dir)
    counts["articles_imported"] = _migrate_articles(conn, data_dir)
    narr, items = _migrate_narratives(conn, data_dir)
    counts["narratives_imported"] = narr
    counts["narrative_items_imported"] = items
    return counts


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


# ── Sources ────────────────────────────────────────────────────────

def _derive_id(name: str, url: str) -> str:
    """Generate a stable source id from legacy {name, url} entry.

    Legacy pending_queue.json:sources lacks an `id` field. We build one
    from the lowercased name with non-alphanumerics replaced.
    """
    import re
    base = (name or url or "unknown").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:40] or "legacy"


def _derive_kind(url: str) -> str:
    """Best-guess source kind from URL."""
    u = (url or "").lower()
    if "rss" in u or "feed" in u or ".xml" in u or "atom" in u:
        return "rss"
    if "arxiv.org/api" in u:
        return "api"
    return "html"


def _backfill_sources_from_articles(conn, data_dir: Path) -> int:
    """Create Source entries for any name referenced by articles that we
    don't have yet. Prevents FK failures when migrating articles.
    """
    from agentsblog.db import upsert_source
    from agentsblog.models import Source, SourceKind
    data = _load_json(data_dir / "pending_queue.json")
    if not data:
        return 0
    # Collect all distinct source names from articles
    names: set[str] = set()
    for section in ("pending", "published"):
        for raw in data.get(section, []):
            if raw.get("source"):
                names.add(raw["source"])
    if not names:
        return 0
    # Check which are missing
    existing_rows = conn.execute("SELECT id FROM sources").fetchall()
    existing_ids = {r["id"] for r in existing_rows}
    backfilled = 0
    for name in sorted(names):
        sid = _derive_id(name, "")
        if sid in existing_ids:
            continue
        try:
            upsert_source(conn, Source(
                id=sid, name=name, url="(migrated)",
                kind=SourceKind.HTML, tier=get_source_tier(name),
                enabled=True, notes="auto-backfilled from article references",
            ))
            backfilled += 1
        except Exception:
            pass
    return backfilled


def _migrate_sources(conn, data_dir: Path) -> int:
    """Import sources from legacy pending_queue.json:sources[]. Generates ids."""
    from agentsblog.db import upsert_source
    from agentsblog.models import Source, SourceKind
    pending = _load_json(data_dir / "pending_queue.json")
    if not pending:
        return 0
    sources = pending.get("sources", [])
    imported = 0
    seen_ids: set[str] = set()
    for raw in sources:
        try:
            name = raw.get("name", "Unknown")
            url = raw.get("url", "")
            sid = _derive_id(name, url)
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            kind = _derive_kind(url)
            tier = get_source_tier(name)
            src = Source(
                id=sid, name=name, url=url,
                kind=SourceKind(kind), tier=tier,
                enabled=True, notes="migrated from pending_queue.json:sources",
            )
            upsert_source(conn, src)
            imported += 1
        except Exception:
            pass
    return imported


# ── Articles ───────────────────────────────────────────────────────

def _migrate_articles(conn, data_dir: Path) -> int:
    """Import pending + published articles from legacy pending_queue.json."""
    from agentsblog.db import upsert_article
    data = _load_json(data_dir / "pending_queue.json")
    if not data:
        return 0
    imported = 0
    for section, status in (("pending", ArticleStatus.PENDING),
                            ("published", ArticleStatus.PUBLISHED)):
        for raw in data.get(section, []):
            try:
                article = _legacy_to_article(raw, status)
                if upsert_article(conn, article):
                    imported += 1
            except Exception:
                # FK constraint failures (e.g. article references a source
                # we couldn't migrate) — skip silently
                pass
    return imported


def _legacy_to_article(raw: dict, status: ArticleStatus) -> Article:
    """Convert legacy dict shape to Article.

    Generates a valid source_id from legacy 'source' field (a name like
    "Anthropic News") via the same _derive_id() used for sources.
    """
    name = raw.get("source", "unknown")
    url = raw.get("url", "")
    source_id = _derive_id(name, url)
    return Article(
        id=raw["id"],
        source_id=source_id,
        title=raw.get("title", ""),
        url=url,
        date=raw.get("date", ""),
        status=status,
        summary=raw.get("summary", ""),
        importance=raw.get("importance", 3),
        decayed_importance=float(raw.get("importance", 3)),
        ai_impact=raw.get("ai_impact"),
        is_breakthrough=bool(raw.get("is_breakthrough", False)),
        breakthrough_score=raw.get("breakthrough_score", 0) or 0,
        breakthrough_reasons=raw.get("breakthrough_reasons", []) or [],
        agent_impact=(raw.get("analysis") or {}).get("agent_impact", ""),
        business_impact=(raw.get("analysis") or {}).get("business_impact", ""),
        it_impact=(raw.get("analysis") or {}).get("it_impact", ""),
        translated_title=(raw.get("analysis") or {}).get("translated_title", ""),
        message_id=raw.get("message_id"),
    )


# ── Narratives ─────────────────────────────────────────────────────

def _migrate_narratives(conn, data_dir: Path) -> tuple[int, int]:
    """Import narratives + narrative items.

    Two-pass: first create all narratives (so narrative_items FK works),
    then create narrative_items in second pass.
    """
    data = _load_json(data_dir / "narratives.json")
    if not data:
        return 0, 0
    narratives = data.get("narratives", [])
    if not narratives:
        return 0, 0

    # Pass 1: narratives only
    narr_count = 0
    for n in narratives:
        try:
            conn.execute(
                """INSERT OR REPLACE INTO narratives
                    (id, title, status, first_seen, last_seen,
                     entities_json, source, importance_max)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    n["id"], n.get("title", ""), n.get("status", "active"),
                    n.get("first_seen", ""), n.get("last_seen", ""),
                    json.dumps(n.get("entities", [])),
                    n.get("source", "auto"),
                    n.get("importance_max", 0),
                ),
            )
            narr_count += 1
        except Exception:
            pass

    # Pass 2: items (FK may fail silently if referenced article doesn't exist)
    item_count = 0
    for n in narratives:
        for it in n.get("items", []):
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO narrative_items
                        (narrative_id, article_id, role, attached_at)
                    VALUES (?, ?, ?, ?)""",
                    (n["id"], it.get("item_id", ""),
                     it.get("role", "followup"),
                     it.get("attached_at", "")),
                )
                item_count += 1
            except Exception:
                # article referenced by item_id may not exist — skip
                pass
    return narr_count, item_count