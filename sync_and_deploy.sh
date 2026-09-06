#!/bin/bash
# Build the static site + (optionally) push to git remote.
# Default: regenerate only. Set PUSH=1 to git commit + push.

set -e

BLOG_DIR="${BLOG_DIR:-$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || readlink "$0" 2>/dev/null || echo "$0")")" && pwd)}"
cd "$BLOG_DIR"

PY=$(command -v python3 || command -v python)

echo "[$(date '+%H:%M:%S')] regenerating site..."
"$PY" -m agentsblog build-site

if [ "${PUSH:-0}" = "1" ]; then
    git add public/ data/blog.db 2>/dev/null || git add public/
    if ! git diff --cached --quiet 2>/dev/null; then
        git commit -m "Auto-deploy: $(date '+%Y-%m-%d %H:%M')" || true
        git push origin main 2>/dev/null || echo "[$(date '+%H:%M:%S')] no remote configured"
        echo "[$(date '+%H:%M:%S')] pushed"
    else
        echo "[$(date '+%H:%M:%S')] nothing to push"
    fi
fi

echo "[$(date '+%H:%M:%S')] done"