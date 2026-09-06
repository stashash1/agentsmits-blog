"""Typed models — single source of truth for all data flowing through the pipeline.

Replaces raw dicts everywhere. Validated at construction, JSON-serializable via
Pydantic's `model_dump_json()`. Frozen dataclasses for value-like things
(breakthrough result), mutable models for stateful ones (Article, Narrative).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# ════════════════════════════════════════════════════════════════
# Enums
# ════════════════════════════════════════════════════════════════

class ArticleStatus(StrEnum):
    """Article lifecycle states."""
    PENDING = "pending"          # scanned, awaiting publish
    PUBLISHED = "published"      # sent to TG
    SKIPPED = "skipped"          # deduped / filtered / stale
    FAILED = "failed"            # send error, will retry
    DIGESTED = "digested"        # absorbed into a release/industry digest

class SourceKind(StrEnum):
    """How a source delivers content."""
    RSS = "rss"
    HTML = "html"
    API = "api"            # structured API (arxiv, etc.)
    CHANGELOG_MD = "changelog_md"  # raw GitHub CHANGELOG.md


# ════════════════════════════════════════════════════════════════
# Core models
# ════════════════════════════════════════════════════════════════

class Source(BaseModel):
    """A monitored news source."""
    model_config = ConfigDict(frozen=True)

    id: str                          # e.g. "anthropic"
    name: str                        # e.g. "Anthropic"
    url: str                         # primary URL (RSS feed or HTML page)
    kind: SourceKind
    tier: Literal[1, 2, 3] = 3
    enabled: bool = True
    notes: str = ""                  # e.g. "Cloudflare-blocked, fail-open"


class Article(BaseModel):
    """A single news item. Mutable state throughout the pipeline.

    Required fields are sourced from RSS/scan; optional fields are added
    later by scoring / analysis / breakthrough detection / publish.
    """
    model_config = ConfigDict(extra="forbid")

    id: str                          # deterministic from URL
    source_id: str                   # FK → Source.id
    title: str
    url: str
    date: str                        # YYYY-MM-DD from source
    status: ArticleStatus = ArticleStatus.PENDING

    # Content
    summary: str = ""                # RSS description / first paragraph
    description: str = ""            # extended description if any

    @field_validator("summary", "description", "agent_impact",
                     "business_impact", "it_impact", "translated_title",
                     mode="before")
    @classmethod
    def _str_from_none(cls, v):
        """Legacy data has None for analysis fields — coerce to empty string."""
        return v if v is not None else ""

    # Scoring
    importance: int = Field(default=3, ge=1, le=5)
    decayed_importance: float = 0.0  # soft signal; >= importance by default
    ai_impact: dict[str, Any] | None = None  # full ImpactResult dump

    # Breakthrough detection
    is_breakthrough: bool = False
    breakthrough_score: int = 0
    breakthrough_reasons: list[str] = Field(default_factory=list)

    # Analysis (filled by analyze step / manual entry)
    translated_title: str = ""
    agent_impact: str = ""
    business_impact: str = ""
    it_impact: str = ""
    tags: list[str] = Field(default_factory=list)

    # Narrative clustering
    narrative_id: str | None = None

    # Publishing
    published_at: datetime | None = None
    message_id: int | None = None

    # Digest membership (QW-3)
    is_digest_member: bool = False
    digest_id: str | None = None

    # Internal bookkeeping
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("article id must be non-empty")
        return v

    @field_validator("url")
    @classmethod
    def _url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("article url must be non-empty")
        return v

    @property
    def url_normalized(self) -> str:
        """URL with trailing slash stripped — for dedup comparison."""
        return self.url.rstrip("/")

    @property
    def is_publishable(self) -> bool:
        """True if article has enough analysis to be published."""
        return bool(self.agent_impact)


# ════════════════════════════════════════════════════════════════
# Scoring outputs (frozen — pure functions)
# ════════════════════════════════════════════════════════════════

class ImpactResult(BaseModel):
    """Result of impact scoring — stored alongside Article."""
    model_config = ConfigDict(frozen=True)

    base: int
    tier: Literal[1, 2, 3]
    keyword_bonus: int
    version_bonus: int
    penalty: int
    total: int
    matched_keywords: tuple[str, ...] = ()
    matched_categories: tuple[str, ...] = ()


class BreakthroughResult(BaseModel):
    """Result of breakthrough detection."""
    model_config = ConfigDict(frozen=True)

    is_breakthrough: bool
    score: int
    matched_architectures: tuple[str, ...] = ()
    matched_sota: tuple[str, ...] = ()
    matched_open_source: tuple[str, ...] = ()
    matched_non_breakthrough: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()


# ════════════════════════════════════════════════════════════════
# Narrative clustering
# ════════════════════════════════════════════════════════════════

class NarrativeItem(BaseModel):
    article_id: str
    role: Literal["primary", "followup"] = "followup"
    attached_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Narrative(BaseModel):
    """A cluster of related articles — entity-overlap based."""
    model_config = ConfigDict(extra="forbid")

    id: str                          # e.g. "n-00042"
    title: str
    status: Literal["active", "cooling", "dormant"] = "active"
    first_seen: datetime
    last_seen: datetime
    entities: list[str] = Field(default_factory=list)
    items: list[NarrativeItem] = Field(default_factory=list)
    source: str = "auto"
    importance_max: int = 0


# ════════════════════════════════════════════════════════════════
# Observability
# ════════════════════════════════════════════════════════════════

class MetricEvent(BaseModel):
    """Structured event for the central event log."""
    model_config = ConfigDict(extra="forbid")

    ts: datetime
    run_id: str
    script: str                      # "scan" | "publish" | "analyze" | ...
    event: str                       # "started" | "completed" | "error" | ...
    severity: Literal["debug", "info", "warn", "error"] = "info"
    details: dict[str, Any] = Field(default_factory=dict)


class SourceHealth(BaseModel):
    """Rolling health snapshot for a single source."""
    source_id: str
    last_check: datetime | None = None
    last_ok: datetime | None = None
    last_error: str = ""
    fail_streak: int = 0
    items_found_last_run: int = 0
    avg_fetch_ms: int = 0