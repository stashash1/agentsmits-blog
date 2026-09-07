"""Direct Telegram Bot API transport — bypasses the broken OpenClaw gateway path.

Use this when `openclaw message send` is unhealthy (e.g. accountId-derived target
mismatch, sendRichMessage 404, terminal-disconnect cache). Reads the bot token
from a local file path (env: AGENTSBLOG_BOT_TOKEN_FILE) and uses numeric chat_id
from AGENTSBLOG_TELEGRAM_CHAT_ID.

The Bot API is HTTPS-only — works through the same network stack (hosts file
mapping for api.telegram.org → 149.154.167.99, AmneziaVPN route) that the
browser test confirmed works for the same token.
"""
from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


log = logging.getLogger(__name__)


BOT_API_BASE = "https://api.telegram.org"


@dataclass(frozen=True)
class DirectSendResult:
    ok: bool
    msg_id: int = 0
    reason: str = ""
    duration_ms: int = 0
    error: str = ""


def _read_token_file(path: str | os.PathLike) -> str | None:
    """Read the bot token from a file. Whitespace-trimmed, single line.

    Uses utf-8-sig to transparently strip a UTF-8 BOM if present.
    """
    try:
        p = Path(path).expanduser()
        if not p.exists():
            log.warning("direct_api: token file %s missing", p)
            return None
        text = p.read_text(encoding="utf-8-sig").strip()
        # Bot token format: <digits>:<base64-ish>[35+]; total ~45-47 chars
        if not text or ":" not in text or len(text) < 30:
            log.warning("direct_api: token file %s has invalid content", p)
            return None
        return text
    except Exception as e:
        log.warning("direct_api: failed to read token file: %s", e)
        return None


def _resolve_chat_id(target: str, bot_token: str, *, timeout: float = 15.0) -> str | None:
    """Resolve @username or numeric chat_id to a numeric chat_id via getChat."""
    if not target:
        return None
    # Already numeric? (e.g. -100xxx, positive int)
    s = str(target).strip()
    if s.lstrip("-").isdigit():
        return s
    # Otherwise it's a username; resolve via getChat
    url = f"{BOT_API_BASE}/bot{bot_token}/getChat"
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps({"chat_id": s}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        ctx = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        log.error("direct_api: getChat HTTP %s: %s", e.code, e.read().decode("utf-8", errors="replace")[:200])
        return None
    except Exception as e:
        log.error("direct_api: getChat error: %s", e)
        return None

    if not body.get("ok"):
        log.error("direct_api: getChat not ok: %s", body.get("description", body))
        return None
    result = body.get("result") or {}
    cid = result.get("id")
    return str(cid) if cid is not None else None


def send(
    text: str,
    *,
    chat_id: str,
    bot_token: str,
    parse_mode: str | None = None,
    retries: int = 2,
    delay: float = 4.0,
    timeout: float = 20.0,
) -> DirectSendResult:
    """Send a message via Telegram Bot API directly (urllib).

    Returns DirectSendResult. chat_id may be a numeric string or @username —
    the latter is resolved via getChat first.
    """
    if not (text or "").strip():
        return DirectSendResult(ok=False, reason="error", error="empty_text")
    if not bot_token:
        return DirectSendResult(ok=False, reason="error", error="missing_token")

    # Resolve target to numeric chat_id if needed
    resolved = _resolve_chat_id(chat_id, bot_token, timeout=timeout)
    if not resolved:
        return DirectSendResult(ok=False, reason="error", error=f"cannot resolve chat_id from {chat_id!r}")

    url = f"{BOT_API_BASE}/bot{bot_token}/sendMessage"
    payload: dict = {"chat_id": resolved, "text": text[:4096]}
    if parse_mode and parse_mode.upper() in ("HTML", "MARKDOWN", "MARKDOWNV2"):
        payload["parse_mode"] = parse_mode

    last_err = ""
    t0 = time.monotonic()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                duration_ms = int((time.monotonic() - t0) * 1000)
                if body.get("ok"):
                    msg_id = int((body.get("result") or {}).get("message_id") or 0)
                    return DirectSendResult(ok=True, msg_id=msg_id, reason="sent",
                                           duration_ms=duration_ms)
                last_err = body.get("description", "unknown error")[:200]
                log.warning("direct_api: send not ok (attempt %d): %s", attempt + 1, last_err)
                # Some errors are non-retriable (chat not found, etc.)
                if body.get("error_code") in (400, 403, 404):
                    break
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
            log.warning("direct_api: HTTP %d (attempt %d): %s", e.code, attempt + 1, last_err)
            if e.code in (400, 403, 404):
                break
        except Exception as e:
            last_err = str(e)[:200]
            log.warning("direct_api: send attempt %d failed: %s", attempt + 1, last_err)
        if attempt < retries - 1:
            time.sleep(delay)

    duration_ms = int((time.monotonic() - t0) * 1000)
    return DirectSendResult(ok=False, msg_id=0, reason="error", error=last_err,
                            duration_ms=duration_ms)


def send_from_env(text: str, settings, *,
                  chat_id: str | None = None,
                  parse_mode: str | None = None) -> DirectSendResult:
    """High-level: read token from env-configured file, target from env or settings.

    Required env (or .env):
        AGENTSBLOG_BOT_TOKEN_FILE=path/to/file  (file contains the bot token, one line)
        AGENTSBLOG_TELEGRAM_CHAT_ID=-100xxx     (numeric chat_id, optional — falls back to settings.telegram_target)
    """
    token_path = os.environ.get("AGENTSBLOG_BOT_TOKEN_FILE")
    if not token_path:
        return DirectSendResult(ok=False, reason="error", error="AGENTSBLOG_BOT_TOKEN_FILE not set")

    token = _read_token_file(token_path)
    if not token:
        return DirectSendResult(ok=False, reason="error", error="bot token not readable")

    target = chat_id or os.environ.get("AGENTSBLOG_TELEGRAM_CHAT_ID") or settings.telegram_target
    pm = parse_mode or settings.telegram_parse_mode
    return send(text, chat_id=target, bot_token=token, parse_mode=pm)
