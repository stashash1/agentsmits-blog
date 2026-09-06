"""Site builder command stub — full implementation lands in stage 5."""
from __future__ import annotations

import sys

from agentsblog.config import Settings


def build_site_cmd(settings: Settings) -> int:
    print("build-site: implementation lands in stage 5 (site/)", file=sys.stderr)
    return 1