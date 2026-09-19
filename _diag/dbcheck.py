
import sqlite3, json, datetime
c = sqlite3.connect(r'C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db')
c.row_factory = sqlite3.Row
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
print('TABLES:', tables)
for t in tables:
    try:
        n = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        print(f'{t}: {n}')
    except Exception as e:
        print(t, 'ERR', e)
