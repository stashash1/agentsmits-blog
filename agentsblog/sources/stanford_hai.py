"""Stanford HAI AI Index Report — single static link, annual."""
from __future__ import annotations

from datetime import datetime, timezone

from agentsblog.models import Article, ArticleStatus, SourceKind
from agentsblog.sources.base import Registry, fetch, make_article_id, strip_html
from agentsblog.sources.registry import add_meta


@Registry.register("stanford_hai")
class StanfordHaiSource:
    def __init__(self, source):
        self.source = source
        self.page_url = "https://hai.stanford.edu/ai-index/2026-ai-index-report"

    def scan(self):
        # Returns nothing — the report is a hardcoded annual event, not
        # something we discover via scraping. Replaced by an explicit
        # `add-manual` call when the next report drops.
        return []


add_meta(id="stanford_hai", name="Stanford HAI",
         url="https://hai.stanford.edu/ai-index/2026-ai-index-report",
         kind=SourceKind.HTML, tier=3,
         notes="Hardcoded annual report; use `add-manual` for new editions")