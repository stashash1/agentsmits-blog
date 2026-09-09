import sqlite3, json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from agentsblog.config import Settings
from agentsblog.db import connect, init_schema, list_pending
from agentsblog.clustering.narratives import find_matching_narrative, _filter_entities
from agentsblog.models import Narrative
from agentsblog.scoring.impact import extract_entities_from_item
from datetime import datetime, timezone

s = Settings()
conn = connect(s.db_path)
init_schema(conn)

# Load all active/cooling narratives
conn.row_factory = sqlite3.Row
narrs_rows = conn.execute(
    "SELECT id, title, status, importance_max, entities_json FROM narratives WHERE status IN ('active','cooling') ORDER BY importance_max DESC"
).fetchall()
narrs = []
for r in narrs_rows:
    n = Narrative(
        id=r['id'], title=r['title'], status=r['status'],
        first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc),
        entities=json.loads(r['entities_json']),
        importance_max=r['importance_max'],
        items=[],
        source='auto',
    )
    narrs.append(n)
print(f'Loaded {len(narrs)} active/cooling narratives')

# Use list_pending to get proper Article models (with analysis parsed from ai_impact_json)
arts = list_pending(conn, min_importance=3, limit=None)
print(f'\nPublishable items (imp>=3): {len(arts)}')
for a in arts:
    ents = extract_entities_from_item(a)
    ents_f = _filter_entities(ents)
    match = find_matching_narrative(ents_f, narrs)
    print(f'\n[imp={a.importance}] {a.id}')
    print(f'  title: {(a.translated_title or a.title)[:80]}')
    print(f'  ents: {ents_f[:12]}')
    if match:
        print(f'  -> MATCH: {match.id} | {match.title[:80]} (imp_max={match.importance_max})')
    else:
        print(f'  -> no match (would create new)')

conn.close()
