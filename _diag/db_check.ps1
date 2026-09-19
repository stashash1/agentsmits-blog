[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$py = 'C:\Users\Admin\python312\python.exe'

Write-Host '=== blog.db: last 5 published posts ==='
& $py -c @"
import sqlite3, json
con = sqlite3.connect('data/blog.db')
con.row_factory = sqlite3.Row
print('--- tables ---')
for r in con.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\"):
    print(' ', r['name'])
print('--- posts (last 5) ---')
try:
    rows = con.execute('SELECT id, title, created_at, telegram_msg_id FROM posts ORDER BY id DESC LIMIT 5').fetchall()
    for r in rows:
        print(f\"  id={r['id']} created={r['created_at']} tg_msg={r['telegram_msg_id']!r}\")
        print(f\"     title={r['title'][:80]}\")
except Exception as e:
    print(' posts query err:', e)

print('--- posts count ---')
try:
    print('  total:', con.execute('SELECT COUNT(*) FROM posts').fetchone()[0])
    print('  last 24h:', con.execute(\"SELECT COUNT(*) FROM posts WHERE created_at >= datetime('now','-1 day')\").fetchone()[0])
    print('  last 7d:', con.execute(\"SELECT COUNT(*) FROM posts WHERE created_at >= datetime('now','-7 day')\").fetchone()[0])
except Exception as e:
    print(' count err:', e)

print('--- recently_sent.json ---')
try:
    rs = json.load(open('data/recently_sent.json', encoding='utf-8'))
    print(f\"  items: {len(rs) if isinstance(rs, list) else 'dict-with-'+str(len(rs))}\")
    if isinstance(rs, list) and rs:
        for it in rs[:3]:
            print(' ', {k: (str(v)[:60]) for k,v in it.items()})
except Exception as e:
    print(' err:', e)
"@
