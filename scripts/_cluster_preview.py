import sqlite3, json
conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(
    "SELECT id, source_id, title, importance, summary, date, url FROM articles WHERE status='pending' ORDER BY importance DESC, date DESC"
).fetchall()
print(f"Total pending: {len(rows)}")
print("---")
for r in rows:
    print(f"[imp={r['importance']}] [{r['source_id']}] {r['title'][:90]}")
    if r['summary']:
        print(f"    {r['summary'][:160]}")
    print()
