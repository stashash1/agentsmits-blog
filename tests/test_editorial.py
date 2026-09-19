"""Behavioral quality gates, schema failures and delivery recovery."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from agentsblog.editorial import Draft, Fact, Review, analyze_article, eligibility, draft_issues
from agentsblog.models import Article
from agentsblog.publishing import delivery
from agentsblog.publishing.editorial_format import format_editorial
from agentsblog.publishing.publisher import publish_one
from agentsblog.publishing.telegram import SendResult


SOURCE = 'The adapter is transferred through object storage. Each worker loads the adapter independently.'


@pytest.fixture
def draft():
    return Draft(
        decision='publish', reason='Конкретный способ разделить обучение и генерацию.',
        headline='Как отделить обучение адаптера от генерации',
        lead='Авторы показали схему обмена адаптерами через объектное хранилище между отдельными рабочими процессами.',
        facts=[Fact(claim='Адаптер передаётся через объектное хранилище.', evidence_quote='The adapter is transferred through object storage.'),
               Fact(claim='Каждый рабочий процесс загружает адаптер самостоятельно.', evidence_quote='Each worker loads the adapter independently.')],
        technical_detail='В этой схеме обучение и генерация разделены: процессы обмениваются сохранённым адаптером через объектное хранилище, а не общей памятью.',
        why_it_matters='Такую схему можно рассмотреть, когда обучение и генерация должны работать на разных машинах.',
        take='Практический смысл здесь в разделении ресурсов; применимость нужно оценивать на своей нагрузке.',
        caveat='Источник не устанавливает универсальный выигрыш по скорости для любой нагрузки.',
        practical_step='Сравните задержку загрузки адаптера на своей инфраструктуре.',
        topics=['Инженерия'], relevance=5, novelty=4, usefulness=5)


@pytest.fixture
def review():
    return Review(approved=True, factual_accuracy=5, specificity=5, readability=5,
                  unsupported_claims=[], issues=[])


def article():
    return Article(id='test', source_id='test', title='Adapter transport', url='https://example.com/story',
                   date=datetime.now(timezone.utc).date().isoformat())


def approved(draft, review, settings):
    with patch('agentsblog.editorial.call_model'):
        return analyze_article(article(), SOURCE, settings,
                               model_call=lambda system, data, schema, settings: draft if schema is Draft else review)[0]


def test_old_analysis_cannot_pass_quality_gate(tmp_settings):
    settings = tmp_settings.model_copy(update={'editorial_required': True})
    a = article(); a.agent_impact = 'Новые конкурентные преимущества для бизнеса'
    assert 'needs_editorial_review' in eligibility(a, settings)
    with patch('agentsblog.publishing.publisher.tg_send') as send:
        assert publish_one(a, settings, agi_days=0, agi_percent=0)['reason'] == 'editorial_gate'
    send.assert_not_called()


def test_approved_draft_passes_but_edits_invalidate_it(draft, review, tmp_settings):
    s = tmp_settings.model_copy(update={'editorial_required': True})
    a = approved(draft, review, s)
    assert eligibility(a, s) == []
    a.summary = 'Новый неподтверждённый факт'
    assert 'changed_after_review' in eligibility(a, s)


def test_old_or_future_news_is_blocked(draft, review, tmp_settings):
    s = tmp_settings.model_copy(update={'editorial_required': True})
    for offset in (-20, 3):
        a = approved(draft, review, s)
        a.date = (datetime.now(timezone.utc)+timedelta(days=offset)).date().isoformat()
        assert 'outside_news_window' in eligibility(a, s)


def test_invented_quote_is_blocked_before_review(draft):
    draft.facts[0].evidence_quote = 'The product is ten times faster than anything else.'
    assert 'evidence_not_in_source' in draft_issues(draft, SOURCE)


def test_reviewer_can_reject_high_scoring_draft(draft, review, tmp_settings):
    review.unsupported_claims = ['Неподтверждённое превосходство']
    assert approved(draft, review, tmp_settings) is None


def test_analysis_persists_review_and_does_not_repeat(db, make_article, draft, review, tmp_settings):
    from agentsblog.db import upsert_article, get_article
    from agentsblog.editorial import run_analysis
    a = make_article(db, date=datetime.now(timezone.utc).date().isoformat())
    upsert_article(db, a)
    with patch('agentsblog.editorial.read_source', return_value=SOURCE) as reader, \
         patch('agentsblog.editorial.call_model', side_effect=lambda system, data, schema, settings: draft if schema is Draft else review):
        assert run_analysis(tmp_settings)['approved'] == 1
        assert run_analysis(tmp_settings)['approved'] == 0
    assert reader.call_count == 1
    assert get_article(db, a.id).ai_impact['editorial']['state'] == 'approved'
    assert db.execute('SELECT source_text FROM editorial_reviews').fetchone()[0] == SOURCE


def test_analysis_failure_backs_off_and_retains_source(db, make_article, tmp_settings):
    from agentsblog.db import upsert_article
    from agentsblog.editorial import run_analysis
    upsert_article(db, make_article(db, date=datetime.now(timezone.utc).date().isoformat()))
    with patch('agentsblog.editorial.read_source', return_value=SOURCE) as reader, \
         patch('agentsblog.editorial.call_model', side_effect=TimeoutError('model unavailable')):
        assert run_analysis(tmp_settings)['failed'] == 1
        assert run_analysis(tmp_settings)['failed'] == 0
    assert reader.call_count == 1
    row = db.execute('SELECT state,attempts,source_text,next_attempt_at FROM editorial_reviews').fetchone()
    assert tuple(row)[:3] == ('failed', 1, SOURCE)
    assert datetime.fromisoformat(row['next_attempt_at']) > datetime.now(timezone.utc)


def test_concurrent_analyzer_skips_without_model(tmp_settings):
    from agentsblog.editorial import run_analysis
    from agentsblog.utils.locking import exclusive_lock
    with exclusive_lock(tmp_settings.resolved_data_dir / 'editorial.lock') as acquired:
        assert acquired
        with patch('agentsblog.editorial.call_model') as model:
            assert run_analysis(tmp_settings)['busy'] == 1
        model.assert_not_called()


def test_html_escapes_content_and_does_not_show_countdown(draft, review, tmp_settings):
    draft.headline = 'Адаптер <script> & инфраструктура'
    a = approved(draft, review, tmp_settings)
    text = format_editorial(a)
    assert '&lt;script&gt; &amp;' in text and '<script>' not in text
    assert 'ДО AGI' not in text and 'ПРОРЫВ' not in text
    assert '<b>Где границы</b>' in text


def test_delivery_claim_blocks_parallel_sender(tmp_settings):
    a = article()
    assert delivery.reserve(a, tmp_settings) is None
    assert delivery.reserve(a, tmp_settings)['reason'] == 'delivery_needs_review'


def test_ambiguous_send_is_never_automatically_retried(tmp_settings):
    a = article()
    delivery.reserve(a, tmp_settings)
    assert delivery.finish(a, tmp_settings, SendResult(ok=False, reason='unknown')) == 'unknown'
    assert delivery.reserve(a, tmp_settings)['reason'] == 'delivery_needs_review'


def test_confirmed_send_is_recovered_without_resending(tmp_settings):
    a = article(); delivery.reserve(a, tmp_settings)
    delivery.finish(a, tmp_settings, SendResult(ok=True, msg_id=123, reason='sent'))
    a.id = 'another-scanner-id'
    assert delivery.reserve(a, tmp_settings) == {'ok': True, 'reason': 'dedup', 'msg_id': 123}


def test_daily_limit_counts_reservations(tmp_settings):
    s = tmp_settings.model_copy(update={'editorial_required': True,
        'editorial_min_interval_minutes': 0, 'editorial_max_daily_posts': 3})
    for i in range(3):
        a = article(); a.url += str(i)
        assert delivery.reserve(a, s) is None
    a = article(); a.url += 'fourth'
    assert delivery.reserve(a, s)['reason'] == 'daily_limit'


def test_minimum_interval_between_posts(tmp_settings):
    s = tmp_settings.model_copy(update={'editorial_required': True})
    a = article(); delivery.reserve(a, s)
    delivery.finish(a, s, SendResult(ok=True, msg_id=1, reason='sent'))
    a.url += '/another'
    assert delivery.reserve(a, s)['reason'] == 'minimum_interval'


def test_transport_timeout_is_not_success(tmp_settings):
    import subprocess
    from agentsblog.publishing.telegram import send
    with patch('agentsblog.publishing.telegram.subprocess.run', side_effect=subprocess.TimeoutExpired('send', 120)):
        result = send('text', tmp_settings)
    assert not result.ok and result.reason == 'unknown'


def test_site_escapes_jinja_templates(tmp_settings, db, make_article):
    from agentsblog.db import upsert_article, mark_published
    from agentsblog.site.builder import build_site
    a = make_article(db, title='<script>alert(1)</script>', summary='<img src=x onerror=alert(1)>')
    upsert_article(db, a); mark_published(db, a.id, 7)
    build_site(tmp_settings)
    html = (tmp_settings.resolved_public_dir / 'index.html').read_text(encoding='utf-8')
    assert '<script>alert(1)</script>' not in html
    assert '&lt;script&gt;' in html
