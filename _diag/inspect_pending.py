#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
from datetime import datetime, timezone, timedelta

QUEUE = r'C:\Users\Admin\dev\project\agentsmits-blog\data\pending_queue.json'

with open(QUEUE, 'r', encoding='utf-8') as f:
    data = json.load(f)

pending = data.get('pending', [])
msk = timezone(timedelta(hours=3))
now = datetime.now(msk)
print('Now:', now.strftime('%Y-%m-%d %H:%M MSK'))
print('Total pending:', len(pending))
print()

for i, p in enumerate(pending):
    print('[' + str(i+1) + '] ' + str(p.get('id', '?'))[:70])
    src = p.get('source')
    dt = p.get('date')
    tier = p.get('ai_impact', {}).get('tier') if p.get('ai_impact') else None
    imp = p.get('importance')
    dec = p.get('decayed_importance')
    print('    Source: ' + str(src) + ' | Date: ' + str(dt) + ' | Tier: ' + str(tier) + ' | Base: ' + str(imp) + ' | Decayed: ' + str(dec))
    if p.get('analysis'):
        a = p['analysis']
        title = (a.get('translated_title') or '')[:120]
        summ = (a.get('summary') or '')[:200]
        print('    Title: ' + title)
        print('    Summary: ' + summ + '...')
    else:
        print('    Title (orig): ' + (p.get('title') or '')[:120])
        print('    *** NO ANALYSIS ***')
    print()
