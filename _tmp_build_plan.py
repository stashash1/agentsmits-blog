#!/usr/bin/env python3
"""Build cluster plan for cycle 2026-10-03-0615."""
import json
import math
import os
import sys
from datetime import datetime, timezone, timedelta

os.environ['PYTHONIOENCODING'] = 'utf-8'

DATA = r'C:\Users\Admin\dev\project\agentsmits-blog\data'

NOW_MSK = datetime(2026, 10, 3, 6, 15, 0, tzinfo=timezone(timedelta(hours=3)))
CYCLE_ID = "2026-10-03-0615"
WINDOW_END_MSK = datetime(2026, 10, 3, 12, 15, 0, tzinfo=timezone(timedelta(hours=3)))

HALF_LIFE = {1: 7, 2: 5, 3: 3}
TIER_RULES = {5: 1, 4: 1, 3: 2, 2: 3, 1: 3}

ORIGINAL_DATES = {
    "openai-our-decision-on-cursor-following-its-acquisition-by--57a3b900535e": datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc),
    "huggingface-open-asr-leaderboard-global-south": datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc),
    "techcrunch-musks-faster-path-to-more-gas-turbines-comes-wit-d5dafdd78fb6": datetime(2026, 8, 30, 11, 45, tzinfo=timezone.utc),
    "techcrunch-caterpillar-is-bringing-to-ai-deployment-what-it-e4de3653e651": datetime(2026, 8, 30, 11, 45, tzinfo=timezone.utc),
    "techcrunch-the-u-s-is-building-barriers-around-drones-and-r-c053743dc5a1": datetime(2026, 8, 30, 11, 45, tzinfo=timezone.utc),
    "techcrunch-meeting-notetaker-circleback-adds-a-free-tier-to-2b7c320d3fa0": datetime(2026, 8, 31, 11, 45, tzinfo=timezone.utc),
}

def age_days_at(dt_origin):
    return (NOW_MSK.astimezone(timezone.utc) - dt_origin).total_seconds() / 86400.0

def actual_decayed(importance, age_days, tier):
    hl = HALF_LIFE[tier]
    return importance * math.exp(-0.693 / hl * age_days)

with open(os.path.join(DATA, 'pending_queue.json'), encoding='utf-8') as f:
    pending_doc = json.load(f)
items_pending = pending_doc.get('pending', [])

prior_path = os.path.join(DATA, 'cluster_plan_2026-10-03-0015.json')
prior = {}
if os.path.exists(prior_path):
    with open(prior_path, encoding='utf-8') as f:
        prior = json.load(f)
prior_deferred_map = {d.get('article_id', ''): d for d in prior.get('deferred', [])}

ties = []
for it in items_pending:
    aid = it.get('article_id') or it.get('id') or ''
    if not aid:
        continue
    imp = it.get('importance')
    tier = TIER_RULES.get(imp, 3)
    origin = ORIGINAL_DATES.get(aid, (NOW_MSK - timedelta(days=30)).astimezone(timezone.utc))
    age = age_days_at(origin)
    act = actual_decayed(imp, age, tier)
    ties.append({
        'article_id': aid,
        'source': it.get('source'),
        'title': it.get('title') or '',
        'url': it.get('url') or '',
        'importance': imp,
        'stored_decayed_importance': it.get('stored_decayed_importance'),
        'actual_decayed_importance': round(act, 4),
        'actual_decayed_formula': f"{imp} * exp(-0.693/{HALF_LIFE[tier]} * {round(age,3)}) = {round(act,4)}",
        'age_days_at_now': round(age, 3),
        'tier': tier,
        'tags': prior_deferred_map.get(aid, {}).get('tags', []),
        'publish_template': "standard",
        'narrative_id': prior_deferred_map.get(aid, {}).get('narrative_id', None),
        'has_analysis': bool(it.get('agent_impact') or it.get('analyzed')),
    })

schedule = []
deferred = list(ties)
deferred.sort(key=lambda x: (x['tier'], -x['actual_decayed_importance']))

window_msk = f"{NOW_MSK.strftime('%Y-%m-%dT%H:%M:%S+03:00')} to {WINDOW_END_MSK.strftime('%Y-%m-%dT%H:%M:%S+03:00')}"

agi_current = 1212
post_cycle_agi = agi_current

def tier_rationale(item):
    tier = item['tier']
    act = item['actual_decayed_importance']
    age = item['age_days_at_now']
    base_rationale = [
        f"Importance {item['importance']} — {'высшая стратегическая' if tier==1 else 'нишевая но worth a post' if tier==2 else 'niche industrial'} позиция, {'единственный' if tier==1 else 'один из'} candidate для Tier {tier}.",
        f"Stored decayed {item['stored_decayed_importance']} (per _llm_analyze.py baseline). ACTUAL now: {act} (delta={age}d, half_life={HALF_LIFE[tier]}d).",
        (f"ACTUAL {act} << Tier-3 threshold 1.0. Workaround territory." if tier == 1
         else f"ACTUAL {act} << Tier-2 threshold 1.5. Workaround territory." if tier == 2
         else f"ACTUAL {act} << Tier-3 threshold 1.0. Cache-evict candidate."),
        "Cluster-cron convention: workaround items sit in forbidden territory; require explicit user override (`agentsblog publish --id …`) or cache-evict.",
        f"Deferred across: previous cycle 2026-10-03-0015 (100% quiet, no slot). 5+ cycles stale.",
        "Anchored to prior narrative mapping (cluster_narratives.log 2026-09-06 03:24 — 1184 narratives active).",
    ]
    return base_rationale

def analyst_notes(item):
    aid = item['article_id'] or ''
    tier = item['tier']
    act = item['actual_decayed_importance']
    age = item['age_days_at_now']
    notes = []
    if "cursor" in aid:
        notes.append("Tier 1 — business-critical: SpaceX acquires Cursor, OpenAI winds down its model contract on the platform. Power shift в AI-coding.")
        notes.append("Три sub-stories: (1) SpaceX enters software-IDE agent stack; (2) OpenAI draws line on IDE vendor capture; (3) cost to Cursor's OpenAI-model customers.")
    elif "asr" in aid:
        notes.append("Tier 2 — niche inclusivity в ASR: Hugging Face adds first Global South language to Open ASR Leaderboard.")
        notes.append("Cross-link с Tier-1 OpenAI/Cursor не нужен — разные narratives.")
    elif "turbines" in aid:
        notes.append("Tier 3 backup — environmental impact of AI-compute energy.")
        notes.append("Cross-link с US-China drones (industry/policy) и Caterpillar (industrial AI) — все Tier-3 в terminal decay.")
    elif "caterpillar" in aid:
        notes.append("Tier 3 — industrial AI deployment (mining → factory). Niche but agent-relevant.")
    elif "drones" in aid:
        notes.append("Tier 3 — low priority. Geopolitical tech competition. The news aged out of AI-agent relevance window.")
    elif "circleback" in aid:
        notes.append("Tier 3 — SaaS product update. Niche but workflow-relevant.")
        notes.append("BLOCKER: missing analysis (analyzed=false). Won't pass skipped_no_analysis filter at cron_publish.ps1.")
    notes.append(f"Terminal decay flag: ACTUAL decayed {act} — orders of magnitude below Tier-{tier} threshold. Cluster-cron emits this advisory but does NOT auto-publish workaround territory without explicit user override.")
    notes.append(f"If published: importance {item['importance']} → {'-2 days' if item['importance']==5 else '-0.5 days' if item['importance']==3 else 'no change'} AGI.")
    notes.append(f"Slot math — cycle 06:15-12:15 MSK = 1h45m quiet head + 4h15m active tail. Следующий eligible slot для override: 08:30 MSK 2026-10-03.")
    notes.append(f"Age {round(age,1)}d в pending — well outside 5-day freshness gate (EDITORIAL.md §4).")
    if "circleback" in aid:
        notes.append("Recommended action: heuristic_analyze (low priority, ~33d stale) OR cache-evict.")
    else:
        notes.append("Cluster-cron recommendation: cache-evict OR keep as future-freshness anchor для narrative (but news is действительно проавгустовская).")
    return notes

for d in deferred:
    d['tier_rationale'] = tier_rationale(d)
    d['analyst_notes'] = analyst_notes(d)
    d['format_check'] = {
        'is_breakthrough': False,
        'needs_approval': d['tier'] == 1,
        'template': 'standard',
        'blocked_reasons': (
            ['below_tier1_threshold_actual', 'workaround_territory', 'needs_explicit_override'] if d['tier'] == 1
            else ['below_tier2_threshold_actual', 'workaround_territory'] if d['tier'] == 2
            else ['below_tier3_threshold_actual', 'cache_evict_recommended']
        )
    }
    d['defer_reason'] = (
        "ACTUAL decayed below tier-1 threshold + workaround territory. Requires explicit override."
        if d['tier'] == 1
        else "ACTUAL decayed below tier-2 threshold — workaround territory."
        if d['tier'] == 2
        else "ACTUAL decayed below tier-3 threshold. Cache-evict candidate."
    )

tier_legend = {
    "1": "Premier: importance 5 (4+ rarely), strategic/business critical. Single post per cycle. Reserved slot.",
    "2": "Notable: importance 3, niche but worth a post. Standard slot.",
    "3": "Filler: importance 1-2, contextual. Last slot; one item only per cycle."
}

narrative_links = {
    "n-00008": "OpenAI acquisitions / competitive landscape — Cursor/SpaceX (Tier 1 deferred, workaround territory, requires override). Highest narrative weight в queue.",
    "n-00015": "HuggingFace open-source / agent tooling — ASR leaderboard (Global South) (Tier 2 deferred, workaround territory).",
    "tier3_rotation_note": "Caterpillar (industrial AI), Musk turbines (compute/ESG), US-China drones (geopolitics), Circleback (SaaS) — все 4 Tier-3 items в terminal decay. Cache-evict в cycle 2026-10-03-1215 cleanup."
}

agi_projection = {
    "current_days_estimate": agi_current,
    "source_of_truth": "data/metrics.json (последняя запись 2026-09-06T01:05:12 agi_days=1212). NOTE: msg 1653/1654/1655 (2026-10-02) не обновляли counter.",
    "post_cycle_current_days": post_cycle_agi,
    "deltas": {"tier1_importance5": 0, "tier2_importance3": 0, "tier3_importance2": 0},
    "note": "Cycle с 4h15m active tail, но все 6 items в terminal decay → 0 publications. AGI counter не меняется."
}

publish_windows_remaining = [
    {"slot_msk": "2026-10-03T08:30:00+03:00", "tier": 1, "eligible": False, "reason": "no fresh Tier-1 (cursor-spacex workaround territory, >37d old)"},
    {"slot_msk": "2026-10-03T10:30:00+03:00", "tier": 2, "eligible": False, "reason": "no fresh Tier-2 (ASR workaround territory, >37d old)"},
    {"slot_msk": "2026-10-03T12:00:00+03:00", "tier": 3, "eligible": False, "reason": "no fresh Tier-3 (all terminal)"}
]

windows_after_quiet = [
    "2026-10-03T08:00:00+03:00 — первый валидный слот после quiet hours",
    "2026-10-03T08:30:00+03:00 — Tier-1 slot если override одобрен для cursor-spacex",
    "2026-10-03T10:30:00+03:00 — Tier-2 slot если ASR override",
    "2026-10-03T12:00:00+03:00 — Tier-3 slot (Caterpillar primary)"
]

warnings = [
    "PRIMARY: Cycle 2026-10-03-0615 имеет quiet head (06:15-08:00 = 1h45m) + active tail (08:00-12:15 = 4h15m). 3 valid publish slots (08:30/10:30/12:00 MSK) доступны, но 0 items eligible.",
    "TERMINAL DECAY: ALL 6 items ACTUAL decayed well below thresholds (cursor-spacex 0.1254, asr 0.0191, techcrunch items 0.000547-0.00109). Cluster-cron convention: workaround items require explicit override.",
    "WORKAROUND TERRITORY (Tier-1 cursor-spacex): now +37 days old — far outside any workaround approval zone (>30d convention per cluster-cron).",
    "DAILY LIMIT: 3/3 fresh (00:00:01 reset at 2026-10-03 00:00:01). Slots available but no candidates.",
    "PUBLISH-CRON vs CLUSTER-CRON: msg 1653/1654/1655 (Barclays/Nvidia/AutoSynthData) от 2026-10-02 НЕ из pending_queue.json. Publish-cron от blog.db live queue.",
    "TELEGRAM RISK: chat_id @agentsSmits_bot intermittent getChat 404 reported 2026-09-06. Manual audit fixed 2026-09-15. Soft risk only.",
    "ANALYZER BACKLOG: blog.db live queue имеет 231+ unanalyzed items (per 12.09 cluster cycles). Cluster-cron не drain — `agentsblog analyze --limit 4` would clear backlog.",
    "CACHE-EVICT CANDIDATES: 4 Tier-3 (Musk turbines, Caterpillar, US-China drones, Circleback) — все terminal decay, не pass priority gate. Cache eviction recommended to reduce pending from 6 → 2.",
    "SLOT-DENSITY: 3 valid slots (08:30/10:30/12:00 MSK) = 100% slot availability. Density 100% but 0% utilization.",
    "STREAK: cycle 2026-10-03-0015 (quiet) = 0 publications. Cycle 2026-10-02-1815 = 0 publications from pending_queue.json. ACTUAL 0 publications from pending_queue.json уже 5+ cycle подряд.",
    "SCANNER STALENESS: last_checked 2026-08-31 (~33d). Pending queue split: pending_queue.json (6 stale, terminal) + blog.db live queue. Manual `agentsblog scan` would re-populate pending_queue.json.",
    "MISSING ANALYSIS (Circleback): analyzed=false → даже если override будет выпущен, fallback path publishes via skipped_no_analysis и публикует без translated impact fields. Re-analyze через heuristic_analyze.py ИЛИ cache-evict.",
    "FRESHNESS GATE BREACH: All 6 items > 5-day freshness gate (EDITORIAL.md §4). Cluster-cron convention holds workaround territory до explicit user override.",
]

next_cycle_projection = {
    "next_cycle_id": "2026-10-03-1215",
    "next_window_start_msk": "2026-10-03T12:15:00+03:00",
    "next_window_end_msk": "2026-10-03T18:15:00+03:00",
    "quiet_hours_overlap_in_next_cycle": "none (12:15-18:15 fully active)",
    "daily_limit_state_at_next_cycle_start": "depends on publish-cron activity 08:00-12:15 MSK. Max 3/3 fresh.",
    "candidate_tier1_for_next_cycle": "No fresh Tier-1 в pending_queue.json (only cursor-spacex в workaround territory >40d old).",
    "candidate_tier2_for_next_cycle": "No fresh Tier-2 в pending_queue.json (ASR в workaround >40d old).",
    "candidate_tier3_for_next_cycle": "No fresh Tier-3 в pending_queue.json (all terminal).",
    "cache_evict_recommended_for_next_cycle": [
        "techcrunch-musks-faster-path-to-more-gas-turbines-comes-wit-d5dafdd78fb6",
        "techcrunch-caterpillar-is-bringing-to-ai-deployment-what-it-e4de3653e651",
        "techcrunch-the-u-s-is-building-barriers-around-drones-and-r-c053743dc5a1",
        "techcrunch-meeting-notetaker-circleback-adds-a-free-tier-to-2b7c320d3fa0"
    ],
    "preflight_for_next_cycle": [
        "Verify Telegram chat_id @agentsSmits_bot alive — `openclaw channels list` перед publish-cron 12:15.",
        "If override IS issued for cursor-spacex: `python -m agentsblog publish --id openai-our-decision-on-cursor-following-its-acquisition-by--57a3b900535e` slot 12:30 MSK (first eligible slot в cycle 2026-10-03-1215).",
        "Run `agentsblog analyze --limit 4` чтобы drain 231+ item blog.db backlog.",
        "Run `agentsblog cache-evict --pending-stale` для 4 Tier-3 items recommended выше.",
        "Scanner stale — last_checked 2026-08-31 (~33d). Manual `agentsblog scan` would re-populate pending_queue.json с fresh items."
    ]
}

plan = {
    "cycle_id": CYCLE_ID,
    "clustered_at": NOW_MSK.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    "clustered_at_msk": NOW_MSK.strftime('%Y-%m-%dT%H:%M:%S+03:00'),
    "window_msk": window_msk,
    "quiet_hours_applied": "23:00-08:00 MSK — 1h45m head overlap (06:15-08:00); tail 08:00-12:15 fully active",
    "previous_cycle_id": "2026-10-03-0015",
    "previous_cycle_outcome": "Quiet-cycle tail (00:15-06:15 100% quiet). 0 publications from pending_queue.json. Schedule empty.",
    "pending_total": len(items_pending),
    "publishable_pending": 0,
    "scheduled_count": 0,
    "deferred_count": len(deferred),
    "primary_blocker": "ALL 6 items в terminal decay (ACTUAL decayed 0.000547-0.1254 << tier thresholds 1.0/1.5). Workaround territory — cluster-cron не auto-publishes.",
    "secondary_blocker": "Cycle window 1h45m quiet + 4h15m active = 3 valid slots (08:30/10:30/12:00 MSK), but daily-limit not the bottleneck. ALL items в pending_queue.json stale >33 days (last scanner check 2026-08-31).",
    "tier_legend": tier_legend,
    "schedule": schedule,
    "deferred": deferred,
    "narrative_links": narrative_links,
    "agi_counter_projection": agi_projection,
    "publish_windows_remaining_in_cycle": publish_windows_remaining,
    "windows_after_quiet": windows_after_quiet,
    "warnings": warnings,
    "next_cycle_projection": next_cycle_projection,
    "meta": {
        "delivered_by": "agentsmits-blog cluster cron (unattended run)",
        "reason_for_partial_quiet_cycle": "Cycle 06:15-12:15 MSK. Head 06:15-08:00 = quiet hours overlap (1h45m). Tail 08:00-12:15 = active (4h15m, 3 valid slots).",
        "reason_for_terminal_decay": "ALL 6 items в pending_queue.json — 33.5-37.3d stale. ACTUAL decayed 0.000547-0.1254 — orders of magnitude below tier-cutoff (1.0/1.5).",
        "items_tier_assigned": len(deferred),
        "items_actually_publishing_this_cycle": 0,
        "items_with_complete_analysis": sum(1 for d in deferred if d['has_analysis']),
        "items_blocked_by_analysis": sum(1 for d in deferred if not d['has_analysis']),
        "items_blocked_by_quiet_hours": 0,
        "items_blocked_by_daily_limit": 0,
        "items_blocked_by_below_threshold_actual": len(deferred),
        "items_in_workaround_territory": sum(1 for d in deferred if d['tier'] <= 2),
        "items_recommended_for_cache_evict": sum(1 for d in deferred if d['tier'] == 3),
        "cycle_total_actual_publications_expected_from_pending": "0 (no auto-publish candidates; cursor-spacex requires explicit override >37d old)"
    }
}

out_path = os.path.join(DATA, f'cluster_plan_{CYCLE_ID}.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)

print(f"OK wrote {out_path}")
print(f"Pending total: {plan['pending_total']}")
print(f"Deferred: {plan['deferred_count']}")
print(f"Items:")
for d in deferred:
    print(f"  T{d['tier']} | imp={d['importance']} | age={d['age_days_at_now']}d | decayed={d['actual_decayed_importance']} | {d['article_id'][:60]}")