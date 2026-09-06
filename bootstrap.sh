#!/bin/bash
# Bootstrap agentsmits-blog — initialize SQLite DB + verify deps.
# Replaces the old bootstrap.sh which hand-created 14 JSON files.
#
# Usage:
#   ./bootstrap.sh           # default: init-db only (idempotent)
#   ./bootstrap.sh --fresh   # wipe data/ first, then init-db
#
# ENV overrides:
#   AGENTSBLOG_ROOT          alternate project root
#   AGENTSBLOG_TELEGRAM_ACCOUNT / _TARGET — set Telegram publishing target
#   SKIP_PYTHON_CHECK=1      don't verify Python version
#   SKIP_OPENCLAW_CHECK=1    don't verify openclaw CLI (rare)

set -e

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || readlink "$0" 2>/dev/null || echo "$0")")" && pwd)}"
cd "$PROJECT_DIR"

echo "==> Bootstrapping agentsmits-blog in $PROJECT_DIR"

if [ "${1:-}" = "--fresh" ] && [ -d data ]; then
    echo "  --fresh: archiving existing data/ to data.bak.$(date +%s)"
    mv data "data.bak.$(date +%s)"
fi

mkdir -p data

# === Verify Python ===
if [ -z "${SKIP_PYTHON_CHECK:-}" ]; then
    if ! command -v python3 >/dev/null 2>&1 && ! command -v python >/dev/null 2>&1; then
        echo "  ✗ ERROR: Python 3 not found"
        exit 1
    fi
    PY=$(command -v python3 || command -v python)
    PY_VERSION=$("$PY" --version 2>&1 | head -1)
    echo "  ✓ Python: $PY_VERSION"
fi

# === Install package in editable mode (if not already) ===
if ! "$PY" -c "import agentsblog" 2>/dev/null; then
    echo "  Installing agentsblog package..."
    "$PY" -m pip install -e . 2>&1 | tail -3
fi

# === Initialize SQLite DB ===
echo "  Initializing SQLite database..."
"$PY" -m agentsblog init-db

# === Initialize other data files (idempotent) ===
echo "  Touching runtime files..."
for f in recently_sent.json sent_messages.json sync_status.json; do
    if [ ! -f "data/$f" ]; then
        case "$f" in
            *.json) echo '{}' > "data/$f" ;;
        esac
    fi
done
: > data/events.log 2>/dev/null || true
: > data/telegram_audit.log 2>/dev/null || true

# === Verify openclaw CLI ===
if [ -z "${SKIP_OPENCLAW_CHECK:-}" ]; then
    if ! command -v openclaw >/dev/null 2>&1; then
        echo "  ⚠ WARNING: 'openclaw' CLI not in PATH — Telegram publishing will fail."
        echo "    Install OpenClaw or set SKIP_OPENCLAW_CHECK=1 to silence."
    else
        echo "  ✓ openclaw CLI: $(openclaw --version 2>&1 | head -1)"
    fi
fi

echo ""
echo "==> Bootstrap complete."
echo ""
echo "    Next steps:"
echo "      1. Run a one-shot scan:    $PY -m agentsblog scan --dry-run"
echo "      2. See what's queued:      $PY -m agentsblog status"
echo "      3. Publish to Telegram:    $PY -m agentsblog publish --allow-during-quiet"
echo "      4. Build the static site:  $PY -m agentsblog build-site"
echo "      5. Add manually:           $PY -m agentsblog add-manual --help"
echo "      6. Set up cron (see README.md for recipes)"