"""Tests for the HTTP API (FastAPI)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agentsblog.api.server import create_app
from agentsblog.config import Settings


@pytest.fixture
def app_client(tmp_settings):
    """FastAPI TestClient wired to a fresh tmp DB."""
    # Override token for testing
    s = tmp_settings.model_copy(update={"api_token": "test-token"})
    app = create_app(s)
    return TestClient(app), s


def _auth(token: str = "test-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Public endpoints ───────────────────────────────────────────────

def test_root_is_public(app_client):
    client, _ = app_client
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "agentsblog"


def test_healthz_is_public(app_client):
    client, s = app_client
    r = client.get("/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["telegram_target"] == s.telegram_target


def test_stats_requires_auth(app_client):
    client, _ = app_client
    r = client.get("/stats")
    assert r.status_code == 401


def test_stats_rejects_bad_token(app_client):
    client, _ = app_client
    r = client.get("/stats", headers=_auth("wrong"))
    assert r.status_code == 403


def test_stats_with_auth(app_client):
    client, _ = app_client
    r = client.get("/stats", headers=_auth())
    assert r.status_code == 200
    data = r.json()
    assert "pending" in data
    assert "published" in data


# ── POST /articles ─────────────────────────────────────────────────

def test_add_article_minimal(app_client):
    client, _ = app_client
    body = {
        "title": "Anthropic releases Claude 4",
        "url": "https://www.anthropic.com/news/claude-4",
        "source": "anthropic",
    }
    r = client.post("/articles", json=body, headers=_auth())
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["source"] == "anthropic"
    assert data["title"] == "Anthropic releases Claude 4"
    assert data["status"] == "pending"


def test_add_article_auto_registers_source(app_client):
    client, _ = app_client
    body = {
        "title": "Big news",
        "url": "https://example.com/x",
        "source": "new_source_we_havent_seen",
    }
    r = client.post("/articles", json=body, headers=_auth())
    assert r.status_code == 201
    # Verify source was created
    stats = client.get("/stats", headers=_auth()).json()
    assert stats["sources"] >= 1


def test_add_article_with_analysis(app_client):
    client, _ = app_client
    body = {
        "title": "Deep dive",
        "url": "https://example.com/y",
        "source": "anthropic",
        "agent_impact": "Big impact on agents",
        "business_impact": "Enterprise ready",
        "it_impact": "New patterns",
        "tags": ["agents", "release"],
        "importance": 5,
    }
    r = client.post("/articles", json=body, headers=_auth())
    assert r.status_code == 201
    data = r.json()
    assert data["importance"] == 5


def test_add_article_invalid_url(app_client):
    client, _ = app_client
    body = {
        "title": "Bad url",
        "url": "not-a-url",
        "source": "anthropic",
    }
    r = client.post("/articles", json=body, headers=_auth())
    assert r.status_code == 422


def test_add_article_importance_out_of_range(app_client):
    client, _ = app_client
    body = {
        "title": "x", "url": "https://e.com", "source": "anthropic",
        "importance": 10,
    }
    r = client.post("/articles", json=body, headers=_auth())
    assert r.status_code == 422


def test_add_article_dedup_same_url(app_client):
    """Same URL → same id, second call updates."""
    client, _ = app_client
    body = {
        "title": "Same news",
        "url": "https://e.com/dup",
        "source": "anthropic",
    }
    r1 = client.post("/articles", json=body, headers=_auth())
    r2 = client.post("/articles", json=body, headers=_auth())
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


# ── POST /publish/{id} ────────────────────────────────────────────

def test_publish_by_id_missing(app_client):
    client, _ = app_client
    r = client.post("/publish/nonexistent", headers=_auth())
    assert r.status_code == 404


def test_publish_by_id_no_analysis(app_client):
    client, _ = app_client
    # Add without analysis
    r = client.post("/articles", json={
        "title": "x", "url": "https://e.com/no-analysis",
        "source": "anthropic",
    }, headers=_auth())
    aid = r.json()["id"]
    r2 = client.post(f"/publish/{aid}?allow_during_quiet=true",
                     headers=_auth())
    assert r2.status_code == 422


def test_publish_by_id_quiet_hours(app_client):
    client, s = app_client
    # Force quiet hours
    s2 = s.model_copy(update={"quiet_hours_start": 0, "quiet_hours_end": 23})
    app2 = create_app(s2)
    c2 = TestClient(app2)
    # Add with analysis
    r = c2.post("/articles", json={
        "title": "x", "url": "https://e.com/qh",
        "source": "anthropic", "agent_impact": "Impact",
    }, headers=_auth())
    aid = r.json()["id"]
    # Try to publish — should hit quiet hours
    r2 = c2.post(f"/publish/{aid}", headers=_auth())
    assert r2.status_code == 429


def test_publish_by_id_happy_path(app_client, monkeypatch):
    """Stub telegram send to verify orchestration."""
    client, _ = app_client
    r = client.post("/articles", json={
        "title": "x", "url": "https://e.com/happy",
        "source": "anthropic", "agent_impact": "Big impact",
    }, headers=_auth())
    aid = r.json()["id"]

    from unittest.mock import patch
    from agentsblog.publishing.telegram import SendResult
    with patch("agentsblog.api.server.publish_one") as mock_pub:
        mock_pub.return_value = {"ok": True, "msg_id": 5555,
                                 "reason": "sent", "article_id": aid}
        r2 = client.post(f"/publish/{aid}?allow_during_quiet=true",
                         headers=_auth())
        assert r2.status_code == 200
        data = r2.json()
        assert data["message_id"] == 5555
        assert data["status"] == "published"


# ── POST /scan ─────────────────────────────────────────────────────

def test_scan_endpoint(app_client, monkeypatch):
    client, _ = app_client
    from unittest.mock import patch
    from agentsblog.scanner import run_scan as real_run_scan
    with patch("agentsblog.scanner.run_scan") as mock_scan:
        mock_scan.return_value = {"run_id": "test", "new_pending": 5}
        r = client.post("/scan", headers=_auth())
        assert r.status_code == 200
        assert r.json()["new_pending"] == 5


def test_scan_endpoint_requires_auth(app_client):
    client, _ = app_client
    r = client.post("/scan")
    assert r.status_code == 401


# ── Open mode (no token) ──────────────────────────────────────────

def test_open_mode_no_token(tmp_settings, db):
    """When api_token is empty, all endpoints work without Authorization header."""
    s = tmp_settings.model_copy(update={"api_token": ""})
    app = create_app(s)
    c = TestClient(app)
    r = c.get("/stats")
    assert r.status_code == 200
    r = c.post("/articles", json={
        "title": "x", "url": "https://e.com", "source": "anthropic",
    })
    assert r.status_code == 201