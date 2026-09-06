"""RSS 2.0 generator.

Standalone function: (articles, settings) → RSS XML string.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from email.utils import format_datetime


def render_rss(articles: list[dict], settings) -> str:
    """Render RSS 2.0 from a list of article dicts."""
    items_xml: list[str] = []
    for art in articles:
        title = html.escape(art.get("translated_title") or art.get("title", ""))
        link = html.escape(art.get("url", ""))
        desc_parts: list[str] = []
        if art.get("summary"):
            desc_parts.append(html.escape(art["summary"]))
        for k in ("agent_impact", "business_impact", "it_impact"):
            if art.get(k):
                desc_parts.append(f"<p><b>{k.replace('_', ' ').title()}:</b> "
                                  f"{html.escape(art[k])}</p>")
        description = "".join(desc_parts)

        pub = _format_pubdate(art.get("published_at"))
        items_xml.append(f"""    <item>
      <title>{title}</title>
      <link>{link}</link>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub}</pubDate>
      <guid isPermaLink="false">{art.get('id','')}</guid>
    </item>""")

    last_build = format_datetime(datetime.now(timezone.utc))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{html.escape(settings.site_title)}</title>
    <link>{html.escape(settings.site_url)}</link>
    <description>Новости и аналитика искусственного интеллекта</description>
    <language>ru</language>
    <lastBuildDate>{last_build}</lastBuildDate>
    <atom:linkrel="self" type="application/rss+xml"
               href="{html.escape(settings.site_url)}/rss.xml" />
{chr(10).join(items_xml)}
  </channel>
</rss>
"""


def _format_pubdate(value) -> str:
    if not value:
        now = datetime.now(timezone.utc)
        return format_datetime(now)
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        else:
            dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return format_datetime(dt)
    except (ValueError, TypeError):
        return format_datetime(datetime.now(timezone.utc))