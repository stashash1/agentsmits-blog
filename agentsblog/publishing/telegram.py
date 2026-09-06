"""Telegram publishing wrapper around `openclaw message send`.

Encapsulates the subprocess invocation, parse-mode handling, retry logic,
and timeout-send recovery. Returns either an integer message_id (success)
or a sentinel like -1 (quiet hours) or 0 (unknown / dedup armed).

No business logic (sorting, scoring, dedup between texts) — just transport.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Literal

from agentsblog.config import Settings


log = logging.getLogger(__name__)


# ── Result type ────────────────────────────────────────────────────

@dataclass(frozen=True)
class SendResult:
    ok: bool
    msg_id: int = 0
    reason: str = ""            # "sent" | "quiet_hours" | "duplicate" | "timeout" | "error" | "sent_no_msgid"
    duration_ms: int = 0
    error: str = ""


# ── openclaw CLI invoker ───────────────────────────────────────────

def _build_cmd(text: str, settings: Settings) -> list[str]:
    cmd = [
        shutil.which("openclaw") or "openclaw",
        "message", "send",
        "--channel", settings.telegram_channel,
        "--account", settings.telegram_account,
        "--target", settings.telegram_target,
        "--message", text,
    ]
    pm = settings.telegram_parse_mode
    if pm:
        # Send parse_mode via --delivery JSON
        cmd += ["--delivery", json.dumps({"parse_mode": pm})]
    return cmd


def send(text: str, settings: Settings, *,
         retries: int = 2, delay: float = 8.0) -> SendResult:
    """Send a Telegram message via openclaw CLI.

    Returns SendResult. Caller is responsible for the message_id tracking
    and DB updates. The transport layer here only knows about the wire.
    """
    # Empty-text guard
    if not (text or "").strip():
        log.warning("send_telegram: empty text, refusing")
        return SendResult(ok=False, reason="error", error="empty_text")

    # Length guard
    text = (text or "")[: settings.telegram_max_len]

    t0 = time.monotonic()
    last_err = ""
    for attempt in range(retries):
        try:
            result = subprocess.run(
                _build_cmd(text, settings),
                capture_output=True, text=True, timeout=120,
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            stderr = (result.stderr or "")
            stdout = (result.stdout or "")

            # Detect benign state-migration warning
            if result.returncode != 0 and "Legacy state migration warnings" in stderr:
                log.info("state-migration warning; message likely delivered")
                return SendResult(ok=True, msg_id=0,
                                  reason="state_migration_warning",
                                  duration_ms=duration_ms)

            # Success path
            if result.returncode == 0:
                m = re.search(r"Message ID:\s*(\d+)", stdout)
                if m:
                    return SendResult(ok=True, msg_id=int(m.group(1)),
                                      reason="sent", duration_ms=duration_ms)
                if "Sent via telegram" in stdout:
                    return SendResult(ok=True, msg_id=0,
                                      reason="sent_no_msgid", duration_ms=duration_ms)

            # Sent despite non-zero RC
            if "Sent via telegram" in stdout:
                m = re.search(r"Message ID:\s*(\d+)", stdout)
                msg_id = int(m.group(1)) if m else 0
                return SendResult(ok=True, msg_id=msg_id,
                                  reason="sent_with_nonzero_rc",
                                  duration_ms=duration_ms,
                                  error=stderr[:200])

            # Real failure
            last_err = stderr[:300] or f"exit code {result.returncode}"
            log.warning("send attempt %d failed: %s", attempt + 1, last_err)
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - t0) * 1000)
            # Likely sent — gateway timeout
            return SendResult(ok=True, msg_id=0, reason="timeout",
                              duration_ms=duration_ms)
        except Exception as e:
            last_err = str(e)[:200]

        if attempt < retries - 1:
            time.sleep(delay)

    return SendResult(ok=False, msg_id=0, reason="error", error=last_err)