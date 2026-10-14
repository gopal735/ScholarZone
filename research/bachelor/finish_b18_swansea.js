const fs = require('fs');
const P = 'research/bachelor/b18-international-scholarship-ug-students-swansea.json';
const o = JSON.parse(fs.readFileSync(P, 'utf8'));
const ns = o.new_scholarship, off = o.programme_detail_official, v = o.programme_detail_verification, au = o.programme_detail_applicant_utility, rn = o.research_notes;

const URL_MAIN = 'https://www.swansea.ac.uk/international-students/my-finances/international-scholarships/international-excellence-scholarships/';
const URL_INDEX = 'https://www.swansea.ac.uk/international-students/my-finances/international-scholarships/';

// ---------- new_scholarship ----------
ns.name = 'International Excellence Scholarship';
ns.degree_levels = "Bachelor's (also open to postgraduate taught)";
ns.funding_type = 'Tuition fee discount';
ns.program_type = 'Entrance scholarship';
ns.duration = 'First year of study, with an additional second-year award on condition';
ns.deadline = '12:00 GMT on 27 November 2026, for January and March 2027 entry';
ns.deadline_date = '2026-11-27';
ns.deadline_precision = 'day_month_time';
ns.application_period = 'Applications close at 12:00 GMT on 27 November 2026. The published schemes are for January and March 2027 entry; no September intake is published on this page.';
ns.application_method = 'Separate application using the form for the applicant\'s country of ordinary residence';
ns.status = 'open';
ns.description = 'Swansea University International Excellence Scholarships are tuition-fee discounts of up to GBP 5,000 for the first year of study for overseas students who have demonstrated academic excellence or show potential to do so. Undergraduates who receive the full GBP 5,000 in year one can receive an additional GBP 2,000 in year two by achieving a minimum 70% average in year one.';
ns.best_fit = 'An overseas applicant with an offer of an undergraduate place at Swansea for January or March 2027 entry who has a strong academic record.';
ns.funding_amount = 5000;
ns.funding_currency = 'GBP';
ns.funding_period = 'first year of study';
ns.funding_note = 'A discount on tuition fees, not a cash payment. A second-year top-up of GBP 2,000 is conditional on a 70% year-one average.';
ns.eligibility = [
  'Overseas student, defined by country of ordinary residence, being the country where the applicant has been living for the last 5 years, excluding countries of residence purely for the purpose of studying',
  'Have received an offer to study an undergraduate course or a postgraduate taught course at Swansea University',
  'Apply using the form matching the applicant\'s country of ordinary residence - either the China scheme or the Rest of the World scheme',
  'Only one application per student is considered',
  'For the second-year award, achieve a minimum 70% average in the first year of study',
];
ns.eligibility_summary = 'Overseas students with an offer of an undergraduate or postgraduate taught place at Swansea, applying through the scheme for their country of ordinary residence (China or Rest of the World) by 12:00 GMT on 27 November 2026.';
ns.coverage = ['Discount on tuition fees of up to GBP 5,000 for the first year of study', 'An additional GBP 2,000 tuition discount in the second year for undergraduates achieving 70% in year one'];
ns.benefits = [
  'Up to GBP 5,000 tuition fee discount for the first year of study',
  'An additional GBP 2,000 in the second year for undergraduates who achieve a minimum 70% average in year one',
  'Separate application schemes for China and for the Rest of the World',
];
ns.requirements = [
  'Hold an offer of an undergraduate or postgraduate taught place at Swansea University',
  'Submit the scholarship form for the applicant\'s country of ordinary residence',
  'Include transcripts of previous studies',
  'Provide proof of average score or GPA issued by the institution, if no average or GPA appears on the transcript',
  'Achieve a minimum 70% average in year one to qualify for the second-year award',
];
ns.required_documents = [
  'Completed scholarship application form for the relevant country scheme',
  'Transcripts of previous studies',
  'Proof of average score or GPA issued by the institution, where the transcript does not show one',
];
ns.english_requirement = null;
ns.english_requirement_note = 'Not published on the scholarship page. Full eligibility is governed by the terms and conditions the page directs applicants to read, which were not fetched in this pass.';
ns.selection_notes = 'Awards are made to students who have demonstrated academic excellence or show potential to do so. Only one application per student is considered. The page states applicants must read the full terms and conditions to determine eligibility.';
ns.notes = 'The page states applicants must have received an offer to study an undergraduate course OR a postgraduate taught course, so this award is not bachelor-exclusive. It is recorded here because it is applicable to undergraduates. The page publishes January and March 2027 entry only; no September intake is published.';

// ---------- programme_detail_official ----------
off.official_source_urls = [URL_MAIN, URL_INDEX];
off.official_updates_url = URL_MAIN;
off.catalogue_url = URL_INDEX;
off.application_cycle = 'January and March 2027 entry';
off.deadline_central = '2026-11-27';
off.deadline_central_display = '12:00 GMT on 27 November 2026';
off.deadline_central_timezone = 'GMT';
off.deadline_institutional = '2026-11-27';
off.deadline_note = 'Both the China and Rest of the World schemes close at 12:00 GMT on 27 November 2026. The page links separate terms and conditions documents for each scheme, which state full eligibility; those documents were not fetched in this pass, so no term beyond what is on the page is asserted here.';
off.status = 'open';
off.status_note = 'Both schemes are open and close at 12:00 GMT on 27 November 2026, which was after the date of verification on 2026-10-03.';
off.funding_amount = 5000;
off.funding_currency = 'GBP';
off.funding_period = 'first year of study';
off.funding_duration = 'First year, plus a conditional second-year award';
off.tuition_coverage = true;
off.tuition_coverage_note = 'The award is explicitly a discount on tuition fees, not a cash grant. The page states the scholarship is worth up to GBP 5,000 for the first year of study.';
off.living_cost_coverage = false;
off.travel_coverage = false;
off.fully_funded = false;
off.funding_label = 'Up to GBP 5,000 tuition discount in year one, plus a conditional GBP 2,000 in year two';
off.benefits = [
  'Scholarships awarded as a discount on tuition fees worth up to GBP 5,000 for the first year of study',
  'Undergraduate students who receive the full GBP 5,000 in their first year will be awarded an additional GBP 2,000 in their second year if they achieve a minimum average of 70% in their first year',
  'Separate application schemes: International Excellence Scholarship (China) and International Excellence Scholarship (Rest of the World)',
  'Both schemes published for January and March 2027 entry',
  'An alternate application form is accepted where the Google form cannot be used',
];
off.eligibility = [
  'Be an overseas student, with country of ordinary residence defined as the country where the applicant has been living for the last 5 years, excluding countries where they reside purely for the purpose of studying',
  'Have received an offer to study an undergraduate course or a postgraduate taught course at Swansea University',
  'Complete the scholarship form that best represents the area of the applicant\'s country of ordinary residence',
  'Only one application per student will be considered',
  'Include transcripts of previous studies and provide proof of average score or GPA issued by the institution if no average score or GPA is on the transcript',
  'For the second-year award, achieve a minimum 70% average in the first year of study',
];
off.citizenship_residency = 'Overseas students. Country of ordinary residence is the country where the applicant has been living for the last 5 years, excluding countries where they reside purely for the purpose of studying.';
off.international_eligibility = 'Open to overseas students, applying through either the China scheme or the Rest of the World scheme. The page publishes no restriction on field of study and no academic threshold; it states awards recognise demonstrated academic excellence or potential, and directs applicants to the full terms and conditions for eligibility.';
off.degree_levels = ["Bachelor's", "Master's (postgraduate taught)"];
off.study_mode = null;
off.study_mode_note = 'Not published on the scholarship page.';
off.research_requirement = null;
off.subject_or_agency_requirement = null;
off.application_method = 'Separate scholarship application, by country-of-residence scheme';
off.application_route = 'Google form for the relevant scheme, with an alternate PDF form accepted where the Google form cannot be used. Both schemes are published for January and March 2027 entry.';
off.requirements = [
  'Hold an offer to study an undergraduate course or a postgraduate taught course at Swansea University',
  'Submit the scholarship form matching the applicant\'s country of ordinary residence',
  'Include transcripts of previous studies',
  'Provide proof of average score or GPA issued by the institution where the transcript does not show one',
  'Read the full terms and conditions linked from the page to determine eligibility',
  'Achieve a minimum 70% year-one average to qualify for the second-year award',
];
off.documents = [
  'Completed scholarship application form for the relevant scheme',
  'Transcripts of previous studies',
  'Proof of average score or GPA issued by the institution, if no average score or GPA is on the transcript',
];
off.english_requirement = null;
off.english_requirement_note = 'Not published on the scholarship page.';
off.selection_criteria = [
  'Demonstrated academic excellence, or potential to demonstrate it, during study at Swansea University',
  'No published academic threshold on the page; eligibility is governed by the linked terms and conditions',
];
off.selection_weighting = null;
off.duration = 'First year of study, with a conditional second-year award';
off.award_holder_conditions = [
  'The second-year award of GBP 2,000 requires a minimum 70% average in the first year of study',
  'Only one application per student is considered',
  'The award is a tuition fee discount and is applied to tuition, not paid separately',
  'Eligibility is governed by the scheme terms and conditions linked from the page',
];
off.supplements_or_initiatives = [
  'Two parallel schemes are published for the same deadline: International Excellence Scholarship (China) and International Excellence Scholarship (Rest of the World), both for January and March 2027 entry'
];
off.deadline_central_display = '12:00 GMT on 27 November 2026';
off.description = 'Swansea University offers International Excellence Scholarships as tuition fee discounts of up to GBP 5,000 for the first year of study to overseas students who have demonstrated academic excellence or show potential to do so. Undergraduates who receive the full GBP 5,000 in year one may receive a further GBP 2,000 in year two on achieving a 70% average. Applications close at 12:00 GMT on 27 November 2026 for January and March 2027 entry.';
off.coverage = 'Tuition fees only; not living costs, not travel';
off.last_verified_date = '2026-10-03';

// ---------- verification ----------
v.cycle_verified = 'January and March 2027 entry; applications close 12:00 GMT on 27 November 2026; verified 2026-10-03';
v.verification_confidence = 0.86;
v.official_fields_confirmed = Array.from(new Set([...(v.official_fields_confirmed || []),
  'deadline_central', 'deadline_central_timezone', 'deadline_institutional', 'application_cycle',
  'citizenship_residency', 'international_eligibility', 'application_route', 'documents',
  'requirements', 'funding_duration', 'tuition_coverage_note', 'award_holder_conditions',
  'degree_levels', 'funding_period', 'application_period', 'application_method', 'selection_criteria',
]));
v.unverified_or_removed_claims = (v.unverified_or_removed_claims || []).filter(c => !/INTERIM/i.test(c) && !/not yet complete/i.test(c)).concat([
  'COMPLETED from the official page on 2026-10-03. This record previously carried eleven literal "INTERIM" placeholders and empty eligibility, requirements and benefits arrays. All fields that the official page establishes are now filled from that page.',
  'SCOPE NOTE: the official page states applicants must have received an offer to study an undergraduate course OR a postgraduate taught course, so the award is not bachelor-exclusive. It is recorded here because it applies to undergraduates.',
  'ENTRY INTAKE NOTE: the page publishes January and March 2027 entry only. No September intake is published on this page, so the record is not a September-intake award.',
  'STILL UNKNOWN - the linked scheme terms and conditions were not fetched, so no eligibility threshold beyond what the page itself states is asserted. The page states awards recognise academic excellence or potential and directs readers to the terms for full eligibility.',
  'STILL UNKNOWN - no English language requirement is published on this page.',
  'STILL UNKNOWN - study mode and subject restrictions are not published on this page.',
]);
v.source_citations = Array.from(new Set([...(v.source_citations || []), URL_MAIN, URL_INDEX]));

// ---------- research notes ----------
rn.degree_level_confirmed = "CONFIRMED at bachelor's level, with a stated caveat. The page states that applicants 'must have received an offer to study an undergraduate course or a postgraduate taught course at Swansea University to apply', so the award covers both undergraduate and postgraduate taught entry. It applies to undergraduates and is therefore valid for this catalogue, but it is not an undergraduate-only award. The second-year top-up is stated specifically for undergraduates: 'Undergraduate students who receive the full GBP 5,000 in their first year of study will be awarded an additional GBP 2,000 in their second year if they achieve a minimum average of 70%'.";
rn.skeleton = false;
rn.substitution = 'Award identity confirmed. The assigned pool label was the generic "International Scholarship for UG Students - Swansea University"; the named award actually published on the Swansea international scholarships pages is the "International Excellence Scholarship", which is what is recorded here.';
rn.logo = 'Not verified - logo_override.url is null by design rather than guessed';
rn.unverified = [
  'The linked scheme terms and conditions, which govern full eligibility and were not fetched',
  'Any English language requirement',
  'Study mode and any subject restriction',
  'Whether any September intake exists outside the January and March 2027 schemes published here',
];

fs.writeFileSync(P, JSON.stringify(o, null, 2));
console.log('b18-swansea COMPLETED from official page');
console.log('  degree_levels : ' + ns.degree_levels);
console.log('  funding       : ' + ns.funding_amount + ' ' + ns.funding_currency + ' (tuition discount, not cash)');
console.log('  deadline      : ' + ns.deadline);
console.log('  eligibility   : ' + ns.eligibility.length + ' entries | requirements: ' + ns.requirements.length + ' | docs: ' + ns.required_documents.length);
console.log('  skeleton      : ' + rn.skeleton + ' | confidence: ' + v.verification_confidence);