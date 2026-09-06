"""GitHub Copilot changelog via RSS."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, RssSource
from agentsblog.sources.registry import add_meta


@Registry.register("github_copilot")
class GitHubCopilotSource(RssSource):
    feed_url = "https://github.blog/changelog/label/copilot/feed/"
    cutoff_days = 14
    per_source_limit = 10


add_meta(id="github_copilot", name="GitHub Copilot",
         url="https://github.blog/changelog/label/copilot/feed/",
         kind=SourceKind.RSS, tier=2)