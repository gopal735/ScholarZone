// Part 5: image, official sources, verification block, database notes, and file writer for slot 49.
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
const NUS_REG_FEES_URL =
  'https://www.nus.edu.sg/registrar/administrative-policies-procedures/undergraduate/undergraduate-fees';
const MOE_TG_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme';
const MOE_TG_EMP_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme/employment';
const LOGO_URL = 'https://nus.edu.sg/images/default-source/base/logo.png';
const OAM_LOGO_URL = 'https://nus.edu.sg/oam/assets/OAM_Revamp/images/logo-nus.png';
const FAQ_URL = 'https://faq.nus.edu.sg/s/';

function extend(record) {
  // ---- image / logo ----
  record.image = {
    logo_url: LOGO_URL,
    logo_source_url: AWARD_URL,
    logo_source_type: 'official_provider_page',
    logo_verified: true,
    logo_verified_at: VERIFIED_DATE,
    logo_verification_method:
      'Probed the asset directly on the official nus.edu.sg domain. https://nus.edu.sg/images/default-source/base/logo.png returned HTTP 200 with Content-Type image/png and 26,329 bytes, with the PNG signature (89 50 4E 47 0D 0A 1A 0A) confirmed on the first bytes, 300 x 137 pixels, Format32bppArgb. The bytes were downloaded and visually inspected: it is the NUS institutional mark, a navy shield with an open book and a ring above an orange lion, beside the dark-blue "NUS" wordmark and the words "National University of Singapore", on a transparent field. It is not a white-on-transparent wordmark and is safe on a light card. The identical asset was also confirmed at http-200 with Content-Type image/png and 26,329 bytes on www.nus.edu.sg. A second official mark was verified the same way: https://nus.edu.sg/oam/assets/OAM_Revamp/images/logo-nus.png, the masthead mark rendered on the scholarship page itself, HTTP 200, Content-Type image/png, 11,114 bytes, 146 x 67, same crest and wordmark. The awarding body is NUS itself, so the NUS institutional mark is the correct logo; no ministry, aggregator, CDN or third-party mark was used.',
    image_url: null,
    image_source_url: null,
    image_source_type: null,
    image_verified: false,
    image_verified_at: null,
    image_alt_text: 'National University of Singapore institutional logo',
    image_usage_note:
      'The PNG has a transparent background with navy and orange elements, so it renders correctly on a light card. No photograph of the campus or of scholarship holders was verified on an official source, so image_url remains null.',
  };

  // ---- official sources ----
  record.official_source = 'National University of Singapore (NUS), Office of Admissions';
  record.official_source_url = AWARD_URL;
  record.official_programme_guide_url = null;
  record.official_catalogue_url = CATALOGUE_URL;
  record.official_application_route =
    'There is no separate scholarship application: submit a single application for undergraduate admission to NUS through the NUS Applicant Portal within the admissions application period for your qualification, and all eligible students are considered for this scholarship automatically; only shortlisted candidates are informed by e-mail and attend a selection interview between January and July.';
  record.official_updates_url = DATES_URL;

  // ---- verification ----
  record.verification = {
    is_verified: true,
    verification_status: 'active',
    last_verified_at: '2026-10-03T00:00:00+08:00',
    last_verified_date: VERIFIED_DATE,
    verification_date_meaning:
      'Date on which the official NUS Office of Admissions pages and the official MOE Tuition Grant Scheme pages were read and every field in this record was confirmed against them.',
    verified_by: 'ScholarZone research agent',
    source_type: 'official_university',
    source_domain: 'nus.edu.sg',
    verification_confidence: 0.93,
    official_fields_confirmed: [
      'Official award name: "Science & Technology Undergraduate Scholarship"',
      'Scholarship type: University-Level',
      'Nationality band: Singapore Permanent Residents / International Students',
      'Student type: Freshmen',
      'Award purpose: "a freshmen scholarship offered to support outstanding Asian students (excluding Singapore citizens)"',
      'Benefit: 100% coverage of subsidised undergraduate tuition fees (after MOE Tuition Grant - scholarship recipients must take up the MOE Tuition Grant)',
      'Benefit: S$6,000 annual living allowance',
      'Benefit: S$1,750 one-time computer allowance upon enrolment',
      'Benefit: S$200 one-time settling-in allowance upon enrolment',
      'Benefit: annual accommodation allowance equivalent to the lowest double room rate for on-campus accommodation',
      'Benefit: travel allowance for the incoming passage and the return passage (subject to proof of employment)',
      'Eligibility: citizens of an Asian country or region, excluding Singapore',
      'Eligibility: strong leadership qualities and potential',
      'Eligibility: excellent co-curricular activities record',
      'Eligibility: outstanding high school results',
      'Eligibility: applying for admission to a full-time undergraduate degree programme in Computing, Engineering (excluding Infrastructure and Project Management) or Science (excluding Environmental Studies and Pharmacy) at NUS',
      'Eligibility: transfer applicants from local or overseas universities are not eligible',
      'Full official list of eligible programmes across School of Computing, College of Design and Engineering, College of Humanities and Sciences and the joint Computer Engineering programme',
      'Local Double Degree Programme rule: covered only if the home programme falls within the listed programmes',
      'Duration: tenable for the normal candidature period of the undergraduate programme at NUS',
      'Bond: six-year bond with a Singapore-registered company immediately after graduation',
      'MOE Tuition Grant is required, and no other scholarship, fellowship, bursary, grant, award or allowance may be held concurrently',
      'Renewal: every semester, provided the scholar maintains a GPA of at least 3.50 (or equivalent) and has good conduct',
      '75% of the credits/units required for graduation must be earned in Singapore, no more than 25% through overseas programmes, and overseas programmes must be completed before September of the year prior to graduation (NUS example: 160 units to graduate, maximum 40 units overseas)',
      'NUS does not guarantee and/or provide scholarship recipients with employment upon graduation',
      'Withdrawal or premature termination allows the University to impose repayment of all scholarship monies disbursed',
      'Application method: automatic consideration through the NUS undergraduate admission application, with no separate scholarship application',
      'Shortlisting: strength of the application; only shortlisted applicants informed by e-mail; interviews January to July; outcomes by mid-July; committee decision final',
      'Deadline: application period published as "Based on admissions application timeline", with no calendar date',
      'MOE Tuition Grant bond: Permanent Residents and international students who receive a Tuition Grant must work for a Singapore entity for three years upon graduation, employed full-time in a Singapore entity for 3 years',
      'NUS Office of Admissions contact details and the scholarship enquiry route at faq.nus.edu.sg',
      'Logo asset served from the official nus.edu.sg domain',
    ],
    programme_check_required: [
      'The NUS undergraduate admissions application dates for the specific qualification held, which are set on the admissions timeline rather than on the scholarship page and are currently published for Academic Year 2027/2028 as closed',
      'Whether the intended degree programme is still on the eligible-programme list at the time of application, since NUS revises programme names and college structures',
      'The monetary value of the annual accommodation allowance in the year of award, which NUS publishes only as the lowest on-campus double room rate',
      'The travel allowance amount and the documentation NUS requires to release the return passage against proof of employment',
      'The current subsidised and non-subsidised undergraduate tuition fees, published annually by the NUS Office of the University Registrar',
      'Whether Singapore Permanent Residents are assessed on identical terms to international students, since NUS lists the award in both sections while the eligibility criterion is written as a citizenship test',
      'The current MOE Tuition Grant terms, including bond deferment and liquidated damages, administered by the Ministry of Education',
    ],
    unverified_or_removed_claims: [
      'deadline_date is null because NUS publishes no calendar deadline for this scholarship; the application period is stated only as "Based on admissions application timeline"',
      'The 1 February to 19 March 2027 window on the Important Dates and Application page belongs to NUS Scholarships for Freshmen (Singapore Citizens) and is not attributed to this award',
      'No fixed duration in years is published, because the award follows the normal candidature period of each individual programme',
      'No fixed sum is published for the accommodation allowance; NUS states only an amount equivalent to the lowest double room rate for on-campus accommodation',
      'No fixed sum is published for the travel allowance; NUS states only that it defrays transport cost for the incoming and return passage, subject to proof of employment',
      'No monthly stipend exists, so monthly_amount is null; the recurring cash benefit is the S$6,000 annual living allowance',
      'No English language test, score or certificate is published for this scholarship, so every English requirement score field is null',
      'No scholarship document set is published beyond the undergraduate admission application, so universal_documents, commonly_requested_documents and the empty checklist categories are deliberately empty',
      'No numerical selection weighting is published, so official_universal_weighting and selection_weighting are null',
      'No age limit and no gender restriction are published',
      'No nationality quota, number of awards or aggregate budget is published',
      'No language-of-instruction information is published on the scholarship page, so possible_languages is empty',
      'deadline_timezone is null because NUS publishes no timezone for this scholarship; Asia/Singapore is the university\'s own timezone but is not stated for the award',
      'short_title "S&TUS" is a database-created short form; NUS publishes no acronym or short name for this award',
      'legacy_titles is empty because NUS publishes no alternative or former name for this award',
    ],
    source_citations: [
      AWARD_URL,
      PR_AWARD_URL,
      DATES_URL,
      CATALOGUE_URL,
      ADM_DATES_URL,
      NUS_TG_URL,
      NUS_REG_FEES_URL,
      MOE_TG_URL,
      MOE_TG_EMP_URL,
      LOGO_URL,
      OAM_LOGO_URL,
      FAQ_URL,
    ],
  };

  // ---- database notes ----
  record.database_notes = [
    'DUPLICATION CHECK: this record is deliberately distinct from the NUS International Undergraduate Scholarship already in the do-not-duplicate list, which is open to citizens of all countries except Singapore and carries different benefits. The Science & Technology Undergraduate Scholarship is field-restricted to Computing, Engineering and Science, is limited to citizens of an Asian country or region excluding Singapore, and carries a six-year bond.',
    'NUS also administers an ASEAN Undergraduate Scholarship from the same Office of Admissions; it is a different award with a different citizenship gate (ASEAN countries only) and is not recorded here.',
    'The award is published by NUS under both "Scholarships for Freshmen (Singapore Permanent Residents)" and "Scholarships for Freshmen (International Students)". Both versions were read and carry identical scholarship benefits, terms and conditions, programme list and shortlisting process. The eligibility criteria reproduced here are NUS\'s own wording, which frames the award as support for outstanding Asian students excluding Singapore citizens while labelling the nationality band as Singapore Permanent Residents / International Students. NUS does not publish whether the two are assessed on identical terms.',
    'SHORT TITLE: NUS publishes no acronym or short form for this award. "S&TUS" is a clear short form created for this database and is not an official NUS abbreviation.',
    'LEGACY TITLES: none. NUS publishes no alternative or former name for this award, so legacy_titles is an empty array rather than a guessed one.',
    'DEGREE LEVEL: confirmed at bachelor\'s level directly from the awarding body. The page labels the award "Student Type: Freshmen", describes it as "a freshmen scholarship offered to support outstanding Asian students (excluding Singapore citizens)", requires applicants to be "Applying for admission to a full-time undergraduate degree programme ... at NUS", states the scholarship "is tenable for the normal candidature period of the undergraduate programme at NUS", and the Important Dates and Application page states the qualification requirement as "High school qualifications eligible for admission to NUS". No master\'s, doctoral or research component appears in the official text.',
    'ADMISSION VERSUS FUNDING: this is an admission-linked award that is considered automatically through the undergraduate admission application. There is no separate scholarship application, no scholarship form, no scholarship portal submission, no scholarship deadline and no scholarship fee. This is recorded explicitly in application_method (direct_student_application and central_application both false, automatic_consideration true) and in programme_structure.application_required false.',
    'BOND: the scholarship carries a six-year bond with a Singapore-registered company immediately after graduation. Recipients must also take up the MOE Tuition Grant, which for Singapore Permanent Residents and international students carries a separate three-year bond requiring full-time employment in a Singapore entity after graduation. NUS states it does not guarantee and/or provide employment upon graduation. For these reasons fully_funded is false and the award is never presented as an unconditional full ride.',
    'TUITION BASIS: coverage is stated only against subsidised undergraduate tuition fees after the MOE Tuition Grant. The difference between the subsidised and the full non-subsidised international rate is not covered, and the NUS fees page states that eligible students who do not complete the MOE Tuition Grant application and signing by the stipulated deadlines will be charged the non-subsidised tuition fees. No current fee figures are quoted here because they are published annually and were not read as a fee table in this session.',
    'DEADLINE: deadline_date is null with deadline_precision "programme_specific" because NUS publishes no calendar date for this scholarship, only "Based on admissions application timeline". The Academic Year 2027/2028 admissions windows quoted in typical_application_window are quoted for context from the NUS admissions Important Dates page and were all marked [Closed] at the verification date; they are not this scholarship\'s deadlines. The 1 February to 19 March 2027 window on the scholarship Important Dates page applies to NUS Scholarships for Freshmen (Singapore Citizens) only and is expressly not attributed here.',
    'UNPUBLISHED AMOUNTS: no sum is published for the accommodation allowance (stated only as the lowest on-campus double room rate) or for the travel allowance (stated only as the incoming and return passage, return subject to proof of employment). No monthly stipend, aggregate budget, number of awards, age limit, gender restriction, nationality quota, English test score, selection weighting or scholarship document list is published. These are recorded as null or empty rather than filled with plausible values.',
    'LOGO: the NUS institutional mark was verified live on the official nus.edu.sg domain (two assets, both HTTP 200 with Content-Type image/png and confirmed PNG signatures, downloaded and visually inspected). The awarding body is NUS itself, so the university mark is the correct logo. No logo was taken from any aggregator, CDN, third-party site or other awarding body.',
    'RESEARCH DATE: SCHEMA_CONTRACT.md states the batch research date as 2026-10-03 and requires that exact date for last_verified_date, _verification_timestamp, logo_verified_at and image_verified_at, so those fields use 2026-10-03 for consistency with the rest of the dataset. The NUS and MOE pages were read in a session whose local clock showed 2026-10-10, and the page contents matched the cycle already recorded for this award.',
    'FETCH RECORD: nine official-domain pages were read for this record (seven NUS pages including both published versions of the award page, plus two MOE Tuition Grant Scheme pages), and three logo assets were probed on the official nus.edu.sg domain. No third-party aggregator, scholarship-listing site, news article, blog or stock source was used for any fact in this record.',
    '_completeness_score reflects that NUS publishes no scholarship documents, no English test scores, no selection weighting, no accommodation or travel amounts and no deadline date for this award; those are honest nulls and empty arrays, not gaps in the research.',
  ];

  record._source_domain = 'nus.edu.sg';
  record._source_type = 'official_provider';
  record._cycle =
    'NUS undergraduate admissions intake cycle (verified 2026-10-03; admissions windows currently published for Academic Year 2027/2028, all shown closed)';
  record._verification_timestamp = '2026-10-03T00:00:00+08:00';
  record._completeness_score = 0.93;
}

module.exports = { extend, VERIFIED_DATE };
