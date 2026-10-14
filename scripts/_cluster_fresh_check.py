import sqlite3, json, sys, math
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

# Recent pending items (last 7 days)
today = '2026-10-04'
cutoff = '2026-09-27'  # 7 days
rows = conn.execute(
    f"SELECT id, source_id, title, importance, date, agent_impact, narrative_id, "
    f"decayed_importance, is_breakthrough, breakthrough_score "
    f"FROM articles WHERE status='pending' AND date >= '{cutoff}' "
    f"ORDER BY importance DESC, decayed_importance DESC, date DESC"
).fetchall()
print(f'PENDING_LAST_7D={len(rows)} (cutoff={cutoff})', flush=True)

# Group by importance
imps = {}
for r in rows:
    imps.setdefault(r['importance'], []).append(r)
for imp in sorted(imps.keys(), reverse=True):
    print(f'\n=== IMPORTANCE {imp}: {len(imps[imp])} items ===', flush=True)
    for r in imps[imp][:15]:
        bt = '[BT]' if r['is_breakthrough'] else '   '
        ana = '[A]' if r['agent_impact'] else '[ ]'
        narr = r['narrative_id'] or '-'
        print(f'  {bt}{ana} date={r["date"]} decayed={r["decayed_importance"]:.4f} [{r["source_id"]}] narr={narr}', flush=True)
        print(f'      {r["title"][:120]}', flush=True)

# Check fresh tier candidates
print('\n=== FRESH TIER CANDIDATES (date >= 2026-10-01) ===', flush=True)
fresh = conn.execute(
    f"SELECT id, source_id, title, importance, date, decayed_importance, agent_impact "
    f"FROM articles WHERE status='pending' AND date >= '2026-10-01' "
    f"ORDER BY importance DESC, decayed_importance DESC, date DESC LIMIT 30"
).fetchall()
for r in fresh:
    ana = '[A]' if r['agent_impact'] else '[ ]'
    print(f'  imp={r["importance"]} decayed={r["decayed_importance"]:.4f} date={r["date"]} {ana} [{r["source_id"]}] {r["title"][:80]}', flush=True)

# Most recent publish runs
print('\n=== LAST 5 PUBLISH (recent activity) ===', flush=True)
last = conn.execute(
    f"SELECT id, source_id, title, published_at, message_id, importance "
    f"FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 5"
).fetchall()
for r in last:
    print(f'  [{r["source_id"]}] imp={r["importance"]} | {r["title"][:60]} | {r["published_at"]}', flush=True)

# Daily limit
daily = conn.execute(
    f"SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) = '2026-10-04'"
).fetchone()['n']
print(f'\nDAILY_LIMIT_USED=2026-10-04: {daily}/3', flush=True)

# Last 3 cycles of publish
print('\n=== DAILY COUNT LAST 7 DAYS ===', flush=True)
for d in ['2026-10-04', '2026-10-03', '2026-10-02', '2026-10-01', '2026-09-30', '2026-09-29', '2026-09-28']:
    n = conn.execute(f"SELECT COUNT(*) AS n FROM articles WHERE status='published' AND date(published_at) = '{d}'").fetchone()['n']
    print(f'  {d}: {n}', flush=True)

conn.close()