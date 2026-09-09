import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

rows = conn.execute(
    """SELECT id, source_id, title, importance, decayed_importance, date, narrative_id,
              agent_impact, business_impact, it_impact, summary, translated_title, tags_json
       FROM articles
       WHERE status='pending' AND importance >= 3
       ORDER BY importance DESC, decayed_importance DESC, date DESC"""
).fetchall()
print(f'Publishable (imp>=3): {len(rows)}')
for r in rows:
    print(f'\n[imp={r["importance"]} decayed={r["decayed_importance"]:.2f}] [{r["source_id"]:15s}] {r["date"]} | narr={r["narrative_id"]}')
    print(f'  ID: {r["id"]}')
    print(f'  Title (orig): {(r["title"] or "")[:120]}')
    print(f'  Title (ru): {(r["translated_title"] or "")[:120]}')
    if r['summary']:
        s = r['summary'].replace('\n', ' ')[:200]
        print(f'  Summary: {s}')

# Also list the rest (imp<3) for completeness
low = conn.execute(
    """SELECT id, source_id, title, importance, decayed_importance, date FROM articles
       WHERE status='pending' AND importance < 3
       ORDER BY importance DESC, date DESC"""
).fetchall()
print(f'\n=== Below publish threshold ({len(low)} items) ===')
for r in low:
    print(f'  [imp={r["importance"]} decayed={r["decayed_importance"]:.2f}] {r["source_id"]:15s} {r["date"]} | {r["title"][:90]}')

conn.close()
