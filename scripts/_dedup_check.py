import sqlite3, sys, json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')
from agentsblog.config import Settings
from agentsblog.db import connect, init_schema, list_pending
from agentsblog.publishing.dedup import was_recently_sent
from agentsblog.publishing.formatter import compute_agi, format_standard

s = Settings()
conn = connect(s.db_path)
init_schema(conn)

# Check for each publishable item whether it's been recently sent (24h dedup)
agi_days, agi_pct = compute_agi(s)
arts = list_pending(conn, min_importance=3, limit=None)
print(f'AGI: {agi_days} days / {agi_pct}%')
print(f'\nDedup check for {len(arts)} publishable items:')
for a in arts:
    text = format_standard(a, agi_days=agi_days, agi_percent=agi_pct)
    if text is None:
        print(f'\n[a.id]  format_standard returned None — no analysis')
        continue
    prev = was_recently_sent(text, s)
    if prev is False:
        print(f'\n[{a.id}]  NOT in dedup (clean) -> OK to publish')
    else:
        msg = prev if isinstance(prev, int) else 'dedup'
        print(f'\n[{a.id}]  DEDUP HIT — already sent (msg_id={msg})')

conn.close()
