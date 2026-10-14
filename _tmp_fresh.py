import sqlite3, sys, json
from datetime import datetime, timezone, timedelta

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

now_utc = datetime.now(timezone.utc)
now_msk = now_utc + timedelta(hours=3)
print(f"NOW_UTC: {now_utc.isoformat()}")
print(f"NOW_MSK: {now_msk.isoformat()}")
print(f"Freshness cutoff (5 days back): {(now_msk - timedelta(days=5)).date().isoformat()}")

# Check freshness distribution
print("\n=== FRESHNESS DISTRIBUTION (status=pending, analyzed) ===")
rows = conn.execute(
    "SELECT date, COUNT(*) as n FROM articles "
    "WHERE status='pending' AND agent_impact IS NOT NULL "
    "GROUP BY date ORDER BY date DESC"
).fetchall()
for r in rows:
    days_old = (now_msk.date() - datetime.fromisoformat(r['date']).date()).days if r['date'] else None
    fresh = "FRESH" if days_old is not None and days_old <= 5 else "stale"
    print(f"  {r['date']} (Δ={days_old}d, {fresh}): {r['n']} items")

# Try computing ACTUAL current decayed_importance
print("\n=== CURRENT DECAY (re-computed) for imp=5 analyzed ===")
rows = conn.execute(
    "SELECT id, title, importance, date, decayed_importance, agent_impact "
    "FROM articles WHERE status='pending' AND importance=5 AND agent_impact IS NOT NULL "
    "ORDER BY date DESC LIMIT 15"
).fetchall()
for r in rows:
    try:
        # Parse agent_impact JSON to get half_life
        ai = json.loads(r['agent_impact']) if r['agent_impact'] else {}
        half_life = ai.get('half_life_days', 7)
    except:
        half_life = 7
    try:
        d = datetime.fromisoformat(r['date'])
        delta = (now_msk.date() - d.date()).days
    except:
        delta = 0
    import math
    actual = r['importance'] * math.exp(-0.693 / half_life * delta)
    print(f"  Δ={delta}d hl={half_life} stored_decayed={r['decayed_importance']:.2f} ACTUAL={actual:.2f} date={r['date']} | {r['title'][:50]}")

# Check what's actually FRESH and analyzable
print("\n=== FRESH (≤5 days) AND ANALYZED ===")
fresh = conn.execute(
    "SELECT COUNT(*) as n FROM articles "
    "WHERE status='pending' AND agent_impact IS NOT NULL "
    "AND date >= date('now', '-5 days')"
).fetchone()['n']
print(f"Fresh and analyzed: {fresh}")

# Check what dates the most recent analyzed items have
print("\n=== MOST RECENT ANALYZED ITEMS ===")
recent = conn.execute(
    "SELECT date, COUNT(*) as n FROM articles "
    "WHERE status='pending' AND agent_impact IS NOT NULL "
    "GROUP BY date ORDER BY date DESC LIMIT 10"
).fetchall()
for r in recent:
    print(f"  {r['date']}: {r['n']}")

conn.close()
