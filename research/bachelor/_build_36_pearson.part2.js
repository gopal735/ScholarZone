// PART 2: funding, funding_breakdown, coverage, eligibility block, academic_requirements,
// english_requirement, language_of_instruction
module.exports = {
  funding: {
    scholarship_available: true,
    scholarship_type: "Full four-year merit-based entrance scholarship for international undergraduate students, awarded on school nomination",
    scholarship_currency: "CAD",
    monthly_amount: null,
    monthly_amount_note: "No monthly stipend or living allowance is published. The award covers tuition, books, incidental fees and full residence support for four years. The University of Toronto's 2023-24 Annual Report on Student Financial Support gives an annual value of approximately $85,000 per scholar per year, 'depending on the student's program of study'; this is a university-published total-coverage figure, not a monthly stipend. The award page itself publishes no dollar value.",
    travel_support: false,
    visa_support: false,
    installation_support: false,
    living_allowance: null,
    insurance: false,
    travel_amount: null,
    travel_amount_note: "No travel, airfare or relocation allowance is published for this award.",
    institutional_costs: true,
    fully_funded: true,
    fully_funded_note: "The official award page describes the scholarships as covering 'tuition, books, incidental fees, and full residence support for four years', and the International Students Scholarships page describes them as 'full 4-year scholarships'. The official page does not publish a monetary value, a delivery mechanism for residence support, or any cash living allowance, travel allowance, installation allowance or insurance allowance. No service bond or return-home requirement is published, so the award is not conditional on future service.",
    // Additional official context, kept in the open map:
    program_level_funding_figure: "The official award page states '$12M+ funding in 2024' and '37 scholars annually' as programme-level figures. The University of Toronto's 2023-24 Annual Report on Student Financial Support states the university's funding commitment in 2023-24 was about $12.5M, of which $2.8M was from endowment income and divisional contributions and the remainder from operating funds, and that 'Across all year levels, 150 Pearson Scholars each receive an annual scholarship valued at approximately $85,000, depending on the student's program of study.' These are programme figures, not per-award amounts computed by this database."
  },
  funding_breakdown: {
    tuition: {
      covered: true,
      amount: null,
      currency: "CAD",
      conditions: "Tuition is covered for four years. Tenable only at the University of Toronto for first-entry, undergraduate programmes. No monetary value is published on the award page; the amount depends on programme, campus and year of study."
    },
    book_allowance: {
      covered: true,
      amount: null,
      currency: "CAD",
      conditions: "'Books' are listed as a covered component for four years. The award page does not state whether books are reimbursed, provided as an allowance, or paid directly, nor does it publish a cap."
    },
    incidental_fees: {
      covered: true,
      amount: null,
      currency: "CAD",
      conditions: "'Incidental fees' are listed as a covered component for four years. University of Toronto describes incidental fees as non-academic fees contributing to student societies, campus-based services, athletics and recreation facilities and student health and dental plans."
    },
    accommodation_support: {
      covered: true,
      amount: null,
      currency: "CAD",
      conditions: "'Full residence support' is listed as a covered component for four years. The award page does not define what full residence support includes, how it is delivered, or whether it covers a meal plan."
    },
    monthly_stipend: {
      available: false,
      note: "Not published in official source"
    },
    travel_allowance: {
      available: false,
      note: "Not published in official source"
    },
    installation_allowance: {
      available: false,
      note: "Not published in official source"
    },
    visa_support: {
      available: false,
      note: "Not published in official source. Eligibility requires the applicant to be a non-Canadian requiring a study permit; a study permit is a condition of entry to Canada but is not an award component. The university's Centre for International Experience provides immigration advising to international students generally."
    },
    insurance: {
      available: false,
      note: "Not published in official source. International students must enrol in the University Health Insurance Plan (UHIP), which the university describes as a cost separate from tuition and other fees; the award page does not state whether UHIP is covered."
    },
    research_allowance: {
      available: false,
      note: "Not published in official source"
    },
    equipment_allowance: {
      available: false,
      note: "Not published in official source"
    },
    family_allowance: {
      available: false,
      note: "Not published in official source"
    },
    bond: {
      available: false,
      note: "No service bond, return-home requirement, minimum grade or continuation condition is published on the official award page. The award therefore carries no obligation that would prevent it being described as unconditionally funded within the four components listed."
    },
    total_estimated_value: {
      available: true,
      amount: 85000,
      currency: "CAD",
      basis: "annual, per scholar",
      conditions: "University-published figure, not a database computation. The University of Toronto's 2023-24 Annual Report on Student Financial Support states: 'Across all year levels, 150 Pearson Scholars each receive an annual scholarship valued at approximately $85,000, depending on the student's program of study.' The award page itself publishes no monetary value, and no total four-year value is published by any official source read."
    }
  },
  coverage: [
    "Tuition for four years",
    "Books for four years",
    "Incidental fees for four years",
    "Full residence support for four years",
    "Tenable only at the University of Toronto, for first-entry undergraduate programmes",
    "Enrichment and mentorship programming through the Pearson Program Office (non-monetary)"
  ],
  coverage_limitations: [
    "The official award page lists the covered components but publishes no monetary value for the award and no definition of what 'full residence support' includes or how it is delivered.",
    "Exact benefit structure may differ by programme, campus and residence assignment; the annual value published by the university depends on the student's programme of study.",
    "No cash living allowance, travel allowance, installation allowance or insurance allowance is published, and the award page does not state whether the University Health Insurance Plan (UHIP) is covered.",
    "The scholarship is tenable only at the University of Toronto and only for first-entry undergraduate programmes; it is not transferable and cannot be deferred to another institution or a later intake.",
    "If awarded, the scholarship is restricted to the applicant's top choice of programme at the time scholarship decisions are made, even though up to three programme areas may be applied for.",
    "Support is stated for four years; the official page does not state that it continues to degree completion for programmes requiring more than four years.",
    "International applicants cannot receive need-based financial aid from the university: the University of Toronto states it is a publicly funded institution and cannot offer financial aid to international students."
  ],
  eligible_applicants: [
    "International students, defined by the university as non-Canadians requiring a study permit",
    "Students enrolled in the final year of senior secondary school in 2026/2027",
    "Students who graduated from senior secondary school no earlier than June 2026",
    "Students beginning undergraduate studies at the University of Toronto in September 2027",
    "International students studying at Canadian high schools",
    "Students nominated by their current secondary school (one nominee per school per year)"
  ],
  citizenship_restriction: true,
  worldwide_eligibility: true,
  bachelor_requirement: true,
  final_year_bachelor_allowed: true,
  final_year_condition: "For this bachelor's award the relevant condition is secondary school completion, not completion of a bachelor's degree. Applicants must be enrolled in the final year of senior secondary school in 2026/2027, or have graduated from senior secondary school no earlier than June 2026. Students already attending post-secondary studies, and students beginning post-secondary studies in January 2027 at the University of Toronto or another post-secondary institution, are not eligible.",
  equivalent_degree_allowed: false,
  equivalent_degree_note: "An equivalent prior degree is not accepted: applicants must be entering first-entry undergraduate study directly from senior secondary school, and students already attending post-secondary studies are ineligible. A wide range of equivalent senior-secondary curricula are accepted for admission, including the International Baccalaureate Diploma with English HL or SL, British-patterned education (five IGCSE/GCSE/Ordinary Level subjects plus three A Level/International A Level subjects, with four AS subjects considered for most programmes), six CAPE units, the French Baccalauréat including Anglais, a U.S.-patterned high school diploma from an accredited high school, and national curricula listed in the university's High School Requirements by Country section. The IB Career-related Programme is not accepted as a basis of admission to degree programmes.",
  age_limit: {
    minimum_age: null,
    maximum_age: null,
    age_calculation_date: null,
    official_source: null
  },
  gender_restriction: false,
  nationality_quota: null,
  previous_emjm_scholarship_ineligible: false,
  previous_award_restriction: "None published. The official award page does not bar applicants or recipients from holding, or having held, other scholarships or awards, and publishes no restriction on concurrent awards, funding or sponsorship.",
  eligibility: {
    citizenship: "Must be an international student, which the university defines as a non-Canadian requiring a study permit. International students studying at Canadian high schools are also eligible. No nationality quota is published; the official award page states that 188 countries are represented among Pearson Scholars.",
    residence_requirement: "No residence requirement is published beyond being a non-Canadian requiring a study permit. Applicants may attend secondary school anywhere in the world, including in Canada.",
    age_limit: "None published.",
    secondary_school_requirement: "Must be enrolled in the final year of senior secondary school in 2026/2027, or have graduated from senior secondary school no earlier than June 2026. Students already attending post-secondary studies, or beginning post-secondary studies in January 2027 at the University of Toronto or another institution, are not eligible.",
    academic_requirements: "Must be admissible to a first-entry undergraduate programme at the University of Toronto. No minimum average, GPA or rank is published specifically for the Pearson Scholarship. The university publishes curriculum-specific minimum admission requirements and states that conditional offers will be made on the previous year's grades and in-term or mid-term results where available, with all required documents due by the published document deadline. For U.S.-patterned education the university expects competitive applicants to be enrolled in a rigorous academic course load and to have taken the highest level of course available in prerequisite subjects.",
    gpa_requirement: "No GPA, minimum average or class rank is published as a Pearson Scholarship criterion. The university's curriculum-specific minimum admission requirements function as the academic floor for admission, and U of T assesses applicants holistically within their academic context.",
    language_requirement: "All applicants must demonstrate a high level of English proficiency unless they qualify for an exemption. Exemptions apply to applicants who have completed or are completing four or more years of full-time study in a recognized Canadian school in Canada, or four or more years of full-time study in an English-language school located in a country where the dominant language is English. Regardless of test results, all applicants must present a senior/Grade 12 English course (equivalent to Ontario ENG4U/EAE4U), which is calculated as part of the admission average. Minimum scores are institution-wide admission requirements, not scholarship-specific thresholds: IELTS Academic overall 6.5 with no band below 6.0; TOEFL iBT overall 4.5 with 4.5 in Writing and 4.0 in Speaking for tests completed on or after January 21, 2026 (or a total of 89 with 22 in each of Speaking and Writing for tests completed before that date); PTE Academic overall 65 with no part below 60; Duolingo English Test overall 120 with 120 in Production for tests completed on or after July 1, 2024; CAEL overall 70 with no part below 60; Cambridge English C1 Advanced or C2 Proficiency overall 180 with at least 170 in each component.",
    work_experience: "None required. Not a published criterion.",
    extracurricular_requirement: "Applicants are expected to be recognised as leaders within their school. The university states that 'a special emphasis is placed on the impact the student has had on the life of their school and community'.",
    leadership_requirement: "Yes. The scholarship recognises students who demonstrate exceptional academic achievement, creativity and leadership potential, who are recognised as leaders within their school, and whose future potential to contribute positively to the global community is emphasised.",
    financial_need: "Not a stated criterion. The award is merit-based and the official pages publish no financial-need test. Financial need may be relevant to other University of Toronto international admission awards, but not to the Pearson Scholarship. The university states it cannot offer financial aid to international students.",
    previous_scholarship_restriction: "None published.",
    enrolment_status_requirement: "Must be entering first-entry undergraduate studies at the University of Toronto in September 2027. Students already attending post-secondary studies, and students beginning post-secondary studies in January 2027 at the University of Toronto or another post-secondary institution, are ineligible. Applicants may be nominated by their school before applying to the University of Toronto, but must apply for admission in order to submit the scholarship application.",
    health_requirement: "None published for the award itself. International students must enrol in the University Health Insurance Plan (UHIP).",
    field_restrictions: "None for the award itself. Applicants may apply to up to three programme areas on the admission application; however, if awarded, the Pearson Scholarship is restricted to the applicant's top choice of programme at the time scholarship decisions are made. Some programme areas require supplemental applications and prerequisites.",
    official_source: "https://future.utoronto.ca/pearson-scholarships"
  },
  academic_requirements: {
    fixed_percentage_requirement: false,
    percentage_note: "No fixed percentage, minimum admission average, GPA threshold or class rank is published for the Lester B. Pearson International Scholarship on any official University of Toronto page read. Academic assessment is relative to the applicant's curriculum and school context.",
    programme_specific_requirements: "Applicants must be admissible to a first-entry undergraduate programme. The university sets curriculum-specific minimum requirements, including: International Baccalaureate Diploma with English HL or SL (prerequisites at Standard or Higher Level; final results must be submitted electronically by the IBO); British-patterned education requiring five IGCSE/GCSE/Ordinary Level academic subjects and three A Level/International A Level academic subjects (four AS subjects considered for most programmes), with English required and Mathematics AS or A Level required for programmes with a Calculus prerequisite, and BTEC National, Cambridge Technical and T-Level qualifications not accepted in lieu of AS or A Level subjects; six CAPE units with English at CSEC or CAPE level; French Baccalauréat including Anglais, with Anglais in both the première and terminale years; and a U.S.-patterned high school diploma from an accredited high school with prerequisites at Senior Year/Grade 12 level or AP/IB, and Calculus, AP Calculus (AB or BC) or one semester of university calculus for most mathematics, science, computer science and commerce programmes. Applicants following a national curriculum can consult High School Requirements by Country. Applicants must apply to at least one undergraduate programme, and may apply to up to three programme areas; several programme areas require supplemental applications by their own deadlines.",
    selection_factors_may_include: [
      "Exceptional academic achievement",
      "Creativity",
      "Leadership potential and being recognised as a leader within the school",
      "Impact the student has had on the life of their school and community",
      "Community involvement",
      "Future potential to contribute positively to the global community",
      "School nomination as the school's single top candidate"
    ],
    holistic_selection_note: "The official pages describe recognition of 'exceptional academic achievement, creativity and leadership potential', and the University of Toronto Scarborough page states that 'a special emphasis is placed on the impact the student has had on the life of their school and community, and their future potential to contribute positively to the global community.' No published weighting, scoring rubric or ranking of criteria is given, and no interview is described."
  },
  english_requirement: {
    universal_requirement: true,
    minimum_ielts: "Overall band 6.5 with no band below 6.0 (IELTS Academic, including IELTS Online). IELTS Indicator and IELTS One Skill Retake results are not accepted.",
    minimum_toefl: "Overall score of 4.5 with 4.5 in Writing and 4.0 in Speaking for tests completed on or after January 21, 2026; for tests completed before January 21, 2026, a total score of 89 with 22 in each of Speaking and Writing. TOEFL iBT including Home Edition and Paper Edition. TOEFL Essentials, TOEFL ITP and TOEFL ITP Plus for China are not accepted, and TOEFL MyBest scores are not used.",
    minimum_pte: "Overall score of 65 with no part below 60 (PTE Academic, including UKVI sittings).",
    minimum_duolingo: "Overall score of 120 with a score of 120 in Production (Duolingo English Test, for tests completed on or after July 1, 2024).",
    moi_rule: "A senior/Grade 12 English course is mandatory for admission to all programmes and is calculated as part of the admission average, but it does not satisfy the English proficiency requirement. Exemption from the proficiency test requires four or more years of full-time study in a recognized Canadian school in Canada, or four or more years of full-time study in an English-language school in a country where the dominant language is English.",
    moi_accepted: false,
    test_score_note: "These are University of Toronto institution-wide undergraduate admission requirements, not Pearson-specific thresholds. Scores must be sent electronically by the testing agency directly to University Admissions & Outreach; scores submitted by the applicant or their school are not accepted. Do not send results until the U of T applicant number has been received. Register for tests using the same first name, surname and date of birth as on the admission application. Scores are also required by the published supporting-documentation deadline. Applicants who do not meet the requirement but are otherwise admissible may be considered for English Language Transition Programs (six weeks to eight months, offered on all three campuses).",
    test_validity_months: null,
    accepted_tests: [
      "Cambridge English C1 Advanced or C2 Proficiency (minimum overall 180, at least 170 in each component; B2 First not accepted)",
      "Canadian Academic English Language Assessment (CAEL), including CAEL Online (overall 70, no part below 60)",
      "Caribbean Examinations Council English courses (final grade A (I) or B (II) in CSEC English)",
      "Duolingo English Test (overall 120, 120 in Production; tests on or after July 1, 2024)",
      "English Language Diagnosis and Assessment / Certificate of Proficiency in English (ELDA/COPE) (total 86, 32 Writing, 22 each Reading and Listening; discretionary range total 80+)",
      "GCSE/IGCSE/GCE/AICE English (minimum final grade B/6 in Ordinary Level English, English Language or English as a Second Language, or minimum final or predicted grade C in GCE A Level/AS Level/AICE English or English Language; English as an Additional Language and English Literature not accepted)",
      "International Baccalaureate English (at least 4 predicted or final in HL or SL English A: Literature or English A: Language and Literature; IB English B HL with a score of 7 also acceptable)",
      "IELTS Academic, including IELTS Online (overall 6.5, no band below 6.0)",
      "Pearson Test of English (PTE) Academic (overall 65, no part below 60)",
      "TOEFL iBT, including Home Edition and Paper Edition (overall 4.5, 4.5 Writing, 4.0 Speaking for tests on or after January 21, 2026; total 89 with 22 each in Speaking and Writing for earlier tests)",
      "University of Toronto School of Continuing Studies 'Academic English' course (grade B at the 60/Advanced level)",
      "University Studies (one year of full-time study at a recognized university in a country where English is dominant, with at least four full-year transferable courses at grade C or better)",
      "Ontario College of Applied Arts and Technology (three-year Advanced Diploma or final-semester enrolment with overall B+ standing, all study completed in Ontario)"
    ]
  },
  language_of_instruction: {
    programme_specific: true,
    possible_languages: ["English"],
    bilingual_programmes: false,
    language_note: "English is the language of instruction and examination at the University of Toronto, and the university states that success in its degree programmes requires a high level of English proficiency. The university publishes French-language admission pathways for the French Baccalauréat (including Anglais in the première and terminale years), but instruction is in English."
  }
};
