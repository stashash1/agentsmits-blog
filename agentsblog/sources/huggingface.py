"""HuggingFace blog via RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("huggingface")
class HuggingFaceSource(RssSource):
    feed_url = "https://huggingface.co/blog/feed.xml"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="huggingface", name="HuggingFace",
         url="https://huggingface.co/blog/feed.xml",
         kind=SourceKind.RSS, tier=2)