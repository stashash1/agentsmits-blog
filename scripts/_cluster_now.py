import sqlite3, json, math
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
now = datetime.now(timezone.utc)
print(f'NOW_UTC={now.isoformat()}')

rows = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, breakthrough_score, summary, url
    FROM articles
    WHERE status='pending' AND importance >= 5 AND agent_impact IS NOT NULL
    ORDER BY importance DESC, decayed_importance DESC, date DESC
""").fetchall()
print(f'IMP5_ANALYZED={len(rows)}')
for r in rows:
    print(f'  imp={r["importance"]} decayed={r["decayed_importance"]:.3f} [{r["source_id"]}] | {r["title"][:80]}')
    print(f'    date={r["date"]} | url={(r["url"] or "")[:80]}')

rows4 = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, breakthrough_score, summary, url
    FROM articles
    WHERE status='pending' AND importance >= 4 AND importance < 5 AND agent_impact IS NOT NULL
    ORDER BY decayed_importance DESC, date DESC
""").fetchall()
print(f'IMP4_ANALYZED={len(rows4)}')
for r in rows4[:25]:
    print(f'  imp={r["importance"]} decayed={r["decayed_importance"]:.3f} [{r["source_id"]}] | {r["title"][:70]}')

recent_pub = conn.execute("""
    SELECT id, source_id, title, published_at, message_id
    FROM articles
    WHERE status='published' AND published_at IS NOT NULL
    ORDER BY published_at DESC LIMIT 20
""").fetchall()
print('RECENT_PUB:')
for r in recent_pub:
    print(f'  {r["published_at"]} | msg={r["message_id"]} | {r["title"][:60]}')

today_count = conn.execute("""
    SELECT COUNT(*) AS n FROM articles
    WHERE status='published' AND date(published_at, 'utc') = date('now', 'utc')
""").fetchone()['n']
print(f'TODAY_PUB_UTC={today_count}')

high_decayed = conn.execute("""
    SELECT id, source_id, title, importance, date, decayed_importance, agent_impact
    FROM articles
    WHERE status='pending' AND decayed_importance >= 1.0 AND agent_impact IS NOT NULL
    ORDER BY decayed_importance DESC, importance DESC
""").fetchall()
print(f'HIGH_DECAYED_GE_1.0={len(high_decayed)}')
for r in high_decayed[:30]:
    print(f'  imp={r["importance"]} decayed={r["decayed_importance"]:.3f} [{r["source_id"]}] | {r["title"][:70]}')

# Check actual compute of decay using fresh date
print('\n--- RECOMPUTE_DECAY FOR TOP IMP5 ITEMS ---')
import math
for r in rows[:5]:
    d = r['date']
    if d:
        try:
            dt = datetime.fromisoformat(d.replace('Z', '+00:00'))
            age_days = (now - dt).total_seconds() / 86400.0
            hl = 7.0 if r['importance'] == 5 else (5.0 if r['importance'] == 3 else 3.0)
            actual = r['importance'] * math.exp(-0.693 / hl * age_days)
            print(f'  age={age_days:.2f}d hl={hl} actual={actual:.4f} | {r["title"][:60]}')
        except Exception as e:
            print(f'  ERR {e}')

conn.close()