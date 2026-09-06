"""HTTP API server command — wired up via FastAPI."""
from __future__ import annotations

import argparse

from agentsblog.config import Settings


def serve_cmd(args: argparse.Namespace, settings: Settings) -> int:
    try:
        import uvicorn  # noqa: F401
    except ImportError:
        print(
            "ERROR: uvicorn not installed.\n"
            "  Install with: pip install -e '.[api]'\n"
            "  Or: pip install fastapi uvicorn",
            file=__import__("sys").stderr,
        )
        return 1

    from agentsblog.api.server import create_app
    app = create_app(settings)
    host = args.host or settings.api_host
    port = args.port or settings.api_port
    print(f"[OK] Starting agentsblog API on http://{host}:{port}")
    if settings.api_token:
        print("  Auth: bearer token REQUIRED (Authorization: Bearer <token>)")
    else:
        print("  Auth: DISABLED (set AGENTSBLOG_API_TOKEN to enable)")
    print("  Endpoints:")
    print("    GET  /")
    print("    GET  /healthz")
    print("    GET  /stats        (auth)")
    print("    POST /articles     (auth)")
    print("    POST /publish/{id} (auth)")
    print("    POST /scan         (auth)")
    print()
    print("  Ctrl+C to stop")

    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0