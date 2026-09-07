import sqlite3
c = sqlite3.connect('data/blog.db')
print('---articles columns---')
for r in c.execute("PRAGMA table_info(articles)"):
    print(' ', r[1], r[2])
print()
print('---last 4 published (raw)---')
sql = (
    "SELECT * FROM articles WHERE status='published' "
    "ORDER BY COALESCE(published_at, updated_at, '') DESC LIMIT 4"
)
cols = [d[0] for d in c.description] if False else None
for row in c.execute(sql):
    if cols is None:
        cols = [d[0] for d in c.description]
    d = dict(zip(cols, row))
    print(' ', {k:v for k,v in d.items() if k in ('id','status','importance','source','published_at','updated_at','telegram_msg_id','message_id','published_msg_id','last_published_at') and v is not None})
