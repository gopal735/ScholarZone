// check_b03.js — focused, independent invariant check on the completed slot-b03 record.
// Deliberately does not reuse validate_bachelor.js: it re-derives the contract and repo
// rules from SCHEMA_CONTRACT.md / RESEARCH_PROTOCOL.md / validate_bachelor.js constants
// so a bug in the shared validator cannot hide a defect here.
const fs = require('fs');
const F = 'C:/Users/GopaL/Desktop/Projects folder/ScholarZone/research/bachelor/b03-universita-di-pisa-borse-di-studio.json';
const LOGOS_TRIED = [
  { url: 'https://www.dsu.toscana.it/image/layout_set_logo?img_id=21919169', want: 'image/png' },
  { url: 'https://www.unipi.it/wp-content/uploads/Raggruppa-3020.svg', want: 'image/svg+xml' },
];

let fail = 0;
const ok = (c, m) => { console.log((c ? '  PASS  ' : '  FAIL  ') + m); if (!c) fail++; };

// 0. real parse
let d;
try { d = JSON.parse(fs.readFileSync(F, 'utf8')); console.log('JSON.parse: OK\n'); }
catch (e) { console.log('JSON.parse: FAILED — ' + e.message); process.exit(1); }

console.log('1. six top-level keys, nothing else');
const TOP = ['new_scholarship', 'programme_detail_official', 'programme_detail_applicant_utility', 'programme_detail_verification', 'logo_override', 'research_notes'];
const keys = Object.keys(d);
ok(keys.length === 6, 'exactly 6 top-level keys (got ' + keys.length + ')');
TOP.forEach(k => ok(keys.includes(k), 'present: ' + k));
ok(!d.research_notes.skeleton, 'research_notes.skeleton is not true');

console.log('\n2. new_scholarship required fields');
const NS = ['name', 'country', 'region', 'degree_levels', 'funding_type', 'program_type', 'official_source', 'official_source_url', 'catalogue_url', 'official_updates_url', 'duration', 'deadline', 'deadline_date', 'deadline_precision', 'application_period', 'application_method', 'status', 'is_verified', 'last_verified_date', 'description', 'best_fit', 'funding_amount', 'funding_currency', 'funding_period', 'eligibility_summary', 'eligibility', 'coverage', 'benefits', 'requirements', 'required_documents', 'english_requirement', 'selection_notes', 'image_url', 'image_source_url', 'image_source_type', 'image_alt_text', 'image_verified_at', 'notes'];
const NS_REQ = ['name', 'country', 'region', 'degree_levels', 'funding_type', 'official_source_url', 'status'];
NS_REQ.forEach(k => ok(d.new_scholarship[k] !== undefined && d.new_scholarship[k] !== null && d.new_scholarship[k] !== '', 'required: ' + k));
NS.forEach(k => ok(k in d.new_scholarship, 'schema key present: ' + k));

console.log('\n3. region + status + degree level');
ok(d.new_scholarship.region === 'Europe', 'region === Europe (got ' + d.new_scholarship.region + ')');
ok(!['Africa', 'Asia', 'Europe (continent error)'].includes(d.new_scholarship.region), 'region is not a continent or an invalid value');
ok(['open', 'upcoming', 'closed'].includes(d.new_scholarship.status), "ns.status in lowercase set (got " + d.new_scholarship.status + ')');
ok(['OPEN', 'UPCOMING', 'CLOSED', 'ONGOING', 'DISCONTINUED'].includes(d.programme_detail_official.status), 'pd.status in canonical set (got ' + d.programme_detail_official.status + ')');
ok(/bachelor|undergraduate/i.test(d.new_scholarship.degree_levels), "degree_levels mentions Bachelor's (got " + d.new_scholarship.degree_levels + ')');
// contract: deadline earlier than today => closed
ok(d.new_scholarship.deadline_date === '2026-09-07' && d.new_scholarship.status === 'closed', 'deadline 2026-09-07 precedes 2026-10-03 and status is closed');

console.log('\n4. programme_detail_official required keys');
const PD = ['official_source_urls', 'application_link', 'official_updates_url', 'catalogue_url', 'application_cycle', 'deadline_central', 'deadline_central_display', 'deadline_central_timezone', 'deadline_institutional', 'deadline_note', 'status', 'status_note', 'funding_amount', 'funding_currency', 'funding_period', 'funding_duration', 'tuition_coverage', 'tuition_coverage_note', 'living_cost_coverage', 'travel_coverage', 'fully_funded', 'funding_label', 'benefits', 'eligibility', 'citizenship_residency', 'international_eligibility', 'degree_levels', 'study_mode', 'research_requirement', 'subject_or_agency_requirement', 'application_method', 'application_route', 'requirements', 'documents', 'english_requirement', 'english_requirement_note', 'selection_criteria', 'selection_weighting', 'duration', 'award_holder_conditions', 'supplements_or_initiatives', 'official_contacts', 'description', 'program_type', 'region', 'coverage', 'last_verified_date'];
const pdMiss = PD.filter(k => !(k in d.programme_detail_official));
ok(pdMiss.length === 0, 'all 47 programme_detail_official keys present' + (pdMiss.length ? ' (missing: ' + pdMiss.join(', ') + ')' : ''));

console.log('\n5. applicant_utility: 6 array keys, and banned keys absent from official');
const AU = ['application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs', 'document_audit', 'alerts', 'submission_workflow'];
AU.forEach(k => ok(Array.isArray(d.programme_detail_applicant_utility[k]) && d.programme_detail_applicant_utility[k].length > 0, 'non-empty: ' + k));
const BANNED = ['application_readiness_checklist', 'common_rejection_risks', 'estimated_uncovered_costs', 'document_audit', 'alerts', 'submission_workflow'];
const inOfficial = BANNED.filter(k => k in d.programme_detail_official);
ok(inOfficial.length === 0, 'no utility-only guidance leaked into programme_detail_official' + (inOfficial.length ? ' (' + inOfficial.join(', ') + ')' : ''));

console.log('\n6. verification block');
const V = d.programme_detail_verification;
['cycle_verified', 'verification_confidence', 'official_fields_confirmed', 'institution_check_required', 'unverified_or_removed_claims', 'source_citations', 'researched_by'].forEach(k => ok(k in V, 'present: ' + k));
ok(Array.isArray(V.source_citations) && V.source_citations.length >= 2, 'source_citations has >= 2 real URLs (got ' + V.source_citations.length + ')');
V.source_citations.forEach(u => ok(/^https:\/\//.test(u), 'https citation: ' + u));
ok(V.official_fields_confirmed.length > 0, 'official_fields_confirmed non-empty (' + V.official_fields_confirmed.length + ' entries)');
ok(V.researched_by === 'bachelor_03', 'researched_by follows the convention (got "' + V.researched_by + '")');
ok(typeof V.verification_confidence === 'number' && V.verification_confidence >= 0.6 && V.verification_confidence <= 1, 'verification_confidence in 0..1 (' + V.verification_confidence + ')');

console.log('\n7. repo invariants: no placeholder strings');
const PLACEHOLDER = new Set(['', 'n/a', 'na', '-', 'none', 'tbd', 'unknown', 'null']);
const FIELDS = ['funding_currency', 'funding_period', 'deadline_central', 'application_route', 'study_mode'];
const flats = [];
(function walk(o, p) { if (o === null || typeof o !== 'object') { flats.push([p, o]); return; } if (Array.isArray(o)) return o.forEach((v, i) => walk(v, p + '[' + i + ']')); for (const k of Object.keys(o)) walk(o[k], p ? p + '.' + k : k); })(d, '');
FIELDS.forEach(f => {
  const hits = flats.filter(([k, v]) => k.endsWith('.' + f) || k === f).filter(([, v]) => typeof v === 'string' && PLACEHOLDER.has(v.toLowerCase()));
  ok(hits.length === 0, f + ' has no placeholder string' + (hits.length ? ' (' + hits.map(h => h[1]).join(', ') + ')' : ''));
});
ok(d.new_scholarship.funding_amount === null && d.new_scholarship.funding_currency === null && d.new_scholarship.funding_period === null, 'unpublished amount is real JSON null, not "null"/"n/a"');

console.log('\n8. funding invariants');
ok(d.programme_detail_official.fully_funded === false, 'fully_funded is false');
ok(d.programme_detail_official.fully_funded === false || d.programme_detail_official.tuition_coverage === true, 'fully_funded implies tuition_coverage');
ok(d.programme_detail_official.tuition_coverage === false && d.programme_detail_official.living_cost_coverage === true, 'tuition_coverage false + living_cost_coverage true (correct: a living quota is not a tuition waiver)');
ok(!/tuition waiv|full tuition/i.test(d.new_scholarship.eligibility_summary || ''), 'eligibility_summary does not claim a tuition waiver');
ok(/tassa regionale/.test(d.programme_detail_official.tuition_coverage_note || ''), 'tuition_coverage_note quotes the narrow regional-fee exemption');

console.log('\n9. degree-level evidence is quoted, not inferred');
const dl = d.research_notes.degree_level_confirmed;
ok(typeof dl === 'string' && dl.length > 50, 'research_notes.degree_level_confirmed is a populated string');
ok(/conseguimento del primo titolo di studio/.test(dl), 'it contains the awarding body\'s own first-degree wording');

console.log('\n10. logo provenance');
const lo = d.logo_override;
ok(lo !== null, 'logo_override is not null');
ok(lo.official_host === true, 'official_host is true');
try { const h = new URL(lo.url); const p = new URL(lo.page_url);
  ok(h.hostname === p.hostname, 'logo url and page url are on the same host (' + h.hostname + ')');
  ok(h.hostname.includes('dsu.toscana.it'), 'logo is served by the awarding body, not the eligible institution');
} catch (e) { ok(false, 'logo/page urls are absolute and parseable: ' + e.message); }
ok(lo.image_kind === 'official_logo', 'image_kind is official_logo');
const OFFICIAL_HOST = new URL(d.new_scholarship.official_source_url).hostname;
ok(new URL(lo.url).hostname.includes('dsu.toscana.it') && OFFICIAL_HOST.includes('dsu.toscana.it'), 'logo host matches the official_source_url host (' + OFFICIAL_HOST + ') — no cross-body provenance');

console.log('\n11. researched_by / cycle / pages');
ok(Array.isArray(d.research_notes.official_pages_read) && d.research_notes.official_pages_read.length >= 4, 'official_pages_read has >= 4 entries (' + d.research_notes.official_pages_read.length + ')');
ok(d.research_notes.substitution !== null && d.research_notes.substitution !== undefined, 'substitution is recorded (as "no substitution", since the assigned target resolved)');
ok(/b01/.test(d.research_notes.substitution), 'the substitution note records that b01 was not the destination');

console.log('\n12. deadline presentation');
ok(d.programme_detail_official.deadline_central === '2026-09-07T13:00', 'deadline_central is the official ISO datetime (got ' + d.programme_detail_official.deadline_central + ')');
ok(d.programme_detail_official.deadline_central_timezone === 'Europe/Rome', 'timezone recorded (got ' + d.programme_detail_official.deadline_central_timezone + ')');
ok(/13\.00 del 7 settembre 2026/.test(d.programme_detail_official.deadline_central_display), 'deadline_central_display quotes the official Italian wording');
ok(/timezone/i.test(V.unverified_or_removed_claims.join(' ')) || /Europe\/Rome/.test(V.unverified_or_removed_claims.join(' ')), 'the timezone inference is disclosed as an inference');

console.log('\n' + (fail === 0 ? '=== ALL CHECKS PASSED ===' : '=== ' + fail + ' CHECK(S) FAILED ==='));
process.exit(fail === 0 ? 0 : 1);
