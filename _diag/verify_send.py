"""Verify 5 publishes actually landed in Telegram + DB."""
import json, sqlite3

rows = []
with open(r"C:\Users\Admin\dev\project\agentsmits-blog\data\telegram_audit.log", encoding="utf-8") as f:
    for line in f:
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("ts", "").startswith("2026-09-14"):
            rows.append(r)

print(f"2026-09-14 audit entries: {len(rows)}")
for r in rows:
    msg = r.get("msg_id", 0)
    res = r.get("result", "?")
    acc = r.get("account", "?")
    ms = r.get("duration_ms", "?")
    art = (r.get("article_id") or "")[:50]
    ts = r.get("ts", "")[11:19]
    print(f"  ts={ts} result={res:8} account={acc:18} msg_id={msg:5} ms={ms:5} art={art}")
    if r.get("error"):
        print(f"    err: {r['error'][:140]}")

conn = sqlite3.connect(r"C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db")
n = conn.execute(
    "SELECT COUNT(*) FROM articles WHERE status='published' "
    "AND message_id IS NOT NULL AND message_id>0 "
    "AND published_at LIKE '2026-09-14%'"
).fetchone()[0]
print(f"\nDB: articles marked published today with message_id>0: {n}")

print("\n--- last 8 published with msg_id (DB) ---")
for r in conn.execute(
    "SELECT id, message_id, published_at, substr(title,1,55) "
    "FROM articles WHERE message_id IS NOT NULL AND message_id>0 "
    "ORDER BY published_at DESC LIMIT 8"
):
    pa = (r[2] or "")[11:19]
    print(f"  msg={r[1]:5} {pa} {(r[0] or '')[:50]:50} | {r[3]}")

n_pending = conn.execute("SELECT COUNT(*) FROM articles WHERE status='pending'").fetchone()[0]
print(f"\npending left: {n_pending}")
