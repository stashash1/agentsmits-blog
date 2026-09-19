// Cross-check selection_queue for tier-1 / importance-5 items not yet promoted
const fs = require('fs');
const path = require('path');

const sel = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'data', 'selection_queue.json'), 'utf8'));
const pubIds = new Set(JSON.parse(fs.readFileSync(path.join(process.cwd(), 'data', 'pending_queue.json'), 'utf8'))
  .published.map(p => p.id));

console.log('selection_total =', (sel.pending || []).length + (sel.published || []).length);
console.log('selection_pending =', (sel.pending || []).length);
console.log('selection_published =', (sel.published || []).length);
console.log('');
console.log('== selection.pending (importance >= 4 OR tier 1) ==');
for (const p of (sel.pending || [])) {
  if ((p.importance || 0) >= 4 || (p.ai_impact && p.ai_impact.tier === 1)) {
    console.log(JSON.stringify({
      id: p.id,
      source: p.source,
      importance: p.importance,
      tier: p.ai_impact && p.ai_impact.tier,
      title: (p.title || '').slice(0, 90),
    }));
  }
}
console.log('');
console.log('pending_queue.id is in selection.published?');
const selPubIds = new Set((sel.published || []).map(p => p.id));
const pend = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'data', 'pending_queue.json'), 'utf8')).pending;
for (const p of pend) {
  console.log(' -', p.id, '-> sel_pub=', selPubIds.has(p.id), 'queue_pub=', pubIds.has(p.id));
}
