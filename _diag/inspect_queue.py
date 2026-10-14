# -*- coding: utf-8 -*-
"""Quick inspector for pending_queue.json — used by cluster cron."""
import json
import sys
from datetime import datetime, timezone, timedelta

PATH = r"C:\Users\Admin\dev\project\agentsmits-blog\data\pending_queue.json"

try:
    with open(PATH, encoding="utf-8") as f:
        d = json.load(f)
except Exception as e:
    print(f"ERROR loading pending_queue.json: {e}")
    sys.exit(1)

if isinstance(d, dict):
    items = d.get("items", [])
    print(f"QUEUE TYPE: dict, top keys: {list(d.keys())}")
    print(f"ITEM COUNT: {len(items)}")
    if "last_checked" in d:
        print(f"last_checked: {d['last_checked']}")
    if "metadata" in d:
        print(f"metadata: {d['metadata']}")
elif isinstance(d, list):
    items = d
    print(f"QUEUE TYPE: list, COUNT: {len(items)}")
else:
    print(f"QUEUE TYPE: {type(d).__name__}")
    items = []

MSK = timezone(timedelta(hours=3))
NOW = datetime.now(MSK)
print(f"NOW MSK: {NOW.isoformat()}")
print(f"---")

if items and isinstance(items[0], dict):
    print(f"SAMPLE ITEM KEYS: {list(items[0].keys())[:25]}")
    for i, it in enumerate(items[:10]):
        title = (it.get("title") or it.get("translated_title") or "")[:60]
        age = it.get("age_days")
        importance = it.get("importance") or it.get("stored_importance")
        analyzed = it.get("analyzed", it.get("has_analysis"))
        tier = it.get("tier", "?")
        print(f"  [{i}] tier={tier} imp={importance} age={age}d analyzed={analyzed} | {title}")
    print(f"---")
    # Tier distribution
    from collections import Counter
    tiers = Counter()
    for it in items:
        t = it.get("tier", "none")
        tiers[t] += 1
    print(f"TIER DIST: {dict(tiers)}")
    # Analyzed vs not
    analyzed_count = sum(1 for it in items if it.get("analyzed") or it.get("has_analysis"))
    print(f"ANALYZED: {analyzed_count}/{len(items)}")
