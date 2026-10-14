const fs = require('fs');

// ---------- PHASE 1: artifact validation, no mutation ----------
const A = JSON.parse(fs.readFileSync('verification/detail_shape_repairs.json', 'utf8'));
const problems = [];
const P = m => { problems.push(m); console.log('  FAIL ' + m); };

console.log('PHASE 1 - ARTIFACT VALIDATION');
console.log('='.repeat(70));
console.log('generated_at     : ' + A.generated_at);
console.log('public_total     : ' + A.public_total);
console.log('detail_500_count : ' + A.detail_500_count);
console.log('repaired_records : ' + A.repaired_records);
console.log('records.length   : ' + A.records.length);
console.log('unexplained      : ' + A.unexplained.length);
console.log('');

if (A.records.length !== 117) P('records length ' + A.records.length + ' != 117');
if (A.unexplained.length !== 0) P('unexplained is ' + A.unexplained.length + ', expected 0');
if (A.repaired_records !== A.records.length) P('repaired_records ' + A.repaired_records + ' != records.length ' + A.records.length);

// ---- Which fields does the artifact actually target? ----
const fieldNames = {};
const ids = [];
const dupIds = [];
const seenIds = new Set();
const entries = [];

A.records.forEach((r, i) => {
  const id = r.id;
  if (!Number.isInteger(id)) P('records[' + i + '].id is not an integer: ' + JSON.stringify(id));
  if (id == null) P('records[' + i + '] has no id');
  if (seenIds.has(id)) dupIds.push(id); else seenIds.add(id);
  ids.push(id);

  if (!r.fields || typeof r.fields !== 'object') { P('records[' + i + '] has no fields object'); return; }
  const fk = Object.keys(r.fields);
  if (fk.length === 0) P('record ' + id + ' has empty fields object');

  fk.forEach(fn => {
    fieldNames[fn] = (fieldNames[fn] || 0) + 1;
    const ent = r.fields[fn];
    if (!('stored' in ent) || !('repaired' in ent)) { P('record ' + id + ' field ' + fn + ' missing stored/repaired'); return; }

    // stored must be a bare string (the defect)
    if (typeof ent.stored !== 'string') P('record ' + id + ' field ' + fn + ' stored is ' + typeof ent.stored + ', expected string');

    // repaired must be exactly [same string] - byte for byte, no nesting
    if (!Array.isArray(ent.repaired)) { P('record ' + id + ' field ' + fn + ' repaired is not an array'); return; }
    if (ent.repaired.length !== 1) P('record ' + id + ' field ' + fn + ' repaired length ' + ent.repaired.length + ', expected 1');
    if (Array.isArray(ent.repaired[0])) P('record ' + id + ' field ' + fn + ' repaired[0] is itself an array - double wrapping risk');
    if (ent.repaired[0] !== ent.stored) P('record ' + id + ' field ' + fn + ' repaired text differs from stored');

    entries.push({ id, field: fn, http: r.http_status, name: r.name, stored: ent.stored });
  });
});

if (dupIds.length) P('duplicate record ids in artifact: ' + dupIds.join(','));

console.log('FIELD COUNTS BY NAME');
Object.entries(fieldNames).sort((a, b) => b[1] - a[1]).forEach(([f, n]) => console.log('  ' + f.padEnd(30) + n));
console.log('');
console.log('total field entries : ' + entries.length);
console.log('distinct ids        : ' + seenIds.size);
console.log('');

// ---- HTTP status distribution ----
const st = {};
A.records.forEach(r => { st[r.http_status] = (st[r.http_status] || 0) + 1; });
console.log('http_status distribution:', JSON.stringify(st));
const non500 = A.records.filter(r => r.http_status !== 500);
console.log('records with http_status != 500 (latent defects):', non500.length);
non500.forEach(r => console.log('   id ' + r.id + ' http=' + r.http_status + '  fields=' + Object.keys(r.fields).join(',')));
console.log('');

// ---- Cross-check against the live source of detail data ----
console.log('CROSS-CHECK vs backend/config/programme_details.json');
let found = 0, mismatch = 0, missing = 0;
const pd = JSON.parse(fs.readFileSync('backend/config/programme_details.json', 'utf8'));
const pdById = {};
(pd.records || []).forEach(r => (pdById[String(r.id)] = r));
entries.forEach(e => {
  const rec = pdById[String(e.id)];
  if (!rec) { missing++; if (missing <= 5) console.log('   id ' + e.id + ' NOT FOUND in programme_details.json'); return; }
  const container = rec.official || rec.applicant_utility || rec.verification || rec;
  const cur = container[e.field];
  if (cur === undefined) { mismatch++; if (mismatch <= 5) console.log('   id ' + e.id + ' field ' + e.field + ' absent in programme_details record'); return; }
  if (cur !== e.stored) {
    mismatch++;
    if (mismatch <= 5) console.log('   id ' + e.id + ' field ' + e.field + ' stored text does NOT match live config');
    return;
  }
  found++;
});
console.log('   matched stored text : ' + found + ' / ' + entries.length);
console.log('   missing records     : ' + missing);
console.log('   text mismatches     : ' + mismatch);
console.log('');
console.log('PROBLEMS: ' + problems.length);
fs.writeFileSync('research/bachelor/_merged/phase1_artifact_validation.json', JSON.stringify({
  problems, entries, field_counts: fieldNames, distinct_ids: seenIds.size,
  http_status_distribution: st, matched: found, missing, mismatch,
}, null, 2));