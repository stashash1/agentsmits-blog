#!/usr/bin/env python3
"""
Narrative store — load/save/match narratives для pending items.

Stage 2 (quality-news-analyst, 2026-08-10): narrative clustering.
Объединяет новости по entity overlap в "истории" (narratives).

Использование:
    from narrative_store import load_narratives, save_narratives, find_matching, attach_item

Структура data/narratives.json:
{
  "schema_version": 1,
  "updated_at": "...",
  "narratives": [
    {
      "id": "n-001",
      "title": "Claude Code обновления",
      "status": "active",       # active | cooling | dormant
      "first_seen": "2026-08-01",
      "last_seen": "2026-08-10",
      "entities": ["claude", "anthropic", "claude-code"],
      "items": [
        {"item_id": "...", "role": "primary", "attached_at": "..."},
        ...
      ],
      "source": "auto",
      "importance_max": 4
    }
  ]
}

Jaccard threshold: 0.4 (см. spike 2026-08-10-narrative-clustering).
"""
from __future__ import annotations
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterable

sys.path.insert(0, os.path.dirname(__file__))
from _config import DATA_DIR
from impact_scoring import extract_entities_from_item


NARRATIVES_PATH = Path(DATA_DIR) / "narratives.json"

# Counter для генерации narrative ID (sequence, не timestamp — иначе
# коллизии в один и тот же миллисекундный интервал).
_NARRATIVE_COUNTER = None

def _next_narrative_id() -> str:
    global _NARRATIVE_COUNTER
    if _NARRATIVE_COUNTER is None:
        # Init from max existing ID
        try:
            data = load_narratives()
            max_n = 0
            for n in data.get("narratives", []):
                m = n.get("id", "")
                if m.startswith("n-"):
                    try:
                        max_n = max(max_n, int(m[2:]))
                    except ValueError:
                        pass
            _NARRATIVE_COUNTER = max_n
        except Exception:
            _NARRATIVE_COUNTER = 0
    _NARRATIVE_COUNTER += 1
    return f"n-{_NARRATIVE_COUNTER:05d}"

# Threshold для Jaccard overlap — найден через spike на 163 items,
# даёт реальные нарративы (n>=2) без ложных слияний.
JACCARD_THRESHOLD = 0.4

# Generic entities, которые НЕ участвуют в Jaccard (слишком шумные, появляются
# везде в AI-новостях). Используются для scoring/narrative metadata, но не для
# clustering — иначе все новости кластеризуются вокруг "agent"/"ai".
GENERIC_ENTITIES = frozenset({
    "agent", "agents", "agentic", "ai", "ai-",
    "open source", "open-source", "benchmark", "sota",
    "rag", "embedding", "reasoning", "multimodal",
    "robot", "robotics", "autonomous",
    "safety", "alignment",
})

# Narrative status по Δt от last_seen:
NARRATIVE_COOLING_DAYS = 3    # >3d → cooling
NARRATIVE_DORMANT_DAYS = 14   # >14d → dormant


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_dt() -> datetime:
    return datetime.now(timezone.utc)


def load_narratives() -> dict:
    """Load narratives.json. Если файл не существует — возвращает пустую структуру."""
    if not NARRATIVES_PATH.exists():
        return {"schema_version": 1, "updated_at": _now_iso(), "narratives": []}
    try:
        with open(NARRATIVES_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # Corrupted file — backup и start fresh
        backup = NARRATIVES_PATH.with_suffix(".corrupt.bak")
        try:
            NARRATIVES_PATH.rename(backup)
        except OSError:
            pass
        return {"schema_version": 1, "updated_at": _now_iso(), "narratives": []}


def save_narratives(data: dict) -> None:
    """Atomic save narratives.json (tmp → rename)."""
    data["updated_at"] = _now_iso()
    tmp = NARRATIVES_PATH.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(NARRATIVES_PATH)


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s.replace("Z", "+00:00") if "T" in s and s.endswith("Z") else s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def narrative_status(last_seen: str, now: datetime | None = None) -> str:
    """active (≤3d), cooling (3-14d), dormant (>14d)."""
    now = now or _now_dt()
    last = _parse_date(last_seen)
    if not last:
        return "active"
    delta = now - last
    if delta.days > NARRATIVE_DORMANT_DAYS:
        return "dormant"
    if delta.days > NARRATIVE_COOLING_DAYS:
        return "cooling"
    return "active"


def _specific_entities(entities: Iterable[str]) -> set[str]:
    """Убирает generic entities из набора (для Jaccard clustering).
    Generic entities используются для narrative metadata, но НЕ для matching.
    """
    return {e.lower() for e in entities if e and e.lower() not in GENERIC_ENTITIES}


def find_matching_narrative(
    entities: Iterable[str],
    narratives: list[dict],
    *,
    threshold: float = JACCARD_THRESHOLD,
    only_status: tuple[str, ...] = ("active", "cooling"),
) -> dict | None:
    """Находит существующий narrative с Jaccard ≥ threshold.
    Использует только SPECIFIC entities (без GENERIC_ENTITIES) — иначе
    'agent'/'ai' появляются везде и кластеризуют всё в один нарратив.
    Возвращает best match (highest Jaccard) или None.
    """
    entities_set = _specific_entities(entities)
    if not entities_set:
        return None
    best = None
    best_score = 0.0
    for n in narratives:
        if n.get("status") and n["status"] not in only_status:
            continue
        n_ents = _specific_entities(n.get("entities", []))
        if not n_ents:
            continue
        score = jaccard(entities_set, n_ents)
        if score >= threshold and score > best_score:
            best = n
            best_score = score
    return best


def attach_to_narrative(
    narrative: dict,
    item: dict,
    role: str = "followup",
) -> None:
    """Добавляет item в narrative. Mutates narrative in-place.
    role: primary (создатель нарратива), followup (расширение), reaction (комментарий).
    """
    item_id = item.get("id")
    if not item_id:
        return
    # Дедуп — не добавлять дважды
    if any(it.get("item_id") == item_id for it in narrative.get("items", [])):
        return
    narrative.setdefault("items", []).append({
        "item_id": item_id,
        "role": role,
        "attached_at": _now_iso(),
        "title": item.get("title", "")[:200],
        "source": item.get("source", ""),
        "importance": item.get("importance"),
    })
    narrative["last_seen"] = _now_iso()
    narrative["status"] = "active"
    # Update entities — union
    existing_ents = set(narrative.get("entities", []))
    new_ents = set(extract_entities_from_item(item))
    narrative["entities"] = sorted(existing_ents | new_ents)
    # Update importance_max
    narrative["importance_max"] = max(
        narrative.get("importance_max", 0),
        item.get("importance") or 0,
    )


def create_narrative(item: dict, entities: list[str] | None = None) -> dict:
    """Создаёт новый narrative для item."""
    ents = entities or extract_entities_from_item(item)
    n_id = _next_narrative_id()
    return {
        "id": n_id,
        "title": (item.get("title", "") or "")[:120],
        "status": "active",
        "first_seen": _now_iso(),
        "last_seen": _now_iso(),
        "entities": sorted(ents),
        "items": [{
            "item_id": item.get("id"),
            "role": "primary",
            "attached_at": _now_iso(),
            "title": (item.get("title", "") or "")[:200],
            "source": item.get("source", ""),
            "importance": item.get("importance"),
        }],
        "source": "auto",
        "importance_max": item.get("importance") or 0,
    }


def update_all_statuses(data: dict, now: datetime | None = None) -> int:
    """Пересчитывает status у всех narratives. Возвращает количество обновлённых."""
    now = now or _now_dt()
    updated = 0
    for n in data.get("narratives", []):
        old = n.get("status")
        new = narrative_status(n.get("last_seen", ""), now=now)
        if old != new:
            n["status"] = new
            updated += 1
    return updated


# ============================================================
# CLI: отчёт по narratives
# ============================================================

def main():
    import argparse
    p = argparse.ArgumentParser(description="Inspect narratives.json")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--status", choices=["active", "cooling", "dormant", "all"], default="all")
    args = p.parse_args()

    data = load_narratives()
    update_all_statuses(data)
    save_narratives(data)

    narrs = data.get("narratives", [])
    print(f"Total narratives: {len(narrs)}")
    from collections import Counter
    statuses = Counter(n.get("status", "?") for n in narrs)
    for s, c in statuses.most_common():
        print(f"  {s}: {c}")

    if args.status != "all":
        narrs = [n for n in narrs if n.get("status") == args.status]

    print(f"\nTop {args.limit} narratives by size:")
    narrs.sort(key=lambda x: -len(x.get("items", [])))
    for n in narrs[:args.limit]:
        items = n.get("items", [])
        print(f"--- {n['id']} | {n.get('status', '?')} | n={len(items)} | "
              f"imp_max={n.get('importance_max', '?')} ---")
        print(f"  title: {n.get('title', '')[:90]}")
        print(f"  entities: {n.get('entities', [])[:8]}")
        for it in items[:3]:
            print(f"  - [{it.get('importance')}|{it.get('source','')[:15]}] "
                  f"{it.get('title','')[:80]}")
        if len(items) > 3:
            print(f"  ... +{len(items) - 3} more")


if __name__ == "__main__":
    main()