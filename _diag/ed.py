
import sqlite3, json
c = sqlite3.connect(r'C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db')
c.row_factory = sqlite3.Row
cols = [r[1] for r in c.execute("PRAGMA table_info(editorial_reviews)")]
print('COLS:', cols)
rows = c.execute("SELECT * FROM editorial_reviews ORDER BY rowid DESC LIMIT 6").fetchall()
for r in rows:
    d = dict(r)
    print({k: (str(v)[:200] if v is not None else None) for k,v in d.items()})
    print('---')
# verdict distribution
try:
    rows = c.execute("SELECT verdict, COUNT(*) n FROM editorial_reviews GROUP BY verdict").fetchall()
    print('verdicts:', [(r['verdict'], r['n']) for r in rows])
except Exception as e:
    print('no verdict col:', e)
