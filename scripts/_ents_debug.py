import sqlite3, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from agentsblog.config import Settings
from agentsblog.db import connect, init_schema, list_pending
from agentsblog.scoring.impact import extract_entities_from_item

s = Settings()
conn = connect(s.db_path)
init_schema(conn)
arts = list_pending(conn, min_importance=3, limit=None)
for a in arts:
    ents = extract_entities_from_item(a)
    print(f'\n[{a.id}]')
    print(f'  title (orig): {(a.title or "")[:120]}')
    print(f'  title (ru): {(a.translated_title or "")[:120]}')
    print(f'  summary: {(a.summary or "")[:200]}')
    print(f'  tags: {a.tags}')
    print(f'  agent_impact[:80]: {(a.agent_impact or "")[:80]}')
    print(f'  -> ents: {ents}')
