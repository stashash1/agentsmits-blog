import sys, sqlite3
sys.path.insert(0, '.')
from agentsblog.scoring.impact import is_release_item
from agentsblog.db import connect, list_pending
from agentsblog.models import Article

# Force load via DB
conn = sqlite3.connect('data/blog.db')

cur = conn.cursor()
cur.execute("SELECT id, title, source_id, source_id, date, importance, url, summary, agent_impact, business_impact, it_impact FROM articles WHERE status='pending'")
rows = cur.fetchall()
cols = [d[0] for d in cur.description]
print('cols:', cols)

for r in rows:
    art_dict = dict(zip(cols, r))
    # build Article-like object via __init__
    a = Article(
        id=art_dict['id'],
        source_id=art_dict['source_id'],
        title=art_dict['title'],
        url=art_dict['url'] or '',
        date=art_dict['date'] or '',
        importance=art_dict['importance'],
        summary=art_dict['summary'],
        agent_impact=art_dict['agent_impact'],
        business_impact=art_dict['business_impact'],
        it_impact=art_dict['it_impact'],
    )
    is_rel = is_release_item(a)
    if is_rel:
        print(f"RELEASE: {art_dict['id']} | source={art_dict['source_id']} | imp={art_dict['importance']} | is_release={is_rel}")
        print(f"  title: {art_dict['title']}")
print('---DONE---')
conn.close()
