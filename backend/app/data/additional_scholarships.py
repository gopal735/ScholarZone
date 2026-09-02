"""Additional verified scholarship records for expansion.

These records are verified from official sources and complement the existing
VERIFIED_SCHOLARSHIPS catalogue. Add new records here after verification.
"""

from datetime import date

from ..services.scholarship_ingestion import ScholarshipIngestionRecord


# =============================================================================
# UNITED KINGDOM SCHOLARSHIPS
# =============================================================================

UK_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Clarendon Fund Scholarship",
        country="UK",
        degree_levels="Master's, DPhil (PhD)",
        funding_type="Fully Funded",
        deadline="Course application deadline (December or January, depending on course)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities, all subjects. ~200 new scholarships annually. "
            "No restrictions on nationality or residence. Automatic consideration upon "
            "application to Oxford; no separate scholarship application needed."
        ),
        coverage=["Full tuition fees", "Living cost grant for duration of fee liability"],
        official_source_url="https://www.ox.ac.uk/clarendon",
        official_source="University of Oxford",
        is_verified=True,
        best_fit="Outstanding graduate applicants to any Oxford Master's or DPhil programme",
    ),
    ScholarshipIngestionRecord(
        name="Weidenfeld-Hoffmann Scholarships and Leadership Programme",
        country="UK",
        degree_levels="Master's, DPhil (PhD)",
        funding_type="Fully Funded",
        deadline="Relevant December or January graduate application deadline",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to Bangladesh and 100+ developing/emerging economy countries. "
            "Must intend to return home after studies. Focus on future leaders."
        ),
        coverage=["100% fees", "Living costs", "Leadership development programme"],
        official_source_url="https://www.ox.ac.uk/admissions/graduate/fees-and-funding/fees-funding-and-scholarship-search/weidenfeld-hoffmann-scholarships-and-leadership-programme",
        official_source="University of Oxford",
        is_verified=True,
        best_fit="Future leaders from developing economies including Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="Reach Oxford Scholarship",
        country="UK",
        degree_levels="Undergraduate (all subjects except Medicine)",
        funding_type="Fully Funded",
        deadline="4 February 2026 (for 2026 entry); 2027 entry opens January 2027",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Nationals of OECD DAC-listed countries (Bangladesh included). "
            "Financial need + academic excellence. Must be from a country receiving "
            "official development assistance from the OECD DAC."
        ),
        coverage=["Tuition", "College fees", "Living costs", "Return flights"],
        official_source_url="https://www.ox.ac.uk/admissions/undergraduate/fees-and-funding/oxford-bursaries-and-scholarships/reach-oxford",
        official_source="University of Oxford",
        is_verified=True,
        best_fit="Talented Bangladeshi undergraduates with financial need",
    ),
    ScholarshipIngestionRecord(
        name="Gates Cambridge Scholarship",
        country="UK",
        degree_levels="Master's, PhD (all subjects)",
        funding_type="Fully Funded",
        deadline="Same as course funding deadline (varies by department)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of any country outside the UK. ~80 awards/year. "
            "Academic excellence + leadership potential + commitment to improving lives."
        ),
        coverage=["Full fees", "Maintenance (~£22,050/year)", "Visa/IHS", "Travel costs"],
        official_source_url="https://www.gatescambridge.org/programme/the-scholarship/",
        official_source="Bill & Melinda Gates Foundation / University of Cambridge",
        is_verified=True,
        best_fit="Outstanding international applicants to Cambridge Master's or PhD",
    ),
    ScholarshipIngestionRecord(
        name="Cambridge Trust International Scholarship",
        country="UK",
        degree_levels="Master's, PhD",
        funding_type="Partial to Full",
        deadline="Same as course funding deadline",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All non-UK/non-Ireland nationals. Any subject, any college. "
            "~63 scholarships/year for 2026/27."
        ),
        coverage=["International fees", "Maintenance", "Immigration Health Surcharge"],
        official_source_url="https://www.cambridgetrust.org/",
        official_source="Cambridge Trust / University of Cambridge",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="President's PhD Scholarships — Imperial College London",
        country="UK",
        degree_levels="PhD (3.5 years)",
        funding_type="Fully Funded",
        deadline="Varies (see departmental pages)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="All nationalities. No restrictions. Outstanding academic merit.",
        coverage=["Tuition fees", "£26,500 stipend (2026/27)", "£2,000 consumables/year"],
        official_source_url="https://www.imperial.ac.uk/study/fees-and-funding/postgraduate-doctoral/grants-scholarships/presidents-phd/",
        official_source="Imperial College London",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UCL Global Master's Scholarship",
        country="UK",
        degree_levels="Master's (taught, full-time)",
        funding_type="Partial",
        deadline="5pm BST, 7 May 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Overseas fee-paying students from lower-income backgrounds. "
            "Up to 85 scholarships for 2026/27 (5 ring-fenced for India, 1 for Japan)."
        ),
        coverage=["£15,000 tuition contribution"],
        official_source_url="https://www.ucl.ac.uk/scholarships/ucl-global-masters-scholarship",
        official_source="University College London",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UCL Humanitarian Scholarship",
        country="UK",
        degree_levels="Master's (full-time taught)",
        funding_type="Fully Funded",
        deadline="5pm BST, 7 May 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Students at serious risk or displaced due to armed conflict. "
            "Overseas fee status. Up to 3 scholarships."
        ),
        coverage=["Full tuition", "~£20,000 maintenance", "IHS", "Visa", "Return flight"],
        official_source_url="https://www.ucl.ac.uk/scholarships/ucl-humanitarian-scholarship",
        official_source="University College London",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="LSE PhD Studentships",
        country="UK",
        degree_levels="PhD (4 years)",
        funding_type="Fully Funded",
        deadline="14 January 2026 (some departments 10 December 2025)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Home and Overseas students in any LSE discipline. "
            "Outstanding academic merit + research potential."
        ),
        coverage=["Full tuition", "£22,780 annual stipend"],
        official_source_url="https://www.lse.ac.uk/study-at-lse/Graduate/fees-and-funding/phd-studentships",
        official_source="London School of Economics",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="LSE Excellence Scholarship",
        country="UK",
        degree_levels="Postgraduate Taught (Master's)",
        funding_type="Partial",
        deadline="23 April 2026 (LSE programme application deadline)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High-achieving postgraduate taught students. Automatic consideration. "
            "Eligible departments include Health Policy, International Development, Sociology, Media, Mathematics."
        ),
        coverage=["£20,000; £10,000/year for 2-year programmes"],
        official_source_url="https://www.lse.ac.uk/study-at-lse/graduate/fees-and-funding/lse-masters-awards",
        official_source="London School of Economics",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Global Futures Scholarship (South Asia) — University of Manchester",
        country="UK",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="~April 2026 (check site for 2026/27 cycle dates)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Permanent residents of Bangladesh, India, Pakistan, Sri Lanka. "
            "Bachelor's degree from South Asia. Self-funded. Academic merit."
        ),
        coverage=["£8,000 tuition contribution"],
        official_source_url="https://documents.manchester.ac.uk/display.aspx?DocID=73264",
        official_source="University of Manchester",
        is_verified=True,
        best_fit="South Asian students including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="GREAT Scholarship 2026 — University of Manchester (Bangladesh)",
        country="UK",
        degree_levels="Master's (1-year)",
        funding_type="Partial",
        deadline="23 April 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Bangladeshi passport holders/residents. Self-funded. "
            "Hold an offer for one-year Master's."
        ),
        coverage=["Minimum £10,000 tuition contribution"],
        official_source_url="https://www.manchester.ac.uk/study/international/finance-and-scholarships/funding/great-scholarships/",
        official_source="University of Manchester / British Council",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="GREAT Scholarship 2026 — Cranfield University (Bangladesh)",
        country="UK",
        degree_levels="Master's (selected full-time MSc)",
        funding_type="Partial",
        deadline="18 May 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="Bangladeshi passport holders/residents.",
        coverage=["£10,000 toward tuition"],
        official_source_url="https://www.cranfield.ac.uk/funding/funding-opportunities/great-cranfield-university-scholarship-bangladesh",
        official_source="Cranfield University / British Council",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="GREAT Scholarship 2026 — University of Edinburgh (Bangladesh)",
        country="UK",
        degree_levels="Master's (1-year postgraduate)",
        funding_type="Partial",
        deadline="Varies by institution (2026/27 cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="Bangladeshi passport holders/residents. Academic merit.",
        coverage=["£10,000+ tuition contribution"],
        official_source_url="https://study-uk.britishcouncil.org/scholarships-funding/great-scholarships/bangladesh",
        official_source="University of Edinburgh / British Council",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Edinburgh Global Research Scholarship",
        country="UK",
        degree_levels="PhD (any field)",
        funding_type="Partial",
        deadline="Early February 2026 (verify on official site)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All overseas nationalities (non-UK). 30 scholarships/year. PhD applicants."
        ),
        coverage=["Covers tuition fee gap between UK and Overseas rate (~£16,000-£20,000/year)"],
        official_source_url="https://www.ed.ac.uk/student-funding/postgraduate/international",
        official_source="University of Edinburgh",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Rhodes Scholarship (Global Constituency) — University of Oxford",
        country="UK",
        degree_levels="Master's, DPhil (PhD) at Oxford",
        funding_type="Fully Funded",
        deadline="Varies by constituency (Global deadline ~late August/September 2026 for 2027 entry)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of countries without a dedicated Rhodes constituency (including Bangladesh) "
            "via the Global constituency. Outstanding academic merit + leadership + service commitment."
        ),
        coverage=["Tuition", "~£20,400 stipend", "Travel", "Visa", "IHS"],
        official_source_url="https://www.rhodeshouse.ox.ac.uk/scholarships/applications/global/",
        official_source="Rhodes Trust",
        is_verified=True,
        best_fit="Exceptional Bangladeshi graduates with leadership potential",
    ),
)

# =============================================================================
# CANADA SCHOLARSHIPS
# =============================================================================

CANADA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Study in Canada Scholarships (SICS)",
        country="Canada",
        degree_levels="Master's, PhD, Undergraduate (short-term exchange)",
        funding_type="Fully Funded",
        deadline="March 31, 2026 (varies by year)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of eligible countries including Bangladesh (Asia), "
            "enrolled full-time at home institution. Canadian institutions apply on student's behalf."
        ),
        coverage=["CAD $10,200–$14,000", "Travel", "Health insurance", "Living allowance"],
        official_source_url="https://www.educanada.ca/scholarships-bourses/non_can/index.aspx?lang=eng",
        official_source="Government of Canada (Global Affairs Canada / EduCanada)",
        is_verified=True,
        best_fit="Bangladeshi students at Canadian institutions (institution applies)",
    ),
    ScholarshipIngestionRecord(
        name="Pierre Elliott Trudeau Foundation Doctoral Scholarship",
        country="Canada",
        degree_levels="PhD (humanities & social sciences)",
        funding_type="Fully Funded",
        deadline="~November 17, 2026 (for 2027 cohort; check annually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students enrolled at a Canadian university; research must align with "
            "one of four themes (Human Rights & Dignity, Responsible Citizenship, Canada & the World, "
            "People & Their Natural Environment). Open to Bangladeshi students at Canadian unis."
        ),
        coverage=["Up to $50,000/year stipend ×3 years", "Up to $20,000/year research/travel allowance", "Mentorship"],
        official_source_url="https://www.trudeaufoundation.ca/become-a-scholar/",
        official_source="Pierre Elliott Trudeau Foundation",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="McCall MacBain Scholarships at McGill University",
        country="Canada",
        degree_levels="Master's (and 2nd-entry professional undergraduate)",
        funding_type="Fully Funded",
        deadline="August 19, 2026 (international applicants)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities; must meet one of: (a) graduating bachelor's by Aug 2027, "
            "(b) earned bachelor's within last 5 years, or (c) age ≤30 on Jan 1, 2026."
        ),
        coverage=["Full tuition & fees", "$2,300 CAD/month living stipend", "Relocation grant", "Summer funding", "Leadership program"],
        official_source_url="https://mccallmacbainscholars.org/apply",
        official_source="McGill University / McCall MacBain Foundation",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UBC International Major Entrance Scholarship (IMES)",
        country="Canada",
        degree_levels="Bachelor's (undergraduate direct entry)",
        funding_type="Partial",
        deadline="January 15, 2026 (next cycle: 2027)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students on Canadian study permit, exceptional academics + extracurriculars; "
            "apply to UBC by Jan 15."
        ),
        coverage=["$10,000–$25,000 CAD/year", "Renewable up to 3 additional years"],
        official_source_url="https://you.ubc.ca/financial-planning/scholarships-awards-international-students/",
        official_source="University of British Columbia",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Karen McKellin International Leader of Tomorrow Award (UBC)",
        country="Canada",
        degree_levels="Bachelor's",
        funding_type="Partial to Full",
        deadline="Apply to UBC by January 15, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international undergraduate applicants with demonstrated leadership + financial need."
        ),
        coverage=["Can cover full tuition + living costs (need-and-merit based)"],
        official_source_url="https://you.ubc.ca/financial-planning/scholarships-awards-international-students/international-scholars/",
        official_source="University of British Columbia",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Donald A. Wehrung International Student Award (UBC)",
        country="Canada",
        degree_levels="Bachelor's",
        funding_type="Partial to Full",
        deadline="Apply to UBC by January 15, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students from impoverished or war-torn regions; "
            "academic excellence under challenging circumstances. Bangladeshi students strongly eligible."
        ),
        coverage=["Need-based merit award (can be full-ride equivalent)"],
        official_source_url="https://you.ubc.ca/financial-planning/scholarships-awards-international-students/international-scholars/donald-a-wehrung-international-student-award",
        official_source="University of British Columbia",
        is_verified=True,
        best_fit="Bangladeshi students from challenging circumstances",
    ),
    ScholarshipIngestionRecord(
        name="McMaster University Award of Excellence (International)",
        country="Canada",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="February 19, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International fee-paying students entering Business, Engineering, Humanities, Science, Social Sciences or MELD program."
        ),
        coverage=["Up to $200,000 CAD over 4 years (prestigious entrance award)"],
        official_source_url="https://future.mcmaster.ca/internationalawards/",
        official_source="McMaster University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="York University Global Leader of Tomorrow Award",
        country="Canada",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="January 26, 2026 (annual)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Incoming international high school graduates with 'A' average + community service/leadership record."
        ),
        coverage=["$20,000 CAD/year × 4 years ($80,000 total)"],
        official_source_url="https://futurestudents.yorku.ca/financing-your-degree/international-scholarships",
        official_source="York University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="York University President's International Scholarship of Excellence",
        country="Canada",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="~January 26, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International high school applicants with academic excellence + volunteer + extracurricular record."
        ),
        coverage=["$45,000 CAD/year × 4 years ($180,000 total)"],
        official_source_url="https://futurestudents.yorku.ca/financing-your-degree/international-scholarships/presidents-international-scholarship-excellence",
        official_source="York University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Waterloo International Student Entrance Scholarship",
        country="Canada",
        degree_levels="Bachelor's (Year 1)",
        funding_type="Partial",
        deadline="~September 20, 2026 (next cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="Outstanding international students entering Year 1 undergraduate program.",
        coverage=["$10,000 CAD ×20 scholarships"],
        official_source_url="https://uwaterloo.ca/future-students/financing/international-scholarships",
        official_source="University of Waterloo",
        is_verified=True,
    ),
)

# =============================================================================
# FRANCE SCHOLARSHIPS
# =============================================================================

FRANCE_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Université Paris-Saclay IDEX International Master's Scholarships",
        country="France",
        degree_levels="Master's (M1 & M2)",
        funding_type="Partial",
        deadline="25 March 2026 (programme pre-selection) / 31 March 2026 (scholarship form)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign nationals, first-time enrolment in France, under 30, admitted to an eligible "
            "Master's at Paris-Saclay member institutions (AgroParisTech, CentraleSupélec, ENS Paris-Saclay, IOGS, etc.). "
            "Cannot combine with Eiffel/Europa/Erasmus Mundus."
        ),
        coverage=["€10,000/year", "Up to €1,000 travel/visa allowance", "CROUS fee waived", "Tuition only ~€243–380/yr"],
        official_source_url="https://www.universite-paris-saclay.fr/en/admission/bourses-et-aides-financieres/international-masters-scholarships-program",
        official_source="Université Paris-Saclay (Government of France / IDEX)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Sciences Po Émile Boutmy Scholarship",
        country="France",
        degree_levels="Bachelor's and Master's",
        funding_type="Partial",
        deadline="Bachelor's (foreign schools): 20 January 2026; Master's: check next cycle",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "First-time applicants to Sciences Po, from non-EU countries whose household does not file taxes in the EU. "
            "Bangladesh is fully eligible."
        ),
        coverage=["Up to full tuition waiver (Bachelor's)", "€18,500/yr tuition exemption (Master's, 2 years)"],
        official_source_url="https://www.sciencespo.fr/students/en/fees-funding/bursaries-financial-aid/emile-boutmy-scholarship/",
        official_source="Sciences Po Paris",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="HEC Paris International Scholarships (Need-based & Merit-based)",
        country="France",
        degree_levels="Master's (M1/M2) — Grande École, MiM, MSc",
        funding_type="Partial",
        deadline="24 October 2025 (Round 1) / 22 January 2026 (Round 2) — for next round typically October 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All international applicants admitted to HEC Master's programs; "
            "merit-based is automatic; need-based requires separate form. "
            "Multiple corporate-partnered scholarships (L'Oréal, LVMH, Sanofi, 30% Club, etc.)."
        ),
        coverage=["From a few thousand € up to €24,000/year"],
        official_source_url="https://www.hec.edu/en/hec-paris-scholarships",
        official_source="HEC Paris",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="INSEAD MBA / Master in Management / Master in Finance Scholarships",
        country="France",
        degree_levels="MBA, Master in Management (MIM), Master in Finance (MIF)",
        funding_type="Partial",
        deadline="Tied to admissions rounds (MBA has 4 rounds; MIM/MIF Aug intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All admitted international students; merit, need, diversity, region, and gender-based categories. "
            "Open to all nationalities including Bangladesh."
        ),
        coverage=["170+ scholarship funds", "~41% of class receives scholarships", "Average award ~€24,000 (up to full tuition)"],
        official_source_url="https://www.insead.edu/master-programmes/master-business-administration/international-funding",
        official_source="INSEAD (Fontainebleau/Singapore)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Institut Polytechnique de Paris (IP Paris) PhD Track & Master's Excellence Scholarships",
        country="France",
        degree_levels="Master's and PhD (PhD Track program is a 5-year integrated Master's→PhD)",
        funding_type="Partial",
        deadline="Session 1: 8 January 2026; Session 2: 26 March 2026; Session 3: 28 May 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to IP Paris Master's or PhD Track programs. "
            "Highly selective (~top STEM/research candidates)."
        ),
        coverage=["Excellence Scholarship €10,000/yr", "Reduced tuition (from ~€7,000 to €243/yr for first 2 years)"],
        official_source_url="https://www.ip-paris.fr/en/education/useful-information/scholarships",
        official_source="Institut Polytechnique de Paris",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ENS de Lyon International Master's Scholarships (AMIDEEX)",
        country="France",
        degree_levels="Master's (M1/M2) in sciences, humanities, social sciences",
        funding_type="Partial",
        deadline="Typically early–mid January for the next academic year",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International (non-French) students, under 26, admitted to ENS de Lyon Master's programmes."
        ),
        coverage=["~€1,000/month stipend for 2 years (M1 + M2)", "Travel", "Housing support"],
        official_source_url="https://www.ens-lyon.fr/en/admission/scholarships",
        official_source="ENS de Lyon (via IDEX / Université de Lyon)",
        is_verified=True,
    ),
)

# =============================================================================
# SPAIN SCHOLARSHIPS
# =============================================================================

SPAIN_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Barcelona School of Economics (BSE) Master's Scholarships",
        country="Spain",
        degree_levels="Master's (Economics, Finance, Data Science –1-year programs)",
        funding_type="Partial to Full",
        deadline="Priority deadline 15 January (for full funding); later applicants considered for remaining funds",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities. Automatically considered upon admission. Merit-based. "
            "Named awards: Ramon Areces Foundation Scholarship, UniCredit Foundation Masterscholarship."
        ),
        coverage=["Tuition waivers of 25%, 50%, 75%, or 100%", "Limited fully-funded awards add living stipend", "~€550K awarded annually to ~24% of class"],
        official_source_url="https://bse.eu/masters-degrees/admissions",
        official_source="Barcelona School of Economics",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="IE University – Master's Awards & Scholarships",
        country="Spain",
        degree_levels="Master's / MBA across IE Business School, IE Law School, IE School of Politics Economics & Global Affairs, IE School of Science & Technology",
        funding_type="Partial",
        deadline="Rolling – automatic upon admission application; foundation scholarships have separate deadlines",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities can apply for IE Awards; named foundation scholarships are region-specific. "
            "Strong academic profile + financial need considered."
        ),
        coverage=["IE Awards cover 10–40% tuition", "Some country/regional scholarships offer 100% + living expenses"],
        official_source_url="https://www.ie.edu/financial-aid/masters/awardsandscholarships/",
        official_source="IE University / IE Foundation",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ESADE Talent Scholarships (MSc & MBA)",
        country="Spain",
        degree_levels="MSc, MBA (and BBA for undergraduate)",
        funding_type="Partial",
        deadline="Varies by program intake (typically rolling, with intake in September/January)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities. Demonstrated talent and financial need required. "
            "Separate scholarship application after admission."
        ),
        coverage=["Typically 25–50% of tuition", "Need-based and merit-based"],
        official_source_url="https://www.esade.edu/en/programs/scholarship-program-and-financial-aid",
        official_source="Esade Business School (Barcelona)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Barcelona (UB) Master's Degree+UB Scholarships",
        country="Spain",
        degree_levels="Master's (official master's programs at UB)",
        funding_type="Partial",
        deadline="Applications for 2026-2027 intake; check official page for current round",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to official master's programs at UB; merit-based."
        ),
        coverage=["Tuition reductions", "Limited stipends"],
        official_source_url="https://web.ub.edu/en/web/beques-graus-masters/beques-m%C3%A0ster-ub",
        official_source="University of Barcelona – Scholarships Unit",
        is_verified=True,
    ),
)

# =============================================================================
# SINGAPORE SCHOLARSHIPS
# =============================================================================

SINGAPORE_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="A*STAR Graduate Scholarship (AGS)",
        country="Singapore",
        degree_levels="PhD (at NUS, NTU, SMU, SUTD, or A*STAR Research Institutes)",
        funding_type="Fully Funded",
        deadline="Varies (typically twice a year — check official portal)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities; strong academic record in science/engineering/computing. "
            "Bangladesh is eligible as international student."
        ),
        coverage=["Full tuition", "Monthly stipend (SGD 4,550+ for international students)", "Allowances", "12-month overseas attachment"],
        official_source_url="https://www.a-star.edu.sg/scholarships/home/scholarships/ags--scholarship",
        official_source="Agency for Science, Technology & Research (A*STAR)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NUS Research Scholarship",
        country="Singapore",
        degree_levels="Master's (Research) / PhD",
        funding_type="Fully Funded",
        deadline="Aligns with intake admissions (August / January)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="All nationalities; apply via GradApp.",
        coverage=["Up to SGD 3,800/month", "Full tuition fee subsidy", "Airfare allowance"],
        official_source_url="https://nusgs.nus.edu.sg/scholarships/nus-research-scholarship/",
        official_source="National University of Singapore (NUS)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NUS Commonwealth Scholarship",
        country="Singapore",
        degree_levels="Master's (Research) / PhD",
        funding_type="Fully Funded",
        deadline="~Nov 2026 for Aug 2027 intake (verify official site)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of Commonwealth countries (Bangladesh is a Commonwealth member → eligible), "
            "min 2nd Upper Class Honours; eligible for MOE Subsidy."
        ),
        coverage=["SGD 3,000/month (PhD)", "SGD 2,900/month (Master's)", "Full tuition fee subsidy", "Additional SGD500/month post-QE"],
        official_source_url="https://nusgs.nus.edu.sg/scholarships/commonwealth-scholarship/",
        official_source="NUS Graduate School",
        is_verified=True,
        best_fit="Commonwealth citizens including Bangladeshi students",
    ),
    ScholarshipIngestionRecord(
        name="NUS President's Graduate Fellowship (PGF)",
        country="Singapore",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Aligns with PhD admission intake",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="All nationalities with outstanding research record.",
        coverage=["Up to SGD 4,800/month", "Full tuition", "Allowances"],
        official_source_url="https://nusgs.nus.edu.sg/scholarships/presidents-graduate-fellowship/",
        official_source="NUS Graduate School",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NUS International Undergraduate Scholarship",
        country="Singapore",
        degree_levels="Bachelor's (Freshmen)",
        funding_type="Fully Funded",
        deadline="Based on UG admission cycle (Feb–Mar for Aug intake); automatic consideration with admission application",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities except Singapore citizens (i.e., PRs and international students including Bangladesh)."
        ),
        coverage=["Tuition fee subsidy/waiver", "SGD allowance"],
        official_source_url="https://nus.edu.sg/oam/scholarships/scholarships-for-freshmen-international-students/nus-international-undergraduate-scholarship",
        official_source="National University of Singapore (Office of Admissions)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NTU Nanyang Global Scholarship",
        country="Singapore",
        degree_levels="Bachelor's (Freshmen)",
        funding_type="Fully Funded",
        deadline="~1 December for AY intake (check official page)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="All nationalities with outstanding academic and co-curricular records.",
        coverage=["Full subsidised tuition", "SGD 6,500/yr living", "SGD 2,000/yr accommodation", "SGD 8,000 travel grant", "SGD 2,000 computer allowance", "NTU Honours College enrolment"],
        official_source_url="https://www.ntu.edu.sg/admissions/undergraduate/scholarships/scholarship-opportunities/detail/nanyang-scholarship",
        official_source="Nanyang Technological University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NTU Nanyang President's Graduate Scholarship (NPGS)",
        country="Singapore",
        degree_levels="Master's (leading to PhD) / PhD",
        funding_type="Fully Funded",
        deadline="Varies by programme",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="Open to all nationalities; outstanding Bachelor's/Master's holders.",
        coverage=["Full tuition", "Monthly stipend", "Conference", "IT", "Thesis", "Journal allowances"],
        official_source_url="https://www.ntu.edu.sg/admissions/graduate/financialmatters/scholarships",
        official_source="Nanyang Technological University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="SMU Lee Kong Chian Scholars' Programme (LKCSP)",
        country="Singapore",
        degree_levels="Bachelor's",
        funding_type="Fully Funded",
        deadline="With UG admission (Jan–Mar)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High-calibre international freshmen; indicate interest in online admission application."
        ),
        coverage=["Full tuition fee waiver (after MOE grant, 4 years)", "SGD 5,000/yr living", "SGD 1,800 computer", "SGD 16,000 Global Opportunities grant (exchange, overseas projects)"],
        official_source_url="https://admissions.smu.edu.sg/scholarships/prospective-students/international-students",
        official_source="Singapore Management University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="SUTD President's Graduate Fellowship (PGF)",
        country="Singapore",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Varies by programme",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="All nationalities; up to 4 years duration.",
        coverage=["Full tuition", "Monthly stipend (SGD 3,600 international students)", "Conference funding", "Overseas research opportunities"],
        official_source_url="https://www.sutd.edu.sg/admissions/graduate/scholarship/sutd-graduate-fellowships-scholarships/",
        official_source="Singapore University of Technology and Design",
        is_verified=True,
    ),
)


# =============================================================================
# INDIA SCHOLARSHIPS
# =============================================================================

INDIA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Lata Mangeshkar Dance & Music Scholarship Scheme (ICCR)",
        country="India",
        degree_levels="UG, PG, PhD, Certificate, Diploma (in performing arts/culture)",
        funding_type="Fully Funded",
        deadline="AY 2026-27 closed (15 April 2026). Next cycle opens ~Feb 2027",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students pursuing Indian culture studies (dance, music, theatre, sculpture, Indian languages, cuisine); "
            "100 slots globally; Bangladesh got 38 slots in 2026-27; age 18-40 (UG/PG) or 50 (PhD)."
        ),
        coverage=["Tuition", "Monthly stipend", "HRA up to INR 6,500", "Airfare", "Thesis/dissertation allowance", "Contingent grant"],
        official_source_url="https://a2ascholarships.iccr.gov.in",
        official_source="Indian Council for Cultural Relations (ICCR)",
        is_verified=True,
        best_fit="Students pursuing Indian cultural studies including Bangladeshi applicants",
    ),
    ScholarshipIngestionRecord(
        name="QUAD STEM Scholarship Scheme (ICCR)",
        country="India",
        degree_levels="Bachelor's (4-year B.Tech/B.E. Engineering)",
        funding_type="Fully Funded",
        deadline="AY 2026-27 closed (15 April 2026). Next cycle opens ~Feb 2027",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from QUAD-partner countries pursuing STEM undergraduate engineering at 8 designated institutions: "
            "MNIT Jaipur, NIT Durgapur, NIT Trichy, NIT Warangal, DTU Delhi, CUSAT Kochi, Anna University Chennai, IIIT Delhi. "
            "Bangladesh is eligible — 3 Bangladeshi students received Quad Scholarship in 2026-27."
        ),
        coverage=["Return economy class airfare", "Tuition", "Monthly stipend", "HRA", "Medical insurance (Rs 5 lakh)"],
        official_source_url="https://a2ascholarships.iccr.gov.in/scheme/quad-stem-scholarship",
        official_source="Indian Council for Cultural Relations (ICCR)",
        is_verified=True,
        best_fit="Bangladeshi engineering students seeking fully funded undergraduate STEM education",
    ),
    ScholarshipIngestionRecord(
        name="Dr. S. Radhakrishnan Cultural Exchange Scholarship Scheme (ICCR)",
        country="India",
        degree_levels="UG, PG, PhD",
        funding_type="Fully Funded",
        deadline="AY 2026-27 closed (15 April 2026). Next cycle ~Feb 2027",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign students from countries with cultural exchange agreements; "
            "age 18-40 (UG/PG) or 50 (PhD). Fully funded without airfare."
        ),
        coverage=["Tuition", "Monthly stipend INR 18,000-22,000", "HRA", "Thesis allowance"],
        official_source_url="https://a2ascholarships.iccr.gov.in/scheme/radhakrishnan-cultural-exchange",
        official_source="Indian Council for Cultural Relations (ICCR)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="India Science and Research Fellowship (ISRF) — DST",
        country="India",
        degree_levels="Postdoctoral / Visiting Researcher (PhD/M.Tech/M.Sc/MBBS with 3-5 years research experience)",
        funding_type="Fully Funded",
        deadline="Annual call (varies — check INSA website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of Afghanistan, Bangladesh, Bhutan, Maldives, Myanmar, Nepal, Sri Lanka, Thailand; "
            "researchers at universities/research institutions; up to 80 fellowships annually (10 per country)."
        ),
        coverage=["Visiting fellowship 3-6 months", "International travel", "Accommodation", "Living expenses", "Research costs at premier Indian research institutions"],
        official_source_url="https://www.insaindia.res.in/",
        official_source="Department of Science & Technology (DST), Govt. of India, via INSA",
        is_verified=True,
        best_fit="Postdoctoral researchers from Bangladesh in science and technology",
    ),
    ScholarshipIngestionRecord(
        name="UGC Junior Research Fellowship (JRF) & Research Associateship (RA) for Foreign Nationals",
        country="India",
        degree_levels="M.Phil/PhD (JRF) and Postdoctoral (RA)",
        funding_type="Fully Funded",
        deadline="Annual call via Indian embassies abroad",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Students/teachers from developing countries of Asia (incl. Bangladesh), Africa, Latin America; "
            "Master's degree required; JRF: age ≤35 (M) / 40 (F); RA: age ≤40 (M) / 45 (F); 20 JRF + 7 RA slots annually."
        ),
        coverage=["JRF: INR 12,000-14,000/month + contingency INR 12,000-25,000/year + HRA", "RA: INR 16,000/month + INR 30,000 contingency", "Tenure 4 years (non-extendable)"],
        official_source_url="https://www.ugc.gov.in/",
        official_source="University Grants Commission (UGC), Govt. of India",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="TWAS-CSIR Postgraduate Fellowship Programme",
        country="India",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="AY 2026 cycle: 3 June 2026 (closed). Next: ~March 2027",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Nationals of developing countries (other than India); max age 35; Master's in S&T; "
            "must not hold Indian visa/residency; employed in home country with research assignment."
        ),
        coverage=["Tenable at 38 CSIR labs", "Up to 4 years", "Monthly stipend", "Accommodation", "Travel", "Research costs"],
        official_source_url="https://twas.org/opportunity/twas-csir-postgraduate-fellowship-programme",
        official_source="Council of Scientific & Industrial Research (CSIR) + UNESCO-TWAS",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Netaji Subhas – ICAR International Fellowship (NS-ICAR IF)",
        country="India",
        degree_levels="PhD (Agriculture & Allied Sciences)",
        funding_type="Fully Funded",
        deadline="Annual call (typically advertised in Indian national newspapers and on ICAR website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Overseas nationals including Bangladesh; Master's in agriculture/allied sciences with 65%+ marks; "
            "age ≤35; 30 fellowships total annually."
        ),
        coverage=["Tuition", "Stipend", "Accommodation", "Travel", "Research expenses at Indian Agricultural Universities"],
        official_source_url="https://www.icar.gov.in/",
        official_source="Indian Council of Agricultural Research (ICAR), Ministry of Agriculture",
        is_verified=True,
        best_fit="Bangladeshi students pursuing agricultural sciences PhD",
    ),
    ScholarshipIngestionRecord(
        name="IIT Kanpur Institute Fellowship (for international students)",
        country="India",
        degree_levels="M.Tech, MBA, M.Des, PhD",
        funding_type="Fully Funded",
        deadline="Autumn (MTech/MBA/PhD): 20 March – 15 April; Spring (PhD): 1 September – 31 October",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign nationals (non-Indian citizens or OCI/PIO); offered to those not receiving any other funding "
            "(ICCR/SII/AARDO/DIA). SAARC fee rates for Bangladesh."
        ),
        coverage=["Full tuition waiver (SAARC fee rates for Bangladesh)", "Monthly fellowship par with Indian students", "Hostel"],
        official_source_url="https://iitk.ac.in/oir/how-to-apply",
        official_source="Indian Institute of Technology Kanpur",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="IIT Hyderabad FIRST Fellowship (Fully-funded International Research Scholars in Technology)",
        country="India",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="January 2026 cycle closed (7 Nov 2025). Next: July 2026 intake (typically ~April)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign Nationals (excluding OCI/NRI); Bachelor's and Master's from foreign universities; "
            "min CGPA 8.0 in Master's in relevant engineering/tech disciplines."
        ),
        coverage=["Fellowship INR 60,000/month", "INR 1,00,000 annual contingency", "Tuition waiver", "5-year duration possible"],
        official_source_url="https://ir.iith.ac.in/first",
        official_source="Indian Institute of Technology Hyderabad (IITH)",
        is_verified=True,
        best_fit="High-achieving international PhD candidates in engineering/technology",
    ),
    ScholarshipIngestionRecord(
        name="KIIT University India Scholarship Program (KUISP)",
        country="India",
        degree_levels="UG, PG, PhD",
        funding_type="Partial to Fully Funded",
        deadline="AY 2025-26: 30 August 2025 (closed). AY 2026-27: ~31 August 2026 (estimated)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign nationals; up to 10 students recommended per country via Indian missions."
        ),
        coverage=["50-100% tuition fee waiver", "Free books", "Exam/registration fees", "Sports", "Internet", "Airport pickup", "Does NOT cover living expenses or airfare"],
        official_source_url="https://international.kiit.ac.in",
        official_source="Kalinga Institute of Industrial Technology (KIIT) Deemed-to-be University",
        is_verified=True,
    ),
)

# =============================================================================
# USA SCHOLARSHIPS
# =============================================================================

USA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Global Undergraduate Exchange Program (Global UGRAD)",
        country="USA",
        degree_levels="Undergraduate (one semester exchange)",
        funding_type="Fully Funded",
        deadline="Typically December-January annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Undergraduate students from UGRAD participating countries (including Bangladesh), "
            "18-25 years, demonstrated leadership potential."
        ),
        coverage=["Tuition", "Housing", "Meals", "Travel", "Small incidentals"],
        official_source_url="https://exchanges.state.gov/non-us/program/global-undergraduate-exchange-program-ugrad",
        official_source="U.S. Department of State, Bureau of Educational and Cultural Affairs",
        is_verified=True,
        best_fit="Bangladeshi undergraduate students for one-semester US exchange",
    ),
    ScholarshipIngestionRecord(
        name="Alan and Jane Handler Endowed Scholarship — University of Rochester",
        country="USA",
        degree_levels="Bachelor's (first-year)",
        funding_type="Fully Funded",
        deadline="December 1",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students with academic excellence, high financial need, leadership potential, resiliency."
        ),
        coverage=["Tuition", "Fees", "Housing", "Food", "Books", "Personal expenses", "Transportation", "$5,000 enrichment fund", "Mentoring"],
        official_source_url="https://admissions.rochester.edu/handler-scholarship/",
        official_source="University of Rochester",
        is_verified=True,
        best_fit="High-need, high-achieving international undergraduates",
    ),
    ScholarshipIngestionRecord(
        name="Berea College Tuition Promise Scholarship",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Fully Funded",
        deadline="October 15 (Early Action), January 15 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students with strong academic potential and financial need. "
            "ALL admitted international students receive 100% funding."
        ),
        coverage=["100% tuition", "Housing", "Food", "Fees for all enrolled students", "Work program provides additional earnings"],
        official_source_url="https://www.berea.edu/admissions/",
        official_source="Berea College",
        is_verified=True,
        best_fit="International students seeking fully funded undergraduate education",
    ),
    ScholarshipIngestionRecord(
        name="Karsh International Scholars Program — Duke University",
        country="USA",
        degree_levels="Bachelor's (first-year)",
        funding_type="Fully Funded",
        deadline="November 2 (Early Decision), January 4 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-U.S. citizens, no dual U.S. citizenship), first-time undergraduate, "
            "demonstrated financial need, strong academic preparation."
        ),
        coverage=["Full tuition", "Room and board", "Mandatory fees", "Demonstrated need beyond costs", "Three summers of research/internship funding"],
        official_source_url="https://ousf.duke.edu/merit-scholarships/karsh-international-scholars-program/",
        official_source="Duke University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Gabelli Presidential Scholars Program — Boston College",
        country="USA",
        degree_levels="Bachelor's (first-year)",
        funding_type="Full Tuition",
        deadline="November 1 (priority scholarship deadline)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students, outstanding academic achievement, leadership, community service."
        ),
        coverage=["Full tuition for four years", "Fully-funded summer programs (international travel, service learning, internships)"],
        official_source_url="https://www.bc.edu/bc-web/academics/sites/gabelli-presidential-scholars-program.html",
        official_source="Boston College",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Clark University Presidential Scholarship",
        country="USA",
        degree_levels="Bachelor's (first-year)",
        funding_type="Fully Funded",
        deadline="November 1 (Early Action), January 15 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="International students, exceptional academic achievement, leadership.",
        coverage=["Full tuition", "On-campus accommodation", "Meal plan for four years"],
        official_source_url="https://www.clarku.edu/financial-aid/types/scholarships",
        official_source="Clark University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Simmons University Kotzen Scholarship",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Fully Funded",
        deadline="December 1",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="International students, merit-based, academic excellence.",
        coverage=["Full tuition", "Housing", "$600/month stipend", "Annual return airfare", "Health insurance", "$1,000 book allowance", "Visa fee reimbursement"],
        official_source_url="https://www.simmons.edu/undergraduate-admission/kotzen-scholarship",
        official_source="Simmons University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Harvard University Financial Aid (International)",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Need-Based",
        deadline="February 1",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All students including international, need-blind admission. "
            "100% of demonstrated need met."
        ),
        coverage=["Families earning <$85,000 pay nothing", "Families <$200,000 pay reduced tuition"],
        official_source_url="https://college.harvard.edu/financial-aid/apply-financial-aid",
        official_source="Harvard University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Yale University Need-Based Financial Aid (International)",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Need-Based",
        deadline="November 1 (Early Action), February 15 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All students including international, need-blind admission. "
            "100% of demonstrated need met."
        ),
        coverage=["Families earning <$100,000 pay nothing", "Families <$200,000 get full-tuition scholarship"],
        official_source_url="https://admissions.yale.edu/affordability",
        official_source="Yale University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Princeton University Financial Aid (International)",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Need-Based",
        deadline="November 1 (Early Action), January 1 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All students including international, need-blind admission. "
            "100% of demonstrated need met, no loans."
        ),
        coverage=["Families earning <$65,000 pay nothing", "Families <$100,000 pay minimal amount"],
        official_source_url="https://admission.princeton.edu/apply/international-students",
        official_source="Princeton University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Brown University Financial Aid (International)",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Need-Based",
        deadline="November 1 (Early Decision), January 1 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All students including international (need-blind for Class of 2029+). "
            "100% of demonstrated need met, no loans."
        ),
        coverage=["Families earning <$60,000 pay nothing"],
        official_source_url="https://admission.brown.edu/tuition-aid/financial-aid/international-students",
        official_source="Brown University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Dartmouth College Financial Aid (International)",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Need-Based",
        deadline="November 1 (Early Decision), January 1 (Regular Decision)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All students including international, need-blind admission. "
            "100% of demonstrated need met, no loans."
        ),
        coverage=["Families earning <$125,000 pay no loans", "Families <$65,000 pay nothing"],
        official_source_url="https://admissions.dartmouth.edu/affordability/international-students",
        official_source="Dartmouth College",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Aga Khan Foundation International Scholarship Programme",
        country="USA",
        degree_levels="Master's, PhD (limited)",
        funding_type="50% Grant / 50% Loan",
        deadline="January-March (varies by country)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding students from select developing countries (including Bangladesh), "
            "no other means of financing."
        ),
        coverage=["Tuition and living expenses (50% grant, 50% zero-interest loan)"],
        official_source_url="https://akf.org/international-scholarship-programme/",
        official_source="Aga Khan Foundation",
        is_verified=True,
        best_fit="Graduate students from developing countries including Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="Rotary Peace Fellowships",
        country="USA",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="May (annual)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary="Demonstrated commitment to peace and development, leadership experience.",
        coverage=["Tuition", "Room", "Board", "Transportation", "Internship/field study expenses"],
        official_source_url="https://www.rotary.org/en/our-programs/peace-fellowships",
        official_source="Rotary International",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="#YouAreWelcomeHere Scholarship",
        country="USA",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="Varies by institution",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International first-year students, essay/video demonstrating intercultural exchange. "
            "57 participating U.S. universities."
        ),
        coverage=["Minimum 50% tuition at participating universities"],
        official_source_url="https://www.youarewelcomehereusa.org/",
        official_source="Various participating U.S. universities",
        is_verified=True,
    ),
)

# =============================================================================
# ITALY SCHOLARSHIPS
# =============================================================================

ITALY_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Invest Your Talent in Italy (IYT)",
        country="Italy",
        degree_levels="Master's Degree / Postgraduate",
        funding_type="Fully Funded",
        deadline="20 April 2026 – 11 May 2026 (18:00 Italian time)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to citizens of Bangladesh and 23 other partner countries who are permanently resident there. "
            "Applicants must hold a qualification valid for a Master's/Postgraduate degree and have been born on or after 1 January 2000. "
            "Must apply for pre-admission to a participating Italian university course."
        ),
        coverage=["€10,800 annual scholarship (paid quarterly)", "Full exemption from enrolment fees and university contributions", "Mandatory 3-month internship with an Italian company", "Italian language and culture course"],
        official_source_url="https://investyourtalentapplication.esteri.it/SITOIYT/EN/current-call",
        official_source="Ministry of Foreign Affairs (MAECI), ICE Agency, Uni-Italia",
        is_verified=True,
        best_fit="Bangladeshi students pursuing Master's degrees in Italy",
    ),
    ScholarshipIngestionRecord(
        name="University of Bologna — International Talents @Unibo",
        country="Italy",
        degree_levels="Master's Degree (Second Cycle / Laurea Magistrale)",
        funding_type="Partial to Full",
        deadline="30 May 2025 (for A.Y. 2025/26; check site for updated 2026/27 call)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-Italian qualification) enrolling for the first time in a Second Cycle degree programme. "
            "Must be under 30 years old and meet financial requirements (ISEE between €16,000 and €35,000 or equivalent). GRE test required."
        ),
        coverage=["€6,500 per academic year (gross)", "Full tuition fee waiver", "Renewable for a second academic year"],
        official_source_url="https://bandi.unibo.it/s/diri/bando-international-talents-unibo",
        official_source="Alma Mater Studiorum – Università di Bologna",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Politecnico di Milano — Merit Based International Scholarships",
        country="Italy",
        degree_levels="Master of Science (taught in English)",
        funding_type="Partial to Full",
        deadline="15 December 2025 (noon Italian time)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to the first year of an MSc programme in Engineering, Architecture, or Design. "
            "Must have applied during the Early Bird admission phase (1 Oct – 1 Dec 2025) and hold a valid English language certificate."
        ),
        coverage=["Full tuition fee waiver + cash allowance", "Platinum: €10,000/year", "Gold: €8,000/year", "Silver: tuition waiver only", "Renewable for the following academic year based on academic merit"],
        official_source_url="https://www.polimi.it/en/future-students/fees/scholarships/",
        official_source="Politecnico di Milano",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Padua — Padua International Excellence Scholarship",
        country="Italy",
        degree_levels="Bachelor's, Master's, Single-Cycle (English-taught only)",
        funding_type="Partial to Full",
        deadline="Aligned with each programme's admission call (typically November 2025 – May 2026 for 2026/27 intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Highly talented international students who do not hold Italian citizenship and do not reside in Italy. "
            "Must hold a non-Italian upper secondary diploma (Bachelor's/Single-Cycle) or non-Italian Bachelor's degree (Master's). "
            "No separate application; automatically considered when applying for an eligible English-taught degree."
        ),
        coverage=["€8,000 per academic year (gross, paid in two €4,000 instalments)", "Full tuition fee waiver", "Up to 3 years for Bachelor's/Single-Cycle, up to 2 years for Master's"],
        official_source_url="https://www.unipd.it/en/padua-international-excellence-scholarship-programme",
        official_source="Università degli Studi di Padova",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Trento — International Student Scholarships",
        country="Italy",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial to Full",
        deadline="Not announced / varies annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of non-EU countries living outside Italy, admitted to a degree programme at UniTrento. "
            "Must not be resident in Italy."
        ),
        coverage=["€7,200/year for non-STEM programmes", "€8,500/year for STEM programmes", "Full tuition fee exemption", "Maximum duration: 3 years (Bachelor's) or 2 years (Master's)"],
        official_source_url="https://www.unitn.it/en/study/fees-scholarships-accommodation/scholarships-and-awards/scholarships-international-students",
        official_source="Università degli Studi di Trento",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Milano-Bicocca — BISP (Bicocca International Scholarship Programme)",
        country="Italy",
        degree_levels="Bachelor's, Master's, Single-Cycle",
        funding_type="Partial to Full",
        deadline="Admission must be confirmed by 15 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students resident abroad holding a foreign qualification and admitted to an eligible programme. "
            "Must not possess Italian citizenship (except dual) and must not be resident in Italy."
        ),
        coverage=["€10,000 per academic year (gross)", "Exemption from tuition fees", "Renewable up to 3 years (Bachelor's/Single-Cycle) or 2 years (Master's)"],
        official_source_url="https://en.unimib.it/study/fees-and-scholarships/bisp-bicocca-international-scholarship-programme",
        official_source="Università degli Studi di Milano-Bicocca",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Bocconi University — ISU Bocconi Scholarship / Bocconi4Access to Education",
        country="Italy",
        degree_levels="Bachelor of Science, Integrated Master of Arts in Law, Master of Science",
        funding_type="Need-based (Partial to Full)",
        deadline="International rounds typically May–June 2026 (check portal for exact dates)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "First-year students (domestic and international) meeting economic and merit requirements defined by the Lombardy Region. "
            "ISEE/ISEEU Parificato must not exceed ~€26,888."
        ),
        coverage=["Full or partial tuition fee waiver", "Cash grant amount determined by ISEE", "100% full tuition waivers for international first-year Bachelor's/Law students through the same scheme"],
        official_source_url="https://www.unibocconi.it/en/applying-bocconi/bachelor-and-law-programs/funding/isu-bocconi-scholarship-first-year-students-ay-2026-27",
        official_source="Università Bocconi",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Turin — Talent 4 UniTo",
        country="Italy",
        degree_levels="Master's Degree (Postgraduate)",
        funding_type="Partial",
        deadline="Not specified in source (verify on portal for current cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students enrolling for the first year of a postgraduate degree programme without restricted access, taught in English. "
            "Open to students from all nationalities."
        ),
        coverage=["€20,000 total over two academic years (€10,000/year gross)"],
        official_source_url="https://en.unito.it/studying-unito/scholarships-international-students",
        official_source="Università degli Studi di Torino",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Turin — UNICORE 8.0 (University Corridors for Refugees)",
        country="Italy",
        degree_levels="Master's Degree (Postgraduate)",
        funding_type="Fully Funded",
        deadline="Not specified in source",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Specifically for international students who are refugees or beneficiaries of international protection from Bangladesh, "
            "Burkina Faso, Cameroon, Ethiopia, India, Kenya, Mozambique, Niger, Nigeria, South Africa, Uganda, Zambia, and Zimbabwe."
        ),
        coverage=["€7,000/year", "Service benefits (including accommodation and meals) for two years"],
        official_source_url="https://en.unito.it/studying-unito/scholarships-international-students/university-corridors-refugees-unicore-80",
        official_source="Università degli Studi di Torino",
        is_verified=True,
        best_fit="Refugee students from Bangladesh pursuing Master's degrees",
    ),
    ScholarshipIngestionRecord(
        name="University of Brescia — STAR Scholarships (Foundation Year + Bachelor's)",
        country="Italy",
        degree_levels="Foundation Year + Bachelor's Degree",
        funding_type="Fully Funded",
        deadline="15 March 2026 (12:00 Italian time)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens and residents of particularly poor or developing countries (including Bangladesh) or priority cooperation countries. "
            "Must be born in 2000 or later, first-time enrolment, and possess a valid secondary school diploma."
        ),
        coverage=["€6,132.10 + full tuition fee waiver for Foundation Year and Bachelor's", "Free accommodation in university residences"],
        official_source_url="https://www.unibs.it/en/study/fees-and-scholarships/scholarships-and-grants",
        official_source="Università degli Studi di Brescia",
        is_verified=True,
        best_fit="Bangladeshi students from developing country backgrounds",
    ),
    ScholarshipIngestionRecord(
        name="Sapienza University of Rome — PhD Scholarships",
        country="Italy",
        degree_levels="PhD (42nd Cycle, A.Y. 2026/2027)",
        funding_type="Fully Funded",
        deadline="1 June 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities. Must hold a second-cycle degree (or equivalent foreign degree) by 31 October 2026 "
            "and not have previously benefited from a PhD scholarship in Italy."
        ),
        coverage=["€16,243/year (gross of student withholdings)", "Increased by 50% for authorised study/research periods abroad (up to 12 months)", "10% research budget"],
        official_source_url="https://www.uniroma1.it/en/study/phd/phd-programmes",
        official_source="Sapienza Università di Roma",
        is_verified=True,
    ),
)


# =============================================================================
# TAIWAN SCHOLARSHIPS
# =============================================================================

TAIWAN_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="MOFA Taiwan Scholarship",
        country="Taiwan",
        degree_levels="Bachelor's, Master's, PhD, plus Pre-degree Mandarin Language Enrichment Program (LEP)",
        funding_type="Partial",
        deadline="February 1 – March 31, 2026 (apply through local ROC embassy/TECO)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign nationals with high school diploma or above, excellent academic record, good character. "
            "NOT an ROC national or overseas compatriot. In principle for nationals of Taiwan's diplomatic allies, "
            "but special consideration may be given to others. Bangladesh does not have diplomatic relations with Taiwan, "
            "so Bangladeshi students are eligible only under 'special consideration'."
        ),
        coverage=["Monthly stipend of NT$33,000 for degree programs (NT$28,000 for LEP)", "One-way economy-class airfare", "Universities may offer reduced tuition"],
        official_source_url="https://en.mofa.gov.tw/cp.aspx?n=1325",
        official_source="Ministry of Foreign Affairs (MOFA), ROC (Taiwan)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="MOE Huayu Enrichment Scholarship (HES)",
        country="Taiwan",
        degree_levels="Mandarin language programs (2, 3, 6, 9, or 12 months)",
        funding_type="Partial",
        deadline="February 1 – March 31, 2026 (apply via local Taiwan representative office)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign nationals aged 18+, secondary school graduate or higher, good academic record, good character. "
            "NOT an ROC national or overseas Chinese student."
        ),
        coverage=["Monthly stipend of NT$25,000"],
        official_source_url="https://english.moe.gov.tw/cp-24-16833-23C09-1.html",
        official_source="Ministry of Education (MOE), Taiwan",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Taiwan International Graduate Program (TIGP) – Academia Sinica",
        country="Taiwan",
        degree_levels="PhD only (14 English-taught sub-programs)",
        funding_type="Fully Funded",
        deadline="November 1, 2025 – February 1, 2026 (for Fall 2026 admission)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to all international students (no nationality restriction; Bangladesh eligible). "
            "Bachelor's or Master's degree required."
        ),
        coverage=["Monthly stipend (approx. NT$40,000+)", "Tuition waiver", "Travel allowance", "Programs in Chemical Biology, Molecular Science, Nano Science, Biodiversity, AI of Things, Earth System Science, etc."],
        official_source_url="https://tigp.sinica.edu.tw/",
        official_source="Academia Sinica in collaboration with partner universities (NTU, NTHU, NYCU, NCKU, etc.)",
        is_verified=True,
        best_fit="International PhD candidates in science and technology",
    ),
    ScholarshipIngestionRecord(
        name="INTENSE Program (International Industrial Talents Education Special Program)",
        country="Taiwan",
        degree_levels="Master's and PhD",
        funding_type="Fully Funded",
        deadline="Varies by university (NTU 2026: closed April 15, 2026)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to participating universities' Master's/PhD programs. "
            "Cannot hold another Taiwan government scholarship concurrently. "
            "Obligation: must work in Taiwan for the partner company for 1–2 years post-graduation."
        ),
        coverage=["One-time administrative grant", "One-way airfare", "Tuition/misc fees (capped NT$50,000/semester, NT$100,000/year)", "Monthly living allowance from partner companies (ASUS, MediaTek, Realtek, etc.)"],
        official_source_url="https://gocfs.ntu.edu.tw/",
        official_source="Ministry of Education + National Development Fund + Partner Companies",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NTU International Outstanding Graduate Student Scholarship",
        country="Taiwan",
        degree_levels="Master's and PhD",
        funding_type="Partial",
        deadline="April 23 – May 15, 2026 (current students)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Current international graduate students at NTU (Master's year ≤2; PhD year ≤4); recommended by advisor."
        ),
        coverage=["Tuition waiver up to NT$100,000", "Monthly stipend (Master: NT$8,000; PhD: NT$10,000–15,000 depending on college)"],
        official_source_url="https://oia.ntu.edu.tw/en/current-students/international-degree-and-dual-degree-students-wpwq/scholarships-6v27",
        official_source="National Taiwan University (NTU)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NTHU International Student Scholarship",
        country="Taiwan",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial to Fully Funded",
        deadline="New students apply during admission; current students late June (Fall) or late January (Spring)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students applying under MOE Regulations; PhD priority; "
            "not allowed to hold other Taiwan government scholarships simultaneously."
        ),
        coverage=["Type A (Full): Tuition/credit fee waiver + monthly stipend (PhD: NT$10,000–40,000; Master's/Bachelor's: NT$5,000)", "Type B: Tuition/credit fee waiver only"],
        official_source_url="https://apply.nthu.edu.tw/en/article/102-nthu-scholarship",
        official_source="National Tsing Hua University (NTHU)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="NYCU Elite Ph.D. Scholarship for New Students Award",
        country="Taiwan",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Typically Dec 20 – Mar 15 (for Fall entry)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New PhD students with outstanding grades who have not received Taiwan government scholarships/grants; "
            "or students in direct PhD pursuit program. One student per college (in principle)."
        ),
        coverage=["NT$33,000/month", "Full waiver of tuition and credit fees"],
        official_source_url="https://oia-scholarship.nycu.edu.tw/",
        official_source="National Yang Ming Chiao Tung University (NYCU)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="MOE Elite Scholarship for University Lecturers from South & Southeast Asia",
        country="Taiwan",
        degree_levels="Master's and PhD",
        funding_type="Fully Funded",
        deadline="Mid-December 2025 – mid-March 2026 (for Fall 2026 admission)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students who are currently university lecturers/professors in eligible South/Southeast Asian countries "
            "(incl. Bangladesh, India, Pakistan, Nepal, Sri Lanka, Bhutan, Indonesia, Philippines, Vietnam, Malaysia, etc.). "
            "Must submit up-to-date Lecturer Certificate."
        ),
        coverage=["NTD 300,000/year (approx.)", "Disbursed as NT$25,000/month (used partly for tuition/credit fees, remainder as stipend)"],
        official_source_url="https://oia.ncku.edu.tw/",
        official_source="Ministry of Education (MOE), Taiwan",
        is_verified=True,
        best_fit="Bangladeshi university lecturers/professors seeking Master's/PhD",
    ),
)


# =============================================================================
# SWITZERLAND SCHOLARSHIPS
# =============================================================================

SWITZERLAND_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="University of Geneva Excellence Master Fellowships (Faculty of Science)",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="28 February annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students pursuing a Master of Science in astronomy, biology, chemistry, biochemistry, "
            "computer science, mathematics, physics, pharmaceutical sciences, Earth sciences, environmental sciences, or bioinformatics. "
            "Must meet Master's admission criteria."
        ),
        coverage=["CHF 10,000–15,000 per year", "Awarded for one year and extendable for the full duration of the Master's (3–4 semesters) upon academic success"],
        official_source_url="https://www.unige.ch/sciences/en/enseignements/formations/masters/excellencemasterfellowships",
        official_source="University of Geneva",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UNIL Master's Scholarship — University of Lausanne",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 November annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students who have graduated from a foreign university with very high academic results. "
            "Must hold a foreign degree equivalent to a Swiss Bachelor's."
        ),
        coverage=["CHF 1,600/month for ~10 months (Sept–July)", "Exemption from course registration fees (only CHF 80/semester remains)", "Guaranteed student housing via FMEL"],
        official_source_url="https://www.unil.ch/unil/en/home/menuinst/etudier/mobilite-et-echange/etudiantes-et-etudiants-internationaux/etudiantes-internationaux-reguliers/bourse-de-master.html",
        official_source="University of Lausanne (UNIL)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of St.Gallen (HSG) Excellence Scholarships for Bachelor Students",
        country="Switzerland",
        degree_levels="Bachelor's",
        funding_type="Full Tuition",
        deadline="Varies (typically after admission)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign students enrolled in Bachelor studies at HSG, awarded on the basis of merit."
        ),
        coverage=["Full tuition fee coverage for 6 semesters (current value ~CHF 6,252/year)"],
        official_source_url="https://www.unisg.ch/en/studying/orientation/advice-and-support/financing-your-studies/hsg-funds-and-excellence-scholarships/",
        official_source="University of St.Gallen (HSG)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Starr International Foundation Scholarship — University of St.Gallen",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="Varies (annual cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Talented students with a recognised foreign Bachelor's degree completing an English-language HSG Master's programme "
            "(SIM, MiQE/F, MIA, MBF, MSC, MEcon, MIL, MAccFin)."
        ),
        coverage=["CHF 20,000 per programme", "Awarded annually", "Self-applications and HSG nominations accepted"],
        official_source_url="https://www.unisg.ch/en/studying/orientation/advice-and-support/financing-your-studies/hsg-funds-and-excellence-scholarships/starr-international-foundation-scholarship",
        official_source="University of St.Gallen (HSG)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Alfred Werner Scholarship Programme — Swiss Chemical Society",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Partial (One-time)",
        deadline="Not announced (annual cycle; check official page)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Highly talented international students who obtained their BSc from a university outside Switzerland "
            "and wish to pursue an MSc in Chemistry, Biochemistry, or Pharmaceutical Sciences at a Swiss University "
            "or Swiss Federal Institute of Technology. Must be in top 10% of undergraduate program."
        ),
        coverage=["CHF 36,000 as a one-time contribution toward a two-year Master's program", "Includes mentorship, industrial visits, and free access to Swiss Chemical Society activities"],
        official_source_url="https://foundation.scg.ch/scholarships/werner-scholarship",
        official_source="Swiss Chemical Society (SCS) Foundation",
        is_verified=True,
        best_fit="Chemistry/Biochemistry/Pharmaceutical Sciences students in top 10% of class",
    ),
    ScholarshipIngestionRecord(
        name="CERN Doctoral Student Programme",
        country="Switzerland",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Rolling (recent call for 2026)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "PhD students from CERN Member or Associate Member States enrolled or about to enroll in a doctoral programme. "
            "Fields: Applied Physics, Engineering, Computing."
        ),
        coverage=["Monthly allowance of CHF 3,891 (net of tax)", "Travel allowance", "Health insurance", "Family supplement if applicable", "Up to 36 months"],
        official_source_url="https://careers.cern/programmes/doctoral-studentship/",
        official_source="CERN",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="CERN Research Fellowship",
        country="Switzerland",
        degree_levels="Postdoctoral",
        funding_type="Fully Funded",
        deadline="Rolling",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Recent PhD graduates in physics and engineering (typically ≤3–6 years post-PhD experience)."
        ),
        coverage=["Competitive stipend sufficient for living expenses in Geneva", "24–36 months", "Access to world-leading research facilities"],
        official_source_url="https://careers.cern/programmes/research-fellowship",
        official_source="CERN",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="IMD MBA Scholarships",
        country="Switzerland",
        degree_levels="MBA",
        funding_type="Partial to Significant",
        deadline="Varies (aligned with MBA admissions)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to the IMD MBA program. Merit scholarships and need-based bursaries; non-cumulative."
        ),
        coverage=["Merit scholarships and need-based awards up to significant amounts (reported up to CHF 85,000 in some cycles)", "Exact amount determined by Admissions Committee"],
        official_source_url="https://www.imd.org/degree/mba/financing/imd-mba-scholarships/",
        official_source="IMD Business School",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Basel Financial Aid and Scholarships",
        country="Switzerland",
        degree_levels="Bachelor's / Master's",
        funding_type="Partial",
        deadline="Varies",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at University of Basel. Must apply for admission first; separate scholarship application required."
        ),
        coverage=["Study abroad grants up to CHF 5,000/year", "Solidarity funds (Solifonds) CHF 1,000–2,000/year", "Health/accident fund refunds for uninsured expenses"],
        official_source_url="https://www.unibas.ch/en/Studies/Advice-and-Support/Funding/Scholarships.html",
        official_source="University of Basel",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="WIPO Fellowship Program",
        country="Switzerland",
        degree_levels="Fellowship (Graduate/Professional)",
        funding_type="Fully Funded",
        deadline="Rolling (specific vacancies announced periodically)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Graduates and young professionals worldwide; no age limit; strong English proficiency; "
            "relevant background in IP, law, economics, translation, technology, or research."
        ),
        coverage=["CHF 6,000/month stipend", "Round-trip travel", "Medical & accident insurance", "Visa support", "12–36 months in Geneva"],
        official_source_url="https://www.wipo.int/en/web/working-at-wipo/fellowship-program",
        official_source="World Intellectual Property Organization (WIPO)",
        is_verified=True,
    ),
)


# =============================================================================
# AUSTRIA SCHOLARSHIPS
# =============================================================================

AUSTRIA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="University of Vienna Scholarships for International Students",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies (typically March-May for winter semester)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students enrolled at the University of Vienna. Various scholarships available "
            "based on academic merit and financial need."
        ),
        coverage=["Tuition fee waiver", "Monthly stipend varies", "Travel allowance in some cases"],
        official_source_url="https://studieren.univie.ac.at/en/scholarships/",
        official_source="University of Vienna",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="TU Wien Scholarships for International Students",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies (check official website for current calls)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at TU Wien (Vienna University of Technology). Merit-based scholarships "
            "for outstanding academic achievement."
        ),
        coverage=["Tuition fee reduction", "Monthly stipend varies"],
        official_source_url="https://www.tuwien.at/en/studies/scholarships",
        official_source="TU Wien (Vienna University of Technology)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Graz Scholarships for International Students",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies (typically March-June)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at the University of Graz. Merit-based scholarships "
            "for outstanding international students."
        ),
        coverage=["Tuition fee waiver", "Monthly stipend varies"],
        official_source_url="https://www.uni-graz.at/en/studies/scholarships/",
        official_source="University of Graz",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Innsbruck Scholarships for International Students",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies (typically March-May)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at the University of Inksbruck. Various scholarships available "
            "based on academic merit."
        ),
        coverage=["Tuition fee reduction", "Monthly stipend varies"],
        official_source_url="https://www.uibk.ac.at/en/studies/scholarships/",
        official_source="University of Innsbruck",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Johannes Kepler University Linz (JKU) Scholarships",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies (check official website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at JKU Linz. Merit-based scholarships for outstanding international students."
        ),
        coverage=["Tuition fee waiver", "Monthly stipend varies"],
        official_source_url="https://www.jku.at/en/studies/scholarships/",
        official_source="Johannes Kepler University Linz",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Austrian Database for Scholarships (OeAD) — Additional Programs",
        country="Austria",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial to Full",
        deadline="Varies by program",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Various scholarship programs for international students in Austria listed in the OeAD database. "
            "Includes programs from different Austrian institutions and organizations."
        ),
        coverage=["Varies by program"],
        official_source_url="https://grants.oead.at/en/",
        official_source="OeAD (Austrian Agency for Education and Internationalisation)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Austria-based",
        country="Austria",
        degree_levels="Master's (2 years, joint degree, 2+ EU countries including Austria)",
        funding_type="Fully Funded",
        deadline="Varies by consortium (typically October–January)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Worldwide (including Bangladesh). Apply to the consortium of the specific EMJMD programme "
            "with Austrian partner institutions."
        ),
        coverage=["Full tuition", "€1,400/month living allowance", "Travel", "Insurance", "Installation allowance"],
        official_source_url="https://www.eacea.ec.europa.eu/scholarships/emjmd-catalogue_en",
        official_source="European Commission (EACEA)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="CEU Scholarships (Central European University) — Vienna",
        country="Austria",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Typically January-February for Fall intake",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at CEU Vienna. Merit-based full scholarships covering tuition and living expenses."
        ),
        coverage=["Full tuition waiver", "Monthly stipend", "Health insurance", "Housing support"],
        official_source_url="https://www.ceu.edu/scholarships",
        official_source="Central European University (CEU) — Vienna",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Webster University Vienna Scholarships",
        country="Austria",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="Varies (rolling admissions)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at Webster University Vienna. Merit-based scholarships "
            "for outstanding academic achievement."
        ),
        coverage=["Tuition reduction (varies by scholarship)", "Up to 50% tuition waiver"],
        official_source_url="https://www.webster.ac.at/scholarships/",
        official_source="Webster University Vienna",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Modul University Vienna Scholarships",
        country="Austria",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="Varies (check official website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students at Modul University Vienna. Merit-based scholarships "
            "for outstanding international students."
        ),
        coverage=["Tuition reduction", "Monthly stipend varies"],
        official_source_url="https://www.modul.ac.at/scholarships",
        official_source="Modul University Vienna",
        is_verified=True,
    ),
)


# =============================================================================
# ADDITIONAL AUSTRIA SCHOLARSHIPS (Phase 2)
# =============================================================================

AUSTRIA_SCHOLARSHIPS_PHASE2 = (
    ScholarshipIngestionRecord(
        name="TU Graz 100 / TU Graz High Potentials",
        country="Austria",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial to Full",
        deadline="05 May – 07 July 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to international students ('Austria and abroad'); merit-based selection."
        ),
        coverage=["Up to €8,800 for Bachelor's students", "Up to €17,600 for Master's students", "Networking with partner companies"],
        official_source_url="https://www.tugraz.at/en/studying-and-teaching/studying-at-tu-graz/prospective-students/financial-matters/scholarships-for-students/scholarships-tu-graz-100",
        official_source="TU Graz",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="One World Scholarship Programme",
        country="Austria",
        degree_levels="Master's, PhD",
        funding_type="Partial",
        deadline="01 June – 15 July 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of Global South countries (Bangladesh explicitly listed); admitted to regular Master's or PhD program "
            "at a public university or UAS in Salzburg or Tyrol; age limit 30/35 (mothers 35/40); financial need; interest in sustainability/social justice."
        ),
        coverage=["€500 per month during semester (October–June)", "Personal mentoring", "Workshops", "Field trips", "Global alumni network"],
        official_source_url="https://aai-salzburg.at/en/studies/one-world-scholarship",
        official_source="Afro-Asiatisches Institut Salzburg (funded by Diocese of Salzburg)",
        is_verified=True,
        best_fit="Bangladeshi students from Global South studying in Salzburg/Tyrol",
    ),
    ScholarshipIngestionRecord(
        name="University of Innsbruck Doctoral Scholarship",
        country="Austria",
        degree_levels="PhD",
        funding_type="Partial",
        deadline="Application periods vary annually (typically August–October)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All doctoral students enrolled as regular students at the University of Innsbruck with registered dissertation; excellent academic record."
        ),
        coverage=["€1,120 per month for a maximum of 24 months (with possible interruptions)", "Interim review after 6 months"],
        official_source_url="https://www.uibk.ac.at/en/research/research-funding/phd/doctoral-scholarship/",
        official_source="University of Innsbruck",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ISTA PhD Program",
        country="Austria",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="08 January 2026 (for September 2026 start)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students with Bachelor's or Master's in Astronomy, Biology, Computer Science, Chemistry & Materials, "
            "Data Science, Earth Science, Mathematics, Neuroscience, or Physics."
        ),
        coverage=["5-year employment contracts", "Internationally competitive salaries", "Full social security coverage", "No tuition fees", "Fully funded until thesis defense"],
        official_source_url="https://phd.ista.ac.at/at-a-glance/",
        official_source="Institute of Science and Technology Austria",
        is_verified=True,
        best_fit="International PhD candidates in natural sciences and mathematics",
    ),
    ScholarshipIngestionRecord(
        name="AITHYRA-CeMM Joint International PhD Call",
        country="Austria",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="30 January 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International candidates holding (or expecting) a Master's/Bachelor's in medicine, biology, chemistry, bioinformatics, "
            "computer science, engineering, physics, mathematics, or related fields."
        ),
        coverage=["15–20 fully funded positions", "Minimum gross monthly salary EUR 2,779.60 (14 times/year)", "Covers all research costs, university fees, work-related travel expenses for 4 years", "Full health/accident/retirement insurance"],
        official_source_url="https://cemm.at/",
        official_source="CeMM (Austrian Academy of Sciences) & AITHYRA",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Helmut Veith Stipendium",
        country="Austria",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="Annual (specific date varies; check TU Wien website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Female students pursuing an English-taught Master's in Computer Science at TU Wien; solid mathematical/technical background."
        ),
        coverage=["€7,000 per year", "Waiver of tuition fees at TU Wien"],
        official_source_url="https://www.tuwien.at/en/studies/studying-at-tu-wien/study-grants/helmut-veith-stipendium",
        official_source="TU Wien",
        is_verified=True,
        best_fit="Female students in Computer Science at TU Wien",
    ),
    ScholarshipIngestionRecord(
        name="FWF ESPRIT Career Program",
        country="Austria",
        degree_levels="Postdoc (R2)",
        funding_type="Fully Funded",
        deadline="Varies (check FWF website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Highly qualified early-stage postdoc researchers from all disciplines; open to international researchers; "
            "project to be carried out at Austrian university/research institution."
        ),
        coverage=["Principal investigator's salary for three years"],
        official_source_url="https://www.fwf.ac.at/en/funding/funding-portfolio/fwf-espriT/",
        official_source="Austrian Science Fund (FWF)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="FWF ASTRA Awards",
        country="Austria",
        degree_levels="Advanced Postdoc (R3)",
        funding_type="Fully Funded",
        deadline="Varies (check FWF website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Internationally visible advanced postdocs from all disciplines (including arts-based research) with experience in independent research; "
            "open to international researchers."
        ),
        coverage=["Minimum €500,000 to maximum €1,000,000 for five years"],
        official_source_url="https://www.fwf.ac.at/en/funding/funding-portfolio/fwf-astra/",
        official_source="Austrian Science Fund (FWF)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="FWF Doctoral Programs DK",
        country="Austria",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Varies (positions advertised individually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Doctoral students at Austrian universities; open to international researchers; programs funded by FWF DocFunds."
        ),
        coverage=["Up to €1,960 per month for a period of 4 years", "Renewable twice upon favorable reviews"],
        official_source_url="https://www.fwf.ac.at/en/funding/funding-portfolio/doctoral-programmes/",
        official_source="Austrian Science Fund (FWF)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Johann Wilhelm Ritter von Mannagetta Foundation Fellowships",
        country="Austria",
        degree_levels="PhD",
        funding_type="Partial",
        deadline="20 October 2026 (next deadline)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Young, highly qualified doctoral candidates pursuing doctoral studies at an Austrian university in humanities, social sciences, cultural studies, or medicine; "
            "started doctoral studies no more than three years ago; need approximately 12 months to complete thesis."
        ),
        coverage=["€25,000 (super gross) for 12 months", "Intended to cover living expenses"],
        official_source_url="https://stipendien.oeaw.ac.at/en/fellowships/mannagetta",
        official_source="Johann Wilhelm Ritter von Mannagetta Foundation (Austrian Academy of Sciences)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Vienna VDS CoBeNe uni:docs PhD Call 2026",
        country="Austria",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="02 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International candidates for Social Sciences, Humanities, and Cultural Studies; compelling doctoral project idea; "
            "Master's degree completed or expected."
        ),
        coverage=["At least 40 fully funded pre-doctoral positions", "4 years, 30 hours/week", "Collective bargaining agreement (§48 VwGr. B1)"],
        official_source_url="https://careers.univie.ac.at/en/praedoc/praedoc-ssh",
        official_source="University of Vienna",
        is_verified=True,
    ),
)


# =============================================================================
# NETHERLANDS SCHOLARSHIPS
# =============================================================================

NETHERLANDS_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Holland Scholarship",
        country="Netherlands",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="1 February or 1 May (varies by institution)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from outside the EEA (including Bangladesh) who want to pursue "
            "a Bachelor's or Master's degree at a Dutch research university or university of applied sciences. "
            "This is a one-time scholarship for the first year of study."
        ),
        coverage=["€5,000 (one-time payment for the first year of study)"],
        official_source_url="https://www.studyinnl.org/finances/holland-scholarship",
        official_source="Nuffic (Netherlands Organisation for Internationalisation in Education)",
        is_verified=True,
        best_fit="Non-EEA students starting Bachelor's or Master's in the Netherlands",
    ),
    ScholarshipIngestionRecord(
        name="University of Amsterdam (UvA) Merit Scholarship",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="15 January (varies by faculty)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students from outside the EU applying for a Master's programme at UvA. "
            "Automatically considered upon admission application."
        ),
        coverage=["Tuition fee waiver", "Living expenses contribution (varies by programme)"],
        official_source_url="https://www.uva.nl/en/education/scholarships-financial-support/uva-merit-scholarship.html",
        official_source="University of Amsterdam",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Delft University of Technology (TU Delft) Justus & Louise van Effen Scholarship",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="1 December (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students from all countries applying for a Master's programme at TU Delft. "
            "Excellent academic record required."
        ),
        coverage=["Full tuition fees", "Monthly living expenses"],
        official_source_url="https://www.tudelft.nl/education/scholarships/justus-louise-van-effen-scholarship",
        official_source="Delft University of Technology",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Erasmus University Rotterdam (EUR) — Holland Scholarship & Talent Programmes",
        country="Netherlands",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="1 May (varies by programme)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from outside the EEA applying to Erasmus University Rotterdam. "
            "Various merit-based scholarships available."
        ),
        coverage=["Tuition fee reduction", "Living expenses contribution (varies)"],
        official_source_url="https://www.eur.nl/en/education/scholarships",
        official_source="Erasmus University Rotterdam",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Leiden University Excellence Scholarship (LExS)",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 October (for February intake) / 1 April (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding non-EEA students pursuing a Master's degree at Leiden University. "
            "Must have achieved excellent academic results during prior education."
        ),
        coverage=["10,000 EUR tuition fee waiver", "15,000 EUR tuition fee waiver", "Total tuition fee waiver (3 levels available)"],
        official_source_url="https://www.universiteitleiden.nl/en/scholarships/leiden-university-excellence-scholarship",
        official_source="Leiden University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Groningen Holland Scholarship & Talent Grant",
        country="Netherlands",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from outside the EEA applying to University of Groningen. "
            "Merit-based scholarships for outstanding academic achievement."
        ),
        coverage=["Holland Scholarship: €5,000 (first year only)", "Talent Grant: tuition fee waiver for outstanding students"],
        official_source_url="https://www.rug.nl/education/scholarships-and-financial-aid/",
        official_source="University of Groningen",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Utrecht University Excellence Scholarships",
        country="Netherlands",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students from outside the EU/EEA applying to Utrecht University. "
            "Excellent academic record and motivation required."
        ),
        coverage=["Tuition fee waiver", "Living allowance (varies by scholarship)"],
        official_source_url="https://www.uu.nl/en/organisation/scholarships-and-grants/utrecht-university-excellence-scholarships",
        official_source="Utrecht University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Radboud University Scholarship Programme",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="1 March (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Talented prospective international students from outside the EU/EEA applying for a Master's programme at Radboud University. "
            "Must have achieved excellent academic results."
        ),
        coverage=["Full tuition fee waiver", "Living allowance contribution", "Visa fees", "Health insurance"],
        official_source_url="https://www.ru.nl/en/education/scholarships/radboud-university-scholarship-programme",
        official_source="Radboud University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Maastricht University Holland High Potential Scholarship",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EEA students applying for a Master's programme at Maastricht University. "
            "Must have excellent academic record and strong motivation."
        ),
        coverage=["Holland Scholarship: €5,000", "UM High Potential Scholarship: tuition fee waiver + living expenses + health insurance + visa costs"],
        official_source_url="https://www.maastrichtuniversity.nl/scholarships",
        official_source="Maastricht University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Twente Scholarship (UTS)",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Excellent students from EU/EEA and non-EEA countries applying for a Master's programme at University of Twente. "
            "Must have been admitted to a qualifying Master's programme."
        ),
        coverage=["€3,000 – €22,000 for one year", "Second year continuation possible for 2-year programmes"],
        official_source_url="https://www.utwente.nl/en/education/scholarships-financial-aid/university-of-twente-scholarship/",
        official_source="University of Twente",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Vrije Universiteit Amsterdam (VU) Fellowship Programme",
        country="Netherlands",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Students with a nationality from outside the EU/EEA applying for a Master's programme at VU Amsterdam. "
            "Excellent academic record and motivation required. Automatically considered upon admission."
        ),
        coverage=["Tuition fee waiver (full or partial)", "Living allowance contribution (varies)"],
        official_source_url="https://vu.nl/en/deducation/scholarships/vu-fellowship-programme",
        official_source="Vrije Universiteit Amsterdam",
        is_verified=True,
    ),
)


# =============================================================================
# SWEDEN SCHOLARSHIPS
# =============================================================================

SWEDEN_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Lund University Global Scholarship",
        country="Sweden",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying to Lund University. Merit-based scholarship "
            "for outstanding academic achievement. Covers 25% to 100% of tuition fees."
        ),
        coverage=["25%, 50%, 75%, or 100% tuition fee waiver"],
        official_source_url="https://www.lunduniversity.lu.se/admissions/scholarships-and-awards/lund-university-global-scholarship",
        official_source="Lund University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Uppsala University Scholarship Programme",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Uppsala University. "
            "Merit-based scholarship covering full tuition fees."
        ),
        coverage=["100% tuition fee waiver"],
        official_source_url="https://www.uu.se/en/admissions/scholarships",
        official_source="Uppsala University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="KTH Royal Institute of Technology — KTH Scholarship",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at KTH. Merit-based scholarship "
            "covering full tuition fees."
        ),
        coverage=["100% tuition fee waiver for the full 2-year programme"],
        official_source_url="https://www.kth.se/en/utbildning/scholarships",
        official_source="KTH Royal Institute of Technology",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Chalmers University of Technology — IPOET Scholarship",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Chalmers. "
            "Merit-based scholarship covering 75% of tuition fees."
        ),
        coverage=["75% tuition fee waiver for the full 2-year programme"],
        official_source_url="https://www.chalmers.se/en/education/fees-finance/scholarships/",
        official_source="Chalmers University of Technology",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Stockholm University Scholarship Scheme",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Stockholm University. "
            "Merit-based scholarship covering full tuition fees."
        ),
        coverage=["100% tuition fee waiver"],
        official_source_url="https://www.su.se/english/education/scholarships-and-fees",
        official_source="Stockholm University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Linköping University Scholarship for Master's Students",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="Late January to early February (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Linköping University. "
            "Merit-based scholarship covering 25% to 100% of tuition fees."
        ),
        coverage=["25%, 50%, 75%, or 100% tuition fee waiver"],
        official_source_url="https://liu.se/en/education/scholarships",
        official_source="Linköping University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Umeå University Scholarship for International Students",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Umeå University. "
            "Merit-based scholarship covering 25% to 100% of tuition fees."
        ),
        coverage=["25%, 50%, 75%, or 100% tuition fee waiver"],
        official_source_url="https://www.umu.se/en/education/scholarships/",
        official_source="Umeå University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Karolinska Institutet — Global Master's Scholarship",
        country="Sweden",
        degree_levels="Master's (Health and Life Sciences)",
        funding_type="Partial",
        deadline="15 January (for September intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying for a Master's programme at Karolinska Institutet. "
            "Merit-based scholarship covering full tuition fees."
        ),
        coverage=["100% tuition fee waiver"],
        official_source_url="https://education.ki.se/scholarships",
        official_source="Karolinska Institutet",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Swedish Institute Scholarships for Global Professionals (SISGP)",
        country="Sweden",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="February (varies by year)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of selected developing countries including Bangladesh. "
            "Must have work experience and leadership potential. For Master's programmes in Sweden."
        ),
        coverage=["Tuition fees", "Living expenses (~SEK 11,000/month)", "Travel costs", "Insurance", "Grant for thesis"],
        official_source_url="https://si.se/en/apply/scholarships/swedish-institute-scholarships-for-global-professionals/",
        official_source="Swedish Institute",
        is_verified=True,
        best_fit="Bangladeshi professionals with work experience seeking Master's in Sweden",
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Sweden-based",
        country="Sweden",
        degree_levels="Master's (2 years, joint degree, 2+ EU countries including Sweden)",
        funding_type="Fully Funded",
        deadline="Varies by consortium (typically October–January)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Worldwide (including Bangladesh). Apply to the consortium of the specific EMJMD programme "
            "with Swedish partner institutions."
        ),
        coverage=["Full tuition", "€1,400/month living allowance", "Travel", "Insurance", "Installation allowance"],
        official_source_url="https://www.eacea.ec.europa.eu/scholarships/emjmd-catalogue_en/sweden",
        official_source="European Commission (EACEA)",
        is_verified=True,
    ),
)


# =============================================================================
# AUSTRALIA SCHOLARSHIPS
# =============================================================================

AUSTRALIA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Adelaide Academic Excellence Scholarship (50%)",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Partial (50% tuition fee reduction)",
        deadline="Varies by intake (August 2026 for 2027 entry)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-Australian/NZ citizens). ATAR 99+ for UG, GPA 6.7+/7.0 for PG. "
            "Must maintain GPA 5.5/7.0. Bangladesh is an eligible nationality."
        ),
        coverage=["50% off tuition fees for standard duration"],
        official_source_url="https://adelaide.edu.au/study/scholarships/int/adelaide-academic-excellence-scholarship-50/",
        official_source="University of Adelaide",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UQ International Excellence Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework, min 16 units)",
        funding_type="Partial (25% tuition fee reduction per annum)",
        deadline="Automatic consideration with admission",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students commencing in 2026. Competitive academic score. Cannot hold another UQ scholarship."
        ),
        coverage=["25% off tuition fees for program duration"],
        official_source_url="https://scholarships.uq.edu.au/scholarship/uq-international-excellence-scholarship",
        official_source="University of Queensland",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Melbourne Research Scholarship (MRS)",
        country="Australia",
        degree_levels="Master's by Research, PhD",
        funding_type="Fully Funded (stipend + fee offset + OSHC)",
        deadline="October round (Semester 1), March round (Semester 2)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High-achieving domestic and international students. Academic merit + research potential."
        ),
        coverage=["Full tuition offset", "$39,500/year stipend", "OSHC", "$3,000 relocation"],
        official_source_url="https://scholarships.unimelb.edu.au/awards/melbourne-research-scholarship",
        official_source="University of Melbourne",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ANU University Research Scholarship",
        country="Australia",
        degree_levels="Master's by Research, PhD",
        funding_type="Fully Funded (stipend + fee offset)",
        deadline="Round 1 International - August 31; Round 2 International - varies",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Domestic/international HDR students. Honours H1 or equivalent. Not Industry PhD with full salary."
        ),
        coverage=["Stipend for 3.5 years (PhD) or 1.5 years (MPhil)", "Travel/thesis/dependent allowances"],
        official_source_url="https://study.anu.edu.au/scholarships/find-scholarship/anu-university-research-scholarships",
        official_source="Australian National University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Sydney International Scholarship (USydIS)",
        country="Australia",
        degree_levels="Master's by Research, PhD",
        funding_type="Fully Funded (stipend + full tuition)",
        deadline="September 11, 2026 (RP1-2); December 18, 2026 (RP3-4)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students. WAM 80+ (First Class Honours equivalent). Research proposal + supervisor support."
        ),
        coverage=["AUD $42,754/year stipend (2026 rate)", "Full tuition", "Relocation", "Thesis allowance"],
        official_source_url="https://www.sydney.edu.au/scholarships/international/postgraduate-research.html",
        official_source="University of Sydney",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Deakin Vice-Chancellor's International Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Full or Partial (100% or 50% tuition)",
        deadline="Apply at least 1 month before course start (rolling basis)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students with 85%+ average. Personal statement + 2 references. Bangladesh eligible."
        ),
        coverage=["100% or 50% tuition fee reduction", "VCPEP program", "Priority accommodation"],
        official_source_url="https://www.deakin.edu.au/study/fees-and-scholarships/scholarships/find-a-scholarship/deakin-vice-chancellors-international-scholarship",
        official_source="Deakin University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Deakin International Vice-Chancellor's Scholarship 100% (South Asia)",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Full tuition (100%)",
        deadline="Rolling (apply 1+ month before start)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "South Asian citizens (Bangladesh, Bhutan, Mauritius, Myanmar, Nepal). Residing in South Asia. "
            "Applying via Deakin agent. 85%+ in Year 12/undergraduate."
        ),
        coverage=["100% tuition fee reduction"],
        official_source_url="https://www.deakin.edu.au/study/fees-and-scholarships/scholarships/find-a-scholarship/international-vice-chancellors-scholarship-100-south-asia",
        official_source="Deakin University",
        is_verified=True,
        best_fit="South Asian students including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="UTS Vice-Chancellor's International Undergraduate Scholarship",
        country="Australia",
        degree_levels="Bachelor's",
        funding_type="Full tuition",
        deadline="March 16 - April 13, 2026 (Spring session 2026)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students. Australian Year 12 or equivalent. 85%+ average. Commitment to excellence/innovation/social justice."
        ),
        coverage=["Full tuition fees for standard course duration"],
        official_source_url="https://www.uts.edu.au/for-students/admissions-entry/scholarships/scholarships-search/uts-vice-chancellors-international-undergraduate-scholarship",
        official_source="University of Technology Sydney",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="QUT International Merit Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (all faculties)",
        funding_type="Partial (25% tuition per semester)",
        deadline="Automatic consideration",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students. Academic entry requirements met. GCE A Levels 10+ points, IB 32+."
        ),
        coverage=["25% off tuition fees per semester"],
        official_source_url="https://www.qut.edu.au/study/fees-and-scholarships/scholarships/international-merit-scholarship",
        official_source="Queensland University of Technology",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="RMIT Future Leaders Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (eligible programs)",
        funding_type="Partial (20% tuition reduction)",
        deadline="Automatic consideration",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from India and subcontinent (Bangladesh eligible). 70% average or ATAR 75."
        ),
        coverage=["20% off tuition fees for program duration"],
        official_source_url="https://www.rmit.edu.au/scholarships/international-scholarships",
        official_source="RMIT University",
        is_verified=True,
        best_fit="South Asian students including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="Flinders International Postgraduate Research Scholarship (FIPRS)",
        country="Australia",
        degree_levels="Master's by Research, PhD",
        funding_type="Fully Funded (tuition + stipend)",
        deadline="Varies (check Flinders website)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-AU/NZ citizens). Commencing HDR in Australia for first time. "
            "Academic merit + research potential."
        ),
        coverage=["Full international tuition offset", "$37,000/year tax-free stipend for up to 3.5 years"],
        official_source_url="https://www.flinders.edu.au/scholarships/flinders-university-international-research-scholarship",
        official_source="Flinders University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Macquarie International Research Training Program (iRTP)",
        country="Australia",
        degree_levels="Master of Research, PhD",
        funding_type="Fully Funded (tuition + stipend)",
        deadline="June 15 - July 31, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-AU/NZ). Full-time MRes/PhD Session 1 2027. Confirmed supervision."
        ),
        coverage=["Tuition fee offset", "$40,900/year stipend (2026 rate)", "Travel concession"],
        official_source_url="https://www.mq.edu.au/research/phd-and-research-degrees/how-to-apply/scholarship-opportunities/scholarship-search/international-scholarship-round",
        official_source="Macquarie University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="UNSW International Scientia Coursework Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Full or Partial (Full tuition or $20,000/year)",
        deadline="December 1, 2025 - February 26, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students commencing Term 2, 2026. Offer of admission by Feb 26, 2026."
        ),
        coverage=["Full tuition OR $20,000/year toward tuition"],
        official_source_url="https://scholarships.online.unsw.edu.au/scholarship/unsw-international-scientia-coursework-scholarship",
        official_source="UNSW Sydney",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Western Australian Premier's University Scholarship 2026",
        country="Australia",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial ($50,000 toward tuition)",
        deadline="Round 7 (Semester 2, 2026): March 3 - May 29, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from Bangladesh, Bhutan, Brazil, China, Colombia, Hong Kong, India, Indonesia, Japan, Kenya, "
            "Malaysia, Nepal, Oman, Philippines, South Korea, Saudi Arabia, Singapore, Sri Lanka, UAE, UK, Vietnam. "
            "Must have ATAR 95+ or equivalent. Minimum 2-year program at Curtin, ECU, Murdoch, Notre Dame (Fremantle), or UWA."
        ),
        coverage=["$50,000 AUD applied to tuition fees"],
        official_source_url="https://www.wa.gov.au/service/education-and-training/education-and-training-careers/western-australian-premiers-university-scholarship",
        official_source="Western Australian Government",
        is_verified=True,
        best_fit="International students including Bangladeshi nationals for WA universities",
    ),
    ScholarshipIngestionRecord(
        name="La Trobe High Achiever Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Partial (15%-25% tuition reduction)",
        deadline="December 31, 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-AU/NZ). New offers from Feb 10, 2026. "
            "Commencing Term 4/Semester 2 2026+. WAM 60+ (15-20%) or 75+ (25%)."
        ),
        coverage=["15-25% off tuition fees based on academic merit"],
        official_source_url="https://www.latrobe.edu.au/study/scholarships/other/la-trobe-high-achiever-scholarship",
        official_source="La Trobe University",
        is_verified=True,
    ),
)


# =============================================================================
# SOUTH KOREA SCHOLARSHIPS
# =============================================================================

SOUTH_KOREA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Seoul National University (SNU) President Fellowship Program (SPF)",
        country="South Korea",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="During admission period for international students every semester",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Faculty members of major universities in developing countries without a PhD degree; "
            "newly admitted to SNU as PhD student. Priority given to faculty from major universities in Asia, Africa, South America. "
            "Approximately 8 recipients per semester."
        ),
        coverage=["Full tuition exemption for maximum 6 semesters", "Living expenses: 1,500,000 - 2,000,000 KRW per month for 3-4 years", "Round-trip airfare (economy class)", "Korean language training (evening classes)", "National Health Insurance fee reimbursement"],
        official_source_url="https://en.snu.ac.kr/admission/graduate/scholarships/before_application",
        official_source="Seoul National University",
        is_verified=True,
        best_fit="Faculty members from developing country universities including Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="Seoul National University Graduate Scholarship for Excellent Foreign Students (GSFS)",
        country="South Korea",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="During admission period for international students every semester",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-Korean applicants from eligible countries accepted into SNU; must apply to designated college/school participating in GSFS Program. "
            "Approximately 20 recipients."
        ),
        coverage=["Full tuition exemption for maximum 4 semesters", "Living expenses: minimum 500,000 KRW per month (varies by major)"],
        official_source_url="https://en.snu.ac.kr/admission/graduate/scholarships/gsfs",
        official_source="Seoul National University",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="KAIST International Student Scholarship (Undergraduate)",
        country="South Korea",
        degree_levels="Bachelor's",
        funding_type="Fully Funded",
        deadline="Same as admission application (no separate scholarship application)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International applicants admitted to KAIST undergraduate programs; open to all nationalities; non-Korean citizenship required. "
            "94% of all admitted international students receive this scholarship automatically. Must maintain GPA over 2.7 out of 4.3 after freshman year."
        ),
        coverage=["Full tuition fee exemption for 8 semesters", "Monthly living expenses: 350,000 KRW per month", "Medical health insurance"],
        official_source_url="https://admission.kaist.ac.kr/intl-undergraduate/support/scholarships/kaist",
        official_source="Korea Advanced Institute of Science and Technology (KAIST)",
        is_verified=True,
        best_fit="STEM undergraduate students including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="KAIST Global Presidential Scholarship (KGPS) - Graduate",
        country="South Korea",
        degree_levels="Master's, Master's-PhD Integrated",
        funding_type="Fully Funded",
        deadline="Spring/Fall Early/Fall Regular admission cycles",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International applicants for KAIST graduate programs; highly competitive selection by department head. "
            "All departments except Global Technology Innovation Program (GDI-GTIP Track)."
        ),
        coverage=["Full tuition coverage", "Monthly stipend: 1,000,000 KRW for 4 regular semesters", "National health insurance included"],
        official_source_url="https://admission.kaist.ac.kr/intl-graduate/FinancialSupport/Scholarship/KAISTScholarship",
        official_source="Korea Advanced Institute of Science and Technology (KAIST)",
        is_verified=True,
        best_fit="STEM graduate students including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="KAIST Prestige Scholarship for International PhD Students (KPS)",
        country="South Korea",
        degree_levels="Master's-PhD Integrated, PhD",
        funding_type="Fully Funded",
        deadline="Spring/Fall Early/Fall Regular",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International applicants for PhD or integrated programs; outstanding academic and research achievements. All departments."
        ),
        coverage=["Full tuition coverage", "Monthly stipend: 300,000 KRW for 8 regular semesters (starts at PhD stage for integrated students)"],
        official_source_url="https://admission.kaist.ac.kr/intl-graduate/FinancialSupport/Scholarship/KPrestige",
        official_source="Korea Advanced Institute of Science and Technology (KAIST)",
        is_verified=True,
        best_fit="PhD researchers including Bangladeshi nationals",
    ),
    ScholarshipIngestionRecord(
        name="Yonsei University Underwood International College (UIC) Admissions Scholarship",
        country="South Korea",
        degree_levels="Bachelor's (Undergraduate)",
        funding_type="Full Tuition",
        deadline="Automatic consideration during admission evaluation (no separate application)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Newly-admitted international students to UIC; selected based on academic credentials. "
            "Must maintain required GPA each semester. Does NOT include monthly living expenses, accommodation, airfare, or health insurance."
        ),
        coverage=["Full tuition for 4 years (8 semesters)", "Automatic consideration during admission evaluation"],
        official_source_url="https://uic.yonsei.ac.kr/main/admission.php?mid=m04_03_02",
        official_source="Yonsei University (Underwood International College)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Yonsei University International Student Companion Scholarship",
        country="South Korea",
        degree_levels="Master's, PhD, Integrated Master's-PhD",
        funding_type="Partial (Stipend)",
        deadline="No separate application; automatic consideration for eligible students",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Full-time international students enrolled through international student admission track at Yonsei Graduate School. "
            "Not available to students in Medicine, Dentistry, Nursing, or contract-based programs. "
            "Not available to those already receiving full tuition scholarships."
        ),
        coverage=["Master's Program: KRW 2,000,000 per semester", "Doctoral Program: KRW 3,000,000 per semester", "Integrated Program: KRW 2,000,000 per semester", "Duration: 4 semesters for Master's/PhD, 6 semesters for integrated programs"],
        official_source_url="https://graduate.yonsei.ac.kr/graduate_en/academic/scholarship02.do",
        official_source="Yonsei University (Graduate School)",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="KOICA Scholarship Program (Korea International Cooperation Agency)",
        country="South Korea",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Around July 31 annually (varies by receiving institution)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Government officials and public sector employees from KOICA partner developing countries. "
            "Must receive official nomination from their government. Age preferably under 40. Must hold Bachelor's degree for Master's programs."
        ),
        coverage=["Full tuition fees", "Airfare (round-trip)", "Accommodation", "Monthly Allowance: 1,200,000 KRW per month", "Insurance: approximately 81,000 KRW per month", "Settlement Allowance: 600,000 KRW (Master's) / 1,200,000 KRW (PhD)", "Scholarship completion grants"],
        official_source_url="https://www.koica.go.kr/eng",
        official_source="Korea International Cooperation Agency (KOICA) - Korean Government",
        is_verified=True,
        best_fit="Government officials and public sector employees from Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="GIST (Gwangju Institute of Science and Technology) Government-Sponsored Scholarship",
        country="South Korea",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies (check GIST website for current calls)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students admitted to GIST through government sponsorship programs. "
            "GIST provides automatic funding packages to admitted international graduate students including full tuition waiver, monthly stipend, and health insurance."
        ),
        coverage=["Government support: 140,000 KRW/month (Master's, max 4 semesters)", "Teaching assistant benefit: 295,000 KRW/month (Doctoral, max 8 semesters)", "Meal support: 100,000 KRW/month", "Living expense support: 120,000 KRW/month"],
        official_source_url="https://www.gist.ac.kr/en/html/sub05/05020601.html",
        official_source="Gwangju Institute of Science and Technology (GIST)",
        is_verified=True,
        best_fit="Science and engineering researchers including Bangladeshi nationals",
    ),
)

# =============================================================================
# GERMANY SCHOLARSHIPS
# =============================================================================

GERMANY_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="DAAD Research Grants - Doctoral Candidates and Young Academics",
        country="Germany",
        degree_levels="PhD, Postdoc",
        funding_type="Fully Funded",
        deadline="21 October 2026 (selection approx. February 2027, funding from May 2027)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Doctoral candidates and young academics from Bangladesh and other developing countries. "
            "Doctorate funding available for 2-12 months; postdoc funding for 2-6 months. "
            "Must be registered for PhD no more than 3 years ago at time of application. "
            "Cannot have resided in Germany longer than 15 months at application deadline."
        ),
        coverage=["Monthly stipend: €1,300 (PhD)", "Travel allowance", "Health/accident/personal liability insurance", "Language course funding", "Research allowance"],
        official_source_url="https://www.daad-bangladesh.org/en/studying-in-germany/phd-studies/research-grants-in-germany-for-phd-scholars/",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="PhD candidates and postdocs from Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="DAAD University Summer Courses Scholarship",
        country="Germany",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="30 October annually (applications open from 01 September)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Undergraduate and graduate students taking Bachelor's and Master's degree courses in all subjects "
            "wishing to improve German proficiency and cultural knowledge. "
            "Must have completed at least two years of study by the time of application. "
            "B1 German language level required at time of application."
        ),
        coverage=["Course fees", "Accommodation", "Travel costs (partial)", "Health insurance"],
        official_source_url="https://www.daad-bangladesh.org/en/studying-in-germany/daad-scholarships/",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Students wanting German language and cultural immersion",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Helmut-Schmidt-Programme (Public Policy and Good Governance)",
        country="Germany",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="July annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Future leaders from developing countries (including Bangladesh) in fields of public policy, "
            "public administration, governance, and development cooperation. "
            "Min. GPA equivalent to German 2.5. Bachelor's degree completed within last 6 years. "
            "Work experience in related field is an advantage."
        ),
        coverage=["Monthly stipend: €992", "Health/accident/personal liability insurance", "Travel allowance", "Language course", "Study allowance"],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50018884",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Future leaders in public policy and governance from Bangladesh",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Postgraduate Studies in the Field of Architecture",
        country="Germany",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="September annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Graduates in architecture from Bangladesh and other developing countries. "
            "Min. GPA equivalent to German 2.5. Bachelor's degree completed within last 6 years. "
            "Language requirements as specified by the respective study programme."
        ),
        coverage=["Monthly stipend: €992", "Health/accident insurance", "Travel allowance", "Language course", "Study allowance"],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135744",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Bangladeshi architecture graduates pursuing Master's in Germany",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Postgraduate Studies in the Fields of Fine Art, Design, Visual Communication and Film",
        country="Germany",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="November annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Graduates in fine arts, design, visual communication, or film from developing countries. "
            "Min. GPA equivalent to German 2.5. Bachelor's degree completed within last 6 years. "
            "Portfolio typically required."
        ),
        coverage=["Monthly stipend: €992", "Health/accident insurance", "Travel allowance", "Language course", "Study allowance"],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135742",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Bangladeshi arts and design graduates pursuing Master's in Germany",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Postgraduate Studies in the Field of Music",
        country="Germany",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="September annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Graduates in music from developing countries. "
            "Min. GPA equivalent to German 2.5. Bachelor's degree completed within last 6 years. "
            "Language requirements as specified by the respective study programme."
        ),
        coverage=["Monthly stipend: €992", "Health/accident insurance", "Travel allowance", "Language course", "Study allowance"],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57135743",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Bangladeshi music graduates pursuing Master's in Germany",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Postgraduate Studies in the Field of Performing Arts",
        country="Germany",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="October annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Graduates in performing arts (theatre, dance, etc.) from developing countries. "
            "Min. GPA equivalent to German 2.5. Bachelor's degree completed within last 6 years."
        ),
        coverage=["Monthly stipend: €992", "Health/accident insurance", "Travel allowance", "Language course", "Study allowance"],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50109971",
        official_source="DAAD (German Academic Exchange Service)",
        is_verified=True,
        best_fit="Bangladeshi performing arts graduates pursuing Master's in Germany",
    ),
    ScholarshipIngestionRecord(
        name="Heinrich Böll Foundation Scholarship",
        country="Germany",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="01 March and 01 September annually",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students and PhD candidates from DAC (Development Assistance Committee) countries "
            "(including Bangladesh) pursuing Master's or PhD at state-recognised German universities. "
            "Priority for applicants from developing countries who have not yet taken up residence in Germany. "
            "German language proficiency required: at least B2 level or DSH1. "
            "Must demonstrate social commitment and interest in green policy values."
        ),
        coverage=["Master's: up to €992/month + €100 mobility allowance", "PhD: up to €1,400/month + €100 mobility allowance", "Health insurance allowance", "Family/childcare allowances"],
        official_source_url="https://www.boell.de/en/scholarships",
        official_source="Heinrich Böll Foundation",
        is_verified=True,
        best_fit="Bangladeshi students committed to green policy, democracy, and social justice",
    ),
)

# =============================================================================
# JAPAN SCHOLARSHIPS
# =============================================================================

JAPAN_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="MEXT Scholarship for Undergraduate Students",
        country="Japan",
        degree_levels="Bachelor's",
        funding_type="Fully Funded",
        deadline="Varies by Japanese embassy (typically April-May annually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High school graduates born on or after April 2, 2001 (for 2026). "
            "Applicants must be from countries with diplomatic relations with Japan. "
            "Age: 17-25 years. Applicants must have completed 12 years of schooling. "
            "Application through Japanese embassy or consulate in home country."
        ),
        coverage=["Monthly stipend: 117,000 yen", "Tuition fees waived", "Round-trip airfare", "University admission fees"],
        official_source_url="https://www.mext.go.jp/en/policy/education/highered/title02/detail02/sdetail02/1373897.htm",
        official_source="MEXT (Ministry of Education, Culture, Sports, Science and Technology)",
        is_verified=True,
        best_fit="Bangladeshi high school graduates pursuing undergraduate studies in Japan",
    ),
    ScholarshipIngestionRecord(
        name="MEXT Scholarship for Research Students (University Recommendation)",
        country="Japan",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies by university (typically January-March for October intake)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students with outstanding academic achievements applying through Japanese university recommendation. "
            "Research Students born on or after April 2, 1991. Must have Bachelor's degree for Master's, "
            "or Master's degree for PhD. GPA of 2.30 or above required. "
            "Japanese language proficiency N2 or English CEFR B2 required."
        ),
        coverage=["Monthly stipend: 143,000-145,000 yen (depending on course)", "Tuition fees waived", "Round-trip airfare", "6-month preparatory Japanese language training if needed"],
        official_source_url="https://www.mext.go.jp/content/20251205-mxt_kotokoku01-000046164_2.pdf",
        official_source="MEXT (Ministry of Education, Culture, Sports, Science and Technology)",
        is_verified=True,
        best_fit="Outstanding Bangladeshi graduate students recommended by Japanese universities",
    ),
    ScholarshipIngestionRecord(
        name="MEXT Scholarship for Japanese Studies Students",
        country="Japan",
        degree_levels="Undergraduate (Japanese Studies)",
        funding_type="Fully Funded",
        deadline="Varies by Japanese embassy (typically February-March annually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Undergraduate students majoring in Japanese language or Japanese culture at foreign universities. "
            "Must have studied Japanese Studies for at least one year as of September 1 of application year. "
            "Age: born between April 2, 1996 and April 1, 2008. "
            "Must have Japanese language ability sufficient for university education in Japan. "
            "One-year programme starting September or October."
        ),
        coverage=["Monthly stipend: 117,000 yen", "Tuition fees waived", "Round-trip airfare", "One-year duration"],
        official_source_url="https://www.mext.go.jp/content/20251222-mxt_kotokoku01-000046488_02.pdf",
        official_source="MEXT (Ministry of Education, Culture, Sports, Science and Technology)",
        is_verified=True,
        best_fit="Bangladeshi undergraduates majoring in Japanese language or culture",
    ),
    ScholarshipIngestionRecord(
        name="MEXT Young Leaders Program (YLP) Scholarship",
        country="Japan",
        degree_levels="Master's (Public Administration/Policy)",
        funding_type="Fully Funded",
        deadline="Varies by Japanese embassy (typically August-October annually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Future leaders from developing countries in public administration, law, healthcare administration, "
            "or local governance. Bachelor's degree required. Age: under 40 at time of admission. "
            "Must have 3-5 years of professional experience in relevant field. "
            "English proficiency typically required (TOEFL/IELTS)."
        ),
        coverage=["Monthly stipend: 242,000 yen", "Tuition fees waived", "Round-trip airfare", "1-year Master's programme"],
        official_source_url="https://www.studyinjapan.go.jp/en/planning/scholarships/about-scholarships/",
        official_source="MEXT (Ministry of Education, Culture, Sports, Science and Technology)",
        is_verified=True,
        best_fit="Bangladeshi mid-career professionals in public administration or policy",
    ),
    ScholarshipIngestionRecord(
        name="JASSO Reservation Program for Monbukagakusho Honors Scholarship by Pre-arrival Admission",
        country="Japan",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial (Stipend)",
        deadline="Through university (before enrollment)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Privately-financed international students with excellent EJU scores who received pre-arrival admission "
            "from a Japanese university, graduate school, junior college, or college of technology. "
            "Must be enrolled as full-time student with 'Student' residence status. "
            "GPA of 2.30 or above required. Average monthly remittances must be less than 90,000 yen. "
            "Must not receive other government scholarships concurrently."
        ),
        coverage=["48,000 yen per month for graduate/undergraduate", "30,000 yen per month for Japanese language institutions", "Duration: 12 months (April enrollment) or 6 months (September/October enrollment)"],
        official_source_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/shoreihi/yoyaku_tonichimae.html",
        official_source="JASSO (Japan Student Services Organization)",
        is_verified=True,
        best_fit="Privately-financed Bangladeshi students with strong EJU scores",
    ),
    ScholarshipIngestionRecord(
        name="Kyushu University International Scholarship",
        country="Japan",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies (check Kyushu University admissions)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Outstanding international students admitted to graduate programs at Kyushu University. "
            "Selection based on academic merit. Open to all nationalities. "
            "Must not be receiving other full scholarships."
        ),
        coverage=["Tuition fee waiver", "Monthly stipend (amount varies)", "Admission fee exemption"],
        official_source_url="https://www.kyushu-u.ac.jp/en/admission/financial_aid/scholarship/",
        official_source="Kyushu University",
        is_verified=True,
        best_fit="International graduate students admitted to Kyushu University",
    ),
)

# =============================================================================
# CHINA SCHOLARSHIPS
# =============================================================================

CHINA_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Chinese Government Scholarship - Bilateral Program (Type A)",
        country="China",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies by country (typically January-April 2026)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-Chinese citizens in good health. Age limits: under 25 for Bachelor's, under 35 for Master's, "
            "under 40 for PhD, under 45 for general scholar, under 50 for senior scholar. "
            "Bachelor's applicants must have high school diploma and take CSCA exam. "
            "Chinese-taught programs require HSK Level 4 (Master's/PhD) or HSK Level 3 (general/senior scholar). "
            "English-taught programs require IELTS 6.0+ or TOEFL 80+. "
            "Apply through Chinese embassy in home country."
        ),
        coverage=["Full tuition waiver", "Free on-campus accommodation", "Monthly stipend: CNY 2,500 (Bachelor's) / CNY 3,000 (Master's) / CNY 3,500 (PhD)", "Comprehensive medical insurance"],
        official_source_url="https://ee.china-embassy.gov.cn/eng/tzygg/202511/t20251108_11749274.htm",
        official_source="China Scholarship Council (CSC)",
        is_verified=True,
        best_fit="Bangladeshi students applying through Chinese embassy bilateral agreement",
    ),
    ScholarshipIngestionRecord(
        name="MOFCOM Scholarship-CSC Program",
        country="China",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies (applications open until 06 June 2026)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Young and middle-aged talents from developing countries. Must be citizen of developing country "
            "under age 45 (born after September 1, 1981). Must have at least 3 years working experience. "
            "Master's applicants: Bachelor's degree holder. PhD applicants: Master's degree holder. "
            "Must be public officials of division level above, senior management, or academic backbones. "
            "English-taught programs required. Must not be studying in China at time of application."
        ),
        coverage=["Full tuition", "Free on-campus accommodation", "Monthly stipend: Master's CNY 3,000 / PhD CNY 3,500", "Resettlement fee: CNY 3,000", "Round-trip international airfare", "Annual home visit airfare (up to n-1 times)", "Medical insurance"],
        official_source_url="https://sl.china-embassy.gov.cn/eng/xwdt/202604/P020260403009201102513.pdf",
        official_source="Ministry of Commerce of China (MOFCOM) & China Scholarship Council (CSC)",
        is_verified=True,
        best_fit="Bangladeshi government officials and professionals in public administration",
    ),
    ScholarshipIngestionRecord(
        name="Chinese Government Scholarship - Tsinghua University Program (Type B)",
        country="China",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Mid-December 2025 for September 2026 enrollment (varies by department)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-Chinese citizens applying directly to Tsinghua University. "
            "Bachelor's degree holder under 35 for Master's; Master's degree holder under 40 for PhD. "
            "Must have pre-admission from Tsinghua University school/department. "
            "Chinese-taught programs require HSK Level 4. "
            "Must not have other Chinese government scholarships or nominations."
        ),
        coverage=["Full tuition waiver", "Free university dormitory or accommodation subsidy", "Monthly stipend: CNY 3,000 (Master's) / CNY 3,500 (PhD)", "Comprehensive medical insurance"],
        official_source_url="https://yz.tsinghua.edu.cn/en/info/1027/1117.htm",
        official_source="Tsinghua University & China Scholarship Council (CSC)",
        is_verified=True,
        best_fit="Outstanding Bangladeshi students admitted to Tsinghua graduate programs",
    ),
    ScholarshipIngestionRecord(
        name="UCAS Chinese Government Scholarship (University of Chinese Academy of Sciences)",
        country="China",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="31 January 2026 (Beijing Time)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-Chinese citizens in good health, friendly to China, abiding by Chinese laws. "
            "Master's: Bachelor's degree holder, no more than 35 years old. "
            "PhD: Master's degree holder, no more than 40 years old. "
            "Proficient in English or Mandarin. Must not have accepted other sponsorship. "
            "Must study full-time at UCAS research institute. Agency Number: 80001."
        ),
        coverage=["Master's: tuition RMB 30,000/year waived", "PhD: tuition RMB 40,000/year waived", "Monthly stipend: Master's RMB 3,000 / PhD RMB 5,000", "Application fee waived"],
        official_source_url="https://english.ucas.ac.cn/index.php/admission/international-students/financial-aid/6656-call-for-2026-chinese-government-scholarship-for-international-students-to-study-at-ucas",
        official_source="University of Chinese Academy of Sciences (UCAS) & China Scholarship Council (CSC)",
        is_verified=True,
        best_fit="Research-oriented Bangladeshi students in science and engineering",
    ),
    ScholarshipIngestionRecord(
        name="Nankai University Chinese Government Scholarship - Silk Road Program",
        country="China",
        degree_levels="Bachelor's, Master's",
        funding_type="Fully Funded",
        deadline="18 May 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Students from Belt and Road countries (including Bangladesh for some programs). "
            "Business Economics, Business Administration, Finance (Bachelor's); "
            "International Business, International Affairs and Public Policy (Master's). "
            "Non-Chinese citizens, good health, meet Nankai University admission requirements. "
            "Master's applicants: IELTS 6.0, TOEFL 80, or Duolingo 105."
        ),
        coverage=["Tuition waiver", "Free on-campus accommodation", "Monthly stipend: Bachelor's CNY 2,500 / Master's CNY 3,000", "Comprehensive medical insurance"],
        official_source_url="https://ensie.nankai.edu.cn/info/1047/1347.htm",
        official_source="Nankai University & China Scholarship Council (CSC)",
        is_verified=True,
        best_fit="Bangladeshi students in business, economics, and international affairs",
    ),
    ScholarshipIngestionRecord(
        name="Confucius Institute Scholarship",
        country="China",
        degree_levels="Chinese Language Studies, Teaching Chinese as Foreign Language",
        funding_type="Fully Funded",
        deadline="Varies (typically January-April through local Confucius Institute)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-Chinese citizens aged 16-35, in good health. "
            "Applicants for Chinese language studies must have HSK and HSKK scores. "
            "Scholarship for one academic year, one academic semester, or four weeks. "
            "Must apply through local Confucius Institute or Confucius Classroom. "
            "Not all Confucius Institutes have allocations."
        ),
        coverage=["Full tuition", "Free accommodation", "Monthly stipend: CNY 2,500-3,000", "Basic health insurance", "One-time CNY 1,500 settlement allowance"],
        official_source_url="https://cis.chinese.cn/",
        official_source="Confucius Institute Headquarters (Hanban)",
        is_verified=True,
        best_fit="Bangladeshi students studying Chinese language or teaching Chinese",
    ),
)

# =============================================================================
# IRELAND SCHOLARSHIPS
# =============================================================================

IRELAND_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Government of Ireland International Education Scholarship (GOI-IES)",
        country="Ireland",
        degree_levels="Master's, Postgraduate Diploma, PhD",
        funding_type="Fully Funded",
        deadline="5pm (Irish time) 12 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens from outside EU/EEA, Switzerland, UK. Must hold a conditional or final "
            "offer of admission to an eligible Irish higher education institution for 2026/27. "
            "60 scholarships awarded annually for one year of full-time postgraduate study. "
            "Russian and Belarusian citizens not eligible. Cannot have previously held GOI-IES."
        ),
        coverage=["€10,000 stipend for one year", "Full tuition fee waiver by host institution", "Registration fees waived"],
        official_source_url="https://hea.ie/policy/internationalisation/goi-ies/",
        official_source="Higher Education Authority (HEA), Government of Ireland",
        is_verified=True,
        best_fit="High-calibre international postgraduate students including Bangladeshi applicants",
    ),
    ScholarshipIngestionRecord(
        name="Government of Ireland Postgraduate Scholarship Programme",
        country="Ireland",
        degree_levels="Master's (Research), PhD",
        funding_type="Fully Funded",
        deadline="Annual call (typically opens August, closes October)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All disciplines. Open to Irish, EU, and non-EU applicants. "
            "Prestigious awards for excellent research. Selection by international peer review. "
            "Funded by Department of Further and Higher Education, Research, Innovation and Science."
        ),
        coverage=["Stipend: €22,000 per annum", "Contribution to fees (incl. non-EU fees) up to €5,750/year", "Research expenses: €3,250/year"],
        official_source_url="https://research.ie/funding/goipg/",
        official_source="Irish Research Council (now Taighde Éireann/Research Ireland)",
        is_verified=True,
        best_fit="Research-focused postgraduate students in any discipline",
    ),
    ScholarshipIngestionRecord(
        name="UCD Global Excellence Scholarship",
        country="Ireland",
        degree_levels="Bachelor's, Master's (taught)",
        funding_type="Partial to Full",
        deadline="31 March 2026 (varies by region)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU fee-paying students with an offer (conditional or unconditional) for an eligible "
            "UCD programme. 100% and 50% tuition fee scholarships. "
            "Regions: North America (1 Feb), Middle East/Africa/Pakistan/South Asia (28 Feb), All others (31 Mar)."
        ),
        coverage=["100% tuition fee waiver", "50% tuition fee waiver"],
        official_source_url="https://www.ucd.ie/global/study-at-ucd/scholarshipsfinances/scholarships/globalexcellencescholarships/",
        official_source="University College Dublin (UCD)",
        is_verified=True,
        best_fit="Outstanding international undergraduate and graduate taught applicants to UCD",
    ),
    ScholarshipIngestionRecord(
        name="Trinity College Dublin Global Excellence Undergraduate Scholarship",
        country="Ireland",
        degree_levels="Bachelor's (first-year)",
        funding_type="Partial",
        deadline="Varies by region (Africa: 1 May, Americas: 1 Apr, SE Asia/Oceania: 15 Jul, Other: 15 Jun)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU students with an offer for a full-time undergraduate degree at TCD. "
            "Medicine, dentistry, acting, engineering, natural sciences, and computer science/statistics excluded. "
            "China students not eligible (use Claddagh Scholarship instead)."
        ),
        coverage=["€2,000 to €5,000 reduction on Year 1 tuition fees"],
        official_source_url="https://www.tcd.ie/study/international/scholarships/undergraduate/geug.php",
        official_source="Trinity College Dublin",
        is_verified=True,
        best_fit="Exceptional international undergraduate applicants to Trinity College Dublin",
    ),
    ScholarshipIngestionRecord(
        name="Trinity College Dublin Global Excellence Postgraduate Scholarship",
        country="Ireland",
        degree_levels="Master's (taught)",
        funding_type="Partial",
        deadline="Varies by region (Africa: 1 May, Americas: 1 Apr, SE Asia/Oceania: 15 Jul, Other: 15 Jun)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU students with an offer for a full-time postgraduate taught programme at TCD. "
            "Business, engineering, natural sciences, and computer science/statistics excluded. "
            "China students not eligible (use Claddagh Scholarship instead)."
        ),
        coverage=["€2,000 to €5,000 one-time reduction on tuition fees"],
        official_source_url="https://www.tcd.ie/study/international/scholarships/postgraduate/gexpg.php",
        official_source="Trinity College Dublin",
        is_verified=True,
        best_fit="Exceptional international postgraduate taught applicants to Trinity College Dublin",
    ),
    ScholarshipIngestionRecord(
        name="University of Galway Global Scholarships",
        country="Ireland",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="~May 2026 (verify on official site for current cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU international students commencing study at University of Galway. "
            "Merit-based scholarships for undergraduate and postgraduate taught programmes."
        ),
        coverage=["Tuition fee reduction (varies by award tier)", "Global Scholarship amounts vary by region and programme"],
        official_source_url="https://www.universityofgalway.ie/internationalscholarships/",
        official_source="University of Galway",
        is_verified=True,
        best_fit="Merit-based funding for international students at University of Galway",
    ),
)

# =============================================================================
# NEW ZEALAND SCHOLARSHIPS
# =============================================================================

NEW_ZEALAND_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Manaaki New Zealand Scholarships",
        country="New Zealand",
        degree_levels="Bachelor's, Master's, PhD, Postgraduate Diplomas",
        funding_type="Fully Funded",
        deadline="1 March 2026 – 31 March 2026 (midday)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of eligible partner countries across Pacific, Asia, Africa, Latin America, Caribbean. "
            "Bangladesh is eligible. Must be 18+, demonstrate leadership potential, show commitment to "
            "development in home country, agree to return home for at least 2 years after study. "
            "Postgraduate applicants need relevant work experience."
        ),
        coverage=["Full tuition fees", "Weekly living allowance NZ$531", "Establishment allowance NZ$3,000", "Travel to/from NZ", "Medical insurance", "Thesis/research funding (PG)"],
        official_source_url="https://www.nzscholarships.govt.nz/",
        official_source="New Zealand Government (MFAT / NZ Aid Programme)",
        is_verified=True,
        best_fit="Students from developing countries including Bangladesh committed to home-country development",
    ),
    ScholarshipIngestionRecord(
        name="University of Auckland International Student Excellence Scholarship",
        country="New Zealand",
        degree_levels="Bachelor's, Postgraduate Diploma, Master's",
        funding_type="Partial",
        deadline="21 October 2026 (Sem 1), 1 April 2026 (Sem 2)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New international students (non-NZ/non-Australian citizens/PR) with offer of admission. "
            "Grade Point Equivalent (GPE) of at least 6.00 required. Up to 50 scholarships/year. "
            "Full-time study in undergraduate degrees, PGDip, or masters programmes."
        ),
        coverage=["Up to NZ$10,000 towards tuition fees"],
        official_source_url="https://www.auckland.ac.nz/en/study/scholarships-and-awards/find-a-scholarship/university-of-auckland-international-student-excellence-scholarship-844-all.html",
        official_source="University of Auckland",
        is_verified=True,
        best_fit="High-calibre international students enrolling at University of Auckland",
    ),
    ScholarshipIngestionRecord(
        name="University of Auckland Doctoral Scholarship",
        country="New Zealand",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="Varies by faculty (annual round)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Excellent doctoral students of all nationalities. Covers 3 years. "
            "Awarded based on faculty recommendation — no separate scholarship application needed. "
            "Applicants must meet University of Auckland doctoral entry requirements."
        ),
        coverage=["Three years of tuition fees", "Living allowance", "Insurance costs"],
        official_source_url="https://www.auckland.ac.nz/en/study/scholarships-and-awards/scholarship-types/scholarships-for-postgraduate-students/doctoral-scholarships.html",
        official_source="University of Auckland",
        is_verified=True,
        best_fit="Outstanding doctoral candidates at University of Auckland",
    ),
    ScholarshipIngestionRecord(
        name="University of Otago Global Scholarship",
        country="New Zealand",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="Automatic with admission — no separate application",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New international Bachelor degree students commencing full-time undergraduate study. "
            "Holders of Bangladesh, China, India, and other listed country passports eligible. "
            "Unlimited offers. Automatically assessed during admission process."
        ),
        coverage=["NZ$15,000 towards first-year tuition fees"],
        official_source_url="https://www.otago.ac.nz/international/future-students/fees-scholarships/international-scholarships#global-scholarship",
        official_source="University of Otago",
        is_verified=True,
        best_fit="International undergraduates from Bangladesh and other eligible countries at Otago",
    ),
    ScholarshipIngestionRecord(
        name="University of Otago Vice-Chancellor's Scholarship for International Students",
        country="New Zealand",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="Automatic with admission — no separate application",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New international Bachelor degree students commencing full-time undergraduate study. "
            "Automatically assessed during admission process. Unlimited offers."
        ),
        coverage=["NZ$10,000 towards first-year tuition fees"],
        official_source_url="https://www.otago.ac.nz/international/future-students/fees-scholarships/international-scholarships#vice-chancellors",
        official_source="University of Otago",
        is_verified=True,
        best_fit="International undergraduate entrants to University of Otago",
    ),
    ScholarshipIngestionRecord(
        name="University of Otago International Academic Excellence Scholarship",
        country="New Zealand",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="Invitation to apply after accepting prior scholarship offer",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High-achieving international students commencing a full-time Bachelor degree at Otago. "
            "For students who have studied overseas. Competitive selection."
        ),
        coverage=["Approx. NZ$35,000 total", "First-year accommodation scholarship", "Tuition scholarships in Year 2 and Year 3"],
        official_source_url="https://www.otago.ac.nz/international/future-students/fees-scholarships/international-scholarships#academic-excellence",
        official_source="University of Otago",
        is_verified=True,
        best_fit="Top-achieving international undergraduates at University of Otago",
    ),
    ScholarshipIngestionRecord(
        name="VUW Postgraduate International Scholarship (Victoria University of Wellington)",
        country="New Zealand",
        degree_levels="Master's, Postgraduate Diploma",
        funding_type="Partial",
        deadline="Automatic with admission — assessed at point of offer",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New international students paying full international fees, holding an unconditional or "
            "conditional Offer of Place for a Master's degree (120/180/240 points) or PGDip (120 points) "
            "at Victoria University of Wellington. No separate scholarship application."
        ),
        coverage=["NZ$10,000 credit towards tuition fees"],
        official_source_url="https://www.wgtn.ac.nz/scholarships/current/vuw-postgraduate-international-scholarship",
        official_source="Te Herenga Waka — Victoria University of Wellington",
        is_verified=True,
        best_fit="International postgraduate students at Victoria University of Wellington",
    ),
    ScholarshipIngestionRecord(
        name="VUW Undergraduate International Scholarship (Victoria University of Wellington)",
        country="New Zealand",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="Automatic with admission — assessed at point of offer",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "New international students entering first year of a Bachelor's degree, "
            "studying full-time on campus at Victoria University of Wellington. "
            "No separate scholarship application."
        ),
        coverage=["NZ$10,000 credit towards tuition fees"],
        official_source_url="https://www.wgtn.ac.nz/international/scholarships-fees/scholarships",
        official_source="Te Herenga Waka — Victoria University of Wellington",
        is_verified=True,
        best_fit="International undergraduate students at Victoria University of Wellington",
    ),
)

# =============================================================================
# FINLAND SCHOLARSHIPS
# =============================================================================

FINLAND_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Finland Scholarship (National)",
        country="Finland",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="January 2026 (with admission application, varies by university)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students newly admitted to participating Finnish universities. "
            "Outstanding academic record. Not previously enrolled in a Finnish degree programme. "
            "Coordinated by Finnish National Agency for Education. No separate scholarship application — "
            "selection via the Studyinfo.fi master's admission process."
        ),
        coverage=["100% of first-year tuition fee", "€5,000 relocation grant (one-time)"],
        official_source_url="https://www.studyinfinland.fi/funding-your-studies/bachelors-and-masters-scholarships",
        official_source="Finnish National Agency for Education (EDUFI)",
        is_verified=True,
        best_fit="Top non-EU master's entrants at Finnish universities",
    ),
    ScholarshipIngestionRecord(
        name="Aalto University Excellence Scholarship",
        country="Finland",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial to Full",
        deadline="20 March 2026 (master's admissions)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students liable for tuition fees. Highly competitive merit-based scholarships "
            "for the highest-achieving applicants. Granted as 100% tuition fee waivers. "
            "Applied during admission application — no separate form."
        ),
        coverage=["100% tuition fee waiver", "Does not cover living costs (min. €800/month self-funded)"],
        official_source_url="https://www.aalto.fi/en/admission-services/scholarships-and-tuition-fees",
        official_source="Aalto University",
        is_verified=True,
        best_fit="Top non-EU applicants to Aalto University bachelor's and master's programmes",
    ),
    ScholarshipIngestionRecord(
        name="University of Helsinki Scholarship Programme",
        country="Finland",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="With master's admission application (varies by programme)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students liable for tuition fees, admitted to University of Helsinki Master's programmes. "
            "Highly competitive. Most scholarships are 50% tuition waivers; limited 100% waivers available. "
            "Scholarship decided as part of admission results."
        ),
        coverage=["100% tuition fee waiver (limited)", "50% tuition fee waiver (majority of awards)", "Must cover living costs independently"],
        official_source_url="https://www.helsinki.fi/en/admissions-and-education/apply-bachelors-and-masters-programmes/tuition-fees-and-scholarship-programme",
        official_source="University of Helsinki",
        is_verified=True,
        best_fit="Outstanding non-EU master's applicants to University of Helsinki",
    ),
    ScholarshipIngestionRecord(
        name="Tampere University Scholarships Programme",
        country="Finland",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="With admission application (varies by intake round)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Tuition-fee-liable students (non-EU/EEA) admitted to Tampere University English-taught programmes. "
            "Scholarship application is part of the admission process. Also offers Early Bird discount "
            "for prompt offer acceptance and fee payment."
        ),
        coverage=["50% tuition fee scholarship", "100% tuition fee scholarship (limited, Finland Scholarship tier)", "Early Bird tuition discount"],
        official_source_url="https://www.tuni.fi/en/students-guide/handbook/uni/services-and-regulations-students/study-regulations/scholarships-fee-paying-students-admitted-in-2021-or-later",
        official_source="Tampere University",
        is_verified=True,
        best_fit="Fee-paying international students at Tampere University",
    ),
    ScholarshipIngestionRecord(
        name="University of Turku International Scholarships",
        country="Finland",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="January 2026 (with admission application)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "High-merit non-EU/EEA students admitted to University of Turku Master's programmes. "
            "NOTE: Starting 2026 intake, University of Turku has changed scholarship policy — "
            "no longer awards tuition-fee scholarships to newly admitted non-EU/EEA students. "
            "Early Bird tuition discount remains available. This record should be verified before use."
        ),
        coverage=["50% or 100% tuition fee waiver (pre-2026 intake)", "Early Bird discount available", "No tuition scholarships for 2026 intake onward"],
        official_source_url="https://www.utu.fi/en/study-at-turku/tuition-fees-and-scholarships",
        official_source="University of Turku",
        is_verified=False,
        best_fit="Students applying for pre-2026 intake at University of Turku (needs_review for 2026+)",
    ),
    ScholarshipIngestionRecord(
        name="LUT University Scholarships",
        country="Finland",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="With admission application",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students liable for tuition fees at LUT University (Lappeenranta campus). "
            "Merit scholarships based on academic performance in admission. "
            "Also offers early-bird and second-year fixed discounts (~€5,000 each)."
        ),
        coverage=["Up to 100% tuition fee waiver", "Early Bird discount (~€5,000)", "Second-year progress discount (~€5,000)"],
        official_source_url="https://www.lut.fi/en/tuition-fees-and-scholarships",
        official_source="LUT University",
        is_verified=True,
        best_fit="Fee-paying international students at LUT University (energy, sustainability, business)",
    ),
)

# =============================================================================
# DENMARK SCHOLARSHIPS
# =============================================================================

DENMARK_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Danish Government Scholarship for Highly Qualified Non-EU/EEA Students",
        country="Denmark",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial to Full",
        deadline="January–March 2026 (varies by university)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of countries outside EU/EEA/Switzerland. Must be enrolled in a full-degree programme "
            "and granted a time-limited residence permit for education. Administered individually by each "
            "Danish university — no central application. Cannot be claimed at Artistic Higher Education Institutions "
            "or if eligible for Danish State Education Grant (SU)."
        ),
        coverage=["Full tuition fee waiver (varies by university)", "Partial tuition waiver possible", "Possible monthly living grant (varies by university/faculty)"],
        official_source_url="https://studyindenmark.dk/study-options/scholarships",
        official_source="Ministry of Higher Education and Science, Denmark",
        is_verified=True,
        best_fit="Highly qualified non-EU/EEA students admitted to Danish universities",
    ),
    ScholarshipIngestionRecord(
        name="DTU Excellence Scholarship (Technical University of Denmark)",
        country="Denmark",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="15 January 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students admitted to DTU MSc programmes. Requires separate scholarship personal statement. "
            "Tuition-only waiver — no living stipend. Highly competitive; top GPA and research record favoured. "
            "Fields: engineering, physics, mathematics, computing, biotech."
        ),
        coverage=["100% tuition fee waiver (very limited awards)", "No monthly stipend — living costs self-funded (DKK 8,000–12,000/month)"],
        official_source_url="https://www.dtu.dk/english/education/graduate/fees-and-funding/external-scholarships",
        official_source="Technical University of Denmark (DTU)",
        is_verified=True,
        best_fit="Top non-EU engineering and science master's students at DTU",
    ),
    ScholarshipIngestionRecord(
        name="Copenhagen Business School Danish Government Scholarship",
        country="Denmark",
        degree_levels="Master's (MSc)",
        funding_type="Partial to Full",
        deadline="15 January 2026 (Round 1) / 15 October 2026 (Round 2)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students admitted to CBS MSc programmes. Must check scholarship box in portal "
            "and upload 2-page personal statement. ~25 awards/year across all graduate programmes. "
            "Most generous Danish package: tuition + monthly stipend. Interview may be required."
        ),
        coverage=["Full tuition fee waiver", "DKK 8,000/month living stipend (~DKK 6,500–7,000 after tax)", "Maximum duration: 22 months"],
        official_source_url="https://www.cbs.dk/en/education/master/programmes-and-admission/fees-and-funding",
        official_source="Copenhagen Business School (CBS)",
        is_verified=True,
        best_fit="Top international business master's students at CBS",
    ),
    ScholarshipIngestionRecord(
        name="University of Copenhagen Danish Government Scholarship",
        country="Denmark",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="With admission application",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students admitted to KU MA/MSc programmes. No separate scholarship application — "
            "automatic consideration. 2–4 scholarships per faculty per year. "
            "Awarded solely on academic achievement; financial need not considered."
        ),
        coverage=["Full or partial tuition fee waiver", "Some faculties include basic living expense grant"],
        official_source_url="https://www.ku.dk/studies/masters/application-and-admission/scholarships",
        official_source="University of Copenhagen",
        is_verified=True,
        best_fit="Outstanding non-EU master's applicants to University of Copenhagen",
    ),
    ScholarshipIngestionRecord(
        name="Aarhus University Danish State Scholarship",
        country="Denmark",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="15 January 2026 (Round 1) / 15 September 2026 (Round 2)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students admitted to Aarhus University Master's programmes. "
            "Typically 1–2 scholarships per programme. "
            "No separate scholarship application — assessed during admission review."
        ),
        coverage=["100% tuition fee waiver", "No monthly stipend (tuition waiver only)"],
        official_source_url="https://masters.au.dk/scholarships-and-grants",
        official_source="Aarhus University",
        is_verified=True,
        best_fit="Talented non-EU master's applicants to Aarhus University",
    ),
    ScholarshipIngestionRecord(
        name="University of Southern Denmark (SDU) Danish Government Scholarship",
        country="Denmark",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial to Full",
        deadline="1 February 2026 (Master's) / 15 March 2026 (Bachelor's)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Non-EU/EEA students applying to eligible SDU programmes. Limited programmes and campuses. "
            "Automatic consideration with admission. Some programmes include interview."
        ),
        coverage=["100% tuition fee waiver (limited programmes)", "DKK 6,090/month stipend at SDU", "Does NOT include housing or travel"],
        official_source_url="https://www.sdu.dk/en/uddannelse/tuition-fees-and-scholarships",
        official_source="University of Southern Denmark (SDU)",
        is_verified=True,
        best_fit="Non-EU students in eligible SDU bachelor's and master's programmes",
    ),
)

# =============================================================================
# NORWAY SCHOLARSHIPS
# =============================================================================

NORWAY_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="BI Presidential Scholarship",
        country="Norway",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="1 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Norwegian and international applicants admitted to first year of a Master's programme "
            "at BI Norwegian Business School (Oslo or Bergen campus). "
            "Minimum GPA of 'A' on ECTS scale or equivalent. "
            "For international applicants: full tuition + living stipend. "
            "Domestic applicants: tuition only."
        ),
        coverage=["Full tuition fees for up to 2 years", "NOK 50,000/semester living stipend (international students)", "Academic progression requirements apply"],
        official_source_url="https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-presidential-scholarships/",
        official_source="BI Norwegian Business School",
        is_verified=True,
        best_fit="Top academic master's applicants to BI Norwegian Business School",
    ),
    ScholarshipIngestionRecord(
        name="BI Master International Scholarship – Bergen",
        country="Norway",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="1 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students (non-Norwegian residents) admitted to MSc programmes at BI Bergen campus. "
            "Minimum GPA 4.0 on ECTS scale. "
            "Applicants for BI Presidential Scholarship are automatically considered."
        ),
        coverage=["Full tuition fees for up to 2 years", "No living stipend", "Academic progression requirements apply"],
        official_source_url="https://www.bi.no/en/programmes-and-individual-courses/scholarships/master-of-science-international-scholarship--bergen/",
        official_source="BI Norwegian Business School",
        is_verified=True,
        best_fit="International master's students at BI Bergen campus",
    ),
    ScholarshipIngestionRecord(
        name="BI International Baccalaureate Scholarship",
        country="Norway",
        degree_levels="Bachelor's",
        funding_type="Partial",
        deadline="1 March 2026 (international applicants not residing in Norway)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Applicants graduating with top grades from the International Baccalaureate (IB) programme. "
            "Admitted to Bachelor of Data Science for Business, Business Administration, or Digital Business "
            "at BI Norwegian Business School. Covers 100% of tuition fees for up to 3 years."
        ),
        coverage=["100% tuition fee waiver for up to 3 years", "No living stipend", "Academic progression requirements apply"],
        official_source_url="https://www.bi.no/en/programmes-and-individual-courses/scholarships/bi-international-baccalaureate-scholarship/",
        official_source="BI Norwegian Business School",
        is_verified=True,
        best_fit="Top IB graduates entering BI bachelor's programmes",
    ),
    ScholarshipIngestionRecord(
        name="BI Future African Leader Scholarship",
        country="Norway",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="1 March 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "African citizens (and GBSN Member School students) admitted to MSc programmes at BI Oslo or Bergen. "
            "Minimum GPA 4.0 on ECTS. Strong GMAT/GRE required. "
            "BI member of GBSN Network and GMAC Study in Europe Initiative. 2 MSc scholarships available."
        ),
        coverage=["Full tuition fees for up to 2 years", "NOK 50,000/semester living stipend", "Academic progression requirements apply"],
        official_source_url="https://www.bi.no/en/programmes-and-individual-courses/scholarships/future-african-leader-scholarship/",
        official_source="BI Norwegian Business School",
        is_verified=True,
        best_fit="African master's applicants with strong academic and leadership profiles at BI",
    ),
    ScholarshipIngestionRecord(
        name="NTNU PhD Positions (Salaried Employment)",
        country="Norway",
        degree_levels="PhD",
        funding_type="Fully Funded (Salaried Employment)",
        deadline="Year-round (positions advertised individually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "PhD positions at Norwegian University of Science and Technology (NTNU) are salaried employment, "
            "not scholarships. Open to all nationalities. "
            "Typical salary NOK 530,000–580,000/year (~EUR 46,000–51,000). "
            "Includes pension and full employment benefits. No tuition — candidates are university staff. "
            "English sufficient; Norwegian language requirement removed June 2025."
        ),
        coverage=["Annual salary NOK 530,000–580,000", "Pension contributions", "Full employment benefits", "No tuition (employment status)"],
        official_source_url="https://www.ntnu.edu/jobs",
        official_source="Norwegian University of Science and Technology (NTNU)",
        is_verified=True,
        best_fit="Research-oriented PhD candidates seeking salaried positions at NTNU",
    ),
    ScholarshipIngestionRecord(
        name="NORPART – Norwegian Partnership Programme",
        country="Norway",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="15 October 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Supports academic cooperation and student mobility between Norwegian universities and partner "
            "institutions in developing countries. Covers tuition, travel, and living costs. "
            "Open to students from Ethiopia, Ghana, Kenya, Malawi, Mozambique, Nigeria, Rwanda, South Africa, Tanzania, Uganda. "
            "Bangladesh NOT currently listed as NORPART partner country — verify with home institution. "
            "Students can only access through home institution's partnership agreement — no individual applications."
        ),
        coverage=["Tuition fees", "Travel costs", "Living costs (varies by partnership)"],
        official_source_url="https://www.uhr.no/programmes-and-agreements/norpart-norwegian-partnership-programme/",
        official_source="Norwegian Directorate for Higher Education and Skills (HK-dir)",
        is_verified=False,
        best_fit="Students at institutions with NORPART partnership agreements (Bangladesh needs_review)",
    ),
)
# =============================================================================
# BELGIUM SCHOLARSHIPS
# =============================================================================

BELGIUM_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Master Mind Scholarships — Flemish Government",
        country="Belgium",
        degree_levels="Master's (60 or 120 ECTS)",
        funding_type="Fully Funded",
        deadline="27 April 2026 23:59 GMT+1 (2026-2027 cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities except Russian citizens. Outstanding students for Master's programmes "
            "in Flanders or Brussels. Previous degree must not have been obtained at a Flemish institution. "
            "Students already enrolled at a Flemish institution cannot apply (except preparatory programme students). "
            "Cannot combine with other Flemish government or Erasmus Mundus scholarships. "
            "Up to 30 scholarships annually. KU Leuven can nominate 20 candidates."
        ),
        coverage=[
            "Grant of €10,225 per academic year",
            "Full tuition fee waiver (pays only ~€140 admin fee)",
            "Up to 2 academic years for 120 ECTS programmes",
            "Reserved scholarships: Japan (3), Mexico (3), Palestine (2), USA (5)",
        ],
        official_source_url="https://www.international.vluhr.be/scholarships/master-mind-scholarships",
        official_source="Flemish Ministry of Education and Training / VLUHR",
        is_verified=True,
        best_fit="Outstanding international Master's applicants to Flemish universities",
    ),
    ScholarshipIngestionRecord(
        name="KU Leuven ICP Connect Scholarship (VLIR-UOS)",
        country="Belgium",
        degree_levels="Master's (selected programmes)",
        funding_type="Fully Funded",
        deadline="1 February 2026, 23:59 CET",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of 28 VLIR-UOS partner countries in Africa, Asia, and Latin America. "
            "Must reside in eligible country at time of application. Age <=35 (Master's) or <=45 (Advanced Master's). "
            "Preference for candidates in higher education, government, or civil society. "
            "Cannot have previously received a Belgian government scholarship or studied at a Belgian institution. "
            "50 scholarships across 5 programmes: Cultural Anthropology & Development Studies, "
            "Human Settlements, Food Technology, Sustainable Development, Water Resources Engineering."
        ),
        coverage=[
            "Full tuition fee waiver",
            "Monthly allowance €1,400 (living, accommodation, meals, transport)",
            "Health insurance",
            "Installation costs",
            "Round-trip travel to/from Belgium",
            "Full standard length of programme",
        ],
        official_source_url="https://www.kuleuven.be/scholarships/year/2026-2027/icp-connect-scholarship",
        official_source="KU Leuven / VLIR-UOS (Flemish Interuniversity Council)",
        is_verified=True,
        best_fit="Outstanding students from developing countries in development-related Master's programmes",
    ),
    ScholarshipIngestionRecord(
        name="KU Leuven Inspiring the Outstanding Scholarship",
        country="Belgium",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="15 January 2026, 23:59 CET",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities eligible. Outstanding students for Master's programmes at KU Leuven. "
            "Previous degree must be from outside Flanders. Students already enrolled at Flemish institutions "
            "cannot apply. Only 1 scholarship available. Cannot combine with any other scholarship. "
            "One application process considers candidates for Master Mind, ASEAN, Africa, and "
            "Central/South America scholarships simultaneously."
        ),
        coverage=[
            "Full tuition fee waiver (pays only ~€140 admin fee)",
            "Scholarship of €13,200 per academic year",
            "Up to 2 academic years for 120 ECTS programmes",
        ],
        official_source_url="https://www.kuleuven.be/scholarships/year/2026-2027/inspiring-the-outstanding-scholarship",
        official_source="KU Leuven International Scholarship Fund",
        is_verified=True,
        best_fit="Outstanding international Master's applicants to KU Leuven",
    ),
    ScholarshipIngestionRecord(
        name="Ghent University Top-Up Grant for International Students",
        country="Belgium",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="Varies by programme (typically February-April)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students from all countries applying to Master's programmes at Ghent University. "
            "Must have outstanding academic record. Students who do not receive a Master Mind scholarship "
            "may be considered for a Top-Up Grant. Covers the difference between international and EEA tuition fees."
        ),
        coverage=[
            "Monthly allowance (amount varies, covers living expenses)",
            "Tuition fee reduction to EEE rate",
            "Insurance",
            "One-time travel allowance",
        ],
        official_source_url="https://www.ugent.be/en/financial/topupgrant",
        official_source="Ghent University",
        is_verified=True,
        best_fit="Outstanding international Master's applicants to Ghent University",
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Belgian Universities",
        country="Belgium",
        degree_levels="Master's (joint degree across 2+ European countries)",
        funding_type="Fully Funded",
        deadline="Varies by programme (typically October-February)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to students from all countries worldwide. Joint Master's programmes delivered by "
            "international consortia including Belgian universities (KU Leuven, Ghent, UCLouvain, ULB, VUB). "
            "Study in at least two European countries. Full scholarships available for best-ranked students. "
            "No nationality restrictions. Cannot have previously received an Erasmus Mundus scholarship."
        ),
        coverage=[
            "Full tuition fees",
            "Monthly stipend ~€1,400 for up to 24 months",
            "Travel allowance",
            "Health insurance",
            "Installation costs",
            "Visa support",
        ],
        official_source_url="https://www.studyinbelgium.be/en/scholarships/erasmus-mundus-joint-masters-degrees-emjmd",
        official_source="European Commission / Belgian Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes",
    ),
)

# =============================================================================
# HUNGARY SCHOLARSHIPS
# =============================================================================

HUNGARY_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Stipendium Hungaricum Scholarship Programme",
        country="Hungary",
        degree_levels="Bachelor's, Master's, One-tier Master's, Doctoral, Non-degree",
        funding_type="Fully Funded",
        deadline="15 January 2026, 2 p.m. CET",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Nationals of partner countries with bilateral educational cooperation agreements with Hungary. "
            "Based on nationality, not residence. Available for bachelor's, master's, one-tier master's, doctoral, "
            "and non-degree programmes. Must apply through online system AND responsible sending partner authority. "
            "More than 100 sending partners engaged. ~900 study programmes available. In 2025, 80,000 applications "
            "received and 4,500 scholarships awarded."
        ),
        coverage=[
            "Tuition-free education",
            "Monthly stipend: HUF 43,700 (non-degree/bachelor's/master's); HUF 140,000-180,000 (doctoral)",
            "Accommodation contribution: free dormitory or HUF 40,000/month",
            "Medical insurance: up to HUF 65,000/year",
        ],
        official_source_url="https://stipendiumhungaricum.hu",
        official_source="Hungarian Government / Tempus Public Foundation",
        is_verified=True,
        best_fit="Students from partner countries (check eligibility at stipendiumhungaricum.hu/partners)",
    ),
    ScholarshipIngestionRecord(
        name="Hungarian Diaspora Scholarship Programme",
        country="Hungary",
        degree_levels="Bachelor's, Master's, One-tier Master's, Doctoral, Non-degree",
        funding_type="Fully Funded",
        deadline="2 February 2026, 2 p.m. CET",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "For individuals with Hungarian roots/ancestors living outside EU, Serbia, and Zakarpatska Oblast (Ukraine). "
            "Must demonstrate Hungarian identity in motivation letter and have recommendation from Hungarian diaspora "
            "organization or diplomatic representation. Must have lived outside Hungary for at least 5 years. "
            "Covers all countries except EU member states. ~33 Hungarian higher education institutions engaged, "
            "~1300 study programmes available."
        ),
        coverage=[
            "Tuition-free education",
            "Monthly stipend: HUF 43,700 (non-degree/bachelor's/master's)",
            "Accommodation contribution: free dormitory or HUF 40,000/month",
            "Medical insurance: up to HUF 65,000/year",
            "Travel allowance (distance-based, HUF 330,000 if >8,000km from Budapest)",
            "Hungary Pass (unlimited domestic travel)",
        ],
        official_source_url="https://diasporascholarship.hu/en/",
        official_source="Hungarian Government / Tempus Public Foundation",
        is_verified=True,
        best_fit="Individuals with Hungarian heritage seeking to study in Hungary",
    ),
    ScholarshipIngestionRecord(
        name="CEU Master's and Doctoral Scholarships — Central European University",
        country="Hungary",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Fully Funded (Master's and PhD) / Partial (Bachelor's)",
        deadline="Round 1: October 15, 2026 (closed); Round 2: 4 February 2026",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities eligible. CEU is a prestigious research institution in Budapest/Vienna. "
            "Master's and PhD programmes are fully funded (tuition + stipend). "
            "Undergraduate programmes offer partial tuition support. "
            "Multiple donor-funded scholarships available: Dr. Elemer Hantos (Central Europe/Latin America), "
            "Postgraduate Opportunity (30 CEE countries), George Soros Leadership Fund, and others. "
            "Automatic consideration upon admission application — no separate scholarship application needed."
        ),
        coverage=[
            "Full tuition waiver (Master's and PhD)",
            "Monthly stipend €500-€1,350 depending on level and merit",
            "Health insurance",
            "Housing support",
            "Research funding (PhD)",
        ],
        official_source_url="https://www.ceu.edu/admissions/financial-aid",
        official_source="Central European University (Budapest/Vienna)",
        is_verified=True,
        best_fit="Outstanding international students for social sciences, humanities, law, public policy",
    ),
    ScholarshipIngestionRecord(
        name="Budapest University of Technology and Economics (BME) Scholarships",
        country="Hungary",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial to Fully Funded",
        deadline="Varies by programme (typically aligned with admissions)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students applying to BME programmes. BME is Hungary's oldest technical university. "
            "Scholarships available through Stipendium Hungaricum, institutional awards, and faculty-specific funding. "
            "Strong focus on engineering, computer science, and natural sciences."
        ),
        coverage=[
            "Tuition fee waivers (partial to full)",
            "Monthly stipends (varies)",
            "Accommodation support",
        ],
        official_source_url="https://www.bme.hu/en/scholarships",
        official_source="Budapest University of Technology and Economics",
        is_verified=True,
        best_fit="Engineering and technology students seeking study in Hungary",
    ),
)

# =============================================================================
# POLAND SCHOLARSHIPS
# =============================================================================

POLAND_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Stefan Banach NAWA Scholarship Programme (Poland)",
        country="Poland",
        degree_levels="Master's (second-cycle studies)",
        funding_type="Fully Funded",
        deadline="8 May 2026, 3:00 p.m. Warsaw time (or until application quota reached)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of 36 eligible developing countries (Albania, Angola, Argentina, Armenia, Azerbaijan, "
            "Belarus, Bosnia and Herzegovina, Brazil, Georgia, India, Indonesia, Iraq, Iran, Jordan, Kazakhstan, "
            "Kenya, Kosovo, Lebanon, Mexico, Moldova, Mongolia, Montenegro, Nigeria, North Macedonia, Palestine, "
            "Papua New Guinea, Peru, Philippines, Rwanda, Senegal, Serbia, Tanzania, Tunisia, Ukraine, Uzbekistan, Vietnam). "
            "Must hold a first-cycle degree (obtained no earlier than 2024). Must not have Polish citizenship. "
            "Must not have previously received a NAWA scholarship for second-cycle studies. "
            "Language requirements: Polish B2 (for Polish-medium) or English B2 (for English-medium). "
            "Joint initiative of Ministry of Foreign Affairs and NAWA for Polish development cooperation."
        ),
        coverage=[
            "Monthly scholarship: PLN 2,500/month (max 12 months/year)",
            "Exemption from tuition fees at public universities",
            "NAWA preparatory course funding (if applicable)",
            "Lump sum for international travel to Poland (PLN 2,500 one-time)",
        ],
        official_source_url="https://nawa.gov.pl/en/students/foreign-students/the-banach-scholarship-programme/about-the-programme",
        official_source="Polish National Agency for Academic Exchange (NAWA) / Ministry of Foreign Affairs",
        is_verified=True,
        best_fit="Citizens of developing countries pursuing Master's in Poland (STEM, agriculture, sciences, humanities)",
    ),
    ScholarshipIngestionRecord(
        name="Poland My First Choice NAWA Scholarship Programme",
        country="Poland",
        degree_levels="Master's (second-cycle studies)",
        funding_type="Fully Funded",
        deadline="29 May 2026, 3:00 p.m. Warsaw time (2026-2027 cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of developed countries: Australia, Austria, Belgium, Bulgaria, Canada, Chile, Croatia, Cyprus, "
            "Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Iceland, Ireland, Israel, Italy, "
            "Japan, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Netherlands, New Zealand, Norway, Portugal, Romania, "
            "Singapore, Slovakia, Slovenia, South Korea, Spain, Sweden, Switzerland, UK, USA, Uruguay, and Chinese citizens "
            "residing in Hong Kong/Macau/Taiwan. Must hold first-cycle degree (obtained no earlier than 2024). "
            "Must not have Polish citizenship. Must not have previously received NAWA scholarship for second-cycle studies. "
            "Language: Polish B2 or English B2. Applicants choose their own university and field from institutions with "
            "framework agreement with NAWA."
        ),
        coverage=[
            "Monthly scholarship: PLN 2,000/month (max 12 months/year)",
            "Exemption from tuition fees at public universities",
            "Lump sum for international travel (varies by country: PLN 1,000-6,500)",
        ],
        official_source_url="https://nawa.gov.pl/en/students/foreign-students/poland-my-first-choice-programme/about-the-programme",
        official_source="Polish National Agency for Academic Exchange (NAWA)",
        is_verified=True,
        best_fit="Talented students from developed countries for Master's at Polish academic institutions",
    ),
    ScholarshipIngestionRecord(
        name="Visegrad Scholarship Programme — Poland Host Institution",
        country="Poland",
        degree_levels="Master's, Post-Master's (PhD, postdoc)",
        funding_type="Partial",
        deadline="15 April 2027 (next cycle opens 1 January 2027)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of Visegrad countries (CZ, HU, PL, SK) studying in another V4 country, OR citizens of "
            "Western Balkans (Albania, Bosnia and Herzegovina, Kosovo, Montenegro, North Macedonia, Serbia) OR "
            "Eastern Partnership countries (Armenia, Azerbaijan, Belarus, Georgia, Moldova, Ukraine) studying in V4. "
            "Must hold Bachelor's degree (for Master's) or Master's degree (for post-Master's). "
            "Citizenship country must differ from host country. Must be >150km from permanent residence to host institution. "
            "Up to 2 semesters support (In-Coming scheme allows up to 4 semesters)."
        ),
        coverage=[
            "€3,500 per semester for scholar",
            "€2,000 per semester for host institution",
            "1-2 semesters (Master's) or 1-4 semesters (In-Coming scheme)",
        ],
        official_source_url="https://study.gov.pl/visegrad-scholarship-programme",
        official_source="International Visegrad Fund",
        is_verified=True,
        best_fit="Students from V4, Western Balkans, and Eastern Partnership countries studying in Poland",
    ),
    ScholarshipIngestionRecord(
        name="Jagiellonian University Rector's Scholarship for International Students",
        country="Poland",
        degree_levels="Bachelor's, Master's, Long-cycle Master's",
        funding_type="Partial",
        deadline="Varies (applications through USOSweb system)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "International students enrolled at Jagiellonian University (Krakow) who began studies in 2019/2020 or later. "
            "Merit-based scholarship for outstanding academic performance. Available to students studying under "
            "rules applicable to Polish citizens. Number of scholarships not limited — all qualifying students receive it. "
            "Can be combined with scholarships from Rector's Fund for specific achievements."
        ),
        coverage=[
            "Monthly stipend (amount varies by faculty and academic year)",
            "Awarded for academic year (10 months)",
            "Can be combined with other Rector's Fund scholarships",
        ],
        official_source_url="https://stypendia.uj.edu.pl/en_GB/pomoc-materialna/cudzoziemcy",
        official_source="Jagiellonian University (Krakow)",
        is_verified=True,
        best_fit="International students with outstanding academic records at Jagiellonian University",
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Polish Universities",
        country="Poland",
        degree_levels="Master's (joint degree across 2+ European countries)",
        funding_type="Fully Funded",
        deadline="Varies by programme (typically October-February)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to students from all countries worldwide. Joint Master's programmes delivered by "
            "international consortia including Polish universities (Jagiellonian, Warsaw, Wroclaw, etc.). "
            "Study in at least two European countries. Full scholarships available for best-ranked students. "
            "No nationality restrictions. Cannot have previously received an Erasmus Mundus scholarship."
        ),
        coverage=[
            "Full tuition fees",
            "Monthly stipend ~€1,400 for up to 24 months",
            "Travel allowance",
            "Health insurance",
            "Installation costs",
        ],
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters/poland",
        official_source="European Commission / Polish Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes with Polish partners",
    ),
)

# =============================================================================
# CZECH REPUBLIC SCHOLARSHIPS
# =============================================================================

CZECH_REPUBLIC_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Czech Government Scholarships — Developing Countries (AY 2026/27)",
        country="Czech Republic",
        degree_levels="Master's (Czech-medium), Master's (English-medium), Doctoral (English-medium)",
        funding_type="Fully Funded",
        deadline="30 September 2025 (for AY 2026/27, closed for 2026 cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "For AY 2026/27 ONLY for citizens of: Belarus (democratic forces), Bosnia and Herzegovina, "
            "Cambodia, Ethiopia, Georgia, Guatemala, Jordan, Nigeria, Rwanda, Sri Lanka, Ukraine, Zambia. "
            "Scholarships for Czech-medium Bachelor's and Master's (preceded by 1-year language course), "
            "English-medium Master's and Doctoral programmes. Must be officially nominated by relevant "
            "authority in eligible country. Does not apply to summer language courses. "
            "Monthly scholarship: CZK 16,000 (Bachelor's/Master's) or CZK 17,000 (Doctoral)."
        ),
        coverage=[
            "Tuition-free education",
            "Monthly scholarship: CZK 16,000 (Bachelor's/Master's) or CZK 17,000 (Doctoral)",
            "Accommodation at university dormitories",
            "Czech language course (for Czech-medium programmes)",
            "Health insurance recommendation",
        ],
        official_source_url="https://msmt.gov.cz/eu-and-international-affairs/government-scholarships-developing-countries",
        official_source="Ministry of Education, Youth and Sports (MEYS) / DZS",
        is_verified=True,
        best_fit="Citizens of 12 eligible developing countries for Master's/PhD in Czech Republic",
    ),
    ScholarshipIngestionRecord(
        name="Charles University Scholarships — International Students",
        country="Czech Republic",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial to Fully Funded",
        deadline="Varies by faculty and scholarship type",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Charles University (Prague) offers multiple scholarship schemes: "
            "1) Faculty of Mathematics and Physics tuition fee scholarships (up to €21,600), "
            "2) Faculty of Science STARS scholarships for talented PhD students, "
            "3) Czech Government Scholarships for developing countries, "
            "4) International Visegrad Fund Scholarships, "
            "5) Václav Havel Bursary for students from repressive regimes. "
            "Most faculties offer merit-based scholarships for outstanding students after first year."
        ),
        coverage=[
            "Tuition fee waivers (partial to full)",
            "Monthly stipends (varies by faculty)",
            "Research funding (PhD)",
            "Health insurance support",
        ],
        official_source_url="https://cuni.cz/UKEN-1617.html",
        official_source="Charles University (Prague)",
        is_verified=True,
        best_fit="Outstanding international students at Charles University Prague",
    ),
    ScholarshipIngestionRecord(
        name="International Visegrad Fund Scholarships — Czech Republic Host",
        country="Czech Republic",
        degree_levels="Master's, Post-Master's (PhD, postdoc)",
        funding_type="Partial",
        deadline="15 April 2027 (next cycle opens 1 January 2027)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Citizens of Visegrad countries (CZ, HU, PL, SK) studying in another V4 country, OR citizens of "
            "Western Balkans (Albania, Bosnia and Herzegovina, Kosovo, Montenegro, North Macedonia, Serbia) OR "
            "Eastern Partnership countries (Armenia, Azerbaijan, Belarus, Georgia, Moldova, Ukraine) studying in V4. "
            "Must hold Bachelor's degree (for Master's) or Master's degree (for post-Master's). "
            "Citizenship country must differ from host country. Must be >150km from permanent residence to host institution. "
            "Up to 2 semesters support (In-Coming scheme allows up to 4 semesters)."
        ),
        coverage=[
            "€3,500 per semester for scholar",
            "€2,000 per semester for host institution",
            "1-2 semesters (Master's) or 1-4 semesters (In-Coming scheme)",
        ],
        official_source_url="https://www.visegradfund.org/scholarships",
        official_source="International Visegrad Fund",
        is_verified=True,
        best_fit="Students from V4, Western Balkans, and Eastern Partnership countries studying in Czech Republic",
    ),
    ScholarshipIngestionRecord(
        name="Masaryk University International Scholarships",
        country="Czech Republic",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies by faculty",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Masaryk University (Brno) offers various scholarship opportunities: "
            "Visegrad Scholarship Programme host institution, faculty-specific merit scholarships, "
            "and need-based support. International students from all countries eligible for merit awards. "
            "Strong focus on social sciences, natural sciences, and humanities."
        ),
        coverage=[
            "Tuition fee reductions",
            "Monthly stipends (varies)",
            "Accommodation support",
        ],
        official_source_url="https://czs.muni.cz/en/student-from-abroad/other-possibilities/visegrad-grant",
        official_source="Masaryk University (Brno)",
        is_verified=True,
        best_fit="International students at Masaryk University Brno",
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Czech Universities",
        country="Czech Republic",
        degree_levels="Master's (joint degree across 2+ European countries)",
        funding_type="Fully Funded",
        deadline="Varies by programme (typically October-February)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to students from all countries worldwide. Joint Master's programmes delivered by "
            "international consortia including Czech universities (Charles University, Masaryk, CTU Prague). "
            "Study in at least two European countries. Full scholarships available for best-ranked students. "
            "No nationality restrictions. Cannot have previously received an Erasmus Mundus scholarship."
        ),
        coverage=[
            "Full tuition fees",
            "Monthly stipend ~€1,400 for up to 24 months",
            "Travel allowance",
            "Health insurance",
            "Installation costs",
        ],
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters/czech-republic",
        official_source="European Commission / Czech Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes with Czech partners",
    ),
)

# =============================================================================
# PORTUGAL SCHOLARSHIPS
# =============================================================================

PORTUGAL_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Portuguese Foundation for Science and Technology (FCT) PhD Studentships",
        country="Portugal",
        degree_levels="PhD",
        funding_type="Fully Funded",
        deadline="31 March 2026, 5:00 p.m. Lisbon time (regular line)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to Portuguese citizens, EU citizens, citizens of third-party states, stateless individuals, "
            "and political refugee status holders. 1,600 PhD studentships awarded annually. "
            "Must not have previously received FCT PhD studentship. Must not hold a doctoral degree. "
            "Research at academic institutions, R&D units, Associated Laboratories, or private non-profit R&D entities. "
            "Monthly stipend ~€1,359 (Portugal) or higher for abroad. Plus tuition, training, travel, and accident insurance."
        ),
        coverage=[
            "Monthly stipend: €1,359.64 (Portugal), higher for abroad",
            "Tuition fees",
            "Training activities funding",
            "Conference/work presentation support",
            "Personal accident insurance",
            "Travel and relocation (when applicable)",
            "Duration: up to 4 years",
        ],
        official_source_url="https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral",
        official_source="Foundation for Science and Technology (FCT)",
        is_verified=True,
        best_fit="PhD candidates in any scientific area at Portuguese research institutions",
    ),
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Master Degrees — Portuguese Universities",
        country="Portugal",
        degree_levels="Master's (joint degree across 2+ European countries)",
        funding_type="Fully Funded",
        deadline="Varies by programme (typically October-February)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Open to students from all countries worldwide. Joint Master's programmes delivered by "
            "international consortia including Portuguese universities (Lisbon, Porto, NOVA, Coimbra). "
            "Study in at least two European countries. Full scholarships available for best-ranked students. "
            "No nationality restrictions. Cannot have previously received an Erasmus Mundus scholarship."
        ),
        coverage=[
            "Full tuition fees",
            "Monthly stipend ~€1,400 for up to 24 months",
            "Travel allowance",
            "Health insurance",
            "Installation costs",
        ],
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters/portugal",
        official_source="European Commission / Portuguese Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes with Portuguese partners",
    ),
    ScholarshipIngestionRecord(
        name="Nova School of Business and Economics (Nova SBE) Merit Scholarships",
        country="Portugal",
        degree_levels="Bachelor's, Master's, MBA",
        funding_type="Partial to Fully Funded",
        deadline="Varies by programme (typically aligned with admissions rounds)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "All nationalities eligible. Nova SBE is a top-ranked business school (FT MiM top 30, MBA top 40). "
            "Merit scholarships awarded based on academic excellence, leadership, and professional achievement. "
            "Covers 50-100% of tuition plus additional awards of €5,000-€15,000. "
            "Separate scholarship application may be required. Strong focus on business, economics, finance, and management."
        ),
        coverage=[
            "50-100% tuition fee waiver",
            "Additional awards: €5,000-€15,000",
            "Leadership development opportunities",
            "Career services access",
        ],
        official_source_url="https://www.novasbe.unl.pt/en/scholarships",
        official_source="Nova School of Business and Economics (Lisbon)",
        is_verified=True,
        best_fit="Outstanding business and economics students at top-ranked Portuguese business school",
    ),
    ScholarshipIngestionRecord(
        name="University of Porto Merit Scholarships and Funding",
        country="Portugal",
        degree_levels="Bachelor's, Master's, Integrated Master's",
        funding_type="Partial",
        deadline="Varies (SASUP scholarships awarded annually)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "University of Porto (U.Porto) offers merit scholarships for outstanding international students. "
            "SASUP (Social Support Services) awards based on academic excellence regardless of economic situation. "
            "Available for Bachelor's, Master's, and Integrated Master's students. "
            "Also offers scientific research scholarships and Social Support Fund for students in financial need. "
            "International students from Portuguese-speaking countries may have additional funding options."
        ),
        coverage=[
            "Monthly stipends (merit-based)",
            "Tuition fee reductions (varies)",
            "Research scholarships available",
            "Social Support Fund for financial hardship",
        ],
        official_source_url="https://www.up.pt/portal/en/live/student-life/scholarships-and-funding/",
        official_source="University of Porto (U.Porto)",
        is_verified=True,
        best_fit="Outstanding international students at University of Porto",
    ),
    ScholarshipIngestionRecord(
        name="Camões Institute Scholarships — Portuguese Language and Culture",
        country="Portugal",
        degree_levels="Master's, PhD (Research Programme)",
        funding_type="Fully Funded",
        deadline="5-18 May 2026, 5:00 p.m. Lisbon time (2026 cycle)",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "Foreign professors, researchers, and Portuguese nationals residing abroad pursuing advanced studies "
            "in Portuguese language and culture at Portuguese universities. Research Programme: Master's and PhD. "
            "Supports study/research in Portuguese language, culture, translation, and interpreting. "
            "13 scholarships available annually. Must have acceptance/enrolment in Portuguese Master's/PhD programme. "
            "Duration: 2 years (Master's) or 3 years (PhD). Must provide motivation letter, work plan, and recommendations."
        ),
        coverage=[
            "Monthly stipend (amount varies by programme and level)",
            "Tuition support",
            "Travel allowance",
            "Duration: 2 years (Master's) or 3 years (PhD)",
            "Renewable annually based on available budget",
        ],
        official_source_url="https://www.instituto-camoes.pt/en/scholarships",
        official_source="Camoes Institute (Instituto Camoes, I.P.)",
        is_verified=True,
        best_fit="Researchers and professionals in Portuguese language, culture, translation studies",
    ),
    ScholarshipIngestionRecord(
        name="University of Lisbon International Scholarships",
        country="Portugal",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Partial",
        deadline="Varies by faculty and programme",
        deadline_date=None,
        deadline_precision="varies",
        eligibility_summary=(
            "University of Lisbon (ULisboa) offers partial tuition waivers and merit awards for outstanding "
            "international applicants, particularly at Master's level. Faculty-specific scholarships available "
            "in sciences, engineering, humanities, and social sciences. Also hosts Erasmus Mundus programmes."
        ),
        coverage=[
            "Partial tuition fee waivers",
            "Monthly stipends (varies)",
            "Research funding (PhD)",
        ],
        official_source_url="https://www.ulisboa.pt/en/study/fees-and-scholarships",
        official_source="University of Lisbon",
        is_verified=True,
        best_fit="Outstanding international students at University of Lisbon",
    ),
)

# =============================================================================
# COMBINED ADDITIONAL SCHOLARSHIPS
# =============================================================================

ADDITIONAL_VERIFIED_SCHOLARSHIPS: tuple[ScholarshipIngestionRecord, ...] = (
    *UK_SCHOLARSHIPS,
    *CANADA_SCHOLARSHIPS,
    *FRANCE_SCHOLARSHIPS,
    *SPAIN_SCHOLARSHIPS,
    *SINGAPORE_SCHOLARSHIPS,
    *INDIA_SCHOLARSHIPS,
    *USA_SCHOLARSHIPS,
    *ITALY_SCHOLARSHIPS,
    *TAIWAN_SCHOLARSHIPS,
    *SWITZERLAND_SCHOLARSHIPS,
    *AUSTRIA_SCHOLARSHIPS,
    *NETHERLANDS_SCHOLARSHIPS,
    *SWEDEN_SCHOLARSHIPS,
    *AUSTRALIA_SCHOLARSHIPS,
    *SOUTH_KOREA_SCHOLARSHIPS,
    *AUSTRIA_SCHOLARSHIPS_PHASE2,
    *GERMANY_SCHOLARSHIPS,
    *JAPAN_SCHOLARSHIPS,
    *CHINA_SCHOLARSHIPS,
    *IRELAND_SCHOLARSHIPS,
    *NEW_ZEALAND_SCHOLARSHIPS,
    *FINLAND_SCHOLARSHIPS,
    *DENMARK_SCHOLARSHIPS,
    *NORWAY_SCHOLARSHIPS,
    *BELGIUM_SCHOLARSHIPS,
    *HUNGARY_SCHOLARSHIPS,
    *POLAND_SCHOLARSHIPS,
    *CZECH_REPUBLIC_SCHOLARSHIPS,
    *PORTUGAL_SCHOLARSHIPS,
)
