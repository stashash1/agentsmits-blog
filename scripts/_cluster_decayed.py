import sqlite3, json, math
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)
msk_offset = timedelta(hours=3)
now_msk = now_utc + msk_offset
print(f'NOW_UTC={now_utc.isoformat()}')
print(f'NOW_MSK={now_msk.isoformat()}')

# MSK-day-based today's publications
today_msk_start = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
today_msk_start_utc = today_msk_start - msk_offset
print(f'TODAY_MSK_START_UTC={today_msk_start_utc.isoformat()}')

recent_pub = conn.execute("""
    SELECT id, published_at, message_id FROM articles
    WHERE status='published' AND published_at >= ?
    ORDER BY published_at DESC
""", (today_msk_start_utc.isoformat(),)).fetchall()
print(f'TODAY_PUB_MSK={len(recent_pub)}')
for r in recent_pub:
    print(f'  {r["published_at"]} | msg={r["message_id"]}')

# Recompute actual decay for top items using consistent half-life mapping
def compute_decay(imp, date_str, now):
    if not date_str:
        return 0.0
    # Treat stored dates as naive — assume UTC
    try:
        if 'Z' in date_str or '+' in date_str:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(date_str)
            dt = dt.replace(tzinfo=timezone.utc)
        age = (now - dt).total_seconds() / 86400.0
    except Exception:
        return 0.0
    hl_map = {5: 7.0, 4: 7.0, 3: 5.0, 2: 3.0, 1: 3.0}
    hl = hl_map.get(imp, 5.0)
    return imp * math.exp(-0.693 / hl * age)

# Check freshness gate (5 days)
freshness_limit_days = 5

print('\n--- TOP IMP5 ITEMS WITH ACTUAL DECAY ---')
rows5 = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, url, narrative_id
    FROM articles
    WHERE status='pending' AND importance >= 5 AND agent_impact IS NOT NULL
    ORDER BY importance DESC, decayed_importance DESC, date DESC
""").fetchall()
for r in rows5:
    actual = compute_decay(r['importance'], r['date'], now_utc)
    print(f'  imp={r["importance"]} stored={r["decayed_importance"]:.3f} actual={actual:.4f} age_days={((now_utc - datetime.fromisoformat(r["date"].replace("Z","+00:00") if "Z" in r["date"] else r["date"])).total_seconds()/86400):.2f} [{r["source_id"]}] | {r["title"][:65]}')

print('\n--- FRESH (age<=5d) IMP3+ ITEMS WITH ANALYSIS ---')
fresh_rows = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, url, narrative_id
    FROM articles
    WHERE status='pending' AND importance >= 3 AND agent_impact IS NOT NULL
    ORDER BY date DESC, importance DESC
""").fetchall()
fresh_count = 0
for r in fresh_rows:
    if not r['date']:
        continue
    try:
        if 'Z' in r['date'] or '+' in r['date']:
            dt = datetime.fromisoformat(r['date'].replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(r['date']).replace(tzinfo=timezone.utc)
    except Exception:
        continue
    age = (now_utc - dt).total_seconds() / 86400.0
    if age <= freshness_limit_days:
        fresh_count += 1
        actual = compute_decay(r['importance'], r['date'], now_utc)
        print(f'  imp={r["importance"]} actual={actual:.4f} age={age:.2f}d [{r["source_id"]}] | {r["title"][:65]}')
print(f'FRESH_COUNT={fresh_count}')

# Tier-1 slot 20:30, Tier-2 slot 22:30, Tier-3 slot would be ~00:30 (next cycle)
print('\n--- TIER-1 SLOT: 20:30 MSK 2026-10-07 ---')
print(f'  Active window: 18:15-23:00 MSK (4h 45m)')
print(f'  Tier-1 reserved 20:30 MSK (2h 15m into active)')

print('\n--- TIER-2 SLOT: 22:30 MSK 2026-10-07 ---')
print(f'  Tier-2 reserved 22:30 MSK (30 min before quiet gate)')

print('\n--- TIER-3 SLOT: would be 00:30 MSK 2026-10-08 ---')
print(f'  OUTSIDE this cycle window. Belongs to cycle 2026-10-08-0015')

conn.close()