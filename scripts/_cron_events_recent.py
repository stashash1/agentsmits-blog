import sqlite3, json
conn = sqlite3.connect('data/blog.db')
cur = conn.cursor()
cur.execute("SELECT id, ts, run_id, script, event, details_json FROM events WHERE ts >= '2026-09-08T14:00:00' ORDER BY id DESC LIMIT 30")
for r in cur.fetchall():
    print(r[0], r[1], r[2], r[3], r[4])
    if r[5] and r[5] != '{}':
        try:
            d = json.loads(r[5])
            for k,v in d.items():
                print(f'   {k}: {v}')
        except Exception:
            print('   (raw):', r[5])
conn.close()
