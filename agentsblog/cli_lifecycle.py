"""Lifecycle commands: init-db, migrate."""
from __future__ import annotations

from agentsblog.config import Settings
from agentsblog.db import connect, init_schema


def init_db_cmd(settings: Settings) -> int:
    """Create SQLite + schema. Idempotent."""
    conn = connect(settings.db_path)
    init_schema(conn)
    print(f"[OK] Initialized {settings.db_path}")
    return 0


def migrate_cmd(settings: Settings) -> int:
    """One-shot import of legacy JSON files into SQLite.

    Maps:
      data/pending_queue.json     → articles (status=pending/published)
      data/narratives.json        → narratives + narrative_items
      data/sources.md             → parsed (TODO: parser)
    """
    from agentsblog.migration import migrate_all
    conn = connect(settings.db_path)
    init_schema(conn)
    counts = migrate_all(conn, settings.resolved_data_dir)
    print("[OK] Migration complete:")
    for k, v in counts.items():
        print(f"   {k}: {v}")
    return 0