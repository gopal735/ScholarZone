// Part 3: eligibility detail, academic/English/language, application method and documents for slot 49.
const AWARD_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students/science-technology-undergraduate-scholarship';
const DATES_URL = 'https://nus.edu.sg/oam/scholarships/important-dates-and-application';
const ADM_DATES_URL = 'https://nus.edu.sg/oam/admissions/important-dates';

function extend(record) {
  // ---- eligibility detail ----
  record.eligibility = {
    citizenship:
      'Citizens of an Asian country or region, excluding Singapore. NUS also labels the award\'s nationality band as "Singapore Permanent Residents / International Students" and publishes the award under both the Singapore Permanent Residents and the International Students sections, while the eligibility criterion is written as a citizenship test. Applicants who are Singapore citizens, or who are citizens of a country or region outside Asia, are not eligible.',
    residence_requirement:
      'None published. NUS states no residence or domicile requirement for this scholarship; the gate is the citizenship test above.',
    age_limit: 'No age limit is published.',
    secondary_school_requirement:
      'Yes. The qualification requirement is "High school qualifications eligible for admission to NUS", and an eligibility criterion is to possess outstanding high school results.',
    academic_requirements:
      'Possess outstanding high school results. NUS publishes no percentage, grade-point average or rank cut-off for high-school performance.',
    gpa_requirement:
      'No high-school GPA threshold is published for admission to the award. The published GPA threshold applies after enrolment: the scholarship is renewed every semester provided the scholar maintains a Grade Point Average (GPA) of at least 3.50 (or equivalent) and has good conduct.',
    language_requirement:
      'None published on the scholarship page. English proficiency is handled through the separate NUS undergraduate admissions process; no language test, score or certificate is named for this scholarship.',
    work_experience: 'Not required and not published as a criterion.',
    extracurricular_requirement: 'Yes - "Have excellent co-curricular activities record".',
    leadership_requirement: 'Yes - "Have strong leadership qualities and potential".',
    financial_need:
      'No. The award is not means-tested; NUS publishes no income, asset or family-circumstance test for it.',
    previous_scholarship_restriction:
      'Besides the MOE Tuition Grant, scholarship recipients may not concurrently hold any other scholarship, fellowship, bursary, grant, award or allowance.',
    enrolment_status_requirement:
      'Freshmen only. Applicants must be applying for admission to a full-time undergraduate degree programme at NUS, and transfer applicants from local or overseas universities are not eligible.',
    health_requirement: 'None published.',
    field_restrictions:
      'The award is restricted to the full-time undergraduate programmes named in the Terms and Conditions. School of Computing: Artificial Intelligence, Business Analytics, Business Artificial Intelligence Systems, Computer Science, Information Security. College of Design and Engineering: engineering majors only - Biomedical Engineering, Chemical Engineering, Civil Engineering, Computer Engineering, Electrical Engineering, Engineering Science, Environmental and Sustainability Engineering, Industrial & Systems Engineering, Materials Science & Engineering, Mechanical Engineering, and Robotics & Machine Intelligence. School of Computing and College of Design and Engineering: Computer Engineering. College of Humanities and Sciences: science majors only, excluding Environmental Studies and Pharmacy - Chemistry, Data Science and Analytics, Data Science and Economics, Food Science and Technology, Geospatial Intelligence, Life Sciences, Mathematics, Pharmaceutical Science, Physics, Quantitative Finance, and Statistics. The field restriction is stated twice: applicants must be applying for admission to a programme in Computing, Engineering (excluding Infrastructure and Project Management) or Science (excluding Environmental Studies and Pharmacy) at NUS, and must be entering one of the programmes listed above. Students in local Double Degree Programmes are covered only if the home programme falls within the listed programmes.',
    official_source: AWARD_URL,
  };

  // ---- academic requirements ----
  record.academic_requirements = {
    fixed_percentage_requirement: null,
    percentage_note:
      'No high-school percentage or equivalent numerical threshold is published. NUS states the criterion qualitatively as "Possess outstanding high school results", so no universal percentage field can be filled.',
    programme_specific_requirements:
      'The applicant must be entering one of the specific full-time undergraduate programmes listed in the Terms and Conditions (School of Computing; College of Design and Engineering engineering majors only; College of Humanities and Sciences science majors only, excluding Environmental Studies and Pharmacy; and Computer Engineering under School of Computing and College of Design and Engineering). Engineering excludes Infrastructure and Project Management and Science excludes Environmental Studies and Pharmacy.',
    selection_factors_may_include: [
      'Outstanding high school results',
      'Excellent co-curricular activities record',
      'Strong leadership qualities and potential',
      'Strength of the application for undergraduate admission to NUS overall',
      'Performance at the selection interview(s)',
      'Entry into one of the eligible Computing, Engineering or Science programmes',
    ],
    holistic_selection_note:
      'NUS states that "Invited applicants will be assessed for scholarship suitability based on the strength of their application" and publishes no numerical weighting among high school results, co-curricular record, leadership and interview performance. NUS reserves the right not to award any scholarship if there are no candidates of sufficient merit, and the decision of the selection committee is final with enquiries or disputes not entertained.',
  };

  // ---- English requirement ----
  record.english_requirement = {
    universal_requirement: false,
    minimum_ielts: null,
    minimum_toefl: null,
    minimum_pte: null,
    minimum_duolingo: null,
    moi_rule:
      'No medium-of-instruction rule is published for this scholarship. English requirements are a condition of admission to NUS, administered through the NUS undergraduate admissions process, and are not stated on the scholarship page.',
    moi_accepted: null,
    test_score_note:
      'The NUS Science & Technology Undergraduate Scholarship page publishes no English language test, score or certificate requirement, so every score field here is null.',
    test_validity_months: null,
    accepted_tests: [],
  };

  // ---- language of instruction ----
  record.language_of_instruction = {
    programme_specific: true,
    possible_languages: [],
    bilingual_programmes: false,
    language_note:
      'The language of instruction is set by each NUS degree programme, not by this award, and the scholarship page publishes no information about it. The scholarship page itself is published in English only. Applicants should confirm the language of instruction on the individual NUS programme page.',
  };

  // ---- application method ----
  record.application_method = {
    direct_student_application: false,
    central_application: false,
    application_route:
      'No separate scholarship application. Consideration is automatic through the NUS undergraduate admission application submitted via the NUS Applicant Portal; only applicants shortlisted for the selection interview(s) are informed via e-mail.',
    portal_url: 'https://myaces.nus.edu.sg/applicantPortal/app/login',
    application_steps: [
      'Confirm you are a citizen of an Asian country or region other than Singapore, since the award is closed to Singapore citizens and to citizens of countries outside Asia.',
      'Choose a full-time first-degree programme that appears on the official eligible-programme list, checking that it is not Infrastructure and Project Management (Engineering) or Environmental Studies or Pharmacy (Science).',
      'Hold, or be completing, a high school qualification eligible for admission to NUS and assemble results that show outstanding high school performance.',
      'Build and document an excellent co-curricular activities record and leadership roles, because both are explicit eligibility criteria and the application is assessed on its overall strength.',
      'Submit a single application for undergraduate admission to NUS through the NUS Applicant Portal within the admissions application period for your qualification; there is no scholarship form, scholarship portal submission or scholarship deadline.',
      'Wait for NUS to make contact: only applicants shortlisted for the selection interview(s) are informed via e-mail.',
      'Attend the selection interview(s), which are conducted from January to July, if shortlisted.',
      'On award, take up the MOE Tuition Grant and complete the MOE Tuition Grant application and signing, and accept the scholarship terms including the six-year bond with a Singapore-registered company immediately after graduation.',
      'Maintain a GPA of at least 3.50 (or equivalent) and good conduct each semester, and keep at least 75% of the credits/units required for graduation earned in Singapore.',
    ],
    application_fee:
      'No scholarship application fee is published, because there is no separate scholarship application. Any NUS undergraduate admission application fee is set by the NUS admissions process and is not published on the scholarship page.',
    multiple_applications_allowed: false,
    paper_application_available: false,
  };

  // ---- official application documents ----
  record.official_application_documents = {
    universal_documents: [],
    commonly_requested_documents: [],
    two_recommendation_letters: false,
    secondary_school_documents: [],
    document_language:
      'Not published on the scholarship page. The award requires no documents of its own; the document language and format are those of the NUS undergraduate admission application.',
    document_format:
      'Not published on the scholarship page. The only submission is the NUS undergraduate admission application; NUS publishes no scholarship-specific form, upload or format for this award.',
    transcript_requirement:
      'Not published as a scholarship requirement. NUS states only that applicants hold "High school qualifications eligible for admission to NUS"; the transcript and result documents required are those of the NUS undergraduate admission application.',
    certified_translation_requirement:
      'Not published on the scholarship page. Translation requirements, where they apply, are set by the NUS undergraduate admissions process.',
  };

  // ---- document checklist ----
  record.document_checklist = {
    identity_documents: [],
    academic_documents: [
      {
        document:
          'High school qualification eligible for admission to NUS (the only academic credential the scholarship pages name)',
        required: true,
        notes:
          'Stated on the Important Dates and Application page as the qualification requirement for the Science & Technology Undergraduate Scholarship. The document set itself is whatever the NUS undergraduate admission application requires; the scholarship page publishes no separate document list.',
        source: DATES_URL,
      },
    ],
    language_documents: [],
    recommendation_documents: [],
    application_essays: [],
    financial_documents: [],
    additional_documents: [
      {
        document: 'No additional scholarship document is published',
        required: false,
        notes:
          'Because there is no separate scholarship application, NUS publishes no scholarship form, essay, referee report, portfolio or financial document for this award. Shortlisted candidates are contacted by e-mail for the selection interview.',
        source: AWARD_URL,
      },
    ],
  };

  record.required_documents = [
    'A submitted NUS undergraduate admission application (the only application route; there is no separate scholarship form or deadline)',
    'A high school qualification eligible for admission to NUS, stated by NUS as the qualification requirement for this scholarship',
    'Documented evidence of co-curricular activities and leadership, to make the strength of the application visible, since NUS assesses scholarship suitability on the strength of the application',
  ];
}

module.exports = { extend };
