// Read pending_queue.json and emit a compact report of pending items
const fs = require('fs');
const path = require('path');

const file = path.join(process.cwd(), 'data', 'pending_queue.json');
const d = JSON.parse(fs.readFileSync(file, 'utf8'));

const pend = d.pending || [];
const pub = d.published || [];
const agi = d.agi_counter || {};

console.log('== QUEUE SUMMARY ==');
console.log('pending_count =', pend.length);
console.log('published_count =', pub.length);
console.log('agi_counter =', JSON.stringify(agi));
console.log('sources_count =', (d.sources || []).length);
console.log('');

// Drop items already in published (by id) — same logic the publisher applies
const pubIds = new Set(pub.map(p => p.id));
const fresh = pend.filter(p => !pubIds.has(p.id));
console.log('pending_already_published =', pend.length - fresh.length);
console.log('pending_fresh =', fresh.length);
console.log('');

// Importance distribution
const impDist = {};
for (const p of fresh) {
  const k = 'imp_' + (p.importance ?? 'null');
  impDist[k] = (impDist[k] || 0) + 1;
}
console.log('importance_distribution =', JSON.stringify(impDist));

// Source distribution
const srcDist = {};
for (const p of fresh) {
  srcDist[p.source || 'unknown'] = (srcDist[p.source || 'unknown'] || 0) + 1;
}
console.log('source_distribution =', JSON.stringify(srcDist, null, 2));
console.log('');

// Tier distribution (if pre-tagged)
const tierDist = {};
for (const p of fresh) {
  const t = p.ai_impact && p.ai_impact.tier ? 'tier_' + p.ai_impact.tier : 'tier_unknown';
  tierDist[t] = (tierDist[t] || 0) + 1;
}
console.log('ai_tier_distribution =', JSON.stringify(tierDist));
console.log('');

// Date range
const dates = fresh.map(p => p.date || p.published_at || p.created_at).filter(Boolean).sort();
if (dates.length) {
  console.log('oldest_date =', dates[0]);
  console.log('newest_date =', dates[dates.length - 1]);
}
console.log('');

// Print fresh pending items
console.log('== PENDING ITEMS (fresh only) ==');
for (const p of fresh) {
  const ai = p.ai_impact || {};
  console.log(JSON.stringify({
    id: p.id,
    source: p.source,
    importance: p.importance,
    ai_total: ai.total ?? null,
    ai_tier: ai.tier ?? null,
    date: p.date || p.published_at || p.created_at || null,
    title: (p.title || '').slice(0, 100),
    has_summary: !!p.summary,
    has_analysis: !!p.analysis,
    publishing: !!p.publishing,
  }));
}
