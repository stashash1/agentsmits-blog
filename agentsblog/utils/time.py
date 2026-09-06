"""Time + quiet-hours helpers — replaces the conflicting QUIET_HOURS_* constants."""
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