#!/usr/bin/env python3
"""Read current state for cluster plan 2026-10-03-0615."""
import json
import os
import sys

# Force UTF-8 output
os.environ['PYTHONIOENCODING'] = 'utf-8'

DATA = r'C:\Users\Admin\dev\project\agentsmits-blog\data'

# Read pending_queue.json
try:
    with open(os.path.join(DATA, 'pending_queue.json'), encoding='utf-8') as f:
        pending = json.load(f)
except Exception as e:
    print(f"ERR pending: {e}", file=sys.stderr)
    pending = {}

print("=== PENDING QUEUE ===")
print(f"Type: {type(pending).__name__}")
if isinstance(pending, dict):
    for k in pending.keys():
        v = pending[k]
        if isinstance(v, list):
            print(f"  {k}: list[{len(v)}]")
        else:
            print(f"  {k}: {type(v).__name__}")
    # Try common shapes
    items = pending.get('pending') or pending.get('items') or pending.get('articles') or []
    if not items and 'pending' in str(pending.keys()).lower():
        for k, v in pending.items():
            if isinstance(v, list) and v:
                items = v
                break
elif isinstance(pending, list):
    items = pending
else:
    items = []

print(f"\nItems count: {len(items)}")
for i, it in enumerate(items[:30]):
    aid = it.get('article_id') or it.get('id') or '?'
    src = it.get('source', '?')
    imp = it.get('importance', '?')
    dec = it.get('actual_decayed_importance') or it.get('decayed_importance') or '?'
    title = it.get('title', '')[:60]
    age = it.get('age_days_at_now') or it.get('age_days', '?')
    print(f"  {i+1}. {aid} | imp={imp} | src={src} | dec={dec} | age={age}d")
    print(f"     title: {title}")

# Read sent_messages to see what's been published recently
print("\n=== SENT MESSAGES (recent) ===")
try:
    with open(os.path.join(DATA, 'sent_messages.json'), encoding='utf-8') as f:
        sent = json.load(f)
    if isinstance(sent, dict) and 'messages' in sent:
        msgs = sent['messages']
    elif isinstance(sent, list):
        msgs = sent
    else:
        msgs = []
    print(f"Total messages in sent_messages.json: {len(msgs)}")
    # Get last 10
    for m in msgs[-15:]:
        if isinstance(m, dict):
            ts = m.get('published_at', m.get('ts', '?'))
            mid = m.get('msg_id', '?')
            title = m.get('title', '')[:60]
            print(f"  msg {mid} @ {ts}: {title}")
except Exception as e:
    print(f"ERR sent: {e}", file=sys.stderr)

# Read metrics
print("\n=== METRICS SUMMARY ===")
try:
    with open(os.path.join(DATA, 'metrics.json'), encoding='utf-8') as f:
        metrics = json.load(f)
    pub = metrics.get('published', [])
    print(f"Total recorded published: {len(pub)}")
    if pub:
        last = pub[-5:]
        for p in last:
            ts = p.get('ts', '?')
            mid = p.get('msg_id', '?')
            aid = p.get('article_id', '?')
            imp = p.get('importance', '?')
            print(f"  msg {mid} @ {ts}: {aid} (imp={imp})")
    daily_counts = metrics.get('daily_counts', {})
    print(f"Daily counts: {dict(list(daily_counts.items())[-10:])}")
    runs_pub = metrics.get('runs', {}).get('publish', [])
    if runs_pub:
        last_run = runs_pub[-1]
        print(f"Last publish run: {last_run.get('ts', '?')} -> {last_run.get('action', '?')}")
        det = last_run.get('details', {})
        print(f"  details: published={det.get('published', '?')}, agi_days={det.get('agi_days', '?')}, pending_left={det.get('pending_left', '?')}")
except Exception as e:
    print(f"ERR metrics: {e}", file=sys.stderr)

# Read narratives briefly
print("\n=== NARRATIVES (count) ===")
try:
    with open(os.path.join(DATA, 'narratives.json'), encoding='utf-8') as f:
        narr = json.load(f)
    if isinstance(narr, dict):
        narrs = narr.get('narratives') or narr.get('items') or []
    elif isinstance(narr, list):
        narrs = narr
    else:
        narrs = []
    print(f"Total narratives: {len(narrs)}")
    for n in narrs[:10]:
        if isinstance(n, dict):
            print(f"  {n.get('id', n.get('narrative_id', '?'))} | active={n.get('status', n.get('active', '?'))} | n={n.get('size', n.get('n', '?'))} | imp_max={n.get('imp_max', n.get('max_importance', '?'))} | title: {(n.get('title','') or '')[:50]}")
except Exception as e:
    print(f"ERR narratives: {e}", file=sys.stderr)

# Last events log
print("\n=== EVENTS LOG (last 5) ===")
try:
    with open(os.path.join(DATA, 'events.log'), encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    for line in lines[-5:]:
        print(f"  {line.rstrip()[:200]}")
except Exception as e:
    print(f"ERR events: {e}", file=sys.stderr)
