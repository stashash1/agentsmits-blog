import sqlite3
import json

conn = sqlite3.connect('data/blog.db')
cur = conn.cursor()

# Schema introspection
cur.execute("PRAGMA table_info(articles)")
cols = [r[1] for r in cur.fetchall()]
print('articles columns:', cols)

cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending'")
print('Pending count:', cur.fetchone()[0])

cur.execute("SELECT importance, COUNT(*) FROM articles WHERE status='pending' GROUP BY importance ORDER BY importance DESC")
print('Pending by importance:', cur.fetchall())

# source-like column
src_col = 'source' if 'source' in cols else ('source_id' if 'source_id' in cols else None)
if src_col:
    cur.execute(f"SELECT {src_col}, COUNT(*) FROM articles WHERE status='pending' GROUP BY {src_col} ORDER BY 2 DESC")
    print(f'Pending by {src_col}:', cur.fetchall())

# Publishable
pub_col_select = ', '.join(c for c in ['id', src_col, 'title', 'importance', 'date', 'narrative_id', 'scanned_at', 'summary', 'translated_title', 'url', 'tags'] if c and c in cols)
cur.execute(f"SELECT {pub_col_select} FROM articles WHERE status='pending' AND importance >= 3 ORDER BY importance DESC, date DESC")
rows = cur.fetchall()
print('Publishable (imp>=3):')
for row in rows:
    print(' ', row)

# Pending imp=2
imp2_cols = ', '.join(c for c in ['id', src_col, 'title', 'importance', 'date', 'narrative_id', 'scanned_at'] if c and c in cols)
cur.execute(f"SELECT {imp2_cols} FROM articles WHERE status='pending' AND importance = 2 ORDER BY date DESC")
print('imp=2 items:')
for row in cur.fetchall():
    print(' ', row)

# Recent published
cur.execute("SELECT COUNT(*) FROM articles WHERE status='published'")
print('Published count:', cur.fetchone()[0])
recent_cols = ', '.join(c for c in ['id', src_col, 'title', 'importance', 'published_at', 'telegram_msg_id'] if c and c in cols)
cur.execute(f"SELECT {recent_cols} FROM articles WHERE status='published' ORDER BY published_at DESC LIMIT 15")
print('Last 15 published:')
for row in cur.fetchall():
    print(' ', row)

# AGI counter
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    print('Tables:', tables)
    if 'settings' in tables:
        cur.execute("SELECT * FROM settings")
        for row in cur.fetchall():
            print(' setting:', row)
except Exception as e:
    print('AGI settings err:', e)

# last event
try:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
    if cur.fetchone():
        cur.execute("SELECT * FROM events ORDER BY rowid DESC LIMIT 5")
        for row in cur.fetchall():
            print(' event:', row)
except Exception as e:
    print('events err:', e)

# recently_sent? narratives?
for tname in ['narratives', 'sources', 'telegram_audit']:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tname,))
    if cur.fetchone():
        cur.execute(f"SELECT COUNT(*) FROM {tname}")
        print(f' {tname} count:', cur.fetchone()[0])

conn.close()
