"""Tests for db.py — schema, CRUD, URL-based dedup, source health."""
from __future__ import annotations

import pytest

from agentsblog.db import (
    append_event,
    get_article,
    get_source_health,
    init_schema,
    is_url_known,
    list_pending,
    mark_published,
    record_source_check,
    upsert_article,
)
from agentsblog.models import ArticleStatus


def test_init_schema_is_idempotent(tmp_settings):
    from agentsblog.db import connect
    conn = connect(tmp_settings.db_path)
    assert init_schema(conn) == 1
    # Second call must not raise
    assert init_schema(conn) == 1


def test_upsert_article_inserts_and_updates(db, make_article):
    a = make_article(db)
    assert upsert_article(db, a) is True   # inserted
    assert upsert_article(db, a) is False  # updated
    row = get_article(db, a.id)
    assert row is not None
    assert row.title == a.title


def test_url_dedup_catches_id_change(db, make_article):
    """Same URL but different id → still recognized as duplicate."""
    a1 = make_article(db, id="anthropic-foo", url="https://example.com/release")
    upsert_article(db, a1)
    # Different id, same URL
    a2 = make_article(db, id="anthropic-bar", url="https://example.com/release/")
    # URL-based check should catch this regardless of id
    assert is_url_known(db, a2.url) is True


def test_is_url_known_returns_false_for_new_url(db):
    assert is_url_known(db, "https://never-seen.com/x") is False


def test_list_pending_orders_by_importance(db, make_article):
    upsert_article(db, make_article(db, id="low", importance=2, date="2026-09-01"))
    upsert_article(db, make_article(db, id="high", importance=5, date="2026-09-02"))
    upsert_article(db, make_article(db, id="mid", importance=3, date="2026-09-03"))
    pending = list_pending(db, min_importance=1)
    assert [p.id for p in pending] == ["high", "mid", "low"]


def test_list_pending_filters_by_importance(db, make_article):
    upsert_article(db, make_article(db, id="high", importance=5))
    upsert_article(db, make_article(db, id="low", importance=2))
    pending = list_pending(db, min_importance=3)
    assert len(pending) == 1
    assert pending[0].id == "high"


def test_list_pending_breakthroughs_first(db, make_article):
    upsert_article(db, make_article(db, id="regular", importance=5))
    upsert_article(db, make_article(db, id="bt", importance=4, is_breakthrough=True))
    pending = list_pending(db)
    assert pending[0].id == "bt"


def test_list_pending_honors_limit(db, make_article):
    for i in range(10):
        upsert_article(db, make_article(db, id=f"a{i}", importance=4))
    pending = list_pending(db, limit=3)
    assert len(pending) == 3


def test_mark_published_transitions_atomic(db, make_article):
    a = make_article(db)
    upsert_article(db, a)
    mark_published(db, a.id, message_id=12345)
    row = get_article(db, a.id)
    assert row.status is ArticleStatus.PUBLISHED
    assert row.message_id == 12345
    assert row.published_at is not None


def test_mark_published_idempotent(db, make_article):
    a = make_article(db)
    upsert_article(db, a)
    mark_published(db, a.id, 100)
    mark_published(db, a.id, 200)  # second call should be a no-op (already published)
    row = get_article(db, a.id)
    assert row.message_id == 100  # first one wins


def test_source_health_records_success_then_failure(db, make_source):
    make_source(db, id="anthropic")
    record_source_check(db, "anthropic", ok=True, items_found=5, fetch_ms=200)
    h = get_source_health(db, "anthropic")
    assert h is not None
    assert h.fail_streak == 0
    assert h.items_found_last_run == 5
    assert h.last_error == ""

    record_source_check(db, "anthropic", ok=False, error="503")
    h2 = get_source_health(db, "anthropic")
    assert h2.fail_streak == 1
    assert h2.last_error == "503"
    # last_ok preserved from previous success
    assert h2.last_ok is not None


def test_source_health_resets_on_success_after_failures(db, make_source):
    make_source(db, id="x")
    for _ in range(3):
        record_source_check(db, "x", ok=False, error="timeout")
    h = get_source_health(db, "x")
    assert h.fail_streak == 3
    record_source_check(db, "x", ok=True)
    h2 = get_source_health(db, "x")
    assert h2.fail_streak == 0


def test_append_event(db):
    append_event(db, run_id="r1", script="scan", event="started")
    append_event(db, run_id="r1", script="scan", event="completed",
                 details={"new_pending": 5})
    row = db.execute("SELECT COUNT(*) AS n FROM events").fetchone()
    assert row["n"] == 2
    # details_json is valid JSON
    detail_row = db.execute(
        "SELECT details_json FROM events WHERE event = 'completed'"
    ).fetchone()
    import json
    assert json.loads(detail_row["details_json"]) == {"new_pending": 5}