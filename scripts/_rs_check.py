import json
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
with open(r'data/recently_sent.json', encoding='utf-8') as f:
    d = json.load(f)
items = d.get('items', [])
print(f'Total items in recently_sent: {len(items)}')
print('Last 5:')
for item in items[-5:]:
    ts = item.get('ts', 'n/a')
    fp = item.get('fp', 'n/a')
    mid = item.get('msg_id', '?')
    head = item.get('text_head', '')
    print(f'  - ts={ts} msg_id={mid} fp={fp[:20] if isinstance(fp, str) else fp} head={head[:100]}')
