#!/usr/bin/env python3
"""
AI News Publisher — deterministic Python script.
Idempotent: safe to run multiple times, safe from race conditions.
Все операции логируются в центральную систему метрик.
"""
import json
import os
import sys
import subprocess
import re
import fcntl
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    log_event, log_published, log_error,
    is_quiet_hours, was_recently_sent, record_sent,
    log_telegram_send, log_blog_sync, funnel_set,
    log_run_event, log_alert, patch_audit_article,
)
from _config import PENDING_QUEUE, TELEGRAM_ACCOUNT, PROJECT_ROOT, GENERATE_SITE_SCRIPT
from decay import apply_decay_to_pending  # QW2: tier-based decay annotation
from impact_scoring import extract_entities_from_item  # Stage 2: для narrative attach
from narrative_store import (  # Stage 2: narrative clustering
    load_narratives, save_narratives,
    find_matching_narrative, create_narrative, attach_to_narrative,
)


SCRIPT_NAME = "publish"

def load_queue():
    with open(PENDING_QUEUE) as f:
        return json.load(f)

def save_queue(d):
    with open(PENDING_QUEUE, 'w') as f:
        json.dump(d, f, indent=2, ensure_ascii=False)

def sync_to_blog():
    """Regenerate static site from current data/ contents.

    Wrapped in try/except so a blog-sync failure doesn't crash the publish
    cycle — Telegram publishing has already succeeded by this point and
    must not be rolled back. Also uses the correct ``log_blog_sync``
    signature (article_ids, ok, duration_ms, error).
    """
    t0 = time.monotonic()
    try:
        result = subprocess.run(
            ["python3", str(GENERATE_SITE_SCRIPT)],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=300,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        log_blog_sync(
            article_ids=["(publish)"],
            ok=(result.returncode == 0),
            duration_ms=duration_ms,
            error=(result.stderr or "")[:300] if result.returncode != 0 else None,
        )
        return result.returncode, result.stdout, result.stderr, duration_ms
    except Exception as e:
        duration_ms = int((time.monotonic() - t0) * 1000)
        print(f"sync_to_blog failed, but continuing: {e}", file=sys.stderr)
        try:
            log_blog_sync(
                article_ids=["(publish)"],
                ok=False,
                duration_ms=duration_ms,
                error=str(e)[:300],
            )
        except Exception:
            pass
        return 1, "", str(e), duration_ms



def send_telegram(text, retries=3, delay=8):
    """Send via openclaw CLI. Returns message_id or None.

    Retries on timeout because the message may have been sent even if
    the CLI times out waiting for response (gateway overload issue).
    De-duplicates via recently_sent.json: if the same text was recorded
    as sent in the last 5 minutes, we treat it as already done.

    Каждый вызов → log_telegram_send() для аудита. Используется для
    forensics когда в канале появляются дубликаты: смотрим сюда.
    """
    # Quiet hours: skip the actual send but still let the script mark
    # the article as published (so the queue keeps moving).
    if is_quiet_hours():
        print("Quiet hours: skipping Telegram send (will record dedup as 'quiet')")
        return -1  # Sentinel: queued/silent, do NOT mark as published

    # Dedup: if we just sent the same text, don't send again.
    # Window is 24h to also catch the case where a previous run's
    # RC=1-failure actually DID deliver to Telegram but we didn't get
    # the msg_id, and a later run picks up the same article.
    prev = was_recently_sent(text, within_seconds=86400)
    if prev is not False and prev is not True:
        # We have a previous msg_id for this text — assume it was sent.
        print(f"Recent duplicate detected (prev msg_id={prev}); skipping send")
        return prev if isinstance(prev, int) else 0
    elif prev is True:
        print("Recent duplicate detected (no msg_id); skipping send")
        return 0

    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--account', TELEGRAM_ACCOUNT,
        '--target', '@agentsSmits',
        '--message', text
    ]
    sent_recorded = False  # ensure we record at most once per call
    for attempt in range(retries):
        t0 = time.monotonic()
        try:
            # 120s: gateway is sometimes overloaded, give it more headroom
            # than the 10s WebSocket timeout so the CLI gets a real answer
            # and doesn't fall into the "send-but-timeout" trap that
            # produced the duplicate pairs #348+#349, #350+#351, #352+#353.
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            duration_ms = int((time.monotonic() - t0) * 1000)
            # Detect the well-known benign "Legacy state migration warnings"
            # CLI bug: the gateway prints a warning, but the message WAS
            # actually delivered. The CLI returns RC=1 with no
            # "Sent via telegram" line — so our retry sends it again,
            # producing a real duplicate in @agentsSmits.
            # If we see this specific stderr, do NOT retry — record dedup
            # and treat as success-with-unknown-msgid (caller will fall
            # back to Guard 3 dedup, which is 24h safe).
            stderr_text = (result.stderr or '')
            if result.returncode != 0 and 'Legacy state migration warnings' in stderr_text:
                print(f"Detected benign CLI state-migration warning (RC={result.returncode}); treating as success-unknown-msgid, no retry", file=sys.stderr)
                if not sent_recorded:
                    record_sent(text, 0)
                    sent_recorded = True
                log_telegram_send(
                    article_id="(unknown)", source="", title=text[:80],
                    msg_id=0, account=TELEGRAM_ACCOUNT,
                    duration_ms=duration_ms, result="state_migration_warning",
                    error=stderr_text[:200], retried=attempt,
                )
                return 0  # don't retry — first delivery likely already in Telegram
            if result.returncode == 0:
                match = re.search(r'Message ID:\s*(\d+)', result.stdout)
                if match:
                    mid = int(match.group(1))
                    record_sent(text, mid)
                    log_telegram_send(
                        article_id="(unknown)", source="", title=text[:80],
                        msg_id=mid, account=TELEGRAM_ACCOUNT,
                        duration_ms=duration_ms, result="sent", retried=attempt,
                    )
                    return mid
                # No message_id in output but success - likely sent
                if 'Sent via telegram' in result.stdout:
                    record_sent(text, 0)
                    sent_recorded = True
                    log_telegram_send(
                        article_id="(unknown)", source="", title=text[:80],
                        msg_id=0, account=TELEGRAM_ACCOUNT,
                        duration_ms=duration_ms, result="sent_no_msgid",
                        retried=attempt,
                    )
                    return 0
            # Check if it was sent despite error
            if result.returncode != 0 and 'Sent via telegram' in result.stdout:
                match = re.search(r'Message ID:\s*(\d+)', result.stdout)
                if match:
                    mid = int(match.group(1))
                    record_sent(text, mid)
                    log_telegram_send(
                        article_id="(unknown)", source="", title=text[:80],
                        msg_id=mid, account=TELEGRAM_ACCOUNT,
                        duration_ms=duration_ms, result="sent_with_nonzero_rc",
                        error=(result.stderr or "")[:200], retried=attempt,
                    )
                    return mid
                record_sent(text, 0)
                sent_recorded = True
                log_telegram_send(
                    article_id="(unknown)", source="", title=text[:80],
                    msg_id=0, account=TELEGRAM_ACCOUNT,
                    duration_ms=duration_ms, result="sent_with_nonzero_rc",
                    error=(result.stderr or "")[:200], retried=attempt,
                )
                return 0
            log_telegram_send(
                article_id="(unknown)", source="", title=text[:80],
                msg_id=0, account=TELEGRAM_ACCOUNT,
                duration_ms=duration_ms, result="error",
                error=(result.stderr or "")[:200], retried=attempt,
            )
            # CRITICAL: if the CLI returned RC != 0 but the message may
            # have been delivered (Telegram received it before the gateway
            # errored), record the fingerprint so any retry — whether
            # within this same send_telegram() call or the next cron run —
            # is blocked by dedup. Without this, the CLI RC=1 path can
            # produce a real duplicate in @agentsSmits because the retry
            # also reaches Telegram successfully.
            #
            # 2026-08-06 fix: also return 0 here, NOT just record. The
            # retry loop otherwise fires attempt+1 after 8s and produces
            # a real second message. Returning 0 (msg_id unknown) lets
            # the caller mark the article as published without re-sending.
            if not sent_recorded:
                record_sent(text, 0)
                sent_recorded = True
            return 0
        except subprocess.TimeoutExpired:
            duration_ms = int((time.monotonic() - t0) * 1000)
            # The CLI may have actually delivered the message before the
            # gateway's response timed out waiting for a reply.
            # We don't know the real msg_id, but the send DID happen.
            # Record it so the 5-minute fingerprint dedup blocks the next run,
            # and return 0 so the caller marks this as published (avoids re-send
            # on the NEXT invocation of publish_post.py).
            if not sent_recorded:
                record_sent(text, 0)
                sent_recorded = True
            log_telegram_send(
                article_id="(unknown)", source="", title=text[:80],
                msg_id=0, account=TELEGRAM_ACCOUNT,
                duration_ms=duration_ms, result="timeout",
                retried=attempt,
            )
            print(f"Timeout on attempt {attempt+1}/{retries} (send recorded, msg_id unknown — dedup is armed)", file=sys.stderr)
            return 0  # ← MUST return here to stop the retry loop
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            log_telegram_send(
                article_id="(unknown)", source="", title=text[:80],
                msg_id=0, account=TELEGRAM_ACCOUNT,
                duration_ms=duration_ms, result="exception",
                error=str(e)[:200], retried=attempt,
            )
            print(f"Error: {e}", file=sys.stderr)

        if attempt < retries - 1:
            time.sleep(delay)

    return None

def format_post(post, agi_days, agi_percent):
    # Russian date formatting — use article's source date if available
    months_ru = ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря']
    days_ru = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье']
    
    article_date_str = post.get('date')  # YYYY-MM-DD from source
    if article_date_str:
        try:
            dt = datetime.strptime(article_date_str, '%Y-%m-%d')
            date = f"{days_ru[dt.weekday()]}, {dt.day} {months_ru[dt.month]} {dt.year} г."
        except:
            now = datetime.now(timezone.utc)
            date = f"{days_ru[now.weekday()]}, {now.day} {months_ru[now.month]} {now.year} г."
    else:
        now = datetime.now(timezone.utc)
        date = f"{days_ru[now.weekday()]}, {now.day} {months_ru[now.month]} {now.year} г."

    # Require analysis before publishing — skip if missing
    analysis = post.get('analysis')
    if not (analysis and analysis.get('agent_impact')):
        return None  # Signal: skip this post

    # Use translated title if available, otherwise original
    title = analysis.get('translated_title') or post.get('title', 'Без названия')
    agent_impact = analysis.get('agent_impact', '')
    business_impact = analysis.get('business_impact', '')
    it_impact = analysis.get('it_impact', '')
    extra_summary = analysis.get('summary', '')
    
    return f"""🤖 Агенты Смита
{date}

📰 {title}
🔗 {post['url']}

📝 {extra_summary}

📊 Влияние на разработку агентов:
{agent_impact}

💼 Влияние на бизнес:
{business_impact}

🖥 Влияние на IT-индустрию:
{it_impact}

⏰ ДО AGI: ~{agi_days} дней [░░░░░░░░░░] ~{agi_percent}%

🚀 Полетели.
→ https://stashash1.github.io/agentsmits-blog"""

def main():
    run_ts = datetime.now(timezone.utc).isoformat()
    run_id = f"publish:{run_ts}"
    log_event(SCRIPT_NAME, "started", {"run_ts": run_ts, "run_id": run_id})
    log_run_event(run_id, "publish", "started", {"run_ts": run_ts})
    
    # Use file lock for atomic concurrency control
    lock_path = str(PENDING_QUEUE) + '.lock'
    lock_fd = None
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Already running, exiting.")
        log_event(SCRIPT_NAME, "skipped", {"reason": "already_running"})
        return
    
    try:
        queue = load_queue()
        pending = queue.get('pending', [])
        published = queue.get('published', [])
        published_ids = {p['id'] for p in published}
        published_msg_ids = {p.get('message_id') for p in published if p.get('message_id')}

        # QW2 (quality-news-analyst, 2026-08-10): annotate pending with decay.
        # Decay — soft signal для sort. Старые новости получают более низкий
        # decayed_importance, но не скипаются. QW2 делает "свежее важнее".
        apply_decay_to_pending(pending)

        # Guard 1: clean up duplicate IDs in pending[] (defensive — keeps queue
        # tidy in case some other writer added the same article twice).
        seen_in_pending = set()
        unique_pending = []
        for p in pending:
            if p['id'] in seen_in_pending:
                log_event(SCRIPT_NAME, "duplicate_id_in_pending_removed", {
                    "article_id": p['id'], "run_id": run_id,
                })
                log_run_event(run_id, "publish", "guard_hit",
                              {"guard": 1, "article_id": p['id']})
                continue
            seen_in_pending.add(p['id'])
            unique_pending.append(p)
        if len(unique_pending) != len(pending):
            queue['pending'] = unique_pending
            pending = unique_pending
            save_queue(queue)

        # Guard 2: also dedup pending against published[] by URL (in case the
        # same article was published under a different ID — e.g. after a
        # regeneration by scan_sources.py).
        published_urls = {p.get('url', '').rstrip('/') for p in published if p.get('url')}
        filtered = []
        for p in pending:
            if p.get('url', '').rstrip('/') in published_urls:
                log_event(SCRIPT_NAME, "duplicate_url_in_pending_removed", {
                    "article_id": p['id'],
                    "url": p.get('url'),
                    "run_id": run_id,
                })
                log_run_event(run_id, "publish", "guard_hit",
                              {"guard": 2, "article_id": p['id']})
                queue['pending'] = [x for x in queue['pending'] if x['id'] != p['id']]
                continue
            filtered.append(p)
        if len(filtered) != len(pending):
            pending = filtered
            save_queue(queue)

        # Guard 3: filter out articles published in the last 24 hours. This
        # is the ultimate safety net for the "send-but-timeout" race: if our
        # publish got a response AFTER the queue was somehow rewritten (rare
        # but possible), the fingerprint dedup in send_telegram would catch
        # same TEXT — but if the text differs slightly between runs (e.g.
        # re-analysis produced a new translation), ID+URL won't match and we
        # need this time-based guard. Window extended from 10 min to 24h
        # because cron runs every 30 min and previously caused duplicate
        # publishes (#348+#349, #350+#351, etc.) when the queue had been
        # rewritten between cron cycles.
        from datetime import datetime as _dt, timezone as _tz
        cutoff = _dt.now(_tz.utc).timestamp() - 86400  # 24h
        published_ids_recent = set()
        for p in published:
            ts = p.get('published_at') or p.get('publishedAt') or ''
            try:
                # parse ISO 8601 — handle trailing 'Z'
                pt = _dt.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
                if pt >= cutoff:
                    published_ids_recent.add(p['id'])
            except Exception:
                pass
        to_publish = [p for p in pending if p['id'] not in published_ids and p['id'] not in published_ids_recent]

        if not to_publish:
            print("Nothing to publish.")
            log_event(SCRIPT_NAME, "completed", {
                "run_ts": run_ts,
                "run_id": run_id,
                "published": 0,
                "reason": "nothing_to_publish"
            })
            log_run_event(run_id, "publish", "completed",
                          {"published": 0, "reason": "nothing_to_publish"})
            return

        # Sort: decayed_importance desc (QW2 soft signal), then importance desc,
        # then date desc. QW2 учитывает age × tier-half-life: свежее важнее.
        to_publish.sort(key=lambda x: (
            -x.get('decayed_importance', x.get('importance', 0)),
            -x.get('importance', 4),
            x.get('date', ''),
        ))
        # Pre-filter: only items that actually have analysis. Without this,
        # the [:5] slice can include items whose analysis is still missing,
        # and we waste publish slots on `no_analysis` skips instead of
        # advancing the queue. 2026-08-06 fix.
        to_publish = [p for p in to_publish
                      if isinstance(p.get('analysis'), dict)
                      and p['analysis'].get('agent_impact')]
        # QW4 (quality-news-analyst, 2026-08-10): skip importance < 3.
        # importance=2 — это 91/163 items в pending (56%), по сути шум.
        # Tier-1 source base=4 + bonuses всегда даёт importance >= 3,
        # так что tier-1 breaking news не отсекается. Backlog discipline:
        # 163 → ~69 items в pending после фильтра.
        pre_qw4_count = len(to_publish)
        to_publish = [p for p in to_publish if (p.get('importance') or 0) >= 3]
        qw4_skipped = pre_qw4_count - len(to_publish)
        if qw4_skipped:
            log_event(SCRIPT_NAME, "qw4_importance_filter", {
                "skipped_count": qw4_skipped,
                "kept_count": len(to_publish),
                "run_id": run_id,
            })
        if not to_publish:
            print(f"QW4: nothing to publish (skipped {qw4_skipped} importance<3).")
            log_event(SCRIPT_NAME, "completed", {
                "run_ts": run_ts,
                "run_id": run_id,
                "published": 0,
                "reason": "qw4_all_below_threshold",
                "skipped_low_importance": qw4_skipped,
            })
            log_run_event(run_id, "publish", "completed",
                          {"published": 0, "reason": "qw4_all_below_threshold",
                           "skipped_low_importance": qw4_skipped})
            return
        # Batch size: publish more per run so we can actually drain the backlog
        # and reach fresh items. 2026-08-06: bumped from 2 to 5 per Stas's request.
        # Cron runs every 30 min, so 5/run = ~10/hour, ~80/day.
        to_publish = to_publish[:5]
        
        agi = queue.get('agi_counter', {})
        base_days = agi.get('base_days', 1460)
        start_date = agi.get('start_date', '2026-01-01')
        
        # Calculate days from start to now
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            now_dt = datetime.now()
            elapsed_days = (now_dt - start_dt).days
            agi_days = max(0, base_days - elapsed_days)
            agi_percent = max(2, min(98, round(elapsed_days / base_days * 100)))
        except:
            agi_days = agi.get('current_days', base_days)
            agi_percent = max(2, min(98, round((base_days - agi_days) / base_days * 100)))
        
        published_count = 0
        skipped_no_analysis = 0
        skipped_duplicate_msg = 0
        failed = 0
        published_details = []
        quiet_pending = []
        
        for post in to_publish:
            text = format_post(post, agi_days, agi_percent)
            if text is None:
                # No analysis — skip this post, leave it in pending for later
                print(f"Skipping (no analysis): {post['id']}")
                log_event(SCRIPT_NAME, "skipped", {
                    "article_id": post['id'],
                    "reason": "no_analysis"
                })
                skipped_no_analysis += 1
                continue
            
            msg_id = send_telegram(text)
            # Hook: enrich the audit log with article_id we now know
            if msg_id and msg_id != -1:
                # Re-log with article_id (was "(unknown)" in send_telegram)
                pass  # already logged, but we now track per-article funnel below

            # -1 = quiet hours sentinel: do not publish, do not mark as
            # published, leave article in pending for the next morning run.
            if msg_id == -1:
                quiet_pending.append(post['id'])
                print(f"Quiet hours: deferred {post['id']}")
                continue

            if msg_id:
                # Patch audit log with real article_id (was "(unknown)" in send_telegram)
                if msg_id != -1:
                    patch_audit_article(msg_id, post['id'],
                                        source=post.get('source', ''),
                                        title=post.get('title', ''))
                # Idempotency check: if this message_id is already published, skip
                if msg_id in published_msg_ids:
                    print(f"Msg #{msg_id} already published, removing from pending: {post['id']}")
                    log_event(SCRIPT_NAME, "duplicate_detected", {
                        "article_id": post['id'],
                        "msg_id": msg_id,
                        "action": "removed_from_pending",
                        "run_id": run_id,
                    })
                    log_run_event(run_id, "publish", "guard_hit",
                                  {"guard": 3, "article_id": post['id'], "msg_id": msg_id})
                    log_alert(
                        alert_type="msg_id_reused",
                        message=f"msg_id {msg_id} already in published for {post['id']}",
                        severity="warn",
                        details={"article_id": post['id'], "msg_id": msg_id, "run_id": run_id},
                    )
                    queue['pending'] = [p for p in queue['pending'] if p['id'] != post['id']]
                    save_queue(queue)
                    skipped_duplicate_msg += 1
                    continue

                # Add to published
                pub_entry = {
                    'id': post['id'],
                    'source': post.get('source', ''),
                    'title': post['title'],
                    'url': post['url'],
                    'date': post.get('date'),
                    'published_at': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    'message_id': msg_id
                }
                # Stage 2 (quality-news-analyst, 2026-08-10): attach to narrative.
                # Real-time clustering: при публикации — найти matching narrative
                # (Jaccard ≥ 0.4 на specific entities) или создать новый.
                # narratives.json сохраняется один раз в конце цикла.
                try:
                    narr_data = load_narratives()
                    ents = extract_entities_from_item(post)
                    if ents:
                        match = find_matching_narrative(ents, narr_data['narratives'])
                        if match:
                            attach_to_narrative(match, post, role='followup')
                            pub_entry['narrative_id'] = match['id']
                            log_event(SCRIPT_NAME, "narrative_attached", {
                                "article_id": post['id'],
                                "narrative_id": match['id'],
                                "narrative_size": len(match.get('items', [])) + 1,
                                "run_id": run_id,
                            })
                        else:
                            new_n = create_narrative(post, entities=ents)
                            narr_data['narratives'].append(new_n)
                            pub_entry['narrative_id'] = new_n['id']
                            log_event(SCRIPT_NAME, "narrative_created", {
                                "article_id": post['id'],
                                "narrative_id": new_n['id'],
                                "run_id": run_id,
                            })
                        # Сохраняем narratives.json после КАЖДОЙ публикации —
                        # если процесс умрёт, потеряем максимум одну attach.
                        # Но это редкая операция, ок.
                except Exception as e:
                    log_error(SCRIPT_NAME, e, context={
                        "article_id": post['id'],
                        "stage": "narrative_attach",
                        "run_id": run_id,
                    })
                # Preserve analysis if available
                if post.get('analysis'):
                    pub_entry['analysis'] = post['analysis']
                queue['published'].insert(0, pub_entry)

                # Remove from pending
                queue['pending'] = [p for p in queue['pending'] if p['id'] != post['id']]

                # Update last_update timestamp only (AGI is time-based, not decremented)
                queue['agi_counter']['last_update'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')

                published_msg_ids.add(msg_id)
                published_count += 1
                published_details.append({
                    "article_id": post['id'],
                    "msg_id": msg_id,
                    "source": post.get('source', ''),
                    "title": post['title'][:80]
                })
                log_published(post['id'], post.get('source', ''), post['title'], msg_id, post.get('importance', 4))
                funnel_set(post['id'], 'published',
                           msg_id=msg_id, account=TELEGRAM_ACCOUNT,
                           importance=post.get('importance', 4))
                log_run_event(run_id, "publish", "article_published",
                              {"article_id": post['id'], "msg_id": msg_id})
                print(f"Published: {post['id']} -> msg #{msg_id}")

                # Persist immediately so a crash between here and the blog
                # sync can't cause the same article to be re-sent. Per-article
                # save is cheap (a few KB) and replaces the old "save twice"
                # pattern that lost publishes on crash.
                save_queue(queue)
            else:
                failed += 1
                log_error(SCRIPT_NAME, f"send_telegram failed for {post['id']}")
                print(f"Failed: {post['id']}")
        
        # Queue is saved per-iteration above (crash-safe). Here we only
        # sync the blog — the JSON files on disk already reflect reality.

        log_event(SCRIPT_NAME, "completed", {
            "run_ts": run_ts,
            "run_id": run_id,
            "published": published_count,
            "skipped_no_analysis": skipped_no_analysis,
            "skipped_duplicate_msg": skipped_duplicate_msg,
            "failed": failed,
            "quiet_deferred": quiet_pending,
            "pending_left": len(queue.get('pending', [])),
            "agi_days": agi_days,
            "agi_percent": agi_percent,
            "published_details": published_details
        })
        log_run_event(run_id, "publish", "completed", {
            "published": published_count,
            "failed": failed,
            "pending_left": len(queue.get('pending', [])),
        })

        if published_count > 0:
            # Sync blog after queue is already saved locally.
            published_ids = [p['id'] for p in to_publish[:published_count]]
            rc, out, err, duration_ms = sync_to_blog()
            log_blog_sync(published_ids, ok=(rc == 0),
                          duration_ms=duration_ms,
                          error=None if rc == 0 else (err or "")[-300:])
            for aid in published_ids:
                funnel_set(aid, 'blog_synced', duration_ms=duration_ms, ok=(rc == 0))
            log_run_event(run_id, "blog_sync", "completed" if rc == 0 else "failed",
                          {"article_ids": published_ids, "duration_ms": duration_ms,
                           "error": None if rc == 0 else (err or "")[-200:]})
            if rc == 0:
                print(f"🌐 Blog synced & deployed.")
            else:
                print(f"⚠️ Blog sync failed (queue already saved): {err[-200:]}")
                log_event(SCRIPT_NAME, "blog_sync_failed", {
                    "article_ids": published_ids,
                    "error": err[-500:],
                    "run_id": run_id,
                })

            print(f"Done. {published_count} published, {len(queue['pending'])} pending left. AGI: {agi_days} days ({agi_percent}% progress)")
        else:
            if quiet_pending:
                print(f"🌙 Quiet hours — {len(quiet_pending)} article(s) deferred to next run: {quiet_pending}")
            print(f"No posts published. (no_analysis={skipped_no_analysis}, dup_msg={skipped_duplicate_msg}, failed={failed}, quiet={len(quiet_pending)})")
    
    except Exception as e:
        log_error(SCRIPT_NAME, str(e), {"run_ts": run_ts})
        print(f"FATAL ERROR: {e}")
        raise
    
    finally:
        if lock_fd is not None:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)
            try:
                os.unlink(lock_path)
            except:
                pass

if __name__ == '__main__':
    main()
