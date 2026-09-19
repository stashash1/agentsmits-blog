
import sqlite3
c = sqlite3.connect(r'C:\Users\Admin\dev\project\agentsmits-blog\data\blog.db')
c.row_factory = sqlite3.Row
# pending with agent_impact (ready to publish) vs without
r = c.execute("SELECT COUNT(*) n FROM articles WHERE status='pending' AND agent_impact != ''").fetchone()
print('pending+analyzed (ready to publish):', r['n'])
r = c.execute("SELECT COUNT(*) n FROM articles WHERE status='pending' AND (agent_impact IS NULL OR agent_impact='')").fetchone()
print('pending NOT analyzed:', r['n'])
# importance of unanalyzed pending
rows = c.execute("SELECT importance, COUNT(*) n FROM articles WHERE status='pending' AND agent_impact='' GROUP BY importance ORDER BY importance DESC").fetchall()
for x in rows: print('  importance', x['importance'], '->', x['n'])
# last published
rows = c.execute("SELECT published_at, COUNT(*) n FROM articles WHERE status='published' AND published_at IS NOT NULL GROUP BY substr(published_at,1,10) ORDER BY 1 DESC LIMIT 10").fetchall()
print('published per day (last):')
for x in rows: print('  ', x['published_at'][:10], x['n'])
# narratives
r = c.execute("SELECT COUNT(*) n FROM narratives").fetchone(); print('narratives:', r['n'])
cols = [x[1] for x in c.execute("PRAGMA table_info(narratives)")]
print('narr cols:', cols)
