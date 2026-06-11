#!/bin/bash
# Скрипт для автодеплоя блога: генерирует сайт и пушит на GitHub

set -e

BLOG_DIR="/home/stas/.openclaw/workspace/projects/ai-blog"
cd "$BLOG_DIR"

# Копируем актуальные данные из telegram-ai-channel
cp ../telegram-ai-channel/pending_queue.json ./pending_queue.json
cp ../telegram-ai-channel/selection_queue.json ./selection_queue.json

# Генерируем сайт
python3 generate_site.py

# Коммитим и пушим
git add .
git commit -m "Auto-deploy: $(date '+%Y-%m-%d %H:%M')" || true
git push origin main 2>/dev/null || echo "No remote configured or nothing to push"