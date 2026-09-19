"""FastAPI HTTP server — manual article submission + health checks.

Endpoints:
  GET  /                  — service info
  GET  /healthz           — liveness probe
  GET  /stats             — pipeline stats (counts per status)
  POST /articles          — manually add a news article (the missing API)
  POST /publish/{id}      — publish a specific article immediately
  POST /scan              — trigger scan (async, returns run_id)

Auth: optional bearer token via AGENTSBLOG_API_TOKEN. Empty token = open.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header
from pydantic import BaseModel, Field, HttpUrl

from agentsblog.config import Settings
from agentsblog.db import (
    connect, get_article, init_schema, list_pending, mark_published,
)
from agentsblog.models import Article, ArticleStatus, Source, SourceKind
from agentsblog.publishing.formatter import compute_agi
from agentsblog.publishing.publisher import publish_one
from agentsblog.scoring.impact import extract_entities_from_item


log = logging.getLogger(__name__)


# ── Request/response models ────────────────────────────────────────

class ArticleIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    url: HttpUrl
    source: str = Field(..., min_length=1, max_length=64)
    summary: str = ""
    agent_impact: str = ""
    business_impact: str = ""
    it_impact: str = ""
    translated_title: str = ""
    tags: list[str] = Field(default_factory=list)
    importance: int = Field(default=4, ge=1, le=5)
    is_breakthrough: bool = False
    publish: bool = False  # publish immediately after adding


class ArticleOut(BaseModel):
    id: str
    source: str
    title: str
    url: str
    status: str
    importance: int
    published_at: str | None = None
    message_id: int | None = None


class StatsOut(BaseModel):
    pending: int
    published: int
    skipped: int
    failed: int
    digested: int
    sources: int
    narratives: int


class HealthOut(BaseModel):
    status: str = "ok"
    db_path: str
    api_token_set: bool
    telegram_target: str


# ── Server factory ─────────────────────────────────────────────────

def create_app(settings: Settings) -> FastAPI:
    """Build a FastAPI app wired to the given settings."""
    app = FastAPI(
        title="agentsblog API",
        version="0.2.0",
        description="Manual article submission + health checks for the AI blog pipeline",
    )

    # ── Auth dependency ──
    def auth(authorization: str | None = Header(default=None)):
        if not settings.api_token:
            return  # open mode
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_token:
            raise HTTPException(status_code=403, detail="Invalid token")
        return token

    # ── Helpers ──
    def _conn():
        conn = connect(settings.db_path)
        init_schema(conn)
        return conn

    # ── Routes ──

    @app.get("/")
    def root():
        return {
            "service": "agentsblog",
            "version": "0.2.0",
            "endpoints": [
                "GET /healthz", "GET /stats",
                "POST /articles", "POST /publish/{article_id}",
                "POST /scan",
            ],
        }

    @app.get("/healthz", response_model=HealthOut)
    def healthz():
        return HealthOut(
            status="ok",
            db_path=str(settings.db_path),
            api_token_set=bool(settings.api_token),
            telegram_target=settings.telegram_target,
        )

    @app.get("/stats", response_model=StatsOut, dependencies=[Depends(auth)])
    def stats():
        conn = _conn()
        out = {"sources": 0, "narratives": 0}
        for status in ("pending", "published", "skipped", "failed", "digested"):
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM articles WHERE status = ?", (status,)
            ).fetchone()
            out[status] = row["n"]
        out["sources"] = conn.execute("SELECT COUNT(*) AS n FROM sources").fetchone()["n"]
        out["narratives"] = conn.execute("SELECT COUNT(*) AS n FROM narratives").fetchone()["n"]
        return StatsOut(**out)

    @app.post("/articles", response_model=ArticleOut,
              status_code=201, dependencies=[Depends(auth)])
    def add_article(body: ArticleIn) -> ArticleOut:
        """Add a news article manually. THE missing API endpoint."""
        if body.publish and not body.agent_impact.strip():
            raise HTTPException(status_code=422, detail="agent_impact is required to publish")
        conn = _conn()
        # Auto-register source if missing
        existing = conn.execute(
            "SELECT id FROM sources WHERE id = ?", (body.source,)
        ).fetchone()
        if not existing:
            from agentsblog.db import upsert_source
            upsert_source(conn, Source(
                id=body.source, name=body.source.title(),
                url=str(body.url), kind=SourceKind.HTML,
                tier=3, enabled=True,
                notes="auto-created from API",
            ))

        import hashlib
        aid = f"{body.source}-{hashlib.md5(str(body.url).encode()).hexdigest()[:12]}"
        existing_article = get_article(conn, aid)
        if existing_article and existing_article.status is not ArticleStatus.PENDING:
            raise HTTPException(status_code=409, detail="article already processed")
        article = Article(
            id=aid,
            source_id=body.source,
            title=body.title,
            url=str(body.url),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            summary=body.summary,
            agent_impact=body.agent_impact,
            business_impact=body.business_impact,
            it_impact=body.it_impact,
            translated_title=body.translated_title,
            tags=body.tags,
            importance=body.importance,
            is_breakthrough=body.is_breakthrough,
            status=ArticleStatus.PENDING,
        )
        from agentsblog.db import upsert_article
        upsert_article(conn, article)
        log.info("added article %s via API", aid)

        # Optionally publish immediately
        if body.publish:
            agi_days, agi_percent = compute_agi(settings)
            result = publish_one(article, settings,
                                 agi_days=agi_days, agi_percent=agi_percent)
            if not result["ok"]:
                raise HTTPException(status_code=429 if result["reason"] == "quiet_hours" else 502,
                                    detail=f"publish failed: {result['reason']}")
            if result["ok"] and result["reason"] != "dedup":
                mark_published(conn, aid, result.get("msg_id") or 0)
                article = get_article(conn, aid)

        return ArticleOut(
            id=article.id,
            source=article.source_id,
            title=article.title,
            url=article.url,
            status=article.status.value,
            importance=article.importance,
            published_at=article.published_at.isoformat() if article.published_at else None,
            message_id=article.message_id,
        )

    @app.post("/publish/{article_id}",
              response_model=ArticleOut, dependencies=[Depends(auth)])
    def publish_by_id(article_id: str, allow_during_quiet: bool = False):
        conn = _conn()
        article = get_article(conn, article_id)
        if article is None:
            raise HTTPException(status_code=404, detail="article not found")
        if article.status is not ArticleStatus.PENDING:
            raise HTTPException(status_code=409, detail="article is not pending")
        if not article.is_publishable:
            raise HTTPException(
                status_code=422,
                detail="article has no analysis; cannot publish",
            )
        from agentsblog.utils.time import is_quiet_hours, local_now
        if not allow_during_quiet and is_quiet_hours(
            local_now(settings.tz_offset),
            start_hour=settings.quiet_hours_start,
            end_hour=settings.quiet_hours_end,
        ):
            raise HTTPException(status_code=429, detail="quiet hours; try later")
        agi_days, agi_percent = compute_agi(settings)
        result = publish_one(article, settings,
                             agi_days=agi_days, agi_percent=agi_percent,
                             allow_during_quiet=allow_during_quiet)
        if not result["ok"]:
            raise HTTPException(status_code=502, detail=f"publish failed: {result['reason']}")
        if result["ok"] and result["reason"] != "dedup":
            mark_published(conn, article_id, result.get("msg_id") or 0)
        updated = get_article(conn, article_id)
        return ArticleOut(
            id=updated.id, source=updated.source_id, title=updated.title,
            url=updated.url, status=updated.status.value,
            importance=updated.importance,
            published_at=updated.published_at.isoformat() if updated.published_at else None,
            message_id=updated.message_id,
        )

    @app.post("/scan", dependencies=[Depends(auth)])
    def trigger_scan(source: str | None = None, limit: int | None = None):
        """Trigger a scan. Returns summary."""
        from agentsblog.scanner import run_scan as do_scan
        summary = do_scan(
            settings,
            limit_sources=[source] if source else None,
            dry_run=False,
            max_items_per_source=limit,
        )
        return summary

    return app
