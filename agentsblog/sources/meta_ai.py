"""Meta AI blog via RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("meta_ai")
class MetaAISource(RssSource):
    feed_url = "https://ai.meta.com/blog/rss.xml"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="meta_ai", name="Meta AI",
         url="https://ai.meta.com/blog/rss.xml",
         kind=SourceKind.RSS, tier=1)