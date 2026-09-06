"""OpenAI news via RSS feed."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("openai")
class OpenAISource(RssSource):
    feed_url = "https://openai.com/news/rss.xml"
    cutoff_days = 14
    per_source_limit = 10

    def _post_filter(self, article) -> int:
        # IPO / S-1 / acquisition bumps importance
        bump = 0
        url_l = article.url.lower()
        if any(x in url_l for x in ("s-1", "confidential", "ipo", "acquisition")):
            bump = 1
        return min(5, article.importance + bump)


add_meta(id="openai", name="OpenAI",
         url="https://openai.com/news/rss.xml",
         kind=SourceKind.RSS, tier=1)