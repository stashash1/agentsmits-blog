
import sqlite3, json
c = sqlite3.connect(r'C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db')
c.row_factory = sqlite3.Row
# articles schema
cols = [r[1] for r in c.execute("PRAGMA table_info(articles)")]
print('ARTICLES COLS:', cols)
print()
# status distribution guesses
for col in ['status','state','published','agent_impact','published_at','analyzed_at','scored_at']:
    if col in cols:
        try:
            rows = c.execute(f"SELECT {col}, COUNT(*) n FROM articles GROUP BY {col} ORDER BY n DESC LIMIT 12").fetchall()
            print(f'-- {col}:')
            for r in rows: print('  ', repr(r[0])[:60], r['n'])
        except Exception as e:
            print(col, 'ERR', e)
print()
# recent articles
rows = c.execute("SELECT * FROM articles ORDER BY rowid DESC LIMIT 3").fetchall()
for r in rows:
    d = dict(r)
    print({k: (str(v)[:80] if v is not None else None) for k,v in d.items()})
