
import sqlite3
c = sqlite3.connect(r'C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db')
c.row_factory = sqlite3.Row
rows = c.execute("SELECT article_id, state, error, updated_at FROM editorial_reviews ORDER BY updated_at DESC LIMIT 6").fetchall()
for r in rows:
    print(r['updated_at'], r['state'], repr(r['error'])[:200], r['article_id'][:60])
