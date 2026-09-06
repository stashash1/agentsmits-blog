"""xAI (Grok) blog — Cloudflare-blocked.

Returns empty until bypass is found. Use `add-manual` for major Grok releases.
"""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, SourceBase
from agentsblog.sources.registry import add_meta


@Registry.register("xai")
class XaiSource(SourceBase):
    """Cloudflare blocks urllib — currently returns empty.

    TODO: when a working endpoint or RSS appears, swap for RssSource/HtmlSource.
    """
    def scan(self):
        return []


add_meta(id="xai", name="xAI",
         url="https://x.ai/blog",
         kind=SourceKind.HTML, tier=1,
         notes="Cloudflare-blocked; currently returns empty")