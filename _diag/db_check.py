"""One-shot diagnostic for blog.db — articles by status, pending split by analysis presence."""
import sqlite3

conn = sqlite3.connect(r"C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== articles by status ===")
for r in cur.execute("SELECT status, COUNT(*) c FROM articles GROUP BY status"):
    print(f"  {r['status']:12} {r['c']}")

print("\n=== pending split by agent_impact ===")
n_total = cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending'").fetchone()[0]
n_no_a  = cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending' AND (agent_impact IS NULL OR TRIM(agent_impact)='')").fetchone()[0]
n_w_a   = cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending' AND agent_impact IS NOT NULL AND TRIM(agent_impact)<>''").fetchone()[0]
print(f"  pending total        = {n_total}")
print(f"  with agent_impact    = {n_w_a}")
print(f"  without agent_impact = {n_no_a}")

print("\n=== pending top 8 by importance ===")
for r in cur.execute("""SELECT id, importance, decayed_importance,
                              substr(title,1,70) AS title,
                              length(content) AS clen,
                              CASE WHEN ai_impact IS NOT NULL THEN 1 ELSE 0 END AS has_ai,
                              analyzed_at
                         FROM articles
                        WHERE status='pending'
                        ORDER BY importance DESC, decayed_importance DESC LIMIT 8"""):
    print(f"  imp={r['importance']:2} di={r['decayed_importance']:5} ai={r['has_ai']} cl={r['clen']:5} {r['id']}")
    print(f"      title: {r['title']}")
    print(f"      analyzed_at: {r['analyzed_at']}")

print("\n=== pending bottom 5 by importance ===")
for r in cur.execute("""SELECT id, importance, decayed_importance, substr(title,1,60) AS title
                         FROM articles
                        WHERE status='pending'
                        ORDER BY importance ASC, decayed_importance ASC LIMIT 5"""):
    print(f"  imp={r['importance']:2} di={r['decayed_importance']:5} {r['id']} | {r['title']}")

print("\n=== schema of articles table ===")
for r in cur.execute("SELECT name, type FROM pragma_table_info('articles') ORDER BY cid"):
    print(f"  {r['name']:25} {r['type']}")
