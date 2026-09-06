"""Generic source abstractions — the building blocks for all 21 parsers.

Replaces the 1100-line `pipeline/scan_sources.py` with a small, declarative
set of base classes. New sources become 10-20 line modules instead of
copy-pasted 50-line functions.
"""
from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Iterable

from agentsblog.models import Article, ArticleStatus, Source, SourceKind


# ── HTTP layer ─────────────────────────────────────────────────────

@dataclass
class FetchResult:
    body: str | None
    status: int = 0
    fetch_ms: int = 0
    error: str = ""


_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch(url: str, *, timeout: int = 15) -> FetchResult:
    """Simple GET with browser-like headers. Returns body or None on error.

    No retries — the scanner loop records source health and alerts on
    consecutive failures.
    """
    t0 = time.monotonic()
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": _USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read().decode("utf-8", errors="ignore")
        return FetchResult(body=data, status=r.status, fetch_ms=int((time.monotonic() - t0) * 1000))
    except urllib.error.HTTPError as e:
        return FetchResult(body=None, status=e.code, fetch_ms=int((time.monotonic() - t0) * 1000),
                           error=f"HTTP {e.code}")
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        return FetchResult(body=None, status=0, fetch_ms=int((time.monotonic() - t0) * 1000),
                           error=str(e)[:200])


# ── ID generation ──────────────────────────────────────────────────

def make_article_id(prefix: str, url: str, max_len: int = 60) -> str:
    """Deterministic short id: `<prefix>-<url-slug-or-hash>`.

    Truncating the last path segment causes collisions (different URLs ->
    same ID), so we use a hash suffix when the slug would exceed max_len.
    """
    import hashlib
    slug = url.rstrip("/").split("/")[-1]
    base = f"{prefix}-{slug}"
    if len(base) <= max_len:
        return base
    short = slug[: max_len - len(prefix) - 14]  # 12 hex + "-" + prefix
    digest = hashlib.md5(url.encode()).hexdigest()[:12]
    return f"{prefix}-{short}-{digest}"


def _normalize_url_for_dedup(url: str) -> str:
    return url.rstrip("/")


# ── RSS / Atom parsing helpers ─────────────────────────────────────

def parse_rss_items(xml: str) -> list[dict[str, str]]:
    """Extract (title, link, pubDate, description) tuples from an RSS feed.

    Handles both `<![CDATA[...]]>` and plain text in title/description.
    """
    items = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    return [rss_item_fields(item) for item in items]


def rss_item_fields(item: str) -> dict[str, str]:
    """Extract named fields from one RSS <item>."""
    return {
        "title": _xml_field(item, "title"),
        "link": _xml_field(item, "link"),
        "pubDate": _xml_field(item, "pubDate"),
        "description": _xml_field(item, "description"),
    }


def _xml_field(block: str, name: str) -> str:
    """Extract `<name>...</name>` (CDATA-aware) from a block of XML."""
    # Order matters: CDATA first (it can contain '<' / '>').
    m = re.search(rf"<{name}><!\[CDATA\[(.*?)\]\]></{name}>", block, re.DOTALL)
    if m:
        return m.group(1).strip()
    m = re.search(rf"<{name}>([^<]*)</{name}>", block, re.DOTALL)
    return m.group(1).strip() if m else ""


def parse_pubdate_to_iso(pub_date: str) -> tuple[datetime | None, str | None]:
    """Parse RFC 2822 pubDate → (datetime, YYYY-MM-DD). Returns (None, None) on failure."""
    if not pub_date:
        return None, None
    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt, dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None, None


def parse_iso_to_date(iso: str) -> tuple[datetime | None, str | None]:
    """Parse ISO 8601 timestamp (with or without Z) → (datetime, YYYY-MM-DD)."""
    if not iso:
        return None, None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt, dt.strftime("%Y-%m-%d")
    except ValueError:
        return None, None


def parse_url_embedded_date(url: str, pattern: str = r"/(\d{2})/(\d{2})/(\d{4})/") -> str | None:
    """Extract DD/MM/YYYY date from URL (RBC convention)."""
    m = re.search(pattern, url)
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"


def is_within_days(dt: datetime | None, *, cutoff_days: int, now: datetime | None = None) -> bool:
    """True if `dt` is within `cutoff_days` from `now` (or now() default).
    None dates are assumed fresh — don't block scanners on missing metadata.
    """
    if dt is None:
        return True
    now = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).days <= cutoff_days


def strip_html(s: str, max_len: int = 300) -> str:
    """Strip HTML tags + collapse whitespace + truncate."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:max_len]


# ── Source base class ──────────────────────────────────────────────

class SourceBase(ABC):
    """Base for all scanners. Subclass and implement `.scan()`.

    Lifecycle (called by `run_scan()`):
      1. fetch() → body / error
      2. parse() → raw items
      3. dedup() → known URLs filtered
      4. .scan() → list[Article]
    """

    source: Source    # populated by registry

    def __init__(self, source: Source):
        self.source = source

    @abstractmethod
    def scan(self) -> list[Article]:
        """Fetch + parse + return articles. Empty list on any failure."""

    # ── helpers subclasses can use ──

    def _make_article(
        self,
        *,
        url: str,
        title: str,
        date: str = "",
        summary: str = "",
        importance: int = 4,
    ) -> Article:
        return Article(
            id=make_article_id(self.source.id, url),
            source_id=self.source.id,
            title=title,
            url=url,
            date=date,
            summary=summary,
            importance=importance,
            status=ArticleStatus.PENDING,
        )

    def _respects_cutoff(
        self, dt: datetime | None, *, cutoff_days: int = 14,
    ) -> bool:
        return is_within_days(dt, cutoff_days=cutoff_days)


# ── Concrete generic subclasses ────────────────────────────────────

class RssSource(SourceBase):
    """Generic RSS scanner. Subclass and set `.feed_url`.

    Handles date parsing (RFC 2822), title/link/description extraction,
    and date filtering.
    """

    feed_url: str = ""
    cutoff_days: int = 14
    per_source_limit: int = 10

    def scan(self) -> list[Article]:
        result = fetch(self.feed_url)
        if not result.body:
            return []
        articles: list[Article] = []
        for item in parse_rss_items(result.body):
            if not item["title"] or not item["link"]:
                continue
            if len(item["title"]) < 10:
                continue
            dt, date_str = parse_pubdate_to_iso(item["pubDate"])
            if dt and not self._respects_cutoff(dt):
                continue
            articles.append(self._make_article(
                url=item["link"],
                title=item["title"],
                date=date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                summary=strip_html(item["description"]),
            ))
            if len(articles) >= self.per_source_limit:
                break
        return articles


class HtmlSource(SourceBase):
    """Generic HTML scanner. Subclass and implement `.extract_articles(html)`.

    Subclasses override `extract_articles` to handle site-specific markup.
    """

    page_url: str = ""
    timeout: int = 15

    def scan(self) -> list[Article]:
        result = fetch(self.page_url, timeout=self.timeout)
        if not result.body:
            return []
        return self.extract_articles(result.body)

    def extract_articles(self, html: str) -> list[Article]:  # noqa: ARG002
        # Default: empty. Subclasses parse site-specific markup.
        return []


class ChangelogMdSource(SourceBase):
    """Raw GitHub CHANGELOG.md parser (e.g. claude-code)."""

    raw_url: str = ""
    repo_label: str = ""
    max_versions: int = 5

    def scan(self) -> list[Article]:
        result = fetch(self.raw_url)
        if not result.body:
            return []
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        version_re = re.compile(r"^##\s+([0-9][^\n]+)$", re.MULTILINE)
        matches = list(version_re.finditer(result.body))
        articles: list[Article] = []
        seen: set[str] = set()
        for m in matches[: self.max_versions]:
            version = m.group(1).strip()
            if version in seen:
                continue
            seen.add(version)
            body_start = m.end()
            next_match = version_re.search(result.body, pos=body_start)
            body_end = next_match.start() if next_match else len(result.body)
            body = result.body[body_start:body_end].strip()
            summary_m = re.search(r"-\s+(.{20,200}?)[\.\n]", body)
            summary = summary_m.group(1).strip() if summary_m else ""
            article_url = (
                f"https://github.com/{self.repo_label}/blob/main/CHANGELOG.md"
                f"#{version.replace('.', '')}"
            )
            articles.append(self._make_article(
                url=article_url,
                title=f"{self.source.name} {version}",
                date=today,
                summary=summary,
            ))
        return articles


# ── Registry ────────────────────────────────────────────────────────

class Registry:
    """Source registry — populated via `@register("id")` decorator."""

    _sources: dict[str, type[SourceBase]] = {}

    @classmethod
    def register(cls, source_id: str) -> callable:
        def decorator(klass: type[SourceBase]) -> type[SourceBase]:
            cls._sources[source_id] = klass
            return klass
        return decorator

    @classmethod
    def get(cls, source_id: str) -> type[SourceBase] | None:
        return cls._sources.get(source_id)

    @classmethod
    def all(cls) -> Iterable[tuple[str, type[SourceBase]]]:
        return cls._sources.items()

    @classmethod
    def ids(cls) -> Iterable[str]:
        return cls._sources.keys()