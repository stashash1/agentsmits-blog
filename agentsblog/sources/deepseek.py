"""DeepSeek blog — JS-rendered, no RSS.

Returns empty until a working endpoint is found. Use `add-manual` for
critical releases.
"""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, SourceBase
from agentsblog.sources.registry import add_meta


@Registry.register("deepseek")
class DeepSeekSource(SourceBase):
    """JS-rendered — currently returns empty.

    TODO: when DeepSeek publishes an RSS / Atom feed, swap this for RssSource.
    """
    def scan(self):
        return []


add_meta(id="deepseek", name="DeepSeek",
         url="https://deepseek.com/blog",
         kind=SourceKind.HTML, tier=1,
         notes="JS-rendered; currently returns empty")