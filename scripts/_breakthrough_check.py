import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, '.')
from agentsblog.config import Settings
from agentsblog.db import connect, init_schema, list_pending
from agentsblog.models import Article
from agentsblog.scoring.breakthrough import detect_breakthrough

s = Settings()
conn = connect(s.db_path)
init_schema(conn)
arts = list_pending(conn, min_importance=3, limit=None)
print(f'Publishable items (imp>=3): {len(arts)}')
for a in arts:
    bt = detect_breakthrough(a)
    bt_summary = "BREAKTHROUGH" if bt.is_breakthrough else "standard"
    print(f'\n[{bt_summary} | score={bt.score}] [imp={a.importance}] [{a.source_id}] {a.date}')
    print(f'  ID: {a.id}')
    print(f'  Title: {(a.translated_title or a.title)[:120]}')
    print(f'  Reasons: {bt.reasons}')
    print(f'  Arch: {bt.matched_architectures[:2]}')
    print(f'  SOTA: {bt.matched_sota[:2]}')
    print(f'  Non-break: {bt.matched_non_breakthrough[:2]}')
conn.close()
