#!/bin/bash
# Legacy hourly sync → kept for backward compat.
# New setups should use `openclaw cron` or systemd timers calling pipeline/publish_post.py directly.
# This wrapper still works for older deployments.

set -e

BLOG_DIR="${BLOG_DIR:-$(cd "$(dirname "$(readlink -f "$0")")" && pwd)}"
cd "$BLOG_DIR"

# Regenerate site (data/ is already in the right place)
python3 generate_site.py

if [ -d .git ]; then
    git add public/ 2>/dev/null || true
    if ! git diff --cached --quiet; then
        git commit -m "Auto-sync: $(date '+%Y-%m-%d %H:%M')" || true
        REMOTE="${REMOTE:-origin}"
        git push "$REMOTE" main 2>/dev/null || echo "[$(date '+%H:%M:%S')] push failed"
    fi
fi
