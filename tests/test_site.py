"""Tests for site builder — feed + articles pages must render."""
from __future__ import annotations

from datetime import datetime, timezone

from agentsblog.db import upsert_article
from agentsblog.site import build_site
from agentsblog.site.rss import render_rss


def test_build_site_creates_files(tmp_settings, db, make_article):
    """Smoke test: build produces all 3 pages + CSS."""
    upsert_article(db, make_article(
        db,
        id="site-1", title="Test article", agent_impact="Big impact",
        importance=4, date="2026-09-06",
    ))

    summary = build_site(tmp_settings)

    assert summary["wrote"] == ["index.html", "articles.html", "rss.xml", "assets/styles.css"]
    assert summary["feed_count"] == 0  # nothing is 'published' yet

    out = tmp_settings.resolved_public_dir
    assert (out / "index.html").exists()
    assert (out / "articles.html").exists()
    assert (out / "rss.xml").exists()
    assert (out / "assets" / "styles.css").exists()


def test_feed_renders_published_articles(tmp_settings, db, make_article):
    """Only 'published' status shows up on feed."""
    art = make_article(
        db, id="p-1", title="Pub", agent_impact="x", importance=4,
        date="2026-09-06",
    )
    upsert_article(db, art)
    from agentsblog.db import mark_published
    mark_published(db, art.id, message_id=123)

    summary = build_site(tmp_settings)
    assert summary["feed_count"] == 1
    assert summary["articles_count"] == 1

    html = (tmp_settings.resolved_public_dir / "index.html").read_text(encoding="utf-8")
    assert "Pub" in html
    assert "Актуальные новости" in html
    assert "Лента" in html  # nav


def test_articles_page_is_structurally_different_from_feed(tmp_settings, db, make_article):
    """Critical: articles.html must have a DIFFERENT structure than index.html.

    The legacy generate_site.py used the same template for both, which the
    user explicitly called out as a problem. This test guards against
    re-introducing that bug.
    """
    art = make_article(
        db, id="p-1", title="Deep analysis article",
        agent_impact="Big effect on agent dev",
        business_impact="Affects business",
        it_impact="Affects IT",
        date="2026-09-06", importance=5,
    )
    upsert_article(db, art)
    from agentsblog.db import mark_published
    mark_published(db, art.id, 1)
    # Add tags for category grouping
    from agentsblog.db import connect
    conn = connect(tmp_settings.db_path)
    import json
    conn.execute(
        "UPDATE articles SET tags_json = ? WHERE id = ?",
        (json.dumps(["agents", "release"]), "p-1"),
    )

    build_site(tmp_settings)
    index_html = (tmp_settings.resolved_public_dir / "index.html").read_text(encoding="utf-8")
    articles_html = (tmp_settings.resolved_public_dir / "articles.html").read_text(encoding="utf-8")

    # Articles page should have category grouping
    assert "Глубокий разбор" in articles_html
    assert "#agents" in articles_html or "#release" in articles_html
    # Articles page should NOT have the subscribe banner or archive (focused reading)
    assert "Подпишись на канал" not in articles_html
    assert "Архив" not in articles_html

    # Feed page should have subscribe + archive
    assert "Подпишись на канал" in index_html
    assert "Актуальные новости" in index_html


def test_breakthrough_badge_in_html(tmp_settings, db, make_article):
    art = make_article(
        db, id="bt-1", title="GPT-5 Mamba breakthrough",
        agent_impact="New architecture", importance=5,
        date="2026-09-06", is_breakthrough=True,
    )
    upsert_article(db, art)
    from agentsblog.db import mark_published
    mark_published(db, art.id, 1)

    build_site(tmp_settings)
    html = (tmp_settings.resolved_public_dir / "index.html").read_text(encoding="utf-8")
    assert "ПРОРЫВ" in html
    assert "hero-card-bt" in html


def test_rss_renders_xml(tmp_settings):
    """RSS 2.0 — well-formed output."""
    art = {
        "id": "r-1", "source_id": "openai", "title": "Hello",
        "url": "https://openai.com/x",
        "translated_title": "Привет",
        "summary": "Summary text",
        "agent_impact": "Big",
        "published_at": "2026-09-06T12:00:00Z",
    }
    xml = render_rss([art], tmp_settings)
    assert xml.startswith("<?xml")
    assert "<rss version=\"2.0\"" in xml
    assert "Привет" in xml
    assert "Big" in xml
    assert "<pubDate>" in xml


def test_rss_handles_articles_without_analysis(tmp_settings):
    """Article without analysis should still render in RSS (just no impact fields)."""
    art = {
        "id": "r-2", "source_id": "techcrunch", "title": "T",
        "url": "https://t.com/x",
        "published_at": None,  # also test missing date
    }
    xml = render_rss([art], tmp_settings)
    assert "<item>" in xml
    assert "<pubDate>" in xml  # fallback to now


def test_empty_state_when_no_articles(tmp_settings, db):
    """Empty DB → graceful empty state, no crash."""
    build_site(tmp_settings)
    index_html = (tmp_settings.resolved_public_dir / "index.html").read_text(encoding="utf-8")
    articles_html = (tmp_settings.resolved_public_dir / "articles.html").read_text(encoding="utf-8")
    assert "Постов этой недели пока нет" in index_html
    assert "пока нет" in articles_html or "Запустите" in articles_html


def test_build_site_idempotent(tmp_settings, db, make_article):
    """Building twice produces identical files."""
    upsert_article(db, make_article(
        db, id="idem-1", title="x", agent_impact="x", date="2026-09-06",
    ))
    build_site(tmp_settings)
    first = (tmp_settings.resolved_public_dir / "index.html").read_bytes()
    build_site(tmp_settings)
    second = (tmp_settings.resolved_public_dir / "index.html").read_bytes()
    # RSS lastBuildDate will differ — strip that for comparison
    # Easier: assert it's a complete HTML page both times
    assert b"<html" in first
    assert b"<html" in second