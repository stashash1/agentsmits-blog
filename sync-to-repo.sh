#!/bin/bash
# Syncs JSON data files to git and pushes to trigger CI rebuild
# Run via cron: 0 * * * * /home/stas/.openclaw/workspace-channel/agentsmits-blog/sync-to-repo.sh

set -e

BLOG_DIR="/home/stas/.openclaw/workspace-channel/agentsmits-blog"
DATA_DIR="/home/stas/.openclaw/workspace/projects/telegram-ai-channel"
REMOTE="git@github.com:stashash1/agentsmits-blog.git"

cd "$BLOG_DIR"

# Copy latest JSON from data dir
cp "$DATA_DIR/pending_queue.json" ./pending_queue.json
cp "$DATA_DIR/selection_queue.json" ./selection_queue.json

# Check if anything changed
if ! git diff --quiet pending_queue.json selection_queue.json 2>/dev/null; then
    git add pending_queue.json selection_queue.json
    git commit -m "Auto-sync: $(date '+%Y-%m-%d %H:%M')"
    git push "$REMOTE" main
    echo "[$(date)] Pushed JSON updates to GitHub"
else
    echo "[$(date)] No changes in JSON files"
fi
