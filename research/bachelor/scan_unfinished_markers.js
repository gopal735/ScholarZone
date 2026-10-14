const fs = require('fs');
const D = 'research/bachelor';

// Marker strings that mean "work not finished" but are not in the standard
// placeholder list. b18-swansea was counted COMPLETE by both gates while its
// eligibility array was empty and three fields literally read "INTERIM".
const MARKERS = ['interim', 'tbd', 'pending_tbc', 'partial_tbc', 'wip', 'draft', 'not_started', 'in_progress', 'placeholder', 'to_be_confirmed'];

const files = fs.readdirSync(D).filter(f => /^(\d\d|b\d{2,3}|w\d)-.*[.]json$/.test(f));
const hits = [];
files.forEach(f => {
  const t = fs.readFileSync(`${D}/${f}`, 'utf8');
  const found = [];
  MARKERS.forEach(m => {
    const re = new RegExp(`"([^"]*\\b${m}\\b[^"]*)"`, 'gi');
    let x;
    while ((x = re.exec(t))) found.push(x[1]);
  });
  if (found.length) hits.push({ file: f, values: [...new Set(found)].slice(0, 10) });
});

console.log('records containing unfinished-work marker strings:');
hits.forEach(h => console.log('  ' + h.file.padEnd(50) + JSON.stringify(h.values)));
console.log(hits.length ? `\ntotal: ${hits.length}` : '  none');
console.log('');

// Which of these also have an empty required array?
const emptyArr = [];
hits.forEach(h => {
  const o = JSON.parse(fs.readFileSync(`${D}/${h.file}`, 'utf8'));
  const off = o.programme_detail_official || {};
  const ns = o.new_scholarship || {};
  const gaps = [];
  ['eligibility', 'requirements', 'benefits'].forEach(k => { if (Array.isArray(off[k]) && !off[k].length) gaps.push('official.' + k); });
  if (Array.isArray(ns.eligibility) && !ns.eligibility.length) gaps.push('ns.eligibility');
  if (Array.isArray(ns.requirements) && !ns.requirements.length) gaps.push('ns.requirements');
  if (gaps.length) emptyArr.push({ file: h.file, gaps });
});
console.log('of those, records with an EMPTY required array:');
emptyArr.forEach(e => console.log('  ' + e.file.padEnd(50) + e.gaps.join(', ')));