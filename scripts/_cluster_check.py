import sqlite3
import sys
import os

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

# Force UTF-8 stdout for Windows cp1251 consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

rows = conn.execute(
    "SELECT id, source_id, title, importance, date, status, agent_impact, narrative_id, published_at FROM articles WHERE status='pending' ORDER BY importance DESC, date DESC"
).fetchall()
print(f'Total pending in DB: {len(rows)}')
print(f'now (utc): {__import__("datetime").datetime.utcnow().isoformat()}')

# Date spread
dates = [r['date'] for r in rows if r['date']]
if dates:
    print(f'Date range: {min(dates)} -> {max(dates)}')

# Importance histogram
imps = {}
for r in rows:
    imps.setdefault(r['importance'], 0)
    imps[r['importance']] += 1
print(f'Importance histogram: {dict(sorted(imps.items(), reverse=True))}')

# Analyzed vs not
n_analyzed = sum(1 for r in rows if r['agent_impact'])
n_no = sum(1 for r in rows if not r['agent_impact'])
print(f'Analyzed: {n_analyzed} | Not analyzed: {n_no}')

# Sources
srcs = {}
for r in rows:
    srcs.setdefault(r['source_id'], 0)
    srcs[r['source_id']] += 1
print(f'Sources: {dict(sorted(srcs.items(), key=lambda x: -x[1]))}')

# Today's publishes
today = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) >= date('now', '-1 day')").fetchone()['n']
print(f'Published in last 24h: {today}')

# Last successful publish
last = conn.execute("SELECT id, published_at, message_id FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 3").fetchall()
print('Last 3 published:')
for r in last:
    print(f'  - {r["id"][:60]:60s} | {r["published_at"]} | msg_id={r["message_id"]}')

# How many imp>=3 (publishable) pending?
pub = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='pending' AND importance >= 3").fetchone()['n']
print(f'Pending with importance >= 3 (publishable): {pub}')

conn.close()
