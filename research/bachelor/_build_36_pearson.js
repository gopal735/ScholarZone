// SLOT 36 build + validation: merges the four parts, enforces SCHEMA_CONTRACT.md key
// order, validates required nested shapes, then writes the JSON array atomically and
// re-reads + parses the written file to confirm it was actually saved.
const fs = require('fs');
const path = require('path');

const OUT = path.join('research', 'bachelor', '36-canada-toronto-pearson.json');
const B = (n) => require('./_build_36_pearson.part' + n + '.js');

// --- 1. Required top-level keys, in the exact order mandated by SCHEMA_CONTRACT.md ----
const REQUIRED = [
  'id','title','short_title','legacy_titles','country','host_region','degree','degree_levels','study_level',
  'program_type','funding_type','administering_authority','implementing_agency','programme_action','description',
  'programme_structure','status','status_label','status_note','is_verified','verification_status','verification_type',
  'last_verified_at','last_verified_date','verified_by','verification_notes','next_verification_due',
  'source_last_updated','current_programme_guide_checked','application_deadline','programme_duration','funding',
  'funding_breakdown','coverage','coverage_limitations','eligible_applicants','citizenship_restriction',
  'worldwide_eligibility','bachelor_requirement','final_year_bachelor_allowed','final_year_condition',
  'equivalent_degree_allowed','equivalent_degree_note','age_limit','gender_restriction','nationality_quota',
  'previous_emjm_scholarship_ineligible','previous_award_restriction','eligibility','academic_requirements','english_requirement',
  'language_of_instruction','application_method','official_application_documents','document_checklist',
  'required_documents','selection_process','selection_criteria','degree_outcome','student_rights_and_cost_protection',
  'practical_application_data','risk_flags','application_status_workflow','best_fit','not_best_fit','image',
  'official_source','official_source_url','official_programme_guide_url','official_catalogue_url',
  'official_application_route','official_updates_url','verification','database_notes','_source_domain',
  '_source_type','_cycle','_verification_timestamp','_completeness_score'
];

// --- 2. Merge in contract order -------------------------------------------------------
const parts = [B(1), B(2), B(3), B(4)];
const record = {};
for (const p of parts) Object.assign(record, p);
const keys = Object.keys(record);

const problems = [];
const missing = REQUIRED.filter((k) => !(k in record));
const extra = keys.filter((k) => !REQUIRED.includes(k));
if (missing.length) problems.push('MISSING keys: ' + missing.join(', '));
if (extra.length) problems.push('EXTRA top-level keys (contract allows extras only in open maps): ' + extra.join(', '));
if (keys.length !== REQUIRED.length) problems.push('key count ' + keys.length + ' != required ' + REQUIRED.length);

// verify the order matches the contract exactly
const orderOk = keys.every((k, i) => k === REQUIRED[i]);
if (!orderOk) {
  const firstDiff = keys.findIndex((k, i) => k !== REQUIRED[i]);
  problems.push('ORDER mismatch at index ' + firstDiff + ': got "' + keys[firstDiff] + '" expected "' + REQUIRED[firstDiff] + '"');
}

// --- 3. Nested-shape validation ------------------------------------------------------
const TYPE = {
  id: 'string', title: 'string', short_title: 'string', legacy_titles: 'array', country: 'string',
  host_region: 'string', degree: 'string', degree_levels: 'array', study_level: 'string', program_type: 'string',
  funding_type: 'string', administering_authority: 'string', implementing_agency: 'string',
  programme_action: 'string', description: 'string', programme_structure: 'object', status: 'string',
  status_label: 'string', status_note: 'string', is_verified: 'boolean', verification_status: 'string',
  verification_type: 'string', last_verified_at: 'string', last_verified_date: 'string', verified_by: 'string',
  verification_notes: 'string', next_verification_due: 'string', source_last_updated: 'string',
  current_programme_guide_checked: 'boolean', application_deadline: 'object', programme_duration: 'object',
  funding: 'object', funding_breakdown: 'object', coverage: 'array', coverage_limitations: 'array',
  eligible_applicants: 'array', citizenship_restriction: 'boolean', worldwide_eligibility: 'boolean',
  bachelor_requirement: 'boolean', final_year_bachelor_allowed: 'boolean', final_year_condition: 'string',
  equivalent_degree_allowed: 'boolean', equivalent_degree_note: 'string', age_limit: 'object',
  gender_restriction: 'boolean', nationality_quota: 'string', previous_emjm_scholarship_ineligible: 'boolean',
  eligibility: 'object', academic_requirements: 'object', english_requirement: 'object',
  language_of_instruction: 'object', application_method: 'object', official_application_documents: 'object',
  document_checklist: 'object', required_documents: 'array', selection_process: 'object',
  selection_criteria: 'object', degree_outcome: 'object', student_rights_and_cost_protection: 'object',
  practical_application_data: 'object', risk_flags: 'array', application_status_workflow: 'array',
  best_fit: 'string', not_best_fit: 'array', image: 'object', official_source: 'string',
  official_source_url: 'string', official_programme_guide_url: 'string', official_catalogue_url: 'string',
  official_application_route: 'string', official_updates_url: 'string', verification: 'object',
  database_notes: 'array', _source_domain: 'string', _source_type: 'string', _cycle: 'string',
  _verification_timestamp: 'string', _completeness_score: 'number'
};
for (const [k, t] of Object.entries(TYPE)) {
  const v = record[k];
  if (v === null) continue; // null allowed only where the source publishes nothing
  const actual = Array.isArray(v) ? 'array' : typeof v;
  if (actual !== t) problems.push('TYPE "' + k + '": expected ' + t + ', got ' + actual);
}

const NEED = {
  application_deadline: ['single_central_deadline','deadline_date','deadline_timezone','deadline_precision','typical_application_window','application_period','official_rule','deadline_warning','next_verification_due'],
  programme_duration: ['official_range','duration_years','normal_duration_years','duration_months','renewable','renewal_note'],
  funding: ['scholarship_available','scholarship_type','scholarship_currency','monthly_amount','monthly_amount_note','travel_support','visa_support','installation_support','living_allowance','insurance','travel_amount','travel_amount_note','institutional_costs','fully_funded','fully_funded_note'],
  age_limit: ['minimum_age','maximum_age','age_calculation_date','official_source'],
  eligibility: ['citizenship','residence_requirement','age_limit','secondary_school_requirement','academic_requirements','gpa_requirement','language_requirement','work_experience','extracurricular_requirement','leadership_requirement','financial_need','previous_scholarship_restriction','enrolment_status_requirement','health_requirement','field_restrictions','official_source'],
  academic_requirements: ['fixed_percentage_requirement','percentage_note','programme_specific_requirements','selection_factors_may_include','holistic_selection_note'],
  english_requirement: ['universal_requirement','minimum_ielts','minimum_toefl','minimum_pte','minimum_duolingo','moi_rule','moi_accepted','test_score_note','test_validity_months','accepted_tests'],
  language_of_instruction: ['programme_specific','possible_languages','bilingual_programmes','language_note'],
  application_method: ['direct_student_application','central_application','application_route','portal_url','application_steps','application_fee','multiple_applications_allowed','paper_application_available'],
  official_application_documents: ['universal_documents','commonly_requested_documents','two_recommendation_letters','secondary_school_documents','document_language','document_format','transcript_requirement','certified_translation_requirement'],
  document_checklist: ['identity_documents','academic_documents','language_documents','recommendation_documents','application_essays','financial_documents','additional_documents'],
  selection_process: ['decision_maker','selection_type','central_selection','possible_stages','official_universal_weighting','weighting_note','interview_possible','results_timing','scholarship_rank_note'],
  selection_criteria: ['academic_excellence','leadership','community_service','extracurricular_achievement','financial_need','additional_factors','interview_required','portfolio_required','source'],
  degree_outcome: ['awarded_qualification','typical_programme_length','possible_awards','degree_note','credit_transfer'],
  student_rights_and_cost_protection: ['tuition_fee_for_recipients','application_fee_for_recipients','student_agreement','programme_website','common_services','bond_requirement','bond_breach_consequence'],
  practical_application_data: ['application_readiness_checklist','programme_comparison_fields','motivation_letter_strategy','profile_fit_labels','common_mistakes'],
  image: ['logo_url','logo_source_url','logo_source_type','logo_verified','logo_verified_at','logo_verification_method','image_url','image_source_url','image_source_type','image_verified','image_verified_at','image_alt_text','image_usage_note'],
  verification: ['is_verified','verification_status','last_verified_at','last_verified_date','verification_date_meaning','verified_by','source_type','source_domain','verification_confidence','official_fields_confirmed','programme_check_required','unverified_or_removed_claims','source_citations']
};
for (const [parent, kids] of Object.entries(NEED)) {
  const obj = record[parent];
  if (!obj || typeof obj !== 'object') { problems.push('NESTED parent missing: ' + parent); continue; }
  for (const k of kids) if (!(k in obj)) problems.push('NESTED "' + parent + '.' + k + '" missing');
}

// --- 4. Value sanity (no invented dates, no forbidden claims) ------------------------
if (record.status !== 'OPEN' && record.status !== 'UPCOMING' && record.status !== 'CLOSED' &&
    record.status !== 'ONGOING' && record.status !== 'PROGRAMME_SPECIFIC' &&
    record.status !== 'DISCONTINUED' && record.status !== 'UNKNOWN') {
  problems.push('status not in the allowed enum: ' + record.status);
}
if (!/^2026-10-10$/.test(record.last_verified_date)) problems.push('last_verified_date must be the real verification date');
if (record._completeness_score < 0 || record._completeness_score > 1) problems.push('_completeness_score out of range');
if (record.risk_flags.length < 4 || record.risk_flags.length > 8) problems.push('risk_flags must have 4-8 entries, has ' + record.risk_flags.length);
if (record.host_region !== 'Canada') problems.push('host_region must be Canada for this slot');
if (record.degree !== "Bachelor's") problems.push("degree must be Bachelor's");
if (!Array.isArray(record.legacy_titles)) problems.push('legacy_titles must be an array');
// the unverified premise must not be asserted anywhere in the record
const flat = JSON.stringify(record);
if (/"funded by the Government of Canada"/i.test(flat) && !record.database_notes.join(' ').includes('could not be confirmed')) {
  problems.push('Government of Canada funding claim detected outside the disclosure notes');
}
if (record.official_source_url.indexOf('utoronto.ca') === -1) problems.push('official_source_url must be an official utoronto.ca URL');

// --- 5. Write atomically, then re-read and re-parse to confirm the save -------------
if (problems.length) {
  console.error('VALIDATION FAILED before write:');
  problems.forEach((p) => console.error('  - ' + p));
  process.exit(1);
}

const payload = JSON.stringify([record], null, 2) + '\n';
const tmp = OUT + '.tmp';
fs.writeFileSync(tmp, payload, 'utf8');
// confirm the temp file parses before replacing the destination
JSON.parse(fs.readFileSync(tmp, 'utf8'));
fs.renameSync(tmp, OUT);

// independent re-read of the destination
const reread = fs.readFileSync(OUT, 'utf8');
const parsed = JSON.parse(reread);
if (!Array.isArray(parsed) || parsed.length !== 1) { console.error('POST-WRITE: not a 1-element array'); process.exit(1); }
const rereadKeys = Object.keys(parsed[0]);
if (rereadKeys.length !== REQUIRED.length) { console.error('POST-WRITE key count mismatch'); process.exit(1); }

console.log('WRITE OK -> ' + OUT);
console.log('  bytes on disk      : ' + fs.statSync(OUT).size);
console.log('  top-level keys     : ' + rereadKeys.length + ' / ' + REQUIRED.length);
console.log('  extras beyond contract: ' + (keys.length - REQUIRED.length));
console.log('  key order matches contract: ' + rereadKeys.every((k, i) => k === REQUIRED[i]));
console.log('  id                 : ' + parsed[0].id);
console.log('  title              : ' + parsed[0].title);
console.log('  status             : ' + parsed[0].status + ' | deadline_date: ' + parsed[0].application_deadline.deadline_date + ' (' + parsed[0].application_deadline.deadline_precision + ')');
console.log('  logo_url           : ' + parsed[0].image.logo_url + ' (verified: ' + parsed[0].image.logo_verified + ')');
console.log('  citations          : ' + parsed[0].verification.source_citations.length);
console.log('  unverified claims  : ' + parsed[0].verification.unverified_or_removed_claims.length);
console.log('  completeness       : ' + parsed[0]._completeness_score);
