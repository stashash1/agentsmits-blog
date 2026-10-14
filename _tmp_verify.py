import json
import os
d = json.load(open(r'C:\Users\Admin\dev\project\agentsmits-blog\data\cluster_plan_2026-10-03-0615.json', encoding='utf-8'))
print('cycle_id:', d['cycle_id'])
print('window_msk:', d['window_msk'])
print('quiet_hours_applied:', d['quiet_hours_applied'])
print('pending_total:', d['pending_total'])
print('scheduled:', d['scheduled_count'])
print('deferred:', d['deferred_count'])
print('publishable:', d['publishable_pending'])
print('---DEFERRED TIERS---')
for x in d['deferred']:
    print(f"  T{x['tier']} | imp={x['importance']} | age={x['age_days_at_now']}d | act={x['actual_decayed_importance']} | {x['article_id'][:55]}")
print('---WARNINGS COUNT:', len(d['warnings']))
print('---NEXT CYCLE:', d['next_cycle_projection']['next_cycle_id'])
print('---CACHE EVICT COUNT:', len(d['next_cycle_projection']['cache_evict_recommended_for_next_cycle']))
print('---META:', json.dumps(d['meta'], ensure_ascii=False, indent=2))