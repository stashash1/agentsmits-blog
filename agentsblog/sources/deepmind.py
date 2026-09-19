"""DeepMind blog via sitemap + per-page fetch.

DeepMind articles are loaded via JavaScript — fetching the blog index
yields no article links. So we parse the sitemap, sort by URL desc
(newest first), and fetch each page to extract its `<title>`.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from agentsblog.models import Article, ArticleStatus, SourceKind
from agentsblog.sources import base as _b
from agentsblog.sources.base import Registry, make_article_id
from agentsblog.sources.registry import add_meta


@Registry.register("deepmind")
class DeepMindSource:
    def __init__(self, source):
        self.source = source
        self.sitemap_url = "https://deepmind.google/sitemap.xml"
        self.per_source_limit = 5

    def scan(self):
        result = _b.fetch(self.sitemap_url)
        self.last_fetch = result
        if not result.body:
            return []
        urls = re.findall(r"<loc>(https://deepmind\.google/blog/[^<]+)</loc>", result.body)
        urls = [u for u in urls if not u.endswith("/blog/")]
        urls.sort(reverse=True)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = []
        for url in urls[: self.per_source_limit]:
            page = _b.fetch(url)
            if not page.body:
                continue
            title_m = re.search(r"<title[^>]*>([^<]+)</title>", page.body)
            if not title_m:
                continue
            title = re.sub(r"\s*[-–] Google DeepMind\s*$", "", title_m.group(1).strip())
            if len(title) < 10:
                continue
            desc_m = re.search(r'<meta content="([^"]+)" name=description', page.body)
            if not desc_m:
                desc_m = re.search(r'<meta content="([^"]+)" property="og:description"', page.body)
            desc = desc_m.group(1).strip() if desc_m else ""
            out.append(Article(
                id=make_article_id(self.source.id, url),
                source_id=self.source.id,
                title=title, url=url, date=today,
                summary=desc, importance=4, status=ArticleStatus.PENDING,
            ))
        return out


add_meta(id="deepmind", name="Google DeepMind",
         url="https://deepmind.google/sitemap.xml",
         kind=SourceKind.HTML, tier=1,
         notes="Sitemap → fetch each blog page")
