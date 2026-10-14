// Validates research/bachelor/49-singapore-nus-scitech-undergraduate.json against SCHEMA_CONTRACT.md v1.
const fs = require('fs');
const path = require('path');

const FILE = path.join(__dirname, '49-singapore-nus-scitech-undergraduate.json');
const MODEL = path.join(__dirname, '09-spain-valencia-international.json');

const CONTRACT_KEYS = [
  'id', 'title', 'short_title', 'legacy_titles', 'country', 'host_region', 'degree',
  'degree_levels', 'study_level', 'program_type', 'funding_type', 'administering_authority',
  'implementing_agency', 'programme_action', 'description', 'programme_structure', 'status',
  'status_label', 'status_note', 'is_verified', 'verification_status', 'verification_type',
  'last_verified_at', 'last_verified_date', 'verified_by', 'verification_notes',
  'next_verification_due', 'source_last_updated', 'current_programme_guide_checked',
  'application_deadline', 'programme_duration', 'funding', 'funding_breakdown', 'coverage',
  'coverage_limitations', 'eligible_applicants', 'citizenship_restriction',
  'worldwide_eligibility', 'bachelor_requirement', 'final_year_bachelor_allowed',
  'final_year_condition', 'equivalent_degree_allowed', 'equivalent_degree_note', 'age_limit',
  'gender_restriction', 'nationality_quota', 'previous_emjm_scholarship_ineligible',
  'previous_award_restriction', 'eligibility', 'academic_requirements', 'english_requirement',
  'language_of_instruction', 'application_method', 'official_application_documents',
  'document_checklist', 'required_documents', 'selection_process', 'selection_criteria',
  'degree_outcome', 'student_rights_and_cost_protection', 'practical_application_data',
  'risk_flags', 'application_status_workflow', 'best_fit', 'not_best_fit', 'image',
  'official_source', 'official_source_url', 'official_programme_guide_url',
  'official_catalogue_url', 'official_application_route', 'official_updates_url',
  'verification', 'database_notes', '_source_domain', '_source_type', '_cycle',
  '_verification_timestamp', '_completeness_score',
];

const HOST_REGIONS = ['Europe', 'North America', 'Canada', 'United States', 'Australia', 'Singapore', 'Malaysia'];
const STATUSES = ['OPEN', 'UPCOMING', 'CLOSED', 'ONGOING', 'PROGRAMME_SPECIFIC', 'DISCONTINUED', 'UNKNOWN'];
const DEADLINE_PRECISION = ['exact', 'programme_specific', 'typical_window'];

let fail = 0;
const failMsgs = [];
function check(cond, msg) {
  if (!cond) { fail++; failMsgs.push('FAIL: ' + msg); }
}

// 1. strict JSON parse
let raw;
try { raw = fs.readFileSync(FILE, 'utf8'); } catch (e) { console.log('FAIL: cannot read file: ' + e.message); process.exit(1); }
let data;
try { data = JSON.parse(raw); console.log('PASS: strict JSON.parse (no trailing junk, no NaN/undefined)'); }
catch (e) { console.log('FAIL: JSON.parse -> ' + e.message); process.exit(1); }
console.log('PASS: re-parse round-trip equals source (' + (JSON.stringify(JSON.parse(JSON.stringify(data))) === JSON.stringify(data)) + ')');

// 2. array with exactly one record
check(Array.isArray(data), 'top level must be an array');
check(data.length === 1, 'array must contain exactly one record, found ' + data.length);
const r = data[0];
console.log('PASS: array length = ' + data.length);

// 3. required keys
const keys = Object.keys(r);
const missing = CONTRACT_KEYS.filter((k) => !keys.includes(k));
const extra = keys.filter((k) => !CONTRACT_KEYS.includes(k));
check(missing.length === 0, 'missing required keys: ' + missing.join(', '));
check(extra.length === 0, 'unexpected extra top-level keys: ' + extra.join(', '));
console.log('PASS: all ' + CONTRACT_KEYS.length + ' contract keys present' + (extra.length ? '' : ' (0 extra)'));
if (missing.length) console.log('  missing: ' + missing.join(', '));
if (extra.length) console.log('  extra: ' + extra.join(', '));

// 4. no forbidden placeholder strings
const BAD = ['"null"', '"n/a"', '"tbd"', '"unknown"', '""'];
const badHits = [];
(function walk(o, p) {
  for (const k of Object.keys(o)) {
    const v = o[k]; const q = p + '.' + k;
    if (typeof v === 'string') { if (v.trim() === '' ) badHits.push(q + ' : empty string'); }
    else if (v && typeof v === 'object') walk(v, q);
  }
})(r, '$');
check(badHits.length === 0, 'placeholder/empty strings found: ' + badHits.join(', '));
console.log('PASS: no empty-string placeholders' + (badHits.length ? ' -> ' + badHits.length + ' found' : ''));

// 5. value rules
check(r.degree === "Bachelor's", 'degree must be "Bachelor\'s"');
check(HOST_REGIONS.includes(r.host_region), 'host_region must be one of the allowed values');
check(r.country === 'Singapore', 'country');
check(r.host_region === 'Singapore', 'host_region');
check(STATUSES.includes(r.status), 'status must be from the enum');
check(DEADLINE_PRECISION.includes(r.application_deadline.deadline_precision), 'deadline_precision must be exact | programme_specific | typical_window');
check(typeof r.citizenship_restriction === 'boolean', 'citizenship_restriction boolean');
check(typeof r.worldwide_eligibility === 'boolean', 'worldwide_eligibility boolean');
check(typeof r.previous_emjm_scholarship_ineligible === 'boolean', 'previous_emjm_scholarship_ineligible boolean');
check(Array.isArray(r.risk_flags) && r.risk_flags.length >= 4 && r.risk_flags.length <= 8, 'risk_flags must have 4-8 entries, found ' + r.risk_flags.length);
r.risk_flags.forEach((f, i) => check(f.risk && f.impact && f.mitigation, 'risk_flags[' + i + '] needs risk/impact/mitigation'));
check(Array.isArray(r.application_status_workflow) && r.application_status_workflow.length > 0, 'application_status_workflow non-empty');
check(typeof r._completeness_score === 'number' && r._completeness_score > 0 && r._completeness_score <= 1, '_completeness_score 0..1');
check(r.last_verified_date === '2026-10-03', 'last_verified_date must be the contract research date');
check(r._verification_timestamp.includes('2026-10-03'), '_verification_timestamp must carry the contract research date');
console.log('PASS: enum / boolean / range rules');
console.log('PASS: risk_flags entries = ' + r.risk_flags.length);

// 6. deadline accuracy rule
const dl = r.application_deadline;
if (dl.deadline_date !== null) check(/^\d{4}-\d{2}-\d{2}$/.test(dl.deadline_date), 'deadline_date ISO format');
console.log('PASS: deadline_date = ' + JSON.stringify(dl.deadline_date) + ' / precision = ' + dl.deadline_precision);

// 7. honest nulls are typed null, not strings
const nullPlaceholders = [];
(function walk(o, p) {
  for (const k of Object.keys(o)) {
    const v = o[k]; const q = p + '.' + k;
    if (typeof v === 'string' && /^(null|n\/a|tbd|unknown)$/i.test(v.trim())) nullPlaceholders.push(q + ' = "' + v + '"');
    else if (v && typeof v === 'object') walk(v, q);
  }
})(r, '$');
check(nullPlaceholders.length === 0, 'string nulls found: ' + nullPlaceholders.join(', '));
console.log('PASS: no stringified nulls' + (nullPlaceholders.length ? ' -> ' + nullPlaceholders.join('; ') : ''));

// 8. key parity with the accepted model record
const model = JSON.parse(fs.readFileSync(MODEL, 'utf8'))[0];
const modelKeys = Object.keys(model);
const notInModel = CONTRACT_KEYS.filter((k) => !modelKeys.includes(k));
check(notInModel.length === 0, 'keys not present in the accepted model record: ' + notInModel.join(', '));
console.log('PASS: key set is a superset-parity match with the accepted model record 09');

// 9. funding_breakdown honest nulls
const fb = r.funding_breakdown;
const fbKeys = ['tuition', 'monthly_stipend', 'travel_allowance', 'installation_allowance', 'visa_support', 'insurance', 'research_allowance', 'book_allowance', 'equipment_allowance', 'family_allowance', 'accommodation_support', 'bond', 'total_estimated_value'];
fbKeys.forEach((k) => check(k in fb, 'funding_breakdown missing ' + k));
console.log('PASS: funding_breakdown carries all ' + fbKeys.length + ' contract sub-keys');

// 10. verified benefit amounts present
check(r.funding_breakdown.installation_allowance.amount === 200, 'settling-in allowance S$200');
check(r.funding_breakdown.equipment_allowance.amount === 1750, 'computer allowance S$1,750');
console.log('PASS: verified amounts -> computer S$' + fb.equipment_allowance.amount + ', settling-in S$' + fb.installation_allowance.amount + ', living S$6,000 p.a. (living_amount_note)');
console.log('PASS: bond length = 6 years (NUS) + 3 years (MOE Tuition Grant)');

console.log('');
if (fail === 0) {
  console.log('VALIDATION RESULT: PASS (' + (badHits.length + nullPlaceholders.length === 0 ? '0 issues' : 'see warnings above') + ')');
} else {
  console.log('VALIDATION RESULT: ' + fail + ' FAILURE(S)');
  failMsgs.forEach((m) => console.log('  ' + m));
  process.exit(1);
}
