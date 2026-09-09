import sqlite3
conn = sqlite3.connect('data/blog.db')
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT ts, run_id, script, event, severity, details_json FROM events ORDER BY ts DESC LIMIT 15").fetchall()
for r in rows:
    d = r['details_json'][:200]
    print(f"{r['ts']} [{r['severity']}] {r['script']}/{r['event']} | {d}")
conn.close()
