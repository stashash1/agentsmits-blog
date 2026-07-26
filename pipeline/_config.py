"""Portable path resolution for agentsmits-blog pipeline.

Pipeline scripts import these constants instead of hard-coding paths.
Layout assumption (default; each path is overridable via ENV):

    <project_root>/
        data/                            # all mutable state lives here
        pipeline/                        # all scripts (+ this file)
        scripts/                         # deployment glue (generate_site.py wrappers)
        public/                          # generated site (deploy target)
        skills/                          # OpenClaw skills (channel-publisher, ...)
        config/default.env               # default environment values

ENV overrides (all optional):
    AGENTSBLOG_DATA_DIR     override the data/ directory
    AGENTSBLOG_PUBLIC_DIR   override the public/ directory
    AGENTSBLOG_ROOT         override project root entirely
    AGENTSBLOG_TELEGRAM_ACCOUNT   Telegram account id (default: "agentsmits")
    AGENTSBLOG_TELEGRAM_TARGET   Telegram chat/target (default: "@agentsSmits")
    AGENTSBLOG_TELEGRAM_CHANNEL  "telegram" channel name (default: "telegram")
    AGENTSBLOG_QUIET_HOURS_START / _END   integer hour 0..23 (default 23 / 8 MSK)
    AGENTSBLOG_TZ_OFFSET    UTC offset in hours for quiet-hours tz (default: 3 = MSK)
"""
from __future__ import annotations

import os
from pathlib import Path

# Project root: parent of pipeline/ directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = Path(os.environ.get("AGENTSBLOG_ROOT", _PROJECT_ROOT))

# Mutable state
DATA_DIR = Path(os.environ.get("AGENTSBLOG_DATA_DIR", PROJECT_ROOT / "data"))
PUBLIC_DIR = Path(os.environ.get("AGENTSBLOG_PUBLIC_DIR", PROJECT_ROOT / "public"))

# Common JSON / log files (paths under data/)
PENDING_QUEUE = DATA_DIR / "pending_queue.json"
SELECTION_QUEUE = DATA_DIR / "selection_queue.json"
ARTICLES_QUEUE = DATA_DIR / "articles_queue.json"
CURRENT_JSON = DATA_DIR / "current.json"
ARCHIVE_JSON = DATA_DIR / "archive.json"
RECENTLY_SENT = DATA_DIR / "recently_sent.json"
SENT_MESSAGES = DATA_DIR / "sent_messages.json"
METRICS = DATA_DIR / "metrics.json"
EVENTS_LOG = DATA_DIR / "events.log"
TELEGRAM_AUDIT = DATA_DIR / "telegram_audit.log"
SYNC_STATUS = DATA_DIR / "sync_status.json"
DAILY_SUMMARIES = DATA_DIR / "daily_summaries.json"
SOURCES_MD = DATA_DIR / "sources.md"

# Quiet hours — when Telegram publishing should pause
QUIET_HOURS_START = int(os.environ.get("AGENTSBLOG_QUIET_HOURS_START", "23"))  # 23:00
QUIET_HOURS_END = int(os.environ.get("AGENTSBLOG_QUIET_HOURS_END", "8"))      # 08:00
TZ_OFFSET_HOURS = int(os.environ.get("AGENTSBLOG_TZ_OFFSET", "3"))  # MSK = UTC+3

# Telegram publishing (openclaw CLI)
# NOTE 2026-07-26: account "agentsmits" was lost (renamed/removed); the working
# OpenClaw Telegram account is "default" (bot @AgentsSmits_bot, posting to
# @agentsSmits). The pipeline was silently failing with
# "Telegram bot token missing" since ~14-Jul because of this.
TELEGRAM_ACCOUNT = os.environ.get("AGENTSBLOG_TELEGRAM_ACCOUNT", "default")
TELEGRAM_CHANNEL = os.environ.get("AGENTSBLOG_TELEGRAM_CHANNEL", "telegram")
TELEGRAM_TARGET = os.environ.get("AGENTSBLOG_TELEGRAM_TARGET", "@agentsSmits")

# Generated site
GENERATE_SITE_SCRIPT = PROJECT_ROOT / "generate_site.py"


def telegram_send_cmd(text: str) -> list[str]:
    """Build the openclaw CLI invocation for sending a Telegram message."""
    return [
        "openclaw", "message", "send",
        "--channel", TELEGRAM_CHANNEL,
        "--account", TELEGRAM_ACCOUNT,
        "--target", TELEGRAM_TARGET,
        "--message", text,
    ]


def ensure_data_dir() -> None:
    """Create data/ if it doesn't exist (fresh deploy)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def init_paths() -> None:
    """Compatibility hook — call once at script start to materialize paths."""
    ensure_data_dir()


if __name__ == "__main__":
    # Sanity-check: print the resolved paths so deploy can verify
    ensure_data_dir()
    print(f"PROJECT_ROOT: {PROJECT_ROOT}")
    print(f"DATA_DIR:     {DATA_DIR}")
    print(f"PUBLIC_DIR:   {PUBLIC_DIR}")
    print(f"PENDING_QUEUE exists: {PENDING_QUEUE.exists()}")
    print(f"TELEGRAM_ACCOUNT: {TELEGRAM_ACCOUNT}")
    print(f"TELEGRAM_TARGET:  {TELEGRAM_TARGET}")
