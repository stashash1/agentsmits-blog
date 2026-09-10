import json

with open('C:/Users/Admin/dev/project/agentsmits-blog/data/pending_queue.json', encoding='utf-8') as f:
    d = json.load(f)

print('=== pending_queue.json ===')
print('keys:', list(d.keys()))
print('sources count:', len(d.get('sources', [])))
print('pending count:', len(d.get('pending', [])))
print('published count:', len(d.get('published', [])))
print()
print('=== AGI counter ===')
print(json.dumps(d.get('agi_counter'), indent=2))
print()
print('=== PENDING ITEMS ===')
for i, item in enumerate(d['pending']):
    print(f'--- [{i}] ---')
    print(f"id: {item.get('id')}")
    print(f"importance: {item.get('importance')}")
    print(f"source: {item.get('source')}")
    print(f"date: {item.get('date')}")
    print(f"url: {item.get('url')}")
    print(f"title: {item.get('title')}")
    sum_ = item.get('summary', '')
    if sum_:
        print(f"summary: {sum_}")
    # Print extra fields if any
    for k, v in item.items():
        if k not in ('id', 'importance', 'source', 'date', 'url', 'title', 'summary'):
            print(f"  {k}: {v}")
    print()

print('=== SOURCES (first 5) ===')
for s in d.get('sources', [])[:5]:
    print(s)
