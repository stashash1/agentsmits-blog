// Build cluster plan for next 6h cycle
// Inputs: data/pending_queue.json
// Output: _diag/cluster_plan.json + summary to stdout
const fs = require('fs');
const path = require('path');

const ROOT = process.cwd();
const d = JSON.parse(fs.readFileSync(path.join(ROOT, 'data', 'pending_queue.json'), 'utf8'));
const pend = d.pending || [];
const pubIds = new Set((d.published || []).map(p => p.id));
const fresh = pend.filter(p => !pubIds.has(p.id));

// Already pre-tagged by ai_impact.tier (1/2/3). Respect it but assign cluster labels.
const items = fresh.map(p => {
  const ai = p.ai_impact || {};
  const tier = ai.tier || 3;
  return {
    id: p.id,
    source: p.source,
    title: p.title,
    url: p.url,
    date: p.date,
    importance: p.importance,
    decayed_importance: p.decayed_importance ?? null,
    tier_pre: tier,
    cluster: null, // filled below
    final_tier: tier,
    slot_msk: null,
    analyst_notes: [],
    defer: false,
    defer_reason: null,
  };
});

// Cluster assignment by topic proximity
const clusterOf = (id) => {
  if (id.startsWith('openai-our-decision-on-cursor')) return 'A_strategy';
  if (id.includes('musks-faster-path-to-more-gas-turbines')) return 'A_strategy'; // Musk/SpaceX context -> infrastructure for AI compute
  if (id.includes('caterpillar')) return 'B_industry';
  if (id.includes('barriers-around-drones')) return 'B_industry';
  if (id.includes('open-asr-leaderboard')) return 'C_global';
  if (id.includes('circleback')) return 'D_productivity';
  return 'X_other';
};
for (const it of items) it.cluster = clusterOf(it.id);

// Cluster composition
const clusterCounts = items.reduce((m, i) => (m[i.cluster] = (m[i.cluster] || 0) + 1, m), {});

// Tier adjustments based on topical weight + decay
// Cluster A (strategy) is Tier 1 anchor regardless of pre-tier on Musk turbines
const openaiCursor = items.find(i => i.id.startsWith('openai-our-decision-on-cursor'));
if (openaiCursor) {
  openaiCursor.final_tier = 1;
  openaiCursor.slot_msk = '21:30';
  openaiCursor.analyst_notes.push('Anchor post for the 6h cycle. Big strategic move (OpenAI ↔ Cursor ↔ SpaceX). Highest decayed_importance in queue.');
  openaiCursor.analyst_notes.push('Use breakthrough-style framing? No — M&A, not new architecture/SOTA. Standard Tier 1 template with clear “что это значит” framing.');
  openaiCursor.analyst_notes.push('Wait — Musk turbines is also in cluster A. Merge? No: turbines is environmental/infra angle, different story arc. Keep separate posts.');
}

// Cluster A second member — Musk turbines
const muskTurbines = items.find(i => i.id.includes('musks-faster-path'));
if (muskTurbines) {
  // Different theme from Cursor (energy pollution vs M&A). Demote to Tier 2 within cluster — environmental impact relevant to AI compute scaling.
  muskTurbines.final_tier = 2;
  muskTurbines.slot_msk = '22:15';
  muskTurbines.analyst_notes.push('Pulled into Tier 2: AI-compute energy angle makes this more than just a Tesla/SpaceX environmental story.');
  muskTurbines.analyst_notes.push('Cluster A narrative connection: directly continues the Musk/SpaceX thread opened by the OpenAI↔Cursor post.');
}

// Cluster C — HuggingFace ASR (pre Tier 2)
const asr = items.find(i => i.id.includes('open-asr-leaderboard'));
if (asr) {
  asr.final_tier = 2;
  asr.slot_msk = '22:45';
  asr.analyst_notes.push('Global South inclusion angle. Mid-tier slot. Decay 0.9 — still publishable but don’t defer further.');
}

// Cluster B — Caterpillar + US/China drones
const cat = items.find(i => i.id.includes('caterpillar'));
const drones = items.find(i => i.id.includes('barriers-around-drones'));
if (cat) {
  cat.final_tier = 3;
  cat.slot_msk = null;
  cat.defer = true;
  cat.defer_reason = 'Quiet hours 23:00–08:00 MSK block publication inside the 6h cycle. Defer to next cycle prime slot (08:00 MSK).';
  cat.analyst_notes.push('Industrial automation → edge AI → agent deployment in physical environments. Pairs thematically with US/China drones post.');
  cat.analyst_notes.push('Decay 3-day half-life: at 7 days old the news is aging. Schedule first in next cycle.');
}
if (drones) {
  drones.final_tier = 3;
  drones.slot_msk = null;
  drones.defer = true;
  drones.defer_reason = 'Quiet hours 23:00–08:00 MSK block publication inside the 6h cycle. Defer to next cycle (08:30 MSK after Caterpillar).';
  drones.analyst_notes.push('Geopolitics + robotics framing. Pairs well with Caterpillar (industrial agent deployment in adversarial supply chains).');
  drones.analyst_notes.push('Decay 3-day half-life: still fresh enough to hold until morning slot.');
}

// Cluster D — Circleback
const circleback = items.find(i => i.id.includes('circleback'));
if (circleback) {
  circleback.final_tier = 3;
  circleback.slot_msk = null;
  circleback.defer = true;
  circleback.defer_reason = 'No analysis yet (LLM translation/summary missing). Defer until analyze pipeline fills it. Likely next-cycle slot 09:00 MSK.';
  circleback.analyst_notes.push('Low strategic value (product pricing tier). Tier 3 even after analysis arrives.');
  circleback.analyst_notes.push('BLOCKER: pending_queue item has analysis:null. publish_post.py will skip with "no analysis". Run pipeline/analyze first.');
}

// Cycle window and quiet hours enforcement
const cycleWindow = {
  start_msk: '2026-09-17T21:21:00+03:00',
  end_msk: '2026-09-18T03:21:00+03:00',
  quiet_hours_msk: '23:00–08:00 MSK',
  publishable_slots_msk: ['21:30', '22:15', '22:45'],
  deferred_to_next_cycle_msk: ['08:00', '08:30', '09:00'],
  total_pre_quiet_minutes: 99, // 21:21 → 23:00
  note: 'Quiet hours 23:00–08:00 MSK leave only ~99 minutes of publishable time inside this 6h cycle. 3 posts scheduled, 3 deferred to next cycle morning slots.',
};

// AGI snapshot at time of plan
const agi = d.agi_counter || {};

// Detect Telegram config failure from recent logs
let telegramBlocked = false;
try {
  const log = fs.readFileSync(path.join(ROOT, 'data', 'cron-stdout.log'), 'utf8').slice(-8000);
  if (/plugins\.entries\.telegram: plugin disabled/i.test(log)) telegramBlocked = true;
} catch {}

const plan = {
  generated_at_msk: '2026-09-17T21:21+03:00',
  cron_job: 'agentsmits-blog-cluster',
  cycle_window: cycleWindow,
  agi_counter: agi,
  cluster_counts: clusterCounts,
  items,
  operational_alerts: [
    telegramBlocked
      ? 'Telegram channel currently blocked: `plugins.entries.telegram: plugin disabled (channel disabled in config) but config is present`. All scheduled slots will fail to deliver until config is fixed. See data/cron-publish.log.'
      : 'Telegram delivery OK at planning time.',
    'Last successful publish in logs: 2026-09-12 (per data/cron-publish.log). Current run started 2026-09-17 21:21:30 with 0 published / 0 failed / 0 skipped at the point of planning.',
  ],
};

fs.writeFileSync(path.join(ROOT, '_diag', 'cluster_plan.json'), JSON.stringify(plan, null, 2), 'utf8');

// Emit concise stdout summary
console.log('=== CLUSTER PLAN (next 6h cycle, 2026-09-17 21:21 MSK) ===');
console.log('AGI:', agi.current_days, '/', agi.base_days, 'days (', Math.round(agi.current_days / agi.base_days * 100), '%)');
console.log('Quiet hours:', cycleWindow.quiet_hours_msk, '| publishable pre-quiet:', cycleWindow.total_pre_quiet_minutes, 'min');
console.log('Cluster composition:', JSON.stringify(clusterCounts));
console.log('');
console.log('Scheduled in this cycle:');
for (const it of items.filter(i => !i.defer)) {
  console.log('  ' + it.slot_msk + ' MSK | Tier ' + it.final_tier + ' | ' + it.cluster + ' | ' + it.id);
}
console.log('Deferred to next cycle:');
for (const it of items.filter(i => i.defer)) {
  console.log('  next-cycle morning | Tier ' + it.final_tier + ' | ' + it.cluster + ' | ' + it.id + '  (' + it.defer_reason + ')');
}
console.log('');
console.log('Operational alerts:');
for (const a of plan.operational_alerts) console.log('  ⚠ ' + a);
