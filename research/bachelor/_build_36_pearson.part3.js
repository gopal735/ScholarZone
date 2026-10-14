// PART 3: application_method, official_application_documents, document_checklist,
// required_documents, selection_process, selection_criteria, degree_outcome,
// student_rights_and_cost_protection, practical_application_data, risk_flags,
// application_status_workflow, best_fit, not_best_fit
module.exports = {
  application_method: {
    direct_student_application: false,
    central_application: true,
    application_route: "Two linked applications are required and neither can substitute for the other. First the applicant's current secondary school must nominate them through the university's secure online nomination process (one nominee per school per year; the school receives a personalised nomination form from July, or must first register to participate). Second, the student must submit an undergraduate application through the Ontario Universities' Application Centre (OUAC) to the University of Toronto, then complete the Join U of T (or Engineering Applicant Portal) steps. Only after both nomination and the admission application are in place is the student issued a private link to the Lester B. Pearson International Student Scholarship application, which is submitted together with all required documentation by the published deadline.",
    portal_url: "https://join.utoronto.ca/ (Join U of T applicant portal); Engineering applicants use https://portal.engineering.utoronto.ca/sites/myportal/ (Engineering Applicant Portal). School-side: https://apply.adm.utoronto.ca/register/pearson-participate (school participation registration). Questions: https://apply.adm.utoronto.ca/register/pearson-inquiry (Pearson Scholarship Inquiry Form).",
    application_steps: [
      "1. Confirm eligibility: be a non-Canadian requiring a study permit; be in the final year of senior secondary school in 2026/2027 or have graduated no earlier than June 2026; and be beginning studies at the University of Toronto in September 2027.",
      "2. Ask the guidance counsellor, principal or head of school whether the school is eligible to nominate students for the Lester B. Pearson International Student Scholarship. Schools already verified by University Admissions & Outreach and the University Registrar's Office are contacted by email each July with a personalised, secure nomination form; unverified schools must first apply to participate in the programme.",
      "3. School submits the nomination by the nomination deadline (October 9, 2026 for 2027 entry). Each school may nominate only one student per year, and the university encourages the school to nominate the student who best exemplifies the qualities of a Pearson Scholar.",
      "4. Student submits an OUAC undergraduate application to the University of Toronto, selecting up to three programme areas, by the Pearson admission deadline (October 16, 2026 for 2027 entry).",
      "5. About a week after the OUAC application is received, the student receives instructions to log into the Join U of T or Engineering Applicant Portal, where required documents, supplemental applications and next steps are listed.",
      "6. Student completes the Pearson scholarship application using the private link issued after nomination. This can only be done after the admission application has been submitted. The application and all required documentation must be submitted by the scholarship application deadline (November 6, 2026 for 2027 entry).",
      "7. University review and decision. Meeting the English language requirement is a condition of admission."
    ],
    application_fee: null,
    multiple_applications_allowed: true,
    paper_application_available: false
  },
  official_application_documents: {
    universal_documents: [
      "OUAC undergraduate application to the University of Toronto (all applications start with the Ontario Universities' Application Centre)",
      "Complete documentation (transcripts) for all secondary and post-secondary studies attempted",
      "Proof of English language proficiency, where the applicant is required to present it and does not qualify for an exemption",
      "Pearson scholarship application completed via the private link issued after nomination, with all required documentation"
    ],
    commonly_requested_documents: [
      "Self-reported grades form (where applicable)",
      "Standardized test results (for example SAT, ACT, IB, AP)",
      "Mid-term / in-term results where final results are not yet available",
      "Programme-specific supplemental applications and profiles where required",
      "Any further documents listed on the applicant portal for the applicant's academic background"
    ],
    two_recommendation_letters: null,
    secondary_school_documents: "Full documentation (transcripts) for all secondary studies attempted. Applicants currently studying in an Ontario high school do not upload transcripts: the school sends Grade 11 and 12 results through the OUAC, and unsolicited Ontario transcripts or report cards are not reviewed. Most students apply in their final year of high school, and conditional offers may be made on previous-year grades and in-term or mid-term results. For International Baccalaureate applicants, final results must be submitted electronically by the IBO. For GCE/ British-patterned applicants, final IGCSE/GCSE/O Level and AS/A Level results must be issued by the appropriate examination board.",
    document_language: "Documents in English or French are accepted. Documents in any other language require notarized translations.",
    document_format: "Electronic submission is preferred and required wherever available: transcripts and test scores should be sent directly by the school, examination authority or testing agency. Where electronic submission is not available, documents may be uploaded manually on the Join U of T applicant portal or the Engineering Applicant Portal. Uploaded (unofficial) documents may support a provisional admission decision, but official transcripts sent directly by the issuing institution are required at any point and are always required to finalize an offer.",
    transcript_requirement: "Transcripts are required for all secondary and post-secondary studies attempted. Submit what is available by the deadline, including mid-term and interim results if final results are pending, and check the applicant portal regularly. Any documents submitted become the property of the University of Toronto and are not returned or forwarded.",
    certified_translation_requirement: true
  },
  document_checklist: {
    identity_documents: [
      {
        item: "Government-issued photo identification",
        required: "conditional",
        note: "The university reserves the right to require recent, government-issued photo identification for verification purposes, and to share English facility test results with other test providers that have submitted results. Not published as a standing Pearson checklist item."
      }
    ],
    academic_documents: [
      {
        item: "Transcripts for all senior secondary studies attempted",
        required: true,
        note: "Required. Electronic submission by the school is preferred; upload to the applicant portal where electronic submission is not available."
      },
      {
        item: "Transcripts for any post-secondary studies attempted",
        required: true,
        note: "Required for all post-secondary studies attempted. Note that students already attending post-secondary studies are ineligible for the Pearson Scholarship, though documentation of any attempted studies is still required for the admission application."
      },
      {
        item: "Self-reported grades form",
        required: "conditional",
        note: "Requested where applicable, depending on academic background, through the applicant portal."
      },
      {
        item: "Standardized test results (SAT, ACT, IB, AP)",
        required: "conditional",
        note: "Submitted where the applicant has written such tests. For U.S.-patterned education, SAT, ACT and AP scores should be sent electronically (SAT and AP institution code 0982; ACT institution code 5366). Applicants to Engineering are required to fully disclose all test scores."
      },
      {
        item: "Final IB results sent electronically by the IBO",
        required: "conditional",
        note: "Required for International Baccalaureate applicants."
      },
      {
        item: "Final GCE / IGCSE / A Level results issued by the examination board",
        required: "conditional",
        note: "Required for British-patterned applicants; predicted results should be sent by the school."
      }
    ],
    language_documents: [
      {
        item: "English proficiency test result (IELTS, TOEFL iBT, PTE Academic, Duolingo English Test, CAEL, Cambridge C1/C2, ELDA/COPE or another accepted qualification)",
        required: "conditional",
        note: "Required only if the applicant is not exempt. Exemptions apply after four or more years of full-time study in a recognized Canadian school, or four or more years in an English-language school in a country where English is dominant. Scores must be sent electronically by the testing agency."
      },
      {
        item: "Senior / Grade 12 English course result",
        required: true,
        note: "Required for all applicants, including those exempt from the proficiency test. Equivalent to Ontario ENG4U/EAE4U; counted in the admission average. Does not by itself satisfy the proficiency requirement."
      }
    ],
    recommendation_documents: [],
    application_essays: [
      {
        item: "Pearson scholarship application content (submitted via the private nomination link)",
        required: true,
        note: "The official award page does not enumerate the component documents of the Pearson scholarship application; it states only that the applicant must 'complete the Pearson International Scholarship application and submit all required documentation' by November 6, 2026. The exact list appears once the applicant receives the private link. Generative AI tools are prohibited for creating content for any University of Toronto undergraduate award application."
      }
    ],
    financial_documents: [],
    additional_documents: [
      {
        item: "School nomination submitted by the applicant's secondary school",
        required: true,
        note: "The gating requirement. Without a school nomination the applicant cannot receive the private scholarship application link. Each school may nominate only one student per year."
      },
      {
        item: "Programme supplemental applications",
        required: "conditional",
        note: "Some programme areas require a supplemental application or profile (for example the Online Student Profile for Applied Science & Engineering, the Rotman Commerce and Computer Science supplementary applications for Arts & Science, the One Idea Supplementary Application for Architecture, Landscape and Design, a Statement of Interest for Kinesiology & Physical Education, the Music Questionnaire, and the U of T Scarborough Supplementary Application Form)."
      },
      {
        item: "Notarized translations of any documents not in English or French",
        required: "conditional",
        note: "Required for documents in a language other than English or French."
      }
    ]
  },
  required_documents: [
    "OUAC undergraduate application to the University of Toronto, with up to three programme areas selected",
    "School nomination submitted by the applicant's current secondary school through the university's secure online nomination process",
    "Pearson scholarship application completed via the private link issued after nomination",
    "Full documentation (transcripts) for all secondary and post-secondary studies attempted",
    "Senior / Grade 12 English course result",
    "Proof of English language proficiency, where required and not exempt, sent electronically by the testing agency",
    "Self-reported grades form, where applicable",
    "Standardized test results (SAT, ACT, IB, AP), where written",
    "Programme supplemental applications or profiles, where required by the chosen programme areas",
    "Notarized translations of any documents not in English or French",
    "All documentation required by the Pearson scholarship application, as listed on the private applicant link (exact list not published publicly)"
  ],
  selection_process: {
    decision_maker: "University of Toronto. Enrollment Services manages Pearson Scholarship applications and receives questions at pearson.scholarship@utoronto.ca; University Admissions & Outreach and the University Registrar's Office verify participating high schools; the Pearson Program Office within the Centre for International Experience supports enrolled scholars.",
    selection_type: "Competitive, school-nominated, holistic merit review with no published weighting or rubric",
    central_selection: true,
    possible_stages: [
      "High school verification by University Admissions & Outreach and the University Registrar's Office",
      "School nomination of one student per year, with the school choosing its top candidate",
      "OUAC admission application to the University of Toronto",
      "Receipt of the private Pearson scholarship application link (only after nomination and after the admission application is submitted)",
      "Submission of the Pearson scholarship application and all required documentation",
      "Holistic review of academic achievement, creativity, leadership and community impact",
      "Award decision and notification to recipients, then to all nominees"
    ],
    official_universal_weighting: null,
    weighting_note: "No universal weighting, points system or scoring rubric is published. The university describes the qualities recognised (exceptional academic achievement, creativity, leadership potential, impact on school and community, and future potential to contribute positively to the global community) but does not publish how they are weighted, and publishes no interview or additional testing stage.",
    interview_possible: null,
    results_timing: "The official award page states: 'Pearson Scholarship recipients will be notified starting at the end of January 2026. All nominees will be notified of our decisions by April 2026.' Note that this FAQ text references the prior (2026-entry) cycle while the page body publishes 2027-entry deadlines; for the 2027-entry cycle the corresponding window would be expected to run from the end of January 2027 to April 2027, but the official page as read still shows the 2026 dates. Separately, admission decisions for the 2027 intake are released beginning in January and continue through to late May, and may also be released in the summer depending on programme and applicant type.",
    scholarship_rank_note: "The university describes the award as its 'most prestigious' and 'most competitive' award for international students and as 'one of the largest scholarship programs for international students in Canada'. Approximately 37 students are named Pearson Scholars each year. For scale, a University of Toronto Mississauga news article on an earlier cohort reported that recipients were chosen from a total of 1,761 applicants."
  },
  selection_criteria: {
    academic_excellence: true,
    leadership: true,
    community_service: true,
    extracurricular_achievement: true,
    financial_need: false,
    additional_factors: "Creativity; the impact the student has had on the life of their school and community; and future potential to contribute positively to the global community. Applicants must also have been selected by their school as its single nominee for the year.",
    interview_required: false,
    portfolio_required: false,
    source: "https://future.utoronto.ca/pearson-scholarships (award page and 'Pearson Scholars demonstrate exceptional academic achievement, creativity, and potential to contribute positively to the global community'); https://www.utsc.utoronto.ca/artscicoop/lester-b-pearson-international-scholarship ('A special emphasis is placed on the impact the student has had on the life of their school and community, and their future potential to contribute positively to the global community.'); https://www.utoronto.ca/news/learn-more-about-ourselves-and-each-other-u-t-welcomes-its-newest-pearson-scholars (October 2, 2026: 'the scholarship recognizes students who demonstrate exceptional academic achievement, creativity and leadership – and a commitment to making an impact in their communities')"
  },
  degree_outcome: {
    awarded_qualification: "Any first-entry undergraduate degree at the University of Toronto, restricted to the applicant's top choice of programme at the time scholarship decisions are made",
    typical_programme_length: "Four years of scholarship support. University of Toronto undergraduate degrees are typically four years; some programmes, including engineering, co-op and certain professional programmes, take longer, and the official page states four years of coverage rather than coverage to degree completion.",
    possible_awards: [
      "First-entry undergraduate degree at University of Toronto St. George (downtown Toronto)",
      "First-entry undergraduate degree at University of Toronto Mississauga",
      "First-entry undergraduate degree at University of Toronto Scarborough"
    ],
    degree_note: "The scholarship is tenable only at the University of Toronto for first-entry, undergraduate programmes and is available only to undergraduate degree applicants. Applicants may apply to up to three programme areas, but if awarded the scholarship is restricted to the top choice of programme at the time decisions are made. Pearson Scholars study across the university's three campuses. In addition to the award, scholars receive enrichment and mentorship programming from the Pearson Program Office.",
    credit_transfer: "The University of Toronto may award transfer credit for A Level and International A Level subjects, International Baccalaureate Higher Level subjects, Advanced Placement examinations, French Baccalauréat subjects, CAPE subjects and other recognised qualifications; applicants should consult the university's Transfer Credit Information. Final IB results must be submitted electronically by the IBO."
  },
  student_rights_and_cost_protection: {
    tuition_fee_for_recipients: "Tuition is covered by the scholarship for four years. International tuition fee schedules are published by the university's Student Accounts office; the award page itself publishes no rate.",
    application_fee_for_recipients: null,
    student_agreement: null,
    programme_website: "https://future.utoronto.ca/pearson-scholarships",
    common_services: "Pearson Scholars receive, through the Pearson Program Office within the Centre for International Experience: Pearson Welcome Events each September (a Pearson Orientation, a team-building activity and a Pearson Welcome Reception attended by senior leadership); one-on-one check-in meetings each semester with an advisor assigned on the scholar's campus of study for their four years at the university; the Pearson Peer Mentorship Program pairing Year 1 scholars with upper-year Pearson Scholars; the Pearson Faculty Mentorship Program matching second-year scholars with a University of Toronto Faculty Mentor; enrichment activities on themes such as leadership, career exploration, alumni networking, graduate school applications and entrepreneurship; a Pearson Social Committee of 8-10 scholars planning monthly social events; and the voluntary Pearson Scholars Professional Development Plan. All university students also have access through their incidental fees to libraries and study spaces, health and wellness services, athletics and recreation facilities, academic advising, career services, accessibility support and student-run clubs.",
    bond_requirement: "None. No service bond, return-home obligation, minimum grade or continuation condition is published for this award.",
    bond_breach_consequence: "None published. The official award page states no bond or breach consequence. Separately, the university publishes an academic integrity rule specific to award applications: the use of generative artificial intelligence tools such as ChatGPT is prohibited when creating content for any University of Toronto undergraduate award application, and nominees or applicants found to have used generative AI to create content will be disqualified from award eligibility."
  },
  practical_application_data: {
    application_readiness_checklist: [
      "Confirm the school is willing and able to nominate, and that it is a verified Pearson participant (if not, the counsellor must apply to participate well before the deadline).",
      "Diarise all three deadlines separately: school nomination, OUAC admission for Pearson consideration, and the Pearson scholarship application with documentation.",
      "Ensure the senior-secondary curriculum satisfies the University of Toronto's minimum admission requirements for the intended programme areas, including the senior/Grade 12 English course.",
      "Confirm English proficiency and book a test early if required, so the score can reach the university by the supporting-documentation deadline; check exemption eligibility first.",
      "Order transcripts and any mid-term or in-term results from the school early, plus notarized translations if documents are not in English or French.",
      "Prepare the admission application and rank programme choices deliberately, since an award would be restricted to the top choice.",
      "Plan for supplemental applications for the chosen programme areas and their own deadlines.",
      "Write all scholarship application content personally; generative AI use is prohibited and disqualifying.",
      "Budget independently of the scholarship for items not published as covered, including books and supplies (the university suggests $1,000–$2,000 per year), health insurance (UHIP) and personal living costs."
    ],
    programme_comparison_fields: [
      "Benefit components covered: tuition, books, incidental fees, full residence support (four years)",
      "Award duration: four years, no published renewal application",
      "Number of awards: approximately 37 per year",
      "Application gate: mandatory school nomination, one nominee per school per year",
      "Application route: OUAC admission application plus a separate private scholarship application",
      "Eligibility: non-Canadian requiring a study permit, final year of senior secondary school or graduated no earlier than June of the preceding year, September entry",
      "Field restriction: unrestricted, but tied to the top-ranked programme choice",
      "Country eligibility: worldwide, with 188 countries represented among scholars",
      "Host institution: University of Toronto only, across three campuses"
    ],
    motivation_letter_strategy: "The scholarship application content should be written by the applicant and grounded in their own verifiable record, since the university prohibits the use of generative AI in any undergraduate award application and disqualifies applicants found to have used it. The official criteria signal what to evidence: exceptional academic achievement, creativity, leadership within the school, concrete impact on the life of the school and community, and future potential to contribute positively to the global community. Because each school may nominate only one student, the case must also be the school's single strongest; applicants should give their counsellor evidence early enough to be selected. Because the award would be restricted to the top-ranked programme choice, the statement should connect the applicant's record and ambitions to that first-choice programme specifically, and should demonstrate that the applicant is entering first-entry undergraduate study directly from senior secondary school.",
    profile_fit_labels: [
      "Top of cohort with a rigorous course load in their own curriculum",
      "Recognised leader within their school",
      "Demonstrated, documented impact on their school or community",
      "Strong service, entrepreneurship, research, competition or artistic record",
      "Able to be nominated by a school that is a verified Pearson participant",
      "Applying directly from senior secondary school, not from another post-secondary institution",
      "Seeking full financial support to study in Canada, with no other route to fund an international undergraduate degree"
    ],
    common_mistakes: [
      "Assuming the general University of Toronto admissions deadline of January 15, 2027 applies — Pearson requires the OUAC application by October 16, 2026.",
      "Waiting for the school to act: nomination closes October 9, 2026, before the admission deadline, and a school that has not participated must register first.",
      "Applying to the scholarship before submitting the admission application — the private link can only be used after the admission application is submitted.",
      "Assuming the scholarship is open to any programme area applied for: if awarded, it is restricted to the top choice of programme at the time decisions are made.",
      "Assuming a prior degree or existing post-secondary study is acceptable — students already attending post-secondary studies are ineligible.",
      "Assuming a January intake is acceptable — students must begin studies in September.",
      "Submitting an English test score that the university cannot accept (for example IELTS Indicator, IELTS One Skill Retake, TOEFL Essentials, TOEFL ITP, or TOEFL MyBest), or submitting scores through the applicant rather than the testing agency.",
      "Assuming the senior/Grade 12 English course satisfies the English proficiency requirement — it does not.",
      "Using generative AI to draft application content, which results in disqualification from award eligibility.",
      "Paying an agent or intermediary: the university states it does not work with recruitment agents or agencies, and fraudulent emails offering application assistance have been reported.",
      "Budgeting as though personal living costs, travel, installation and health insurance are covered — none of these is published as part of the award."
    ]
  },
  risk_flags: [
    {
      risk: "Mandatory school nomination gate. Applicants cannot apply directly; only a verified participating secondary school can nominate them, and each school may nominate only one student per year.",
      impact: "An applicant at a school that is not registered, or that has already used its single nomination on another student, cannot be considered at all regardless of their record.",
      mitigation: "Confirm with the counsellor in early July whether the school is a verified participant and whether the nomination is still available. If the school has not participated, have the counsellor apply to participate as early as possible and well before the noon (EST) October 9, 2026 deadline."
    },
    {
      risk: "Three separate deadlines, all far earlier than the university's general admissions deadline. For 2027 entry these are October 9 (nomination), October 16 (OUAC admission for Pearson consideration) and November 6, 2026 (scholarship application and documentation), against a general deadline of January 15, 2027.",
      impact: "Applicants who assume the general deadline, or who learn of the award late, miss the cycle entirely.",
      mitigation: "Treat the Pearson deadlines as the only relevant ones and diarise all three. Aim to have the admission application submitted before the nomination deadline so the scholarship link can be used immediately."
    },
    {
      risk: "Fraudulent agents and fraudulent scholarship emails. The University of Toronto has been alerted to fraudulent emails offering assistance with Pearson applications, and states it does not interact with agencies or educational agents to recruit students or offer scholarships.",
      impact: "Financial loss, submission of false acceptances, and fees paid to unaffiliated third parties.",
      mitigation: "Apply only through the OUAC and the private nomination link issued by the university. Be cautious of any agent providing false acceptances or requiring fees; the university states recipients can only be nominated by their current secondary school through its online process and that the scholarship is available only to undergraduate degree applicants."
    },
    {
      risk: "Generative AI prohibition in award applications. The university prohibits the use of generative AI tools such as ChatGPT when creating content for any University of Toronto undergraduate award application.",
      impact: "Automatic disqualification from award eligibility.",
      mitigation: "Write all scholarship application content personally and do not use generative AI tools to draft, edit or translate it."
    },
    {
      risk: "Programme restriction on award. Applicants may apply to up to three programme areas, but if awarded, the scholarship is restricted to the top choice of programme at the time decisions are made.",
      impact: "A recipient cannot redirect the scholarship to a second or third choice programme later.",
      mitigation: "Rank programme choices deliberately and verify admission and prerequisite requirements for the first choice before submitting."
    },
    {
      risk: "Benefit scope is not fully specified. The official page names tuition, books, incidental fees and full residence support but publishes no monetary value, no definition of full residence support, and no statement on meal plans, health insurance, travel, installation or personal living costs.",
      impact: "Budgeting errors and unexpected out-of-pocket costs, even for a fully covered award.",
      mitigation: "Budget independently for items not published as covered. The university suggests $1,000–$2,000 per year for books and school supplies, requires international students to enrol in the University Health Insurance Plan (UHIP) at separate cost, and publishes tuition schedules and residence fees separately."
    },
    {
      risk: "The official award page mixes current-cycle and prior-cycle content. The body publishes 2027-entry deadlines, while parts of the counsellor FAQ still reference 2026-entry dates (for example 'end of January 2026', 'April 2026', 'July 1, 2025' and 'October 10, 2025').",
      impact: "Dates read out of context can be wrong by a full cycle.",
      mitigation: "Use the 'Important dates and deadlines' block and the numbered steps for the current cycle, and re-verify dates on the live page before relying on them."
    },
    {
      risk: "Extreme selectivity with only approximately 37 awards per year, on top of the school nomination constraint.",
      impact: "Very low probability of success even for strong, nominated applicants.",
      mitigation: "Treat the award as a reach option and pursue other funding in parallel. Note that the university cannot offer financial aid to international students, and that most other University of Toronto international admission awards are automatic on admission."
    }
  ],
  application_status_workflow: [
    "Not yet nominated",
    "School registered and verified as a Pearson participant",
    "School nomination submitted (one nominee per school per year)",
    "OUAC admission application submitted to the University of Toronto",
    "Pearson scholarship application link received (private, issued after nomination and admission application)",
    "Pearson scholarship application and all required documentation submitted",
    "Application under university review",
    "Award decision issued to recipients",
    "All nominees notified of decisions",
    "Enrolled at the University of Toronto as a Pearson Scholar"
  ],
  best_fit: "An exceptional international student in the final year of senior secondary school (or who graduated no earlier than June of the preceding year) who requires a study permit, has been selected by their school as its single nominee, can meet the October and November deadlines ahead of the university's general January deadline, has a documented record of academic achievement, creativity, leadership within their school and impact on their school and community, and needs full four-year support including residence to study for a first-entry undergraduate degree at the University of Toronto.",
  not_best_fit: [
    "Canadian citizens, permanent residents or protected persons who do not require a study permit",
    "Students already attending any post-secondary institution, or beginning post-secondary studies in January",
    "Students seeking a January or mid-year intake rather than a September start",
    "Applicants who cannot secure a school nomination, or whose school has already nominated another student",
    "Graduate, master's, doctoral, professional-certificate, non-degree or exchange applicants",
    "Applicants who can only be considered for another university, or who need the award to be transferable or deferred",
    "Applicants expecting a cash living allowance, travel or installation support, or insurance to be provided: none of these is published for this award",
    "Applicants relying on an agent or intermediary to apply"
  ]
};
