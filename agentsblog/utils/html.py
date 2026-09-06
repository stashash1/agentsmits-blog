"""HTML escaping helpers — single place, no surprises.

Telegram parse_mode=HTML requires `&`, `<`, `>` escaped. Quotes too if
attributes are involved. We don't auto-link: URLs are sent on separate
lines so Telegram's native URL preview kicks in.
"""
from __future__ import annotations

_ESCAPE_TABLE = str.maketrans({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
})


def escape(text: str) -> str:
    """Escape for Telegram HTML / generic HTML embedding."""
    return (text or "").translate(_ESCAPE_TABLE)