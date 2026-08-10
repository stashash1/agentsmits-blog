#!/usr/bin/env python3
"""
Cluster narratives — batch job для narrative clustering.

Stage 2 (quality-news-analyst, 2026-08-10): M3+M5 из roadmap.
Запускается:
- One-shot backfill по существующим pending + recently_published.
- Cron каждые 6 часов для поддержания narratives в актуальном состоянии.

Использование:
    python3 pipeline/cluster_narratives.py                # full pass
    python3 pipeline/cluster_narratives.py --dry-run      # не сохранять
    python3 pipeline/cluster_narratives.py --limit 50     # только топ-50 items

Алгоритм:
1. Загрузить pending_queue.json (отфильтровать importance >= 3, чтобы не сортировать мусор).
2. Загрузить recently_published (за последние 7 дней).
3. Сортировать items по (importance desc, date desc) — топ-новости идут первыми.
4. Greedy clustering:
   - Если item.matches existing narrative (Jaccard >= 0.4) → attach as followup.
   - Иначе → create new narrative.
5. Сохранить narratives.json.
"""
from __future__ import annotations
import json
import os
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from _config import PENDING_QUEUE, SENT_MESSAGES
from impact_scoring import extract_entities_from_item
from narrative_store import (
    load_narratives, save_narratives,
    find_matching_narrative, create_narrative,
    attach_to_narrative, update_all_statuses, NARRATIVES_PATH,
)


def load_pending(min_importance: int = 3) -> list[dict]:
    with open(PENDING_QUEUE) as f:
        queue = json.load(f)
    pending = queue.get("pending", [])
    return [p for p in pending if (p.get("importance") or 0) >= min_importance]


def load_recently_published(days: int = 7) -> list[dict]:
    """Загружает recently_published из pending_queue.json (если есть)."""
    with open(PENDING_QUEUE) as f:
        queue = json.load(f)
    published = queue.get("published", [])
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    return [p for p in published if (p.get("published_at") or "") >= cutoff]


def cluster_batch(
    items: list[dict],
    narratives: list[dict],
    *,
    threshold: float = 0.4,
) -> tuple[list[dict], int, int]:
    """Принимает items + существующие narratives, возвращает (обновлённые narratives, новых, обновлённых)."""
    created = 0
    attached = 0
    # Sort: importance desc, then date desc — top stories first.
    items_sorted = sorted(items, key=lambda x: (
        -x.get("importance", 0),
        -(int((x.get("date", "") or "0000-00-00").replace("-", "")[:8]) if x.get("date") else 0),
    ))
    for item in items_sorted:
        entities = extract_entities_from_item(item)
        if not entities:
            continue
        match = find_matching_narrative(entities, narratives, threshold=threshold)
        if match:
            attach_to_narrative(match, item, role="followup")
            attached += 1
        else:
            new_n = create_narrative(item, entities=entities)
            narratives.append(new_n)
            created += 1
    return narratives, created, attached


def main():
    p = argparse.ArgumentParser(description="Cluster narratives (batch)")
    p.add_argument("--dry-run", action="store_true",
                   help="Не сохранять narratives.json")
    p.add_argument("--limit", type=int, default=0,
                   help="Ограничить количество items (0 = без лимита)")
    p.add_argument("--min-importance", type=int, default=3,
                   help="Минимальный importance для clustering")
    p.add_argument("--include-published", action="store_true",
                   help="Включить recently_published в clustering")
    p.add_argument("--published-days", type=int, default=7,
                   help="За сколько дней брать published (default=7)")
    args = p.parse_args()

    pending = load_pending(min_importance=args.min_importance)
    items = list(pending)
    if args.include_published:
        published = load_recently_published(days=args.published_days)
        items.extend(published)
    print(f"Items to cluster: {len(items)} (pending={len(pending)}, "
          f"published={'+' + str(len(published)) if args.include_published else 0})")

    if args.limit > 0:
        items = items[:args.limit]
        print(f"Limited to: {len(items)}")

    data = load_narratives()
    update_all_statuses(data)
    before_count = len(data["narratives"])

    narratives, created, attached = cluster_batch(items, data["narratives"])
    data["narratives"] = narratives
    after_count = len(data["narratives"])

    print(f"\n=== CLUSTERING RESULT ===")
    print(f"Narratives before: {before_count}")
    print(f"Narratives after: {after_count}")
    print(f"New narratives: {created}")
    print(f"Items attached: {attached}")
    print(f"Items skipped (no entities): {len(items) - created - attached}")

    # Top narratives
    from collections import Counter
    statuses = Counter(n.get("status", "?") for n in narratives)
    print(f"\nStatus distribution:")
    for s, c in statuses.most_common():
        print(f"  {s}: {c}")

    # Top 10 by size
    narrs_by_size = sorted(narratives, key=lambda x: -len(x.get("items", [])))
    print(f"\nTop 10 narratives by size:")
    for n in narrs_by_size[:10]:
        items_n = n.get("items", [])
        print(f"--- {n['id']} | {n.get('status', '?')} | n={len(items_n)} | "
              f"imp_max={n.get('importance_max', '?')} ---")
        print(f"  title: {n.get('title', '')[:80]}")
        print(f"  entities: {n.get('entities', [])[:8]}")
        for it in items_n[:3]:
            print(f"    [{it.get('importance')}|{it.get('source','')[:15]}] "
                  f"{it.get('title','')[:80]}")

    if args.dry_run:
        print("\n[DRY-RUN] Не сохраняю narratives.json")
        return

    save_narratives(data)
    print(f"\nSaved: {NARRATIVES_PATH}")


if __name__ == "__main__":
    main()