import sqlite3, json, sys
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

rows = conn.execute(
    "SELECT id, source_id, title, importance, date, status, agent_impact, narrative_id, "
    "decayed_importance, is_breakthrough, breakthrough_score, summary, url "
    "FROM articles WHERE status='pending' ORDER BY importance DESC, decayed_importance DESC, date DESC"
).fetchall()
print(f'TOTAL_PENDING={len(rows)}', flush=True)
print(f'NOW_UTC={datetime.now(timezone.utc).isoformat()}', flush=True)
print(f'NOW_MSK={(datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()}', flush=True)

if rows:
    dates = [r['date'] for r in rows if r['date']]
    if dates:
        print(f'DATE_RANGE={min(dates)} -> {max(dates)}', flush=True)
    imps = {}
    for r in rows:
        imps.setdefault(r['importance'], 0)
        imps[r['importance']] += 1
    print(f'IMPORTANCE_HIST={dict(sorted(imps.items(), reverse=True))}', flush=True)
    n_analyzed = sum(1 for r in rows if r['agent_impact'])
    print(f'ANALYZED={n_analyzed} NOT_ANALYZED={len(rows) - n_analyzed}', flush=True)

    today = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) >= date('now', '-1 day')").fetchone()['n']
    print(f'PUBLISHED_24H={today}', flush=True)

    pub = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='pending' AND importance >= 3").fetchone()['n']
    print(f'PUBLISHABLE_PENDING={pub}', flush=True)

    print('---PENDING ITEMS (all, ordered):---', flush=True)
    for r in rows:
        bt = '[BT]' if r['is_breakthrough'] else '    '
        narr = r['narrative_id'] or '-'
        ana = '[A]' if r['agent_impact'] else '[ ]'
        print(f'{bt}{ana} imp={r["importance"]} decayed={r["decayed_importance"]:.2f} [{r["source_id"]}] narr={narr} | {r["title"][:80]}', flush=True)
        if r['summary']:
            print(f'      SUM: {r["summary"][:200]}', flush=True)

last = conn.execute("SELECT id, source_id, title, published_at, message_id FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 8").fetchall()
print('---LAST 8 PUBLISHED:---', flush=True)
for r in last:
    print(f'  [{r["source_id"]}] {r["title"][:60]} | {r["published_at"]} | msg={r["message_id"]}', flush=True)

try:
    with open('data/narratives.json', encoding='utf-8') as f:
        narr = json.load(f)
    active = [n for n in narr.get('narratives', []) if n.get('status') == 'active']
    print(f'---NARRATIVES: total={len(narr.get("narratives", []))} active={len(active)}---', flush=True)
    recent = sorted(active, key=lambda n: n.get('last_seen', ''), reverse=True)[:10]
    for n in recent:
        print(f'  {n["id"]} | {n.get("title", "")[:60]} | n={len(n.get("items", []))} | imp_max={n.get("importance_max", "?")} | seen={n.get("last_seen", "")[:16]}', flush=True)
except Exception as e:
    print(f'NARRATIVES_ERR={e}', flush=True)

# AGI counter
try:
    with open('data/metrics.json', encoding='utf-8') as f:
        m = json.load(f)
    print(f'AGI_COUNTER={m.get("agi_counter")}', flush=True)
except Exception as e:
    print(f'AGI_ERR={e}', flush=True)

conn.close()
