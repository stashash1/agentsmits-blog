"""Neural Digest (Russian AI news aggregator) via RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("neural_digest")
class NeuralDigestSource(RssSource):
    feed_url = "https://neural-digest.ru/feed/"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="neural_digest", name="Neural Digest",
         url="https://neural-digest.ru/feed/",
         kind=SourceKind.RSS, tier=3)