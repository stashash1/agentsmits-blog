from _config import PENDING_QUEUE
#!/usr/bin/env python3
"""
Audit-скрипт: ищет аномалии в published[] за последние N дней.

Проверяет:
- Дубли по URL (один и тот же URL опубликован > 1 раза)
- Дубли по title-prefix (похожие заголовки)
- Записи с одинаковым message_id
- Записи без message_id (потерянные)

Использование:
    python3 scripts/dedup_audit.py                # last 30 days
    python3 scripts/dedup_audit.py --days 7       # last 7 days
    python3 scripts/dedup_audit.py --fix          # удалить дубли (с backup)
"""

import sys
import os
import json
import shutil
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from metrics import log_event, log_alert

SCRIPT_NAME = "dedup_audit"


def load_published():
    with open(PENDING_QUEUE) as f:
        return json.load(f).get("published", [])


def within_days(item, days):
    """True if item's published_at is within last N days."""
    ts = item.get("published_at") or ""
    if not ts:
        return True  # include untimestamped
    try:
        pt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - pt).days <= days
    except Exception:
        return True


def find_duplicates(items, days):
    """Find URL/title-prefix/msg_id duplicates."""
    items = [it for it in items if within_days(it, days)]

    # Group by URL (normalized)
    url_groups = defaultdict(list)
    for it in items:
        u = (it.get("url") or "").rstrip("/")
        if u:
            url_groups[u].append(it)

    url_dups = {u: lst for u, lst in url_groups.items() if len(lst) > 1}

    # Group by title prefix (first 60 chars, lowercased)
    title_groups = defaultdict(list)
    for it in items:
        t = (it.get("title") or "")[:60].lower().strip()
        if t:
            title_groups[t].append(it)

    title_dups = {t: lst for t, lst in title_groups.items() if len(lst) > 1}

    # Group by message_id
    msg_groups = defaultdict(list)
    for it in items:
        mid = it.get("message_id")
        if mid:
            msg_groups[mid].append(it)

    msg_dups = {m: lst for m, lst in msg_groups.items() if len(lst) > 1}

    # No message_id at all (potentially broken)
    no_mid = [it for it in items if not it.get("message_id")]

    return {
        "url_dups": url_dups,
        "title_dups": title_dups,
        "msg_id_dups": msg_dups,
        "no_message_id": no_mid,
        "total_scanned": len(items),
    }


def fix_duplicates(days=30, dry_run=True):
    """Remove duplicate published[] entries by URL.

    Strategy: keep the entry with the earliest published_at (oldest).
    Remove newer copies. Backups to .bak-dedup-audit.
    """
    published = load_published()
    report = find_duplicates(published, days)

    url_dups = report["url_dups"]
    title_dups = report["title_dups"]
    msg_dups = report["msg_id_dups"]

    total_issues = sum(len(v) for v in url_dups.values()) \
                 + sum(len(v) for v in msg_dups.values())

    print(f"=== Audit Report (last {days} days) ===")
    print(f"Total items scanned: {report['total_scanned']}")
    print(f"URL duplicates: {len(url_dups)} groups ({sum(len(v) for v in url_dups.values())} entries)")
    print(f"Title-prefix duplicates: {len(title_dups)} groups ({sum(len(v) for v in title_dups.values())} entries)")
    print(f"message_id duplicates: {len(msg_dups)} groups ({sum(len(v) for v in msg_dups.values())} entries)")
    print(f"No message_id: {len(report['no_message_id'])} (not necessarily an issue)")
    print()

    to_remove = set()

    if url_dups:
        print(f"--- URL duplicates ---")
        for u, lst in list(url_dups.items())[:20]:
            print(f"  x{len(lst)}: {u[:80]}")
            for it in lst:
                ts = (it.get("published_at") or "?")[:19]
                mid = it.get("message_id", "?")
                print(f"    msg_id={mid} | {ts} | {it.get('title','')[:60]}")
            # Keep oldest, remove rest
            sorted_lst = sorted(lst, key=lambda x: x.get("published_at") or "")
            for it in sorted_lst[1:]:
                to_remove.add(id(it))
            print()

    if msg_dups:
        print(f"--- message_id duplicates ---")
        for m, lst in list(msg_dups.items())[:20]:
            print(f"  msg_id={m} appears x{len(lst)}")
            for it in lst:
                print(f"    url={it.get('url','')[:70]} | {it.get('title','')[:50]}")
            # Keep one, remove others (by URL match to first)
            sorted_lst = sorted(lst, key=lambda x: x.get("published_at") or "")
            for it in sorted_lst[1:]:
                to_remove.add(id(it))
            print()

    print(f"Total to remove: {len(to_remove)}")

    if not to_remove:
        print("No fixes needed.")
        return 0

    if dry_run:
        print("\n[dry-run] Run with --fix to apply changes")
        return len(to_remove)

    # Backup
    backup = str(PENDING_QUEUE) + f".bak-dedup-audit-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(PENDING_QUEUE, backup)
    print(f"Backup: {backup}")

    # Apply: keep items NOT in to_remove
    new_published = [it for it in published if id(it) not in to_remove]

    with open(PENDING_QUEUE) as f:
        queue = json.load(f)
    queue["published"] = new_published

    with open(PENDING_QUEUE, "w") as f:
        json.dump(queue, f, ensure_ascii=False, indent=2)

    removed = len(published) - len(new_published)
    print(f"Removed {removed} duplicates. New total: {len(new_published)}")

    log_event(SCRIPT_NAME, "dedup_fix_applied", {
        "removed_count": removed,
        "url_dup_groups": len(url_dups),
        "msg_id_dup_groups": len(msg_dups),
        "backup_file": backup,
    })
    log_alert(
        alert_type="dedup_fix_applied",
        message=f"dedup_audit removed {removed} duplicates from published[]",
        severity="info",
        details={"removed": removed, "backup": backup, "days": days},
    )

    return removed


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=30, help="Анализировать за N дней")
    p.add_argument("--fix", action="store_true", help="Применить исправления")
    args = p.parse_args()
    return fix_duplicates(days=args.days, dry_run=not args.fix)


if __name__ == "__main__":
    sys.exit(0 if main() is not None else 0)