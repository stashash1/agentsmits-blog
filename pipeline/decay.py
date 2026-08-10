#!/usr/bin/env python3
"""
Decay & freshness — temporal half-life scoring для pending items.

QW2 (quality-news-analyst, 2026-08-10): tier-based half-life.
Tier-1 source (Anthropic/OpenAI/DeepMind/etc) — важные новости живут 7 дней.
Tier-2 — 5 дней. Tier-3 — 3 дня.

Использование:
    from decay import decayed_importance, apply_decay_to_pending
    score = decayed_importance(item)  # float
    # batch (аннотирует pending):
    apply_decay_to_pending(pending)

exp-decay формула (мягкая, с MIN_DECAY_FACTOR floor):
    decayed = max(MIN_DECAY_FACTOR, importance * 0.5 ** (Δt_days / half_life))
    clamped to [0, 5]

Используется в publish_post.py как soft signal (sort by decayed_importance),
НЕ как hard filter — старые новости не скипаются, а имеют более низкий приоритет.
"""
from __future__ import annotations
import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from impact_scoring import get_source_tier  # already implemented
from _config import PENDING_QUEUE


# Tier → half-life (days). Чем меньше, тем быстрее новость "протухает".
TIER_HALF_LIFE_DAYS = {
    1: 7,   # Anthropic/OpenAI/DeepMind/etc — важные события живут неделю
    2: 5,   # Cohere/Perplexity/Copilot/Cursor — пол-недели
    3: 3,   # arXiv/TechCrunch/etc — исследование и индустрия — короткий цикл
}

# Минимальный decay factor — даже очень старые новости не падают ниже этого.
# 0.3 = "старая новость всё ещё может быть опубликована, но с самым низким приоритетом".
MIN_DECAY_FACTOR = 0.3


def tier_half_life_days(tier: int) -> float:
    return TIER_HALF_LIFE_DAYS.get(tier, 3)


def _parse_date(s: str | None) -> datetime | None:
    """Парсит ISO date/datetime. Возвращает tz-aware UTC."""
    if not s:
        return None
    s = str(s).strip()
    # Поддержка YYYY-MM-DD
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.replace("Z", "+00:00") if "T" in s and s.endswith("Z") else s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def decayed_importance(item: dict, now: datetime | None = None) -> float:
    """Возвращает float: importance × exp-decay(Δt / half_life).
    Clamp [0, 5].
    """
    now = now or datetime.now(timezone.utc)
    base = item.get("importance") or 0
    if base <= 0:
        return 0.0

    source = item.get("source") or ""
    tier = get_source_tier(source)
    half_life = tier_half_life_days(tier)

    # Anchor date: prefer 'date' (article date), fallback 'scraped_at'/'added_at'
    pub_date = _parse_date(item.get("date"))
    if pub_date is None:
        pub_date = _parse_date(item.get("scraped_at"))
    if pub_date is None:
        pub_date = _parse_date(item.get("analyzed_at"))
    if pub_date is None:
        # No date known → assume fresh, no decay
        return float(min(base, 5))

    delta_days = max(0.0, (now - pub_date).total_seconds() / 86400.0)
    raw = base * (0.5 ** (delta_days / half_life))
    # Floor: даже очень старые новости сохраняют минимальный вес.
    decayed = max(base * MIN_DECAY_FACTOR, raw)
    return max(0.0, min(5.0, decayed))


def decay_breakdown(item: dict, now: datetime | None = None) -> dict:
    """Debug: возвращает dict с полным разбором decay для observability."""
    now = now or datetime.now(timezone.utc)
    base = item.get("importance") or 0
    source = item.get("source") or ""
    tier = get_source_tier(source)
    half_life = tier_half_life_days(tier)
    pub_date = _parse_date(item.get("date"))
    delta_days = 0.0
    if pub_date:
        delta_days = max(0.0, (now - pub_date).total_seconds() / 86400.0)
    decayed = decayed_importance(item, now=now)
    return {
        "base": base,
        "tier": tier,
        "source": source,
        "half_life_days": half_life,
        "publish_date": pub_date.isoformat() if pub_date else None,
        "delta_days": round(delta_days, 2),
        "decayed": round(decayed, 3),
    }


def apply_decay_to_pending(pending: list[dict], now: datetime | None = None) -> list[dict]:
    """Аннотирует каждый item полем 'decay' (breakdown + decayed_importance).
    Mutates items in-place. Возвращает тот же список для convenience.
    """
    now = now or datetime.now(timezone.utc)
    for item in pending:
        bd = decay_breakdown(item, now=now)
        item["decay"] = bd
        item["decayed_importance"] = bd["decayed"]
    return pending


# ============================================================
# CLI: dry-run отчёт
# ============================================================

def main():
    import argparse
    p = argparse.ArgumentParser(description="Apply decay to pending_queue.json")
    p.add_argument("--dry-run", action="store_true",
                   help="Show decay stats without writing")
    p.add_argument("--threshold", type=float, default=3.0,
                   help="Mark items below this decayed_importance as 'would_skip'")
    p.add_argument("--limit", type=int, default=30,
                   help="Show top N most-decayed items")
    args = p.parse_args()

    if not PENDING_QUEUE.exists():
        print(f"ERROR: {PENDING_QUEUE} not found")
        sys.exit(1)

    with open(PENDING_QUEUE) as f:
        queue = json.load(f)

    pending = queue.get("pending", [])
    print(f"Pending items: {len(pending)}")

    now = datetime.now(timezone.utc)
    apply_decay_to_pending(pending, now=now)

    # Distribution
    decayed_scores = [round(item.get("decayed_importance", 0), 2) for item in pending]
    bins = {"4-5": 0, "3-4": 0, "2-3": 0, "1-2": 0, "0-1": 0}
    for s in decayed_scores:
        if s >= 4: bins["4-5"] += 1
        elif s >= 3: bins["3-4"] += 1
        elif s >= 2: bins["2-3"] += 1
        elif s >= 1: bins["1-2"] += 1
        else: bins["0-1"] += 1
    print("Decayed distribution:")
    for k, v in bins.items():
        print(f"  {k}: {v}")

    # Items that would be skipped by QW4+decay
    would_skip = sum(1 for item in pending
                     if (item.get("importance") or 0) >= 3
                     and item.get("decayed_importance", 0) < args.threshold)
    would_publish = sum(1 for item in pending
                        if (item.get("importance") or 0) >= 3
                        and item.get("decayed_importance", 0) >= args.threshold)
    print(f"\nWith QW4 (importance>=3) + decay threshold={args.threshold}:")
    print(f"  Would publish: {would_publish}")
    print(f"  Would skip (decayed): {would_skip}")

    # Top N most decayed
    print(f"\nTop {args.limit} most-decayed items (current importance -> decayed):")
    sorted_items = sorted(pending, key=lambda x: x.get("decayed_importance", 0))
    for item in sorted_items[:args.limit]:
        bd = item["decay"]
        print(f"  imp={bd['base']}→{bd['decayed']:.2f} | "
              f"Δt={bd['delta_days']}d | tier={bd['tier']} | "
              f"{bd['source'][:18]} | {item.get('title','')[:70]}")

    if not args.dry_run:
        # Save
        queue["pending"] = pending
        # Backup
        backup = str(PENDING_QUEUE) + ".bak.pre-decay-2026-08-10"
        if not Path(backup).exists():
            with open(PENDING_QUEUE) as f:
                original = f.read()
            with open(backup, "w") as f:
                f.write(original)
            print(f"\nBackup: {backup}")
        with open(PENDING_QUEUE, "w") as f:
            json.dump(queue, f, ensure_ascii=False, indent=2)
        print(f"Saved: {PENDING_QUEUE}")


if __name__ == "__main__":
    main()