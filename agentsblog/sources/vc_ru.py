"""VC.ru AI — no RSS, only search page. Returns empty."""
from __future__ import annotations

from agentsblog.models import SourceKind
from agentsblog.sources.base import Registry, SourceBase
from agentsblog.sources.registry import add_meta


@Registry.register("vc_ru")
class VcRuSource(SourceBase):
    def scan(self):
        return []


add_meta(id="vc_ru", name="VC.ru AI",
         url="https://vc.ru/search?q=AI",
         kind=SourceKind.HTML, tier=3,
         notes="No RSS; returns empty")