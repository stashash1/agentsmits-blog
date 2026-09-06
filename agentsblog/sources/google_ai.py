"""Google AI Blog via RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("google_ai")
class GoogleAISource(RssSource):
    feed_url = "https://blog.google/technology/ai/rss/"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="google_ai", name="Google AI Blog",
         url="https://blog.google/technology/ai/rss/",
         kind=SourceKind.RSS, tier=3)