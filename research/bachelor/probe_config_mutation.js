const fs = require('fs');
const { execSync } = require('child_process');

const FILES = [
  'backend/config/record_corrections.json',
  'backend/config/retired_records.json',
  'backend/config/verification_confirmations.json',
];

// Decisive test: does the working tree differ from HEAD in CONTENT, or only in
// FORMATTING? If the parsed structures are deep-equal, the mutation is a
// re-serialisation and no data changed.
function deepDiff(a, b, pathStr, out) {
  if (out.length > 60) return;
  const ta = a === null ? 'null' : Array.isArray(a) ? 'array' : typeof a;
  const tb = b === null ? 'null' : Array.isArray(b) ? 'array' : typeof b;
  if (ta !== tb) { out.push(`${pathStr}: type ${ta} -> ${tb}`); return; }
  if (ta === 'array') {
    if (a.length !== b.length) { out.push(`${pathStr}: length ${a.length} -> ${b.length}`); }
    const n = Math.min(a.length, b.length);
    for (let i = 0; i < n; i++) deepDiff(a[i], b[i], `${pathStr}[${i}]`, out);
    return;
  }
  if (ta === 'object') {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const k of keys) {
      if (!(k in a)) { out.push(`${pathStr}.${k}: ADDED`); continue; }
      if (!(k in b)) { out.push(`${pathStr}.${k}: REMOVED`); continue; }
      deepDiff(a[k], b[k], `${pathStr}.${k}`, out);
    }
    return;
  }
  if (a !== b) out.push(`${pathStr}: ${JSON.stringify(a).slice(0, 90)} -> ${JSON.stringify(b).slice(0, 90)}`);
}

FILES.forEach(f => {
  const head = execSync(`git show HEAD:${f}`, { encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  const work = fs.readFileSync(f, 'utf8');
  const stat = fs.statSync(f);

  console.log('='.repeat(76));
  console.log(f);
  console.log('  HEAD bytes            : ' + Buffer.byteLength(head));
  console.log('  working tree bytes    : ' + Buffer.byteLength(work));
  console.log('  working tree mtime    : ' + stat.mtime.toISOString());
  console.log('  identical byte-for-byte: ' + (head === work));

  let hj, wj, hErr = null, wErr = null;
  try { hj = JSON.parse(head); } catch (e) { hErr = e.message; }
  try { wj = JSON.parse(work); } catch (e) { wErr = e.message; }
  if (hErr || wErr) { console.log('  parse error HEAD=' + hErr + ' WORK=' + wErr); return; }

  const out = [];
  deepDiff(hj, wj, '', out);
  console.log('  CONTENT differences   : ' + out.length);
  out.slice(0, 25).forEach(d => console.log('      ' + d));
  if (out.length > 25) console.log('      ... +' + (out.length - 25) + ' more');

  // Which top-level keys changed?
  const keysH = Object.keys(hj), keysW = Object.keys(wj);
  const added = keysW.filter(k => !keysH.includes(k));
  const removed = keysH.filter(k => !keysW.includes(k));
  if (added.length) console.log('  top-level keys ADDED  : ' + added.join(', '));
  if (removed.length) console.log('  top-level keys REMOVED: ' + removed.join(', '));

  const rh = (hj.records || []).length, rw = (wj.records || []).length;
  if (rh !== rw) console.log(`  records count: ${rh} -> ${rw}`);
  else console.log(`  records count: ${rh} (unchanged)`);
});