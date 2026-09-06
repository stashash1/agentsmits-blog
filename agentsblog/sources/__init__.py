"""Source registry and generic parsers — implementation lands in stage 2."""
from agentsblog.sources.base import (  # noqa: F401
    ChangelogMdSource,
    HtmlSource,
    Registry,
    RssSource,
    SourceBase,
    fetch,
    make_article_id,
)
from agentsblog.sources.registry import (  # noqa: F401
    SOURCES_META,
    add_meta,
    all_meta,
    all_scanners,
    get_meta,
    get_scanner,
    register_all,
)

__all__ = [
    "ChangelogMdSource", "HtmlSource", "Registry", "RssSource", "SourceBase",
    "fetch", "make_article_id",
    "SOURCES_META", "add_meta", "all_meta", "all_scanners",
    "get_meta", "get_scanner", "register_all",
]