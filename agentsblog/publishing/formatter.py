"""Telegram post formatters — 3 formats from the legacy publisher.

Pure functions of (article, agi_days, agi_percent) → formatted text.
No I/O, no DB access.

The legacy code had 3 formats (standard, breakthrough, release-digest);
we keep them all here but split into named functions for testability.
"""
from __future__ import annotations

from datetime import datetime, timezone

from agentsblog.models import Article


_MONTHS_RU = ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
               'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
_DAYS_RU = ['понедельник', 'вторник', 'среда', 'четверг',
            'пятница', 'суббота', 'воскресенье']


def _ru_date(date_str: str) -> str:
    """Format YYYY-MM-DD → 'понедельник, 6 сентября 2026 г.'"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return f"{_DAYS_RU[dt.weekday()]}, {dt.day} {_MONTHS_RU[dt.month]} {dt.year} г."
    except (ValueError, TypeError):
        now = datetime.now(timezone.utc)
        return f"{_DAYS_RU[now.weekday()]}, {now.day} {_MONTHS_RU[now.month]} {now.year} г."


def _breakthrough_reason_lines(article: Article) -> str:
    """Translate `breakthrough_reasons` into a short bulleted list."""
    from agentsblog.scoring.breakthrough import (
        ARCHITECTURE_PATTERNS, SOTA_PATTERNS, OPEN_SOURCE_FRONTIER,
    )
    labels = {
        r"\bMamba\b": "Mamba (альтернатива трансформеру)",
        r"\bMoE\b": "Mixture-of-Experts",
        r"\bmixture\s+of\s+experts\b": "Mixture-of-Experts",
        r"\bdiffusion\s+transformer\b": "Diffusion Transformer",
        r"\bJEPA\b": "JEPA (world model от Meta)",
        r"\bV[- ]?JEPA\b": "V-JEPA",
        r"\bworld\s+model": "world model",
        r"\bhybrid\s+(?:model|architecture|intelligence|approach)\b": "гибридная архитектура",
        r"\btest[- ]time\s+compute\b": "test-time compute",
        r"\binference[- ]time\s+scaling\b": "inference-time scaling",
        r"\bprocess\s+reward\s+model\b": "process reward model",
        r"\bconstitutional\s+AI\b": "Constitutional AI",
        r"\bRLAIF\b": "RLAIF",
        r"\bDPO\b": "DPO",
        r"\bmechanistic\s+interpretability\b": "mechanistic interpretability",
        r"\bchain[- ]of[- ]thought\b": "Chain-of-Thought",
        r"\btree[- ]of[- ]thoughts?\b": "Tree-of-Thoughts",
        r"\bagentic\s+(?:framework|workflow|reasoning|loop|system)\b": "агентский фреймворк",
        r"\bagentic\s+AI\b": "Agentic AI",
        r"\bmultimodal\s+(?:model|architecture|foundation)\b": "мультимодальная архитектура",
        r"\b(?:new|open|novel)\s+(?:framework|library|toolkit|method|approach|technique|protocol)\b": "новая техника / фреймворк",
        r"\bvision[- ]language[- ]action\b": "Vision-Language-Action",
        r"\bVLA\b": "VLA",
        r"\bembodied\s+(?:AI|agent|intelligence)\b": "embodied AI",
        r"\bhumanoid\b": "humanoid-робот",
    }
    used: set[str] = set()
    lines: list[str] = []
    for reason in article.breakthrough_reasons:
        if reason.startswith("new_architecture_or_technique"):
            # Surface matched patterns as labels
            for pat in ARCHITECTURE_PATTERNS[:3]:
                label = labels.get(pat)
                if label and label not in used:
                    used.add(label)
                    lines.append(f"- {label}")
    if "sota_or_milestone" in " ".join(article.breakthrough_reasons):
        for pat in SOTA_PATTERNS[:2]:
            clean = pat.replace(r"\b", "").replace("[- ]?", "").replace("\\", "")[:40]
            lines.append(f"- SOTA / milestone: {clean}")
    if "open_source_frontier" in article.breakthrough_reasons:
        lines.append("- Open-source достигает frontier-уровня")
    if not lines:
        lines.append("- Новый технологический вектор (importance + ключевые сигналы)")
    return "\n".join(lines)


def format_standard(
    article: Article, *,
    agi_days: int, agi_percent: int,
) -> str | None:
    """Standard single-post format. Returns None if article lacks analysis."""
    if not (article.agent_impact):
        return None

    title = article.translated_title or article.title or "Без названия"
    date_str = _ru_date(article.date)
    summary = article.summary or ""

    parts = [f"## {title}", "", date_str, ""]
    if summary:
        parts += [summary, ""]
    if article.url:
        parts += [f"[Источник]({article.url})", ""]
    if article.agent_impact:
        parts += ["### Влияние на разработку агентов", article.agent_impact, ""]
    if article.business_impact:
        parts += ["### Влияние на бизнес", article.business_impact, ""]
    if article.it_impact:
        parts += ["### Влияние на IT-индустрию", article.it_impact, ""]
    parts += ["---", ""]
    parts += [f"**ДО AGI:** ~{agi_days} дней [ . . . . . . . . . . ] ~{agi_percent}%", ""]
    parts += ["[Полетели →](https://stashash1.github.io/agentsmits-blog)"]
    return "\n".join(parts)


def format_breakthrough(
    article: Article, *,
    agi_days: int, agi_percent: int,
) -> str | None:
    """Rich breakthrough format with banner + 'Что нового' section."""
    if not article.agent_impact:
        return None

    title = article.translated_title or article.title or "Без названия"
    date_str = _ru_date(article.date)
    summary = article.summary or ""

    parts = ["# ВАЖНАЯ СТАТЬЯ • ПРОРЫВ", "", f"## {title}", "", date_str, ""]
    if summary:
        parts += [summary, ""]
    if article.url:
        parts += [f"[Источник]({article.url})", ""]
    parts += ["### Что нового (прорыв)", _breakthrough_reason_lines(article), ""]
    if article.agent_impact:
        parts += ["### Влияние на разработку агентов", article.agent_impact, ""]
    if article.business_impact:
        parts += ["### Влияние на бизнес", article.business_impact, ""]
    if article.it_impact:
        parts += ["### Влияние на IT-индустрию", article.it_impact, ""]
    parts += ["---", ""]
    parts += [f"**ДО AGI:** ~{agi_days} дней [ . . . . . . . . . . ] ~{agi_percent}%", ""]
    parts += ["[Это меняет правила игры →](https://stashash1.github.io/agentsmits-blog)"]
    return "\n".join(parts)


def format_release_digest(
    items: list[Article],
    *,
    source_name: str,
    agi_days: int, agi_percent: int,
    breakthrough: bool = False,
) -> str:
    """Release digest: multiple items from same source bundled into one post."""
    now = datetime.now(timezone.utc)
    date_str = f"{_DAYS_RU[now.weekday()]}, {now.day} {_MONTHS_RU[now.month]} {now.year} г."

    header = "ВАЙДЖЕСТ РЕЛИЗОВ • ПРОРЫВ" if breakthrough else "ДАЙДЖЕСТ РЕЛИЗОВ"

    lines: list[str] = [
        f"Source: {source_name}",
        date_str,
        "",
        header,
        "",
    ]
    if items:
        first = items[0]
        title = first.translated_title or first.title or "Дайджест релизов"
        lines.append(f"## {title}")
        if first.url:
            lines.append(f"[Источник]({first.url})")
        lines.append("")
    lines.append("Релизы в дайджесте:")
    for it in items[:5]:
        label = it.title[:50]
        lines.append(f"- {label} — {it.url}")
    if len(items) > 5:
        lines.append(f"...и ещё {len(items) - 5}")
    lines.append("")
    if items and items[0].agent_impact:
        first = items[0]
        lines += ["### Влияние на разработку агентов", first.agent_impact, ""]
        if first.business_impact:
            lines += ["### Влияние на бизнес", first.business_impact, ""]
        if first.it_impact:
            lines += ["### Влияние на IT-индустрию", first.it_impact, ""]
    lines += ["---", ""]
    lines += [f"**ДО AGI:** ~{agi_days} дней [ . . . . . . . . . . ] ~{agi_percent}%"]
    return "\n".join(lines)


def format_industry_digest(
    items: list[Article], *,
    source_name: str,
    agi_days: int, agi_percent: int,
) -> str:
    """Industry news digest (tier-3 sources bundled)."""
    now = datetime.now(timezone.utc)
    date_str = f"{_DAYS_RU[now.weekday()]}, {now.day} {_MONTHS_RU[now.month]} {now.year} г."

    lines: list[str] = [
        f"Source: {source_name}",
        date_str,
        "",
        "ДАЙДЖЕСТ ИНДУСТРИИ",
        "",
    ]
    if items:
        first = items[0]
        lines.append(f"## {first.translated_title or first.title}")
        if first.url:
            lines.append(f"[Источник]({first.url})")
        lines.append("")
    lines.append("События:")
    for it in items[:8]:
        lines.append(f"- {it.title[:60]} — {it.url}")
    if len(items) > 8:
        lines.append(f"...и ещё {len(items) - 8}")
    lines.append("")
    if items and items[0].agent_impact:
        first = items[0]
        lines += ["### Влияние на разработку агентов", first.agent_impact, ""]
    lines += ["---", ""]
    lines += [f"**ДО AGI:** ~{agi_days} дней [ . . . . . . . . . . ] ~{agi_percent}%"]
    return "\n".join(lines)


def compute_agi(settings) -> tuple[int, int]:
    """Compute (days_to_agi, percent_complete) from settings."""
    try:
        start = datetime.strptime(settings.agi_start_date, "%Y-%m-%d")
        elapsed = (datetime.now() - start).days
        days = max(0, settings.agi_base_days - elapsed)
        pct = max(2, min(98, round(elapsed / settings.agi_base_days * 100)))
        return days, pct
    except ValueError:
        return settings.agi_base_days, 50