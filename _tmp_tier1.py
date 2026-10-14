import sqlite3, json, sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

# Top Tier-1 candidates
print("=== TIER 1 (imp=5, analyzed) ===")
rows = conn.execute(
    "SELECT id, source_id, title, importance, date, decayed_importance, "
    "is_breakthrough, breakthrough_score, narrative_id "
    "FROM articles WHERE status='pending' AND importance=5 AND agent_impact IS NOT NULL "
    "ORDER BY decayed_importance DESC, date DESC LIMIT 20"
).fetchall()
for r in rows:
    bt = '[BT]' if r['is_breakthrough'] else '    '
    print(f"{bt} imp={r['importance']} decayed={r['decayed_importance']:.2f} date={r['date']} src={r['source_id']} | {r['title'][:70]}")

# Fresh Tier-2 (imp=4, analyzed, decayed >= 2.0)
print("\n=== TIER 2 (imp=4, analyzed, fresh) ===")
rows2 = conn.execute(
    "SELECT id, source_id, title, importance, date, decayed_importance, "
    "is_breakthrough, breakthrough_score, narrative_id "
    "FROM articles WHERE status='pending' AND importance=4 AND agent_impact IS NOT NULL "
    "AND decayed_importance >= 2.0 "
    "ORDER BY decayed_importance DESC, date DESC LIMIT 20"
).fetchall()
print(f"Total count: {len(rows2)}")
for r in rows2[:15]:
    bt = '[BT]' if r['is_breakthrough'] else '    '
    print(f"{bt} imp={r['importance']} decayed={r['decayed_importance']:.2f} date={r['date']} src={r['source_id']} | {r['title'][:70]}")

# Tier-3 (imp=3, analyzed, decayed >= 1.5)
print("\n=== TIER 3 (imp=3, analyzed, fresh) ===")
rows3 = conn.execute(
    "SELECT id, source_id, title, importance, date, decayed_importance, "
    "is_breakthrough, breakthrough_score, narrative_id "
    "FROM articles WHERE status='pending' AND importance=3 AND agent_impact IS NOT NULL "
    "AND decayed_importance >= 1.5 "
    "ORDER BY decayed_importance DESC, date DESC LIMIT 20"
).fetchall()
print(f"Total count: {len(rows3)}")
for r in rows3[:10]:
    bt = '[BT]' if r['is_breakthrough'] else '    '
    print(f"{bt} imp={r['importance']} decayed={r['decayed_importance']:.2f} date={r['date']} src={r['source_id']} | {r['title'][:70]}")

# Total counts by tier
print("\n=== TOTAL COUNTS ===")
t1 = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='pending' AND importance=5 AND agent_impact IS NOT NULL AND decayed_importance >= 4.0").fetchone()['n']
t2 = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='pending' AND importance=4 AND agent_impact IS NOT NULL AND decayed_importance >= 2.0").fetchone()['n']
t3 = conn.execute("SELECT COUNT(*) AS n FROM articles WHERE status='pending' AND importance=3 AND agent_impact IS NOT NULL AND decayed_importance >= 1.5").fetchone()['n']
print(f"Tier-1 candidates (imp=5, fresh, analyzed): {t1}")
print(f"Tier-2 candidates (imp=4, fresh, analyzed): {t2}")
print(f"Tier-3 candidates (imp=3, fresh, analyzed): {t3}")

# Today's published count (30 Sep MSK)
print("\n=== PUBLISH METRICS ===")
today_msk_start = "2026-09-29T21:00:00"  # 30 Sep 00:00 MSK = 29 Sep 21:00 UTC
today_published = conn.execute(
    "SELECT COUNT(*) AS n FROM articles WHERE status='published' AND published_at >= ?",
    (today_msk_start,)
).fetchone()['n']
print(f"Today (30 Sep MSK) published: {today_published}")

# Last 5 published
last5 = conn.execute(
    "SELECT id, source_id, title, published_at, message_id FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 5"
).fetchall()
for r in last5:
    print(f"  msg={r['message_id']} {r['published_at']} | {r['title'][:60]}")

conn.close()
