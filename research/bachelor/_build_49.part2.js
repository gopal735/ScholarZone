// Part 2: funding, coverage, eligibility, academic and language blocks for slot 49.
const AWARD_URL =
  'https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students/science-technology-undergraduate-scholarship';
const DATES_URL = 'https://nus.edu.sg/oam/scholarships/important-dates-and-application';
const NUS_TG_URL = 'https://nus.edu.sg/oam/financial-aid/moe-tuition-grant-tuition-fees';
const MOE_TG_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme';
const MOE_TG_EMP_URL = 'https://www.moe.gov.sg/financial-matters/tuition-grant-scheme/employment';

function extend(record) {
  // ---- funding ----
  record.funding = {
    scholarship_available: true,
    scholarship_type:
      'University-level merit scholarship awarded at admission, considered automatically with the NUS undergraduate admission application',
    scholarship_currency: 'SGD',
    monthly_amount: null,
    monthly_amount_note:
      'No monthly stipend is paid. The recurring cash benefit is a S$6,000 annual living allowance plus an annual accommodation allowance set by reference to the lowest on-campus double room rate; NUS publishes no monthly rate.',
    travel_support: true,
    visa_support: false,
    installation_support: true,
    living_allowance: true,
    insurance: false,
    travel_amount: null,
    travel_amount_note:
      'NUS states the travel allowance "defray[s] transport cost for incoming passage from home country to Singapore at the start of Programme, and return passage between Singapore and home country after the completion of Programme (subject to proof of employment)". No per-passage amount, cap or claim procedure is published.',
    institutional_costs:
      'NUS publishes no aggregate institutional cost or budget for this scholarship. The only published monetary values are the S$6,000 annual living allowance, the S$1,750 one-time computer allowance and the S$200 one-time settling-in allowance; the tuition element is a coverage statement against subsidised fees rather than a sum, and the accommodation allowance is expressed as a room rate rather than a sum.',
    fully_funded: false,
    fully_funded_note:
      'Not unconditionally fully funded. Tuition coverage is stated only against subsidised undergraduate tuition fees after the MOE Tuition Grant, which recipients are required to take up, so the gap to the full non-subsidised international rate is not covered. The award also carries a six-year bond with a Singapore-registered company immediately after graduation, and the required MOE Tuition Grant carries its own three-year bond for Permanent Residents and international students. NUS states it does not guarantee and/or provide scholarship recipients with employment upon graduation.',
  };

  record.funding_breakdown = {
    tuition: {
      covered: true,
      amount: null,
      currency: 'SGD',
      conditions:
        '100% coverage of subsidised undergraduate tuition fees (after MOE Tuition Grant - scholarship recipients must take up the MOE Tuition Grant). No monetary figure is published and coverage is stated only against the subsidised rate.',
    },
    monthly_stipend: {
      available: false,
      note: 'Not published in official source - the award pays an annual living allowance, not a monthly stipend.',
    },
    travel_allowance: {
      available: true,
      amount: null,
      currency: 'SGD',
      conditions:
        'Travel allowance to defray transport cost for incoming passage from home country to Singapore at the start of the programme, and return passage between Singapore and home country after completion of the programme (subject to proof of employment). No amount is published.',
    },
    installation_allowance: {
      available: true,
      amount: 200,
      currency: 'SGD',
      conditions: 'S$200 one-time settling-in allowance upon enrolment.',
    },
    visa_support: { available: false, note: 'Not published in official source.' },
    insurance: { available: false, note: 'Not published in official source.' },
    research_allowance: { available: false, note: 'Not published in official source.' },
    book_allowance: { available: false, note: 'Not published in official source.' },
    equipment_allowance: {
      available: true,
      amount: 1750,
      currency: 'SGD',
      conditions: 'S$1,750 one-time computer allowance upon enrolment.',
    },
    family_allowance: { available: false, note: 'Not published in official source.' },
    accommodation_support: {
      available: true,
      amount: null,
      currency: 'SGD',
      conditions:
        'Annual accommodation allowance equivalent to the lowest double room rate for on-campus accommodation. NUS publishes no monetary figure; it states the allowance only by reference to the room rate.',
    },
    bond: {
      available: true,
      amount: null,
      currency: null,
      conditions:
        'Scholarship recipients are required to serve a six-year bond with a Singapore-registered company immediately after graduation. Separately, recipients must take up the MOE Tuition Grant, and Permanent Residents and international students who receive a Tuition Grant are required to work for a Singapore entity for three years upon graduation (employed full-time in a Singapore entity for 3 years to fulfil the bond obligations).',
    },
    total_estimated_value: {
      note:
        'No total value is computed or presented as an award. The tuition element is a coverage statement against subsidised fees, the accommodation allowance is expressed as a room rate rather than a sum, and the travel allowance is unquantified by NUS, so any headline total would be invented.',
    },
  };

  // ---- coverage ----
  record.coverage = [
    '100% coverage of subsidised undergraduate tuition fees (after MOE Tuition Grant - scholarship recipients must take up the MOE Tuition Grant)',
    'S$6,000 annual living allowance',
    'S$1,750 one-time computer allowance upon enrolment',
    'S$200 one-time settling-in allowance upon enrolment',
    'Annual accommodation allowance equivalent to the lowest double room rate for on-campus accommodation',
    'Travel allowance to defray transport cost for incoming passage from home country to Singapore at the start of the programme, and return passage between Singapore and home country after completion of the programme (subject to proof of employment)',
  ];

  record.coverage_limitations = [
    'Tuition coverage is stated only against subsidised undergraduate tuition fees after the MOE Tuition Grant; the difference between the subsidised and the full non-subsidised international tuition rate is not covered, and NUS states that students who do not complete the MOE Tuition Grant application and signing by the stipulated deadlines will be charged the non-subsidised tuition fees.',
    'Recipients are required to take up the MOE Tuition Grant, which itself carries a three-year bond to work for a Singapore entity after graduation for Permanent Residents and international students, in addition to the scholarship\'s own six-year bond.',
    'The accommodation allowance is capped at the lowest double room rate for on-campus accommodation; NUS publishes no monetary figure for it.',
    'The travel allowance covers only the incoming passage and the return passage, and the return passage is subject to proof of employment; personal travel is not covered.',
    'NUS does not guarantee and/or provide scholarship recipients with employment upon graduation, so the six-year bond is a real post-graduation constraint rather than a formality.',
    'Besides the MOE Tuition Grant, recipients may not concurrently hold any other scholarship, fellowship, bursary, grant, award or allowance.',
    'Exact benefit structure may differ in future cycles; all amounts and terms quoted here are those published on the official page at the verification date.',
  ];

  record.eligible_applicants = [
    'Citizens of an Asian country or region, excluding Singapore',
    'Applicants with outstanding high school results',
    'Applicants with an excellent co-curricular activities record',
    'Applicants with strong leadership qualities and potential',
    'Applicants applying for admission to a full-time undergraduate degree programme in Computing, Engineering (excluding Infrastructure and Project Management) or Science (excluding Environmental Studies and Pharmacy) at NUS',
    'Freshmen entering one of the specific full-time undergraduate programmes listed in the scholarship Terms and Conditions',
    'Students in local Double Degree Programmes whose home programme falls within one of the listed programmes',
    'Holders of a high school qualification eligible for admission to NUS',
  ];

  // ---- citizenship / global flags ----
  record.citizenship_restriction = true;
  record.worldwide_eligibility = false;
  record.bachelor_requirement = false;
  record.final_year_bachelor_allowed = false;
  record.final_year_condition =
    'Not applicable in the bachelor\'s-degree sense. This is a freshmen admission scholarship, so the qualifying credential is a high-school qualification: NUS states the qualification requirement as "High school qualifications eligible for admission to NUS". Final-year high-school students applying for first-year admission to NUS are the intended applicants. Transfer applicants from local or overseas universities are not eligible.';
  record.equivalent_degree_allowed = true;
  record.equivalent_degree_note =
    'Yes, by reference. The scholarship publishes no qualification list of its own; it adopts the NUS admissions rule "High school qualifications eligible for admission to NUS", which NUS administers across Singapore-Cambridge GCE A-Level, Polytechnic Diploma from Singapore, NUS High School Diploma, IB Diploma and International Qualifications (except IB Diploma). Whether a particular foreign school-leaving qualification counts is decided by the NUS undergraduate admissions process, not by the scholarship terms.';
  record.age_limit = null;
  record.gender_restriction = false;
  record.nationality_quota = null;
  record.previous_emjm_scholarship_ineligible = false;
  record.previous_award_restriction =
    'Scholarship recipients are required to take up the MOE Tuition Grant. Besides this, they may not concurrently hold any other scholarship, fellowship, bursary, grant, award or allowance. No restriction on having previously applied for, or held, this same scholarship is published.';
}

module.exports = { extend };
