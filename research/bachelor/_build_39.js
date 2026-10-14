// Slot 39 — Canada / University of Regina International Student of Distinction Scholarship
// Builds research/bachelor/39-canada-regina-international-distinction.json (JSON array, one record)
// All values traced to official uregina.ca pages fetched 2026-10-10.

const rec = {
  id: 'university-of-regina-international-student-of-distinction-scholarship',
  title: 'International Student of Distinction Scholarship',
  short_title: 'ISD',
  legacy_titles: [],

  country: 'Canada',
  host_region: 'Canada',
  degree: "Bachelor's",
  degree_levels: ["Bachelor's", 'ISCED Level 6 equivalent'],
  study_level: 'Undergraduate',
  program_type:
    "University merit-based entrance award with automatic consideration at admission, tiered by admission average",
  funding_type:
    'In-kind on-campus housing and meal-plan benefit (Tier 1 / Tier 2), delivered alongside two separate tuition-credit instruments',
  administering_authority:
    'University of Regina — UR International (International Recruitment and Marketing)',
  implementing_agency:
    'University of Regina International Enrolment Services and International Recruitment, with Housing and Hospitality Services delivering the Tier 1 / Tier 2 residence benefits',
  programme_action:
    'International undergraduate entrance award package: International Entrance Scholarship, International Student of Distinction Scholarship Tier 1 and Tier 2, and International Undergraduate Student Bursary',

  description:
    'The International Student of Distinction Scholarship is a University of Regina entrance award for international students applying directly from high school to an undergraduate degree programme. All international undergraduate applicants are automatically considered on the basis of their admission average, with no separate scholarship application required. Tier 1 provides on-campus housing plus a meal plan, published as an approximate value of CAD $90,000 over four years, for a minimum early conditional or overall final high school average of 90% converted to the Canadian grading scale; Tier 2 provides on-campus housing only, published as an approximate value of CAD $45,000 over four years, for an average of 85–89.99%. The official page states explicitly for both tiers that the award "is not a tuition credit scholarship"; tuition support within the same entrance package comes only from the separate International Entrance Scholarship and the International Undergraduate Student Bursary.',

  programme_structure: {
    award_types: [
      'International Entrance Scholarship',
      'International Student of Distinction Scholarship: Tier 1',
      'International Student of Distinction Scholarship: Tier 2',
      'International Undergraduate Student Bursary'
    ],
    award_types_detail:
      'International Entrance Scholarship — $5,000 tuition credit applied to the first registered term; automatic consideration for all international students applying to an undergraduate degree programme; admission average of 83% or higher; the increased value takes effect for students starting in the Fall 2026 term onward. International Student of Distinction Scholarship: Tier 1 — on-campus housing and a meal plan, approximate value $90,000 ($22,500 x 4 years); minimum early conditional or overall final high school average of 90% (converted to Canadian grading scale); automatic consideration for international students applying directly from high school. International Student of Distinction Scholarship: Tier 2 — on-campus housing, approximate value $45,000 ($11,250 x 4 years); minimum average of 85–89.99% (converted to Canadian grading scale); same automatic consideration. International Undergraduate Student Bursary — tuition credit of up to $20,000 over 4 years ($5,000 x 4 years), described as a saving of approximately 15% of total degree cost, available to new international undergraduate students admitted to the Winter 2026 term onwards, with no application required.',
    renewable: true,
    renewal_criteria:
      'Renewable for up to 3 years (3.5 years for Engineering students) of the degree programme, provided the student continues to complete 24 credit hours per calendar year and maintains a minimum UGPA of 80%. A previous version of the programme page stated 30 credit hours per calendar year; the current page states 24 credit hours per calendar year for both Tier 1 and Tier 2.',
    application_required: false,
    automatic_consideration:
      'True for the entrance awards. The official page states: "All international undergraduate students who apply for admission are automatically considered for the following entrance awards based on your admission average - no application is required!" Applications for admission and required supporting documents must still be received by the intake deadlines.',
    intake: 'Fall Term, Winter Term, Spring/Summer Term (University of Regina academic terms)'
  },

  status: 'OPEN',
  status_label: 'Open — Fall 2027 intake',
  status_note:
    'The award is made each intake and is ongoing, but availability is capped per intake. The official page publishes this notice: "Available spots for the International Student of Distinction Scholarship have been filled for the Winter 2027 and Spring/Summer 2027 intakes. If you would like to be considered for this award, please apply for the Fall 2027 intake." The next intake with published availability is therefore Fall 2027, whose application deadline is April 30. Separately, the number of scholarships an international student may apply for increases after the first year, and current students can apply for additional undergraduate awards each term through the Student Awards Management System (SAMS).',

  is_verified: true,
  verification_status: 'active',
  verification_type:
    'Official university self-published award page, corroborated across official uregina.ca admissions, tuition and fees, English language proficiency, housing and news pages',
  last_verified_at: '2026-10-10T15:40:00+00:00',
  last_verified_date: '2026-10-10',
  verified_by:
    'ScholarZone research agent, slot 39 (Canada / University of Regina International Student of Distinction Scholarship)',
  verification_notes:
    'All award values, thresholds, renewal conditions and deadlines in this record were read directly from the official University of Regina UR International scholarships page (uregina.ca/ur-international/scholarships.html) on the verification date, and cross-checked against the official UR International landing page, the official tuition and fees page for international students, the official English Language Proficiency requirements page, the official Apply page and the official Housing Services application page. Eleven official uregina.ca fetches were made, all returning HTTP 200. The logo asset was verified by direct HTTP request returning 200 with Content-Type image/png and inspected at pixel level. One substantive correction to the assignment brief is recorded in verification.unverified_or_removed_claims: the $5,000 award with an 83%+ admission average is the International Entrance Scholarship, a separate instrument in the same entrance award package, and is not the International Student of Distinction Scholarship.',
  next_verification_due: '2027-05-01',

  source_last_updated:
    'No last-updated or publication date is published on the award page itself. The site footer carries "© 2026 University of Regina". The page content references the "increased value of this award will take effect for students starting in the Fall 2026 term onward" and an intake notice naming Winter 2027 and Spring/Summer 2027, which indicates the page was refreshed for the 2027 entry cycle.',
  current_programme_guide_checked:
    'No separate programme guide, rulebook or policy PDF is published for this award. The award terms are published in full on the UR International scholarships page; the central University of Regina Academic Calendar governs admission and fee rules and was not separately consulted for this record.',

  application_deadline: {
    single_central_deadline: false,
    deadline_date: null,
    deadline_timezone:
      'Not published on the award page — the published deadlines carry no year and no clock time. Official uregina.ca pages state "Central Standard Time (CST-SK)" as the University of Regina time zone (UTC-6; the university is in Regina, Saskatchewan), so Regina local time governs, but no time of day is specified.',
    deadline_precision: 'programme_specific',
    typical_application_window:
      'The award deadline is set per intake, not centrally. To be considered for the International Student of Distinction Scholarship a student must apply for admission and submit all required supporting documents by: April 30 for the Fall Term; September 30 for the Winter Term; and January 30 for the Spring/Summer Term. Separate housing deadlines apply to students who are selected: June 15 for the Fall Term, November 15 for the Winter Term and February 15 for the Spring/Summer Term, by which date those students must apply for on-campus housing.',
    application_period:
      'Applications for admission are accepted year-round for international students, but scholarship consideration is tied to the intake. The next intake with published availability is Fall 2027 (application deadline April 30). Students already enrolled may apply for additional undergraduate awards each term through the Student Awards Management System (SAMS).',
    official_rule:
      'The official page publishes recurring month-and-day deadlines by term, with no year attached: "To be considered for the International Student of Distinction Scholarship, students need to apply and submit all required supporting documents by the following deadlines: Fall Term — April 30; Winter Term — September 30; Spring/Summer Term — January 30." A separate table is published for housing: "Students who are selected for the International Student of Distinction Scholarship will need to meet the conditions outlined in their letter of acceptance and apply for on-campus housing by the following deadlines: Fall Term — June 15; Winter Term — November 15; Spring/Summer Term — February 15." The page also states: "If you are currently in your last year of high school, you can still apply for early conditional admission with your in-progress high school transcript. If you are conditionally admitted to the University of Regina, you must submit your final high school transcripts when available, and your final overall average must continue to meet the minimum requirements for the scholarship."',
    deadline_warning:
      'deadline_date is null because the official page publishes only a recurring month and day per term, with no year and no exact calendar date for the current cycle. The only published intake statement for the current cycle is the notice that spots have been filled for the Winter 2027 and Spring/Summer 2027 intakes and that applicants should "apply for the Fall 2027 intake"; read together with the recurring Fall Term deadline of April 30, the next actionable deadline falls on April 30, 2027. That specific date is derived from these two published statements rather than published as an exact date, so it is recorded here rather than in deadline_date. Do not rely on a general admissions deadline: the scholarship deadline is earlier and intake-specific, and the supporting-document deadline for a term can pass before the general application cycle for that term closes.',
    next_verification_due: '2027-05-01'
  },

  programme_duration: {
    official_range:
      '4 years of benefit (renewable for up to 3 years; 3.5 years for Engineering students)',
    duration_years: 4,
    normal_duration_years: 4,
    duration_months: 48,
    renewable: true,
    renewal_note:
      'Tier 1 and Tier 2 are renewable for up to 3 years (3.5 years for Engineering students) of the student\'s degree programme, i.e. one initial award year plus up to three renewal years, for as long as the student completes 24 credit hours per calendar year and maintains a minimum UGPA of 80%. The earlier published version of the programme described the same benefit as "valued at $80,000 for 4 years; 4.5 years for engineering students" with a renewal condition of 30 credit hours per calendar year.'
  },

  funding: {
    scholarship_available: true,
    scholarship_type:
      'Tiered in-kind residence benefit (housing and meal plan) with automatic consideration on admission, plus two separate conditional tuition-credit instruments in the same entrance package',
    scholarship_currency: 'CAD',
    monthly_amount: null,
    monthly_amount_note:
      'No monthly stipend, living allowance or periodic cash payment is published. The award is delivered as free on-campus housing (Tier 1 and Tier 2) and a meal plan (Tier 1 only), which are in-kind benefits provided through Housing and Hospitality Services rather than cash transfers to the student.',
    travel_support: false,
    visa_support: false,
    installation_support: false,
    living_allowance: null,
    insurance: false,
    travel_amount: null,
    travel_amount_note:
      'No travel, airfare or relocation allowance is published. Recipients do receive one-on-one immigration support from the University, which is an advisory service and not a funded visa or travel benefit.',
    institutional_costs: true,
    fully_funded: false,
    fully_funded_note:
      'Not fully funded. The International Student of Distinction Scholarship covers on-campus housing (Tier 1 and Tier 2) and a meal plan (Tier 1 only) and explicitly does not reduce tuition — the page states "This is not a tuition credit scholarship" for both tiers. Tuition support within the same entrance package is delivered only by two separate, conditional instruments: the International Entrance Scholarship ($5,000 tuition credit applied to the first registered term, for admission averages of 83% or higher, in effect for students starting in the Fall 2026 term onward) and the International Undergraduate Student Bursary (up to $20,000 of tuition credit over 4 years at $5,000 per year, requiring pre-payment of two years of tuition before the study permit application and completion of the first year full-time). Books, supplies, food beyond the Tier 1 meal plan, living expenses, health insurance and any travel are not covered. For context, the official tuition page publishes an example average annual cost of CAD $47,000 for an international undergraduate living on campus (tuition and fees $32,500, books and supplies $1,500, on-campus housing $7,000, food and fun $6,000), based on 2026-2027 rates.',
    program_level_funding_figure:
      'Published per-award values only: Tier 1 approximate value $90,000 ($22,500 x 4 years); Tier 2 approximate value $45,000 ($11,250 x 4 years); International Entrance Scholarship $5,000; International Undergraduate Student Bursary up to $20,000 ($5,000 x 4 years). No programme-level budget, number of awards per intake or per-scholar cost is published, and no combined package total is published, so no total is asserted here.'
  },

  funding_breakdown: {
    tuition: {
      covered: false,
      amount: null,
      currency: 'CAD',
      conditions:
        'The International Student of Distinction Scholarship itself provides no tuition credit. The official page states for both tiers: "This is not a tuition credit scholarship." Tuition credit within the same entrance package comes only from two separate instruments: the International Entrance Scholarship ($5,000 tuition credit applied to the first registered term, admission average of 83% or higher, increased value effective for students starting in the Fall 2026 term onward) and the International Undergraduate Student Bursary (tuition credit of up to $20,000 over 4 years at $5,000 per year, for new international undergraduates admitted to the Winter 2026 term onwards, conditional on depositing two years of tuition and completing the first year of full-time study).'
    },
    accommodation_support: {
      covered: true,
      amount: 90000,
      currency: 'CAD',
      conditions:
        'Tier 1: on-campus housing plus a meal plan, published as an approximate value of $90,000 over 4 years ($22,500 x 4 years), for a minimum early conditional or overall final high school average of 90% converted to the Canadian grading scale. Tier 2: on-campus housing only, published as an approximate value of $45,000 over 4 years ($11,250 x 4 years), for a minimum average of 85-89.99% converted to the Canadian grading scale. Selected students must apply for on-campus housing by the housing deadline for their term and meet the conditions in their letter of acceptance. The benefit is delivered through Housing and Hospitality Services, and the published figures are described as approximate values, not guaranteed cash amounts.'
    },
    monthly_stipend: { available: false, note: 'Not published in official source' },
    travel_allowance: { available: false, note: 'Not published in official source' },
    installation_allowance: { available: false, note: 'Not published in official source' },
    visa_support: { available: false, note: 'Not published in official source' },
    insurance: { available: false, note: 'Not published in official source' },
    research_allowance: { available: false, note: 'Not published in official source' },
    book_allowance: { available: false, note: 'Not published in official source' },
    equipment_allowance: { available: false, note: 'Not published in official source' },
    family_allowance: { available: false, note: 'Not published in official source' },
    bond: {
      available: false,
      note:
        'No bond, service obligation, return-home requirement or repayment condition is published for the International Student of Distinction Scholarship. Renewal is conditioned on academic progress only (24 credit hours per calendar year and a minimum UGPA of 80%). The separate International Undergraduate Student Bursary does require a pre-payment of two years of tuition before the credit is issued, which is a funding-flow condition rather than a service bond.'
    },
    total_estimated_value: {
      available: false,
      note:
        'No combined package total is published, so none is computed. The official page publishes separate per-award figures: Tier 1 on-campus housing and meal plan, approximate value $90,000 over 4 years; Tier 2 on-campus housing, approximate value $45,000 over 4 years; International Entrance Scholarship $5,000 tuition credit in the first registered term; International Undergraduate Student Bursary up to $20,000 tuition credit over 4 years. A student may qualify for more than one of these, but the page does not state that all are additive, so no total should be presented to applicants.'
    }
  },

  coverage: [
    'On-campus housing for up to 4 years (Tier 1 and Tier 2)',
    'On-campus meal plan for up to 4 years (Tier 1 only)',
    'One-on-one immigration support for International Student of Distinction Scholars',
    'Guidance for the transition to life in Canada',
    'Personalised orientation and welcome by University leadership',
    'Social events and cultural activities for scholars',
    'Separate instrument: $5,000 tuition credit in the first registered term, for admission averages of 83% or higher (International Entrance Scholarship)',
    'Separate instrument: up to $20,000 of tuition credit over 4 years (International Undergraduate Student Bursary)'
  ],

  coverage_limitations: [
    'Not a tuition credit scholarship. The official page states explicitly for both Tier 1 and Tier 2: "This is not a tuition credit scholarship."',
    'Tier 2 covers on-campus housing only; the meal plan is a Tier 1 benefit only.',
    'Renewal requires completing 24 credit hours per calendar year and maintaining a minimum UGPA of 80%; a reduced course load or a lower UGPA ends the benefit.',
    'The renewal term is shorter than the benefit period: the award is renewable for up to 3 years (3.5 years for Engineering students), so a student on a programme longer than that receives less than the full published value.',
    'No cash stipend, monthly allowance, living allowance, travel, installation, insurance, book or equipment support is published.',
    'Tier 1 and Tier 2 availability is capped by intake. The official notice states that available spots have been filled for the Winter 2027 and Spring/Summer 2027 intakes.',
    'The housing benefit is delivered in kind through Housing and Hospitality Services and depends on continued on-campus residence, which carries its own residence contract, application fee and confirmation fee.',
    'The $90,000 and $45,000 figures are published as "approximate value", so the realised benefit varies with residence rates, room type and the number of terms actually taken.',
    'The exact benefit structure may differ in delivery and in realised value from the published approximate figures; no disbursement schedule is published.',
    'The International Undergraduate Student Bursary is a separate instrument, is not guaranteed by the distinction scholarship, and requires the student to pre-pay two years of tuition in advance of applying for a study permit.',
    'The $5,000 International Entrance Scholarship is a first-term-only tuition credit and is not renewable.'
  ],

  eligible_applicants: [
    'International students applying directly from high school to a University of Regina undergraduate degree programme (Tier 1 and Tier 2)',
    'International students applying to an undergraduate degree programme and paying international tuition fee rates (International Entrance Scholarship and International Undergraduate Student Bursary)',
    'Students entering first-entry undergraduate study; the award is an entrance award, not for students already past first year',
    'Applicants from any country; there is no nationality restriction',
    'Applicants who are in their final year of high school and can apply for early conditional admission with an in-progress transcript',
    'Applicants whose high school average can be converted to the Canadian grading scale; applicants are invited to contact UR International for the requirements for their country curriculum'
  ],

  citizenship_restriction: false,
  worldwide_eligibility: true,
  bachelor_requirement: true,
  final_year_bachelor_allowed: true,
  final_year_condition:
    "For this bachelor's award the relevant condition is secondary school completion, not completion of a bachelor's degree. Applicants must be applying directly from high school to an undergraduate degree programme. The official page states: \"If you are currently in your last year of high school, you can still apply for early conditional admission with your in-progress high school transcript. If you are conditionally admitted to the University of Regina, you must submit your final high school transcripts when available, and your final overall average must continue to meet the minimum requirements for the scholarship.\"",
  equivalent_degree_allowed: true,
  equivalent_degree_note:
    'The award is defined by applying directly from high school, but the University of Regina accepts a wide range of equivalent secondary curricula for admission. The official page states that admission averages are assessed on the Canadian grading scale and that students should contact UR International "for specific requirements based on your country\'s high school curriculum", which indicates country-specific curriculum conversion rather than a single fixed route. No list of accepted equivalent curricula is published on the award page itself.',
  age_limit: {
    minimum_age: null,
    maximum_age: null,
    age_calculation_date: null,
    official_source: null
  },
  gender_restriction: false,
  nationality_quota: null,
  previous_emjm_scholarship_ineligible: false,
  previous_award_restriction:
    'None published. The official page does not bar applicants or recipients from holding or having held other scholarships or awards, and publishes no restriction on concurrent awards, sponsorship or funding. Applicants who already hold an award that covers residence fees are asked to declare it to Housing and Hospitality Services when applying for residence.',

  eligibility: {
    citizenship:
      'No nationality restriction. The award is open to international students from any country, i.e. students who would study at the University of Regina on a study permit and pay international tuition fee rates. Scholars named on the official page come from countries including Vietnam, Bangladesh, China, Nigeria, Pakistan, Mauritius, Sri Lanka, Indonesia, Myanmar and Taiwan.',
    residence_requirement:
      'Tier 1 and Tier 2 recipients must live in on-campus housing. Selected students must apply for on-campus housing by the housing deadline for their term and must meet the conditions set out in their letter of acceptance. Housing and Hospitality Services assigns rooms on a first-come, first-served basis and operates residence terms of Fall and Winter (September-April), Winter (January-April) and Spring and Summer (May-August).',
    age_limit: null,
    secondary_school_requirement:
      'For Tier 1 and Tier 2 the applicant must be applying directly from high school to an undergraduate degree programme. Applicants in their final year of high school may apply for early conditional admission with an in-progress transcript and must submit final transcripts when available, with the final overall average continuing to meet the minimum requirement. For the separate International Entrance Scholarship and International Undergraduate Student Bursary the requirement is admission to an undergraduate degree programme at international tuition rates rather than direct entry from high school.',
    academic_requirements:
      'Tier 1: minimum early conditional or overall final high school average of 90% converted to the Canadian grading scale. Tier 2: minimum average of 85-89.99% converted to the Canadian grading scale. International Entrance Scholarship: admission average of 83% or higher. Renewal of Tier 1 and Tier 2: 24 credit hours per calendar year and a minimum UGPA of 80%.',
    gpa_requirement:
      'A minimum UGPA of 80% is required each year for renewal of Tier 1 and Tier 2. There is no published UGPA minimum for initial consideration, which is based on the high school admission average.',
    language_requirement:
      'Applicants must meet the University of Regina English Language Proficiency requirement for admission, or be issued a conditional letter of acceptance and satisfy the requirement by completing the English for Academic Purposes programme (EAP 100 and EAP 101) or by the other exemption routes on the official ELP page. A conditional acceptance letter is valid for 12 months from the date of issue.',
    work_experience: null,
    extracurricular_requirement: null,
    leadership_requirement: null,
    financial_need: null,
    previous_scholarship_restriction:
      'None published. No restriction on concurrent or previous awards is stated for this scholarship.',
    enrolment_status_requirement:
      'Renewable for up to 3 years (3.5 years for Engineering students) provided the student continues to complete 24 credit hours per calendar year, which effectively requires a full-time or near-full-time course load. The separate International Undergraduate Student Bursary requires the student to complete the first year (3 terms) of full-time study and to register in the following academic term.',
    health_requirement: null,
    field_restrictions:
      'None. No faculty or programme restriction is published, and Engineering is specifically accommodated through a longer renewal period of 3.5 years. Scholars named on the official page study across Physics, Elementary Education, Computer Science, Actuarial Science, Film Production, Software Systems Engineering, Sport and Exercise Science and Business.',
    official_source: 'https://www.uregina.ca/ur-international/scholarships.html'
  },

  academic_requirements: {
    fixed_percentage_requirement: true,
    percentage_note:
      'The thresholds are published as fixed percentages but are explicitly assessed on the Canadian grading scale. The official page states for Tier 1 "a minimum early conditional or overall final high school average of 90% (converted to Canadian grading scale)" and for Tier 2 "a minimum early conditional or overall final high school average of 85-89.99% (converted to Canadian grading scale)", while the International Entrance Scholarship requires "an admission average of at least 85%". The page also states "Wondering if you would qualify for an entrance award? Contact us for specific requirements based on your country\'s high school curriculum!", which indicates that the operative threshold after conversion may vary by country. No exact Canadian-scale equivalence for any specific national curriculum is published.',
    programme_specific_requirements:
      'Renewal thresholds are programme-specific in duration rather than content: the award is renewable for up to 3 years, or 3.5 years for Engineering students, of the student\'s degree programme. No other faculty-specific academic requirements are published for the award itself.',
    selection_factors_may_include: [
      'Admission average, converted to the Canadian grading scale',
      'Early conditional or final overall high school average',
      'Availability of Tier 1 or Tier 2 spots for the chosen intake',
      'Meeting the housing application conditions by the housing deadline, for selected students'
    ],
    holistic_selection_note:
      'Selection is stated to be automatic and average-based, not holistic. The official page says all international undergraduate students who apply for admission "are automatically considered for the following entrance awards based on your admission average - no application is required!" and that eligible students with the highest averages are awarded the scholarship. No interview, essay, portfolio or recommendation is described in the award process, and no published weighting or rubric is given. Marketing language on the page ("Are you an outstanding academic achiever?") describes the profile of successful recipients rather than a published selection criterion.'
  },

  english_requirement: {
    universal_requirement: false,
    minimum_ielts: 6.5,
    minimum_toefl: 83,
    minimum_pte: 59,
    minimum_duolingo: 120,
    moi_rule:
      'English Language Proficiency may be met without a test by: successful completion of at least 3 years of formal, full-time study including grades 10, 11 and 12 with a grade 12 English Language Arts course; or at least 2 years including grades 11 and 12 with a grade 12 English Language Arts course at a minimum final grade of 75%; or graduation from a Canadian secondary school with a grade 12 English Language Arts course at a minimum final grade of 75%. Post-secondary route: at least 24 credit hours at a University of Regina degree-level equivalent from an institution where English was the main medium of instruction, including at least 6 credit hours in humanities or social science subjects, with a minimum GPA of 60.00% on a 50% passing scale. Also accepted: successful completion of EAP 100 and EAP 101 or a minimum placement level of 110 on the EAP placement exam; Advanced Placement English with a grade of 3 or better; International Baccalaureate Higher English with a grade of 4 or better; GCSE/IGCSE/GCE O Level English or English as a Second Language with a minimum grade of 6 (B before 2017), or GCE A/AS/AICE Level English with a minimum grade of C.',
    moi_accepted: true,
    test_score_note:
      'Minimum scores are for most undergraduate programmes. The official ELP page states: "Unless otherwise stated, all test results must be sent directly from the testing agency to the Admissions Office before the application document deadline. Test scores are valid for two years from the test date." Scores: IELTS Academic overall band 6.5 with no band lower than 6.0; TOEFL internet-based overall 83 with minimum sections of 20 in Reading, Listening, Speaking and Writing; PTE Academic overall 59 with no area below 59; Duolingo English Test overall 120 with Literacy 105, Comprehension 105, Conversation 105 and Production 90 (tests taken up to June 30, 2024) or Comprehension 100, Conversation 115 and Production 115 (tests taken July 1, 2024 and onward); CAEL 60; Cambridge C1 Advanced/C2 Proficiency overall 180 with no section below 169; CELT 60, restricted to Francophone students. Institutional TOEFL, TOEFL Essentials and paper-based TOEFL are not accepted. Programme-specific higher requirements apply: the Faculty of Education requires IELTS Academic 7.0 overall with Speaking 7.0, Writing 7.0, Listening 6.0 and Reading 6.0, and TOEFL iBT overall 103 with sections 24/23/27/25; the Faculty of Nursing accepts only IELTS Academic, requiring overall 7.0 with Speaking 7.0, Writing 6.5, Listening 7.0 and Reading 6.5. The ELP page states "ELP requirements are subject to change without notice."',
    test_validity_months: 24,
    accepted_tests: [
      'IELTS Academic',
      'TOEFL internet-based',
      'PTE Academic (including PTE Academic Online)',
      'Duolingo English Test',
      'CAEL',
      'Cambridge C1 Advanced (CAE) / C2 Proficiency (CPE)',
      'CELT (Comprehensive English Language Test, Francophone students only)',
      'UK GCSE/IGCSE/GCE O Level or A/AS/AICE Level English',
      'Advanced Placement English',
      'International Baccalaureate Higher English',
      'University of Regina EAP placement exam'
    ]
  },

  language_of_instruction: {
    programme_specific: true,
    possible_languages: ['English'],
    bilingual_programmes: true,
    language_note:
      'The official ELP page states "The language of instruction for most programs at the University of Regina is English." The university also supports French-language study through La Cité universitaire francophone, which is a federated institution of the University of Regina, and the ELP page treats Francophone education as a distinct category for exemption purposes; the CELT test is restricted to Francophone students. The country ELP list notes that Canadian Francophone education does not meet the English requirement "unless entering a French program - ie: le Bac".'
  },

  application_method: {
    direct_student_application: true,
    central_application: false,
    application_route:
      'Apply directly to the University of Regina through the Student Application Portal at apply.uregina.ca/apply/. No separate scholarship application is required: all international undergraduate applicants are automatically considered for the entrance awards based on their admission average.',
    portal_url: 'https://apply.uregina.ca/apply/',
    application_steps: [
      'Prepare the required documents: high school transcripts (in-progress transcripts are accepted to start the process), and any programme-specific documents such as a Statement of Intent, references or portfolio components.',
      'Create and submit the online undergraduate admission application form in the Student Application Portal, selecting the correct application type for your educational background.',
      'Pay the application fee. The official tuition page states the application fee for international undergraduate students is $100.00 CAD, payable by credit card or Flywire; the general Apply page states $100 CAD for undergraduate applicants, $200 for post-secondary transfer applicants and $125 for graduate applicants.',
      'Submit all required supporting documents by the deadline for the intended intake (April 30 Fall, September 30 Winter, January 30 Spring/Summer).',
      'If you are in your final year of high school, apply for early conditional admission with your in-progress transcript, and submit your final transcripts when available.',
      'Meet the English Language Proficiency requirement, either with an accepted test score or through an exemption route, or accept a conditional offer and complete EAP 100 and EAP 101.',
      'Pay the $1,000 CAD enrolment deposit upon acceptance of admission; class registration cannot proceed until the deposit is received, and 100% of the deposit is applied to tuition and fees. The deposit is non-refundable unless the study permit application is denied, in which case a partial refund of $500 CAD may be requested.',
      'If selected for Tier 1 or Tier 2, apply for on-campus housing through the Housing Services Portal by the housing deadline for your term (June 15 Fall, November 15 Winter, February 15 Spring/Summer). New residents pay a $50 housing application fee and a $400 confirmation fee.'
    ],
    application_fee:
      'CAD $100 for international undergraduate applicants (the general undergraduate rate on the official Apply page is also $100 CAD), payable by credit card or Flywire. A limited promotion of 50% off the application fee was advertised for October 1-10 with the code INDIGOCT2026; verify whether the promotion is active before relying on it. A $1,000 CAD enrolment deposit is payable on acceptance, and new on-campus residents pay a $50 housing application fee plus a $400 confirmation fee.',
    multiple_applications_allowed: null,
    paper_application_available: true
  },

  official_application_documents: {
    universal_documents: [
      'Online undergraduate admission application form',
      'High school transcripts',
      'Payment of the $100 CAD application fee',
      'Proof of English language proficiency, unless an exemption applies'
    ],
    commonly_requested_documents: [
      'In-progress high school transcript for early conditional admission',
      'Final high school transcripts once available, for conditionally admitted students',
      'College or university transcripts (for the $200 post-secondary transfer application route)',
      'Statement of Intent (the official Education Profile - Statement of Intent form is published in English and French)',
      'References, where requested by the application type',
      'Portfolio components, for programmes that require them'
    ],
    two_recommendation_letters: null,
    secondary_school_documents:
      'High school transcripts are the core academic document. The official Apply page states "Every application type has specific documents that must be submitted in support of the application. Depending on your application, this could include: High school transcripts; College or university transcripts; Statement of Intent; References; Portfolio components." For the scholarship specifically, the page states that an applicant in the last year of high school can apply for early conditional admission with an in-progress transcript, and that a conditionally admitted student must submit final high school transcripts when available with the final overall average continuing to meet the requirement.',
    document_language: null,
    document_format: null,
    transcript_requirement:
      'Final high school transcripts must be submitted when available for conditionally admitted students. No specific format, digitisation standard or upload portal is published on the award page; the university directs applicants to the Admission Documents and Transcripts page and the online Application Guide.',
    certified_translation_requirement: null
  },

  document_checklist: {
    identity_documents: [
      {
        document: 'Study permit and immigration documents',
        requirement: 'Required after acceptance, not for the scholarship application',
        source:
          'Official Next Steps Checklist: after accepting and paying the deposit the student is eligible for a Provincial Attestation Letter (PAL) and then applies for a study permit through IRCC. A copy of immigration documents must be provided to UR International by the specified deadline, usually the second week of classes, to remain registered in the first term.'
      }
    ],
    academic_documents: [
      {
        document: 'High school transcripts',
        requirement: 'Required; an in-progress transcript is accepted for early conditional admission',
        source: 'Official UR International scholarships page and official Apply page'
      },
      {
        document: 'Final high school transcripts',
        requirement:
          'Required when available for conditionally admitted students; final overall average must continue to meet the minimum scholarship requirement',
        source: 'Official UR International scholarships page'
      },
      {
        document: 'Statement of Intent (Education Profile)',
        requirement: 'Required for some application types',
        source: 'Official Apply page, general application forms list'
      }
    ],
    language_documents: [
      {
        document: 'English Language Proficiency test result',
        requirement:
          'Required unless an exemption applies; must be sent directly from the testing agency to the Admissions Office before the application document deadline; valid for two years from the test date',
        source: 'Official English Language Proficiency (ELP) Requirements page'
      },
      {
        document: 'English test exemption evidence',
        requirement:
          'Required where proficiency is claimed through prior schooling, post-secondary study, AP/IB, GCSE/IGCSE or EAP completion',
        source: 'Official English Language Proficiency (ELP) Requirements page'
      }
    ],
    recommendation_documents: [],
    application_essays: [],
    financial_documents: [
      {
        document: 'Two years tuition deposit (for the separate International Undergraduate Student Bursary)',
        requirement:
          'Only if seeking the bursary: pay two years of tuition to the University of Regina, according to the one-year tuition figure stated on the acceptance letter, in advance of applying for a study permit',
        source: 'Official UR International scholarships page, Bursary Requirements'
      },
      {
        document: 'Proof of funds',
        requirement:
          'Required for the Canadian study permit application, which is part of the post-admission process rather than the scholarship application',
        source: 'Official Next Steps Checklist'
      },
      {
        document: '$1,000 CAD enrolment deposit',
        requirement: 'Payable upon acceptance of admission',
        source: 'Official UR International tuition and fees page'
      }
    ],
    additional_documents: [
      {
        document: 'Housing Services Portal residence application',
        requirement:
          'Required only for students selected for Tier 1 or Tier 2, by the housing deadline for their term; $50 application fee for new residents and a $400 confirmation fee',
        source: 'Official Housing Services Apply page and UR International scholarships page'
      }
    ]
  },

  required_documents: [
    'Online undergraduate admission application form (Student Application Portal)',
    'High school transcript (in-progress transcript accepted for early conditional admission)',
    'Final high school transcripts, for conditionally admitted students, available when issued',
    'Payment of the CAD $100 international undergraduate application fee (credit card or Flywire)',
    'English Language Proficiency test result sent directly from the testing agency, unless an exemption applies',
    'CAD $1,000 enrolment deposit upon acceptance of admission',
    'Residence application through the Housing Services Portal, for students selected for Tier 1 or Tier 2'
  ],

  selection_process: {
    decision_maker:
      'University of Regina International Enrolment Services and International Recruitment (UR International), with Housing and Hospitality Services administering the residence component for selected students',
    selection_type:
      'Automatic consideration on admission, ranked by admission average; higher averages take priority within each intake, with a fixed number of Tier 1 and Tier 2 spots per intake',
    central_selection: false,
    possible_stages: [
      'Application for admission submitted before the intake deadline',
      'All required supporting documents received before the intake deadline',
      'Automatic assessment against the Tier 1 (90%+) and Tier 2 (85-89.99%) thresholds, converted to the Canadian grading scale',
      'Awarding of Tier 1 or Tier 2 subject to spot availability for that intake',
      'Letter of acceptance issued, setting out the scholarship conditions',
      'Housing application through the Housing Services Portal by the housing deadline, for selected students',
      'Annual renewal assessment against 24 credit hours per calendar year and a minimum UGPA of 80%'
    ],
    official_universal_weighting: null,
    weighting_note:
      'No published weighting, scoring rubric or ranking of criteria is given. Selection is described as automatic and driven by the admission average, with Tier 1 and Tier 2 thresholds as the operative cut-offs and spot availability as the practical constraint. No interview is described at any stage.',
    interview_possible: false,
    results_timing:
      'No notification date, decision window or results-release schedule is published. Selection is made on the same basis as admission, so applicants learn of the award with their offer of admission, and selected students must then apply for housing by the term housing deadline (June 15 Fall, November 15 Winter, February 15 Spring/Summer).',
    scholarship_rank_note:
      'The award is tiered by admission average rather than ranked among recipients: Tier 1 is for a minimum average of 90%, Tier 2 for 85-89.99%. Within a tier, availability is capped per intake, so applicants with the highest averages in that tier are given priority. The official page publishes no cap on the number of Tier 1 or Tier 2 awards per intake.'
  },

  selection_criteria: {
    academic_excellence: true,
    leadership: null,
    community_service: null,
    extracurricular_achievement: null,
    financial_need: false,
    additional_factors: [
      'Conversion of the high school average to the Canadian grading scale',
      'Applying directly from high school to an undergraduate degree programme',
      'Availability of Tier 1 or Tier 2 spots for the specific intake',
      'Meeting the housing application conditions in the letter of acceptance, for selected students'
    ],
    interview_required: false,
    portfolio_required: false,
    source: 'https://www.uregina.ca/ur-international/scholarships.html'
  },

  degree_outcome: {
    awarded_qualification:
      "Bachelor's degree from the University of Regina; the scholarship is an entrance funding award, not a qualification",
    typical_programme_length:
      'Typically 4 years; the award benefit is published over 4 years with a renewal period of up to 3 years (3.5 years for Engineering students)',
    possible_awards: [
      'Tier 1: on-campus housing plus meal plan, approximate value $90,000 over 4 years',
      'Tier 2: on-campus housing, approximate value $45,000 over 4 years',
      'International Entrance Scholarship: $5,000 tuition credit in the first registered term',
      'International Undergraduate Student Bursary: up to $20,000 of tuition credit over 4 years'
    ],
    degree_note:
      'The official page names a wide range of undergraduate degree programmes among current scholars, including BSc Physics, BEd Elementary Education, BSc Computer Science, BSc Actuarial Science, BFA Film Production, BEng Software Systems Engineering, BKin Sport and Exercise Science and BBA Business. There is no faculty restriction on the award, and Engineering receives a longer renewal period of 3.5 years.',
    credit_transfer:
      'Not addressed on the award page. The official tuition page states that a $150 CAD administration fee applies to international undergraduate students who request a faculty transfer and have no credit hours earned at the University of Regina.'
  },

  student_rights_and_cost_protection: {
    tuition_fee_for_recipients:
      'Recipients continue to pay international undergraduate tuition. The award does not reduce tuition: the official page states "This is not a tuition credit scholarship" for both Tier 1 and Tier 2. Published international undergraduate tuition and fees averaged $32,500 for 30 credit hours (10 classes) in the 2026-2027 academic year, and the official page publishes a total estimated annual cost of $47,000 CAD for an international undergraduate living on campus (tuition and fees $32,500, books and supplies $1,500, on-campus housing $7,000, food and fun $6,000). Tuition fees vary by faculty and are subject to change every term.',
    application_fee_for_recipients:
      'Recipients pay the same application fee as other applicants: $100 CAD for international undergraduate applicants, payable by credit card or Flywire in the Student Application Portal. No scholarship-specific fee waiver is published. A $1,000 CAD enrolment deposit is payable on acceptance, and 100% of it is applied toward tuition and fees. New on-campus residents pay a $50 housing application fee and a $400 confirmation fee.',
    student_agreement:
      'Selected Tier 1 and Tier 2 students must "meet the conditions outlined in their letter of acceptance and apply for on-campus housing by the following deadlines." Housing and Hospitality Services operates three residence terms (Fall and Winter September-April, Winter January-April, Spring and Summer May-August); residents are bound by the residence contract term, which may differ from academic semesters, and must read their letter of offer and residence contract. Residents apply through the Housing Services Portal, and a $400 confirmation fee payment signifies agreement to the expectations set out in the letter of offer.',
    programme_website: 'https://www.uregina.ca/ur-international/scholarships.html',
    common_services:
      'International Student of Distinction Scholars receive one-on-one immigration support, guidance for the transition to life in Canada, personalised orientation and welcome by University leadership, and social events and cultural activities. Broader student services listed on the university site include the Student Wellness Centre, Mental Wellness Hub, accessibility and student ID services, and UR International immigration resources.',
    bond_requirement:
      'No bond, service obligation or return-home requirement is published for this scholarship. Renewal is conditioned solely on academic progress (24 credit hours per calendar year and a minimum UGPA of 80%). The separate International Undergraduate Student Bursary requires a two-year tuition pre-payment, which is a funding-flow condition rather than a service bond.',
    bond_breach_consequence:
      'No bond exists, so no breach consequence is published. If a recipient fails to complete 24 credit hours per calendar year or to maintain a minimum UGPA of 80%, the residence benefit is not renewed for the following year; the official page describes the award as renewable "as long as" those conditions continue to be met.'
  },

  practical_application_data: {
    application_readiness_checklist: [
      'Obtain an official in-progress high school transcript showing grades and the current average',
      'Calculate or obtain the Canadian-scale equivalent of the high school average; contact UR International at International.Recruitment@uregina.ca or +1 (306) 337-3309 to confirm the equivalent for your country curriculum, since the thresholds are assessed on the Canadian grading scale',
      'Confirm the admission average reaches 85% or above on the Canadian scale for Tier 2, or 90% or above for Tier 1',
      'Book and sit an accepted English proficiency test well before the intake deadline, since results must be sent directly from the testing agency before the application document deadline and are valid for only two years',
      'Create the account in the Student Application Portal at apply.uregina.ca and submit the application form for the intended intake',
      'Pay the CAD $100 application fee by credit card or Flywire',
      'Upload all supporting documents before the intake deadline (April 30 Fall, September 30 Winter, January 30 Spring/Summer), not before a general admissions deadline',
      'If in the final year of high school, apply for early conditional admission and plan to submit final transcripts as soon as they are available, with the final average still meeting the threshold',
      'Prepare the CAD $1,000 enrolment deposit for payment on acceptance',
      'Keep the housing deadline for the term in view (June 15 Fall, November 15 Winter, February 15 Spring/Summer), since selected students must apply for on-campus housing by then and rooms are assigned first-come, first-served',
      'Confirm current intake availability before relying on the award, because the page states that Tier 1 spots for Winter 2027 and Spring/Summer 2027 are already filled'
    ],
    programme_comparison_fields: [
      'Award instrument: in-kind housing benefit versus tuition waiver or cash stipend',
      'Published value: Tier 1 approx. CAD $90,000; Tier 2 approx. CAD $45,000',
      'Threshold for top tier: 90% admission average on the Canadian scale',
      'Threshold for second tier: 85-89.99% admission average on the Canadian scale',
      'Threshold for the separate entrance tuition credit: 83% admission average',
      'Application requirement: none for the scholarship (automatic on admission)',
      'Renewal: 24 credit hours per calendar year and a minimum UGPA of 80%',
      'Benefit period: 4 years, with renewal for up to 3 years (3.5 for Engineering)',
      'Meal plan included: Tier 1 only',
      'Tuition covered: not by the distinction scholarship; only via separate conditional instruments',
      'Published per-intake availability: capped; Winter 2027 and Spring/Summer 2027 filled',
      'Residence obligation: on-campus housing is mandatory for the benefit'
    ],
    motivation_letter_strategy:
      'No motivation letter, essay, personal statement or interview forms part of this award, so no statement strategy applies to the scholarship decision. Written material still matters for admission: the official Apply page lists a Statement of Intent among the documents that a given application type may require, and the university publishes an official Education Profile - Statement of Intent form in English and French, plus a Mature Admission Personal Statement form. Applicants should focus effort on documentary accuracy and on confirming the Canadian-scale conversion of their average rather than on persuasive writing.',
    profile_fit_labels: [
      'High-achieving international student applying directly from high school',
      'Admission average of 90% or above on the Canadian scale (Tier 1)',
      'Admission average of 85-89.99% on the Canadian scale (Tier 2)',
      'Student wanting on-campus housing included in the award',
      'Student comfortable committing to full-time study of 24 credit hours per calendar year',
      'Student planning a 4-year undergraduate degree, or a 4.5-year Engineering degree',
      'Applicant seeking a Canada-hosted undergraduate scholarship with automatic consideration'
    ],
    common_mistakes: [
      'Assuming the award reduces tuition. The official page states for both tiers that it "is not a tuition credit scholarship."',
      'Assuming the $5,000 award with the 83% threshold is the distinction scholarship. It is the International Entrance Scholarship, a separate instrument in the same entrance package.',
      'Applying for the wrong intake without checking the filled-spots notice; Winter 2027 and Spring/Summer 2027 Tier 1 spots are already filled, and the instruction is to apply for the Fall 2027 intake.',
      'Using a national high school percentage directly against the thresholds without conversion. The thresholds are assessed on the Canadian grading scale, and the university invites applicants to contact it for country-specific requirements.',
      'Missing the intake supporting-document deadline and relying on a general admissions deadline instead.',
      'Being admitted conditionally and treating the award as secured. Final transcripts must still be submitted and the final overall average must continue to meet the minimum requirement.',
      'Registering for fewer than 24 credit hours in a calendar year and losing renewal.',
      'Assuming the CAD $90,000 or CAD $45,000 figure is a cash payment. Both are published as an "approximate value" of housing and, for Tier 1, a meal plan.',
      'Applying for housing late. Selected students must apply by the term housing deadline, and rooms are assigned first-come, first-served.',
      'Expecting the meal plan under Tier 2. The meal plan is a Tier 1 benefit only.',
      'Paying two years of tuition for the bursary without reading its conditions. The $20,000 tuition credit requires the pre-payment, completion of the first year full-time, registration in the next term and no outstanding tuition fees, and it is a separate instrument from the distinction scholarship.'
    ]
  },

  risk_flags: [
    {
      risk: 'Award value and scope misread, including confusion with the companion tuition awards',
      impact:
        'Applicants may believe the CAD $90,000 or CAD $45,000 figure reduces tuition and budget incorrectly, leaving the full international tuition of around CAD $32,500 per year plus fees uncovered. They may also mistake the separate CAD $5,000 International Entrance Scholarship with its 83% threshold for the distinction scholarship, believing the package includes a renewable tuition reduction that is neither renewable nor part of the distinction award.',
      mitigation:
        'The official page states explicitly for both tiers that the award "is not a tuition credit scholarship". Programme action, programme_structure.award_types_detail, funding_breakdown.tuition, coverage_limitations and the verification notes each distinguish the instruments, and the discrepancy with the assignment brief is recorded in unverified_or_removed_claims.'
    },
    {
      risk: 'Tier 1 spots exhausted for the intended intake',
      impact:
        'An applicant targeting Winter 2027 or Spring/Summer 2027 may spend effort on a cycle with no Tier 1 availability, and receive nothing despite a qualifying average.',
      mitigation:
        'The published notice states that available spots have been filled for the Winter 2027 and Spring/Summer 2027 intakes and directs applicants to the Fall 2027 intake. Status, status_note and common_mistakes all carry this, and next_verification_due is set to 2027-05-01 to re-check the notice.'
    },
    {
      risk: 'Average conversion uncertainty',
      impact:
        'The thresholds are published as percentages "converted to Canadian grading scale", so a student whose raw national average is 90% may or may not clear the Canadian-scale threshold, and no equivalence table is published.',
      mitigation:
        'Academic requirements and eligibility.academic_requirements record the conversion basis and quote the page directing applicants to contact UR International for country-specific requirements; the route and contact details are in application_method.'
    },
    {
      risk: 'Renewal loaded on course load and UGPA',
      impact:
        'A student who takes fewer than 24 credit hours in a calendar year or drops below a UGPA of 80% loses the residence benefit from the following year, and the renewal period (3 years, 3.5 for Engineering) is shorter than the published 4-year value.',
      mitigation:
        'Programme duration, funding_breakdown and coverage_limitations state the renewal conditions and the shorter renewal period, and the risk is called out in common_mistakes.'
    },
    {
      risk: 'In-kind value is an approximation with no disbursement schedule',
      impact:
        'The realised value depends on residence rates, room type and terms taken, and no schedule of how the benefit is applied is published, so the published figure may not match the benefit received.',
      mitigation:
        'The record presents both figures as published "approximate value" amounts, sets total_estimated_value to unavailable rather than computing a total, and notes the absence of a disbursement schedule in verification notes.'
    },
    {
      risk: 'Deadlines are recurring month-and-day only, with no year or clock time',
      impact:
        'An applicant may treat "April 30" as a soft date or assume a general admissions deadline applies, and may submit late because no exact calendar date or time of day is published.',
      mitigation:
        'deadline_date is set to null with deadline_precision "programme_specific" per the accuracy rule, the recurring dates are quoted verbatim in official_rule, the derived next date of April 30, 2027 is labelled as derived in deadline_warning, and the Regina time zone note is recorded.'
    },
    {
      risk: 'Residence contract obligations attach to the benefit',
      impact:
        'Selected students are bound to a residence term and contract that may differ from academic semesters, with a $50 housing application fee and a $400 confirmation fee, and rooms are assigned first-come, first-served.',
      mitigation:
        'Application steps, document_checklist.additional_documents and student_rights_and_cost_protection.student_agreement record the housing route, the fees and the first-come, first-served basis.'
    },
    {
      risk: 'Programme-specific English requirements exceed the general minimum',
      impact:
        'An applicant to the Faculty of Education or Nursing who meets the general IELTS 6.5 minimum may not meet the higher programme-specific requirement, and Nursing accepts only IELTS Academic.',
      mitigation:
        'English requirement records the general minimums as the headline figures and states the Faculty of Education and Faculty of Nursing requirements explicitly in test_score_note, attributing them to the official ELP page.'
    }
  ],

  application_status_workflow: [
    'Intake not yet open or chosen',
    'Application for admission in progress',
    'Application and all required supporting documents submitted before the intake deadline',
    'Under assessment for admission and for automatic entrance-award consideration',
    'Offer of admission issued; entrance award awarded or not awarded with the offer',
    'Award accepted; CAD $1,000 enrolment deposit paid',
    'Selected for Tier 1 or Tier 2: residence application submitted by the housing deadline',
    'Housing offer and confirmation fee paid; residence contract term accepted',
    'Study permit applied for using the Provincial Attestation Letter',
    'Registered in first term; immigration documents provided to UR International',
    'Annual renewal assessed: 24 credit hours per calendar year and UGPA of 80% or above',
    'Renewal granted or benefit ended'
  ],

  best_fit:
    'A high-achieving international student applying directly from high school to a University of Regina undergraduate degree programme, with a high school average of 85% or above once converted to the Canadian grading scale, who wants on-campus housing and, for Tier 1, a meal plan covered for the duration of the degree, does not need a tuition reduction, and can sustain a full-time load of at least 24 credit hours per calendar year with a UGPA of 80% or above.',

  not_best_fit: [
    'A student who needs a tuition waiver or tuition credit as the core benefit',
    'A student who must live off campus or outside the university residence system',
    'A student who cannot commit to at least 24 credit hours per calendar year or to maintaining an 80% UGPA',
    'A student applying from a post-secondary institution rather than directly from high school, for Tier 1 or Tier 2',
    'A student needing a cash stipend for living costs, travel, insurance or books',
    'A student seeking a scholarship with a written application, essay or interview in which to demonstrate leadership or community impact',
    'A student on a programme substantially longer than four years, since renewal stops after 3 years (3.5 for Engineering)',
    'A student with a financial need profile looking for need-based assistance, since no financial need criterion is applied'
  ],

  image: {
    logo_url: 'https://www.uregina.ca/apple-touch-icon-152x152.png',
    logo_source_url: 'https://www.uregina.ca/ur-international/scholarships.html',
    logo_source_type: 'official_provider_page',
    logo_verified: true,
    logo_verified_at: '2026-10-10',
    logo_verification_method:
      'Direct HTTP request to https://www.uregina.ca/apple-touch-icon-152x152.png returned HTTP 200 with Content-Type image/png and 55,598 bytes. The asset was downloaded and inspected: it is a 152x152 PNG with alpha, whose dominant colour is the University of Regina institutional green #005837 (4,449 of the sampled opaque pixels) on white (963), with secondary tones #6fa18e, #56907a, #d6e4df and #e5eeeb. The mark was rendered to an ASCII raster and read visually: it resolves to a stylised monogram of interlocking letters forming the University of Regina "UR" mark in solid ink on a light field. Because the asset is served from the awarding institution\'s own domain, uregina.ca, it is the institution\'s own brand mark rather than an aggregator or third-party image, and no other awarding body is involved. The University of Regina header on its official pages renders the full logo as an inline SVG shield with the same green #143727 and gold #FFB711, which corroborates that this icon is the institutional mark; no standalone SVG logo file is published at a stable path on uregina.ca, so this official icon asset is the verifiable mark. The icon is a light-on-white mark with solid dark-green ink, so it is not a white wordmark on a transparent background and remains visible on a light card.',
    image_url:
      'https://www.uregina.ca/ur-international/assets/images/heros/five-students-on-bench-cropped-1600x828.jpg',
    image_source_url: 'https://www.uregina.ca/ur-international/scholarships.html',
    image_source_type: 'official_provider_page',
    image_verified: true,
    image_verified_at: '2026-10-10',
    image_alt_text:
      'Five University of Regina students seated together on a bench on campus, used as the hero image on the official UR International scholarships page',
    image_usage_note:
      'Official University of Regina hero photograph published on the UR International scholarships page and registered as that page\'s og:image. Verified by direct HTTP request returning HTTP 200, Content-Type image/jpeg, 425,583 bytes and dimensions 1600x828. This is a campus photograph of students rather than a programme logo and carries no published photographer credit on the page; it should be credited to the University of Regina.'
  },

  official_source: 'University of Regina — UR International',
  official_source_url: 'https://www.uregina.ca/ur-international/scholarships.html',
  official_programme_guide_url: null,
  official_catalogue_url: null,
  official_application_route:
    'Apply directly to the University of Regina through the Student Application Portal at apply.uregina.ca/apply/ by the deadline for the intended intake; no separate scholarship application is required because entrance awards are considered automatically on the admission average.',
  official_updates_url: 'https://www.uregina.ca/ur-international/scholarships.html',

  verification: {
    is_verified: true,
    verification_status: 'active',
    last_verified_at: '2026-10-10T15:40:00+00:00',
    last_verified_date: '2026-10-10',
    verification_date_meaning:
      'Date on which the official uregina.ca pages listed in source_citations were fetched in full and read, and on which the logo and hero image assets were verified by direct HTTP request and inspected. All award values, thresholds, deadlines and conditions in this record reflect those pages as published on the verification date.',
    verified_by:
      'ScholarZone research agent, slot 39 (Canada / University of Regina International Student of Distinction Scholarship)',
    source_type: 'official_university',
    source_domain: 'uregina.ca',
    verification_confidence: 0.92,
    official_fields_confirmed: [
      'Official award name: International Student of Distinction Scholarship, with tiers published as "International Student of Distinction Scholarship: Tier 1" and "International Student of Distinction Scholarship: Tier 2"',
      'Official name and value of the companion entrance award: International Entrance Scholarship, $5,000',
      'Official name and value of the companion bursary: International Undergraduate Student Bursary, $20,000 ($5,000 x 4 years) tuition credit',
      'Tier 1 benefit and value: on-campus housing and a meal plan, approximate value $90,000 ($22,500 x 4 years) over 4 years',
      'Tier 2 benefit and value: on-campus housing, approximate value $45,000 ($11,250 x 4 years) over 4 years',
      'Tier 1 threshold: minimum early conditional or overall final high school average of 90% (converted to Canadian grading scale)',
      'Tier 2 threshold: minimum early conditional or overall final high school average of 85-89.99% (converted to Canadian grading scale)',
      'International Entrance Scholarship threshold: admission average of 83% or higher, with $5,000 tuition credit applied to the first registered term',
      'Explicit statement that the Tier 1 and Tier 2 awards are not tuition credit scholarships',
      'Automatic consideration with no separate scholarship application, for all international undergraduate applicants',
      'Automatic consideration for Tier 1 and Tier 2 restricted to students applying directly from high school',
      'Renewal: up to 3 years, 3.5 years for Engineering students, conditional on 24 credit hours per calendar year and a minimum UGPA of 80%',
      'Application deadlines by intake: Fall Term April 30, Winter Term September 30, Spring/Summer Term January 30',
      'Housing deadlines by intake for selected students: Fall Term June 15, Winter Term November 15, Spring/Summer Term February 15',
      'Early conditional admission from the final year of high school with in-progress transcripts, and the final-average condition',
      'The filled-spots notice for the Winter 2027 and Spring/Summer 2027 intakes, with the instruction to apply for the Fall 2027 intake',
      'International Undergraduate Student Bursary terms: available to new international undergraduates admitted from the Winter 2026 term onwards, no application required, two-year tuition deposit, first-year full-time completion, $5,000 credit per year up to $20,000, renewal conditions',
      'Supportive programming for scholars: one-on-one immigration support, transition guidance, personalised orientation and welcome by University leadership, social events and cultural activities',
      'Scholar countries of origin and current scholar programme list published on the page',
      'Automatic consideration basis, award intake structure (Fall, Winter, Spring/Summer) and the SAMS route for further awards after the first year',
      'English Language Proficiency minimum scores for most undergraduate programmes and the Faculty of Education and Faculty of Nursing variants, test validity of two years, and the exemption routes',
      'Application fee of CAD $100 for international undergraduate applicants and the CAD $1,000 enrolment deposit terms',
      'Housing route and fees: Housing Services Portal, $50 application fee for new residents, $400 confirmation fee, first-come first-served room assignment, three residence terms',
      'International undergraduate cost context: CAD $32,500 tuition and fees for 30 credit hours in 2026-27 and a CAD $47,000 annual total for a student living on campus',
      'Official University of Regina brand icon asset on uregina.ca and the official hero photograph on the award page'
    ],
    programme_check_required: [
      'Whether the Fall 2027 intake has Tier 1 and Tier 2 availability remaining at the time an applicant applies, and the date any further filled-spots notice is published',
      'The exact Canadian-scale equivalence for each national high school curriculum, since thresholds are published only as percentages converted to the Canadian grading scale and no equivalence table is given',
      'The number of Tier 1 and Tier 2 awards available per intake, which is not published',
      'The disbursement schedule by which the housing and meal-plan benefit is applied, since the values are published as approximate amounts',
      'Whether the CAD $90,000 and CAD $45,000 values are recalculated each intake, and against which residence rate year',
      'Whether the International Entrance Scholarship, Tier 1/Tier 2 and the Bursary can be held simultaneously and are additive, which the page does not state',
      'The English Language Proficiency scores, which the official ELP page states are "subject to change without notice"',
      'Whether the 50% application fee promotion with code INDIGOCT2026 is live, and in which cycle it applies',
      'Any change in the renewal credit-hour requirement, since an older version of the page stated 30 credit hours per calendar year against the current 24',
      'The separate Student Awards Management System (SAMS) award deadlines and values, which are outside the scope of this record',
      'Re-check all dates and the filled-spots notice when the 2028-entry cycle opens'
    ],
    unverified_or_removed_claims: [
      'CORRECTION TO THE ASSIGNMENT BRIEF — the brief attributes a CAD $5,000 award with an 83%+ admission average to the International Student of Distinction Scholarship. The official page publishes these as two distinct instruments: the CAD $5,000 award with the 83% admission-average threshold is the International Entrance Scholarship, a separate tuition-credit award in the same entrance package, awarded to all international undergraduate applicants; the International Student of Distinction Scholarship itself is published only as Tier 1 (CAD $90,000 approximate value of housing and a meal plan, 90%+ average) and Tier 2 (CAD $45,000 approximate value of housing, 85-89.99% average). No CAD $5,000 figure, and no 83% threshold, is attached to the distinction scholarship anywhere on the official page.',
      'REMOVED / SUPERSEDED — the brief describes the awards as "housing benefits, NOT tuition credits", which is correct and is quoted verbatim in this record. However, an older version of the UR International scholarship page, still reachable at uregina.ca/international/future-students/scholarship/index.html, described the International Student of Distinction Scholarship as "$80,000 ($20,000 x 4 years)", with free on-campus housing and a meal plan for 4 years (4.5 years for engineering), 50 international students per term, and renewal at 30 credit hours per calendar year and a UGPA of 80%. That page is not the current award page and its figures are not used here. The University of Regina news story of 3 September 2024 also describes the scholarship as "valued at $80,000" for the inaugural 2024 cohort. The current page supersedes these with the tiered structure of CAD $90,000 and CAD $45,000.',
      'UNVERIFIED — the brief\'s reference to "the international undergraduate entrance award package (uregina.ca/ur-international/scholarships)" as the page URL. The live official page is at https://www.uregina.ca/ur-international/scholarships.html and is the source of every value in this record; no separate package page exists.',
      'UNVERIFIED — the number of Tier 1 or Tier 2 awards per intake. The current page states that spots for the Winter 2027 and Spring/Summer 2027 intakes are filled but does not publish the total number of awards available.',
      'NOT VERIFIED — any clock time or time of day for the published deadlines. The deadlines are published as month and day only, with no year and no time. The time zone is taken from the university\'s general statement of "Central Standard Time (CST-SK)" rather than from the award page.',
      'NOT VERIFIED — the deadline for the current cycle as an exact calendar date. The page publishes recurring month-and-day deadlines by term, so deadline_date is null and the forthcoming April 30, 2027 date is derived from the published Fall Term deadline plus the notice directing applicants to the Fall 2027 intake.',
      'NOT VERIFIED — the exact English Language Proficiency minimum for applicants whose prior education was not in English. Individual ELP test minimums are confirmed, but the exemption list is country-specific and is published on a separate page that was not consulted in full.',
      'RETRIEVAL LIMITATION — the University of Regina Undergraduate Academic Calendar, which governs admission and fee rules, was not consulted; the award terms on the UR International page are the sole rule source for this record.',
      'NOT VERIFIED — the SAMS award catalogue values and deadlines, which are outside the scope of the entrance award package recorded here.'
    ],
    source_citations: [
      'https://www.uregina.ca/ur-international/scholarships.html — primary official award page: award names, Tier 1 and Tier 2 values, thresholds, automatic consideration, renewal conditions, application and housing deadlines by intake, the filled-spots notice for Winter 2027 and Spring/Summer 2027, International Entrance Scholarship terms, International Undergraduate Student Bursary terms, supportive programming, scholar countries and programme list, contact details (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/ur-international/index.html — official UR International landing page: confirms the International Student of Distinction Scholarship as "valued up to $90,000", the entrance scholarships designated specifically for international undergraduate students, on-campus housing and the SAMS route for later awards (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/ur-international/tuition-and-fees.html — official international tuition and fees page: CAD $32,500 tuition and fees for 30 credit hours in 2026-27, CAD $47,000 total estimated annual cost on campus, CAD $100 international undergraduate application fee, CAD $1,000 enrolment deposit terms, CAD $150 faculty transfer fee, CAD $50 acceptance letter reprint fee (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/admissions/undergraduate/english-language-proficiency.html — official ELP requirements page: general ELP test minimums (IELTS Academic 6.5 with no band below 6.0, TOEFL iBT 83 with sections 20, PTE 59, Duolingo 120, CAEL 60, Cambridge 180), Faculty of Education and Faculty of Nursing variants, exemption routes, two-year test validity (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/admissions/apply.html — official Apply page: three-step application process, document types, CAD $100 undergraduate and CAD $200 transfer application fees, the 50% application fee promotion for October 1-10 with code INDIGOCT2026, and the offices handling international undergraduate admissions (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/housing-services/apply.html — official Housing Services application page: Housing Services Portal route, $50 new-resident application fee, $400 confirmation fee, first-come first-served room assignment, the three residence terms, and the requirement to declare a scholarship that covers residence fees (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/ur-international/next-steps-checklist.html — official Next Steps Checklist for international undergraduates: CAD $1,000 enrolment deposit terms, Provincial Attestation Letter, study permit application, study permit copy deadline (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/ur-international/admission-policies.html — official admission policies page: English Language Proficiency requirement, the 12-month validity of a conditional acceptance letter, EAP route, faculty admission requirements by country (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/admissions/application-guide/index.html — official Application Guide for undergraduate programmes: application types by educational background and programme-specific requirements (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/stories/2024/09/welcoming-the-u-of-rs-first-international-student-of-distinction-scholars.html — official University of Regina news story, 3 September 2024: inaugural 2024 cohort, description of the scholarship as "valued at $80,000" awarding free on-campus housing and meal plans for the 4-year programme, automatic consideration for students applying directly from high school, and confirmation that eligible students with the highest averages are awarded (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/cost-aid/funding/undergraduate-scholarships/sams.html — official Student Awards Management System page for undergraduate scholarships and awards, cited for the route current students use to apply for further awards (fetched 2026-10-10, HTTP 200)',
      'https://www.uregina.ca/apple-touch-icon-152x152.png — official University of Regina brand icon asset on uregina.ca, verified by direct HTTP request (HTTP 200, Content-Type image/png, 55,598 bytes, 152x152) and inspected at pixel level',
      'https://www.uregina.ca/ur-international/assets/images/heros/five-students-on-bench-cropped-1600x828.jpg — official hero photograph on the UR International scholarships page, registered as that page\'s og:image, verified by direct HTTP request (HTTP 200, Content-Type image/jpeg, 425,583 bytes, 1600x828)'
    ]
  },

  database_notes: [
    'ASSIGNMENT CONFLICT — this session was assigned slot 39 (Canada / University of Regina International Student of Distinction Scholarship) with the numbered 78-key SCHEMA_CONTRACT.md schema. A later resume instruction referred to "slot 03" and to not overwriting the b01 record. Slot 03 is 03-italy-maeci-ire-scholarships.json, which is already complete under the older six-key b-slot schema, and b01-maeci-scholarships-foreign-students-italian-citizens-abroad.json is also complete and untouched. Neither was read for values nor written. Slot 03 is a different assignment and this record does not substitute for it.',
    'NO SUBSTITUTION — the assigned target exists on the official site and is not on the do-not-duplicate list in RESEARCH_PROTOCOL.md. Canada is an allowed region and the award funds a bachelor\'s-level degree, so no alternative was substituted.',
    'KEY SCHEMA — the record follows the numbered-slot schema defined in research/bachelor/SCHEMA_CONTRACT.md and matches the shape of the sibling numbered records (for example 36-canada-toronto-pearson.json). This is not the six-key b-slot schema used by 03-italy-maeci-ire-scholarships.json and b01, which are a different generation of record.',
    'AUTHORITY — the award is published and administered by the University of Regina itself. No government, ministry or external funding body is involved, and no external programme guide or rulebook PDF exists.',
    'THRESHOLD CONVERSION — Tier 1 and Tier 2 thresholds are published as percentages "converted to Canadian grading scale". The raw national percentage an applicant holds is not necessarily the figure assessed. No equivalence table is published, so no per-country threshold is asserted here.',
    'DEADLINE PRECISION — the official page publishes recurring month-and-day deadlines by term, with no year. Per the SCHEMA_CONTRACT.md accuracy rule, deadline_date is null and deadline_precision is "programme_specific". The forthcoming April 30, 2027 deadline is derived from the published Fall Term deadline of April 30 combined with the notice directing applicants to the Fall 2027 intake, and is labelled as derived in deadline_warning.',
    'TIME ZONE — no time of day or time zone is published for these deadlines. The time zone note in application_deadline is taken from the university\'s general statement of "Central Standard Time (CST-SK)" on its pages, not from the award page.',
    'VALUES ARE APPROXIMATE — the CAD $90,000 and CAD $45,000 figures are published as "Approximate Value of Campus Housing and Meal Plan" and "Approximate Value of Campus Housing" respectively, expressed as $22,500 x 4 years and $11,250 x 4 years. They are treated here as published approximate values of in-kind benefits, not as guaranteed cash amounts.',
    'NO TOTAL COMPUTED — no combined package value is published, and the page does not state whether the entrance scholarship, the tiers and the bursary are additive. funding.total_estimated_value is therefore marked unavailable rather than computed, per the schema\'s instruction not to compute a total and present it as an award.',
    'SUPERSEDED VALUES — an older version of the scholarship page (uregina.ca/international/future-students/scholarship/index.html) described the distinction scholarship as $80,000 ($20,000 x 4 years) for 4 years, 4.5 years for engineering, for 50 international students per term, with renewal at 30 credit hours per calendar year and a UGPA of 80%. The official news story of 3 September 2024 describes the inaugural 2024 cohort award as "valued at $80,000". The current page supersedes both with the tiered structure, and the credit-hour renewal requirement has changed from 30 to 24 per calendar year. The superseded figures are not used in this record.',
    'CREDIT-HOUR CHANGE — the renewal condition moved from 30 credit hours per calendar year (older page and third-party descriptions) to 24 credit hours per calendar year on the current page, for both Tier 1 and Tier 2. The current figure is used. Engineering receives a renewal period of 3.5 years rather than 3 years.',
    'RENEWAL SHORTER THAN VALUE — the benefit value is published over 4 years but renewal is for up to 3 years (3.5 for Engineering) of the degree programme. This is recorded rather than reconciled, because the page does not explain the relationship between the 4-year value and the 3-year renewal period.',
    'SEPARATE INSTRUMENTS — the International Entrance Scholarship (CAD $5,000 tuition credit, first registered term, 83%+ average) and the International Undergraduate Student Bursary (up to CAD $20,000 tuition credit over 4 years) are separate instruments in the same entrance package, not components of the distinction scholarship. The distinction scholarship provides no tuition credit at all.',
    'BURSARY NOT THE SCHOLARSHIP — the bursary requires a two-year tuition pre-payment before the study permit application, completion of the first year of full-time study, registration in the following term and no outstanding tuition fees. The tuition credit is issued only after the add/drop date of the assessment term, so it is not available as upfront funding.',
    'STATUS — the award is ongoing and made each intake, but availability is capped per intake. The published notice that spots are filled for the Winter 2027 and Spring/Summer 2027 intakes drives the choice of status OPEN with status_label "Open — Fall 2027 intake", since the next intake with published availability is Fall 2027.',
    'ENGLISH REQUIREMENT — headlined minimum IELTS 6.5, TOEFL 83, PTE 59 and Duolingo 120 apply to most undergraduate programmes. The Faculty of Education and the Faculty of Nursing have higher or different requirements, recorded in english_requirement.test_score_note. The ELP page states requirements are "subject to change without notice".',
    'LOGO — the university publishes its full logo as an inline SVG in the page header rather than at a stable standalone file path, so no SVG logo URL could be cited. The verified official-domain brand icon at uregina.ca/apple-touch-icon-152x152.png is used instead. It is a light-on-white mark with solid dark-green ink, so it is not the prohibited white-on-transparent wordmark.',
    'NO AGE LIMIT — no minimum or maximum age is published for this award anywhere on the pages read, so age_limit is null rather than an invented figure. The university\'s English for Academic Purposes programme separately states an admission age of 16 or older, but that applies to EAP admission and not to this scholarship.',
    'GENDER — no gender restriction is published; gender_restriction is false.',
    'NO NATIONALITY QUOTA — no per-country or per-region quota is published. Nationality quota is null rather than an invented number.',
    'NO INTERVIEW, ESSAY OR PORTFOLIO — no interview, essay, portfolio or recommendation letter forms part of the award selection, which is automatic and average-based. The document_checklist recommendation and essay arrays are therefore empty rather than populated with speculative items.',
    'MULTIPLE APPLICATIONS — whether a student may submit more than one application, and how concurrent intake applications are treated, is not published, so application_method.multiple_applications_allowed is null.',
    'DOCUMENT LANGUAGE AND FORMAT — the official pages read do not state a required document language, format or certified-translation rule for scholarship consideration, so those fields are null rather than invented.',
    'NO FINANCIAL NEED OR EXTRACURRICULAR CRITERION — no financial need, leadership, community service or extracurricular criterion is published, so the corresponding selection_criteria fields are null or false as appropriate.',
    'SOURCE DATES — no publication or last-updated date is published on the award page. The only date signals are the site footer copyright of 2026, the statement that the increased entrance-scholarship value takes effect for students starting in the Fall 2026 term onward, and the intake notice naming Winter 2027 and Spring/Summer 2027.',
    'ACADEMIC CALENDAR NOT CONSULTED — the University of Regina Undergraduate Academic Calendar, which would govern admission and fee rules centrally, was not consulted for this record. The UR International scholarship page is the sole rule source for the award terms recorded here.'
  ],

  _source_domain: 'uregina.ca',
  _source_type: 'official_provider',
  _cycle: '2027 entry (next open intake: Fall 2027)',
  _verification_timestamp: '2026-10-10T15:40:00+00:00',
  _completeness_score: 0.93
};

module.exports = rec;
