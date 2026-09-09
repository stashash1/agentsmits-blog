"""CLI for agentsblog — argparse subcommands.

Run `agentsblog --help` or `python -m agentsblog --help` for the full list.

Subcommands are implemented as plain functions in their respective modules;
this file just dispatches.
"""
from __future__ import annotations

import argparse
import logging
import sys

from agentsblog import __version__
from agentsblog.config import Settings


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="agentsblog",
        description="AI news aggregator + Telegram publisher + static site generator",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--root",
        type=str,
        default=None,
        help="Override project root (default: auto-detect)",
    )
    p.add_argument(
        "--log-level", default=None,
        help="Logging level (DEBUG/INFO/WARNING/ERROR). Default: INFO.",
    )

    sub = p.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # ── Lifecycle ───────────────────────────────────────────────
    sub.add_parser("init-db", help="Initialize SQLite database (idempotent)")
    sub.add_parser("migrate", help="Import legacy JSON files into SQLite (one-shot)")

    # ── Pipeline ────────────────────────────────────────────────
    scan = sub.add_parser("scan", help="Scan all enabled sources")
    scan.add_argument("--source", action="append", default=[],
                      help="Limit to specific source id (repeatable)")
    scan.add_argument("--dry-run", action="store_true",
                      help="Show what would be added; don't persist")
    scan.add_argument("--limit", type=int, default=None,
                      help="Max items per source")

    pub = sub.add_parser("publish", help="Publish pending items to Telegram")
    pub.add_argument("--dry-run", action="store_true")
    pub.add_argument("--limit", type=int, default=None,
                     help="Override max items per run")
    pub.add_argument("--allow-during-quiet", action="store_true",
                     help="Skip quiet-hours check (admin only)")

    pub_art = sub.add_parser("publish-article", help="Publish draft articles")
    pub_art.add_argument("--id", required=True, help="Article id from articles queue")
    pub_art.add_argument("--dry-run", action="store_true")

    # ── Manual entry (the missing API from the spec) ────────────
    add = sub.add_parser("add-manual", help="Manually add a news item")
    add.add_argument("--title", required=True)
    add.add_argument("--url", required=True)
    add.add_argument("--source", required=True, help="Source id (must exist or auto-register)")
    add.add_argument("--summary", default="")
    add.add_argument("--agent-impact", default="")
    add.add_argument("--business-impact", default="")
    add.add_argument("--it-impact", default="")
    add.add_argument("--tags", default="", help="Comma-separated")
    add.add_argument("--importance", type=int, default=4, choices=[1, 2, 3, 4, 5])
    add.add_argument("--publish", action="store_true",
                     help="Publish immediately after adding")

    # ── Site ────────────────────────────────────────────────────
    sub.add_parser("build-site", help="Regenerate static site (public/)")

    # ── Observability ───────────────────────────────────────────
    sub.add_parser("status", help="Show pipeline status")
    sub.add_parser("health", help="Show source health")

    # ── HTTP API ────────────────────────────────────────────────
    serve = sub.add_parser("serve", help="Run HTTP API (FastAPI; needs [api] extra)")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)

    # ── Sources management ──────────────────────────────────────
    from agentsblog.cli_daily import add_subparser as _add_daily_subparser
    _add_daily_subparser(sub)
    src = sub.add_parser("sources", help="List / manage sources")
    src.add_argument("action", choices=["list", "disable", "enable"], nargs="?", default="list")
    src.add_argument("source_id", nargs="?")

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings_kwargs: dict = {}
    if args.root:
        settings_kwargs["root"] = args.root
    if args.log_level:
        settings_kwargs["log_level"] = args.log_level.upper()
    settings = Settings(**settings_kwargs)

    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    return _dispatch(args, settings)


def _dispatch(args: argparse.Namespace, settings: Settings) -> int:
    """Route subcommand → handler."""
    cmd = args.command
    if cmd == "init-db":
        from agentsblog.cli_lifecycle import init_db_cmd
        return init_db_cmd(settings)
    if cmd == "migrate":
        from agentsblog.cli_lifecycle import migrate_cmd
        return migrate_cmd(settings)
    if cmd == "scan":
        from agentsblog.cli_pipeline import scan_cmd
        return scan_cmd(args, settings)
    if cmd == "publish":
        from agentsblog.cli_pipeline import publish_cmd
        return publish_cmd(args, settings)
    if cmd == "publish-article":
        from agentsblog.cli_pipeline import publish_article_cmd
        return publish_article_cmd(args, settings)
    if cmd == "add-manual":
        from agentsblog.cli_pipeline import add_manual_cmd
        return add_manual_cmd(args, settings)
    if cmd == "build-site":
        from agentsblog.cli_site import build_site_cmd
        return build_site_cmd(settings)
    if cmd == "status":
        from agentsblog.cli_observe import status_cmd
        return status_cmd(settings)
    if cmd == "health":
        from agentsblog.cli_observe import health_cmd
        return health_cmd(settings)
    if cmd == "serve":
        from agentsblog.cli_serve import serve_cmd
        return serve_cmd(args, settings)
    if cmd == "sources":
        from agentsblog.cli_observe import sources_cmd
        return sources_cmd(args, settings)
    if cmd == "daily-summary":
        from agentsblog.cli_daily import daily_summary_cmd
        return daily_summary_cmd(args, settings)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())