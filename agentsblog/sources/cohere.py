"""Cohere blog via HTML (relative /blog/<slug> URLs)."""
from __future__ import annotations

import re

from agentsblog.models import SourceKind
from agentsblog.sources.base import HtmlSource, Registry
from agentsblog.sources.registry import add_meta


@Registry.register("cohere")
class CohereSource(HtmlSource):
    page_url = "https://cohere.com/blog"
    timeout = 15
    per_source_limit = 10

    def extract_articles(self, html):
        pattern = re.compile(
            r'href="/blog/([a-z0-9][a-z0-9-]*)"[^>]*>\s*([^<]{10,200})',
            re.IGNORECASE,
        )
        seen: set[str] = set()
        out = []
        for m in pattern.finditer(html):
            slug = m.group(1)
            title = m.group(2).strip()
            if slug.startswith(("tag/", "category/")) or len(title) < 10:
                continue
            if slug in seen:
                continue
            seen.add(slug)
            url = f"https://cohere.com/blog/{slug}"
            out.append(self._make_article(url=url, title=title))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="cohere", name="Cohere",
         url="https://cohere.com/blog",
         kind=SourceKind.HTML, tier=2)