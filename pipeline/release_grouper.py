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

    # Industry news grouping
    ind_groups, _ = group_industry_news(pending, min_importance=3, min_group_size=2)
    if ind_groups:
        print(f"\n=== INDUSTRY NEWS GROUPS (tier-3, imp≥3, ≥2 items) ===")
        for ig in ind_groups:
            print(f"\n[{ig['source']}] n={ig['count']} imp_max={ig['max_importance']}")
            for it in ig['items'][:3]:
                print(f"  - [{it.get('importance')}|{it.get('date')}] {it.get('title','')[:80]}")
            if ig['count'] > 3:
                print(f"  ... +{ig['count'] - 3} more")


# ============================================================
# QW-3.1 (2026-08-25): INDUSTRY NEWS GROUPING
# ============================================================
# Tier-3 источники (TechCrunch, arXiv, JustAI, Stanford HAI, RBC) дают
# много шума: 13+ items с importance=3 которые всё равно пролезают.
# Батчим их в «Дайджест индустрии» по source.
#
# Правила:
#   - source — tier-3 (см. TIER3_KEYWORDS в impact_scoring.py)
#   - importance >= min_importance (default 3)
#   - группа ≥ min_group_size items (default 2)
#   - max 8 items per digest (читаемость)
#
# Не батчим: tier-1/tier-2 (важные источники, едим соло).
# ============================================================
import re as _re
_TIER3_KEYWORDS_RE = _re.compile(
    r"arxiv|stanford hai|rbc|trends\.rbc|vc\.ru|techcrunch|the verge|"
    r"wired|justai|just-ai|neural digest",
    _re.IGNORECASE,
)


def _is_tier3_source(source: str) -> bool:
    if not source:
        return False
    return bool(_TIER3_KEYWORDS_RE.search(source))


def group_industry_news(
    items: list[dict],
    *,
    min_importance: int = 3,
    min_group_size: int = 2,
    max_items_per_digest: int = 8,
) -> tuple[list[dict], list[dict]]:
    """Группирует tier-3 items в «Дайджест индустрии».

    Возвращает (digests, remaining):
      digests — список dict-ов: {source, items, count, max_importance, earliest_date, latest_date}
      remaining — items, которые НЕ попали ни в один дайджест (для последующей обработки)

    Логика:
      1. Отфильтровать: tier-3 source AND importance >= min_importance.
      2. Сгруппировать по source.
      3. Отсортировать внутри каждой группы по importance desc, date desc.
      4. Если >= min_group_size — создать дайджест (макс max_items_per_digest items).
      5. Если items > max_items_per_digest — создать несколько дайджестов.
      6. Остаток (сверх max_items_per_digest * n_digests) — в remaining.
    """
    by_source: dict[str, list[dict]] = defaultdict(list)
    remaining = []

    for it in items:
        src = (it.get("source") or "").strip()
        imp = it.get("importance") or 0
        if _is_tier3_source(src) and imp >= min_importance:
            by_source[src].append(it)
        else:
            remaining.append(it)

    digests: list[dict] = []
    for src, items_list in by_source.items():
        # Sort: importance desc, then date desc
        items_list.sort(key=lambda x: (
            -(x.get("importance") or 0),
            x.get("date") or "",
        ))
        if len(items_list) < min_group_size:
            # not enough for digest → возвращаем в remaining
            remaining.extend(items_list)
            continue

        # Split into chunks of max_items_per_digest
        for chunk_idx, i in enumerate(range(0, len(items_list), max_items_per_digest)):
            chunk = items_list[i:i + max_items_per_digest]
            if len(chunk) < min_group_size:
                remaining.extend(chunk)
                continue
            digests.append({
                "source": src,
                "items": chunk,
                "count": len(chunk),
                "max_importance": max(it.get("importance") or 0 for it in chunk),
                "earliest_date": min((it.get("date") or "9999") for it in chunk),
                "latest_date": max((it.get("date") or "") for it in chunk),
                "chunk_idx": chunk_idx,
            })

    # Sort: largest digests first (max count desc, then max_importance)
    digests.sort(key=lambda d: (-d["count"], -d["max_importance"], d["source"]))

    return digests, remaining


def make_industry_digest_post(digest: dict) -> dict:
    """Создаёт синтетический пост «Дайджест индустрии» из группы tier-3 items.

    Формат:
      📰 Дайджест индустрии: TechCrunch — 5 событий (2026-08-21 — 2026-08-25)
      • [Title 1] — [1-line summary]
      • [Title 2] — [1-line summary]
      ...
      Что это значит для AI-агентов: [aggregated impact]

    Возвращает dict, аналогичный make_digest_post().
    """
    items_sorted = list(digest["items"])
    src = digest["source"]
    count = digest["count"]
    earliest = digest.get("earliest_date", "")
    latest = digest.get("latest_date", "")

    if earliest and latest and earliest != latest:
        span = f"({earliest} — {latest})"
    elif earliest:
        span = f"({earliest})"
    else:
        span = ""

    chunk_idx = digest.get("chunk_idx", 0)
    chunk_label = f" (часть {chunk_idx + 1})" if chunk_idx > 0 else ""
    title = f"Дайджест индустрии: {src} — {count} событий{chunk_label} {span}".strip()

    # Build bullet list with translated title + 1-line summary
    bullets = []
    for it in items_sorted:
        analysis = it.get("analysis") or {}
        tt = analysis.get("translated_title") or it.get("title", "")
        summ = analysis.get("summary") or it.get("summary", "")
        d = it.get("date", "")
        if tt:
            short = summ.split(". ")[0] if summ else ""
            if short and not short.endswith("."):
                short += "."
            date_label = f" ({d})" if d else ""
            line = f"• {tt}{date_label}"
            if short:
                line += f" — {short[:180]}"
            bullets.append(line)

    summary = "\n".join(bullets)

    # Aggregate impacts from primary (highest importance)
    primary = max(items_sorted, key=lambda x: (x.get("importance") or 0, x.get("date") or ""))
    pa = primary.get("analysis") or {}

    # Build list of URLs (for the URL line at the end)
    urls = []
    for it in items_sorted[:5]:
        u = it.get("url", "")
        if u:
            urls.append(f"• {it.get('title', '')[:50]} — {u}")
    urls_section = ""
    if urls:
        urls_section = "\n\nИсточники:\n" + "\n".join(urls)
        if len(items_sorted) > 5:
            urls_section += f"\n...и ещё {len(items_sorted) - 5}"

    # Add analysis summary (the bullets + URLs + impact)
    analysis_summary = summary + urls_section

    digest_id = f"digest-industry-{src.lower().replace(' ', '-')}-{latest or 'unknown'}"
    if chunk_idx > 0:
        digest_id += f"-part{chunk_idx + 1}"

    digest_post = {
        "id": digest_id,
        "source": src,
        "title": title[:200],
        "url": primary.get("url") or items_sorted[0].get("url", ""),
        "summary": analysis_summary,
        "importance": max(digest["max_importance"], 3),
        "date": latest or primary.get("date", ""),
        "analysis": {
            "translated_title": title,
            "summary": analysis_summary,
            "agent_impact": pa.get("agent_impact", ""),
            "business_impact": pa.get("business_impact", ""),
            "it_impact": pa.get("it_impact", ""),
            "tags": ["industry-digest"] + (pa.get("tags") or [])[:3],
        },
        "_is_industry_digest": True,
        "_is_digest": True,  # используется publish_post для обработки как дайджест
        "_digest_source_ids": [it["id"] for it in items_sorted if it.get("id")],
        "_digest_items": [it for it in items_sorted],
    }
    return digest_post


# ============================================================
# QW-3.1 (2026-08-25): STALE CLEANUP
# ============================================================
# Удаляет из pending items, которые:
#   - importance < min_importance (default 3) — никогда не пройдут QW4
#   - age > max_age_days (для своего tier) — протухли, никому не интересны
#
# TTL по тирам:
#   - tier-1 (Anthropic/OpenAI/...): 21 день (важные — долго живут)
#   - tier-2 (Copilot/Cursor/HF/...): 14 дней
#   - tier-3 (TechCrunch/arXiv/...): 7 дней
#
# Не трогает items с importance >= min_importance (они живы и могут пройти QW4).
# ============================================================
from datetime import datetime as _dt, timezone as _tz

STALE_TTL_DAYS = {
    1: 21,  # tier-1
    2: 14,  # tier-2
    3: 7,   # tier-3
}


def _item_tier(item: dict) -> int:
    """Определяет tier item по source (использует ту же логику что и impact_scoring)."""
    src = (item.get("source") or "").lower()
    if any(kw in src for kw in ("anthropic", "openai", "google ai", "google deepmind",
                                  "deepmind", "microsoft ai", "microsoft research",
                                  "deepseek", "xai", "x.ai", "mistral", "meta ai")):
        return 1
    if any(kw in src for kw in ("cohere", "perplexity", "stability", "alibaba qwen", "qwen",
                                  "huggingface", "hugging face", "github copilot",
                                  "cursor", "claude code")):
        return 2
    return 3


def cleanup_stale_items(
    items: list[dict],
    *,
    min_importance: int = 3,
    now: _dt | None = None,
) -> tuple[list[dict], list[dict]]:
    """Удаляет из items те, что importance<min_importance И старше TTL.

    Возвращает (kept, removed):
      kept — items, которые остаются
      removed — items, которые удалены (с полным описанием для лога)

    Не трогает items без date — они «свежие» по определению.
    """
    now = now or _dt.now(_tz.utc)
    kept = []
    removed = []

    for it in items:
        imp = it.get("importance") or 0
        if imp >= min_importance:
            kept.append(it)
            continue

        # imp < 3: проверяем возраст
        date_str = it.get("date") or ""
        if not date_str:
            # нет даты → оставляем (свежий по определению)
            kept.append(it)
            continue

        try:
            pub_date = _dt.strptime(date_str, "%Y-%m-%d").replace(tzinfo=_tz.utc)
        except ValueError:
            kept.append(it)
            continue

        age_days = (now - pub_date).days
        tier = _item_tier(it)
        ttl = STALE_TTL_DAYS.get(tier, 7)

        if age_days > ttl:
            removed.append({
                "id": it.get("id"),
                "source": it.get("source"),
                "title": it.get("title", "")[:120],
                "importance": imp,
                "age_days": age_days,
                "tier": tier,
                "ttl_days": ttl,
            })
        else:
            kept.append(it)

    return kept, removed


if __name__ == "__main__":
    main()
