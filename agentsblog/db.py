"""SQLite layer for agentsblog.

Single source of truth for all mutable state. Replaces the 14 JSON files in
`data/` (pending_queue.json, selection_queue.json, narratives.json, ...).

Why SQLite over JSON files:
- Atomic transactions (no half-saved state on crash)
- Indexes for fast dedup (URL, ID lookups)
- Concurrent reads, single-writer (handles our cron-overlapping case)
- Migrations via simple version table
- JSON exports on demand for back-compat with old pipeline/

Why stdlib sqlite3 (not sqlalchemy):
- Zero external deps — keeps the project portable
- The schema is small and stable; ORM overhead would be overkill
- Pydantic models (models.py) act as the high-level schema
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from agentsblog.models import Article, ArticleStatus, SourceHealth


# ── Schema migrations ──────────────────────────────────────────────

SCHEMA_VERSION = 2

INIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    kind TEXT NOT NULL,                 -- rss | html | api | changelog_md
    tier INTEGER NOT NULL DEFAULT 3,    -- 1 | 2 | 3
    enabled INTEGER NOT NULL DEFAULT 1, -- 0 | 1 (boolean)
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    url_norm TEXT NOT NULL,             -- url.rstrip('/') for fast dedup
    date TEXT NOT NULL,                 -- YYYY-MM-DD from source
    status TEXT NOT NULL DEFAULT 'pending',
    summary TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 3,
    decayed_importance REAL NOT NULL DEFAULT 0,
    ai_impact_json TEXT,
    is_breakthrough INTEGER NOT NULL DEFAULT 0,
    breakthrough_score INTEGER NOT NULL DEFAULT 0,
    breakthrough_reasons_json TEXT NOT NULL DEFAULT '[]',
    translated_title TEXT NOT NULL DEFAULT '',
    agent_impact TEXT NOT NULL DEFAULT '',
    business_impact TEXT NOT NULL DEFAULT '',
    it_impact TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    narrative_id TEXT,
    published_at TEXT,
    message_id INTEGER,
    is_digest_member INTEGER NOT NULL DEFAULT 0,
    digest_id TEXT,
    added_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources(id),
    FOREIGN KEY (narrative_id) REFERENCES narratives(id)
);

CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status);
CREATE INDEX IF NOT EXISTS idx_articles_url_norm ON articles(url_norm);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_importance ON articles(importance DESC);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(date DESC);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at DESC);

CREATE TABLE IF NOT EXISTS narratives (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    entities_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL DEFAULT 'auto',
    importance_max INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS narrative_items (
    narrative_id TEXT NOT NULL,
    article_id TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'followup',
    attached_at TEXT NOT NULL,
    PRIMARY KEY (narrative_id, article_id),
    FOREIGN KEY (narrative_id) REFERENCES narratives(id),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS source_health (
    source_id TEXT PRIMARY KEY,
    last_check TEXT,
    last_ok TEXT,
    last_error TEXT NOT NULL DEFAULT '',
    fail_streak INTEGER NOT NULL DEFAULT 0,
    items_found_last_run INTEGER NOT NULL DEFAULT 0,
    avg_fetch_ms INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    run_id TEXT NOT NULL,
    script TEXT NOT NULL,
    event TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_run ON events(run_id);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS editorial_reviews (
    article_id TEXT PRIMARY KEY REFERENCES articles(id),
    state TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    next_attempt_at TEXT,
    source_text TEXT NOT NULL DEFAULT '',
    report_json TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deliveries (
    delivery_key TEXT PRIMARY KEY,
    article_id TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    message_id INTEGER,
    error TEXT NOT NULL DEFAULT ''
);
"""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Connection helpers ──────────────────────────────────────────────

def connect(db_path: Path) -> sqlite3.Connection:
    """Open a connection with sane defaults.

    - WAL journal for concurrent reads (cron + manual run)
    - foreign_keys ON (off by default in SQLite!)
    - Row factory for dict-like access
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        isolation_level=None,            # autocommit; we use explicit BEGIN
        timeout=30.0,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit transaction context. Commits on success, rolls back on error."""
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init_schema(conn: sqlite3.Connection) -> int:
    """Apply all pending migrations. Returns current schema version.

    Idempotent: safe to call multiple times. Uses `CREATE TABLE IF NOT EXISTS`
    so re-running never breaks, and INSERT into schema_version is guarded
    by a version check.
    """
    # Run all DDL first (all IF NOT EXISTS — safe to repeat).
    conn.executescript(INIT_SCHEMA)

    current = conn.execute(
        "SELECT COALESCE(MAX(version), 0) AS v FROM schema_version"
    ).fetchone()["v"]

    if current < SCHEMA_VERSION:
        with transaction(conn):
            for v in range(current + 1, SCHEMA_VERSION + 1):
                conn.execute(
                    "INSERT OR IGNORE INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (v, _utcnow()),
                )
    return SCHEMA_VERSION


# ── Repository: Articles ────────────────────────────────────────────

def upsert_article(conn: sqlite3.Connection, article: Article) -> bool:
    """Insert or update an article. Returns True if newly inserted."""
    existing = conn.execute(
        "SELECT id FROM articles WHERE id = ?", (article.id,)
    ).fetchone()
    if existing:
        _update_article_row(conn, article)
        conn.execute("UPDATE editorial_reviews SET state='stale',attempts=0,source_text='' WHERE article_id=? AND state='approved'", (article.id,))
        return False
    _insert_article_row(conn, article)
    return True


def _insert_article_row(conn: sqlite3.Connection, a: Article) -> None:
    conn.execute(
        """INSERT INTO articles (
            id, source_id, title, url, url_norm, date, status,
            summary, description, importance, decayed_importance, ai_impact_json,
            is_breakthrough, breakthrough_score, breakthrough_reasons_json,
            translated_title, agent_impact, business_impact, it_impact, tags_json,
            narrative_id, published_at, message_id,
            is_digest_member, digest_id, added_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            a.id, a.source_id, a.title, a.url, a.url_normalized, a.date, a.status.value,
            a.summary, a.description, a.importance, a.decayed_importance,
            json.dumps(a.ai_impact) if a.ai_impact else None,
            int(a.is_breakthrough), a.breakthrough_score,
            json.dumps(a.breakthrough_reasons),
            a.translated_title, a.agent_impact, a.business_impact, a.it_impact,
            json.dumps(a.tags),
            a.narrative_id,
            a.published_at.isoformat() if a.published_at else None,
            a.message_id,
            int(a.is_digest_member), a.digest_id,
            a.added_at.isoformat(), a.updated_at.isoformat(),
        ),
    )


def _update_article_row(conn: sqlite3.Connection, a: Article) -> None:
    conn.execute(
        """UPDATE articles SET
            source_id = ?, title = ?, url = ?, url_norm = ?, date = ?, status = ?,
            summary = ?, description = ?, importance = ?, decayed_importance = ?,
            ai_impact_json = ?,
            is_breakthrough = ?, breakthrough_score = ?, breakthrough_reasons_json = ?,
            translated_title = ?, agent_impact = ?, business_impact = ?, it_impact = ?,
            tags_json = ?, narrative_id = ?,
            published_at = ?, message_id = ?,
            is_digest_member = ?, digest_id = ?,
            updated_at = ?
        WHERE id = ?""",
        (
            a.source_id, a.title, a.url, a.url_normalized, a.date, a.status.value,
            a.summary, a.description, a.importance, a.decayed_importance,
            json.dumps(a.ai_impact) if a.ai_impact else None,
            int(a.is_breakthrough), a.breakthrough_score,
            json.dumps(a.breakthrough_reasons),
            a.translated_title, a.agent_impact, a.business_impact, a.it_impact,
            json.dumps(a.tags),
            a.narrative_id,
            a.published_at.isoformat() if a.published_at else None,
            a.message_id,
            int(a.is_digest_member), a.digest_id,
            _utcnow(),
            a.id,
        ),
    )


def get_article(conn: sqlite3.Connection, article_id: str) -> Article | None:
    row = conn.execute("SELECT * FROM articles WHERE id = ?", (article_id,)).fetchone()
    return _row_to_article(row) if row else None


def list_pending(
    conn: sqlite3.Connection,
    *,
    min_importance: int = 1,
    limit: int | None = None,
) -> list[Article]:
    """Pending articles ordered by importance desc, then date desc."""
    sql = """SELECT * FROM articles
             WHERE status = 'pending' AND importance >= ?
             ORDER BY is_breakthrough DESC, importance DESC, date DESC"""
    params: tuple[Any, ...] = (min_importance,)
    if limit is not None:
        sql += " LIMIT ?"
        params = params + (limit,)
    rows = conn.execute(sql, params).fetchall()
    return [_row_to_article(r) for r in rows]


def is_url_known(conn: sqlite3.Connection, url: str) -> bool:
    """Fast URL-based dedup (covers ID changes between runs)."""
    norm = url.rstrip("/")
    row = conn.execute(
        "SELECT 1 FROM articles WHERE url_norm = ? LIMIT 1", (norm,)
    ).fetchone()
    return row is not None


def mark_published(
    conn: sqlite3.Connection,
    article_id: str,
    message_id: int | None,
) -> None:
    """Atomic transition: PENDING/FAILED → PUBLISHED."""
    now = _utcnow()
    conn.execute(
        """UPDATE articles SET
            status = ?, published_at = ?, message_id = ?, updated_at = ?
        WHERE id = ? AND status IN ('pending', 'failed')""",
        (ArticleStatus.PUBLISHED.value, now, message_id, now, article_id),
    )


# ── Repository: Source health ──────────────────────────────────────

def record_source_check(
    conn: sqlite3.Connection,
    source_id: str,
    *,
    ok: bool,
    items_found: int = 0,
    fetch_ms: int = 0,
    error: str = "",
) -> None:
    """Update source health. Resets fail_streak on success, increments on fail."""
    now = _utcnow()
    existing = conn.execute(
        "SELECT fail_streak, last_ok FROM source_health WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    fail_streak = 0 if ok else (existing["fail_streak"] + 1 if existing else 1)
    new_last_ok = now if ok else (existing["last_ok"] if existing and existing["last_ok"] else None)

    conn.execute(
        """INSERT INTO source_health
            (source_id, last_check, last_ok, last_error, fail_streak,
             items_found_last_run, avg_fetch_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            last_check = excluded.last_check,
            last_ok = excluded.last_ok,
            last_error = excluded.last_error,
            fail_streak = excluded.fail_streak,
            items_found_last_run = excluded.items_found_last_run,
            avg_fetch_ms = excluded.avg_fetch_ms
        """,
        (
            source_id, now, new_last_ok, error, fail_streak, items_found, fetch_ms,
        ),
    )


def upsert_source(conn: sqlite3.Connection, source) -> bool:
    """Insert or update a source row from a Source model."""
    row = conn.execute("SELECT id FROM sources WHERE id = ?", (source.id,)).fetchone()
    conn.execute(
        """INSERT INTO sources (id, name, url, kind, tier, enabled, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            url = excluded.url,
            kind = excluded.kind,
            tier = excluded.tier,
            notes = excluded.notes
        """,
        (
            source.id, source.name, source.url, source.kind.value, source.tier,
            int(source.enabled), source.notes,
        ),
    )
    return row is None


def get_source_health(conn: sqlite3.Connection, source_id: str) -> SourceHealth | None:
    row = conn.execute(
        "SELECT * FROM source_health WHERE source_id = ?", (source_id,)
    ).fetchone()
    if not row:
        return None
    return SourceHealth(
        source_id=row["source_id"],
        last_check=_parse_dt(row["last_check"]),
        last_ok=_parse_dt(row["last_ok"]),
        last_error=row["last_error"],
        fail_streak=row["fail_streak"],
        items_found_last_run=row["items_found_last_run"],
        avg_fetch_ms=row["avg_fetch_ms"],
    )


# ── Repository: Events ──────────────────────────────────────────────

def append_event(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    script: str,
    event: str,
    severity: str = "info",
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """INSERT INTO events (ts, run_id, script, event, severity, details_json)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            _utcnow(), run_id, script, event, severity,
            json.dumps(details or {}, ensure_ascii=False),
        ),
    )


# ── Helpers ────────────────────────────────────────────────────────

def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _row_to_article(row: sqlite3.Row) -> Article:
    return Article(
        id=row["id"],
        source_id=row["source_id"],
        title=row["title"],
        url=row["url"],
        date=row["date"],
        status=ArticleStatus(row["status"]),
        summary=row["summary"],
        description=row["description"],
        importance=row["importance"],
        decayed_importance=row["decayed_importance"],
        ai_impact=json.loads(row["ai_impact_json"]) if row["ai_impact_json"] else None,
        is_breakthrough=bool(row["is_breakthrough"]),
        breakthrough_score=row["breakthrough_score"],
        breakthrough_reasons=json.loads(row["breakthrough_reasons_json"]),
        translated_title=row["translated_title"],
        agent_impact=row["agent_impact"],
        business_impact=row["business_impact"],
        it_impact=row["it_impact"],
        tags=json.loads(row["tags_json"]),
        narrative_id=row["narrative_id"],
        published_at=_parse_dt(row["published_at"]),
        message_id=row["message_id"],
        is_digest_member=bool(row["is_digest_member"]),
        digest_id=row["digest_id"],
        added_at=_parse_dt(row["added_at"]) or datetime.now(timezone.utc),
        updated_at=_parse_dt(row["updated_at"]) or datetime.now(timezone.utc),
    )
