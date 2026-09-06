"""Perplexity AI blog — Cloudflare-blocked.

Returns empty. Use `add-manual` for major releases.
"""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, SourceBase
from agentsblog.sources.registry import add_meta


@Registry.register("perplexity")
class PerplexitySource(SourceBase):
    def scan(self):
        return []


add_meta(id="perplexity", name="Perplexity AI",
         url="https://www.perplexity.ai/hub/blog",
         kind=SourceKind.HTML, tier=2,
         notes="Cloudflare-blocked; currently returns empty")