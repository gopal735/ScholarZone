const fs = require('fs');
const P = 'research/bachelor/w4-windsor-international-scholarships.json';
const o = JSON.parse(fs.readFileSync(P, 'utf8'));
const ns = o.new_scholarship, off = o.programme_detail_official, v = o.programme_detail_verification, au = o.programme_detail_applicant_utility, rn = o.research_notes;

const PDF = 'https://www.uwindsor.ca/studentawards/sites/uwindsor.ca.studentawards/files/2026-2027_entrance_award_regulations_intl_2026-5.pdf';
const INTL = 'https://www.uwindsor.ca/studentawards/international-students-scholarships';

ns.name = 'Global Lancer Entrance Scholarship';
ns.funding_type = 'Entrance scholarship';
ns.program_type = 'Entrance scholarship';
ns.duration = 'Renewable across a four-year degree, paid over 8 semesters';
ns.deadline = 'No application - the award is automatic on admission';
ns.deadline_date = null;
ns.deadline_precision = 'varies';
ns.application_period = 'No separate scholarship application. The award is made automatically on application for admission, so the admission application date governs eligibility.';
ns.application_method = 'Automatic - evaluated and awarded automatically upon application for admission';
ns.status = 'open';
ns.funding_amount = 24000;
ns.funding_currency = 'CAD';
ns.funding_period = 'over four years';
ns.funding_note = 'Tiered by admission average, from CAD 4,000 to CAD 24,000 over four years. The 80-89.99% band is paid as CAD 1,250 per term over 8 semesters.';
ns.eligibility = [
  'Be entering directly from high school',
  'Be paying international tuition fees',
  'Be entering an undergraduate degree programme',
  'Hold an admission average calculated from the top 6 interim and final Grade 12 U or M level qualifying course grades, or the Ontario equivalent, with foreign school grades converted at the time of admission',
  'Have no previous attendance at a post-secondary educational institution for the automatic open entrance scale',
  'Maintain the required minimum scholarship average of 85% at the end of each 2-term study period to continue renewal'
];
ns.eligibility_summary = 'International students entering an undergraduate programme directly from high school and paying international tuition fees. Value is set by the admission average derived from the top 6 qualifying Grade 12 courses, with foreign grades converted to the Ontario equivalent.';
ns.coverage = [
  'Automatic entrance support from CAD 4,000 to CAD 24,000 over four years depending on admission average',
  'Paid in term instalments directly to the student account after the financial drop date each semester, so long as conditions continue to be met'
];
ns.benefits = [
  '95%+ admission average: CAD 24,000 over four years (CAD 6,000 per year)',
  '90-94.99% admission average: CAD 20,000 over four years (CAD 5,000 per year)',
  '80-89.99% admission average: CAD 10,000 over four years (CAD 2,500 per year)',
  'Below 80% admission average: CAD 4,000 over four years (CAD 1,000 per year)',
  'Paid as term instalments, for example CAD 1,250 per term over 8 semesters in the 80-89.99% band',
  'Displayed as Anticipated Aid on the student homepage before the ensuing term fee deadline date, which is August 15 for Fall, December 15 for Winter and May 15 for Summer'
];
ns.requirements = [
  'Enter directly from high school and pay international tuition fees',
  'Register full-time, as the payment schedule is adjusted if a start term is deferred',
  'Maintain the required minimum scholarship average of 85% at the end of each 2-term study period to continue renewal',
  'Register full-time for 2 semesters within an academic year to receive payments, up to a maximum of 8 instalments'
];
ns.required_documents = [];
ns.english_requirement = null;
ns.selection_notes = 'The May scholarship offer is final and will only change if the student\'s average across the top 6 final Grade 12 U or M level courses increases for courses completed by June 30. Co-op courses are not included in the admission average calculation.';
ns.notes = 'The University of Windsor also runs a separate application-required international scholarship with 10 awards at CAD 10,000 and an application window of August 1 to October 15, with published India and China equivalency tables. That is a different award and is not recorded here.';

off.official_source_urls = [PDF, INTL, 'https://www.uwindsor.ca/studentawards/entering-students', 'https://www.uwindsor.ca/studentawards/faqs-awards'];
off.official_updates_url = PDF;
off.catalogue_url = INTL;
off.application_cycle = '2026-2027 entrance awards cycle';
off.deadline_central = null;
off.deadline_central_display = 'No application and no deadline - the award is automatic on admission';
off.deadline_central_timezone = null;
off.deadline_institutional = null;
off.deadline_note = 'The award is automatic, so the admission application date governs eligibility rather than a separate scholarship deadline. Term fee deadline dates are published as August 15 for Fall, December 15 for Winter and May 15 for Summer.';
off.status = 'open';
off.status_note = 'The 2026-2027 entrance awards regulations are published and the programme is open to international students entering directly from high school.';
off.funding_amount = 24000;
off.funding_currency = 'CAD';
off.funding_period = 'over four years';
off.funding_duration = 'Renewable across the degree, paid over a maximum of 8 instalments';
off.tuition_coverage = true;
off.tuition_coverage_note = 'Entrance support applied to the student account rather than paid separately. The regulations describe payments made directly to the student account after the financial drop date each semester.';
off.living_cost_coverage = false;
off.travel_coverage = false;
off.fully_funded = false;
off.funding_label = 'CAD 4,000 to CAD 24,000 over four years, tiered by admission average, automatic';
off.benefits = [
  'Automatic Entrance Averages: 95%+ = $24,000 over four years; 90-94.99% = $20,000 over four years; 80-89.99% = $10,000 over four years; below 80% = $4,000 over four years',
  'Scholarship value based on top 6 interim and final Grade 12 U or M level qualifying course grades, with foreign school grades converted at the time of admission to an equivalent Ontario Grade 12 average',
  'Co-op courses are not included in the average',
  'The May scholarship offer is final and will only change should a student\'s average increase for courses completed by June 30',
  'Payments made directly to the student account after the financial drop date each semester: early October for Fall, early February for Winter and mid-July for Summer, should conditions continue to be met',
  'Example published: the Global Lancer Scholarship in the 80-89.99% grade range, valued at $10,000 over 8 semesters, is paid in $1,250 instalments each term',
  'Value appears as Anticipated Aid on the student homepage Financial area before the ensuing term fee deadline date'
];
off.eligibility = [
  'Enter directly from high school and pay international tuition fees',
  'Be entering an undergraduate degree programme',
  'Admission average derived from the top 6 interim and final Grade 12 U or M level qualifying course grades, or Ontario equivalent, with foreign grades converted at admission',
  'Co-op courses excluded from the average',
  'Maintain the required minimum scholarship average of 85% at the end of each 2-term study period',
  'Register on a full-time basis for 2 semesters within an academic year to continue receiving payments'
];
off.citizenship_residency = 'International students paying international tuition fees';
off.international_eligibility = 'Open to international students entering directly from high school who pay international tuition fees. Selection is by admission average only, with no separate application. Official admission deferrals to the 2027/2028 academic year automatically defer the entrance scholarship.';
off.degree_levels = ["Bachelor's"];
off.study_mode = null;
off.study_mode_note = 'The regulations require full-time registration but do not publish a study-mode field.';
off.research_requirement = null;
off.subject_or_agency_requirement = 'Open to all undergraduate programmes; the regulations state the open entrance programme applies regardless of programme chosen';
off.application_method = 'Automatic - no separate application';
off.application_route = 'Apply for admission; the entrance scholarship is evaluated and awarded automatically. Scholarship payments appear as Anticipated Aid on the student account.';
off.requirements = [
  'Enter directly from high school',
  'Pay international tuition fees',
  'Register full-time for 2 semesters within an academic year',
  'Maintain the minimum 85% scholarship average at the end of each 2-term study period'
];
off.documents = [];
off.english_requirement = null;
off.english_requirement_note = 'Not published in the international entrance awards regulations.';
off.selection_criteria = [
  'Admission average from the top 6 Grade 12 U or M level qualifying courses, tiered at below 80%, 80-89.99%, 90-94.99% and 95%+',
  'Automatic award, no competition or separate application',
  'Continuation requires an 85% scholarship average at the end of each 2-term study period'
];
off.selection_weighting = null;
off.duration = 'Four years, renewable across a maximum of 8 instalments';
off.award_holder_conditions = [
  'Must maintain a minimum 85% scholarship average at the end of each 2-term study period to continue renewal',
  'Must register full-time for 2 semesters within an academic year',
  'The May offer is final except where the admission average increases on courses completed by June 30',
  'Payments are conditional on conditions continuing to be met',
  'Official admission deferrals automatically defer the entrance scholarship'
];
off.supplements_or_initiatives = [
  'A separate application-required international scholarship with 10 awards at CAD 10,000, open August 1 to October 15, with published India and China equivalency tables',
  'Chancellor Jackman Scholarship Awards, Alumni Entrance Scholarship, Windsor Green Engineering Scholarships and other separately named awards exist at the University but were not recorded here',
  'A separate in-course study scholarship and an International Student Bursary programme exist and are out of scope for this entrance award'
];
off.description = 'The University of Windsor Global Lancer Entrance Scholarship provides automatic entrance support to international students entering directly from high school and paying international tuition fees. Value is tiered by admission average from CAD 4,000 to CAD 24,000 over four years, paid in term instalments, and renewable subject to maintaining an 85% scholarship average.';
off.coverage = 'Entrance support applied to the student account; not living costs or travel';

v.cycle_verified = '2026-2027 entrance awards cycle, from the published 2026-2027 international entrance awards regulations; verified 2026-10-03';
v.verification_confidence = 0.88;
v.official_fields_confirmed = Array.from(new Set([...(v.official_fields_confirmed || []),
  'funding_amount', 'funding_currency', 'funding_period', 'funding_duration', 'tuition_coverage',
  'tuition_coverage_note', 'duration', 'citizenship_residency', 'international_eligibility',
  'application_route', 'selection_criteria', 'award_holder_conditions', 'subject_or_agency_requirement',
  'deadline_note', 'application_cycle',
]));
v.unverified_or_removed_claims = (v.unverified_or_removed_claims || []).filter(c => !/interim write/i.test(c)).concat([
  'COMPLETED from the official 2026-2027 international entrance awards regulations on 2026-10-03. This record previously carried no funding figure and self-declared interim status with funding_amount, funding_currency, funding_period, duration, coverage, tuition_coverage and english_requirement all deliberately null. Funding, currency, duration, coverage and renewal conditions are now established from the official regulations.',
  'SCOPE CORRECTION: the award is the Global Lancer Entrance Scholarship, which is the international scale. The University also publishes a Domestic Open Entrance Scholarship table with Blue and Gold $1,000, Dean\'s $10,000 and President\'s $16,000 levels, and states that effective 2026-27 that open entrance programme is open to DOMESTIC students only. The $16,000 President\'s tier must not be applied to an international applicant; international applicants are assessed on the Global Lancer scale.',
  'STILL UNKNOWN - no English language requirement is published in the international entrance awards regulations.',
  'STILL UNKNOWN - study mode is not published as a field; the regulations require full-time registration.',
  'STILL UNKNOWN - the separate application-required international scholarship with India and China equivalency tables was not recorded as its own record; it is a distinct award.',
]);
v.source_citations = Array.from(new Set([...(v.source_citations || []), PDF, INTL]));

au.application_readiness_checklist = [
  'Apply for admission to an undergraduate programme - there is no separate scholarship application',
  'Enter directly from high school; the award is for direct entrants from high school paying international tuition fees',
  'Note the admission average is calculated from your top 6 interim and final Grade 12 U or M level qualifying courses, with foreign grades converted to an Ontario equivalent',
  'Register full-time for 2 semesters within each academic year to keep receiving payments',
  'Plan to maintain an 85% scholarship average at the end of each 2-term study period, or renewal stops',
  'Do not expect the May offer to rise: it is final unless your average increases on courses completed by June 30'
];
au.common_rejection_risks = [
  'Entering with previous post-secondary attendance rather than directly from high school',
  'Not paying international tuition fees',
  'Falling below the 85% scholarship average at the end of a 2-term study period, which ends renewal',
  'Registering less than full time, which breaks the 2-semester payment condition',
  'Assuming the domestic President\'s $16,000 tier applies - it is domestic-only from 2026-27'
];
au.estimated_uncovered_costs = [
  'Tuition beyond the awarded tier, since the highest tier is CAD 24,000 over four years rather than full tuition',
  'Living expenses and accommodation',
  'Books, supplies and incidental fees',
  'Student health insurance, where international students are billed the UHIP plan',
  'Travel, immigration and permanent residence costs'
];
au.document_audit = [
  'No award-specific documents - the award is automatic',
  'Standard admission documents including proof of qualifying course grades for average calculation'
];
au.alerts = (au.alerts || []).filter(a => a && typeof a === 'object' && a.trigger && a.message);
au.alerts.push(
  { trigger: 'International and domestic scales differ', message: 'The domestic Open Entrance table shows Blue and Gold $1,000, Dean\'s $10,000 and President\'s $16,000, but that programme is open to domestic students only from 2026-27. International applicants are assessed on the Global Lancer scale of $4,000 to $24,000 over four years.' },
  { trigger: 'Renewal needs an 85% scholarship average', message: 'The minimum scholarship average is 85% at the end of each 2-term study period, not an 80% threshold as with some other Canadian entrants awards.' },
  { trigger: 'Co-op courses are excluded from the average', message: 'The admission average uses the top 6 Grade 12 U or M level qualifying courses and explicitly excludes co-op courses.' },
  { trigger: 'The May offer is final', message: 'The May scholarship offer only changes if the admission average rises on courses completed by June 30.' },
  { trigger: 'Payments are instalments against your account', message: 'Value appears as Anticipated Aid before the term fee deadline of August 15 for Fall, December 15 for Winter and May 15 for Summer, and is paid after each semester drop date.' }
);

rn.degree_level_confirmed = "CONFIRMED at bachelor's level. The 2026-2027 international entrance awards regulations govern awards to students entering an undergraduate degree programme directly from high school, and the University publishes separate graduate entrance awards, so this scale is undergraduate-specific.";
rn.skeleton = false;
rn.logo = 'Not verified - logo_override.url is null by design rather than guessed';
rn.official_pages_read = [PDF, INTL, 'https://www.uwindsor.ca/studentawards/entering-students', 'https://www.uwindsor.ca/studentawards/faqs-awards', 'https://www.uwindsor.ca/awards/'];
rn.substitution = 'Award name corrected and scope fixed. The assigned label was "University of Windsor International Scholarships". The applicable automatic international award is the Global Lancer Entrance Scholarship, which is a separate scale from the domestic Open Entrance Scholarship programme.';
rn.unverified = ['Any English language requirement', 'The separate application-required international scholarship with India and China equivalency tables'];

fs.writeFileSync(P, JSON.stringify(o, null, 2));
console.log('w4-windsor COMPLETED from official 2026-27 entrance awards regulations');
console.log('  name      : ' + ns.name);
console.log('  funding   : ' + ns.funding_amount + ' ' + ns.funding_currency + ' (tiered 4,000-24,000 over 4 years)');
console.log('  skeleton  : ' + rn.skeleton + ' | confidence: ' + v.verification_confidence);