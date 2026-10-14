// parity_b03.js â€” prove that the completed canonical record preserves every piece of
// evidence from the superseded sibling file, with an explicit allowlist of the fields
// that were deliberately changed. Nothing may be silently dropped.
const fs = require('fs');
const DIR = 'C:/Users/GopaL/Desktop/Projects folder/ScholarZone/research/bachelor/';
const OLD = JSON.parse(fs.readFileSync(DIR + 'b03-borse-di-studio-universita-di-pisa.json.superseded', 'utf8'));
const NEW = JSON.parse(fs.readFileSync(DIR + 'b03-universita-di-pisa-borse-di-studio.json', 'utf8'));

function walk(o, p, out) {
  if (o === null || typeof o !== 'object') { out.push([p, o]); return out; }
  if (Array.isArray(o)) { o.forEach((v, i) => walk(v, p + '[' + i + ']', out)); return out; }
  for (const k of Object.keys(o)) walk(o[k], p ? p + '.' + k : k, out);
  return out;
}
const flat = (o) => {
  const acc = [];
  walk(o, '', acc);
  return new Map(acc);
};

const oldFlat = flat(OLD);
const newFlat = flat(NEW);

// Fields intentionally changed in the finishing pass. Everything else must match.
const CHANGED_PREFIXES = [
  'new_scholarship.image_url',
  'new_scholarship.image_source_url',
  'new_scholarship.image_source_type',
  'new_scholarship.image_alt_text',
  'new_scholarship.image_verified_at',
  'new_scholarship.notes',
  'programme_detail_verification.researched_by',
  'programme_detail_verification.cycle_verified',
  'programme_detail_verification.verification_confidence',
  'programme_detail_verification.official_fields_confirmed',
  'programme_detail_verification.institution_check_required',
  'programme_detail_verification.unverified_or_removed_claims',
  'logo_override',
  'research_notes',
];

const lostInNew = [];   // present in old, missing entirely from new
const changedNot = [];  // differs but is not on the allowlist
const kept = [];

for (const [k, v] of oldFlat) {
  if (k === '') continue;
  if (!newFlat.has(k)) { lostInNew.push([k, v]); continue; }
  const nv = newFlat.get(k);
  if (JSON.stringify(v) !== JSON.stringify(nv)) {
    const allowed = CHANGED_PREFIXES.some(p => k === p || k.startsWith(p + '.') || k.startsWith(p + '['));
    if (!allowed) changedNot.push([k, v, nv]); else kept.push([k, 'allowed-change']);
  } else {
    if (!CHANGED_PREFIXES.some(p => k === p || k.startsWith(p + '.') || k.startsWith(p + '['))) kept.push([k, 'identical']);
  }
}

console.log('--- SUPERSeded file footprints checked: ' + oldFlat.size + ' leaf paths ---');
console.log('');
console.log('LOST (in old, absent from new): ' + lostInNew.length);
lostInNew.forEach(([k, v]) => console.log('   ' + k + ' = ' + JSON.stringify(v).substring(0, 120)));
console.log('');
console.log('DIFFERENT but NOT allowlisted (would be silent loss): ' + changedNot.length);
changedNot.forEach(([k, v, nv]) => console.log('   ' + k + '\n      old=' + JSON.stringify(v).substring(0, 160) + '\n      new=' + JSON.stringify(nv).substring(0, 160)));
console.log('');
console.log('PRESERVED: ' + kept.length + ' leaf paths');
const byKind = kept.reduce((a, [, k]) => (a[k] = (a[k] || 0) + 1, a), {});
console.log('   ' + JSON.stringify(byKind));

console.log('');
console.log('--- evidence-bearing arrays: old length -> new length ---');
for (const a of ['new_scholarship.eligibility', 'new_scholarship.coverage', 'new_scholarship.benefits',
  'new_scholarship.requirements', 'new_scholarship.required_documents',
  'programme_detail_official.benefits', 'programme_detail_official.eligibility',
  'programme_detail_official.requirements', 'programme_detail_official.documents',
  'programme_detail_official.selection_criteria', 'programme_detail_official.award_holder_conditions',
  'programme_detail_official.supplements_or_initiatives', 'programme_detail_official.degree_levels',
  'programme_detail_official.official_source_urls',
  'programme_detail_applicant_utility.application_readiness_checklist',
  'programme_detail_applicant_utility.common_rejection_risks',
  'programme_detail_applicant_utility.estimated_uncovered_costs',
  'programme_detail_applicant_utility.document_audit',
  'programme_detail_applicant_utility.alerts',
  'programme_detail_applicant_utility.submission_workflow',
  'research_notes.unverified', 'research_notes.official_pages_read',
  'programme_detail_verification.unverified_or_removed_claims',
  'programme_detail_verification.institution_check_required',
  'programme_detail_verification.official_fields_confirmed']) {
  const get = (o) => a.split('.').reduce((x, k) => (x && x[k] !== undefined ? x[k] : undefined), o);
  const o = get(OLD), n = get(NEW);
  console.log('   ' + a.padEnd(62) + ' ' + (Array.isArray(o) ? o.length : String(o)) + '  ->  ' + (Array.isArray(n) ? n.length : String(n)));
}

process.exit(lostInNew.length === 0 && changedNot.length === 0 ? 0 : 1);

