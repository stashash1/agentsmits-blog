#!/usr/bin/env python3
"""Одноразовый скрипт: оставить в pending только записи с date >= cutoff.

Делается по запросу Стаса (2026-07-26):
  - Не публиковать накопившиеся посты.
  - Начать с сегодня минус 1 день (по умолчанию 2026-07-25).

Запускается как:  python3 scripts/_cleanup_pending.py [--cutoff YYYY-MM-DD]

Рядом с pending_queue.json создаётся .bak со старым содержимым.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "pipeline"))
from _config import PENDING_QUEUE  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cutoff", default="2026-07-25",
                   help="Минимальная дата статьи (включительно). По умолчанию 2026-07-25.")
    args = p.parse_args()
    cutoff = date.fromisoformat(args.cutoff)

    with open(PENDING_QUEUE) as f:
        q = json.load(f)

    pending = q.get("pending", [])
    before = len(pending)

    keep, drop = [], []
    for item in pending:
        d = item.get("date")
        try:
            item_date = date.fromisoformat(d) if d else None
        except (TypeError, ValueError):
            item_date = None
        if item_date and item_date >= cutoff:
            keep.append(item)
        else:
            drop.append(item)

    q["pending"] = keep
    q.setdefault("_cleanup", {})["last_run"] = {
        "cutoff": args.cutoff,
        "kept": len(keep),
        "dropped": len(drop),
        "before": before,
        "after": len(keep),
    }
    # Samples для отчёта: какие даты у дропнутых
    from collections import Counter
    drop_dates = Counter()
    for it in drop:
        d = it.get("date") or "?"
        drop_dates[d] += 1
    q["_cleanup"]["dropped_by_date"] = dict(sorted(drop_dates.items()))

    bak = PENDING_QUEUE.with_suffix(".json.bak")
    if not bak.exists():
        import shutil
        shutil.copy2(PENDING_QUEUE, bak)
        backup_created = str(bak)
    else:
        backup_created = f"{bak} (уже существовал, не перезаписан)"

    with open(PENDING_QUEUE, "w") as f:
        json.dump(q, f, indent=2, ensure_ascii=False)

    print(f"OK: {before} -> {len(keep)} (cutoff={args.cutoff})")
    print(f"  dropped_by_date: {dict(sorted(drop_dates.items()))}")
    print(f"  backup: {backup_created}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
