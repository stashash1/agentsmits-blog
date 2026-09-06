"""TechCrunch AI category RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("techcrunch")
class TechCrunchSource(RssSource):
    feed_url = "https://techcrunch.com/category/artificial-intelligence/feed/"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="techcrunch", name="TechCrunch AI",
         url="https://techcrunch.com/category/artificial-intelligence/feed/",
         kind=SourceKind.RSS, tier=3)