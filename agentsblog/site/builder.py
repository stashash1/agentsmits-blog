"""Static site builder — generates index.html, articles.html, rss.xml.

Reads from SQLite (articles + narratives), renders Jinja2 templates,
writes to public/. HTML structure is meaningfully different between
the feed page and the articles page (unlike the legacy single-template
approach where articles.html was just index.html minus archive).

Public structure:
    public/
        index.html      # лента + AGI bar + archive
        articles.html   # статьи (отдельная структура: вступление + тематические блоки)
        rss.xml         # RSS 2.0 с последними 20 articles
        assets/styles.css
"""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentsblog.config import Settings
from agentsblog.db import connect, init_schema


TEMPLATES_DIR = Path(__file__).parent / "templates"
ASSETS_DIR = Path(__file__).parent / "assets"


def _jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _query_feed(conn, *, limit: int = 50) -> list[dict]:
    """Current-week published articles for the feed."""
    rows = conn.execute(
        """SELECT id, source_id, title, url, date, published_at, message_id,
                  is_breakthrough, breakthrough_score, breakthrough_reasons_json,
                  translated_title, summary, agent_impact, business_impact,
                  it_impact, tags_json
           FROM articles
           WHERE status = 'published'
           ORDER BY is_breakthrough DESC, published_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _query_articles(conn, *, limit: int = 100) -> list[dict]:
    """Articles with deep analysis (agent_impact etc) for the articles page."""
    rows = conn.execute(
        """SELECT id, source_id, title, url, date, published_at,
                  is_breakthrough, breakthrough_score,
                  translated_title, summary, agent_impact, business_impact,
                  it_impact, tags_json
           FROM articles
           WHERE status = 'published'
             AND agent_impact != ''
           ORDER BY is_breakthrough DESC, published_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _query_archive(conn, *, limit: int = 20) -> list[dict]:
    """Older posts for the archive section."""
    rows = conn.execute(
        """SELECT id, source_id, title, url, date, published_at
           FROM articles
           WHERE status = 'published'
           ORDER BY published_at DESC
           LIMIT ? OFFSET 50""",
        (limit,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(r) -> dict:
    import json
    d = dict(r)
    # Parse JSON columns: breakthrough_reasons_json, tags_json
    for src_key, dst_key in (
        ("breakthrough_reasons_json", "breakthrough_reasons"),
        ("tags_json", "tags"),
    ):
        raw = d.pop(src_key, None)
        if raw:
            try:
                d[dst_key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                d[dst_key] = []
        else:
            d[dst_key] = []
    return d


def _agi_info(settings: Settings) -> tuple[int, int]:
    """(days_to_agi, percent_complete)."""
    try:
        start = datetime.strptime(settings.agi_start_date, "%Y-%m-%d")
        elapsed = (datetime.now() - start).days
        days = max(0, settings.agi_base_days - elapsed)
        pct = max(2, min(98, round(elapsed / settings.agi_base_days * 100)))
        return days, pct
    except ValueError:
        return settings.agi_base_days, 50


def build_site(settings: Settings) -> dict:
    """Build the static site. Returns a summary dict.

    Renders 3 pages:
      - index.html  (feed: current articles + archive + subscribe banner)
      - articles.html (articles: deeper analysis cards, by category)
      - rss.xml     (RSS 2.0 with last 20 articles)
    Plus copies assets/styles.css to public/assets/.
    """
    from agentsblog.site.rss import render_rss
    conn = connect(settings.db_path)
    init_schema(conn)

    feed = _query_feed(conn, limit=50)
    archive = _query_archive(conn, limit=20)
    articles = _query_articles(conn, limit=100)

    env = _jinja_env()
    agi_days, agi_percent = _agi_info(settings)
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    # ── index.html (feed) ──
    index_tmpl = env.get_template("feed.html.j2")
    index_html = index_tmpl.render(
        title="AI Агенты Смита — Лента",
        feed=feed,
        archive=archive,
        agi_days=agi_days,
        agi_percent=agi_percent,
        updated=now_str,
        site_title=settings.site_title,
    )

    # ── articles.html (separate structure: intro + by-category groups) ──
    by_category = _group_by_category(articles)
    articles_tmpl = env.get_template("articles.html.j2")
    articles_html = articles_tmpl.render(
        title="AI Агенты Смита — Статьи",
        articles=articles,
        by_category=by_category,
        agi_days=agi_days,
        agi_percent=agi_percent,
        updated=now_str,
        site_title=settings.site_title,
    )

    # ── rss.xml ──
    rss_xml = render_rss(feed[: settings.rss_limit], settings)

    # ── Write files ──
    public = settings.resolved_public_dir
    public.mkdir(parents=True, exist_ok=True)
    (public / "index.html").write_text(index_html, encoding="utf-8")
    (public / "articles.html").write_text(articles_html, encoding="utf-8")
    (public / "rss.xml").write_text(rss_xml, encoding="utf-8")

    # ── Copy CSS asset ──
    assets_out = public / "assets"
    assets_out.mkdir(exist_ok=True)
    src_css = ASSETS_DIR / "styles.css"
    if src_css.exists():
        shutil.copy2(src_css, assets_out / "styles.css")

    return {
        "feed_count": len(feed),
        "archive_count": len(archive),
        "articles_count": len(articles),
        "categories": len(by_category),
        "wrote": ["index.html", "articles.html", "rss.xml", "assets/styles.css"],
    }


def _group_by_category(articles: list[dict]) -> dict[str, list[dict]]:
    """Group articles by primary tag for the articles page."""
    out: dict[str, list[dict]] = {}
    for art in articles:
        primary = (art.get("tags") or ["AI"])[0]
        out.setdefault(primary, []).append(art)
    return out