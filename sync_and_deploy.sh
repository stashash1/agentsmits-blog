#!/bin/bash
# Sync latest data + regenerate site, optionally push to git remote.
# Default: regenerate only. Set PUSH=1 to git commit + push.

set -e

BLOG_DIR="${BLOG_DIR:-$(cd "$(dirname "$(readlink -f "$0")")" && pwd)}"
cd "$BLOG_DIR"

echo "[$(date '+%H:%M:%S')] regenerating site..."
python3 generate_site.py

if [ "${PUSH:-0}" = "1" ]; then
    git add data/current.json data/archive.json public/ 2>/dev/null || git add public/
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "Auto-deploy: $(date '+%Y-%m-%d %H:%M')" || true
        git push origin main 2>/dev/null || echo "[$(date '+%H:%M:%S')] no remote configured"
        echo "[$(date '+%H:%M:%S')] pushed"
    else
        echo "[$(date '+%H:%M:%S')] nothing to push"
    fi
fi

echo "[$(date '+%H:%M:%S')] done"
