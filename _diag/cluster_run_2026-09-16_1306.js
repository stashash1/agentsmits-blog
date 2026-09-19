// Cluster scheduler for the 6-hour window starting 2026-09-16 13:06 MSK
// Reads pending_queue.json, assigns slot + tier confirmation, emits analyst notes.
const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, '..', 'data', 'pending_queue.json');
const raw = JSON.parse(fs.readFileSync(FILE, 'utf8'));
const items = raw.pending || [];

const NOW_MS = Date.parse('2026-09-16T10:06:00Z'); // 13:06 MSK
const WINDOW_END_MS = NOW_MS + 6 * 3600 * 1000;     // 19:06 MSK
const QUIET_START_HOUR = 23; // 23:00 MSK
const QUIET_END_HOUR = 8;    // 08:00 MSK (next day)
const MSK_OFFSET_HOURS = 3;

// helper
function toMSK(iso) {
  const d = new Date(iso);
  const msk = new Date(d.getTime() + MSK_OFFSET_HOURS * 3600 * 1000);
  return msk;
}

function formatMSK(d) {
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hh = String(d.getUTCHours()).padStart(2, '0');
  const mi = String(d.getUTCMinutes()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd} ${hh}:${mi} MSK`;
}

// Choose publication slot within the 6h window respecting quiet hours
function chooseSlot(tier, idxInTier, totalInTier) {
  // Pre-defined slots within 13:06..19:06 MSK (all in publishable hours)
  const slots = {
    1: ['14:00', '16:00', '18:00'],
    2: ['15:00', '17:00'],
    3: ['14:30', '15:30', '16:30', '17:30', '18:30'],
  };
  const arr = slots[tier];
  if (idxInTier >= arr.length) {
    // overflow: jam into 18:45 / 19:00
    const fallback = tier === 1 ? ['19:00'] : tier === 2 ? ['18:45'] : ['19:00'];
    return fallback[Math.min(idxInTier - arr.length, fallback.length - 1)];
  }
  return arr[idxInTier];
}

// Analyze cluster
const enriched = items.map((it) => {
  const tier = (it.ai_impact && it.ai_impact.tier) || 3;
  const decayed = it.decayed_importance != null ? it.decayed_importance : (it.importance || 0);
  const ageDays = it.decay ? it.decay.delta_days : null;
  return { ...it, _tier: tier, _decayed: decayed, _age: ageDays };
});

// Sort within each tier by decayed_importance desc
const byTier = { 1: [], 2: [], 3: [] };
for (const e of enriched) {
  byTier[e._tier].push(e);
}
for (const t of [1, 2, 3]) {
  byTier[t].sort((a, b) => b._decayed - a._decayed);
}

console.log(`=== CLUSTER RUN @ ${formatMSK(new Date(NOW_MS))} ===`);
console.log(`Window end: ${formatMSK(new Date(WINDOW_END_MS))}`);
console.log(`Pending total: ${items.length}`);
console.log(`  Tier 1: ${byTier[1].length}`);
console.log(`  Tier 2: ${byTier[2].length}`);
console.log(`  Tier 3: ${byTier[3].length}`);
console.log('');

const plan = [];
for (const tier of [1, 2, 3]) {
  byTier[tier].forEach((e, i) => {
    const slot = chooseSlot(tier, i, byTier[tier].length);
    const titleRu = (e.analysis && e.analysis.translated_title) || e.title;
    const tags = (e.analysis && e.analysis.tags) || [];
    const reason =
      e._decayed >= 4 ? 'prime' :
      e._decayed >= 2 ? 'strong' :
      e._decayed >= 1 ? 'moderate' : 'filler';
    plan.push({
      tier,
      slot,
      id: e.id,
      source: e.source,
      decayed_importance: e._decayed,
      age_days: e._age,
      title: e.title,
      title_ru: titleRu.slice(0, 120),
      tags,
      reason,
    });
  });
}

console.log('--- PUBLICATION PLAN ---');
for (const p of plan) {
  console.log(`[T${p.tier}|${p.slot}|imp=${p.decayed_importance.toFixed(2)}|age=${p.age_days}d|${p.reason}] ${p.id}`);
  console.log(`  src: ${p.source}`);
  console.log(`  title: ${p.title}`);
  console.log(`  ru: ${p.title_ru}`);
}

const outFile = path.join(__dirname, 'cluster_plan_2026-09-16_1306.json');
fs.writeFileSync(outFile, JSON.stringify({ generated_at: new Date(NOW_MS).toISOString(), window_end: new Date(WINDOW_END_MS).toISOString(), plan }, null, 2), 'utf8');
console.log('');
console.log(`Plan written: ${outFile}`);
