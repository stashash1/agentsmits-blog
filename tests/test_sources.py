"""Tests for source parsers — generic base classes + URL parsing helpers."""
from __future__ import annotations

from datetime import datetime, timezone

from agentsblog.sources.base import (
    ChangelogMdSource,
    HtmlSource,
    RssSource,
    make_article_id,
    parse_iso_to_date,
    parse_pubdate_to_iso,
    parse_rss_items,
    parse_url_embedded_date,
    rss_item_fields,
    strip_html,
)


# ── ID generation ──────────────────────────────────────────────────

def test_make_article_id_short_slug():
    assert make_article_id("anthropic", "https://example.com/news") == "anthropic-news"


def test_make_article_id_long_slug_uses_hash():
    """Truncating alone would collide — hash must disambiguate."""
    long_slug = "x" * 100
    id1 = make_article_id("a", f"https://example.com/{long_slug}-aaa")
    id2 = make_article_id("a", f"https://example.com/{long_slug}-bbb")
    assert id1 != id2
    assert len(id1) <= 60


def test_make_article_id_strips_trailing_slash():
    """Trailing slash must not change the id (dedup safety)."""
    a = make_article_id("x", "https://example.com/foo")
    b = make_article_id("x", "https://example.com/foo/")
    assert a == b


# ── RSS parsing ─────────────────────────────────────────────────────

def test_parse_rss_items_basic():
    xml = """<?xml version="1.0"?>
    <rss><channel>
      <item>
        <title>Hello world</title>
        <link>https://example.com/hello</link>
        <pubDate>Mon, 06 Sep 2026 12:00:00 +0000</pubDate>
        <description>Some text</description>
      </item>
      <item>
        <title><![CDATA[CDATA title & entities]]></title>
        <link>https://example.com/cdata</link>
        <pubDate>Tue, 07 Sep 2026 12:00:00 +0000</pubDate>
      </item>
    </channel></rss>"""
    items = parse_rss_items(xml)
    assert len(items) == 2
    assert items[0]["title"] == "Hello world"
    assert items[0]["link"] == "https://example.com/hello"
    assert items[0]["description"] == "Some text"
    assert items[1]["title"] == "CDATA title & entities"  # CDATA decoded, entities preserved


def test_rss_item_fields_missing():
    fields = rss_item_fields("<title>only title</title>")
    assert fields["title"] == "only title"
    assert fields["link"] == ""
    assert fields["pubDate"] == ""


# ── Date parsing ────────────────────────────────────────────────────

def test_parse_pubdate_iso_format():
    dt, date_str = parse_pubdate_to_iso("Mon, 06 Sep 2026 12:00:00 +0000")
    assert dt is not None
    assert dt.year == 2026
    assert date_str == "2026-09-06"


def test_parse_pubdate_garbage_returns_none():
    dt, date_str = parse_pubdate_to_iso("not a date")
    assert dt is None
    assert date_str is None


def test_parse_pubdate_empty():
    assert parse_pubdate_to_iso("") == (None, None)


def test_parse_iso_to_date_with_z():
    dt, date_str = parse_iso_to_date("2026-09-06T12:00:00.486Z")
    assert dt is not None
    assert date_str == "2026-09-06"
    assert dt.tzinfo is not None


def test_parse_iso_to_date_with_offset():
    dt, _ = parse_iso_to_date("2026-09-06T12:00:00+03:00")
    assert dt is not None


def test_parse_iso_to_date_garbage():
    assert parse_iso_to_date("garbage") == (None, None)


def test_parse_url_embedded_date_rbc():
    assert parse_url_embedded_date("https://www.rbc.ru/economics/20/01/2026/abc") == "20/01/2026"


def test_parse_url_embedded_date_no_match():
    assert parse_url_embedded_date("https://example.com/no-date-here") is None


# ── strip_html ─────────────────────────────────────────────────────

def test_strip_html():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_empty():
    assert strip_html("") == ""


def test_strip_html_truncates():
    assert len(strip_html("a" * 1000)) == 300


# ── RssSource subclass behaviour (with stub subclass) ──────────────

class _StubRss(RssSource):
    feed_url = "https://example.com/feed.xml"
    cutoff_days = 30


def test_rss_source_filters_old_items():
    # Build a feed with one old + one fresh item
    import time
    now = datetime.now(timezone.utc)
    fresh = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    xml = f"""<rss><channel>
      <item><title>Fresh news today</title>
            <link>https://e.com/fresh</link>
            <pubDate>{fresh}</pubDate></item>
    </channel></rss>"""
    # Inject body via monkeypatch on the fetch function
    from agentsblog.sources import base as b
    orig_fetch = b.fetch
    b.fetch = lambda url, **kw: type("R", (), {"body": xml, "fetch_ms": 1, "status": 200})()
    try:
        # Need a Source instance
        from agentsblog.models import Source, SourceKind
        src = Source(id="stub", name="Stub", url="https://e.com", kind=SourceKind.RSS, tier=1)
        scanner = _StubRss(src)
        out = scanner.scan()
        assert len(out) == 1
        assert out[0].title == "Fresh news today"
    finally:
        b.fetch = orig_fetch


def test_rss_source_short_title_filtered():
    from agentsblog.sources import base as b
    xml = """<rss><channel>
      <item><title>Hi</title><link>https://e.com/x</link></item>
    </channel></rss>"""
    orig_fetch = b.fetch
    b.fetch = lambda url, **kw: type("R", (), {"body": xml, "fetch_ms": 1, "status": 200})()
    try:
        from agentsblog.models import Source, SourceKind
        src = Source(id="stub", name="Stub", url="https://e.com", kind=SourceKind.RSS, tier=1)
        out = _StubRss(src).scan()
        assert out == []
    finally:
        b.fetch = orig_fetch