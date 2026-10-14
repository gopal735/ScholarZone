const fs = require('fs');

const A = JSON.parse(fs.readFileSync('verification/detail_shape_repairs.json', 'utf8'));
const pd = JSON.parse(fs.readFileSync('backend/config/programme_details.json', 'utf8'));
const pdById = {};
(pd.records || []).forEach(r => (pdById[String(r.id)] = r));

// Correct cross-check: search EVERY sub-object of the record, not the first
// truthy one. The previous version used `rec.official || rec.applicant_utility ||
// ...` which stops at rec.official and can never see a field stored elsewhere.
const entries = [];
A.records.forEach(r => Object.entries(r.fields || {}).forEach(([field, ent]) => {
  entries.push({ id: r.id, field, stored: ent.stored, http: r.http_status, name: r.name });
}));

const result = { matched: 0, mismatch: [], missing_id: [], not_found_field: [], type_bug: [], already_array: 0, absent_both: [] };

entries.forEach(e => {
  const rec = pdById[String(e.id)];
  if (!rec) { result.missing_id.push(e); return; }

  // find the field in any sub-object
  let where = null, value;
  const buckets = { official: rec.official, applicant_utility: rec.applicant_utility, verification: rec.verification, root: rec };
  for (const [k, b] of Object.entries(buckets)) {
    if (b && typeof b === 'object' && Object.prototype.hasOwnProperty.call(b, e.field)) { where = k; value = b[e.field]; break; }
  }
  if (!where) { result.not_found_field.push({ ...e }); return; }

  if (Array.isArray(value)) { result.already_array++; result.absent_both.push({ id: e.id, field: e.field, note: 'already an array in live config - artifact stale or already repaired' }); return; }
  if (typeof value === 'string') {
    if (value === e.stored) result.matched++;
    else result.mismatch.push({ ...e, where, live: value.slice(0, 90) });
    return;
  }
  result.type_bug.push({ ...e, where, live_type: value === null ? 'null' : typeof value });
});

console.log('CORRECTED CROSS-CHECK (all sub-objects searched)');
console.log('='.repeat(72));
console.log('field entries checked      : ' + entries.length);
console.log('exact stored-text matches  : ' + result.matched);
console.log('stored text differs        : ' + result.mismatch.length);
console.log('record id not in config    : ' + result.missing_id.length);
console.log('field absent in record     : ' + result.not_found_field.length);
console.log('already an array (stale)   : ' + result.already_array);
console.log('unexpected type            : ' + result.type_bug.length);
console.log('');
if (result.mismatch.length) { console.log('TEXT MISMATCHES (first 10)'); result.mismatch.slice(0, 10).forEach(m => { console.log('  id ' + m.id + ' ' + m.field + ' [' + m.where + ']'); console.log('      live : ' + m.live); console.log('      artifact: ' + String(m.stored).slice(0, 90)); }); }
if (result.missing_id.length) { console.log('MISSING IDS'); [...new Set(result.missing_id.map(x => x.id))].forEach(id => console.log('  id ' + id)); }
if (result.not_found_field.length) { console.log('FIELD ABSENT'); result.not_found_field.slice(0, 10).forEach(m => console.log('  id ' + m.id + ' ' + m.field)); }
if (result.type_bug.length) { console.log('UNEXPECTED TYPES'); result.type_bug.slice(0, 10).forEach(m => console.log('  id ' + m.id + ' ' + m.field + ' -> ' + m.live_type)); }

// Which sub-object holds each field, and its current live type
console.log('');
console.log('FIELD -> live type distribution');
const byField = {};
entries.forEach(e => {
  const rec = pdById[String(e.id)];
  if (!rec) { byField[e.field] = byField[e.field] || {}; (byField[e.field].noRecord = (byField[e.field].noRecord || 0) + 1); return; }
  let v;
  for (const b of [rec.official, rec.applicant_utility, rec.verification, rec]) {
    if (b && typeof b === 'object' && Object.prototype.hasOwnProperty.call(b, e.field)) { v = b[e.field]; break; }
  }
  const t = v === undefined ? 'absent' : Array.isArray(v) ? 'array' : v === null ? 'null' : typeof v;
  byField[e.field] = byField[e.field] || {};
  byField[e.field][t] = (byField[e.field][t] || 0) + 1;
});
Object.entries(byField).sort().forEach(([f, d]) => console.log('  ' + f.padEnd(22) + JSON.stringify(d)));

fs.writeFileSync('research/bachelor/_merged/phase1_crosscheck.json', JSON.stringify(result, null, 2));