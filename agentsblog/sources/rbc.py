"""РБК Тренды via HTML scraping.

URL pattern encodes date as DD/MM/YYYY. We only match actual article URLs
(filter out navigation/UTM links) and respect the embedded date.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from agentsblog.models import Article, ArticleStatus, SourceKind
from agentsblog.sources import base as _b
from agentsblog.sources.base import Registry, make_article_id, parse_url_embedded_date
from agentsblog.sources.registry import add_meta


@Registry.register("rbc")
class RbcSource:
    def __init__(self, source):
        self.source = source
        self.page_url = "https://trends.rbc.ru/trends/industry/69e87e5f9a7947ca488a8d90"
        self.cutoff_days = 14
        self.per_source_limit = 10

    def scan(self):
        result = _b.fetch(self.page_url)
        if not result.body:
            return []
        pattern = re.compile(
            r'href="(https://www\.rbc\.ru/(?:technology_and_media|economics|politics|society)/[^"]+)"[^>]*>([^<]{20,200})<'
        )
        today = datetime.now(timezone.utc)
        cutoff = today - timedelta(days=self.cutoff_days)
        seen: set[str] = set()
        out = []
        for m in pattern.finditer(result.body):
            url = m.group(1)
            title = m.group(2).strip()
            if "utm_source" in url or "from=" in url:
                continue
            url_date = parse_url_embedded_date(url)
            if url_date:
                try:
                    dt = datetime.strptime(url_date, "%d/%m/%Y")
                    if dt < cutoff.replace(tzinfo=None):
                        continue
                except ValueError:
                    pass
            slug = url.rstrip("/").split("/")[-1]
            if len(slug) < 10 or slug in seen:
                continue
            seen.add(slug)
            out.append(Article(
                id=f"rbc-{slug}",
                source_id=self.source.id,
                title=title, url=url,
                date=url_date or today.strftime("%Y-%m-%d"),
                importance=4, status=ArticleStatus.PENDING,
            ))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="rbc", name="РБК Тренды",
         url="https://trends.rbc.ru/trends/industry/69e87e5f9a7947ca488a8d90",
         kind=SourceKind.HTML, tier=3,
         notes="Currently low-volume; URL embeds DD/MM/YYYY date")