import sqlite3, json, sys
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

# Pending items in DB
rows = conn.execute(
    "SELECT id, source_id, title, importance, date, summary, agent_impact, narrative_id, decayed_importance, is_breakthrough, breakthrough_score FROM articles WHERE status='pending' ORDER BY importance DESC, decayed_importance DESC, date DESC"
).fetchall()
print(f'Total pending in DB: {len(rows)}')
print(f'now (utc): {datetime.now(timezone.utc).isoformat()}')
print(f'now (msk): {(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()}')
print('---')

if rows:
    dates = [r['date'] for r in rows if r['date']]
    if dates:
        print(f'Date range: {min(dates)} -> {max(dates)}')
    imps = {}
    for r in rows:
        imps.setdefault(r['importance'], 0)
        imps[r['importance']] += 1
    print(f'Importance histogram: {dict(sorted(imps.items(), reverse=True))}')
    srcs = {}
    for r in rows:
        srcs.setdefault(r['source_id'], 0)
        srcs[r['source_id']] += 1
    print(f'Sources: {dict(sorted(srcs.items(), key=lambda x: -x[1]))}')
    n_analyzed = sum(1 for r in rows if r['agent_impact'])
    print(f'Analyzed: {n_analyzed} | Not analyzed: {len(rows) - n_analyzed}')

    today = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) >= date('now', '-1 day')").fetchone()['n']
    print(f'Published in last 24h: {today}')
    print('---')
    print('PENDING ITEMS:')
    for r in rows:
        bt = '🔥' if r['is_breakthrough'] else '  '
        print(f'{bt} [imp={r["importance"]}] [decayed={r["decayed_importance"]:.2f}] [{r["source_id"]}] {r["title"][:80]}')
        if r['narrative_id']:
            print(f'    narrative: {r["narrative_id"]}')
        if r['summary']:
            print(f'    {r["summary"][:120]}')
        print()

# Last published
last = conn.execute("SELECT id, source_id, title, published_at, message_id FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 5").fetchall()
print('---')
print('LAST 5 PUBLISHED:')
for r in last:
    print(f'  - [{r["source_id"]}] {r["title"][:60]} | {r["published_at"]}')

# Narratives
print('---')
print('NARRATIVES (from data/narratives.json):')
with open('data/narratives.json') as f:
    narr = json.load(f)
active = [n for n in narr.get('narratives', []) if n.get('status') == 'active']
print(f'Total active narratives: {len(active)}')
recent = sorted(active, key=lambda n: n.get('last_seen', ''), reverse=True)[:10]
for n in recent:
    print(f'  {n["id"]} | {n.get("title", "")[:60]} | n={len(n.get("items", []))} | imp_max={n.get("importance_max", "?")} | last_seen={n.get("last_seen", "")[:16]}')

conn.close()
