import sqlite3
conn = sqlite3.connect('data/blog.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(sources)")
for r in cur.fetchall():
    print(r)
print('---')
cur.execute("SELECT id, name, tier FROM sources ORDER BY id")
for r in cur.fetchall():
    print(r)
conn.close()
