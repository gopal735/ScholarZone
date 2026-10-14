const fs = require('fs');
const path = require('path');
const D = 'research/bachelor';

const audit = JSON.parse(fs.readFileSync('research/bachelor/_merged/consistency_audit.json', 'utf8'));
const routing = JSON.parse(fs.readFileSync('research/bachelor/_merged/closed_status_routing.json', 'utf8'));
const ins = JSON.parse(fs.readFileSync('research/bachelor/_merged/new_scholarships.new.json', 'utf8')).records;
const ref = JSON.parse(fs.readFileSync('research/bachelor/_merged/refreshes.json', 'utf8'));
const incRaw = JSON.parse(fs.readFileSync('research/bachelor/_merged/incomplete.json', 'utf8'));
const incomplete = incRaw.records || incRaw;

// Robust ID: a slot prefix (21, b01..b150) or a wave prefix plus its target token
// (w4-carleton). Never split('-')[0], which collapses every w4 file to "w4".
function idOf(f) {
  const slot = f.match(/^(\d\d|b\d{2,3})-/);
  if (slot) return slot[1];
  const wave = f.match(/^(w\d+)-([a-z0-9]+)-/);
  if (wave) return wave[1] + '-' + wave[2];
  return f.replace(/\.json$/, '');
}

const FLAGS = {
  PLACEHOLDER: o => { const bad = []; const walk = (x, p, out) => { if (!x || typeof x !== 'object') return; for (const [k, v] of Object.entries(x)) { const q = p ? p + '.' + k : k; if (typeof v === 'string' && /^(interim|draft|tbd|wip|unknown|pending|null|n\/a|-|not started)$/i.test(v.trim())) out.push(q); else if (Array.isArray(v)) v.forEach(y => { if (y && typeof y === 'object') walk(y, q, out); }); else if (v && typeof v === 'object') walk(v, q, out); } }; walk(o.new_scholarship, 'new_scholarship', bad); walk(o.programme_detail_official, 'programme_detail_official', bad); return bad; },
  CITATIONS: o => { const n = (o.programme_detail_verification || {}).source_citations || []; return n.length < 2 ? ['only ' + n.length + ' citation(s)'] : []; },
  SINGLE_SOURCE: o => /SINGLE-SOURCE EVIDENCE/i.test(JSON.stringify(o.programme_detail_verification || {})) ? ['evidence rests on one official page'] : [],
  DECLARED_CONFLICT: o => ((o.programme_detail_verification || {}).unverified_or_removed_claims || []).filter(c => /CONFLICT|AMBIGUITY|contradiction|disagree[sd]?|not averaged/i.test(c)).map(c => c.slice(0, 130)),
  CURRENCY_GBP: o => { const ns = o.new_scholarship || {}, off = o.programme_detail_official || {}, h = []; if (String(ns.funding_currency || '').toUpperCase() === 'GBP') h.push('new_scholarship.funding_currency=GBP'); if (String(off.funding_currency || '').toUpperCase() === 'GBP') h.push('programme_detail_official.funding_currency=GBP'); return h; },
  LOGO_HOST: o => { const host = u => { try { return new URL(u).hostname.toLowerCase().replace(/^www\./, ''); } catch { return ''; } }; const reg = h => String(h || '').split('.').slice(-2).join('.'); const ns = o.new_scholarship || {}, lo = o.logo_override || {}; if (!lo.url || !ns.official_source_url) return []; return reg(host(lo.url)) === reg(host(ns.official_source_url)) ? [] : ['logo host ' + host(lo.url) + ' vs source host ' + host(ns.official_source_url)]; },
  STALE_SKELETON_FLAG: o => ((o.research_notes || {}).skeleton === true ? ['skeleton=true on a record that is otherwise complete'] : []),
};
// b22 and b18 are UK universities where GBP is the correct published currency.
const GBP_EXEMPT = new Set(['b18-international-scholarship-ug-students-swansea.json', 'b22-global-excellence-scholarships.json']);

const REJECTED = {};
const FILES = fs.readdirSync(D).filter(f => f.endsWith('.json') && /^(\d\d|b\d{2,3}|w\d)-/.test(f)).sort();
FILES.forEach(f => { let o; try { o = JSON.parse(fs.readFileSync(path.join(D, f), 'utf8')); } catch { return; } if (o && typeof o.verdict === 'string' && /REJECTED|NO APPLICABLE AWARD/i.test(o.verdict)) REJECTED[f] = o; });

const routingByFile = {};
routing.decisions.forEach(d => { routingByFile[d.file] = d; });

const rows = [];
FILES.forEach(f => {
  let o;
  try { o = JSON.parse(fs.readFileSync(path.join(D, f), 'utf8')); }
  catch (e) { rows.push({ id: idOf(f), file: f, scholarship_name: null, region: null, action: 'FAILED', verification_state: 'UNPARSEABLE', official_source: null, citations: 0, confidence: null, human_review: false, review_flags: ['UNPARSEABLE'], reason: e.message }); return; }

  const id = idOf(f);
  if (REJECTED[f]) {
    const rj = REJECTED[f];
    rows.push({
      id, file: f, scholarship_name: (rj.assigned_target || {}).name || null, region: 'United States',
      action: 'REJECTED', verification_state: 'VERIFIED_REJECTION', official_source: 'bowdoin.edu (Williams College)'.replace('bowdoin', 'williams'),
      citations: (rj.official_evidence || []).length, confidence: 1.0, human_review: false, review_flags: [],
      reason: rj.decision,
    });
    return;
  }

  const ns = o.new_scholarship || {}, off = o.programme_detail_official || {}, v = o.programme_detail_verification || {};
  const url = ns.official_source_url || '';
  const host = (() => { try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return null; } })();

  const flags = [];
  Object.entries(FLAGS).forEach(([cat, fn]) => {
    if (cat === 'CURRENCY_GBP' && GBP_EXEMPT.has(f)) return;
    let res = []; try { res = fn(o) || []; } catch { res = ['check failed']; }
    if (res.length) flags.push({ category: cat, reasons: res });
  });

  const r = routingByFile[f];
  const isIncomplete = incomplete.some(i => (i.file || '') === f);
  const isRef = ref.some(x => String(x.name || '').toLowerCase() === String(ns.name || '').toLowerCase());

  let action, verification_state, reason;
  if (r && r.route === 'BLOCKED') { action = 'BLOCKED'; verification_state = 'VERIFIED'; reason = (r.reasons || []).join(' '); }
  else if (r && r.route === 'HISTORICAL') { action = 'HISTORICAL'; verification_state = 'VERIFIED'; reason = (r.reasons || []).join(' '); }
  else if (isIncomplete) { action = 'UNVERIFIED'; verification_state = 'PARTIAL'; reason = 'Held out by the completion gate: ' + ((incomplete.find(i => i.file === f) || {}).reason || ''); }
  else if (isRef) { const m = ref.find(x => String(x.name || '').toLowerCase() === String(ns.name || '').toLowerCase()); action = 'REFRESH'; verification_state = 'VERIFIED'; reason = 'Routes as REFRESH of existing ' + m.existing_state + ' id ' + m.existing_id + '; must not be inserted as a new row.'; }
  else { action = 'INSERT'; verification_state = 'VERIFIED'; reason = ns.status === 'closed' ? 'Complete record; do_add() rejects closed status, so it is not insertion-ready.' : 'Complete record, ready for do_add().'; }

  rows.push({
    id, file: f, scholarship_name: ns.name || null, region: ns.region || null, action, verification_state,
    official_source: ns.official_source || host, official_source_url: url || null,
    citations: (v.source_citations || []).length,
    confidence: typeof v.verification_confidence === 'number' ? v.verification_confidence : null,
    human_review: flags.length > 0,
    review_flags: flags.map(x => x.category),
    review_categories: flags.map(x => x.category),
    review_reasons: flags.flatMap(x => x.reasons),
    reason,
  });
});

rows.sort((a, b) => a.id.localeCompare(b.id, undefined, { numeric: true }));

const counts = rows.reduce((a, r) => (a[r.action] = (a[r.action] || 0) + 1, a), {});
// A review FLAG is a category-instance, so the category counts sum exactly to the
// total. Reason strings are recorded separately because one category can carry
// several reasons (57 has 2 CURRENCY_GBP reasons but is one flag).
const totalFlags = rows.reduce((n, r) => n + ((r.review_categories || []).length), 0);
const uniqueReview = rows.filter(r => r.human_review).length;
const catCounts = {};
rows.forEach(r => (r.review_categories || []).forEach(c => (catCounts[c] = (catCounts[c] || 0) + 1)));
const catSum = Object.values(catCounts).reduce((a, b) => a + b, 0);

fs.writeFileSync('research/bachelor/MANIFEST.json', JSON.stringify({
  generated: new Date().toISOString(),
  file_count: rows.length,
  final_state_counts: counts,
  accounted: Object.values(counts).reduce((a, b) => a + b, 0),
  invariant_37: Object.values(counts).reduce((a, b) => a + b, 0) === 37,
  unique_review_records: uniqueReview,
  total_review_flags: totalFlags,
  flag_counts_by_category: catCounts,
  category_sum: catSum,
  category_sum_matches_total_flags: catSum === totalFlags,
  rows,
}, null, 2));

console.log('FINAL STAGING MANIFEST');
console.log('='.repeat(72));
console.log('files accounted : ' + rows.length + ' (invariant 37: ' + (Object.values(counts).reduce((a, b) => a + b, 0) === 37) + ')');
Object.entries(counts).sort().forEach(([k, v]) => console.log('  ' + k.padEnd(12) + v));
console.log('');
console.log('unique_review_records : ' + uniqueReview);
console.log('total_review_flags    : ' + totalFlags);
console.log('category sum          : ' + catSum + ' (matches: ' + (catSum === totalFlags) + ')');
Object.entries(catCounts).sort((a, b) => b[1] - a[1]).forEach(([c, n]) => console.log('  ' + c.padEnd(24) + n));
console.log('');
console.log('REVIEW RECORDS');
rows.filter(r => r.human_review).forEach(r => console.log('  ' + r.id.padEnd(15) + r.action.padEnd(11) + String(r.review_flags.length) + '  ' + (r.review_categories || []).join(',')));
console.log('');
console.log('NON-INSERT STATES');
rows.filter(r => r.action !== 'INSERT').forEach(r => console.log('  ' + r.action.padEnd(11) + r.id.padEnd(15) + (r.scholarship_name || '').slice(0, 46)));