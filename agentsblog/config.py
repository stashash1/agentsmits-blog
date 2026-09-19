"""Centralized settings for agentsblog.

All env-overridable, validated at startup. Importing this module does NOT touch
disk or environment — it's a pure value object. The single source of truth.

Replaces both `pipeline/_config.py` (path + Telegram constants) and the
duplicated `QUIET_HOURS_*` definitions in `pipeline/metrics.py`.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT_DEFAULT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """All runtime configuration. Load via `Settings()` or `Settings.from_env()`."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTSBLOG_",
        env_file=PROJECT_ROOT_DEFAULT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Paths
    root: Path = Field(default=PROJECT_ROOT_DEFAULT)
    data_dir: Path | None = None
    public_dir: Path | None = None

    # Telegram
    telegram_account: str = "default"
    telegram_channel: str = "telegram"
    telegram_target: str = "@agentsSmits"
    telegram_parse_mode: Literal["HTML", "MARKDOWN", "NONE"] | None = "HTML"
    telegram_max_len: int = 4096  # Telegram hard limit per sendMessage

    # Direct Bot API path (bypass openclaw CLI when gateway path is broken).
    # bot_token_file: path to a file with the bot token (one line, trimmed).
    # telegram_chat_id: numeric chat_id to send to (skips getChat resolution).
    bot_token_file: Path | None = None
    telegram_chat_id: str | None = None

    # Quiet hours (TZ-aware window for not publishing)
    quiet_hours_start: int = 23  # inclusive
    quiet_hours_end: int = 8  # exclusive
    tz_offset: int = 3  # MSK = UTC+3

    # Publishing
    max_publish_per_run: int = 5
    duplicate_window_seconds: int = 86_400  # 24h fingerprint dedup
    # Min importance (1-5) for an item to be sent as a standalone post.
    # Items below this threshold are skipped (queued for digests or dropped).
    min_publish_importance: int = 4
    # Max standalone posts per source per run (diversity cap).
    max_per_source_per_run: int = 2
    # Group same-source releases within this window into one digest post.
    release_group_window_days: int = 7

    # Editorial policy: quality is required before any automatic delivery.
    editorial_required: bool = True
    editorial_min_score: int = Field(default=75, ge=0, le=100)
    editorial_max_age_days: int = Field(default=5, ge=1, le=30)
    editorial_max_daily_posts: int = Field(default=3, ge=1, le=20)
    editorial_min_interval_minutes: int = Field(default=180, ge=0)
    editorial_analysis_batch: int = Field(default=4, ge=1, le=20)
    editorial_model: str = "qwen3:14b"
    editorial_review_model: str = "qwen3:14b"
    editorial_ollama_url: str = "http://127.0.0.1:11434"
    editorial_author_style: str = "Технический разбор: объясни механизм, ограничения и конкретный пример применения. Точно, глубоко, без хайпа."

    # Site
    site_title: str = "AI Агенты Смита"
    site_url: str = "https://stashash1.github.io/agentsmits-blog"
    rss_limit: int = 20

    # AGI counter (display only — no longer decremented)
    agi_base_days: int = 1460
    agi_start_date: str = "2026-01-01"

    # API (optional)
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    api_token: str = ""  # empty = no auth (dev only)

    # Logging
    log_level: str = "INFO"

    # ── Computed paths (not env-overridable directly) ──

    @property
    def resolved_data_dir(self) -> Path:
        d = self.data_dir or (self.root / "data")
        return d.resolve()

    @property
    def resolved_public_dir(self) -> Path:
        d = self.public_dir or (self.root / "public")
        return d.resolve()

    @property
    def db_path(self) -> Path:
        return self.resolved_data_dir / "blog.db"

    @property
    def events_log(self) -> Path:
        return self.resolved_data_dir / "events.log"

    @property
    def telegram_audit(self) -> Path:
        return self.resolved_data_dir / "telegram_audit.log"

    @property
    def resolved_bot_token_file(self) -> Path | None:
        if self.bot_token_file is None:
            return None
        path = self.bot_token_file.expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    # ── Validators ──

    @field_validator("quiet_hours_start", "quiet_hours_end")
    @classmethod
    def _validate_hour(cls, v: int) -> int:
        if not 0 <= v <= 23:
            raise ValueError("quiet hours must be in 0..23")
        return v

    @field_validator("telegram_parse_mode", mode="before")
    @classmethod
    def _parse_mode_none(cls, v):
        # Allow "None"/"" to mean "no parse_mode" (plain text)
        if v in (None, "", "None", "none"):
            return None
        return v

    @classmethod
    def from_env(cls) -> "Settings":
        """Load settings honoring env vars + .env file."""
        return cls()
