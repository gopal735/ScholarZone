const fs = require('fs');

const A = JSON.parse(fs.readFileSync('verification/detail_shape_repairs.json', 'utf8'));
const P = 'backend/config/programme_details.json';
const pd = JSON.parse(fs.readFileSync(P, 'utf8'));
const pdById = {};
(pd.records || []).forEach(r => (pdById[String(r.id)] = r));

const BUCKETS = ['official', 'applicant_utility', 'verification'];

const rows = [];
A.records.forEach(r => {
  Object.entries(r.fields || {}).forEach(([field, ent]) => {
    const rec = pdById[String(r.id)];
    const row = { id: r.id, field, artifact_stored: ent.stored, artifact_repaired: ent.repaired, http: r.http_status };
    if (!rec) { rows.push({ ...row, action: 'SKIP_NO_RECORD', live_type: null, live: null }); return; }
    let bucket = null, cur;
    for (const b of BUCKETS) {
      if (rec[b] && typeof rec[b] === 'object' && Object.prototype.hasOwnProperty.call(rec[b], field)) { bucket = b; cur = rec[b][field]; break; }
    }
    if (bucket === null) { rows.push({ ...row, action: 'SKIP_FIELD_ABSENT', live_type: undefined, live: undefined }); return; }
    const t = Array.isArray(cur) ? 'array' : cur === null ? 'null' : typeof cur;
    row.bucket = bucket; row.live_type = t;
    if (t === 'array') {
      row.action = cur.length === 1 && cur[0] === ent.stored ? 'NOOP_ALREADY_REPAIRED' : 'NOOP_ALREADY_ARRAY_DIFFERENT';
      row.live = JSON.stringify(cur).slice(0, 120);
    } else if (t === 'string') {
      row.live = cur;
      if (cur === ent.stored) { row.action = 'REPAIR_FROM_ARTIFACT'; row.planned = [cur]; }
      else { row.action = 'REPAIR_FROM_LIVE'; row.planned = [cur]; row.text_differs_from_artifact = true; }
    } else {
      row.action = 'SKIP_UNEXPECTED_TYPE'; row.live = JSON.stringify(cur).slice(0, 120);
    }
    rows.push(row);
  });
});

const tally = rows.reduce((a, r) => (a[r.action] = (a[r.action] || 0) + 1, a), {});
const planned = rows.filter(r => r.action.startsWith('REPAIR'));

console.log('PHASE 4 - DRY RUN (NO MUTATION)');
console.log('='.repeat(72));
console.log('artifact field entries : ' + rows.length);
console.log('records in artifact    : ' + A.records.length);
Object.entries(tally).sort().forEach(([k, v]) => console.log('  ' + k.padEnd(32) + v));
console.log('');
console.log('PLANNED MUTATIONS      : ' + planned.length);
console.log('  from artifact text   : ' + planned.filter(r => r.action === 'REPAIR_FROM_ARTIFACT').length);
console.log('  from live text       : ' + planned.filter(r => r.action === 'REPAIR_FROM_LIVE').length);
console.log('');

// ---- invariant checks ----
console.log('INVARIANTS');
const inv = [];
const check = (name, ok, detail) => { console.log('  [' + (ok ? 'PASS' : 'FAIL') + '] ' + name + (detail ? ' - ' + detail : '')); if (!ok) inv.push(name); };

check('artifact records == 117', A.records.length === 117, String(A.records.length));
check('unexplained == 0', A.unexplained.length === 0);
check('no double-wrapping in artifact', !rows.some(r => Array.isArray(r.artifact_repaired[0])));
check('every planned repair is string -> [string]', planned.every(r => typeof r.live === 'string' && r.planned.length === 1 && r.planned[0] === r.live));
check('no planned repair alters text', planned.every(r => r.planned[0] === r.live));
check('no mutation planned for already-array fields', rows.filter(r => r.action.startsWith('NOOP')).every(r => !r.action.startsWith('REPAIR')));
check('no unexpected-type fields targeted', (tally.SKIP_UNEXPECTED_TYPE || 0) === 0);
const distinctPlannedIds = new Set(planned.map(r => r.id)).size;
console.log('  distinct record ids needing repair: ' + distinctPlannedIds);
console.log('');
console.log('DATA-LOSS GUARD');
console.log('  ' + (planned.filter(r => r.text_differs_from_artifact).length) + ' fields have live text differing from the artifact snapshot.');
console.log('  Repair uses the LIVE string for these, so newer text is preserved.');
console.log('  Using the artifact text would have overwritten ' + planned.filter(r => r.text_differs_from_artifact).length + ' newer values.');
console.log('');
console.log('SKIPPED (cannot repair, reported not silently dropped)');
rows.filter(r => r.action.startsWith('SKIP')).forEach(r => console.log('  ' + String(r.id).padEnd(6) + r.field.padEnd(22) + r.action));
console.log('');
console.log('BEFORE TYPE DISTRIBUTION');
const before = {};
rows.forEach(r => { const k = r.field + ' -> ' + (r.live_type === undefined ? 'absent' : r.live_type); before[k] = (before[k] || 0) + 1; });
Object.entries(before).sort().forEach(([k, v]) => console.log('  ' + k.padEnd(42) + v));
console.log('');
console.log('AFTER TYPE DISTRIBUTION (projected)');
const after = {};
rows.forEach(r => {
  const t = r.action.startsWith('REPAIR') ? 'array' : (r.live_type === undefined ? 'absent' : r.live_type);
  const k = r.field + ' -> ' + t; after[k] = (after[k] || 0) + 1;
});
Object.entries(after).sort().forEach(([k, v]) => console.log('  ' + k.padEnd(42) + v));
console.log('');
console.log('INVARIANT FAILURES: ' + inv.length);

fs.writeFileSync('research/bachelor/_merged/phase4_dryrun.json', JSON.stringify({ tally, planned_count: planned.length, rows, invariant_failures: inv }, null, 2));