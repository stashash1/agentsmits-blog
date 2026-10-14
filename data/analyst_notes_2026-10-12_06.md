# Cluster analyst notes — cycle 2026-10-12-0615

_Cluster-cron advisory. Cycle window: 2026-10-12 06:15 → 2026-10-12 12:15 MSK._
_Quiet hours (23:00-08:00 MSK) PARTIALLY overlap: QUIET-HEAD 06:15-08:00 (1h45m) + ACTIVE-TAIL 08:00-12:15 (4h15m). T1 08:30, T2 10:30, T3 11:55 all ACTIVE._

## Headline

- **Scheduled: 0 items.** All 6 pending items remain in terminal decay (42.14-45.14 days old, ACTUAL decayed 0.0000932-0.0573, orders of magnitude below tier cutoffs) AND breach the 5-day freshness gate (8.43-9.03x). Cluster-cron domain has zero auto-publish candidates this cycle.
- **T1 08:30 MSK — ACTIVE** (2h15m into cycle, 30 min AFTER quiet gate ends 08:00 MSK). No auto-publish candidate.
- **T2 10:30 MSK — ACTIVE** (4h15m into cycle, 2h after T1, safe Telegram window). No auto-publish candidate.
- **T3 11:55 MSK — ACTIVE** (5h40m into cycle, 1h25m after T2, 20 min before cycle end, safe Telegram window). No auto-publish candidate.
- **31-cycle stale streak** for pending_queue.json auto-publish (30 from prev cycle 2026-10-11-1815 + 1 this run).
- **Cycle structure (NEW):** TAIL-ACTIVE — cycle starts inside quiet hours (06:15-08:00) but all 3 publish slots fall in ACTIVE-TAIL (08:00-12:15). This is structurally different from prev 4 cycles:
  - 2026-10-11-0015: FULL QUIET (0 ACTIVE)
  - 2026-10-11-1215: FULL ACTIVE (3 ACTIVE)
  - 2026-10-11-1815: HEAD-ACTIVE (2 ACTIVE + 1 BLOCKED_BY_QUIET)
  - 2026-10-12-0615 (THIS): TAIL-ACTIVE (3 ACTIVE) ← new pattern

## Pending items — tier assignment

- **T1** — openai-our-decision-on-cursor-following-its-acquisition-by--57a3b900535e | OpenAI | importance 5 | ACTUAL 0.0573 (5.73% of T1 threshold 1.0) | Workaround territory, freshness breach 45.14d, has analysis, narrative n-00008
- **T2** — huggingface-open-asr-leaderboard-global-south | HuggingFace | importance 3 | ACTUAL 0.00576 (0.384% of T2 threshold 1.5) | Workaround territory, freshness breach 45.14d, has analysis, narrative n-00015
- **T3** — techcrunch-musks-faster-path-to-more-gas-turbines-comes-wit-d5dafdd78fb6 | TechCrunch AI | importance 2 | ACTUAL 0.0000932 (0.009% of T3 threshold 1.0) | Cache-evict, freshness breach 43.14d, has analysis
- **T3** — techcrunch-caterpillar-is-bringing-to-ai-deployment-what-it-e4de3653e651 | TechCrunch AI | importance 2 | ACTUAL 0.0000932 | Cache-evict, freshness breach 43.14d, has analysis
- **T3** — techcrunch-the-u-s-is-building-barriers-around-drones-and-r-c053743dc5a1 | TechCrunch AI | importance 2 | ACTUAL 0.000119 (0.012%) | Cache-evict, freshness breach 42.14d, has analysis
- **T3** — techcrunch-meeting-notetaker-circleback-adds-a-free-tier-to-2b7c320d3fa0 | TechCrunch AI | importance 2 | ACTUAL 0.000119 | Cache-evict, freshness breach 42.14d, **missing analysis**

All 6 items: stored baseline from 2026-08-30/31 cluster run. ACTUAL decayed re-computed analytically with +10h54m offset from cycle 2026-10-11-1815 (decay formulas: T1 `5 * exp(-0.693/7 * 45.135) = 0.0573`, T2 `3 * exp(-0.693/5 * 45.135) = 0.00576`, T3 `2 * exp(-0.693/3 * {42.135, 43.135}) = 0.0000932-0.000119`).

## Tier-1 deep-dive (cursor-spacex)

- **Strategic weight**: importance 5 (premier, business-critical). Power shift в AI-coding: SpaceX acquires Cursor, OpenAI winds down its model contract.
- **Decay math**: `5 * exp(-0.693/7 * 45.135) = 0.0573`. 5.73% of T1 threshold 1.0. Below cutoff by 94.3%.
- **Workaround territory**: ACTUAL << threshold, item is 45.14 days old (9.03× the 5-day freshness gate). Cluster-cron does NOT auto-publish.
- **T1 08:30 MSK is ACTIVE** in this cycle. Override window 06:15-08:30 (2h15m cushion) or 08:30-strict. Note: cycle start at 06:15 is INSIDE quiet hours, but T1 slot at 08:30 is 30 min after quiet gate ends, safe window.
- **Channel silence (cluster-cron domain)**: last cluster-cron publish was msg 1671 at 2026-10-08 12:55:04 MSK. At T1 08:30 MSK = ~91h 35m of cluster-cron silence. (Publish-cron has been active — most recent overall channel publish is msg 1678 at 2026-10-10 15:25 MSK, ~41h 5m of overall silence.)
- **AGI impact if published**: importance 5 → -2 days AGI (~1212 → 1210).
- **Recommendation**: if user wants to break the cluster-cron silence, cursor-spacex is the strongest viable T1 (despite being 45.14d old). Alternative: cache-evict and wait for fresh scan.

## Tier-2 deep-dive (ASR)

- **Strategic weight**: importance 3 (niche but worth a post). Hugging Face adds first Global South language to Open ASR Leaderboard.
- **Decay math**: `3 * exp(-0.693/5 * 45.135) = 0.00576`. 0.384% of T2 threshold 1.5. Below cutoff by 99.6%.
- **Workaround territory**: ACTUAL << threshold, item is 45.14 days old.
- **T2 10:30 MSK is ACTIVE** in this cycle (2h after T1, safe Telegram window). 2h override cushion from 08:30 to 10:30.
- **Pairing**: if cursor-spacex IS published at T1 08:30 MSK, ASR remains viable at T2 10:30 MSK (2h interval between T1 and T2 — within minimum 180-min rule, no AGI-counter coupling).
- **AGI impact if published**: importance 3 → -0.5 days AGI.
- **Recommendation**: pure inclusion beat; weaker story than cursor-spacex but pairing-quality is acceptable.

## Tier-3 batch (4 items, all cache-evict candidates)

- All 4 T3 items have ACTUAL decayed 0.0000932-0.000119 (0.009-0.012% of T3 threshold 1.0). All 42.14-43.14 days old.
- T3 slot 11:55 MSK is ACTIVE in this cycle, but no viable T3 candidate in pending_queue.json.
- **Recommendation**: batch cache-evict. Run `agentsblog cache-evict --pending-stale` to drop all 4 from pending_queue.json. Would reduce pending 6 → 2, leaving cursor-spacex + ASR as explicit override territory.
- Circleback is missing analysis (`analyzed=false`). Workarounds: `_llm_analyze.py --id <id>` (Ollama qwen3:8b) or `heuristic_analyze.py` as drain. But age 42.14d → re-analyzing a 42-day-old article is wasted compute; cache-evict is the lighter path.

## Slot schedule

- **T1** | 2026-10-12 08:30 | Tier 1 | ACTIVE | none (workaround) | Telegram risk NONE (well before flake window 18:00-20:00; 30 min after quiet end 08:00)
- **T2** | 2026-10-12 10:30 | Tier 2 | ACTIVE | none (workaround) | Telegram risk NONE (well clear of flake window)
- **T3** | 2026-10-12 11:55 | Tier 3 | ACTIVE | none (workaround) | Telegram risk NONE (20 min before cycle end, well clear of flake window)

**Daily limit**: 0/3 used at cycle start. T1, T2, T3 all eligible if queue has publishable candidates AND user issues explicit override. This is the first cycle in 4 where all 3 slots are ACTIVE (TAIL-ACTIVE pattern).

## Channel state

- **Last cluster-cron publish**: 2026-10-08 12:55:04 MSK, msg_id 1671 (Google agentic Gemini for business).
- **Last publish-cron publish (overall)**: 2026-10-10 15:25 MSK, msg_id 1678 (Как ML Intern помог создать 0.8B prompt rewriter).
- **Cluster-cron silence at cycle start 06:15 MSK**: ~89h 20m.
- **Cluster-cron silence at T1 08:30 MSK**: ~91h 35m.
- **Cluster-cron silence at T2 10:30 MSK**: ~93h 35m.
- **Cluster-cron silence at T3 11:55 MSK**: ~95h 0m.
- **Overall channel silence at cycle start 06:15 MSK**: ~14h 50m.
- **Cycle 2026-10-12-0015** is NOT in data/ (likely skipped or 0 ACTIVE due to FULL QUIET). This 0615 cycle picks up after 1815.

## Cycle-specific observations

- **TAIL-ACTIVE pattern (NEW)**: cycle 06:15-12:15 starts inside quiet hours (06:15-08:00) but all 3 publish slots land in ACTIVE-TAIL (08:00-12:15). Structurally different from 2026-10-11-0015 (FULL QUIET) and 2026-10-11-1815 (HEAD-ACTIVE).
- **Telegram residual flake window 18:00-20:00 MSK**: not relevant (all 3 slots fire 08:30-11:55, well before window opens). Telegram risk NONE.
- **publish-cron (blog.db) is unaffected** by quiet hours for the cluster domain; it operates on its own slot schedule and has been publishing live items.
- **Cluster-cron runs without live exec**: data carried from cycle 2026-10-11-1815 with decay re-computed analytically (+10h54m offset, from 19:21 MSK 2026-10-11 to 06:15 MSK 2026-10-12).
- **Freshness gate breach**: all 6 items 8.43-9.03× the 5-day freshness gate. Stale scan since 2026-08-31T13:06:07Z (~41.7d ago).

## Recommendation (autopilot, advisory-only)

1. **Cache-evict T3 batch** (4 items: musk-gas, caterpillar, drones, circleback). Reduces pending 6 → 2. Circleback also has MISSING_ANALYSIS — hard evict.
2. **Hold T1+T2 in override territory** (cursor-spacex + ASR). User can publish via `agentsblog publish --id <id>` before T1/T2 slot times.
3. **Wait for fresh scanner data** to land before next cycle. 31-cycle stale streak is terminal — cluster-cron domain is advisory-only until scanner runs.
4. **publish-cron continues independently** via blog.db — no action needed there.

## Files written

- `data/cluster_plan_2026-10-12-0615.json` — full cluster plan with tier assignments, slot map, deferred list, decay re-computation, streaks, cycle structure comparison, next cycle preview.
- `data/analyst_notes_2026-10-12_06.md` — this file.

## Cluster-cron domain status

- **Pending queue**: 6 items, all in terminal decay.
- **Stale streak**: 31 cycles.
- **Auto-publish this cycle**: 0.
- **Override territory available**: yes (3 ACTIVE slots, T1/T2 viable via explicit override).
- **Cluster-cron domain**: advisory-only, awaiting fresh scanner data.
- **publish-cron domain**: operating normally on blog.db.
