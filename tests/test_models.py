"""Tests for models.py — Article validation, defaults, computed properties."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentsblog.models import Article, ArticleStatus, Narrative, NarrativeItem


def test_article_minimal_construction():
    a = Article(
        id="x-1", source_id="x",
        title="T", url="https://e.com/x", date="2026-09-06",
    )
    assert a.status is ArticleStatus.PENDING
    assert a.importance == 3
    assert a.is_breakthrough is False
    assert a.tags == []
    assert a.agent_impact == ""
    assert a.url_normalized == "https://e.com/x"  # no trailing slash to strip


def test_article_url_normalized_strips_trailing_slash():
    a = Article(id="x", source_id="x", title="T",
                url="https://example.com/foo/", date="2026-09-06")
    assert a.url_normalized == "https://example.com/foo"


def test_article_rejects_empty_id():
    with pytest.raises(ValidationError):
        Article(id="", source_id="x", title="T",
                url="https://e.com/", date="")


def test_article_rejects_empty_url():
    with pytest.raises(ValidationError):
        Article(id="x", source_id="x", title="T",
                url="", date="2026-09-06")


def test_article_importance_clamped_in_model():
    # Importance is ge=1, le=5 — out of range should fail
    with pytest.raises(ValidationError):
        Article(id="x", source_id="x", title="T",
                url="https://e.com/", date="", importance=10)


def test_is_publishable_requires_agent_impact():
    a = Article(id="x", source_id="x", title="T",
                url="https://e.com/", date="")
    assert a.is_publishable is False
    a2 = a.model_copy(update={"agent_impact": "Some impact text"})
    assert a2.is_publishable is True


def test_narrative_round_trip():
    n = Narrative(
        id="n-1", title="Claude Code updates",
        first_seen=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        last_seen=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        entities=["claude-code", "anthropic"],
    )
    n.items.append(NarrativeItem(article_id="x-1", role="primary"))
    assert len(n.items) == 1
    assert n.items[0].role == "primary"


def test_article_status_enum_values():
    assert ArticleStatus.PENDING.value == "pending"
    assert ArticleStatus.PUBLISHED.value == "published"
    # Membership is type-safe
    for s in ("pending", "published", "skipped", "failed", "digested"):
        ArticleStatus(s)  # should not raise