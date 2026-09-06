"""JustAI blog via HTML scraping."""
from __future__ import annotations

import re

from agentsblog.models import SourceKind
from agentsblog.sources.base import HtmlSource, Registry
from agentsblog.sources.registry import add_meta


@Registry.register("justai")
class JustAISource(HtmlSource):
    page_url = "https://just-ai.com/blog/news"
    timeout = 15
    per_source_limit = 10

    def extract_articles(self, html):
        pattern = re.compile(r'href="(https://just-ai\.com/blog/[^"]+)"[^>]*>([^<]{10,200})<')
        out = []
        seen: set[str] = set()
        for m in pattern.finditer(html):
            url = m.group(1)
            title = m.group(2).strip()
            if len(title) < 10 or url in seen:
                continue
            seen.add(url)
            out.append(self._make_article(url=url, title=title))
            if len(out) >= self.per_source_limit:
                break
        return out


add_meta(id="justai", name="JustAI",
         url="https://just-ai.com/blog/news",
         kind=SourceKind.HTML, tier=3)