"""Mistral AI news via HTML scraping."""
from __future__ import annotations

import re

from agentsblog.models import SourceKind
from agentsblog.sources.base import HtmlSource, Registry, make_article_id
from agentsblog.sources.registry import add_meta


@Registry.register("mistral")
class MistralSource(HtmlSource):
    page_url = "https://mistral.ai/news/"
    timeout = 15
    per_source_limit = 10

    def extract_articles(self, html):
        pattern = re.compile(r'href="(https://mistral\.ai/news/[^"]+)"[^>]*>([^<]{10,100})<')
        seen: set[str] = set()
        out = []
        for m in pattern.finditer(html):
            url = m.group(1)
            title = m.group(2).strip()
            if len(title) < 10 or url in seen:
                continue
            seen.add(url)
            out.append(self._make_article(
                url=url, title=title,
                date="",  # mistral.ai/news doesn't expose dates in HTML
            ))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="mistral", name="Mistral AI",
         url="https://mistral.ai/news/",
         kind=SourceKind.HTML, tier=1)