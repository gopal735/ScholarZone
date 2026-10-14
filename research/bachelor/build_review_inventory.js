const fs = require('fs');
const path = require('path');
const D = 'research/bachelor';

// Build the human-review inventory from the CURRENT verified records, then
// separate unique records from total flags. One record may carry many flags.
const audit = JSON.parse(fs.readFileSync('research/bachelor/_merged/consistency_audit.json', 'utf8'));
const manifest = JSON.parse(fs.readFileSync('research/bachelor/MANIFEST.json', 'utf8'));

const byFile = {};
manifest.records.forEach(r => {
  byFile[r.file] = {
    id: r.id, file: r.file, name: r.name, region: r.region,
    route: r.action, verification_state: r.verification_state,
  };
});

// Re-derive flags straight from the records so the inventory cannot drift from
// the data the way a hand-written summary did.
const FLAGS = {
  PLACEHOLDER: o => {
    const bad = [];
    const walk = (x, p, out) => {
      if (!x || typeof x !== 'object') return;
      for (const [k, v] of Object.entries(x)) {
        const q = p ? p + '.' + k : k;
        if (typeof v === 'string' && /^(interim|draft|tbd|wip|unknown|pending|null|n\/a|-)$/i.test(v.trim())) out.push(q);
        else if (Array.isArray(v)) v.forEach(y => { if (y && typeof y === 'object') walk(y, q, out); });
        else if (v && typeof v === 'object') walk(v, q, out);
      }
    };
    walk(o.new_scholarship, 'new_scholarship', bad);
    walk(o.programme_detail_official, 'programme_detail_official', bad);
    return bad;
  },
  CITATIONS: o => {
    const n = (o.programme_detail_verification || {}).source_citations || [];
    return n.length < 2 ? [`only ${n.length} citation(s)`] : [];
  },
  SINGLE_SOURCE: o => /SINGLE-SOURCE EVIDENCE/i.test(JSON.stringify(o.programme_detail_verification || {})) ? ['evidence rests on one official page'] : [],
  DECLARED_CONFLICT: o => {
    const claims = (o.programme_detail_verification || {}).unverified_or_removed_claims || [];
    return claims.filter(c => /CONFLICT|AMBIGUITY|contradiction|disagree[sd]?|inconsistent between|both official pages|not averaged/i.test(c)).map(c => c.slice(0, 150));
  },
  CURRENCY_GBP: o => {
    const ns = o.new_scholarship || {}, off = o.programme_detail_official || {};
    const hits = [];
    if (String(ns.funding_currency || '').toUpperCase() === 'GBP') hits.push('new_scholarship.funding_currency=GBP');
    if (String(off.funding_currency || '').toUpperCase() === 'GBP') hits.push('programme_detail_official.funding_currency=GBP');
    return hits;
  },
  LOGO_HOST: o => {
    const host = u => { try { return new URL(u).hostname.toLowerCase().replace(/^www\./, ''); } catch { return ''; } };
    const reg = h => { const p = String(h || '').split('.'); return p.slice(-2).join('.'); };
    const ns = o.new_scholarship || {}, lo = o.logo_override || {};
    if (!lo.url || !ns.official_source_url) return [];
    return reg(host(lo.url)) === reg(host(ns.official_source_url)) ? [] : [`logo host ${host(lo.url)} vs source host ${host(ns.official_source_url)}`];
  },
  STALE_SKELETON_FLAG: o => ((o.research_notes || {}).skeleton === true ? ['skeleton=true'] : []),
  COUNTRY_REGION: o => {
    const ns = o.new_scholarship || {};
    const map = { 'United States': ['United States', 'USA', 'US'], Canada: ['Canada'], Australia: ['Australia'], Singapore: ['Singapore'], Malaysia: ['Malaysia'] };
    const exp = map[ns.region];
    if (!exp || !ns.country) return [];
    return exp.map(x => x.toLowerCase()).includes(String(ns.country).toLowerCase()) ? [] : [`country "${ns.country}" vs region "${ns.region}"`];
  },
};

const items = [];
manifest.records.forEach(r => {
  if (!fs.existsSync(path.join(D, r.file))) return;
  const o = JSON.parse(fs.readFileSync(path.join(D, r.file), 'utf8'));
  if (!o || !o.new_scholarship) return;
  const flags = [];
  Object.entries(FLAGS).forEach(([cat, fn]) => {
    let res = [];
    try { res = fn(o) || []; } catch { res = ['check failed']; }
    if (res.length) flags.push({ category: cat, reasons: res });
  });
  if (flags.length) {
    items.push({
      id: r.id, file: r.file, name: r.name, region: r.region,
      route: r.action, verification_state: r.verification_state,
      flag_count: flags.length,
      review_reasons: flags.flatMap(f => f.reasons),
      review_categories: flags.map(f => f.category),
      flag_details: flags,
    });
  }
});

items.sort((a, b) => (a.id || '').localeCompare(b.id || '', undefined, { numeric: true }));

const totalFlags = items.reduce((n, i) => n + i.flag_count, 0);
const catCounts = {};
items.forEach(i => i.review_categories.forEach(c => (catCounts[c] = (catCounts[c] || 0) + 1)));

console.log('HUMAN-REVIEW INVENTORY');
console.log('='.repeat(78));
console.log('UNIQUE records requiring human review : ' + items.length);
console.log('TOTAL review flags                    : ' + totalFlags);
console.log('');
console.log('ID'.padEnd(7) + 'ROUTE'.padEnd(12) + 'FLAGS  CATEGORIES');
items.forEach(i => {
  console.log(String(i.id).padEnd(7) + String(i.route).padEnd(12) + String(i.flag_count).padEnd(7) + i.review_categories.join(', '));
});
console.log('');
console.log('FLAG COUNTS BY CATEGORY (a record may appear in several)');
Object.entries(catCounts).sort((a, b) => b[1] - a[1]).forEach(([c, n]) => console.log('  ' + c.padEnd(24) + n));
console.log('');
console.log('FULL REASON DETAIL');
items.forEach(i => {
  console.log('  ' + i.id + '  ' + i.name);
  i.flag_details.forEach(f => console.log('      [' + f.category + '] ' + f.reasons.join('; ')));
});

fs.writeFileSync('research/bachelor/_merged/human_review_inventory.json', JSON.stringify({
  generated: new Date().toISOString(),
  unique_review_records: items.length,
  total_review_flags: totalFlags,
  flag_counts_by_category: catCounts,
  items,
}, null, 2));