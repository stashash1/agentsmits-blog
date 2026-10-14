import sqlite3, math, json
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)

# Breakthrough items
rows = conn.execute(
    "SELECT id, importance, title, is_breakthrough, breakthrough_score, date FROM articles "
    "WHERE status='pending' AND is_breakthrough=1 "
    "ORDER BY importance DESC, breakthrough_score DESC LIMIT 15"
).fetchall()
print(f'BREAKTHROUGH_PENDING={len(rows)}')
for r in rows:
    age = None
    if r['date']:
        try:
            d = r['date'].replace('Z', '+00:00') if 'Z' in r['date'] else r['date']
            dt = datetime.fromisoformat(d)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age = (now_utc - dt).total_seconds() / 86400.0
        except Exception:
            pass
    age_str = f'{age:.1f}d' if age is not None else '?'
    print(f'  imp={r["importance"]} bt_score={r["breakthrough_score"]} age={age_str} | {r["title"][:70]}')

# Top FRESH Tier-2 candidates by ACTUAL decay (imp=3+ analyzed, age<=5d)
def parse_dt(s):
    if not s:
        return None
    try:
        d = s.replace('Z', '+00:00') if 'Z' in s else s
        dt = datetime.fromisoformat(d)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def compute_decay(imp, date_str):
    dt = parse_dt(date_str)
    if dt is None:
        return 0.0, 999.0
    age = (now_utc - dt).total_seconds() / 86400.0
    hl = 7.0 if imp >= 4 else (5.0 if imp == 3 else 3.0)
    return imp * math.exp(-0.693 / hl * age), age

print('\n--- TOP FRESH TIER-2 CANDIDATES (imp>=3, analyzed, age<=5d) ---')
rows2 = conn.execute(
    "SELECT id, source_id, title, importance, date, decayed_importance, agent_impact "
    "FROM articles WHERE status='pending' AND importance >= 3 AND agent_impact IS NOT NULL"
).fetchall()
fresh = []
for r in rows2:
    actual, age = compute_decay(r['importance'], r['date'])
    if age <= 5.0:
        fresh.append((r, actual, age))
fresh.sort(key=lambda x: (x[1], -x[2]), reverse=True)
print(f'FRESH_COUNT={len(fresh)}')
for r, actual, age in fresh[:15]:
    print(f'  imp={r["importance"]} actual={actual:.3f} age={age:.2f}d [{r["source_id"]}] | {r["title"][:65]}')

conn.close()