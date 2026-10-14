// Part 4: selection, degree outcome, student rights, practical data and risk flags for slot 49.
const AWARD_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students/science-technology-undergraduate-scholarship';
const DATES_URL = 'https://nus.edu.sg/oam/scholarships/important-dates-and-application';
const MOE_TG_EMP_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme/employment';
const MOE_TG_LIQ_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme/liquidated-damages';

function extend(record) {
  // ---- selection process ----
  record.selection_process = {
    decision_maker:
      'NUS selection committee for the Science & Technology Undergraduate Scholarship, operating within the NUS Office of Admissions',
    selection_type:
      'Competitive, automatic consideration at admission with a shortlisting stage and a selection interview for shortlisted applicants',
    central_selection: false,
    possible_stages: [
      'Submit the NUS undergraduate admission application within the admissions application period for your qualification',
      'NUS considers all eligible students applying for undergraduate admission for this scholarship (no separate scholarship submission)',
      'NUS assesses invited applicants for scholarship suitability based on the strength of their application',
      'Only applicants shortlisted for the selection interview(s) are informed via e-mail',
      'Selection interview(s) conducted from January to July',
      'Interviewed candidates are informed of the scholarship outcomes by mid-July',
      'On award, take up the MOE Tuition Grant and complete the MOE Tuition Grant application and signing',
      'Semesterly renewal review against the GPA of at least 3.50 (or equivalent) and good conduct',
    ],
    official_universal_weighting: null,
    weighting_note:
      'NUS publishes no numerical weighting or scoring formula among high school results, co-curricular record, leadership and interview performance, so selection_weighting and official_universal_weighting are null.',
    interview_possible: true,
    results_timing:
      'Selection interview(s) are conducted from January to July, and interviewed candidates will be informed of the scholarship outcomes by mid-July. Only shortlisted applicants are contacted, so absence of contact before mid-July is not an outcome.',
    scholarship_rank_note:
      'No ranked list, waiting list or cut-off score is published. NUS states that it reserves the right not to award any scholarship if there are no candidates of sufficient merit, and that the decision of the selection committee is final and enquiries or disputes surrounding its decisions will not be entertained.',
  };

  // ---- selection criteria ----
  record.selection_criteria = {
    academic_excellence: true,
    leadership: true,
    community_service: false,
    extracurricular_achievement: true,
    financial_need: false,
    additional_factors: [
      'Strength of the application for undergraduate admission to NUS overall',
      'Performance at the selection interview(s)',
      'Entry into one of the eligible Computing, Engineering or Science programmes',
      'Not being a transfer applicant from a local or overseas university',
      'For Double Degree Programme students, the home programme falling within the listed programmes',
    ],
    interview_required: true,
    portfolio_required: false,
    source: AWARD_URL,
  };

  // ---- degree outcome ----
  record.degree_outcome = {
    awarded_qualification:
      'The scholarship funds a full-time NUS undergraduate degree programme in Computing, Engineering or Science; it does not itself award a separate qualification.',
    typical_programme_length:
      'Set by each NUS degree programme. NUS states the scholarship is tenable for the normal candidature period of the undergraduate programme at NUS but publishes no fixed number of years.',
    possible_awards: ['Science & Technology Undergraduate Scholarship (single award type)'],
    degree_note:
      'This is an admission scholarship for freshmen. Applicants must be applying for admission to a full-time undergraduate degree programme at NUS; transfer applicants from local or overseas universities are not eligible.',
    credit_transfer:
      'Addressed indirectly through the credit-distribution rule: overseas programmes must be completed before September of the year prior to graduation, and at least 75% of the credits/units required for graduation must be earned in Singapore with no more than 25% obtained through overseas programmes. NUS\'s own example: if 160 units are required to graduate, a maximum of 40 units may be earned through overseas programmes.',
  };

  // ---- student rights and cost protection ----
  record.student_rights_and_cost_protection = {
    tuition_fee_for_recipients:
      'Subsidised undergraduate tuition fees are fully covered, after the MOE Tuition Grant, and recipients are required to take up the MOE Tuition Grant. Students who do not complete the MOE Tuition Grant application and signing by the stipulated deadlines are charged the non-subsidised tuition fees by NUS.',
    application_fee_for_recipients:
      'No scholarship application fee, because there is no separate scholarship application for this award.',
    student_agreement:
      'On award, recipients take up the MOE Tuition Grant, applying and signing through the MOE Tuition Grant and Scholarships portal, and accept the scholarship terms. Those terms require a six-year bond with a Singapore-registered company immediately after graduation, bar concurrent holding of any other scholarship, fellowship, bursary, grant, award or allowance besides the MOE Tuition Grant, require semesterly renewal at a GPA of at least 3.50 (or equivalent) with good conduct, and require at least 75% of graduation credits to be earned in Singapore with overseas programmes completed before September of the year prior to graduation. NUS reserves the right to impose repayment of all scholarship monies disbursed if the recipient withdraws from the University and/or terminates the scholarship prematurely.',
    programme_website: AWARD_URL,
    common_services:
      'NUS publishes no scholarship-specific student services. The accommodation element is an annual allowance equivalent to the lowest double room rate for on-campus accommodation, and the computer element is a one-time S$1,750 computer allowance upon enrolment.',
    bond_requirement:
      'Six-year bond with a Singapore-registered company immediately after graduation. Separately, recipients must take up the MOE Tuition Grant, and Singapore Permanent Residents and international students who receive a Tuition Grant are required to work for a Singapore entity for three years upon graduation, employed full-time in a Singapore entity for 3 years to fulfil the bond obligations.',
    bond_breach_consequence:
      'NUS states that it does not guarantee and/or provide scholarship recipients with employment upon graduation, and that if the scholarship recipient decides to withdraw from the University and/or terminate the scholarship prematurely, the University reserves the right to impose repayment of all scholarship monies disbursed to the scholar. For the MOE Tuition Grant bond, MOE publishes liquidated-damages consequences where there are changes to course status or where a recipient buys out the bond, and provides a bond-deferment process.',
  };

  // ---- practical application data ----
  record.practical_application_data = {
    application_readiness_checklist: [
      'Confirm you are a citizen of an Asian country or region other than Singapore, because the award is closed to Singapore citizens and to citizens of countries outside Asia',
      'Check your intended programme against the official eligible-programme list before applying, because the award does not cover every Computing, Engineering or Science programme',
      'Rule out Infrastructure and Project Management under Engineering and Environmental Studies and Pharmacy under Science, which are expressly excluded',
      'Confirm you are not applying as a transfer applicant from a local or overseas university',
      'If entering a Double Degree Programme, confirm which programme is your home programme, since coverage depends on it',
      'Hold, or be completing, a high school qualification eligible for admission to NUS and assemble results showing outstanding performance',
      'Assemble documented evidence of co-curricular activities and leadership, since NUS assesses suitability on the strength of the application',
      'Submit the single NUS undergraduate admission application within the admissions application period for your qualification - there is no separate scholarship form or deadline',
      'Be available between January and July for the selection interview if NUS contacts you by e-mail',
      'Plan for the six-year post-graduation bond with a Singapore-registered company before accepting, and for the three-year MOE Tuition Grant bond that comes with the required Tuition Grant',
      'Review any planned overseas exchange or study-abroad load against the 75% in-Singapore credit rule before committing',
    ],
    programme_comparison_fields: [
      'Award type (admission scholarship versus enrolled-student aid)',
      'Whether consideration is automatic with admission or requires a separate application',
      'Citizenship gate (Asian country or region excluding Singapore, versus worldwide)',
      'Field-of-study restriction (Computing, Engineering, Science with named exclusions)',
      'Tuition basis (subsidised fees after the MOE Tuition Grant versus full non-subsidised fees)',
      'Recurring allowance (S$6,000 annual living allowance) and one-time allowances (S$1,750 computer, S$200 settling-in)',
      'Accommodation support (annual allowance at the lowest on-campus double room rate)',
      'Travel support (incoming and return passage, return subject to proof of employment)',
      'Service bond length (six years) and the separate three-year MOE Tuition Grant bond',
      'Renewal threshold (GPA of at least 3.50 or equivalent, reviewed every semester)',
      'Concurrent-award restriction (no other scholarship, fellowship, bursary, grant, award or allowance besides the MOE Tuition Grant)',
    ],
    motivation_letter_strategy:
      'No scholarship-specific essay or motivation letter is required, because there is no separate scholarship application. The strategic equivalent is the NUS undergraduate admission application itself, which NUS assesses for scholarship suitability: make outstanding high-school results, the co-curricular record and leadership visible there, since only applicants shortlisted on the strength of that application are contacted for the selection interview.',
    profile_fit_labels: [
      'Outstanding Asian high-school leaver (excluding Singapore citizens) applying to a first-year NUS degree',
      'Applicant targeting NUS Computing, Engineering or Science',
      'Applicant with a strong co-curricular record and demonstrated leadership',
      'Applicant willing to accept a six-year post-graduation bond with a Singapore-registered company',
      'Applicant willing to take up the MOE Tuition Grant and its bond',
      'Applicant who can keep at least 75% of graduation credits in Singapore',
    ],
    common_mistakes: [
      'Assuming this is a separate scholarship you apply for after admission - NUS considers all eligible students through the undergraduate admission application',
      'Applying to a programme outside the official list, for example Infrastructure and Project Management under Engineering, or Environmental Studies or Pharmacy under Science',
      'Holding a nationality outside Asia, or being a Singapore citizen, neither of which is eligible',
      'Applying as a transfer applicant from a local or overseas university, which is expressly ineligible',
      'Missing the NUS admissions application period for your qualification, because there is no separate scholarship window to fall back on',
      'Assuming the 1 February to 19 March 2027 window applies to this award - that window belongs to NUS Scholarships for Freshmen (Singapore Citizens)',
      'Believing the award covers the full non-subsidised international tuition rate - coverage is stated only against subsidised undergraduate tuition fees after the MOE Tuition Grant',
      'Ignoring the six-year bond, on the assumption that NUS arranges employment - NUS states it does not guarantee and/or provide employment upon graduation',
      'Falling below a GPA of 3.50, since the scholarship is reviewed and renewed every semester',
      'Holding another scholarship, fellowship, bursary, grant, award or allowance concurrently besides the MOE Tuition Grant',
      'Planning an overseas programme or exchange load above 25% of graduation credits, or leaving an overseas programme unfinished past September of the year before graduation',
      'Withdrawing from NUS or terminating the scholarship early, which can trigger repayment of all scholarship monies disbursed',
      'Assuming this is the same award as the NUS International Undergraduate Scholarship, which is open to citizens of all countries except Singapore and is already a separate record in this database',
    ],
  };

  // ---- risk flags ----
  record.risk_flags = [
    {
      risk: 'Six-year service bond and no employment guarantee',
      impact:
        'Recipients must serve a six-year bond with a Singapore-registered company immediately after graduation, while NUS states it does not guarantee and/or provide employment upon graduation, so a graduate who cannot secure a qualifying Singapore position is exposed.',
      mitigation:
        'Record the bond in funding_breakdown.bond and student_rights_and_cost_protection.bond_requirement, and set fully_funded to false so the award is never presented as an unconditional full ride.',
    },
    {
      risk: 'Citizenship gate is narrow',
      impact:
        'Only citizens of an Asian country or region, excluding Singapore, are eligible; applicants from outside Asia and Singapore citizens themselves cannot hold this award.',
      mitigation:
        'Set citizenship_restriction to true and worldwide_eligibility to false, and state the gate in eligible_applicants, not_best_fit and eligibility.citizenship so it is not overstated as a worldwide award.',
    },
    {
      risk: 'No scholarship deadline of its own',
      impact:
        'Because consideration is automatic through the admissions application, an applicant who misses the NUS admissions application period for their qualification has no separate scholarship window to fall back on, and deadlines vary by qualification.',
      mitigation:
        'Set deadline_date to null with deadline_precision "programme_specific", quote NUS\'s "Based on admissions application timeline" wording in official_rule, and warn against reusing the Singapore Citizen window.',
    },
    {
      risk: 'Field-of-study restriction with named exclusions',
      impact:
        'The award covers only the listed Computing, Engineering and Science programmes, excluding Infrastructure and Project Management under Engineering and Environmental Studies and Pharmacy under Science, so an otherwise strong applicant in an excluded programme receives nothing.',
      mitigation:
        'Reproduce the full official programme list in eligibility.field_restrictions and flag the two named exclusions in coverage_limitations, risk flags and not_best_fit.',
    },
    {
      risk: 'Tuition coverage is stated only against subsidised fees',
      impact:
        'Coverage is 100% of subsidised undergraduate tuition fees after the MOE Tuition Grant, which recipients must take up; the gap to the full non-subsidised international rate is not covered, and failing the Tuition Grant signing deadlines triggers non-subsidised fees.',
      mitigation:
        'State the subsidised basis explicitly in funding.tuition and coverage_limitations, and record the MOE Tuition Grant requirement in the bond and student-agreement fields.',
    },
    {
      risk: 'Semesterly renewal at a GPA of 3.50',
      impact:
        'The scholarship is renewed every semester only if the scholar maintains a GPA of at least 3.50 (or equivalent) and has good conduct, so a single weak semester puts the award at risk.',
      mitigation:
        'Record the renewal threshold in programme_structure.renewal_criteria, programme_duration.renewal_note and eligibility.gpa_requirement, and list it among common mistakes.',
    },
    {
      risk: 'Several benefit amounts are published only as rates or passages, not sums',
      impact:
        'The accommodation allowance is expressed as the lowest on-campus double room rate and the travel allowance covers named passages without any amount, so any quoted "total award value" would be invented.',
      mitigation:
        'Keep amount fields null for those elements, prohibit a computed total in funding_breakdown.total_estimated_value, and list the gaps in verification.unverified_or_removed_claims.',
    },
    {
      risk: 'Concurrent-award restriction',
      impact:
        'Besides the MOE Tuition Grant, recipients may not concurrently hold any other scholarship, fellowship, bursary, grant, award or allowance, which forecloses stacking this award with other funding.',
      mitigation:
        'Record the restriction in previous_award_restriction, eligibility.previous_scholarship_restriction and coverage_limitations.',
    },
  ];

  record.application_status_workflow = [
    'NUS undergraduate admissions application period opens for the applicant\'s qualification',
    'Applicant submits the single NUS undergraduate admission application through the Applicant Portal',
    'All eligible students applying for undergraduate admission are considered for this scholarship',
    'NUS assesses invited applicants for scholarship suitability based on the strength of their application',
    'Shortlisted applicants are informed via e-mail',
    'Selection interview(s) conducted from January to July',
    'Outcomes communicated to interviewed candidates by mid-July',
    'On award, MOE Tuition Grant offer accepted and signed through the MOE Tuition Grant and Scholarships portal',
    'Scholarship acceptance terms accepted, including the six-year bond with a Singapore-registered company',
    'Semesterly renewal review against the GPA of at least 3.50 (or equivalent) and good conduct',
    'Graduation, followed by the six-year bond with a Singapore-registered company and the three-year MOE Tuition Grant bond',
  ];

  record.best_fit =
    'An outstanding high-school leaver who is a citizen of an Asian country or region other than Singapore, holds outstanding high school results with an excellent co-curricular record and demonstrated leadership, and is applying for first-year admission to a full-time NUS degree programme on the eligible list in Computing, Engineering or Science. The award suits an applicant who is willing to take up the MOE Tuition Grant, to accept a six-year post-graduation bond with a Singapore-registered company, to forgo any other concurrent scholarship, fellowship, bursary, grant, award or allowance, and to keep at least 75% of the credits required for graduation earned in Singapore.';

  record.not_best_fit = [
    'Singapore citizens, who are excluded by the citizenship criterion',
    'Citizens of countries or regions outside Asia, who are not eligible for this award',
    'Applicants to Infrastructure and Project Management, Environmental Studies or Pharmacy, which are expressly excluded from the field restriction',
    'Applicants to any Computing, Engineering or Science programme not on the official eligible-programme list',
    'Transfer applicants from local or overseas universities, who are not eligible',
    'Applicants who cannot commit to the six-year bond with a Singapore-registered company immediately after graduation',
    'Applicants unwilling to take up the MOE Tuition Grant and its three-year bond',
    'Applicants who need to hold another scholarship, fellowship, bursary, grant, award or allowance concurrently',
    'Applicants planning an overseas exchange or study-abroad load above 25% of graduation credits',
    'Applicants who require a separate scholarship application with its own deadline, rather than automatic consideration',
    'Applicants seeking coverage of the full non-subsidised international tuition rate',
  ];
}

module.exports = { extend };
