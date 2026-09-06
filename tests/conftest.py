"""Pytest configuration: isolated DB per test, fixture factories."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agentsblog.config import Settings
from agentsblog.db import connect, init_schema, upsert_source
from agentsblog.models import Article, ArticleStatus, Source


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    """Settings pointing at a fresh tmp dir — no real data touched."""
    s = Settings(root=tmp_path, data_dir=tmp_path / "data", public_dir=tmp_path / "public")
    return s


@pytest.fixture
def db(tmp_settings: Settings) -> sqlite3.Connection:
    """Fresh DB connection with schema applied."""
    conn = connect(tmp_settings.db_path)
    init_schema(conn)
    return conn


@pytest.fixture
def make_article():
    """Factory that BOTH builds an Article AND registers its Source.

    Pass the `db` fixture as the first positional argument so the FK constraint
    on articles.source_id → sources.id is satisfied automatically.
    """

    def _factory(
        db: sqlite3.Connection,
        *,
        id: str = "anthropic-2026-claude-4",
        source_id: str = "anthropic",
        source_tier: int = 1,
        title: str = "Anthropic releases Claude 4",
        url: str = "https://www.anthropic.com/news/claude-4",
        date: str = "2026-09-06",
        status: ArticleStatus = ArticleStatus.PENDING,
        importance: int = 4,
        agent_impact: str = "New tool-use capabilities",
        is_breakthrough: bool = False,
        **overrides,
    ) -> Article:
        upsert_source(
            db,
            Source(
                id=source_id, name=source_id.title(),
                url=f"https://example.com/{source_id}",
                kind="rss", tier=source_tier, enabled=True,
            ),
        )
        defaults = dict(
            id=id, source_id=source_id, title=title, url=url, date=date,
            status=status, importance=importance, agent_impact=agent_impact,
            is_breakthrough=is_breakthrough,
        )
        defaults.update(overrides)
        return Article(**defaults)

    return _factory


@pytest.fixture
def make_source():
    """Factory that BOTH builds AND inserts a Source, so FK constraints are satisfied."""

    def _factory(
        db: sqlite3.Connection,
        *,
        id: str = "anthropic",
        name: str = "Anthropic",
        tier: int = 1,
        **overrides,
    ) -> Source:
        defaults = dict(
            id=id, name=name,
            url=f"https://example.com/{id}",
            kind="rss", tier=tier, enabled=True, notes="",
        )
        defaults.update(overrides)
        src = Source(**defaults)
        upsert_source(db, src)
        return src

    return _factory