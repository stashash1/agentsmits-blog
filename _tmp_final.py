import sqlite3, sys, json, math
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

now_utc = datetime.now(timezone.utc)
now_msk = now_utc + timedelta(hours=3)

# Compute actual current decayed for Tier-1 candidates
print("=== ACTUAL DECAY (re-computed) for Tier-1 ===")
rows = conn.execute(
    "SELECT id, title, importance, date, decayed_importance, agent_impact "
    "FROM articles WHERE status='pending' AND importance=5 AND agent_impact IS NOT NULL "
    "ORDER BY date DESC LIMIT 15"
).fetchall()
for r in rows:
    try:
        ai = json.loads(r['agent_impact']) if r['agent_impact'] else {}
        half_life = ai.get('half_life_days', 7)
    except:
        half_life = 7
    try:
        d = datetime.fromisoformat(r['date'])
        delta = (now_msk.date() - d.date()).days
    except:
        delta = 0
    actual = r['importance'] * math.exp(-0.693 / half_life * delta)
    print(f"  Δ={delta:>2}d hl={half_life} stored={r['decayed_importance']:.2f} ACTUAL={actual:.2f} date={r['date']} | {r['title'][:55]}")

# Fresh items NOT analyzed
print("\n=== FRESH ITEMS NOT ANALYZED (≤5d, blocking analyzer) ===")
fresh_un = conn.execute(
    "SELECT date, COUNT(*) as n FROM articles "
    "WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='') "
    "AND date >= date('now', '-5 days') "
    "GROUP BY date ORDER BY date DESC"
).fetchall()
total_fresh_un = 0
for r in fresh_un:
    print(f"  {r['date']}: {r['n']} items")
    total_fresh_un += r['n']
print(f"Total fresh+unanalyzed: {total_fresh_un}")

# Stale items that ARE analyzed
print("\n=== STALE BUT ANALYZED (>5d, candidate pool) ===")
stale_an = conn.execute(
    "SELECT date, COUNT(*) as n FROM articles "
    "WHERE status='pending' AND agent_impact IS NOT NULL "
    "AND date < date('now', '-5 days') "
    "GROUP BY date ORDER BY date DESC LIMIT 10"
).fetchall()
total_stale_an = 0
for r in stale_an:
    print(f"  {r['date']}: {r['n']} items")
    total_stale_an += r['n']
print(f"Total stale+analyzed: {total_stale_an}")

conn.close()
