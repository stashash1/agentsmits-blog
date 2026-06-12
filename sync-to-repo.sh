#!/bin/bash
# Syncs JSON data files to git and pushes to trigger CI rebuild
# Run via cron: 0 * * * * /home/stas/.openclaw/workspace-channel/agentsmits-blog/sync-to-repo.sh

set -e

BLOG_DIR="/home/stas/.openclaw/workspace-channel/agentsmits-blog"
DATA_DIR="/home/stas/.openclaw/workspace/projects/telegram-ai-channel"
BOT_DIR="/home/stas/dev/project/agentsmits-bot"
REMOTE="git@github.com:stashash1/agentsmits-blog.git"

cd "$BLOG_DIR"

# Copy scanner queue files
cp "$DATA_DIR/pending_queue.json" ./pending_queue.json
cp "$DATA_DIR/selection_queue.json" ./selection_queue.json

# Copy bot storage (current + archive posts with full content)
mkdir -p "$BOT_DIR/data"
cp "$BOT_DIR/data/current.json" ./ 2>/dev/null || true
cp "$BOT_DIR/data/archive.json" ./ 2>/dev/null || true

# Check if anything changed
if ! git diff --quiet pending_queue.json selection_queue.json current.json archive.json 2>/dev/null; then
    git add pending_queue.json selection_queue.json current.json archive.json
    git commit -m "Auto-sync: $(date '+%Y-%m-%d %H:%M')"
    git push "$REMOTE" main
    echo "[$(date)] Pushed updates to GitHub"
else
    echo "[$(date)] No changes in JSON files"
fi
