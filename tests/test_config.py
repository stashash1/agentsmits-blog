"""Tests for config.py — Settings env handling + path resolution."""
from __future__ import annotations

import os
from pathlib import Path

from agentsblog.config import Settings


def test_defaults(tmp_path: Path):
    s = Settings(root=tmp_path, data_dir=None, public_dir=None)
    assert s.telegram_target == "@agentsSmits"
    assert s.quiet_hours_start == 23
    assert s.quiet_hours_end == 8
    assert s.tz_offset == 3
    assert s.resolved_data_dir == (tmp_path / "data").resolve()
    assert s.resolved_public_dir == (tmp_path / "public").resolve()
    assert s.db_path == (tmp_path / "data" / "blog.db").resolve()


def test_env_overrides(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AGENTSBLOG_TELEGRAM_TARGET", "@my_test_channel")
    monkeypatch.setenv("AGENTSBLOG_QUIET_HOURS_START", "22")
    monkeypatch.setenv("AGENTSBLOG_QUIET_HOURS_END", "7")
    monkeypatch.setenv("AGENTSBLOG_MAX_PUBLISH_PER_RUN", "10")
    s = Settings(root=tmp_path)
    assert s.telegram_target == "@my_test_channel"
    assert s.quiet_hours_start == 22
    assert s.quiet_hours_end == 7
    assert s.max_publish_per_run == 10


def test_quiet_hours_validation():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(quiet_hours_start=25)
    with pytest.raises(ValidationError):
        Settings(quiet_hours_end=-1)


def test_parse_mode_none_is_accepted(monkeypatch, tmp_path):
    monkeypatch.setenv("AGENTSBLOG_TELEGRAM_PARSE_MODE", "")
    s = Settings(root=tmp_path)
    assert s.telegram_parse_mode is None

    monkeypatch.setenv("AGENTSBLOG_TELEGRAM_PARSE_MODE", "None")
    s2 = Settings(root=tmp_path)
    assert s2.telegram_parse_mode is None

    monkeypatch.setenv("AGENTSBLOG_TELEGRAM_PARSE_MODE", "HTML")
    s3 = Settings(root=tmp_path)
    assert s3.telegram_parse_mode == "HTML"


def test_settings_do_not_touch_disk_on_import(tmp_path, monkeypatch):
    """Importing Settings should not read .env or create dirs."""
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("AGENTSBLOG_ROOT", raising=False)
    s = Settings()
    assert s.telegram_target == "@agentsSmits"  # default
    # resolved_data_dir returns a Path, but does NOT mkdir
    s.resolved_data_dir  # accessing the property
    assert not (tmp_path / "data").exists()