"""Soft decay signal: older items get lower decayed_importance.

Doesn't filter — just a sort hint. QW2 (2026-08-10).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from agentsblog.models import Article


def apply_decay(article: Article, *, now: datetime | None = None) -> Article:
    """Compute `decayed_importance` = importance - age_days/30, min 1.

    Mutates the input via model_copy.
    """
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(article.date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - dt).days)
    except (ValueError, TypeError):
        age_days = 0
    decayed = max(1.0, article.importance - age_days / 30.0)
    return article.model_copy(update={"decayed_importance": decayed})


def apply_decay_to_pending(articles: list[Article]) -> list[Article]:
    """In-place mutate the list (returns the same list for convenience)."""
    return [apply_decay(a) for a in articles]