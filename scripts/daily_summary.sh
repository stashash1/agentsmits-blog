#!/usr/bin/env bash
# Daily-summary launcher for cron / systemd.
# Usage:
#   export AGENTSBLOG_BOT_TOKEN_FILE=/etc/agentsblog/bot.token
#   export AGENTSBLOG_TELEGRAM_CHAT_ID=-100XXXXXXXXX
#   ./scripts/daily_summary.sh
#
# Crontab (21:00 MSK = 18:00 UTC):
#   0 18 * * * /opt/agentsblog/scripts/daily_summary.sh >> /var/log/agentsblog-daily.log 2>&1

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${AGENTSBLOG_PY:-python3}"

cd "$ROOT"
exec "$PY" -m agentsblog daily-summary
