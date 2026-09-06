"""Source registry — maps source_id → Source metadata + Scanner class.

Two parallel structures:

1. `Registry` (in base.py) — populated by `@Registry.register("id")` decorators
   on scanner classes. Returns scanner classes by id.

2. `SOURCES_META` (here) — populated by `add_meta()` calls below. Returns
   frozen `Source` models (tier, kind, url, ...) by id.

A source is registered iff BOTH the scanner class and its meta are present.
"""
from __future__ import annotations

from agentsblog.models import Source, SourceKind
from agentsblog.sources.base import Registry, SourceBase


SOURCES_META: dict[str, Source] = {}


def add_meta(
    *,
    id: str,
    name: str,
    url: str,
    kind: SourceKind,
    tier: int,
    notes: str = "",
) -> Source:
    """Register source metadata. Idempotent."""
    src = Source(
        id=id, name=name, url=url, kind=kind, tier=tier,
        enabled=True, notes=notes,
    )
    SOURCES_META[id] = src
    return src


def get_meta(source_id: str) -> Source | None:
    return SOURCES_META.get(source_id)


def all_meta() -> list[Source]:
    return list(SOURCES_META.values())


# ── Import all concrete source modules (side-effect: registers scanners) ──

def register_all() -> None:
    """Import every source module so its @Registry.register decorator fires."""
    import agentsblog.sources.anthropic       # noqa: F401
    import agentsblog.sources.openai          # noqa: F401
    import agentsblog.sources.deepmind        # noqa: F401
    import agentsblog.sources.mistral         # noqa: F401
    import agentsblog.sources.meta_ai         # noqa: F401
    import agentsblog.sources.microsoft_ai    # noqa: F401
    import agentsblog.sources.deepseek        # noqa: F401
    import agentsblog.sources.xai             # noqa: F401
    import agentsblog.sources.huggingface     # noqa: F401
    import agentsblog.sources.cohere          # noqa: F401
    import agentsblog.sources.perplexity      # noqa: F401
    import agentsblog.sources.claude_code     # noqa: F401
    import agentsblog.sources.github_copilot  # noqa: F401
    import agentsblog.sources.cursor          # noqa: F401
    import agentsblog.sources.rbc             # noqa: F401
    import agentsblog.sources.techcrunch      # noqa: F401
    import agentsblog.sources.justai          # noqa: F401
    import agentsblog.sources.neural_digest   # noqa: F401
    import agentsblog.sources.google_ai       # noqa: F401
    import agentsblog.sources.arxiv           # noqa: F401
    import agentsblog.sources.stanford_hai    # noqa: F401
    import agentsblog.sources.vc_ru           # noqa: F401


def get_scanner(source_id: str) -> type[SourceBase] | None:
    """Look up the scanner class for a source id."""
    return Registry.get(source_id)


def all_scanners() -> list[tuple[str, Source, type[SourceBase]]]:
    """Return (id, source_meta, scanner_class) for every registered source."""
    out: list[tuple[str, Source, type[SourceBase]]] = []
    for source_id in Registry.ids():
        meta = SOURCES_META.get(source_id)
        scanner = Registry.get(source_id)
        if meta and scanner:
            out.append((source_id, meta, scanner))
    return out