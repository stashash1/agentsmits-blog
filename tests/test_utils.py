"""Tests for utils — time + HTML escape."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agentsblog.utils.html import escape
from agentsblog.utils.time import is_quiet_hours, local_now


def test_is_quiet_hours_crossing_midnight():
    """Window 23..8 means 23:00..08:00 next day."""
    start, end = 23, 8
    assert is_quiet_hours(datetime(2026, 9, 6, 23, 0), start_hour=start, end_hour=end) is True
    assert is_quiet_hours(datetime(2026, 9, 6, 0, 0), start_hour=start, end_hour=end) is True
    assert is_quiet_hours(datetime(2026, 9, 6, 7, 59), start_hour=start, end_hour=end) is True
    assert is_quiet_hours(datetime(2026, 9, 6, 8, 0), start_hour=start, end_hour=end) is False
    assert is_quiet_hours(datetime(2026, 9, 6, 12, 0), start_hour=start, end_hour=end) is False
    assert is_quiet_hours(datetime(2026, 9, 6, 22, 59), start_hour=start, end_hour=end) is False


def test_is_quiet_hours_normal_window():
    """Window 9..18 means 09:00..18:00 same day."""
    assert is_quiet_hours(datetime(2026, 9, 6, 9, 0), start_hour=9, end_hour=18) is True
    assert is_quiet_hours(datetime(2026, 9, 6, 12, 0), start_hour=9, end_hour=18) is True
    assert is_quiet_hours(datetime(2026, 9, 6, 18, 0), start_hour=9, end_hour=18) is False
    assert is_quiet_hours(datetime(2026, 9, 6, 8, 59), start_hour=9, end_hour=18) is False


def test_local_now_returns_offset_aware():
    msk = local_now(3)
    assert msk.tzinfo is not None
    assert msk.utcoffset() == timedelta(hours=3)


def test_html_escape_basic():
    assert escape("hello") == "hello"
    assert escape("<b>bold</b>") == "&lt;b&gt;bold&lt;/b&gt;"
    assert escape("a & b") == "a &amp; b"


def test_html_escape_handles_none():
    assert escape("") == ""
    # None is tolerated — returns empty
    assert escape(None) == ""  # type: ignore[arg-type]


def test_html_escape_preserves_emoji_and_cyrillic():
    s = "🤖 Привет, мир!"
    assert escape(s) == s
    s2 = "Claude 4 is <released> & amazing"
    assert escape(s2) == "Claude 4 is &lt;released&gt; &amp; amazing"