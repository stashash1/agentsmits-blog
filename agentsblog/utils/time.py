"""Time + quiet-hours helpers - replaces the conflicting QUIET_HOURS_* constants."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def local_now(tz_offset_hours: int) -> datetime:
    """Return current time in a fixed-offset timezone (e.g. MSK = +3)."""
    return datetime.now(timezone(timedelta(hours=tz_offset_hours)))


def is_quiet_hours(
    now: datetime,
    *,
    start_hour: int,
    end_hour: int,
) -> bool:
    """True if `now` falls in the quiet window.

    Window may cross midnight: start=23, end=8 means 23:00..08:00.
    """
    h = now.hour
    if start_hour > end_hour:
        return h >= start_hour or h < end_hour
    return start_hour <= h < end_hour


def parse_iso_date(s: str) -> datetime | None:
    """Parse ISO 8601 date/datetime string to aware datetime (UTC).

    Accepts YYYY-MM-DD and YYYY-MM-DDTHH:MM:SS[Z|+HH:MM].
    Returns None on failure.
    """
    if not s:
        return None
    s = s.strip()
    # Date only: append T00:00:00Z
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        s = s + "T00:00:00+00:00"
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt