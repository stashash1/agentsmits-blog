import sqlite3
c = sqlite3.connect("data/blog.db")
c.row_factory = sqlite3.Row
rows = c.execute(
    "SELECT status, COUNT(*) AS n FROM articles GROUP BY status"
).fetchall()
print("status counts:")
for r in rows:
    print("  ", dict(r))
print("---last 5 published---")
for r in c.execute(
    "SELECT id, source_id, published_at FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 5"
).fetchall():
    print(" ", dict(r))
print("---last published by importance---")
for r in c.execute(
    "SELECT importance, COUNT(*) AS n FROM articles WHERE status='published' GROUP BY importance"
).fetchall():
    print(" ", dict(r))
print("---pending by importance---")
for r in c.execute(
    "SELECT importance, COUNT(*) AS n FROM articles WHERE status='pending' GROUP BY importance"
).fetchall():
    print(" ", dict(r))
