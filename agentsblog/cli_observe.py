"""Observability commands: status, health, sources."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from agentsblog.config import Settings
from agentsblog.db import connect, init_schema


def status_cmd(settings: Settings) -> int:
    """Pipeline status overview."""
    init_schema(connect(settings.db_path))
    conn = connect(settings.db_path)
    counts = {}
    for status in ("pending", "published", "skipped", "failed", "digested"):
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM articles WHERE status = ?", (status,)
        ).fetchone()
        counts[status] = row["n"]
    total_sources = conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]

    print("=== agentsblog status ===")
    print(f"  DB: {settings.db_path}")
    print(f"  Sources: {total_sources}")
    for k, v in counts.items():
        print(f"  articles/{k}: {v}")
    print(f"  total: {sum(counts.values())}")
    return 0


def health_cmd(settings: Settings) -> int:
    """Source health snapshot."""
    init_schema(connect(settings.db_path))
    conn = connect(settings.db_path)
    rows = conn.execute("""
        SELECT s.id, s.name, s.tier, s.enabled,
               h.last_check, h.last_ok, h.fail_streak, h.last_error
        FROM sources s
        LEFT JOIN source_health h ON h.source_id = s.id
        ORDER BY h.fail_streak DESC, s.id
    """).fetchall()
    if not rows:
        print("No sources registered yet. Run `agentsblog scan` first.")
        return 0
    print(f"{'SOURCE':<28} {'TIER':<5} {'ENABLED':<8} {'STREAK':<7} {'LAST_CHECK':<22}")
    print("-" * 80)
    for r in rows:
        lc = (r["last_check"] or "")[:19]
        streak = r["fail_streak"] if r["fail_streak"] is not None else 0
        print(f"{r['id']:<28} {r['tier']:<5} {bool(r['enabled']):<8} "
              f"{streak:<7} {lc:<22}")
        if r["last_error"]:
            print(f"  |- error: {r['last_error'][:100]}")
    return 0


def sources_cmd(args: argparse.Namespace, settings: Settings) -> int:
    """List / disable / enable sources."""
    init_schema(connect(settings.db_path))
    conn = connect(settings.db_path)
    if args.action == "list":
        rows = conn.execute("SELECT id, name, tier, enabled, url FROM sources ORDER BY id").fetchall()
        if not rows:
            print("No sources registered. Will be registered on first scan.")
            return 0
        print(f"{'ID':<28} {'TIER':<5} {'ENABLED':<8} {'URL'}")
        print("-" * 80)
        for r in rows:
            print(f"{r['id']:<28} {r['tier']:<5} {bool(r['enabled']):<8} {r['url'][:60]}")
        return 0
    if not args.source_id:
        print("source_id required for disable/enable", file=sys.stderr)
        return 2
    enabled = 1 if args.action == "enable" else 0
    conn.execute("UPDATE sources SET enabled = ? WHERE id = ?", (enabled, args.source_id))
    print(f"[OK] {args.action}d {args.source_id}")
    return 0