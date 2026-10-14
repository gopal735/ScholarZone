// Builds research/bachelor/49-singapore-nus-scitech-undergraduate.json (v1 array schema)
// Evidence: official nus.edu.sg/oam pages + official moe.gov.sg Tuition Grant Scheme pages.
const fs = require('fs');
const path = require('path');

const VERIFIED_DATE = '2026-10-03';
const AWARD_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students/science-technology-undergraduate-scholarship';
const PR_AWARD_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-singapore-permanent-residents/science-technology-undergraduate-scholarship';
const DATES_URL = 'https://nus.edu.sg/oam/scholarships/important-dates-and-application';
const CATALOGUE_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students';
const ADM_DATES_URL = 'https://nus.edu.sg/oam/admissions/important-dates';
const NUS_TG_URL = 'https://nus.edu.sg/oam/financial-aid/moe-tuition-grant-tuition-fees';
const NUS_REG_FEES_URL = 'https://www.nus.edu.sg/registrar/administrative-policies-procedures/undergraduate/undergraduate-fees';
const MOE_TG_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme';
const MOE_TG_EMP_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme/employment';
const LOGO_URL = 'https://nus.edu.sg/images/default-source/base/logo.png';
const OAM_LOGO_URL = 'https://nus.edu.sg/oam/assets/OAM_Revamp/images/logo-nus.png';

const PROGRAMMES = {
  School_of_Computing: [
    'Artificial Intelligence',
    'Business Analytics',
    'Business Artificial Intelligence Systems',
    'Computer Science',
    'Information Security',
  ],
  College_of_Design_and_Engineering: [
    'Biomedical Engineering',
    'Chemical Engineering',
    'Civil Engineering',
    'Computer Engineering',
    'Electrical Engineering',
    'Engineering Science',
    'Environmental and Sustainability Engineering',
    'Industrial & Systems Engineering',
    'Materials Science & Engineering',
    'Mechanical Engineering',
    'Robotics & Machine Intelligence',
  ],
  School_of_Computing_and_College_of_Design_and_Engineering: ['Computer Engineering'],
  College_of_Humanities_and_Sciences: [
    'Chemistry',
    'Data Science and Analytics',
    'Data Science and Economics',
    'Food Science and Technology',
    'Geospatial Intelligence',
    'Life Sciences',
    'Mathematics',
    'Pharmaceutical Science',
    'Physics',
    'Quantitative Finance',
    'Statistics',
  ],
};

const record = {};

// ---- identity ----
record.id = 'nus-science-technology-undergraduate-scholarship';
record.title = 'Science & Technology Undergraduate Scholarship';
record.short_title = 'S&TUS';
record.legacy_titles = [];
record.country = 'Singapore';
record.host_region = 'Singapore';
record.degree = "Bachelor's";
record.degree_levels = ["Bachelor's", 'ISCED Level 6 equivalent'];
record.study_level = 'Undergraduate';
record.program_type =
  'University merit scholarship awarded at admission, considered automatically through the NUS undergraduate admission application with no separate scholarship application';
record.funding_type =
  'Full coverage of subsidised undergraduate tuition fees plus living, accommodation and one-time allowances, university-funded, subject to a six-year service bond';
record.administering_authority = 'National University of Singapore (NUS), Office of Admissions';
record.implementing_agency = 'NUS Office of Admissions (same body that runs the scheme)';
record.programme_action =
  'NUS Office of Admissions freshmen scholarship portfolio - "Scholarships for Freshmen (International Students)" and "Scholarships for Freshmen (Singapore Permanent Residents)", scholarship type "University-Level"';

// ---- description ----
record.description =
  'The Science & Technology Undergraduate Scholarship is a freshmen scholarship offered by the National University of Singapore to support outstanding Asian students (excluding Singapore citizens). Candidates are considered and shortlisted for the scholarship through their application for undergraduate admission to NUS; there is no separate scholarship application or scholarship deadline. The award provides 100% coverage of subsidised undergraduate tuition fees after the MOE Tuition Grant, a S$6,000 annual living allowance, a S$1,750 one-time computer allowance upon enrolment, a S$200 one-time settling-in allowance upon enrolment, an annual accommodation allowance equivalent to the lowest double room rate for on-campus accommodation, and a travel allowance for the incoming and return passage. Recipients must serve a six-year bond with a Singapore-registered company immediately after graduation, must take up the MOE Tuition Grant, and the scholarship is renewed every semester provided the scholar maintains a GPA of at least 3.50 (or equivalent) and has good conduct.';

// ---- programme structure ----
record.programme_structure = {
  award_types: [
    'Science & Technology Undergraduate Scholarship (single award type; NUS publishes no tiers or variants of this award)',
  ],
  award_types_detail:
    'One award type, restricted by field of study rather than by tier. NUS states that the scholarship is awarded to freshmen pursuing the listed full-time undergraduate programmes, and that it also covers students in local Double Degree Programmes provided the scholarship recipient\'s home programme falls within one of the listed programmes.',
  renewable: true,
  renewal_criteria:
    'The scholarship will be renewed every semester, provided the scholar maintains a Grade Point Average (GPA) of at least 3.50 (or equivalent), and has good conduct. Renewal is also subject to the award-holder conditions, including that at least 75% of the credits/units required for graduation are earned in Singapore and that overseas programmes are completed before September of the year prior to graduation.',
  application_required: false,
  automatic_consideration: true,
  intake:
    'Assessed through the live NUS undergraduate admissions cycle. The official Important Dates and Application page records the application period for this scholarship as "Based on admissions application timeline", with the note "All eligible students will be considered for the scholarship through their application for undergraduate admission to NUS." Selection interview(s) are conducted from January to July and interviewed candidates are informed of the scholarship outcomes by mid-July.',
};

// ---- status ----
record.status = 'OPEN';
record.status_label = 'Open - automatic consideration through the NUS admissions cycle';
record.status_note =
  'The award has no scholarship window of its own and no published closing date: NUS states that all eligible students will be considered for the scholarship through their application for undergraduate admission to NUS, so the award is assessed continuously against the NUS undergraduate admissions timeline for the applicant\'s qualification. As at the verification date the award page carried no closed notice, no waitlist notice and no paused-intake notice, so the cycle is treated as open for the coming intake. The eligibility gate is a citizenship test (citizens of an Asian country or region, excluding Singapore) rather than a nationality quota, and NUS reserves the right not to award any scholarship if there are no candidates of sufficient merit.';

// ---- verification block (top-level summary) ----
record.is_verified = true;
record.verification_status = 'active';
record.verification_type =
  'Official university website (nus.edu.sg, Office of Admissions) plus the official Singapore Ministry of Education Tuition Grant Scheme pages (moe.gov.sg).';
record.last_verified_at = '2026-10-03T00:00:00+08:00';
record.last_verified_date = VERIFIED_DATE;
record.verified_by = 'ScholarZone research agent';
record.verification_notes =
  'Read the official NUS Science & Technology Undergraduate Scholarship page (both the International Students and the Singapore Permanent Residents versions, which carry identical terms), the NUS Scholarships Important Dates and Application page, the NUS Office of Admissions scholarships catalogue page, the NUS admissions Important Dates page, and the NUS Office of the University Registrar MOE Tuition Grant and fees page, plus the MOE Tuition Grant Scheme overview and Employment and pass matters pages. Every amount, eligibility criterion, bond term, renewal threshold and credit-distribution rule in this record was taken verbatim from those pages. Nine official-domain sources were read; no third-party aggregator, listing site, news article or stock source was used for any fact.';
record.next_verification_due = '2027-01-31';
record.source_last_updated =
  'The NUS Office of Admissions pages carry no published last-updated date. The MOE Tuition Grant Scheme pages used for the bond terms are stamped "Last Updated: 23 Jun 2026". The NUS admissions Important Dates page currently publishes the Academic Year 2027/2028 windows and marks every application period as [Closed].';
record.current_programme_guide_checked = true;

// ---- deadline ----
record.application_deadline = {
  single_central_deadline: false,
  deadline_date: null,
  deadline_timezone: null,
  deadline_precision: 'programme_specific',
  typical_application_window:
    'No scholarship window exists. The official Important Dates and Application page records the application period for the Science & Technology Undergraduate Scholarship as "Based on admissions application timeline", that is, the NUS undergraduate admissions application period for the applicant\'s own qualification. For reference, the NUS admissions Important Dates page published Academic Year 2027/2028 windows of 16 December 2026 to 4 January 2027 (NUS High School Diploma), 16 December 2026 to 3 February 2027 (Polytechnic Diploma from Singapore), 16 December 2026 to 17 February 2027 (IB Diploma and International Qualifications except IB Diploma) and 18 February 2027 (late afternoon) to 19 March 2027 (Singapore-Cambridge GCE A-Level), each shown as closed at the time of verification. For this scholarship the only dates NUS publishes are that selection interview(s) are conducted from January to July and that interviewed candidates are informed of the scholarship outcomes by mid-July.',
  application_period:
    'No separate scholarship application period. Consideration is automatic through the NUS undergraduate admission application, so the effective window is the admissions application period for the applicant\'s qualification.',
  official_rule:
    'NUS: "All eligible students will be considered for this scholarship through their application for undergraduate admission to NUS." The Official Important Dates and Application page lists the application period for the Science & Technology Undergraduate Scholarship as "Based on admissions application timeline" and the qualification requirement as "High school qualifications eligible for admission to NUS". The 1 February to 19 March 2027 window published on the same page belongs to NUS Scholarships for Freshmen (Singapore Citizens) and is expressly not this award\'s window.',
  deadline_warning:
    'Do not treat the 1 February to 19 March 2027 window on the Important Dates page as this scholarship\'s deadline; NUS applies that window to the Singapore Citizen NUS Scholarships. Because there is no scholarship deadline of its own, an applicant who misses the NUS admissions application period for their qualification cannot recover by applying separately for the scholarship. deadline_date is null because NUS publishes no calendar date for this award.',
  next_verification_due: '2027-01-31',
};

// ---- duration ----
record.programme_duration = {
  official_range:
    'Tenable for the normal candidature period of the undergraduate programme at NUS. NUS publishes no fixed number of years for this award; the duration follows the candidature period of the specific degree programme entered, and local Double Degree Programme students are covered provided their home programme is one of the listed programmes.',
  duration_years: null,
  normal_duration_years: null,
  duration_months: null,
  renewable: true,
  renewal_note:
    'Renewed every semester on condition that the scholar maintains a GPA of at least 3.50 (or equivalent) and has good conduct, and continues to satisfy the award-holder conditions including the 75% in-Singapore credit rule.',
};

module.exports = { record, VERIFIED_DATE, PROGRAMMES };
