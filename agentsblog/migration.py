"""One-shot import from legacy JSON files into SQLite.

Safely idempotent — re-running won't duplicate data. Logs counts.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentsblog.models import Article, ArticleStatus


def migrate_all(conn, data_dir: Path) -> dict[str, int]:
    """Import all legacy JSON into SQLite. Returns count per source."""
    counts = {
        "articles_imported": 0,
        "articles_skipped": 0,
        "narratives_imported": 0,
        "narrative_items_imported": 0,
    }
    counts["articles_imported"] += _migrate_pending_queue(conn, data_dir)
    narr = _migrate_narratives(conn, data_dir)
    counts["narratives_imported"] = narr[0]
    counts["narrative_items_imported"] = narr[1]
    return counts


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _migrate_pending_queue(conn, data_dir: Path) -> int:
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
                # Skip malformed entries; don't break the whole migration
                pass
    return imported


def _legacy_to_article(raw: dict, status: ArticleStatus) -> Article:
    """Convert legacy dict shape to Article."""
    return Article(
        id=raw["id"],
        source_id=raw.get("source", "unknown").lower().replace(" ", "_"),
        title=raw.get("title", ""),
        url=raw.get("url", ""),
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


def _migrate_narratives(conn, data_dir: Path) -> tuple[int, int]:
    """Import narratives + narrative items."""
    from agentsblog.db import upsert_article
    data = _load_json(data_dir / "narratives.json")
    if not data:
        return 0, 0
    narratives = data.get("narratives", [])
    narr_count = 0
    item_count = 0
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
            for it in n.get("items", []):
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
            pass
    return narr_count, item_count