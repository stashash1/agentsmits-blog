# Cluster analyst notes — cycle 2026-10-10-0615

_Cluster-cron advisory. Cycle window: 2026-10-10 06:15 → 2026-10-10 12:15 MSK._
_Quiet hours (23:00-08:00 MSK) overlap 06:15-08:00. HEAD-QUIET (1h45m) + ACTIVE-TAIL (4h15m). 3 ACTIVE slots in tail._

## Headline

- **Scheduled: 0 items.** All 6 pending items are in terminal decay (39.46–42.46 days old, ACTUAL decayed 0.000174–0.0747, orders of magnitude below tier cutoffs) AND breach the 5-day freshness gate. Cluster-cron domain has zero auto-publish candidates this cycle.
- **T1 08:30 MSK — ACTIVE** (30 min into ACTIVE tail 08:00-12:15, just past quiet-head). No auto-publish candidate.
- **T2 10:30 MSK — ACTIVE** (post-morning-peak, safe Telegram window per MEMORY.md). No auto-publish candidate.
- **T3 12:00 MSK — ACTIVE** (15 min before cycle boundary 12:15 MSK). No auto-publish candidate.
- **25-cycle stale streak** for pending_queue.json auto-publish (24 from prev cycle 2026-10-09-1815 + 1 this run).

## Pending items — tier assignment

| Tier | Item | Source | Importance | ACTUAL decayed | Threshold | Status |
|---|---|---|---|---|---|---|
| T1 | openai-our-decision-on-cursor-following-its-acquisition-by--57a3b900535e | OpenAI | 5 | 0.0747 | 1.0 | Workaround, freshness breach 42.5d, has analysis, narrative n-00008 |
| T2 | huggingface-open-asr-leaderboard-global-south | HuggingFace | 3 | 0.0083 | 1.5 | Workaround, freshness breach 42.5d, has analysis, narrative n-00015 |
| T3 | techcrunch-musks-faster-path-to-more-gas-turbines-comes-wit-d5dafdd78fb6 | TechCrunch AI | 2 | 0.000174 | 1.0 | Cache-evict, freshness breach 40.5d, has analysis |
| T3 | techcrunch-caterpillar-is-bringing-to-ai-deployment-what-it-e4de3653e651 | TechCrunch AI | 2 | 0.000174 | 1.0 | Cache-evict, freshness breach 40.5d, has analysis |
| T3 | techcrunch-the-u-s-is-building-barriers-around-drones-and-r-c053743dc5a1 | TechCrunch AI | 2 | 0.000218 | 1.0 | Cache-evict, freshness breach 39.5d, has analysis |
| T3 | techcrunch-meeting-notetaker-circleback-adds-a-free-tier-to-2b7c320d3fa0 | TechCrunch AI | 2 | 0.000218 | 1.0 | Cache-evict, freshness breach 39.5d, **missing analysis** |

All 6 items: stored baseline from 2026-08-30 cluster run. ACTUAL decayed re-computed analytically with +12h offset from cycle 2026-10-09-1815.

## Tier-1 deep-dive (cursor-spacex)

- **Strategic weight**: importance 5 (premier, business-critical). Power shift в AI-coding: SpaceX acquires Cursor, OpenAI winds down its model contract.
- **Decay math**: `5 * exp(-0.693/7 * 42.46) = 0.0747`. 7.47% of T1 threshold 1.0. Below cutoff by 92.53%.
- **Workaround territory**: ACTUAL << threshold, item is 42.5 days old (8.5× the 5-day freshness gate). Cluster-cron does NOT auto-publish.
- **T1 08:30 MSK is ACTIVE** in this cycle. Override window 08:00-08:30 (30 min cushion) or 08:30-strict.
- **Channel silence**: last Telegram publish was 2026-10-08 12:55:04 MSK (msg_id 1671, Google agentic Gemini for business). At T1 08:30 MSK = ~43h35m of silence. Override path is the cleanest way to break the silence.
- **AGI impact if published**: importance 5 → -2 days AGI.
- **Recommendation**: if user wants to break the silence, cursor-spacex is the strongest viable T1 (despite being 42.5d old). Alternative: cache-evict and wait for fresh scan.

## Tier-2 deep-dive (ASR)

- **Strategic weight**: importance 3 (niche but worth a post). Hugging Face adds first Global South language to Open ASR Leaderboard.
- **Decay math**: `3 * exp(-0.693/5 * 42.46) = 0.0083`. 0.55% of T2 threshold 1.5. Below cutoff by 99.45%.
- **Workaround territory**: ACTUAL << threshold, item is 42.5 days old.
- **T2 10:30 MSK is ACTIVE** in this cycle (post-morning-peak, safe Telegram window). 2h override cushion from 08:30 to 10:30.
- **Pairing**: if cursor-spacex IS published at T1 08:30 MSK, ASR remains viable at T2 10:30 MSK (2h interval between T1 and T2 — within minimum 180-min rule, no AGI-counter coupling).
- **AGI impact if published**: importance 3 → -0.5 days AGI.
- **Recommendation**: pure inclusion beat; weaker story than cursor-spacex but pairing-quality is acceptable.

## Tier-3 batch (4 items, all cache-evict candidates)

- All 4 T3 items have ACTUAL decayed 0.000174-0.000218 (≪ 0.025% of T3 threshold 1.0). All 39.46-40.46 days old.
- T3 slot 12:00 MSK IS ACTIVE in this cycle (15 min before cycle boundary), but no viable T3 candidate in pending_queue.json.
- **Recommendation**: batch cache-evict. Run `agentsblog cache-evict --pending-stale` to drop all 4 from pending_queue.json. Would reduce pending 6 → 2, leaving cursor-spacex + ASR as explicit override territory.
- Circleback is missing analysis (`analyzed=false`). Workarounds: `_llm_analyze.py --id <id>` (Ollama qwen3:8b) or `heuristic_analyze.py` as drain. But age 39.46d — re-analyzing a 39-day-old article is wasted compute; cache-evict is the lighter path.

## Slot schedule

| Slot | Time MSK | Tier | Status | Candidate | Telegram risk |
|---|---|---|---|---|---|
| T1 | 2026-10-10 08:30 | 1 | ACTIVE | none (workaround) | LOW (morning peak 08:00-10:00 = volume, not technical flake per MEMORY.md) |
| T2 | 2026-10-10 10:30 | 2 | ACTIVE | none (workaround) | NONE (post-peak) |
| T3 | 2026-10-10 12:00 | 3 | ACTIVE | none (workaround) | NONE (cycle boundary 15 min) |

**Daily limit**: 0/3 used at cycle start. T1, T2, T3 all eligible if queue has publishable candidates AND user issues explicit override.

## Channel state

- **Last publish**: 2026-10-08 12:55:04 MSK, msg_id 1671 (Google agentic Gemini for business).
- **Silence at cycle start 06:15 MSK**: ~41h 20m.
- **Silence at T1 08:30 MSK**: ~43h 35m.
- **Silence at T2 10:30 MSK**: ~45h 35m.
- **Silence at T3 12:00 MSK**: ~47h 05m.
- **Override path** is the cleanest way to break the silence. Cursor-spacex is the strongest available T1 (despite being 42.5d old).

## Data source duality

- **Cluster-cron domain** (this plan): pending_queue.json — 6 items, terminal-stale (last scanner 2026-08-31, 40.0d ago).
- **Publish-cron domain** (separate cron): blog.db — live items. Publish-cron operates normally in this cycle's ACTIVE tail (08:00-12:15 MSK). This plan does not cover blog.db publications.
- Manual `agentsblog scan` would re-populate pending_queue.json with fresh items when shell access is restored. Until then, cluster-cron is advisory-only.

## Next ACTIVE cycle

- **2026-10-10-1215** is the next cycle: FULLY ACTIVE (12:15-18:15, no quiet overlap). Slots: T1 14:30, T2 16:30, T3 17:55 MSK. T3 17:55 fires 5 min BEFORE Telegram flake window 18:00-20:00 — safe with cushion.
- Channel-silence projection: if no overrides fire in cycle 0615 AND no publish-cron fires from blog.db, expect ~46h+ of channel silence at next cycle start 12:15 MSK. Override path is the cleanest break.

## Recommendation priority

1. **If user wants to break channel silence**: override cursor-spacex at T1 08:30 MSK (importance 5, strongest viable item, AGI -2 days).
2. **If user wants max throughput**: override cursor-spacex (T1 08:30) + ASR (T2 10:30) = 2/3 daily limit used, AGI -2.5 days total. Both items in workaround territory but cleanest pair.
3. **If user wants clean state**: `agentsblog cache-evict --pending-stale` to drop 4 T3 items. Then `agentsblog scan` to repopulate from live sources. Then re-run cluster next cycle with fresh data.
4. **If user does nothing**: 0 publications this cycle. Channel silence extends. Pending queue continues to decay. No AGI counter change.

## Cross-narrative weight

- **n-00008** (open-weight M&A / Cursor ecosystem): holds cursor-spacex (T1). Cross-link to recent techcrunch open-weight acquisition article (published 2026-08-28, msg_id 1522). Story is internally consistent — Cursor is the new prize.
- **n-00015** (ASR/open-benchmark inclusivity): holds ASR (T2). Standalone — no other pending items in this narrative.
- T3 items have no narrative anchors. Pure industry/policy beats — each its own isolated thread.

## Files referenced

- `data/cluster_plan_2026-10-10-0615.json` — full machine-readable plan (this cycle)
- `data/cluster_plan_2026-10-09-1815.json` — previous cycle (decay baseline, TAIL-QUIET)
- `data/pending_queue.json` — 6 items, terminal-stale
- `data/narratives.json` — n-00008, n-00015 active
- `data/metrics.json` — AGI counter ~1212
- `data/sent_messages.json` — last publish msg_id 1671
- `MEMORY.md` — Telegram residual flake window 18:00-20:00 MSK
- `EDITORIAL.md` — quiet hours 23:00-08:00 MSK, freshness gate 5d, daily limit 3

_Delivered by agentsmits-blog cluster cron. Unattended run. No live exec access — data carried from cycle 2026-10-09-1815 with decay re-computed analytically (+12h offset)._
