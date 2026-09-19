"""CLI publishing behavior without network calls."""
from argparse import Namespace
from unittest.mock import patch

from agentsblog.cli_pipeline import add_manual_cmd, publish_cmd
from agentsblog.db import get_article
from agentsblog.models import ArticleStatus
from agentsblog.publishing.telegram import SendResult


def test_add_manual_publish_flag_sends_and_marks_published(tmp_settings, db):
    args = Namespace(source="manual", url="https://example.com/new-release",
                     title="New release", summary="", importance=4,
                     agent_impact="Useful for agents", business_impact="",
                     it_impact="", tags="", publish=True)
    with patch("agentsblog.publishing.publisher._is_quiet_now", return_value=False), \
         patch("agentsblog.publishing.publisher.tg_send", return_value=SendResult(
             ok=True, msg_id=101, reason="sent")) as send:
        assert add_manual_cmd(args, tmp_settings) == 0
    send.assert_called_once()
    article = db.execute("SELECT id FROM articles").fetchone()
    assert get_article(db, article["id"]).status is ArticleStatus.PUBLISHED
    assert add_manual_cmd(args, tmp_settings) == 2


def test_publish_command_reports_failed_delivery(tmp_settings):
    args = Namespace(limit=1, allow_during_quiet=True, dry_run=False)
    with patch("agentsblog.publishing.publisher.run_publish", return_value={
        "run_id": "test", "published": 0, "failed": 1, "skipped": 0,
        "agi_days": 1, "agi_percent": 1,
    }):
        assert publish_cmd(args, tmp_settings) == 1
