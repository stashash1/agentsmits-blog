"""Tests for the scanner orchestrator — registration, dedup, health."""
from __future__ import annotations

from agentsblog.db import (
    get_source_health,
    is_url_known,
    list_pending,
    upsert_article,
)
from agentsblog.models import Article, ArticleStatus, Source, SourceKind
from agentsblog.scanner import run_scan
from agentsblog.sources import (
    SOURCES_META,
    Registry,
    get_meta,
    get_scanner,
    register_all,
    all_scanners,
)


def test_register_all_populates_registry():
    register_all()
    # Every scanner has both meta + class
    registered = set(Registry.ids())
    assert "openai" in registered
    assert "anthropic" in registered
    assert "deepmind" in registered
    assert "huggingface" in registered
    assert "claude_code" in registered
    assert "arxiv" in registered
    # Sources that should be empty returners (still registered, just no items)
    assert "deepseek" in registered
    assert "xai" in registered
    # All IDs >= 20
    assert len(registered) >= 20


def test_meta_and_scanner_paired():
    """Every registered scanner has a Source meta entry and vice versa."""
    register_all()
    scanner_ids = set(Registry.ids())
    meta_ids = set(SOURCES_META.keys())
    # Should be the same set — every source has both
    assert scanner_ids == meta_ids


def test_run_scan_dry_run_does_not_persist(tmp_settings, monkeypatch):
    """Dry-run must not write to DB; only source registration happens."""
    register_all()
    # Stub fetch() to return empty bodies — so no items are produced
    from agentsblog.sources import base as b
    b.fetch = lambda url, **kw: type("R", (), {"body": None, "fetch_ms": 1, "status": 200, "error": "stub"})()
    try:
        summary = run_scan(tmp_settings, dry_run=True)
        # Sources got registered (NOT dry-run controlled), but no articles added
        from agentsblog.db import connect
        conn = connect(tmp_settings.db_path)
        rows = conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()
        assert rows["n"] >= 20
        # No items produced (all sources got empty body)
        assert summary["new_pending"] == 0
        assert summary["skipped_dups"] == 0
        # All 22 sources scanned without exception (empty == ok, not failure)
        assert summary["sources_scanned"] >= 20
    finally:
        # Restore
        b.fetch = lambda url, **kw: type("R", (), {"body": None, "fetch_ms": 1, "status": 200})()


def test_run_scan_dedup_against_existing(tmp_settings, db, make_article):
    """If an article with same URL is already in DB, scanner should skip it."""
    from agentsblog.sources import base as b

    # Pre-seed one OpenAI article
    pre = make_article(
        db,
        id="openai-existing-1",
        source_id="openai",
        url="https://openai.com/news/test-existing",
        title="Pre-existing",
    )
    upsert_article(db, pre)

    # Stub fetch to return a feed containing that same URL
    xml = """<rss><channel>
      <item>
        <title>Brand new OpenAI announcement today</title>
        <link>https://openai.com/news/test-existing</link>
        <pubDate>Mon, 06 Sep 2026 12:00:00 +0000</pubDate>
      </item>
      <item>
        <title>Another genuinely new OpenAI thing</title>
        <link>https://openai.com/news/fresh-1</link>
        <pubDate>Mon, 06 Sep 2026 13:00:00 +0000</pubDate>
      </item>
    </channel></rss>"""
    b.fetch = lambda url, **kw: type("R", (), {"body": xml, "fetch_ms": 1, "status": 200})()
    try:
        summary = run_scan(tmp_settings, limit_sources=["openai"])
        # One URL matched existing → dup; one URL is new → upserted
        by = summary["by_source"]["openai"]
        assert by["new"] == 1
        assert by["dup"] == 1

        # Verify both items in DB
        pending = list_pending(db, min_importance=1)
        assert len(pending) == 2  # pre-existing + the new one
        urls = {p.url_normalized for p in pending}
        assert "https://openai.com/news/test-existing" in urls
        assert "https://openai.com/news/fresh-1" in urls
    finally:
        b.fetch = lambda url, **kw: type("R", (), {"body": None, "fetch_ms": 1, "status": 200})()


def test_source_health_records_per_source(tmp_settings):
    register_all()
    from agentsblog.sources import base as b

    # Mixed: openai succeeds, deepseek returns empty (which is "ok" with 0 items)
    def stub_fetch(url, **kw):
        if "openai.com" in url:
            xml = """<rss><channel>
              <item><title>OpenAI news item here today</title>
                <link>https://openai.com/news/x</link>
                <pubDate>Mon, 06 Sep 2026 12:00:00 +0000</pubDate>
              </item>
            </channel></rss>"""
            return type("R", (), {"body": xml, "fetch_ms": 50, "status": 200})()
        # DeepSeek: empty body, no error
        return type("R", (), {"body": None, "fetch_ms": 1, "status": 200})()
    b.fetch = stub_fetch
    try:
        summary = run_scan(tmp_settings, limit_sources=["openai", "deepseek"])
        from agentsblog.db import connect
        conn = connect(tmp_settings.db_path)
        h_openai = get_source_health(conn, "openai")
        h_deepseek = get_source_health(conn, "deepseek")
        assert h_openai.fail_streak == 0
        assert h_openai.items_found_last_run == 1
        assert h_deepseek.fail_streak == 0
        assert h_deepseek.items_found_last_run == 0
    finally:
        b.fetch = lambda url, **kw: type("R", (), {"body": None, "fetch_ms": 1, "status": 200})()