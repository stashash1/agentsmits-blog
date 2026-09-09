import sqlite3
import sys
import json

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')

conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row

# Existing narratives
narratives = conn.execute("SELECT id, title, status, importance_max, entities_json FROM narratives ORDER BY importance_max DESC, last_seen DESC").fetchall()
print(f'Existing narratives: {len(narratives)}')
for n in narratives[:20]:
    ents = json.loads(n['entities_json'])[:5]
    print(f'  [{n["status"]:8s}] imp={n["importance_max"]} | {n["id"]} | {n["title"][:70]}')
    print(f'      ents: {ents}')

# Which pending items have narrative_id assigned?
arts = conn.execute("""
    SELECT narrative_id, COUNT(*) AS n, GROUP_CONCAT(id, ' | ') AS ids
    FROM articles
    WHERE status='pending'
    GROUP BY narrative_id
    ORDER BY n DESC
""").fetchall()
print('\nPending by narrative:')
for r in arts:
    print(f'  narrative={r["narrative_id"]} | count={r["n"]} | ids={r["ids"][:120]}')

conn.close()
