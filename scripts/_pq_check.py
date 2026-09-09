import json, sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
with open(r'data/pending_queue.json', encoding='utf-8') as f:
    d = json.load(f)
print('pending_queue.json summary:')
print(f'  sources: {len(d.get("sources",[]))}')
print(f'  pending: {len(d.get("pending",[]))}')
print(f'  published: {len(d.get("published",[]))}')
agi = d.get("agi_counter")
print(f'  agi_counter: {agi}')
print()
print('Pending IDs:')
for p in d.get('pending',[]):
    print(f'  - {p["id"]} ({p["source"]}, imp={p["importance"]})')
