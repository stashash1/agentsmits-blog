[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$py = 'C:\Users\Admin\python312\python.exe'
$env:PYTHONIOENCODING = 'utf-8'

Write-Host '=== pending_queue.json stats ==='
& $py -c @"
import json
d = json.load(open('data/pending_queue.json', encoding='utf-8'))
if isinstance(d, dict):
    print('keys:', list(d.keys())[:20])
    if 'items' in d:
        items = d['items']
    elif 'queue' in d:
        items = d['queue']
    else:
        items = []
    print('total items:', len(items))
    if items:
        # newest / oldest
        items.sort(key=lambda x: x.get('discovered_at') or x.get('ts') or x.get('created_at') or '')
        print('oldest:', items[0].get('discovered_at') or items[0].get('ts'))
        print('newest:', items[-1].get('discovered_at') or items[-1].get('ts'))
        # breakdown by source
        from collections import Counter
        c = Counter(i.get('source','?') for i in items)
        print('by source (top 8):', c.most_common(8))
        # tier
        c2 = Counter(i.get('tier','?') for i in items)
        print('by tier:', dict(c2))
else:
    print('type:', type(d).__name__, 'len:', len(d))
    if d:
        d.sort(key=lambda x: x.get('discovered_at') or x.get('ts') or x.get('created_at') or '')
        print('oldest:', d[0].get('discovered_at') or d[0].get('ts'))
        print('newest:', d[-1].get('discovered_at') or d[-1].get('ts'))
"@

Write-Host ''
Write-Host '=== narratives.json stats ==='
& $py -c @"
import json
d = json.load(open('data/narratives.json', encoding='utf-8'))
if isinstance(d, dict):
    print('keys:', list(d.keys())[:10])
    items = d.get('narratives') or d.get('items') or d.get('clusters') or []
    print('narratives:', len(items))
    if items:
        items.sort(key=lambda x: x.get('updated_at') or x.get('created_at') or '')
        print('oldest:', items[0].get('updated_at') or items[0].get('created_at'))
        print('newest:', items[-1].get('updated_at') or items[-1].get('created_at'))
        # importance
        from collections import Counter
        c = Counter(i.get('status','?') for i in items)
        print('by status:', dict(c))
"@

Write-Host ''
Write-Host '=== sync_status.json ==='
Get-Content data\sync_status.json -ErrorAction SilentlyContinue
