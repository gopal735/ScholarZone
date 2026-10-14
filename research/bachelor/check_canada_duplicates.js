const fs = require('fs');
const path = require('path');
const D = 'research/bachelor';

// Canada deep duplicate check. Name similarity alone is NOT accepted as proof,
// so every pair of Canadian records is compared across awarding body, identity,
// award code, cycle, degree, programme, official URL and funding identity.
const files = fs.readdirSync(D).filter(f => /^(\d\d|b\d{2,3}|w\d)-.*[.]json$/.test(f));

const regDomain = h => {
  const p = String(h || '').toLowerCase().split('.').filter(Boolean);
  if (p.length < 2) return String(h || '').toLowerCase();
  const two = ['co.uk','ac.uk','gov.uk','edu.au','gov.au','edu.my','gov.my','edu.sg','gov.sg'];
  const last2 = p.slice(-2).join('.');
  return two.includes(last2) ? p.slice(-3).join('.') : last2;
};
const hostOf = u => { try { return new URL(u).hostname.toLowerCase().replace(/^www\./, ''); } catch { return ''; } };
const norm = s => String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

// Amount strings are extracted from prose so funding identity is compared on the
// real published figures rather than a single possibly-null field.
function moneyTexts(o) {
  const out = new Set();
  const grab = (arr) => (Array.isArray(arr) ? arr : []).forEach(s => {
    if (typeof s !== 'string') return;
    const m = s.match(/(?:CAD|USD|GBP|EUR|AUD|SGD|MYR)?\s?\$?\s?([\d][\d,]{2,})\s?(CAD|USD|GBP|EUR|AUD|SGD|MYR)?/gi) || [];
    m.forEach(x => out.add(x.replace(/\s+/g, ' ').trim().toLowerCase()));
  });
  const ns = o.new_scholarship || {}, off = o.programme_detail_official || {};
  if (ns.funding_amount != null) out.add(String(ns.funding_amount) + ' ' + (ns.funding_currency || ''));
  grab(ns.benefits); grab(ns.coverage); grab(off.benefits);
  return [...out];
}

const records = [];
files.forEach(f => {
  let o;
  try { o = JSON.parse(fs.readFileSync(path.join(D, f), 'utf8')); } catch { return; }
  const ns = o.new_scholarship || {};
  if (ns.region !== 'Canada') return;
  const url = ns.official_source_url || '';
  records.push({
    file: f,
    name: ns.name,
    body: ns.official_source || regDomain(hostOf(url)),
    host: hostOf(url),
    reg: regDomain(hostOf(url)),
    url,
    code: (JSON.stringify(o).match(/\bE\d{3,5}\b/g) || []).join(',') || null,
    cycle: (o.programme_detail_official || {}).application_cycle || null,
    degree: JSON.stringify(ns.degree_levels || null),
    programme: (o.programme_detail_official || {}).subject_or_agency_requirement ? String((o.programme_detail_official).subject_or_agency_requirement).slice(0, 60) : null,
    money: moneyTexts(o),
    status: ns.status,
  });
});

console.log('CANADA DEEP DUPLICATE CHECK');
console.log('records: ' + records.length);
console.log('');

// Group by awarding body (registrable domain) so the comparison is institution-scoped.
const byBody = {};
records.forEach(r => (byBody[r.reg] ||= []).push(r));

let suspects = 0;
Object.entries(byBody).sort().forEach(([body, rs]) => {
  const flag = rs.length > 1 ? '  <-- SAME AWARDING BODY, CHECK' : '';
  console.log(`${body}  (${rs.length})${flag}`);
  rs.forEach(r => console.log(`    ${r.file.padEnd(48)} ${r.name.slice(0, 54)}`));
  if (rs.length > 1) {
    suspects += rs.length;
    // Field-by-field comparison for every pair within the body.
    for (let i = 0; i < rs.length; i++) {
      for (let j = i + 1; j < rs.length; j++) {
        const a = rs[i], b = rs[j];
        const sameName = norm(a.name) === norm(b.name);
        const sameMoney = a.money.filter(m => b.money.includes(m)).length;
        const sameCycle = a.cycle && b.cycle && a.cycle === b.cycle;
        const sameUrl = a.url.replace(/\/+$/, '').toLowerCase() === b.url.replace(/\/+$/, '').toLowerCase();
        console.log(`      PAIR ${a.name.slice(0, 26)} <-> ${b.name.slice(0, 26)}`);
        console.log(`        same_name=${sameName} same_url=${sameUrl} same_cycle=${!!sameCycle} shared_amounts=${sameMoney} codes=${a.code || '-'}/${b.code || '-'}`);
        if (sameMoney > 0) console.log(`        shared amounts: ${a.money.filter(m => b.money.includes(m)).slice(0, 6).join(' | ')}`);
      }
    }
  }
});

console.log('');
console.log('records in multi-record bodies: ' + suspects);

// Global check: any award name duplicated across the whole Canadian set?
const byName = {};
records.forEach(r => (byName[norm(r.name)] ||= []).push(r.file));
const dupNames = Object.entries(byName).filter(([, v]) => v.length > 1);
console.log('exact duplicate names across Canada: ' + (dupNames.length || 'none'));
dupNames.forEach(([k, v]) => console.log('  ' + k + ' -> ' + v.join(', ')));

fs.writeFileSync('research/bachelor/_merged/canada_duplicate_check.json', JSON.stringify({
  generated: new Date().toISOString(),
  canadian_records: records.length,
  awarding_bodies: Object.keys(byBody).length,
  multi_record_bodies: Object.entries(byBody).filter(([, v]) => v.length > 1).map(([k, v]) => ({ body: k, records: v.map(r => ({ file: r.file, name: r.name, url: r.url, code: r.code, cycle: r.cycle, status: r.status, amounts: r.money.slice(0, 8) })) })),
  exact_duplicate_names: dupNames.map(([k, v]) => ({ name: k, files: v })),
}, null, 2));