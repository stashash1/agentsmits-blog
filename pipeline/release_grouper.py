#!/usr/bin/env python3
"""
Release grouper — объединяет несколько релизов одного источника в один пост-дайджест.

Проблема: Claude Code 2.1.218 → 2.1.222 → 2.1.237 → 2.1.240 → 2.1.241,
GitHub Copilot changelog (по 1-2 записи в неделю), Cursor changelog — каждый
релиз публикуется как отдельный пост. Вместо этого делаем один пост-дайджест:

  📦 Дайджест релизов Claude Code
  Версии 2.1.237 → 2.1.241 за последние 3 дня

  • 2.1.241 — <перевод-саммари>
  • 2.1.240 — <перевод-саммари>
  ...

Использование:
    from release_grouper import group_releases
    groups, singles = group_releases(items)
    # groups: list[list[item]] — каждая группа = 2+ релизов одного источника
    # singles: list[item] — то, что не попало в группы

Детект «релиз-паттерна» по 3 сигналам (любой один триггерит):
1. Title содержит версию (`v?N.N(.N)?` или `N.N.N`) + типичные слова (release, update)
2. URL содержит `/changelog/`, `/release`, `/releases/`, `CHANGELOG`
3. Source ∈ KNOWN_RELEASE_SOURCES (Claude Code, GitHub Copilot, Cursor, ...)

QW-3 (quality-news, 2026-08-25): добавлен release-grouper для уменьшения
шума от версионных changelog-новостей в канале.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import dataclass, field


# Источники, которые ВСЕГДА считаются релизами (даже без версии в title)
KNOWN_RELEASE_SOURCES = frozenset({
    "claude code",
    "github copilot",
    "cursor",
    "openai codex",  # если будет
})

# Источники, которые НЕ группируем как релизы (научный/продуктовый контент)
NON_RELEASE_SOURCES = frozenset({
    "arxiv cs.ai",
    "techcrunch ai",
    "justai",
    "neural digest",
    "stanford hai",
})


# Паттерны для детекта релиза в title/URL
# - Версия: v1.0, 1.0.0, 2.1.241, 1.0.0-rc1, etc.
# - Ключевые слова: release, update, version, changelog, hotfix
_VERSION_PATTERN = re.compile(
    r"\b[vV]?\d+\.\d+(?:\.\d+)?(?:[-+][\w.]+)?\b"
)
_RELEASE_KEYWORDS = re.compile(
    r"\b(?:release|releases|released|update|changelog|hotfix|patch|version|новост[ьи]|верс\w*|обновлен\w*|релиз)\b",
    re.IGNORECASE,
)

# URL-паттерны
_RELEASE_URL_PATTERN = re.compile(
    r"/(?:changelog|release|releases|CHANGELOG|version|versions)/",
    re.IGNORECASE,
)


@dataclass
class ReleaseGroup:
    """Группа релизов одного источника."""
    source: str
    items: list[dict] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def max_importance(self) -> int:
        return max((it.get("importance") or 0) for it in self.items)

    @property
    def dates(self) -> list[str]:
        return [it.get("date", "") for it in self.items if it.get("date")]

    @property
    def earliest_date(self) -> str:
        ds = [d for d in self.dates if d]
        return min(ds) if ds else ""

    @property
    def latest_date(self) -> str:
        ds = [d for d in self.dates if d]
        return max(ds) if ds else ""

    def extract_versions(self) -> list[str]:
        """Извлекает версии из title каждого item, отсортированные как строки."""
        versions = []
        for it in self.items:
            t = it.get("title", "") or ""
            m = _VERSION_PATTERN.findall(t)
            for v in m:
                # strip leading 'v'/'V'
                vv = v.lstrip("vV")
                if vv not in versions:
                    versions.append(vv)
        return versions


def is_release_item(item: dict) -> bool:
    """Один item — релиз? True если триггерится любой из 3 сигналов."""
    if not isinstance(item, dict):
        return False

    source = (item.get("source") or "").strip().lower()
    if source in NON_RELEASE_SOURCES:
        return False
    if source in KNOWN_RELEASE_SOURCES:
        return True

    title = item.get("title") or ""
    url = item.get("url") or ""

    # Signal 2: URL содержит changelog/release
    if _RELEASE_URL_PATTERN.search(url):
        return True

    # Signal 1: title содержит версию + ключевое слово
    has_version = bool(_VERSION_PATTERN.search(title))
    has_keyword = bool(_RELEASE_KEYWORDS.search(title))
    if has_version and has_keyword:
        return True

    # Signal 1b: версия + summary содержит ключевое слово
    summary = item.get("summary") or ""
    if has_version and _RELEASE_KEYWORDS.search(summary):
        return True

    return False


def group_releases(items: list[dict], *, min_group_size: int = 2) -> tuple[list[ReleaseGroup], list[dict]]:
    """Группирует релизы одного источника.

    Возвращает (groups, singles):
      groups — список ReleaseGroup, каждый ≥ min_group_size items
      singles — items, которые НЕ попали ни в одну группу (включая релизы-одиночки)

    Параметры:
      items: список pending items
      min_group_size: минимальный размер группы для объединения (default=2).
                      Группы из 1 элемента возвращаются в singles.

    Логика:
      1. Отфильтровать только release-items.
      2. Сгруппировать по source (case-insensitive).
      3. Отсортировать внутри каждой группы по date desc (свежее первым).
      4. Группы ≥ min_group_size → в groups, иначе → в singles.
    """
    by_source: dict[str, list[dict]] = defaultdict(list)
    singles: list[dict] = []
    non_release: list[dict] = []

    for it in items:
        if is_release_item(it):
            src = (it.get("source") or "").strip()
            by_source[src].append(it)
        else:
            non_release.append(it)

    groups: list[ReleaseGroup] = []
    for src, items_list in by_source.items():
        # Sort newest first
        items_list.sort(key=lambda x: (x.get("date") or ""), reverse=True)
        if len(items_list) >= min_group_size:
            groups.append(ReleaseGroup(source=src, items=items_list))
        else:
            # single release → put back to singles
            singles.extend(items_list)

    # Sort groups by max_importance desc, then count desc, then source
    groups.sort(key=lambda g: (-g.max_importance, -g.count, g.source))

    singles = non_release + singles  # non-release всегда идут в singles

    return groups, singles


def make_digest_post(group: ReleaseGroup, importance_override: int | None = None) -> dict:
    """Создаёт синтетический «пост-дайджест» из группы релизов.

    Возвращает dict, который можно подставить в to_publish как обычный item.
    Содержит:
      - source: "Claude Code" (или другой)
      - title: "Дайджест релизов Claude Code: версии 2.1.237-241 (5 шт за 3 дня)"
      - url: первый URL группы
      - importance: max(importance в группе) или override
      - analysis: собранный из items (translated_title, summary, agent/business/it impact)
      - _is_digest: True (маркер для publish_post)
      - _digest_items: список ID/items, которые нужно пометить как published
    """
    versions = group.extract_versions()
    versions_label = ""
    if versions:
        if len(versions) == 1:
            versions_label = f": версия {versions[0]}"
        elif len(versions) == 2:
            versions_label = f": версии {versions[0]} и {versions[1]}"
        else:
            versions_label = f": версии {versions[0]} → {versions[-1]}"

    span_days = ""
    if group.earliest_date and group.latest_date and group.earliest_date != group.latest_date:
        span_days = f" (период {group.earliest_date} — {group.latest_date})"
    elif group.earliest_date:
        span_days = f" ({group.earliest_date})"

    title = f"Дайджест релизов {group.source}{versions_label} — {group.count} шт{span_days}"

    # Combine analyses
    items_sorted = list(group.items)  # already sorted newest first
    summaries = []
    for it in items_sorted:
        analysis = it.get("analysis") or {}
        tt = analysis.get("translated_title") or it.get("title", "")
        summ = analysis.get("summary") or it.get("summary", "")
        d = it.get("date", "")
        if tt:
            line = f"• {tt}"
            if d:
                line += f" ({d})"
            if summ:
                # Trim summary to 1 sentence
                short = summ.split(". ")[0]
                if not short.endswith("."):
                    short += "."
                line += f" — {short[:200]}"
            summaries.append(line)

    combined_summary = "\n".join(summaries[:8])  # max 8 items in digest body

    # Aggregate impacts (use the highest-importance item's analysis as primary)
    primary = max(group.items, key=lambda x: (x.get("importance") or 0, x.get("date") or ""))
    pa = primary.get("analysis") or {}

    digest = {
        "id": f"digest-{group.source.lower().replace(' ', '-')}-{group.latest_date or 'unknown'}",
        "source": group.source,
        "title": title[:200],
        "url": primary.get("url") or group.items[0].get("url", ""),
        "summary": combined_summary,
        "importance": importance_override if importance_override is not None else max(group.max_importance, 3),
        "date": group.latest_date or primary.get("date", ""),
        "analysis": {
            "translated_title": title,
            "summary": combined_summary,
            "agent_impact": pa.get("agent_impact", ""),
            "business_impact": pa.get("business_impact", ""),
            "it_impact": pa.get("it_impact", ""),
            "tags": ["release-digest"] + (pa.get("tags") or [])[:3],
        },
        "_is_digest": True,
        "_digest_source_ids": [it["id"] for it in group.items if it.get("id")],
        "_digest_items": [it for it in group.items],
    }
    return digest


# ============================================================
# CLI для дебага
# ============================================================
def main():
    import json, sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from _config import PENDING_QUEUE

    with open(PENDING_QUEUE) as f:
        queue = json.load(f)

    pending = queue.get("pending", [])
    print(f"Total pending: {len(pending)}")

    groups, singles = group_releases(pending)
    print(f"\n=== RELEASE GROUPS (≥2 items) ===")
    total_in_groups = 0
    for g in groups:
        total_in_groups += g.count
        print(f"\n[{g.source}] n={g.count} imp_max={g.max_importance}")
        print(f"  span: {g.earliest_date} → {g.latest_date}")
        versions = g.extract_versions()
        if versions:
            print(f"  versions: {versions}")
        for it in g.items:
            print(f"  - [{it.get('importance')}|{it.get('date')}] {it.get('title','')[:80]}")

    print(f"\nTotal items in groups: {total_in_groups}")
    print(f"Total singles: {len(singles)}")
    release_singles = sum(1 for it in singles if is_release_item(it))
    print(f"  of which are releases (alone): {release_singles}")
    print(f"  of which are non-release: {len(singles) - release_singles}")

    # Show what a digest post would look like
    if groups:
        print("\n=== SAMPLE DIGEST POST (first group) ===")
        digest = make_digest_post(groups[0])
        print(json.dumps(digest, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
