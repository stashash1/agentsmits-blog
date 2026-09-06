#!/bin/bash
# Bootstrap agentsmits-blog on a fresh deployment.
# - Creates data/ from templates
# - Verifies Python + openclaw are available
# - Initializes pending_queue.json if missing
#
# Usage:
#   ./bootstrap.sh           # interactive
#   ./bootstrap.sh --fresh   # wipe data/ first
#
# ENV overrides:
#   AGENTSBLOG_DATA_DIR       alternate data dir
#   AGENTSBLOG_TELEGRAM_ACCOUNT / _TARGET — set Telegram publishing target
#   SKIP_OPENCLAW_CHECK=1     don't verify openclaw CLI (rare)

set -e

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "$(readlink -f "$0")")" && pwd)}"
cd "$PROJECT_DIR"

echo "==> Bootstrapping agentsmits-blog in $PROJECT_DIR"

if [ "${1:-}" = "--fresh" ] && [ -d data ]; then
    echo "  --fresh: archiving existing data/ to data.bak.$(date +%s)"
    mv data "data.bak.$(date +%s)"
fi

mkdir -p data

# === Minimal pending_queue.json scaffold ===
if [ ! -f data/pending_queue.json ]; then
    echo "  creating data/pending_queue.json (empty queue)"
    cat > data/pending_queue.json <<'EOF'
{
  "sources": [],
  "pending": [],
  "published": [],
  "agi_counter": {
    "base_days": 1460,
    "current_days": 730,
    "start_date": "2026-01-01",
    "last_update": null
  }
}
EOF
fi

# === selection queue scaffold ===
if [ ! -f data/selection_queue.json ]; then
    echo "  creating data/selection_queue.json"
    echo '{"description": "Top articles awaiting deep analysis", "articles": []}' > data/selection_queue.json
fi

# === articles queue scaffold ===
if [ ! -f data/articles_queue.json ]; then
    echo "  creating data/articles_queue.json"
    echo '{"articles": []}' > data/articles_queue.json
fi

# === current.json + archive.json (site storage) ===
if [ ! -f data/current.json ]; then
    echo "  creating data/current.json (empty week)"
    python3 -c "import json,datetime; print(json.dumps({'week_start': datetime.date.today().isoformat(), 'posts': []}, indent=2, ensure_ascii=False))" > data/current.json
fi
if [ ! -f data/archive.json ]; then
    echo "  creating data/archive.json"
    echo '{"archive": []}' > data/archive.json
fi

# === Runtime logs (start empty) ===
for f in metrics.json events.log telegram_audit.log recently_sent.json sent_messages.json sync_status.json daily_summaries.json; do
    if [ ! -f "data/$f" ]; then
        case "$f" in
            *.log)            : > "data/$f" ;;
            *.json)           echo '{}' > "data/$f" ;;
        esac
        echo "  touched data/$f"
    fi
done

# === Verify openclaw CLI ===
if [ -z "${SKIP_OPENCLAW_CHECK:-}" ]; then
    if ! command -v openclaw >/dev/null 2>&1; then
        echo "  ⚠ WARNING: 'openclaw' CLI not in PATH — Telegram publishing will fail."
        echo "    Install OpenClaw or set SKIP_OPENCLAW_CHECK=1 to silence."
    else
        echo "  ✓ openclaw CLI available: $(openclaw --version 2>&1 | head -1)"
    fi
fi

# === Verify Python stdlib is enough ===
if ! python3 -c "import urllib.request, json, fcntl, hashlib, re" 2>/dev/null; then
    echo "  ✗ ERROR: Python stdlib missing modules (urllib/json/fcntl/hashlib/re)"
    exit 1
fi
echo "  ✓ Python stdlib OK"

echo ""
echo "==> Bootstrap complete."
echo "    Next steps:"
echo "      1. Edit data/pending_queue.json → sources[] (URLs you want to monitor)"
echo "      2. Verify Telegram: AGENTSBLOG_TELEGRAM_ACCOUNT / _TARGET env vars (or edit pipeline/_config.py defaults)"
echo "      3. Run a one-shot scan:    python3 pipeline/scan_sources.py"
echo "      4. Run a one-shot publish: python3 pipeline/publish_post.py --dry-run"
echo "      5. Set up scheduled runs:  see deploy/README.md or README.md"
