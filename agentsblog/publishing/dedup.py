"""3-level dedup for Telegram publishing.

Level 1: Article id already published (DB query)
Level 2: Article URL already published (DB query)
Level 3: Same text fingerprint was sent within N seconds (recently_sent.json)

All checks happen against the SQLite DB + a small JSON cache for text
fingerprints. Pure functions where possible.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from agentsblog.config import Settings


def text_fingerprint(text: str) -> str:
    """Stable hash of the first 400 chars — used to detect duplicate sends."""
    return hashlib.sha256((text or "")[:400].encode("utf-8")).hexdigest()[:16]


def _load_recent(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_recent(path: Path, items: list[dict]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump({"items": items}, f, indent=2, ensure_ascii=False)
    except OSError as e:
        # Don't break publishing on cache-save failure
        print(f"[DEDUP WARN] save failed: {e}", flush=True)


def was_recently_sent(
    text: str, settings: Settings, *,
    within_seconds: int | None = None,
) -> Literal[False] | int | bool:
    """True if the same text was recorded as sent within N seconds.

    Returns:
        - False: definitely not sent (no match)
        - True: sent, no msg_id stored
        - int: sent, here's the msg_id
    """
    path = settings.resolved_data_dir / "recently_sent.json"
    window = within_seconds or settings.duplicate_window_seconds
    fp = text_fingerprint(text)
    now_ts = datetime.now(timezone.utc).timestamp()
    items = _load_recent(path)
    if isinstance(items, dict):
        items = items.get("items", [])
    for it in items:
        if it.get("fp") == fp and (now_ts - it.get("ts", 0)) < window:
            mid = it.get("msg_id")
            return mid if mid is not None else True
    return False


def record_sent(text: str, msg_id: int, settings: Settings) -> None:
    """Record a sent message. Prunes entries older than 7 days; keeps last 200."""
    path = settings.resolved_data_dir / "recently_sent.json"
    fp = text_fingerprint(text)
    now_ts = datetime.now(timezone.utc).timestamp()
    items = _load_recent(path)
    if isinstance(items, dict):
        items = items.get("items", [])
    items.insert(0, {
        "fp": fp, "ts": now_ts, "msg_id": msg_id,
        "text_head": (text or "")[:80],
    })
    cutoff = now_ts - 7 * 86400
    items = [it for it in items if it.get("ts", 0) >= cutoff][:200]
    _save_recent(path, items)