const fs = require('fs');
const file = process.argv[2];
const raw = fs.readFileSync(file, 'utf8');
const j = JSON.parse(raw);

console.log('FILE: ' + file);
console.log('PARSE OK | is array: ' + Array.isArray(j) + ' | records: ' + j.length);
const r = j[0];

const s = JSON.stringify(j);
const bad = [];
if (s.includes('"tbd"')) bad.push('"tbd"');
if (s.includes('"n/a"')) bad.push('"n/a"');
console.log('Fake-null/empty check (substring): ' + (bad.length ? 'FAIL ' + bad.join(', ') : 'PASS'));

function walk(o, path) {
  if (o === null || typeof o !== 'object') return [];
  const out = [];
  for (const k of Object.keys(o)) {
    const v = o[k];
    if (typeof v === 'string' && ['null', 'tbd', 'n/a', 'unknown', 'N/A', 'TBD', 'None'].includes(v.trim())) out.push(path + '.' + k + ' = ' + JSON.stringify(v));
    if (typeof v === 'string' && v.trim() === '') out.push('EMPTY ' + path + '.' + k);
    if (v && typeof v === 'object') out.push(...walk(v, path + '.' + k));
  }
  return out;
}
const fakes = walk(r, 'root');
console.log('Fake null-like / empty strings (deep): ' + (fakes.length ? 'FAIL ' + fakes.slice(0, 10).join(', ') : 'PASS'));
console.log('Bytes: ' + Buffer.byteLength(raw));

console.log('--- identity ---');
console.log('id: ' + r.id);
console.log('title: ' + r.title);
console.log('short_title: ' + r.short_title);
console.log('country: ' + r.country + ' | host_region: ' + r.host_region);
console.log('degree: ' + r.degree + ' | degree_levels: ' + JSON.stringify(r.degree_levels));
console.log('study_level: ' + r.study_level);

console.log('--- status / deadline ---');
console.log('status: ' + r.status + ' | label: ' + r.status_label);
console.log('deadline_date: ' + r.application_deadline.deadline_date);
console.log('deadline_precision: ' + r.application_deadline.deadline_precision);
console.log('single_central_deadline: ' + r.application_deadline.single_central_deadline);

console.log('--- key money facts ---');
console.log('Tier1 value: ' + r.funding_breakdown.accommodation_support.amount + ' ' + r.funding_breakdown.accommodation_support.currency);
console.log('fully_funded: ' + r.funding.fully_funded);
console.log('tuition covered by award: ' + r.funding_breakdown.tuition.covered);

console.log('--- image ---');
console.log('logo_url: ' + r.image.logo_url);
console.log('logo_verified: ' + r.image.logo_verified + ' | at ' + r.image.logo_verified_at);
console.log('image_verified: ' + r.image.image_verified);

console.log('--- verification ---');
console.log('verification_status: ' + r.verification.verification_status);
console.log('is_verified: ' + r.is_verified + ' | verification_status: ' + r.verification_status);
console.log('confidence: ' + r.verification.verification_confidence);
console.log('citations: ' + r.verification.source_citations.length);
console.log('official_fields_confirmed: ' + r.verification.official_fields_confirmed.length);
console.log('programme_check_required: ' + r.verification.programme_check_required.length);
console.log('unverified_or_removed_claims: ' + r.verification.unverified_or_removed_claims.length);
console.log('_completeness_score: ' + r._completeness_score);

console.log('--- contract key coverage ---');
const expected = ['id','title','short_title','legacy_titles','country','host_region','degree','degree_levels','study_level','program_type','funding_type','administering_authority','implementing_agency','programme_action','description','programme_structure','status','status_label','status_note','is_verified','verification_status','verification_type','last_verified_at','last_verified_date','verified_by','verification_notes','next_verification_due','source_last_updated','current_programme_guide_checked','application_deadline','programme_duration','funding','funding_breakdown','coverage','coverage_limitations','eligible_applicants','citizenship_restriction','worldwide_eligibility','bachelor_requirement','final_year_bachelor_allowed','final_year_condition','equivalent_degree_allowed','equivalent_degree_note','age_limit','gender_restriction','nationality_quota','previous_emjm_scholarship_ineligible','eligibility','academic_requirements','english_requirement','language_of_instruction','application_method','official_application_documents','document_checklist','required_documents','selection_process','selection_criteria','degree_outcome','student_rights_and_cost_protection','practical_application_data','risk_flags','application_status_workflow','best_fit','not_best_fit','image','official_source','official_source_url','official_programme_guide_url','official_catalogue_url','official_application_route','official_updates_url','verification','database_notes','_source_domain','_source_type','_cycle','_verification_timestamp','_completeness_score'];
const missing = expected.filter(k => !(k in r));
console.log('required keys: ' + expected.length + ' | present: ' + (expected.length - missing.length) + ' | missing: ' + (missing.length ? missing.join(', ') : 'NONE'));

console.log('--- risk flags shape ---');
console.log('risk_flags count: ' + r.risk_flags.length + ' (contract requires 4-8: ' + (r.risk_flags.length >= 4 && r.risk_flags.length <= 8) + ')');
console.log('all have {risk,impact,mitigation}: ' + r.risk_flags.every(x => x.risk && x.impact && x.mitigation));

console.log('--- official source url ---');
console.log('official_source_url: ' + r.official_source_url);
console.log('official_catalogue_url: ' + r.official_catalogue_url);
console.log('official_programme_guide_url: ' + r.official_programme_guide_url);
console.log('official_updates_url: ' + r.official_updates_url);
