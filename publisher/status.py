#!/usr/bin/env python3
"""
Быстрая проверка статуса AI-канала.
Использование:
    python3 scripts/status.py                   # краткий статус
    python3 scripts/status.py --tail 20         # последние 20 событий
    python3 scripts/status.py --funnel <id>     # per-article funnel
    python3 scripts/status.py --errors 24h      # ошибки за 24 часа
    python3 scripts/status.py --health          # источники + telegram + llm
    python3 scripts/status.py --alerts          # последние алерты
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from metrics import (
    get_status, print_status, _load_metrics, METRICS_PATH, LOG_PATH,
)
import argparse
from datetime import datetime, timezone, timedelta


def show_tail(n):
    """Показать последние N событий из events.log."""
    if not os.path.exists(LOG_PATH):
        print("events.log not found")
        return
    with open(LOG_PATH) as f:
        lines = f.readlines()
    print(f"=== Последние {n} событий из events.log ===")
    for line in lines[-n:]:
        try:
            import json
            d = json.loads(line)
            ts = d.get('ts', '?')[:19]
            typ = d.get('type', '?')
            act = d.get('action', '?')
            det = d.get('details', {})
            # Compact view
            extra = ""
            if 'article_id' in det:
                extra = f" | {det['article_id'][:60]}"
            elif 'source' in det:
                extra = f" | {det['source']}"
            elif 'error' in det:
                extra = f" | {det['error'][:80]}"
            print(f"  [{ts}] {typ:8} {act:25}{extra}")
        except Exception:
            pass


def show_funnel(article_id):
    """Per-article lifecycle."""
    m = _load_metrics()
    funnel = m.get("article_funnel", {})
    f = funnel.get(article_id)
    if not f:
        print(f"No funnel data for {article_id}")
        # Suggest similar ids
        similar = [k for k in list(funnel.keys())[:30] if article_id[:20] in k]
        if similar:
            print(f"Similar: {similar[:5]}")
        return
    print(f"=== Funnel for {article_id} ===")
    for stage in ("enqueued", "analyzed", "published", "blog_synced"):
        if stage in f:
            s = f[stage]
            ts = s.get("ts", "?")[:19]
            extra = ""
            if "msg_id" in s:
                extra = f" msg_id={s['msg_id']}"
            if "duration_ms" in s:
                extra += f" duration={s['duration_ms']}ms"
            print(f"  {stage:14} {ts}{extra}")


def show_errors(hours):
    """Ошибки за последние N часов."""
    m = _load_metrics()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cutoff_ts = cutoff.isoformat()
    errors = [e for e in m.get("errors", []) if e.get("ts", "") >= cutoff_ts]
    print(f"=== Ошибки за последние {hours}ч: {len(errors)} ===")
    for e in errors[:30]:
        ts = e.get("ts", "?")[:19]
        script = e.get("details", {}).get("script", "?")
        err = e.get("details", {}).get("error", "?")[:80]
        article_id = e.get("details", {}).get("article_id", "")
        article_info = f" [{article_id[:40]}]" if article_id else ""
        print(f"  [{ts}] {script:10} {err}{article_info}")


def show_health():
    """Source health + telegram + llm overview."""
    m = _load_metrics()
    sh = m.get("source_health", {})
    print(f"=== Source Health ({len(sh)} sources) ===")
    for name, info in sorted(sh.items()):
        ok = "✓" if not info.get("fail_streak", 0) else "✗"
        streak = info.get("fail_streak", 0)
        last_ok = info.get("last_ok_ts", "never")[:19]
        last_fail = info.get("last_fail_ts", "never")
        items = info.get("last_items", "?")
        print(f"  {ok} {name:25} streak={streak} last_ok={last_ok} last_items={items}")
        if streak > 0 and last_fail != "never":
            err = info.get("last_error", "")[:80]
            print(f"      last_error: {err}")
    print()
    bs = m.get("blog_sync", {})
    print(f"=== Blog Sync (last {min(10, len(bs))}) ===")
    for k, v in list(bs.items())[:10]:
        ok = "✓" if v.get("ok") else "✗"
        cnt = len(v.get("article_ids", []) or [])
        dur = v.get("duration_ms", "?")
        err = v.get("error", "")
        err_info = f" err={err[:60]}" if err else ""
        print(f"  {ok} {k} articles={cnt} duration={dur}ms{err_info}")
    print()
    audit = m.get("telegram_audit", [])
    if audit:
        print(f"=== Telegram Audit (last 10 of {len(audit)}) ===")
        for a in audit[:10]:
            ts = a.get("ts", "?")[:19]
            res = a.get("result", "?")
            mid = a.get("msg_id", "?")
            dur = a.get("duration_ms", "?")
            aid = a.get("article_id", "?")[:40]
            print(f"  [{ts}] {res:15} msg={mid} dur={dur}ms article={aid}")


def show_alerts(n=15):
    """Последние алерты."""
    m = _load_metrics()
    alerts = m.get("alerts", [])
    print(f"=== Последние {n} алертов (всего {len(alerts)}) ===")
    for a in alerts[:n]:
        ts = a.get("ts", "?")[:19]
        typ = a.get("type", "?")
        sev = a.get("severity", "?")
        msg = a.get("message", "?")[:100]
        print(f"  [{ts}] [{sev:5}] {typ:30} {msg}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tail", type=int, metavar="N", help="Последние N событий")
    p.add_argument("--funnel", metavar="ARTICLE_ID", help="Per-article funnel")
    p.add_argument("--errors", metavar="HOURS", type=float, help="Ошибки за N часов")
    p.add_argument("--health", action="store_true", help="Source/telegram/llm health")
    p.add_argument("--alerts", action="store_true", help="Последние алерты")
    args = p.parse_args()

    if args.tail:
        show_tail(args.tail)
    elif args.funnel:
        show_funnel(args.funnel)
    elif args.errors:
        show_errors(args.errors)
    elif args.health:
        show_health()
    elif args.alerts:
        show_alerts()
    else:
        print_status()


if __name__ == "__main__":
    main()