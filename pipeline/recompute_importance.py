#!/usr/bin/env python3
"""
Recompute importance для всех pending items в pending_queue.json
на основе AI Impact Scoring (impact_scoring.py).

Использование:
    python3 scripts/recompute_importance.py
    python3 scripts/recompute_importance.py --dry-run
    python3 scripts/recompute_importance.py --verbose
    python3 scripts/recompute_importance.py --limit 10
"""

from _config import PENDING_QUEUE as QUEUE_FILE

import sys
import os
import json
import argparse
from pathlib import Path

# Добавляем scripts/ в PYTHONPATH
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

try:
    from impact_scoring import compute_impact
except ImportError as e:
    print(f"ERROR: import impact_scoring failed: {e}", file=sys.stderr)
    sys.exit(1)



def main():
    parser = argparse.ArgumentParser(
        description="Backfill importance для pending items через AI Impact Scoring."
    )
    parser.add_argument("--dry-run", action="store_true", help="Не сохранять изменения")
    parser.add_argument("--verbose", action="store_true", help="Показывать каждое изменение")
    parser.add_argument("--limit", type=int, default=0, help="Лимит items (0 = все)")
    args = parser.parse_args()

    if not QUEUE_FILE.exists():
        print(f"ERROR: {QUEUE_FILE} not found", file=sys.stderr)
        sys.exit(1)

    # Backup (если не dry-run и бэкап ещё не существует)
    if not args.dry_run:
        backup = QUEUE_FILE.with_suffix(".json.bak-recompute")
        if not backup.exists():
            import shutil
            shutil.copy2(QUEUE_FILE, backup)
            print(f"Backup created: {backup}")

    with open(QUEUE_FILE, encoding="utf-8") as f:
        queue = json.load(f)

    pending = queue.get("pending", [])
    print(f"Pending items: {len(pending)}")

    if args.limit:
        pending = pending[: args.limit]
        print(f"Processing first {args.limit}")

    changes = []
    for item in pending:
        old_imp = item.get("importance", 0)
        title = item.get("title", "")
        summary = item.get("summary", "")
        source = item.get("source", "")

        result = compute_impact(title=title, summary=summary, source=source)
        new_imp = result.total

        item["importance"] = new_imp
        item["ai_impact"] = result.to_dict()

        if old_imp != new_imp:
            changes.append(
                {
                    "id": item.get("id", "?")[:40],
                    "source": source,
                    "title": title[:60],
                    "old": old_imp,
                    "new": new_imp,
                }
            )
            if args.verbose:
                print(f"  {old_imp}→{new_imp}  {source:20}  {title[:60]}")

    print(f"\nChanged: {len(changes)}/{len(pending)}")

    if changes:
        # Distribution
        from collections import Counter
        new_dist = Counter(item["importance"] for item in pending)
        old_dist = Counter(c["old"] for c in changes)
        print(f"\nNew importance distribution:")
        for k in sorted(new_dist.keys(), reverse=True):
            print(f"  importance={k}: {new_dist[k]}")
        print(f"\nTop 10 biggest changes (old → new):")
        biggest = sorted(changes, key=lambda c: abs(c["new"] - c["old"]), reverse=True)[:10]
        for c in biggest:
            print(f"  {c['old']}→{c['new']}  {c['source']:20}  {c['title']}")

    if args.dry_run:
        print("\n[dry-run] Not saved")
    else:
        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to {QUEUE_FILE}")


if __name__ == "__main__":
    main()
