"""Site builder command — full implementation lands in stage 5."""
from __future__ import annotations

import sys

from agentsblog.config import Settings


def build_site_cmd(settings: Settings) -> int:
    from agentsblog.site import build_site
    summary = build_site(settings)
    print(f"[OK] Site built in {settings.resolved_public_dir}")
    print(f"  feed:     {summary['feed_count']} posts")
    print(f"  archive:  {summary['archive_count']} posts")
    print(f"  articles: {summary['articles_count']} posts in {summary['categories']} categories")
    print(f"  wrote:    {', '.join(summary['wrote'])}")
    return 0