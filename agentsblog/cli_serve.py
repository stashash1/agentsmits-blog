"""HTTP API server (FastAPI). Full implementation lands in stage 4."""
from __future__ import annotations

import argparse
import sys

from agentsblog.config import Settings


def serve_cmd(args: argparse.Namespace, settings: Settings) -> int:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "ERROR: uvicorn not installed.\n"
            "  Install with: pip install -e '.[api]'\n"
            "  Or: pip install fastapi uvicorn",
            file=sys.stderr,
        )
        return 1
    print("serve: implementation lands in stage 4 (api/)", file=sys.stderr)
    return 1