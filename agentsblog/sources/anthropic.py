"""Anthropic news via sitemap.xml.

Sitemap lastmod ≠ publication date — we sort by lastmod desc and take the top N.
Titles from slug (titlecased) — good enough for a news digest. Real titles
can be patched in by an analyzer pass later.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from agentsblog.models import SourceKind
from agentsblog.sources import base as _b
from agentsblog.sources.base import Registry, parse_iso_to_date
from agentsblog.sources.registry import add_meta


_KNOWN_TITLES = {
    "seoul-office-partnerships-korean-ai-ecosystem": "Seoul Office: Partnerships for Korea's AI Ecosystem",
    "developing-nuclear-safeguards-for-ai-through-public-private-partnership": "Developing Nuclear Safeguards for AI",
    "tcs-anthropic-partnership": "Anthropic Partners with TCS to Advance Enterprise AI Safety",
    "core-views-on-ai-safety": "Core Views on AI Safety",
    "claude-fable-5-mythos-5": "Claude Fable 5 and Mythos 5",
    "fable-mythos-access": "Fable and Mythos Access Update",
    "anthropic-public-record": "Anthropic Public Record",
    "dxc-anthropic-alliance": "DXC and Anthropic Alliance",
    "claude-corps": "Introducing Claude Corps",
    "chris-olah-pope-leo-encyclical": "Chris Olah, Pope Leo, and the Encyclical on AI",
    "widening-conversation-ai": "Widening the Conversation on AI",
    "AI-enabled-cyber-threats-mitre-attack": "AI-Enabled Cyber Threats and MITRE ATT&CK",
    "services-track-partner-hub": "Services Track Partner Hub",
    "expanding-project-glasswing": "Expanding Project Glasswing",
    "confidential-draft-s1-sec": "Confidential Draft S-1",
    "announcing-our-updated-responsible-scaling-policy": "Announcing Our Updated Responsible Scaling Policy",
}


@Registry.register("anthropic")
class AnthropicSource:
    source = None  # populated at instantiation

    def __init__(self, source):
        self.source = source
        self.sitemap_url = "https://www.anthropic.com/sitemap.xml"
        self.cutoff_days = 7
        self.per_source_limit = 5

    def scan(self):
        result = _b.fetch(self.sitemap_url)
        if not result.body:
            return []
        today = datetime.now(timezone.utc)
        cutoff = today - timedelta(days=self.cutoff_days)

        entries: list[tuple[datetime, str, str, str]] = []
        for block in re.findall(r"<url>(.*?)</url>", result.body, re.DOTALL):
            loc_m = re.search(r"<loc>(https://www\.anthropic\.com/news/[^<]+)</loc>", block)
            lm_m = re.search(r"<lastmod>([^<]+)</lastmod>", block)
            if not loc_m:
                continue
            url = loc_m.group(1)
            if url == "https://www.anthropic.com/news":
                continue
            slug = url.rstrip("/").split("/")[-1]
            dt, date_str = parse_iso_to_date(lm_m.group(1)) if lm_m else (None, None)
            if dt and dt < cutoff:
                continue
            entries.append((dt or today, date_str or today.strftime("%Y-%m-%d"), slug, url))

        entries.sort(key=lambda x: x[0], reverse=True)
        out = []
        for _, date_str, slug, url in entries[: self.per_source_limit]:
            title = _KNOWN_TITLES.get(slug) or slug.replace("-", " ").title()
            out.append(self._make_article(url=url, title=title, date=date_str))
        return out

    def _make_article(self, *, url, title, date):
        from agentsblog.models import Article, ArticleStatus
        from agentsblog.sources.base import make_article_id
        return Article(
            id=make_article_id(self.source.id, url),
            source_id=self.source.id,
            title=title, url=url, date=date,
            importance=4, status=ArticleStatus.PENDING,
        )


add_meta(id="anthropic", name="Anthropic",
         url="https://www.anthropic.com/news",
         kind=SourceKind.HTML, tier=1,
         notes="Uses sitemap.xml; titles from slug or KNOWN_TITLES")