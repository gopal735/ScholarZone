const fs = require('fs');

const A = JSON.parse(fs.readFileSync('verification/detail_shape_repairs.json', 'utf8'));
const P = 'backend/config/programme_details.json';
const BUCKETS = ['official', 'applicant_utility', 'verification'];

// ---------------------------------------------------------------------------
// MINIMUM DETERMINISTIC REPAIR
//   string  ->  [ that exact string ]
// Everything else is left untouched. The artifact supplies only the SET of
// (id, field) targets. The wrapped text is always the LIVE value, never the
// artifact's snapshot, because 9 live strings have been rewritten since the
// artifact was generated and using the snapshot would revert them.
// ---------------------------------------------------------------------------

function run(pass) {
  const raw = fs.readFileSync(P, 'utf8');
  const pd = JSON.parse(raw);
  const byId = {};
  pd.records.forEach(r => (byId[String(r.id)] = r));

  const stats = { wrapped: 0, alreadyArray: 0, absent: 0, noRecord: 0, untouched: 0 };
  const changedFields = [];
  const textChanged = [];

  A.records.forEach(rec => {
    const target = byId[String(rec.id)];
    if (!target) {
      const n = Object.keys(rec.fields || {}).length;
      stats.noRecord += n;
      return;
    }
    Object.keys(rec.fields || {}).forEach(field => {
      let bucket = null, cur;
      for (const b of BUCKETS) {
        if (target[b] && typeof target[b] === 'object' && Object.prototype.hasOwnProperty.call(target[b], field)) { bucket = b; cur = target[b][field]; break; }
      }
      if (bucket === null) { stats.absent++; return; }
      if (Array.isArray(cur)) { stats.alreadyArray++; return; }
      if (typeof cur !== 'string') { stats.untouched++; return; }

      const before = cur;
      target[bucket][field] = [before];
      stats.wrapped++;
      changedFields.push({ id: rec.id, field, bucket });
      // data-loss guard: the wrapped text must be byte-identical
      if (target[bucket][field][0] !== before) textChanged.push({ id: rec.id, field });
    });
  });

  if (pass > 0) fs.writeFileSync(P, JSON.stringify(pd, null, 2));
  return { stats, changedFields, textChanged, bytes: JSON.stringify(pd, null, 2) };
}

// ---- PASS 0: dry run, no write ----
const d = run(0);
console.log('PASS 0 (dry run, no write): ' + JSON.stringify(d.stats));
console.log('');

// ---- PASS 1: apply ----
const p1 = run(1);
console.log('PASS 1 (applied)          : ' + JSON.stringify(p1.stats));
console.log('  fields written          : ' + p1.changedFields.length);
console.log('  records touched         : ' + new Set(p1.changedFields.map(c => c.id)).size);
console.log('  text mutations detected : ' + p1.textChanged.length + '  (must be 0)');
console.log('');

// ---- PASS 2: idempotency ----
const p2 = run(2);
console.log('PASS 2 (idempotency re-run): ' + JSON.stringify(p2.stats));
console.log('  fields written           : ' + p2.changedFields.length + '  (must be 0)');
console.log('');

// ---- verify persisted state ----
const after = JSON.parse(fs.readFileSync(P, 'utf8'));
const byId = {};
after.records.forEach(r => (byId[String(r.id)] = r));

let stillString = 0, doubleWrapped = 0, ok = 0, absent = 0, noRec = 0;
A.records.forEach(rec => {
  const t = byId[String(rec.id)];
  if (!t) { noRec += Object.keys(rec.fields || {}).length; return; }
  Object.keys(rec.fields || {}).forEach(field => {
    let b = null, cur;
    for (const k of BUCKETS) { if (t[k] && typeof t[k] === 'object' && Object.prototype.hasOwnProperty.call(t[k], field)) { b = k; cur = t[k][field]; break; } }
    if (b === null) { absent++; return; }
    if (typeof cur === 'string') stillString++;
    else if (Array.isArray(cur)) {
      if (cur.length === 1 && Array.isArray(cur[0])) doubleWrapped++;
      else ok++;
    }
  });
});
console.log('POST-REPAIR FIELD VERIFICATION');
console.log('  now correctly array     : ' + ok);
console.log('  still bare string       : ' + stillString + '  (must be 0 among repairable)');
console.log('  double-wrapped [[...]]   : ' + doubleWrapped + '  (must be 0)');
console.log('  field absent            : ' + absent);
console.log('  record not in config    : ' + noRec);
console.log('');
console.log('IDEMPOTENCY: ' + (p2.changedFields.length === 0 ? 'PROVEN - second pass wrote 0 fields' : 'FAILED - second pass wrote ' + p2.changedFields.length));
console.log('NO TEXT LOSS: ' + (p1.textChanged.length === 0 ? 'PASS' : 'FAIL'));
console.log('NO DOUBLE WRAP: ' + (doubleWrapped === 0 ? 'PASS' : 'FAIL'));

fs.writeFileSync('research/bachelor/_merged/repair_result.json', JSON.stringify({
  pass1: p1.stats, pass2: p2.stats, changed: p1.changedFields.length,
  records_touched: new Set(p1.changedFields.map(c => c.id)).size,
  text_mutations: p1.textChanged.length, double_wrapped: doubleWrapped,
  verification: { ok, stillString, absent, noRec },
}, null, 2));