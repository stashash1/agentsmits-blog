# Cluster analyst notes — cycle 2026-10-14-1815

_Cluster-cron advisory. Cycle window: 2026-10-14 18:15 → 2026-10-15 00:15 MSK._
_Quiet hours (23:00-08:00 MSK) PARTIALLY overlap: ACTIVE-HEAD 18:15-23:00 (4h45m) + QUIET-TAIL 23:00-00:15 (1h15m). T1 20:30 ACTIVE (passed at cron run 20:58), T2 22:30 ACTIVE (1h32m from cron, actionable), T3 23:55 BLOCKED_BY_QUIET._
_Late cron execution: cluster-cron fired 20:58 MSK, 2h43m into cycle. T1 20:30 already passed. Decay re-computed against actual cron run time (Δ +62h43m from prev cycle 2026-10-12-0615 06:15 MSK)._

## Headline

- **Scheduled: 0 items.** All 6 pending items remain in terminal decay (44.75-47.75 days old, ACTUAL decayed 0.0000498-0.0442, orders of magnitude below tier cutoffs) AND breach the 5-day freshness gate (8.95-9.55x). Cluster-cron domain has zero auto-publish candidates this cycle.
- **T1 20:30 MSK — PASSED** (28 min before cron run 20:58). ACTIVE window structurally (30 min after Telegram flake window 18:00-20:00 ended), but no auto-publish candidate.
- **T2 22:30 MSK — ACTIVE** (4h15m into cycle, 1h32m from cron run 20:58, 2h after T1, safe Telegram window 2h30m after flake window ended). No auto-publish candidate.
- **T3 23:55 MSK — BLOCKED_BY_QUIET** (5h40m into cycle, 1h25m after T2, in quiet hours 23:00-08:00). All 4 T3 candidates in cache-evict territory.
- **41-cycle stale streak** for pending_queue.json auto-publish (31 from prev cycle 2026-10-12-0615 + 10 cycles this run, including 9 cycles not in data/ between 2026-10-12-1215 and 2026-10-14-1215).
- **Cycle structure:** HEAD-ACTIVE — cycle starts in active hours (18:15-23:00) but tail overlaps quiet. Structurally identical to 2026-10-11-1815 (same quiet-head/tail pattern, but cron ran on-time that cycle). This is the second HEAD-ACTIVE cycle observed.

## Pending items — tier assignment

- **T1** — openai-our-decision-on-cursor-following-its-acquisition-by--57a3b900535e | OpenAI | importance 5 | ACTUAL 0.0442 (4.42% of T1 threshold 1.0) | Workaround territory, freshness breach 47.75d, has analysis, narrative n-00008
- **T2** — huggingface-open-asr-leaderboard-global-south | HuggingFace | importance 3 | ACTUAL 0.00404 (0.269% of T2 threshold 1.5) | Workaround territory, freshness breach 47.75d, has analysis, narrative n-00015
- **T3** — techcrunch-musks-faster-path-to-more-gas-turbines-comes-wit-d5dafdd78fb6 | TechCrunch AI | importance 2 | ACTUAL 0.0000514 (0.005% of T3 threshold 1.0) | Cache-evict, freshness breach 45.75d, has analysis
- **T3** — techcrunch-caterpillar-is-bringing-to-ai-deployment-what-it-e4de3653e651 | TechCrunch AI | importance 2 | ACTUAL 0.0000514 | Cache-evict, freshness breach 45.75d, has analysis
- **T3** — techcrunch-the-u-s-is-building-barriers-around-drones-and-r-c053743dc5a1 | TechCrunch AI | importance 2 | ACTUAL 0.0000645 (0.006%) | Cache-evict, freshness breach 44.75d, has analysis
- **T3** — techcrunch-meeting-notetaker-circleback-adds-a-free-tier-to-2b7c320d3fa0 | TechCrunch AI | importance 2 | ACTUAL 0.0000645 | Cache-evict, freshness breach 44.75d, **missing analysis**

All 6 items: stored baseline from 2026-08-30/31 cluster run. ACTUAL decayed re-computed analytically with +62h43m offset from cycle 2026-10-12-0615 (decay formulas: T1 `5 * exp(-0.693/7 * 47.749) = 0.0442`, T2 `3 * exp(-0.693/5 * 47.749) = 0.00404`, T3 `2 * exp(-0.693/3 * {44.749, 45.749}) = 0.0000498-0.0000645`). Δ from prev cycle: T1 -22.9%, T2 -29.9%, T3 -44.8% to -45.8% (faster decay for shorter half-life items).

## Tier-1 deep-dive (cursor-spacex)

- **Strategic weight**: importance 5 (premier, business-critical). Power shift в AI-coding: SpaceX acquires Cursor, OpenAI winds down its model contract.
- **Decay math**: `5 * exp(-0.693/7 * 47.749) = 0.0442`. 4.42% of T1 threshold 1.0. Below cutoff by 95.6%.
- **Workaround territory**: ACTUAL << threshold, item is 47.75 days old (9.55× the 5-day freshness gate). Cluster-cron does NOT auto-publish.
- **T1 20:30 MSK is PASSED** at cron run 20:58 (28 min after slot). Override window for this cycle = CLOSED. Next viable T1 = 2026-10-15-0615 cycle T1 08:30 MSK (after FULL QUIET 2026-10-15-0015).
- **Channel silence (cluster-cron domain)**: last cluster-cron publish was msg 1671 at 2026-10-08 12:55:04 MSK. At cron run 20:58 MSK 2026-10-14 = ~152h 3m of cluster-cron silence. (Publish-cron has been active — most recent overall channel publish is msg 1678 at 2026-10-10 15:25 MSK, ~101h 33m of overall silence.)
- **AGI impact if published**: importance 5 → -2 days AGI (current_days 30 → 28).
- **Recommendation**: if user wants to break the cluster-cron silence, cursor-spacex is the strongest viable T1 (despite being 47.75d old). Override target = 2026-10-15-0615 T1 08:30 MSK (next actionable T1 slot, ~11h32m from cron run).

## Tier-2 deep-dive (ASR)

- **Strategic weight**: importance 3 (niche but worth a post). Hugging Face adds first Global South language to Open ASR Leaderboard.
- **Decay math**: `3 * exp(-0.693/5 * 47.749) = 0.00404`. 0.269% of T2 threshold 1.5. Below cutoff by 99.7%.
- **Workaround territory**: ACTUAL << threshold, item is 47.75 days old.
- **T2 22:30 MSK is ACTIVE** in this cycle (1h32m from cron run 20:58, 2h after T1, safe Telegram window 2h30m after flake window ended).
- **Pairing**: T1 passed without publication. ASR is now standalone viable at T2 22:30 MSK (1h32m override window from 20:58 to 22:30). If user wants single-tier cycle, ASR is the most defensible pick.
- **AGI impact if published**: importance 3 → -0.5 days AGI (current_days 30 → 29.5).
- **Recommendation**: pure inclusion beat; weaker story than cursor-spacex but pairing-quality is acceptable. Override window is tight (1h32m).

## Tier-3 batch (4 items, all cache-evict candidates)

- All 4 T3 items have ACTUAL decayed 0.0000498-0.0000645 (0.005-0.006% of T3 threshold 1.0). All 44.75-45.75 days old.
- T3 slot 23:55 MSK is BLOCKED_BY_QUIET in this cycle, but no viable T3 candidate in pending_queue.json anyway.
- **Recommendation**: batch cache-evict. Run `agentsblog cache-evict --pending-stale` to drop all 4 from pending_queue.json. Would reduce pending 6 → 2, leaving cursor-spacex + ASR as explicit override territory.
- Circleback is missing analysis (`has_analysis=false`). Workarounds: `_llm_analyze.py --id <id>` (Ollama qwen3:8b) or `heuristic_analyze.py` as drain. But age 44.75d → re-analyzing a 44-day-old article is wasted compute; cache-evict is the lighter path.

## Slot schedule

- **T1** | 2026-10-14 20:30 | Tier 1 | PASSED at cron run 20:58 | none (workaround) | Telegram risk NONE (30 min after flake window 18:00-20:00 ended; though already passed)
- **T2** | 2026-10-14 22:30 | Tier 2 | ACTIVE (1h32m from cron) | none (workaround) | Telegram risk NONE (2h30m after flake window ended, 1h25m before quiet gate 23:00)
- **T3** | 2026-10-14 23:55 | Tier 3 | BLOCKED_BY_QUIET | n/a | Telegram risk NONE (quiet hours protect)

**Daily limit**: 0/3 used at cycle start. T2 remaining ACTIVE slot eligible if user issues explicit override. T1 PASSED, T3 BLOCKED.

## Channel state

- **Last cluster-cron publish**: 2026-10-08 12:55:04 MSK, msg_id 1671 (Google agentic Gemini for business).
- **Last publish-cron publish (overall)**: 2026-10-10 15:25 MSK, msg_id 1678 (Как ML Intern помог создать 0.8B prompt rewriter).
- **Cluster-cron silence at cron run 20:58 MSK**: ~152h 3m.
- **Cluster-cron silence at T1 20:30 MSK**: ~151h 35m (T1 already passed).
- **Cluster-cron silence at T2 22:30 MSK** (if published): ~153h 35m.
- **Overall channel silence at cron run 20:58 MSK**: ~101h 33m.
- **Cycles 2026-10-12-1215 through 2026-10-14-1215** (9 cycles between) are NOT in data/cluster_plan_*.json (likely skipped, FULL QUIET, or zero-candidate). This 1815 cycle picks up after 0615, treating the 9 intermediate cycles as +9 to stale streak.

## Cycle-specific observations

- **HEAD-ACTIVE pattern**: cycle 18:15-00:15 starts in active hours (18:15-23:00) with 1 actionable slot remaining (T2 22:30) + 1 passed (T1 20:30) + 1 blocked (T3 23:55). Structurally identical to 2026-10-11-1815 (same quiet-head/tail pattern, but cron ran on-time that cycle and produced cluster_plan with 0 scheduled).
- **Telegram residual flake window 18:00-20:00 MSK**: T1 20:30 fires 30 min AFTER window end (safe, though passed). T2 22:30 well clear. Telegram risk NONE for remaining slots.
- **publish-cron (blog.db) is unaffected** by quiet hours for the cluster domain; it operates on its own slot schedule and has been publishing live items.
- **Cluster-cron runs without live exec**: data carried from cycle 2026-10-12-0615 with decay re-computed analytically (+62h43m offset, from 06:15 MSK 2026-10-12 to 20:58 MSK 2026-10-14).
- **Freshness gate breach**: all 6 items 8.95-9.55× the 5-day freshness gate. Stale scan since 2026-08-31T13:06:07Z (~44.2d ago).
- **AGI counter state**: current_days 30 (per pending_queue.json.agi_counter; unchanged from prior cycles — no publication events). Will move to 28 (T1) / 29.5 (T2) / 30 (T3) if published.

## Recommendation (autopilot, advisory-only)

1. **Cache-evict T3 batch** (4 items: musk-gas, caterpillar, drones, circleback). Reduces pending 6 → 2. Circleback also has MISSING_ANALYSIS — hard evict.
2. **Hold T1+T2 in override territory** (cursor-spacex + ASR). User can publish via `agentsblog publish --id <id>` before slot times.
   - **T1 (cursor-spacex)**: this cycle T1 PASSED. Next viable T1 = 2026-10-15-0615 T1 08:30 MSK (~11h32m from cron run).
   - **T2 (ASR)**: this cycle T2 ACTIVE, 1h32m override window from 20:58 to 22:30 MSK. Tight but actionable.
3. **Wait for fresh scanner data** to land before next cycle. 41-cycle stale streak is terminal — cluster-cron domain is advisory-only until scanner runs.
4. **publish-cron continues independently** via blog.db — no action needed there.
5. **Next cycle 2026-10-15-0015 is FULL QUIET** (00:15-06:15 MSK entirely in quiet hours 23:00-08:00). No cluster-cron publications possible. First actionable cycle = 2026-10-15-0615 (TAIL-ACTIVE).

## Files written

- `data/cluster_plan_2026-10-14-1815.json` — full cluster plan with tier assignments, slot map, deferred list, decay re-computation, streaks, cycle structure comparison, next cycle preview.
- `data/analyst_notes_2026-10-14_18.md` — this file.

## Cluster-cron domain status

- **Pending queue**: 6 items, all in terminal decay.
- **Stale streak**: 41 cycles.
- **Auto-publish this cycle**: 0.
- **Override territory available**: yes (T2 22:30 MSK viable, 1h32m window; T1 deferred to next cycle 2026-10-15-0615).
- **Cluster-cron domain**: advisory-only, awaiting fresh scanner data.
- **publish-cron domain**: operating normally on blog.db.
