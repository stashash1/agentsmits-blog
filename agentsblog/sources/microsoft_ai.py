"""Microsoft AI via TechCommunity RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("microsoft_ai")
class MicrosoftAISource(RssSource):
    feed_url = "https://techcommunity.microsoft.com/api/rss/ai-and-mixed-reality/?direction=desc"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="microsoft_ai", name="Microsoft AI",
         url="https://techcommunity.microsoft.com/api/rss/ai-and-mixed-reality/?direction=desc",
         kind=SourceKind.RSS, tier=1)