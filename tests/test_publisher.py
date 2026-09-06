"""Tests for publishing — formatter, dedup, decay, orchestrator."""
from __future__ import annotations

from unittest.mock import patch

from agentsblog.models import Article, ArticleStatus
from agentsblog.publishing.dedup import (
    record_sent, text_fingerprint, was_recently_sent,
)
from agentsblog.publishing.decay import apply_decay
from agentsblog.publishing.formatter import (
    compute_agi, format_breakthrough, format_standard,
)


# ── text_fingerprint ────────────────────────────────────────────────

def test_fingerprint_stable_for_same_text():
    assert text_fingerprint("hello") == text_fingerprint("hello")


def test_fingerprint_first_400_chars_only():
    """Trailing changes don't affect fingerprint — short-text dedup window."""
    assert text_fingerprint("a" * 500) == text_fingerprint("a" * 500 + "extra")


def test_fingerprint_handles_empty():
    assert text_fingerprint("") != "" or text_fingerprint("") == ""  # doesn't crash


# ── was_recently_sent / record_sent ─────────────────────────────────

def test_record_then_was_recently_sent(tmp_settings):
    record_sent("Hello world", 42, tmp_settings)
    result = was_recently_sent("Hello world", tmp_settings, within_seconds=60)
    assert result == 42


def test_was_recently_sent_no_match(tmp_settings):
    assert was_recently_sent("Never seen", tmp_settings, within_seconds=60) is False


def test_was_recently_sent_handles_missing_file(tmp_settings):
    # recently_sent.json doesn't exist yet
    assert was_recently_sent("anything", tmp_settings, within_seconds=60) is False


def test_was_recently_sent_old_outside_window(tmp_settings):
    """Entries older than the window are ignored."""
    import time
    record_sent("old message", 99, tmp_settings)
    # Wait won't help — record_sent writes now_ts. So we craft an old one
    # by manipulating the JSON directly.
    from agentsblog.utils.time import local_now
    p = tmp_settings.resolved_data_dir / "recently_sent.json"
    import json
    with p.open("w") as f:
        json.dump({"items": [
            {"fp": text_fingerprint("old message"), "ts": time.time() - 9999,
             "msg_id": 99, "text_head": "old message"}
        ]}, f)
    assert was_recently_sent("old message", tmp_settings, within_seconds=60) is False


# ── apply_decay ─────────────────────────────────────────────────────

def test_decay_recent_item_no_change():
    from datetime import datetime, timezone, timedelta
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    a = Article(id="x", source_id="openai", title="t", url="https://e.com",
                date=today, importance=4)
    decayed = apply_decay(a)
    assert decayed.decayed_importance >= 3.9  # near-unchanged


def test_decay_old_item_lower():
    a = Article(id="x", source_id="openai", title="t", url="https://e.com",
                date="2020-01-01", importance=5)
    decayed = apply_decay(a)
    # 6+ years old → huge penalty → floor at 1
    assert decayed.decayed_importance == 1.0


def test_decay_returns_copy_not_mutate():
    a = Article(id="x", source_id="openai", title="t", url="https://e.com",
                date="2026-09-06", importance=4)
    a2 = apply_decay(a)
    assert a is not a2
    assert a.decayed_importance == 0.0  # unchanged


# ── Formatters ──────────────────────────────────────────────────────

def test_format_standard_returns_none_without_analysis():
    a = Article(id="x", source_id="openai", title="t", url="https://e.com",
                date="2026-09-06", summary="s")
    assert format_standard(a, agi_days=1000, agi_percent=50) is None


def test_format_standard_basic():
    a = Article(
        id="x", source_id="openai",
        title="OpenAI launches GPT-5",
        url="https://openai.com/gpt-5",
        date="2026-09-06",
        summary="Big release",
        agent_impact="Tool use is way better",
        business_impact="Boosts enterprise adoption",
        it_impact="New API patterns",
        translated_title="OpenAI выпускает GPT-5",
    )
    out = format_standard(a, agi_days=1000, agi_percent=50)
    assert out is not None
    assert "OpenAI выпускает GPT-5" in out
    assert "Tool use is way better" in out
    assert "https://openai.com/gpt-5" in out
    assert "1000 дней" in out
    assert "50%" in out


def test_format_breakthrough_banner():
    a = Article(
        id="x", source_id="openai",
        title="GPT-5 achieves AGI",
        url="https://openai.com/agi",
        date="2026-09-06",
        summary="Mamba breakthrough",
        agent_impact="New architecture", business_impact="", it_impact="",
        is_breakthrough=True,
        breakthrough_reasons=["new_architecture_or_technique:2", "sota_or_milestone:1"],
    )
    out = format_breakthrough(a, agi_days=500, agi_percent=60)
    assert out is not None
    assert "ПРОРЫВ" in out
    assert "Что нового" in out
    assert "GPT-5 achieves AGI" in out


# ── compute_agi ─────────────────────────────────────────────────────

def test_compute_agi_handles_bad_start_date(tmp_settings):
    """If start_date is malformed, we still return sane numbers."""
    s = tmp_settings.model_copy(update={"agi_start_date": "garbage"})
    days, pct = compute_agi(s)
    assert days > 0
    assert 0 < pct < 100


def test_compute_agi_typical(tmp_settings):
    s = tmp_settings.model_copy(update={
        "agi_base_days": 1460,
        "agi_start_date": "2026-01-01",
    })
    days, pct = compute_agi(s)
    # ~9 months elapsed → ~80% complete → ~292 days left
    assert 100 < days < 1300


# ── publish_one (no actual Telegram send) ───────────────────────────

def test_publish_one_quiet_hours_returns_reason(tmp_settings):
    a = Article(
        id="x", source_id="openai", title="t", url="https://e.com",
        date="2026-09-06",
        agent_impact="x",
    )
    # Force quiet hours
    s = tmp_settings.model_copy(update={
        "quiet_hours_start": 0, "quiet_hours_end": 23,  # entire day is quiet
    })
    from agentsblog.publishing.publisher import publish_one
    r = publish_one(a, s, agi_days=1000, agi_percent=50)
    assert r["ok"] is False
    assert r["reason"] == "quiet_hours"


def test_publish_one_no_analysis_returns_reason(tmp_settings):
    a = Article(id="x", source_id="openai", title="t", url="https://e.com", date="")
    from agentsblog.publishing.publisher import publish_one
    r = publish_one(a, tmp_settings, agi_days=1000, agi_percent=50)
    assert r["ok"] is False
    assert r["reason"] == "no_analysis"


def test_publish_one_happy_path_calls_telegram(tmp_settings):
    a = Article(
        id="x", source_id="openai", title="t", url="https://e.com",
        date="2026-09-06",
        agent_impact="big impact",
        translated_title="Заголовок",
    )
    from agentsblog.publishing.publisher import publish_one
    from agentsblog.publishing.telegram import SendResult
    with patch("agentsblog.publishing.publisher.tg_send") as mock_send:
        mock_send.return_value = SendResult(ok=True, msg_id=7777,
                                           reason="sent", duration_ms=100)
        r = publish_one(a, tmp_settings, agi_days=1000, agi_percent=50)
        assert r["ok"] is True
        assert r["msg_id"] == 7777
        assert mock_send.called


def test_publish_one_dedup_skips_send(tmp_settings):
    a = Article(
        id="x", source_id="openai", title="t", url="https://e.com",
        date="2026-09-06",
        agent_impact="big impact",
        translated_title="Заголовок",
    )
    record_sent("Dedup test", 123, tmp_settings)
    from agentsblog.publishing.formatter import format_standard
    expected_text = format_standard(a, agi_days=1000, agi_percent=50)
    assert expected_text is not None
    record_sent(expected_text, 999, tmp_settings)

    from agentsblog.publishing.publisher import publish_one
    from agentsblog.publishing.telegram import SendResult
    with patch("agentsblog.publishing.publisher.tg_send") as mock_send:
        mock_send.return_value = SendResult(ok=True, msg_id=999,
                                           reason="sent", duration_ms=100)
        r = publish_one(a, tmp_settings, agi_days=1000, agi_percent=50)
        assert r["ok"] is True
        assert r["reason"] == "dedup"
        assert r["msg_id"] == 999
        assert not mock_send.called


# ── run_publish orchestrator ────────────────────────────────────────

def test_run_publish_quiet_hours_short_circuits(tmp_settings, db, make_article):
    """When quiet hours span the entire day, nothing is published."""
    # Pre-seed one publishable article
    art = make_article(
        db, id="q-1", title="Title", agent_impact="Impact",
        importance=4,
    )
    from agentsblog.db import upsert_article
    upsert_article(db, art)

    s = tmp_settings.model_copy(update={
        "quiet_hours_start": 0, "quiet_hours_end": 23,
    })
    from agentsblog.publishing.publisher import run_publish
    summary = run_publish(s, allow_during_quiet=False)
    assert summary["published"] == 0
    assert summary["quiet_deferred"] >= 1


def test_run_publish_dry_run_does_not_mark_published(tmp_settings, db, make_article):
    art = make_article(
        db, id="d-1", title="T", agent_impact="x", importance=4,
    )
    from agentsblog.db import upsert_article
    upsert_article(db, art)

    with patch("agentsblog.publishing.publisher.tg_send") as mock_send:
        from agentsblog.publishing.telegram import SendResult
        mock_send.return_value = SendResult(ok=True, msg_id=1000,
                                           reason="sent", duration_ms=50)
        from agentsblog.publishing.publisher import run_publish
        summary = run_publish(tmp_settings, dry_run=True, allow_during_quiet=True)
        # We "published" 1 in the run log, but DB state is unchanged
        assert summary["published"] >= 1
        # Verify article is STILL pending (dry-run)
        from agentsblog.db import get_article
        row = get_article(db, "d-1")
        assert row.status is ArticleStatus.PENDING
        assert row.message_id is None


def test_run_publish_marks_published(tmp_settings, db, make_article):
    art = make_article(
        db, id="p-1", title="T", agent_impact="big", importance=4,
    )
    from agentsblog.db import upsert_article
    upsert_article(db, art)

    with patch("agentsblog.publishing.publisher.tg_send") as mock_send:
        from agentsblog.publishing.telegram import SendResult
        mock_send.return_value = SendResult(ok=True, msg_id=4242,
                                           reason="sent", duration_ms=50)
        from agentsblog.publishing.publisher import run_publish
        summary = run_publish(tmp_settings, allow_during_quiet=True)
        assert summary["published"] >= 1
        from agentsblog.db import get_article
        row = get_article(db, "p-1")
        assert row.status is ArticleStatus.PUBLISHED
        assert row.message_id == 4242