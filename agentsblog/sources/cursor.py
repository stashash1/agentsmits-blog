"""Cursor changelog via HTML scraping."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from agentsblog.models import Article, ArticleStatus, SourceKind
from agentsblog.sources import base as _b
from agentsblog.sources.base import Registry, make_article_id
from agentsblog.sources.registry import add_meta


@Registry.register("cursor")
class CursorSource:
    def __init__(self, source):
        self.source = source
        self.page_url = "https://cursor.com/changelog"
        self.per_source_limit = 10

    def scan(self):
        result = _b.fetch(self.page_url, timeout=15)
        if not result.body:
            return []
        pattern = re.compile(
            r'href="/changelog/([a-z0-9][a-z0-9-]*)"[^>]*>([^<]{10,200})</a>',
            re.IGNORECASE,
        )
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        seen: set[str] = set()
        out = []
        for m in pattern.finditer(result.body):
            slug = m.group(1)
            title = m.group(2).strip()
            if len(title) < 10 or slug in seen:
                continue
            seen.add(slug)
            url = f"https://cursor.com/changelog/{slug}"
            out.append(Article(
                id=make_article_id(self.source.id, url),
                source_id=self.source.id,
                title=title, url=url, date=today,
                importance=4, status=ArticleStatus.PENDING,
            ))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="cursor", name="Cursor",
         url="https://cursor.com/changelog",
         kind=SourceKind.HTML, tier=2)