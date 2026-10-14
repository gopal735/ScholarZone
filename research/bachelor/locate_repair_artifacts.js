const fs = require('fs');
const path = require('path');

const SKIP = /node_modules|\.git$|worktrees|__pycache__|\.venv|site-packages/;
const found = [];
let scanned = 0;

function scan(dir, depth) {
  if (depth > 3) return;
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (SKIP.test(e.name)) continue;
      scan(p, depth + 1);
      continue;
    }
    if (!/\.(json|csv|md|txt)$/i.test(e.name)) continue;
    let st;
    try { st = fs.statSync(p); } catch { continue; }
    if (st.size > 12e6) continue;
    let t;
    try { t = fs.readFileSync(p, 'utf8'); } catch { continue; }
    scanned++;
    const marks = [];
    // A real 500-audit artifact records HTTP status codes and a detail endpoint.
    if (/117/.test(t) && /(record|repair|affected|serialize)/i.test(t)) marks.push('117+repair');
    if (/386/.test(t) && /(endpoint|detail|sweep|audit)/i.test(t)) marks.push('386+endpoint');
    if (/"status"\s*:\s*500/.test(t)) marks.push('status500');
    if (/\bHTTP 500\b|http_500|status_code\D{0,4}500/.test(t)) marks.push('http500');
    if (marks.length) found.push({ p, marks, size: st.size });
  }
}

['.', 'backend'].forEach(r => scan(r, 0));
console.log('scanned files: ' + scanned);
console.log('candidate artifacts: ' + found.length);
found.slice(0, 30).forEach(f => console.log('  ' + f.marks.join('+').padEnd(16) + f.p));

// Targeted: any repair artifact that actually holds ~117 records.
console.log('\n--- JSON/CSV artifacts whose record count is near 117 ---');
function countRecords(o) {
  if (Array.isArray(o)) return o.length;
  if (o && typeof o === 'object') {
    for (const k of ['records', 'rows', 'items', 'data', 'results', 'affected', 'entries']) {
      if (Array.isArray(o[k])) return o[k].length;
    }
  }
  return null;
}
(function scanFor117(dir, depth) {
  if (depth > 3) return;
  let entries;
  try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
  for (const e of entries) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (!SKIP.test(e.name)) scanFor117(p, depth + 1); continue; }
    if (!/\.json$/i.test(e.name)) continue;
    let st; try { st = fs.statSync(p); } catch { continue; }
    if (st.size > 12e6) continue;
    try {
      const o = JSON.parse(fs.readFileSync(p, 'utf8'));
      const n = countRecords(o);
      if (n !== null && n >= 100 && n <= 135) console.log('  ' + String(n).padStart(4) + ' records  ' + p);
    } catch { /* not json */ }
  }
})('backend', 0);