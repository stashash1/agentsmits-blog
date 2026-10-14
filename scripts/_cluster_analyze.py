import sqlite3, json, math
from datetime import datetime, timezone, timedelta

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
now_utc = datetime.now(timezone.utc)
msk_offset = timedelta(hours=3)
now_msk = now_utc + msk_offset
print(f'NOW_UTC={now_utc.isoformat()}')
print(f'NOW_MSK={now_msk.isoformat()}')

today_msk_start = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
today_msk_start_utc = today_msk_start - msk_offset

recent_pub = conn.execute("""
    SELECT id, published_at, message_id FROM articles
    WHERE status='published' AND published_at >= ?
    ORDER BY published_at DESC
""", (today_msk_start_utc.isoformat(),)).fetchall()
print(f'TODAY_PUB_MSK={len(recent_pub)}')
for r in recent_pub:
    print(f'  {r["published_at"]} | msg={r["message_id"]}')

def parse_dt(date_str):
    if not date_str:
        return None
    try:
        if 'Z' in date_str or '+' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    except Exception:
        return None

def compute_decay(imp, date_str, now):
    dt = parse_dt(date_str)
    if dt is None:
        return 0.0, 999.0
    age = (now - dt).total_seconds() / 86400.0
    hl_map = {5: 7.0, 4: 7.0, 3: 5.0, 2: 3.0, 1: 3.0}
    hl = hl_map.get(imp, 5.0)
    actual = imp * math.exp(-0.693 / hl * age)
    return actual, age

# Fresh items: age <= 5 days
print('\n--- FRESH IMP>=3 ITEMS (age<=5d, has analysis) ---')
fresh_rows = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, url, narrative_id, is_breakthrough
    FROM articles
    WHERE status='pending' AND importance >= 3 AND agent_impact IS NOT NULL
    ORDER BY importance DESC, date DESC
""").fetchall()
fresh_items = []
for r in fresh_rows:
    actual, age = compute_decay(r['importance'], r['date'], now_utc)
    if age <= 5.0 and actual > 0:
        fresh_items.append((r, actual, age))

print(f'FRESH_COUNT={len(fresh_items)}')
for r, actual, age in fresh_items:
    bt = '[BT]' if r['is_breakthrough'] else '    '
    print(f'  {bt} imp={r["importance"]} actual={actual:.3f} age={age:.2f}d [{r["source_id"]}] narr={r["narrative_id"] or "-"} | {r["title"][:65]}')

# Top items overall regardless of freshness
print('\n--- TOP IMP>=3 ITEMS BY ACTUAL DECAY (has analysis) ---')
top_rows = conn.execute("""
    SELECT id, source_id, title, importance, date, status, agent_impact,
           decayed_importance, url, narrative_id, is_breakthrough
    FROM articles
    WHERE status='pending' AND importance >= 3 AND agent_impact IS NOT NULL
    ORDER BY importance DESC, date DESC
""").fetchall()
items_with_decay = []
for r in top_rows:
    actual, age = compute_decay(r['importance'], r['date'], now_utc)
    items_with_decay.append((r, actual, age))

# Sort by actual decay descending
items_with_decay.sort(key=lambda x: x[1], reverse=True)
print(f'TOTAL_WITH_ANALYSIS={len(items_with_decay)}')
for r, actual, age in items_with_decay[:25]:
    bt = '[BT]' if r['is_breakthrough'] else '    '
    fresh_flag = '[F]' if age <= 5.0 else '[ ]'
    print(f'  {bt}{fresh_flag} imp={r["importance"]} actual={actual:.3f} age={age:.2f}d [{r["source_id"]}] | {r["title"][:60]}')

# Also check narratives
narr_file = 'data/narratives.json'
try:
    with open(narr_file, encoding='utf-8') as f:
        narr_data = json.load(f)
    active = [n for n in narr_data.get('narratives', []) if n.get('status') == 'active']
    print(f'\nNARRATIVES total={len(narr_data.get("narratives",[]))} active={len(active)}')
    # Find narratives with multiple recent items
    for n in active[:10]:
        imp_max = n.get('importance_max', 0)
        n_items = len(n.get('items', []))
        last_seen = n.get('last_seen', '')[:16]
        print(f'  {n["id"]} | n={n_items} imp_max={imp_max} seen={last_seen} | {n.get("title","")[:50]}')
except Exception as e:
    print(f'NARR_ERR={e}')

conn.close()