"""Just schema and pending split — minimal."""
import sqlite3

conn = sqlite3.connect(r"C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("=== articles schema ===")
for r in cur.execute("SELECT cid, name, type FROM pragma_table_info('articles') ORDER BY cid"):
    print(f"  {r['cid']:3} {r['name']:30} {r['type']}")

print("\n=== pending split ===")
n_total = cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending'").fetchone()[0]
n_no_a  = cur.execute("SELECT COUNT(*) FROM articles WHERE status='pending' AND (agent_impact IS NULL OR TRIM(agent_impact)='')").fetchone()[0]
n_w_a   = n_total - n_no_a
print(f"  pending total={n_total}  with agent_impact={n_w_a}  without={n_no_a}")

print("\n=== pending top 10 by importance ===")
for r in cur.execute("""SELECT id, importance, decayed_importance,
                              substr(title,1,70) AS title,
                              analyzed_at
                         FROM articles
                        WHERE status='pending'
                        ORDER BY importance DESC, decayed_importance DESC LIMIT 10"""):
    print(f"  imp={r['importance']:2} di={r['decayed_importance']:5} {r['id']}")
    print(f"      title:     {r['title']}")
    print(f"      analyzed:  {r['analyzed_at']}")

print("\n=== importance distribution among pending ===")
for r in cur.execute("""SELECT importance, COUNT(*) c
                         FROM articles WHERE status='pending'
                        GROUP BY importance ORDER BY importance"""):
    print(f"  imp={r['importance']:2}  count={r['c']}")

print("\n=== date range ===")
for r in cur.execute("""SELECT MIN(date) min_d, MAX(date) max_d, COUNT(DISTINCT date) days
                         FROM articles WHERE status='pending'"""):
    print(f"  min={r['min_d']}  max={r['max_d']}  distinct_days={r['days']}")
