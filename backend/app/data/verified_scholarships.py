"""Canonical catalogue of verified scholarship records.

Add new verified records here only after checking their official source URL.
The ingestion service validates this catalogue before it writes to the database.
"""

from datetime import date

from ..services.scholarship_ingestion import ScholarshipIngestionRecord


EMJM_OFFICIAL_SOURCE_URL = "https://erasmus-plus.ec.europa.eu"
GKS_OFFICIAL_SOURCE_URL = "https://www.studyinkorea.go.kr"
DAAD_OFFICIAL_SOURCE_URL = "https://www.daad.de"
ICCR_OFFICIAL_SOURCE_URL = "https://a2ascholarships.iccr.gov.in"
MEXT_OFFICIAL_SOURCE_URL = "https://www.studyinjapan.go.jp"
EIFFEL_OFFICIAL_SOURCE_URL = "https://www.campusfrance.org/en/the-france-excellence-eiffel-scholarship-program"
SWISS_ESKAS_OFFICIAL_SOURCE_URL = "https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships"
FRANCE_CHARPAK_OFFICIAL_SOURCE_URL = "https://www.inde.campusfrance.org/france-excellence-charpak-scholarship-program"
MOPGA_OFFICIAL_SOURCE_URL = "https://www.campusfrance.org/en/mopga-make-our-planet-great-again-funding-programs"
DEUTSCHLANDSTIPENDIUM_OFFICIAL_SOURCE_URL = "https://www.deutschlandstipendium.de/"
STUDY_IN_INDIA_OFFICIAL_SOURCE_URL = "https://www.studyinindia.gov.in/"
JASSO_OFFICIAL_SOURCE_URL = "https://www.jasso.go.jp/en/ryugaku/scholarship_j/shoreihi/about.html"
POSCO_OFFICIAL_SOURCE_URL = "https://www.postf.org/en/asia/purpose"
ETH_ESOP_OFFICIAL_SOURCE_URL = "https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html"
EPFL_OFFICIAL_SOURCE_URL = "https://www.epfl.ch/education/master/master-excellence-fellowships/"
MSCA_OFFICIAL_SOURCE_URL = "https://marie-sklodowska-curie-actions.ec.europa.eu/actions/postdoctoral-fellowships"
ERASMUS_PLUS_OFFICIAL_SOURCE_URL = "https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/studying-abroad"


VERIFIED_SCHOLARSHIPS = (
    ScholarshipIngestionRecord(
        name="Erasmus Mundus Joint Masters (EMJM)",
        country="EU (multiple)",
        degree_levels="PG only (Joint Master's)",
        funding_type="Fully Funded",
        deadline=(
            "Varies by consortium/programme - typically Dec-Feb for a Sept/Oct intake; no single central deadline"
        ),
        deadline_date=None,
        deadline_precision="unknown",
        application_period=(
            "Varies by consortium/programme - typically Dec-Feb for a Sept/Oct intake; no single central deadline"
        ),
        eligibility_summary=(
            "Bachelor's degree (3-4 years) in a relevant field, or final-year students may apply if the programme "
            "allows (must graduate before the program starts). No fixed CGPA requirement - selection weighs "
            "motivation, relevant background, and clarity of goals more heavily than grades."
        ),
        coverage=[
            "Full tuition, approx. EUR 1,400/month stipend, travel allowance, installation allowance "
            "(exact figures vary slightly by consortium)"
        ],
        required_documents=[
            "Academic transcripts/certificates (Bachelor's, HSC, SSC)",
            "CV",
            "Motivation letter",
            "2 recommendation letters (typical)",
            "Proof of English proficiency",
        ],
        official_source_url=EMJM_OFFICIAL_SOURCE_URL,
        official_source="European Commission (Erasmus+)",
        is_verified=True,
        english_requirement=(
            "IELTS/TOEFL, OR a Medium of Instruction (MOI) certificate from a prior English-medium degree - "
            "accepted by many (not all) programmes as a substitute for a test score"
        ),
        best_fit=(
            "Accessible for average-CGPA applicants with a strong personal motivation/story - no fixed CGPA "
            "cutoff, evaluated more holistically than most government scholarships"
        ),
        notes=(
            "This is a category of 50+ separate Joint Master's programmes (each its own university consortium), "
            "not one application. Applicants pick and apply directly to specific joint-programme(s) via the "
            "Erasmus Mundus Catalogue on erasmus-plus.ec.europa.eu. Deadlines are set per-programme."
        ),
        legacy_titles=("erasmus mundus scholarship", "erasmus mundus joint masters (emjm)"),
        preferred_id=1,
        image_url="https://erasmus-plus.ec.europa.eu/sites/default/files/styles/hero_desktop/public/2025-01/emjm_students_european_campus.jpg",
        image_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
        image_source_type="official_scholarship",
        image_verified_at=date(2025, 6, 26),
        image_alt_text="Erasmus Mundus Joint Masters students on a European university campus",
    ),
    ScholarshipIngestionRecord(
        name="Global Korea Scholarship (GKS)",
        country="South Korea",
        degree_levels="UG (Bachelor's/Associate)",
        funding_type="Fully Funded",
        deadline=None,
        deadline_date=None,
        deadline_precision="unknown",
        eligibility_summary=(
            "Citizen of an NIIED-designated country; parents must not hold Korean citizenship; high school "
            "graduate or expecting graduation; undergraduate applicants usually have age and CGPA requirements "
            "that change each cycle."
        ),
        eligibility=[
            "Citizen of an NIIED-designated country; parents must not hold Korean citizenship.",
            "High school graduate or expecting graduation.",
            "Undergraduate applicants usually have age and CGPA requirements that change each cycle.",
        ],
        coverage=[
            "Round-trip airfare; tuition support; Korean language training; monthly stipend; settlement "
            "allowance; medical insurance and other official benefits depending on track."
        ],
        required_documents=[
            "Application form",
            "Personal statement",
            "Study plan",
            "Recommendation letter",
            "Graduation certificate",
            "Transcript",
            "Proof of citizenship",
            "Required medical documents",
        ],
        official_source_url=GKS_OFFICIAL_SOURCE_URL,
        is_verified=True,
        official_source="National Institute for International Education (NIIED)",
        english_requirement=(
            "Not mandatory. TOPIK or TOEFL/IELTS scores may provide additional evaluation advantage."
        ),
        requirements=[
            "English test scores are not mandatory.",
            "TOPIK or TOEFL/IELTS scores may provide additional evaluation advantage.",
        ],
        application_method=["Embassy Track", "University Track"],
        best_fit="Students seeking fully funded undergraduate opportunities in South Korea.",
        notes=(
            "Formerly known as KGSP. Current official name is Global Korea Scholarship (GKS). Applicants must "
            "verify yearly announcements from the official Study in Korea website."
        ),
        legacy_titles=("kgsp (korean government scholarship)", "global korea scholarship (gks)"),
        image_url="https://www.studyinkorea.go.kr/en/community/data/file/2025/01/gks_scholarship_banner.jpg",
        image_source_url="https://www.studyinkorea.go.kr/en/plan/scholarship.do",
        image_source_type="official_scholarship",
        image_verified_at=date(2025, 4, 5),
        image_alt_text="Global Korea Scholarship (GKS) students at a Korean university",
    ),
    ScholarshipIngestionRecord(
        name="DAAD Scholarship",
        country="Germany",
        degree_levels="Mostly Master's/PhD (a few UG-eligible programmes exist but are rare)",
        funding_type="Fully Funded",
        deadline=(
            "Varies by programme - Master's typically ~30 Oct; PhD programmes vary (3 Sept or 21 Oct for 2026/27 cycle). "
            "Deadlines updated annually in Q2."
        ),
        deadline_date=None,
        deadline_precision="unknown",
        application_period=(
            "Varies by programme - typically Sept-Nov for a Oct/Nov deadline; check DAAD database per programme"
        ),
        eligibility_summary=(
            "Most recent degree completed no more than 6 years before the deadline. No general age limit. Exact "
            "GPA/academic requirements are set per individual programme, not centrally by DAAD."
        ),
        eligibility=[
            "Most recent degree completed no more than 6 years before the deadline",
            "No general age limit",
            "Exact GPA/academic requirements are set per individual programme, not centrally by DAAD",
        ],
        coverage=[
            "Monthly stipend: EUR 992 (Master's) / EUR 1,300 (PhD/doctoral) - figures current as of 2025/26",
            "Health, accident, and personal liability insurance",
            "Travel allowance (upon application only)",
            "Annual study/research allowance: EUR 460",
        ],
        required_documents=[
            "Online application form (via DAAD portal)",
            "CV",
            "Motivation letter",
            "Academic transcripts and certificates",
            "Letter of recommendation",
            "Language certificates (German and/or English depending on programme)",
            "Research proposal (for PhD/research programmes)",
        ],
        region="Europe",
        duration="10-24 months for Master's programmes; up to 4 years for PhD (initial award up to 3 years, extendable)",
        official_source_url=DAAD_OFFICIAL_SOURCE_URL,
        official_source="DAAD — German Academic Exchange Service",
        catalogue_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/",
        official_updates_url="https://www.daad-bangladesh.org/en/",
        is_verified=True,
        english_requirement=(
            "Depends on programme - many require IELTS/TOEFL for English-taught programmes; some require German "
            "proficiency instead or in addition"
        ),
        requirements=[
            "Depends on programme - many require IELTS/TOEFL for English-taught programmes",
            "Some require German proficiency instead or in addition",
        ],
        application_method=[
            "Apply directly via DAAD scholarship database (daad.de)",
            "Select programme filtered by Bangladesh + degree level",
            "Submit application through the DAAD portal before the programme-specific deadline",
        ],
        selection_notes=(
            "Selection by independent committees assessing professional qualifications, study/research project quality, "
            "and applicant potential. Special circumstances (e.g. disability) may be considered."
        ),
        program_type="Scholarship database (100+ individual programmes)",
        best_fit=(
            "Best for Master's/PhD applicants who already have a specific field/programme in mind - not one "
            "unified scholarship, requires researching individual programme listings"
        ),
        notes=(
            "DAAD is NOT a single scholarship - it is a database of 100+ separately funded programmes, each with "
            "its own eligibility/deadline/coverage. Figures above are current as of 2025/26. Must check the specific "
            "programme on DAAD's Funding Guide database (daad.de), filtered by Bangladesh + degree level, before "
            "advising a user. Funded by the German Federal Foreign Office."
        ),
        legacy_titles=("daad scholarship",),
        preferred_id=3,
        image_url="https://www.daad.de/shared/study/scholarships/2025/scholarship-banner-students-campus.jpg",
        image_source_url="https://www.daad.de/en/studying-in-germany/scholarships/daad-scholarships",
        image_source_type="official_provider",
        image_verified_at=date(2025, 4, 10),
        image_alt_text="DAAD scholarship recipients at a German university campus",
    ),
    ScholarshipIngestionRecord(
        name="ICCR Scholarship (Suborno Jayanti Scheme)",
        country="India",
        degree_levels="UG/PG/PhD",
        funding_type="Fully Funded",
        deadline="27 February - 22 April 2026 (AY 2026-27 application window)",
        deadline_date=date(2026, 4, 22),
        deadline_precision="exact",
        application_period="27 February - 22 April 2026 (AY 2026-27)",
        eligibility_summary=(
            "18-30 years old for UG/PG; PhD applicants must be under 45 (as of 1 July of the academic year). "
            "Must submit SSC/HSC-equivalent mark sheets and transcripts in English. Excludes Medicine/Paramedical/Nursing, "
            "Fashion, Law, and integrated 5-year BA-LLB/BSc-MSc programmes."
        ),
        eligibility=[
            "18-30 years old for UG/PG (as of 1 July of the academic year)",
            "PhD applicants must be under 45 (as of 1 July of the academic year)",
            "Must submit SSC/HSC-equivalent mark sheets and transcripts in English",
            "Excludes Medicine/Paramedical/Nursing, Fashion, Law, and integrated 5-year programmes",
        ],
        coverage=[
            "Full tuition at an Indian govt./public university",
            "Hostel accommodation (subject to availability; campus hostel mandatory if available)",
            "Monthly stipend: INR 18,000 (UG) / 20,000 (PG) / 22,000 (PhD)",
            "Monthly House Rent Allowance: INR 6,500 (UG) / 7,000 (PG) / 12,500 (PhD)",
            "Annual Contingent Grant: INR 5,500 (UG) / 7,000 (PG) / 10,000 (PhD)",
            "One-time thesis/dissertation allowance: INR 7,000",
        ],
        required_documents=[
            "SSC/HSC (or equivalent) mark sheets and transcripts in English",
            "Proof of English proficiency (500-word essay on an A2A-assigned topic, OR TOEFL/IELTS score)",
            "Medical insurance policy with minimum INR 5,00,000 sum assured",
            "Passport copy (minimum 2 years validity as of 1 July of the academic year)",
            "Photograph",
        ],
        region="South Asia",
        duration="Up to 3 years for PhD (extendable up to 2 years at discretion of university); varies by programme for UG/PG",
        official_source_url=ICCR_OFFICIAL_SOURCE_URL,
        official_source="Indian Council for Cultural Relations (ICCR)",
        catalogue_url="https://iccr.gov.in/scholarship/iccr-scholarship/iccr-scholarship-schemes",
        official_updates_url="https://a2ascholarships.iccr.gov.in/home/notificationList/34",
        is_verified=True,
        english_requirement=(
            "Mandatory 500-word English essay on a topic assigned inside the A2A portal - applies regardless "
            "of IELTS/TOEFL. Test scores are additional proof, not a substitute for the essay."
        ),
        requirements=[
            "Mandatory 500-word English essay on a topic assigned inside the A2A portal",
            "IELTS/TOEFL scores are additional proof, not a substitute for the essay",
            "Passport must have minimum 2 years validity as of 1 July of the academic year",
            "Medical insurance policy with minimum INR 5,00,000 sum assured required",
        ],
        application_method=[
            "Step 1: Register at sjsdhaka.gov.in (Bangladesh-specific Suborno Jayanti portal) FIRST",
            "Step 2: Register at a2ascholarships.iccr.gov.in (ICCR A2A portal)",
            "Select up to 5 university preferences in order of preference",
            "Submit application before the deadline (direct A2A registration without Step 1 gets rejected)",
        ],
        selection_notes=(
            "Selection by Indian Missions/Posts. Offer letter issued by Indian Mission; applicant must accept/reject "
            "within 7 days on A2A Portal. Medical fitness upload required within prescribed time limit after acceptance."
        ),
        program_type="Government scholarship (500 seats for Bangladesh under Suborno Jayanti)",
        best_fit=(
            "Accessible - 500 seats for Bangladesh alone under Suborno Jayanti, covers UG through PhD, workable "
            "for students without IELTS since the essay route is standard, not a fallback"
        ),
        notes=(
            "Two-step registration required: sjsdhaka.gov.in (Bangladesh-specific portal) FIRST, then "
            "a2ascholarships.iccr.gov.in - direct A2A registration without the first step gets rejected. Up to 5 "
            "university preferences allowed. Stipend and allowance figures are per the official ICCR Policy Guidelines "
            "for AY 2026-27. Scholarship allowances disbursed based on academic progress; failure to promote to next "
            "level means no allowances until backlog cleared."
        ),
        legacy_titles=("iccr scholarship", "iccr scholarship (suborno jayanti scheme)"),
        preferred_id=2,
        image_url="https://a2ascholarships.iccr.gov.in/assets/images/header-banner.jpg",
        image_source_url="https://a2ascholarships.iccr.gov.in",
        image_source_type="official_scholarship",
        image_verified_at=date(2025, 3, 15),
        image_alt_text="ICCR Scholarship banner showing international students",
    ),
    ScholarshipIngestionRecord(
        name="MEXT (Monbukagakusho) Scholarship",
        country="Japan",
        degree_levels=(
            "UG/PG/PhD - separate application tracks: Undergraduate, Research Student (leads to Master's/PhD), "
            "Teacher Training, Japanese Studies, College of Technology"
        ),
        funding_type="Fully Funded",
        deadline=(
            "Varies by track - Embassy Recommendation (Research Students): April-June annually; "
            "varies for other tracks. For 2027 cycle, recruitment is April-May 2026."
        ),
        deadline_date=None,
        deadline_precision="approximate",
        application_period="Embassy Recommendation (Research Students): April-June annually",
        eligibility_summary=(
            "Undergraduate track: age 17-25 as of April 1 of the scholarship year, completed (or completing) "
            "11 years of schooling equivalent to high school. Research Student track (leads to Master's/PhD): age "
            "below 35. Bangladeshi nationality required for Embassy-recommended tracks."
        ),
        eligibility=[
            "Research Students: Bangladeshi citizen, born on or after April 2, 1991 (for 2026 cycle), "
            "Bachelor's degree or higher, study in same or related field",
            "Undergraduate: age 17-25 as of April 1 of scholarship year, completed 11-12 years of schooling",
        ],
        coverage=[
            "Full tuition, monthly stipend approx. 117,000-148,000 JPY (undergraduate is at the lower end), "
            "round-trip economy airfare Dhaka-Japan, 6 months-1 year Japanese language training included"
        ],
        required_documents=[
            "Application form (use current year's MEXT form)",
            "Placement Preference Application Form",
            "Field of Study and Research Plan",
            "Academic transcript for all academic years of university attended",
            "Certificate of graduation or degree certificate of the university attended",
            "Recommendation letter from the president/dean or academic advisor at current/last university attended",
            "Medical Certificate (filled by a professional medical doctor)",
        ],
        region="East Asia",
        duration=(
            "Research Students: 2 years for regular course (6 months preparatory education added if needed). "
            "Undergraduate: 5 years including Japanese language training (7 years for medicine/dentistry/pharmacy/veterinary science). "
            "Standard: Master's 2 years, Doctoral 3 years (4 years for some fields)."
        ),
        official_source_url=MEXT_OFFICIAL_SOURCE_URL,
        official_source="Ministry of Education, Culture, Sports, Science and Technology (MEXT), Japan",
        catalogue_url="https://www.studyinjapan.go.jp/en/planning/scholarships/mext-scholarships/",
        official_updates_url="https://www.bd.emb-japan.go.jp/en/education/scholarshipNotice.html",
        is_verified=True,
        english_requirement=(
            "A written English exam is part of the selection process itself (not a pre-submitted score like IELTS) "
            "- no separate IELTS/TOEFL required for the Embassy track. STEM majors also sit Math/Physics/Chemistry exams."
        ),
        requirements=[
            "Application Form (use current year's MEXT form)",
            "Placement Preference Application Form",
            "Field of Study and Research Plan",
            "Academic transcript for all academic years of university attended",
            "Certificate of graduation or degree certificate",
            "Recommendation letter from the president/dean or academic advisor at current/last university",
            "Medical Certificate (filled by a professional medical doctor)",
        ],
        application_method=[
            "Embassy Recommendation: Apply through Bangladesh Ministry of Education SHED portal, then screened by "
            "Embassy of Japan Dhaka (written exam + interview)",
            "University Recommendation: Apply directly to a specific Japanese university, which then recommends to MEXT",
        ],
        selection_notes=(
            "Selection by Embassy of Japan Dhaka (written exam + interview) for Embassy track; by MEXT Tokyo for University track. "
            "Candidates who pass first screening must request provisional acceptance from Japanese universities by September 1."
        ),
        program_type=(
            "Government scholarship (multiple tracks: Research, Undergraduate, Teacher Training, Japanese Studies, "
            "College of Technology, Specialized Training College)"
        ),
        best_fit=(
            "Strong fit for academically strong STEM applicants comfortable with a written entrance exam, not "
            "just document review"
        ),
        notes=(
            "Two distinct application paths for a Bangladeshi UG applicant: (1) Embassy Recommendation - apply via "
            "the Bangladesh Ministry of Education SHED portal, screened by the Embassy of Japan Dhaka (written exam "
            "+ interview in Baridhara); (2) University Recommendation - apply directly to a specific Japanese "
            "university, which then recommends the candidate to MEXT (eligibility/deadline set by that university). "
             "Clarify which path a user means before giving deadline information."
        ),
        image_url="https://www.studyinjapan.go.jp/applies/wp-content/uploads/2025/02/mext_scholarship_students_japan.jpg",
        image_source_url="https://www.studyinjapan.go.jp/en/planning/scholarships/mext-scholarships/",
        image_source_type="official_scholarship",
        image_verified_at=date(2025, 5, 20),
        image_alt_text="MEXT scholarship students at a Japanese university",
    ),
    ScholarshipIngestionRecord(
        name="Eiffel Excellence Scholarship",
        country="France",
        degree_levels="PG/PhD only (Master's and Doctoral)",
        funding_type="Monthly stipend, health insurance, and some travel costs",
        deadline=(
            "Call opens ~October 1, national deadline ~January 8 (exact dates shift slightly each year)"
        ),
        deadline_date=date(2026, 1, 8),
        deadline_precision="month",
        eligibility_summary=(
            "Master's applicants must be 29 or under; PhD applicants 35 or under. Cannot be currently studying "
            "in France. Cannot combine with another French government scholarship."
        ),
        coverage=["Monthly stipend (amount set annually by Campus France), health insurance, some travel costs"],
        required_documents=[
            "Academic transcripts",
            "CV",
            "Research/study project",
            "Recommendation letters",
            "Exact list set by the host French institution",
        ],
        official_source_url=EIFFEL_OFFICIAL_SOURCE_URL,
        official_source="Campus France",
        is_verified=True,
        english_requirement=(
            "Not centrally specified - varies by the specific Master's/PhD programme (French or English-taught)"
        ),
        best_fit=(
            "Only for applicants who already have to be selected/nominated by a French university - cannot apply "
            "directly as an individual"
        ),
        notes=(
            "IMPORTANT: Students CANNOT apply directly. A French higher education institution must select and submit "
            "the application on the student's behalf. A student must first get an offer/interest from a French "
            "university, then ask that university to nominate them for Eiffel."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Swiss Government Excellence Scholarship (ESKAS)",
        country="Switzerland",
        degree_levels=(
            "PhD/Postdoctoral research and Art Master's only - NOT for standard Bachelor's/Master's study"
        ),
        funding_type="Monthly stipend, housing grant, health insurance, and travel card",
        deadline=(
            "Applications open 20 August 2026; country-specific deadlines vary (September to December 2026). "
            "Check go.eskas.ch for exact deadline by country of citizenship."
        ),
        deadline_date=None,
        deadline_precision="unknown",
        eligibility=[
            "Research/PhD: Master's degree or equivalent completed by 31 July 2027 (ETH Zurich: 30 June 2027)",
            "Date of birth after 31 December 1991",
            "Detailed research plan with timeline specifying key milestones and activities",
            "Letter of support from Swiss academic supervisor required (including short CV)",
            "If already in Switzerland: date of entry must not be earlier than 1 August 2026",
            "Art Master's: Bachelor's degree completed by 31 July 2027; must not already hold a Master's degree",
            "Art Master's: Admission letter or proof of application from Swiss University of the Arts or Music",
        ],
        eligibility_summary=(
            "Research/PhD applicants must already hold a Master's degree. Must secure a nomination/support letter "
            "from an academic supervisor at a Swiss institution BEFORE applying. Must not have lived in Switzerland "
            "for more than 12 months prior."
        ),
        coverage=[
            "Monthly stipend CHF 2,450 (all scholarship types)",
            "CHF 600 one-time rental deposit",
            "Compulsory health insurance covered (non-EU/EFTA scholars)",
            "One-year Half-Fare Travelcard for Swiss public transport",
            "Return flight allowance (non-EU/EFTA, amount varies by country)",
            "Tuition fees NOT covered - universities may charge CHF 600-2,000/semester",
        ],
        requirements=[
            "Complete CV including educational background, degrees, awards, positions, publications, teaching and practical experience",
            "Letter of motivation (max. 2 pages): reasons for stay in Switzerland, significance for future career",
            "Research proposal on FCS/ESKAS form (max. 5 pages including summary for non-specialists)",
            "Letter of support from an academic supervisor at a Swiss higher education institution",
            "Short CV (max. 2 pages) from the academic supervisor",
            "Two professors' email addresses (for recommendation letters submitted via system)",
            "Copies of certificates and transcripts from previous universities (with certified translations if not in EN/FR/IT/DE)",
            "Copy of passport (dual citizens submit both)",
            "Copy of residence permit or registration confirmation if already residing in Switzerland",
        ],
        required_documents=[
            "Complete CV including educational background, degrees, awards, positions, publications, teaching and practical experience",
            "Letter of motivation (max. 2 pages): reasons for stay in Switzerland, significance for future career",
            "Research proposal on FCS/ESKAS form (max. 5 pages including summary for non-specialists)",
            "Letter of support from an academic supervisor at a Swiss higher education institution",
            "Short CV (max. 2 pages) from the academic supervisor",
            "Two professors' email addresses (for recommendation letters submitted via system)",
            "Copies of certificates and transcripts from previous universities (with certified translations if not in EN/FR/IT/DE)",
            "Copy of passport (dual citizens submit both)",
            "Copy of residence permit or registration confirmation if already residing in Switzerland",
        ],
        duration=(
            "Research Fellowship: 6-12 months (no extensions). PhD: 12 months, renewable twice up to 36 months "
            "(subject to academic progress). Art Master's: 12 months, extendable up to 21 months depending on "
            "programme and ECTS credits. All start 1 September 2027."
        ),
        application_period=(
            "Applications open 20 August 2026; country-specific deadlines published at go.eskas.ch "
            "(typically September to December 2026 depending on country of origin)"
        ),
        official_updates_url="https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships",
        region="Europe",
        selection_notes=(
            "Selection criteria: Academic profile, research competence, and motivation; originality and methodological "
            "quality of the project; quality of supervision and potential for future collaboration. Art scholarships "
            "assess artistic profile, qualifications, motivation, and portfolio quality. Decisions announced by end of May."
        ),
        program_type="Government scholarship (Federal Commission for Scholarships for Foreign Students)",
        official_source_url=SWISS_ESKAS_OFFICIAL_SOURCE_URL,
        official_source="State Secretariat for Education, Research and Innovation (SERI), Switzerland",
        is_verified=True,
        english_requirement="Not centrally specified - depends on the host institution/programme",
        best_fit=(
            "Only for PhD-track or postgraduate researchers who already have an academic connection in Switzerland "
            "- not usable for undergraduate applicants"
        ),
        notes=(
            "Application now fully online via go.eskas.ch (embassy paper submission discontinued as of 2026-27 "
            "cycle). Requires securing a Swiss academic mentor/supervisor BEFORE applying - this is the hardest "
            "and most time-consuming step, start it months in advance."
        ),
    ),
    ScholarshipIngestionRecord(
        name="France Excellence Charpak Scholarship Program",
        country="France",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="Varies by track (typically spring/summer)",
        deadline_date=None,
        deadline_precision="unknown",
        eligibility=[
            "Indian citizen or hold OCI card",
            "Bachelor's: age 23 or younger at time of application; currently enrolled or completed studies at Indian senior secondary school",
            "Bachelor's: admission to French institution required before applying",
            "Master's: age 30 or younger; currently enrolled or completed studies at Indian institution of higher education",
            "Master's: full-time master's degree in France (semester exchange, internships, research projects not eligible)",
            "Master's: must not have previously been awarded Charpak Master scholarship",
            "Master's: must not be a PhD student or intend to complete master's thesis/training/research in France",
            "Course must take place in France (if part takes place in another country, scholarship will not cover that period)",
        ],
        eligibility_summary=(
            "Indian students admitted to French institutions; age \u226323 (Bachelor's) or \u226330 (Master's); "
            "strong academic record."
        ),
        coverage=[
            "Monthly living allowance €860",
            "Exemption of visa and Campus France procedure fees",
            "Student social security and additional health insurance (mutuelle)",
            "Assistance finding affordable student accommodation (priority CROUS access)",
            "Meal discount at university restaurants (€1 meals)",
            "Access to social and cultural activities organized by Campus France",
            "Travel expenses from India to France NOT covered",
        ],
        required_documents=[
            "Passport size photograph",
            "Copy of passport (first page with photo and expiry date)",
            "Curriculum Vitae (maximum 2 pages)",
            "Copy of admission/acceptance letter from French higher education institution",
            "Mark sheets and degree certificates (XII, Bachelor's, Master's - including ongoing semesters)",
            "French language certificate, if any (DELF/DALF)",
            "Document of employment/internship record, if applicable",
            "Letter(s) of recommendation from current Indian university/employer or last attended institution",
        ],
        requirements=[
            "Passport size photograph",
            "Copy of passport (first page with photo and expiry date)",
            "Curriculum Vitae (maximum 2 pages)",
            "Copy of admission/acceptance letter from French higher education institution",
            "Mark sheets and degree certificates (XII, Bachelor's, Master's - including ongoing semesters)",
            "French language certificate, if any (DELF/DALF)",
            "Document of employment/internship record, if applicable",
            "Letter(s) of recommendation from current Indian university/employer or last attended institution",
        ],
        english_requirement="Not mandatory - knowledge of French is an asset but not required",
        duration=(
            "Bachelor's: duration of the bachelor's programme in France. Master's: 1-2 years "
            "(renewable once for second year based on results)."
        ),
        application_period="Varies by track - typically spring/summer",
        official_updates_url="https://www.inde.campusfrance.org/france-excellence-charpak-scholarship-program",
        region="Europe",
        selection_notes=(
            "Round 1: Complete applications evaluated by selection committee on academic excellence, consistency, "
            "quality of statement of purpose, and overall profile. No minimum CGPA or percentage required. "
            "Round 2: Shortlisted candidates called for Online Interview (typically April). Plagiarism check on SOP; "
            "AI-generated content discouraged and may result in disqualification."
        ),
        program_type="Government scholarship (French Embassy in India / Campus France India)",
        application_method=[
            "Online via Campus France India portal at scholarship.institutfrancaisindia.in",
            "Must have applied for admission to French institution before applying for scholarship",
            "Only one online application per applicant (multiple applications result in disqualification)",
            "Shortlisted candidates attend online interview at British embassy/high commission",
        ],
        official_source_url=FRANCE_CHARPAK_OFFICIAL_SOURCE_URL,
        official_source="Campus France India (French Embassy in India)",
        is_verified=True,
        best_fit="Indian students seeking partial funding for Bachelor's or Master's studies in France.",
        notes=(
            "Four sub-programmes: Bachelor's, Master's, Summer Training/Research Internship, and Exchange. "
            "India-specific but representative of French government scholarship offerings in South Asia."
        ),
    ),
    ScholarshipIngestionRecord(
        name="MOPGA Visiting Fellowship Program",
        country="France",
        degree_levels="Post-doctoral / Early Career Research",
        funding_type="Fully Funded",
        deadline="Typically December–January annually",
        deadline_date=None,
        deadline_precision="month",
        eligibility=[
            "PhD obtained within the last 5 years",
            "Non-French citizens (foreign nationals)",
            "Must not have resided in France for more than 90 days during the 12 months prior to application",
            "Research project must align with MOPGA themes: Earth systems, climate change and sustainability, energy transition, societal challenges of environmental issues, or One Health (human, animal and ecosystem health)",
            "Must secure a hosting agreement with a French research institution/laboratory",
            "Early career researchers (post-doctoral) preferred",
        ],
        eligibility_summary=(
            "PhD obtained <5 years ago; non-French citizens; not resided in France >90 days during specified "
            "period; research in climate/environment fields."
        ),
        coverage=[
            "Monthly allowance of €2,500",
            "Moving grant of €500",
            "Social security registration",
            "Complementary health insurance",
        ],
        required_documents=[
            "CV (max 4 pages)",
            "PhD diploma or certificate of completion",
            "Research project description (2,000–4,500 characters per section)",
            "Host laboratory agreement from French research institution",
            "1–3 recommendation letters",
        ],
        requirements=[
            "CV (max 4 pages)",
            "PhD diploma",
            "Research project description aligned with MOPGA themes",
            "Host laboratory agreement",
            "1–3 recommendation letters",
        ],
        english_requirement="Not centrally specified - varies by host institution and research project language",
        duration="12 months",
        application_period="Calls for application launched yearly in September; applicants notified by email in May; fellowship starts between September and December",
        official_updates_url="https://www.campusfrance.org/en/make-our-planet-great-again-en",
        region="Europe",
        selection_notes=(
            "Selection based on scientific excellence of the project, relevance to MOPGA themes "
            "(Earth systems, climate change, energy transition, societal challenges, One Health), "
            "quality of the host laboratory, and potential for future collaboration. "
            "Applicants notified by email in May."
        ),
        program_type="Government research fellowship (French Ministry for Europe and Foreign Affairs, implemented by Campus France)",
        official_source_url=MOPGA_OFFICIAL_SOURCE_URL,
        official_source="Campus France (French Ministry for Europe and Foreign Affairs)",
        is_verified=True,
        application_method=["Online via Campus France portal"],
        best_fit="Early career researchers in climate/environment fields seeking a 12-month research stay in France.",
        notes=(
            "Field-specific (Earth systems, climate change, energy transition, societal challenges, One Health). "
            "Requires a French host laboratory. Since 2018, has supported 380+ researchers from 78 countries."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Deutschlandstipendium (Germany Scholarship)",
        country="Germany",
        degree_levels="Bachelor's, Master's",
        funding_type="Partial",
        deadline="Varies by university (typically spring/summer for winter semester)",
        deadline_date=None,
        deadline_precision="unknown",
        eligibility=[
            "Enrolled at a public or state-recognized university in Germany",
            "First-semester and higher-semester students eligible",
            "All nationalities can apply",
            "High academic achievement (good grades and study performance)",
            "Social commitment and/or personal achievements (e.g., overcoming social/family obstacles)",
            "No means-testing (income-independent)",
        ],
        eligibility_summary=(
            "All nationalities; enrolled at public or state-recognized German university; high academic achievement; "
            "social commitment; personal achievements."
        ),
        coverage=[
            "€300 per month (€150 federal + €150 private sponsor) for minimum 2 semesters, renewable up to standard study period",
        ],
        required_documents=[
            "Application form (from university)",
            "CV",
            "Motivation letter",
            "Academic transcripts",
            "Language proficiency certificate (varies by program)",
            "Recommendation letters",
            "Passport copy",
            "University admission letter",
        ],
        requirements=[
            "Application form",
            "CV",
            "Motivation letter",
            "Academic transcripts",
            "Language proficiency certificate",
            "Recommendation letters",
            "Passport copy",
            "University admission letter",
        ],
        english_requirement="Not centrally specified - varies by university and study program (German or English)",
        duration="Minimum 2 semesters, renewable up to standard period of study (Regelstudienzeit)",
        application_period="Varies by university - check directly with the university's scholarship office",
        official_updates_url="https://www.deutschlandstipendium.de/deutschlandstipendium/de/services/english/the-deutschlandstipendium-best-of-both-worlds-for-students.html",
        region="Europe",
        selection_notes=(
            "Selection criteria: Academic achievement (grades), social commitment, and personal achievements "
            "(overcoming challenges in social or family background). Selection is made by individual universities, "
            "not centrally. Each university has its own application deadlines and selection process. "
            "Non-financial support (mentoring, networking, internships) often provided by sponsors."
        ),
        program_type="Public-private partnership scholarship (Federal Government + private sponsors, administered by universities)",
        official_source_url=DEUTSCHLANDSTIPENDIUM_OFFICIAL_SOURCE_URL,
        official_source="Federal Ministry of Education and Research (BMBF/BMFTR) + Private Sponsors",
        is_verified=True,
        application_method=["Directly through participating German university"],
        best_fit="High-achieving students at German universities seeking monthly financial support and networking.",
        notes=(
            "Largest public-private scholarship program in Germany (33,500+ recipients in 2025); "
            "includes mentoring, networking, and internship opportunities; not means-tested. "
            "Scholarship funds do not count towards BAföG; no social insurance contributions payable."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Study in India (SII) Scholarship",
        country="India",
        degree_levels="Undergraduate, Postgraduate, Diploma, Certificate",
        funding_type="Partial",
        deadline="Varies by institution and admission cycle",
        deadline_date=None,
        deadline_precision="unknown",
        eligibility=[
            "International students from partner countries (South Asia, South-East Asia, Middle East, Africa)",
            "Merit-based selection",
            "Entry-level eligibility: 10+2 years of schooling for undergraduate, Bachelor's degree for postgraduate, Master's degree for doctoral programmes",
            "Specific eligibility criteria vary by institute and programme",
            "NRIs are eligible for Study in India program but NOT for SII Scholarship",
        ],
        eligibility_summary=(
            "International students from partner countries (South Asia, South-East Asia, Middle East, Africa); merit-based."
        ),
        coverage=[
            "Tuition fee waivers/concessions up to USD 3,200 per annum at partner institutions",
        ],
        required_documents=[
            "Academic transcripts",
            "Passport",
            "Proof of nationality",
            "Admission offer",
        ],
        requirements=[
            "Academic transcripts",
            "Passport",
            "Proof of nationality",
            "Admission offer",
        ],
        english_requirement="Not centrally specified - varies by institution and programme",
        duration=(
            "Undergraduate: 3-5 years (depending on discipline). Postgraduate: 1-2 years. "
            "Doctoral: 3-5 years. Diploma/Certificate: varies by programme."
        ),
        application_period="Varies by institution and admission cycle",
        official_updates_url="https://www.studyinindia.gov.in/scholarships&fellowships",
        region="South Asia",
        selection_notes=(
            "Merit-based selection. Entry-level eligibility: 10+2 years of schooling for undergraduate, "
            "Bachelor's degree for postgraduate, Master's degree for doctoral programmes. "
            "Specific eligibility criteria vary by institute and programme."
        ),
        program_type="Government scholarship (Ministry of Education, implemented by EdCIL India Limited)",
        application_method=[
            "Online via Study in India portal at studyinindia.gov.in",
            "Register and get SII ID (compulsory for tracking foreign student journey)",
            "Explore courses and submit applications to chosen institutes",
            "Accept offer letter and apply for visa/student e-visa with SII ID",
        ],
        official_source_url=STUDY_IN_INDIA_OFFICIAL_SOURCE_URL,
        official_source="Ministry of Education, Government of India (implemented by EdCIL India Limited)",
        is_verified=True,
        best_fit="International students from partner countries seeking partial funding for studies in India.",
        notes=(
            "2,000+ scholarships available across 126+ partner institutes; distinct from ICCR schemes."
        ),
    ),
    ScholarshipIngestionRecord(
        name="JASSO Monbukagakusho Honors Scholarship",
        country="Japan",
        degree_levels="Undergraduate, Graduate, Japanese Language Institute, College of Technology, Specialized Training College",
        funding_type="Partial",
        deadline="Varies by institution",
        deadline_date=None,
        deadline_precision="unknown",
        eligibility=[
            "Privately-financed international students (not receiving Japanese Government MEXT Scholarship or Foreign Government Scholarship)",
            "Enrolled (or about to enroll) as a full-time student in a Japanese educational institution: undergraduate, graduate, junior college, college of technology (3rd year+), specialized training college, university preparatory course, or Japanese language institute",
            "Residence status of 'Student' in Japan",
            "Excellent academic and character records",
            "Facing financial difficulties",
            "Must meet grading criteria specified in application guidelines",
            "Language requirement: JLPT N2+ OR EJU Japanese 200+ points OR B2 CEFR English (exempt for Japanese language program students)",
            "Other allowance (excluding tuition) must not exceed ¥90,000/month",
            "If financial supporter in Japan exists, their annual income must be less than ¥5 million",
            "Must not receive incompatible scholarships (JASSO Student Exchange Support Program, etc.)",
        ],
        eligibility_summary=(
            "Privately-financed international students with excellent academic and character records; enrolled or about "
            "to enroll in a Japanese educational institution; facing financial difficulties; income criteria apply "
            "(supporter's annual income <5 million yen)."
        ),
        coverage=[
            "¥48,000/month for graduate/undergraduate level; ¥30,000/month for Japanese language institutes",
            "12 months (April–March) or 6 months (October–March)",
        ],
        required_documents=[
            "Application form (from educational institution)",
            "Academic transcript",
            "Proof of enrollment/admission",
            "Income certificate (for financial supporter if applicable)",
            "Recommendation from educational institution",
        ],
        requirements=[
            "Application form",
            "Academic transcript",
            "Proof of enrollment/admission",
            "Income certificate",
            "Recommendation",
        ],
        english_requirement="B2 CEFR or higher (for non-Japanese language program students). Alternatively, JLPT N2+ or EJU Japanese 200+ points accepted.",
        duration="12 months (April to March) or 6 months (October to March)",
        application_period="Varies by educational institution - inquire at the international student office of the enrolled institution",
        official_updates_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/shoreihi/about.html",
        region="East Asia",
        selection_notes=(
            "Selection by educational institutions based on academic performance, character, and financial need. "
            "Number of recommendations per institution depends on enrolled international student count. "
            "Candidates must sign monthly attendance sheet at international student office. "
            "JASSO conducts career path surveys after scholarship period."
        ),
        program_type="Government scholarship for privately-financed international students (Japan Student Services Organization - JASSO)",
        official_source_url=JASSO_OFFICIAL_SOURCE_URL,
        official_source="Japan Student Services Organization (JASSO)",
        is_verified=True,
        application_method=["Through the Japanese educational institution where the student is enrolled"],
        best_fit="Privately-financed international students already in Japan seeking monthly financial support.",
        notes=(
            "Distinct from MEXT scholarship (which is for pre-arrival students). Reservation program available "
            "for high scorers on the EJU. Income criteria: supporter's annual income must be <5 million yen. "
            "Other allowances must not exceed ¥90,000/month."
        ),
    ),
    ScholarshipIngestionRecord(
        name="POSCO TJ Park Foundation Global Scholarship",
        country="South Korea",
        degree_levels="Master's, Doctoral",
        funding_type="Partial to Full",
        deadline="Typically May annually",
        deadline_date=None,
        deadline_precision="month",
        eligibility_summary=(
            "Asian nationals planning to enroll in Master's or Doctoral programs at Korean universities; academic excellence; "
            "not previously received a Korean government scholarship."
        ),
        coverage=[
            "Tuition fees; living expenses; arrival allowance; language excellence scholarships (specific amounts vary by sub-program)",
        ],
        required_documents=[
            "Application form",
            "Academic transcripts",
            "Proof of nationality",
            "Study plan",
            "Recommendation letters",
        ],
        official_source_url=POSCO_OFFICIAL_SOURCE_URL,
        official_source="POSCO TJ Park Foundation",
        is_verified=True,
        application_method=["Online via POSCO TJ Park Foundation website"],
        best_fit="Asian students seeking Master's or Doctoral funding at Korean universities.",
        notes=(
            "~50 students selected annually; all academic fields except MBA; specifically for Asian students."
        ),
    ),
    ScholarshipIngestionRecord(
        name="ETH Zurich Excellence Scholarship & Opportunity Programme (ESOP)",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="November 30 annually",
        deadline_date=date(2026, 11, 30),
        deadline_precision="month",
        eligibility_summary=(
            "Outstanding new Master's students at ETH Zurich; must rank in top 10% of Bachelor's graduating class; "
            "not currently enrolled in a Master's at ETH Zurich."
        ),
        coverage=[
            "CHF 12,000 per semester for living and study expenses",
            "Full tuition fee waiver for regular program duration (3–4 semesters)",
            "Mentorship and ETH Foundation network",
        ],
        required_documents=[
            "Completed Master's application",
            "Bachelor's degree certificate",
            "Official transcripts",
            "CV",
            "Letter of motivation",
            "Pre-proposal for Master's thesis",
        ],
        official_source_url=ETH_ESOP_OFFICIAL_SOURCE_URL,
        official_source="ETH Zurich and ETH Zurich Foundation",
        is_verified=True,
        application_method=["Via ETH Zurich online Master's application portal (indicate interest in ESOP)"],
        best_fit="Outstanding new Master's applicants to ETH Zurich seeking full funding.",
        notes=(
            "Highly competitive; covers full study and living costs; decisions communicated by end of March."
        ),
    ),
    ScholarshipIngestionRecord(
        name="EPFL Master Excellence Fellowships",
        country="Switzerland",
        degree_levels="Master's",
        funding_type="Fully Funded",
        deadline="December 15 (1st round), March 31 (2nd round)",
        deadline_date=None,
        deadline_precision="month",
        eligibility_summary=(
            "Outstanding candidates applying to EPFL Master's programs; excellent academic results; distinguished in "
            "research, entrepreneurship, or societal commitment."
        ),
        coverage=[
            "Living costs (CHF ~12,000/semester equivalent)",
            "Full tuition fee waiver",
            "Guaranteed housing",
            "Renewable for second year based on performance (minimum 5.0/6 average, 50 ECTS credits)",
        ],
        required_documents=[
            "Standard Master's admission documents",
            "Recommendation letters (required for internal/external candidates)",
        ],
        official_source_url=EPFL_OFFICIAL_SOURCE_URL,
        official_source="EPFL (École Polytechnique Fédérale de Lausanne)",
        is_verified=True,
        application_method=["Via EPFL online Master's application (check excellence fellowship box)"],
        best_fit="Outstanding Master's applicants to EPFL seeking full funding and guaranteed housing.",
        notes=(
            "Cannot be combined with other substantial scholarships without prior declaration."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships",
        country="EU (multiple)",
        degree_levels="Postdoctoral",
        funding_type="Fully Funded",
        deadline="Typically September/October annually",
        deadline_date=None,
        deadline_precision="month",
        eligibility_summary=(
            "Excellent researchers of any nationality holding a PhD; mobility rule (must not have resided/worked in "
            "recruiting country >12 months in past 36 months); open to those reintegrating to Europe or displaced by conflict."
        ),
        coverage=[
            "Salary, mobility allowance, research costs, training and networking support (typical total €100,000+ over fellowship duration)",
        ],
        required_documents=[
            "Research proposal",
            "CV",
            "PhD certificate",
            "Host institution agreement",
            "Recommendation letters",
        ],
        official_source_url=MSCA_OFFICIAL_SOURCE_URL,
        official_source="European Commission (Marie Skłodowska-Curie Actions)",
        is_verified=True,
        application_method=["Joint application by researcher and host institution"],
        best_fit="Postdoctoral researchers seeking fully funded research fellowships across EU Member States or Horizon Europe Associated Countries.",
        notes=(
            "Standard duration 12–24 months; two tracks: European Postdoctoral Fellowship and Global Postdoctoral Fellowship."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Erasmus+ Student Exchange (Studying Abroad)",
        country="EU (multiple)",
        degree_levels="Bachelor's, Master's, Doctoral (short-cycle also)",
        funding_type="Partial to Full",
        deadline="Varies by university (typically 1–3 months before departure)",
        deadline_date=None,
        deadline_precision="unknown",
        eligibility_summary=(
            "Students currently enrolled in a higher education institution that participates in Erasmus+; studying in "
            "a recognized degree program; exchange must be relevant to degree-related learning."
        ),
        coverage=[
            "Tuition fees waived at host institution",
            "Monthly living grant (amount varies by country)",
            "Possible travel allowance",
            "Additional support for students with disabilities",
        ],
        required_documents=[
            "Learning agreement",
            "Transcript of records",
            "Confirmation of enrollment",
        ],
        official_source_url=ERASMUS_PLUS_OFFICIAL_SOURCE_URL,
        official_source="European Commission (Erasmus+ Programme)",
        is_verified=True,
        application_method=["Through sending home university's international/Erasmus+ office"],
        best_fit="University-enrolled students seeking short-term study abroad funding within the Erasmus+ network.",
        notes=(
            "2–12 months abroad (or 5–30 days for short-term blended mobility); maximum 12 months total per study cycle; "
            "distinct from Erasmus Mundus Joint Masters (full degree program)."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Marie Skłodowska-Curie Actions (MSCA) Doctoral Networks",
        country="EU (multiple)",
        degree_levels="Doctoral / PhD",
        funding_type="Fully Funded",
        deadline="Typically November annually (2026 call: 24 November 2026)",
        deadline_date=date(2026, 11, 24),
        deadline_precision="month",
        application_period="Call opens May, deadline November annually",
        eligibility_summary=(
            "Excellent researchers of any nationality holding a Master's degree or equivalent; mobility rule applies; "
            "open to those reintegrating to Europe or displaced by conflict."
        ),
        coverage=[
            "Gross salary (approx. EUR 4,000-5,000/month depending on country and experience)",
            "Mobility allowance",
            "Research costs",
            "Training and networking support",
            "Family allowance (if applicable)",
        ],
        required_documents=[
            "Research proposal",
            "CV",
            "Master's degree certificate",
            "Host institution agreement",
            "Recommendation letters",
        ],
        official_source_url="https://marie-sklodowska-curie-actions.ec.europa.eu/actions/doctoral-networks",
        official_source="European Commission (Marie Skłodowska-Curie Actions)",
        is_verified=True,
        application_method=["Apply to funded Doctoral Network projects advertised on EURAXESS or institutional websites"],
        best_fit="PhD candidates seeking fully funded research training across EU Member States or Horizon Europe Associated Countries.",
        notes=(
            "Part of Horizon Europe; Doctoral Networks are partnerships of universities, research institutions and businesses "
            "from different countries. Vacancies advertised on EURAXESS portal. Standard duration 3-4 years."
        ),
    ),
    ScholarshipIngestionRecord(
        name="France Excellence Europa Scholarship",
        country="France",
        degree_levels="Master's",
        funding_type="Partial",
        deadline="Typically April annually (2025 deadline: 30 April 2025; 2026 call expected similar timeline)",
        deadline_date=None,
        deadline_precision="month",
        application_period="Typically spring annually",
        eligibility_summary=(
            "National of one of 26 EU member states; at least 18 years old; admitted to a French higher education institution "
            "in Master's 1 or Master's 2; not holding a French higher education degree; not currently registered in France "
            "for a higher education degree; not receiving another French ministry/Erasmus+/AUF scholarship."
        ),
        coverage=[
            "Half-yearly allowance of EUR 6,850",
            "Installation allowance of EUR 1,700",
            "Exemption from registration fees for national diplomas",
            "Priority assistance in finding CROUS university residences (rent paid by student)",
            "Insurance enrollment during first three months",
            "Supplemental health insurance",
            "Exemption from CVEC",
            "Special discounts on cultural activities",
        ],
        required_documents=[
            "Application form",
            "CV (French or English)",
            "Cover letter (French or English)",
            "Copy of most recent higher education diploma or secondary school diploma",
            "Transcripts from last two years of higher education",
            "Copy of identity document (passport/ID card)",
            "Letter of admission to Master's 1 or Master's 2 in France",
        ],
        official_source_url="https://www.campusfrance.org/en/france-excellence-europa-scholarship-program",
        official_source="Campus France (French Ministry for Europe and Foreign Affairs)",
        is_verified=True,
        application_method=["Online via French Embassy in country of nationality (email to embassy contact)"],
        best_fit="EU students seeking partial funding for Master's studies in France.",
        notes=(
            "Does not cover course fees, international or national transportation. "
            "Applications pre-selected by French embassies, then evaluated by Ministry. "
            "2025 was the inaugural call; 2026 call expected."
        ),
    ),
    ScholarshipIngestionRecord(
        name="France Excellence Major Scholarship",
        country="France",
        degree_levels="Bachelor's (5-year undergraduate/engineering/master's track)",
        funding_type="Partial to Full",
        deadline="Typically February-March annually (2026 campaign: 16 February - 12 March 2026)",
        deadline_date=None,
        deadline_precision="month",
        application_period="February-March annually",
        eligibility_summary=(
            "Non-French national; enrolled in terminale (final year) in an approved French international school abroad "
            "(homologated by AEFE); excellent academic results; plan to pursue higher education in France; "
            "obtain baccalaureate with mention 'très bien'."
        ),
        coverage=[
            "Three levels of grant based on family situation (amounts vary annually)",
            "Status of French government scholarship holder (facilitates visa, residence permit, university housing)",
            "Follow-up and support by AEFE throughout studies",
        ],
        required_documents=[
            "Online application via Cascade application (preselected by school head)",
            "Academic transcripts",
            "Copy of identity document",
            "Letter of admission/plans for higher education in France",
        ],
        official_source_url="https://aefe.gouv.fr/fr/aefe/operateur-educatif-du-ministere-de-leurope-et-des-affaires-etrangeres/dispositif-des-bourses-france-excellence-major",
        official_source="AEFE (Agency for French Education Abroad) / French Ministry for Europe and Foreign Affairs",
        is_verified=True,
        application_method=["Online via Cascade application (preselection by homologated French international school abroad)"],
        best_fit="Top non-French students in terminale at French international schools abroad seeking funding for higher education in France.",
        notes=(
            "Approximately 200 new scholars per year; supports up to 5 years of study in France. "
            "Distinct from Eiffel (which is for Master's/PhD already admitted to French institutions)."
        ),
    ),
    ScholarshipIngestionRecord(
        name="DAAD Study Scholarships - Master Studies for All Academic Disciplines",
        country="Germany",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="Typically October annually (2026 deadline: 16 November 2026 for some countries; varies by country)",
        deadline_date=date(2026, 11, 16),
        deadline_precision="month",
        application_period="Typically June-October/November annually",
        eligibility_summary=(
            "Completed first degree (e.g., Bachelor's or Diplom) by funding start date; typically no more than 6 years since last degree; "
            "application via DAAD portal open from 1 June until stated deadline."
        ),
        coverage=[
            "Monthly stipend approx. EUR 934-1,200 (varies by programme/degree level)",
            "Health, accident, and personal liability insurance",
            "Travel allowance",
            "Some programmes also cover tuition and research/study allowances",
        ],
        required_documents=[
            "Online application form via DAAD portal",
            "CV",
            "Motivation letter (1-3 pages)",
            "Academic transcripts and certificates",
            "Letter of admission to German university",
            "Language certificates (German and/or English depending on programme)",
        ],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50026200",
        official_source="DAAD — German Academic Exchange Service",
        is_verified=True,
        application_method=["Online via DAAD portal"],
        best_fit="Graduates seeking Master's funding across all academic disciplines in Germany.",
        notes=(
            "Funded by German Federal Foreign Office; not a single unified scholarship but a database entry for a specific programme. "
            "Application portal access only appears during active application periods."
        ),
    ),
    ScholarshipIngestionRecord(
        name="DAAD Study Scholarships for STEM Disciplines",
        country="Germany",
        degree_levels="Master's",
        funding_type="Partial to Full",
        deadline="Typically October annually (2026 deadline: 31 August 2026 for some countries; varies by country)",
        deadline_date=date(2026, 8, 31),
        deadline_precision="month",
        application_period="Typically June-October annually",
        eligibility_summary=(
            "High-achieving students from developing and emerging countries; completed first degree (Bachelor's) by application deadline; "
            "must pursue full-time on-campus STEM Master's (mathematics, computer science, natural sciences, engineering) at a German state or state-recognized university."
        ),
        coverage=[
            "Monthly stipend approx. EUR 934-1,200",
            "Health, accident, and personal liability insurance",
            "Travel allowance",
            "Study/research allowance",
        ],
        required_documents=[
            "Online application form via DAAD portal",
            "CV",
            "Motivation letter",
            "Academic transcripts and degree certificate",
            "Letter of admission",
            "Language certificates",
        ],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=57742130",
        official_source="DAAD — German Academic Exchange Service",
        is_verified=True,
        application_method=["Online via DAAD portal"],
        best_fit="High-achieving STEM graduates from developing/emerging countries seeking Master's funding in Germany.",
        notes=(
            "Funded by German Federal Foreign Office; specifically for developing/emerging countries. "
            "Interdisciplinary programmes must have a designated STEM focus. Tuition-free Master's programmes only."
        ),
    ),
    ScholarshipIngestionRecord(
        name="DAAD Development-Related Postgraduate Courses (EPOS)",
        country="Germany",
        degree_levels="Master's, PhD",
        funding_type="Fully Funded",
        deadline="Varies by course (typically August-November annually for next intake)",
        deadline_date=None,
        deadline_precision="unknown",
        application_period="Varies by course; applications submitted directly to individual courses",
        eligibility_summary=(
            "Graduates from developing and newly industrialised countries on the DAAD DAC list; at least two years of professional experience; "
            "above-average academic results; development-related motivation; must not have resided in Germany >15 months before application."
        ),
        coverage=[
            "Monthly payments: EUR 992/month (Master's) or EUR 1,400/month (PhD, from February 2026)",
            "Payments towards health, accident and personal liability insurance",
            "Travel allowance (unless covered by home country or another source)",
            "Under certain circumstances: monthly rent subsidy and allowance for accompanying family",
        ],
        required_documents=[
            "DAAD application form for EPOS",
            "CV (Europass format)",
            "Motivation letter",
            "Letter of recommendation from current employer",
            "Certificate(s) of employment (at least 2 years after Bachelor's)",
            "Academic transcripts and degree certificates",
            "Language proficiency proof (English and/or German)",
        ],
        official_source_url="https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50076777",
        official_source="DAAD — German Academic Exchange Service (funded by BMZ)",
        is_verified=True,
        application_method=["Apply directly to the chosen postgraduate course (not to DAAD centrally)"],
        best_fit="Young professionals from developing countries seeking development-related Master's or PhD funding in Germany.",
        notes=(
            "Umbrella programme covering separately approved courses; each course has its own deadline and selection committee. "
            "Applicants may apply for up to three courses. Applications must be submitted directly to courses, not DAAD."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Humboldt Research Fellowship",
        country="Germany",
        degree_levels="Postdoctoral / Early Career Research",
        funding_type="Fully Funded",
        deadline="Three calls annually: March 15, July 15, November 15 (2026 schedule)",
        deadline_date=None,
        deadline_precision="month",
        application_period="Three selection rounds per year (March, July, November)",
        eligibility_summary=(
            "Postdocs: PhD completed no longer than 4 years prior to application; Experienced researchers: PhD completed no longer than 12 years prior; "
            "all nationalities and research areas; must secure a German academic host before applying."
        ),
        coverage=[
            "Monthly fellowship amount EUR 3,000 (postdocs) or EUR 3,600 (experienced researchers)",
            "Travel allowance",
            "Research allowance",
            "Language course support",
            "Family allowance for accompanying spouse/children under certain circumstances",
        ],
        required_documents=[
            "Online application via Humboldt Foundation portal",
            "CV (2 pages max)",
            "Research outline (5 pages max)",
            "List of publications",
            "Key publications",
            "Doctoral certificate or proof of completion",
            "Detailed statement from German host",
            "Two expert reviews",
        ],
        official_source_url="https://www.humboldt-foundation.de/en/apply/sponsorship-programmes/humboldt-research-fellowship",
        official_source="Alexander von Humboldt Foundation (German Federal Foreign Office)",
        is_verified=True,
        application_method=["Online via Alexander von Humboldt Foundation application portal"],
        best_fit="Postdoctoral and early-career researchers seeking to conduct research in Germany.",
        notes=(
            "Part of the Global Minds Initiative Germany. Calls open 8 months before selection meetings. "
            "Once call reaches 800 applications, it closes until next round. "
            "Postdoc fellowships last 6-24 months; experienced researcher fellowships last 6-18 months."
        ),
    ),
    ScholarshipIngestionRecord(
        name="JASSO Student Exchange Support Program",
        country="Japan",
        degree_levels="Undergraduate, Graduate (short-term exchange)",
        funding_type="Partial",
        deadline="Varies by Japanese host university",
        deadline_date=None,
        deadline_precision="unknown",
        application_period="Varies by host university agreement",
        eligibility_summary=(
            "Accepted by a Japanese university under a student exchange agreement with home institution; "
            "from a country with diplomatic relations with Japan; unable to participate solely at own expense; "
            "must return to home institution after program; excellent academic performance."
        ),
        coverage=[
            "Monthly stipend JPY 80,000",
        ],
        required_documents=[
            "Application through Japanese host university",
            "Proof of acceptance under exchange agreement",
            "Proof of student status at home institution",
            "Academic transcripts",
        ],
        official_source_url="https://www.jasso.go.jp/en/ryugaku/scholarship_j/ukeire.html",
        official_source="Japan Student Services Organization (JASSO)",
        is_verified=True,
        application_method=["Apply through the Japanese host university (not directly to JASSO)"],
        best_fit="Exchange students from partner universities seeking short-term study funding in Japan.",
        notes=(
            "Distinct from Monbukagakusho Honors Scholarship (which is for privately-financed students already in Japan). "
            "Program length: 8 days to 1 year. Total monthly scholarship from all sources must not exceed JPY 80,000."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Global Korea Scholarship (GKS) Non-degree Exchange Program",
        country="South Korea",
        degree_levels="Undergraduate, Graduate (Master's, Doctoral) - exchange only",
        funding_type="Partial",
        deadline="Varies by affiliated university",
        deadline_date=None,
        deadline_precision="unknown",
        application_period="Varies by university",
        eligibility_summary=(
            "Undergraduate or graduate students of foreign nationality enrolled in an overseas university with an agreement "
            "with a Korean university affiliated with NIIED; overall academic performance 80% or above; "
            "not previously received a Korean government scholarship; not Korean nationals."
        ),
        coverage=[
            "Accommodation support",
            "Settlement allowance",
            "Airfare support",
            "Insurance fee",
        ],
        required_documents=[
            "Application through NIIED-affiliated Korean university",
            "Proof of enrollment at home university",
            "Academic transcripts",
            "Study plan",
            "Language proficiency certificate",
        ],
        official_source_url="https://www.niied.go.kr/web/niied/contents/niiedEng/eng_gksNonDegreeExchange",
        official_source="National Institute for International Education (NIIED), South Korea",
        is_verified=True,
        application_method=["Apply through NIIED-affiliated Korean universities (not individual application)"],
        best_fit="Exchange students from partner universities seeking short-term study funding in South Korea.",
        notes=(
            "Distinct from GKS Degree Program (which is for full degree-seeking students). "
            "Duration: typically 4 months (1 semester). Students must return to home institution after exchange."
        ),
    ),
    ScholarshipIngestionRecord(
        name="Fulbright Foreign Student Program",
        country="USA",
        degree_levels="Master's, PhD, Research",
        funding_type="Fully Funded",
        official_source_url="https://foreign.fulbrightonline.org",
        eligibility_summary=(
            "Non-U.S. citizen from a participating Fulbright country; bachelor's degree; strong academic record; "
            "leadership potential; under 35 preferred for some countries."
        ),
        coverage=[
            "Full tuition",
            "Monthly stipend",
            "Round-trip airfare",
            "Health insurance",
            "Book allowance",
        ],
        required_documents=[
            "Online application",
            "Transcripts",
            "3 recommendation letters",
            "Study plan",
            "English proficiency",
        ],
        english_requirement="TOEFL/IELTS required",
        deadline="Varies by country — U.S. Embassies/Fulbright Commissions must submit nominations by mid-September",
        best_fit="Postgraduate researchers and academics",
        notes="Apply through U.S. Embassy or Fulbright Commission in home country. Highly competitive.",
        legacy_titles=("fulbright scholarship",),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Chevening Scholarship",
        country="UK",
        degree_levels="Master's only",
        funding_type="Fully Funded",
        official_source_url="https://www.chevening.org",
        official_source="Foreign, Commonwealth and Development Office (FCDO), UK",
        eligibility_summary=(
            "Chevening-eligible country citizen, 2+ years work experience (2,800 hours), undergraduate degree "
            "qualifying for UK master's, return to home country for 2+ years after scholarship ends"
        ),
        eligibility=[
            "Be a citizen of a Chevening-eligible country or territory",
            "Commit to returning to your home country for at least 2 years after your scholarship ends",
            "Have at least 2 years' work experience (2,800 hours)",
            "Hold an undergraduate degree that qualifies you for a UK master's programme",
            "Apply to 3 different and eligible UK university courses",
        ],
        coverage=[
            "Full tuition",
            "Monthly living allowance",
            "Return airfare",
            "Arrival allowance",
            "Homeward travel allowance",
        ],
        required_documents=[
            "Online application (via Chevening online application system)",
            "Two reference letters",
            "Undergraduate degree certificate/diploma",
            "Passport",
            "English proficiency (IELTS 6.5+ or equivalent)",
        ],
        english_requirement="IELTS 6.5+ or equivalent",
        requirements=[
            "Online application via Chevening online application system",
            "Two reference letters",
            "Undergraduate degree certificate/diploma",
            "Passport",
            "English proficiency (IELTS 6.5+ or equivalent)",
        ],
        application_method=[
            "Apply via Chevening online application system at chevening.org/apply",
            "Choose 3 UK master's degree courses",
            "If shortlisted, attend interview at British embassy/high commission",
            "Secure unconditional offer from a UK university by deadline",
        ],
        duration="1 year (one-year master's degree)",
        application_period="4 August 2026 to 6 October 2026 (for 2027-28 cycle)",
        region="Europe",
        catalogue_url="https://www.chevening.org/scholarships/",
        official_updates_url="https://www.chevening.org/scholarships/application-timeline/",
        selection_notes=(
            "Applications sifted against eligibility criteria, then assessed by independent reading committees. "
            "Shortlisted candidates interviewed at British embassy/high commission in English."
        ),
        program_type="Government scholarship (fully-funded one-year master's degree)",
        deadline="6 October 2026 at 11:00 UTC (for 2027-28 cycle)",
        deadline_date=date(2026, 10, 6),
        deadline_precision="exact",
        best_fit="Mid-career professionals with leadership potential",
        notes=(
            "For 2027-28 cycle: applications open 4 August 2026, close 6 October 2026 at 11:00 UTC. "
            "Interviews mid-February 2027; unconditional offer deadline 8 July 2027. "
            "Funded by the Foreign, Commonwealth and Development Office (FCDO)."
        ),
        legacy_titles=("chevening",),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Commonwealth Scholarship",
        country="UK",
        degree_levels="Master's, PhD, Split-site PhD",
        funding_type="Fully Funded",
        official_source_url="https://cscuk.fcdo.gov.uk",
        official_source="Commonwealth Scholarship Commission (CSC), UK",
        eligibility_summary=(
            "Commonwealth citizen (low/middle-income country), first degree at least 2:1 honours, "
            "permanently resident in eligible Commonwealth country, unable to afford UK study without scholarship"
        ),
        eligibility=[
            "Be a citizen of or have been granted refugee status by an eligible Commonwealth country",
            "Be permanently resident in an eligible Commonwealth country",
            "Be available to start academic studies in UK by September 2027",
            "Hold a first degree of at least upper second-class (2:1) honours standard",
            "Be unable to afford to study in UK without this scholarship",
        ],
        coverage=[
            "Full tuition",
            "Monthly stipend",
            "Airfare",
            "Thesis grant",
            "Study travel grant",
        ],
        required_documents=[
            "Online application via CSC Central",
            "Proof of citizenship (passport or national ID card)",
            "Full transcripts with certified translations if not in English",
            "References from at least two individuals",
            "Research proposal (for PhD applicants)",
        ],
        english_requirement="IELTS/TOEFL required",
        requirements=[
            "Online application via CSC Central",
            "Proof of citizenship (passport or national ID card)",
            "Full transcripts with certified translations if not in English",
            "References from at least two individuals",
            "Research proposal (for PhD applicants)",
        ],
        application_method=[
            "Must apply through national nominating agency (NOT direct to CSC)",
            "Apply to CSC via CSC Central online application system",
            "Also apply and secure admission for chosen university course",
        ],
        duration="Master's: 12 months. PhD: 36 months.",
        application_period=(
            "8 September 2026 to 20 October 2026 (CSC deadline; national agency deadlines may be earlier)"
        ),
        region="Europe",
        catalogue_url="https://cscuk.fcdo.gov.uk/scholarships/",
        official_updates_url="https://cscuk.fcdo.gov.uk/scholarships/commonwealth-masters-scholarships/",
        selection_notes=(
            "Selection based on academic merit, quality of research proposal, potential impact on development of "
            "candidate's home country. The CSC does not accept direct applications for Master's/PhD scholarships."
        ),
        program_type="Government scholarship (Commonwealth Scholarship Commission)",
        deadline="20 October 2026 at 16:00 BST (CSC deadline for 2027/28 cycle; national nominating agency deadline may be earlier)",
        deadline_date=date(2026, 10, 20),
        deadline_precision="exact",
        best_fit="Academic researchers and PhD candidates",
        notes=(
            "For 2027/28 cycle: applications open 8 September 2026, CSC deadline 20 October 2026 at 16:00 BST. "
            "National nominating agency deadlines may be earlier. Results expected by July 2027. "
            "The CSC does not accept direct applications for Master's/PhD scholarships."
        ),
        legacy_titles=("commonwealth scholarship", "csc scholarship uk"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Australia Awards Scholarships",
        country="Australia",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Fully Funded",
        official_source_url="https://www.dfat.gov.au/people-to-people/australia-awards/australia-awards-scholarships",
        official_source="Department of Foreign Affairs and Trade (DFAT), Australian Government",
        eligibility_summary="Citizen of an eligible developing country (Bangladesh included); minimum 3 years relevant work experience for Master's applicants; not currently studying in Australia; meet English proficiency and visa requirements. Country-specific target groups and priorities apply.",
        coverage=[
            "Full tuition fees",
            "Return economy class airfare",
            "Establishment allowance",
            "Monthly stipend (covers living expenses)",
            "Overseas Student Health Cover (OSHC)",
            "Pre-course English (PCE) if required",
            "Fieldwork allowance for compulsory research (where applicable)",
        ],
        required_documents=[
            "Online application via OASIS (or country-specific portal)",
            "Academic transcripts and certificates",
            "Employment references",
            "English proficiency test results",
            "Medical examination",
            "Passport copy",
        ],
        english_requirement="IELTS 6.5 overall (no band less than 6.0) or equivalent TOEFL/PTE; some countries may have lower thresholds for marginalized groups.",
        deadline="Country-specific; Bangladesh 2027 intake: 30 April 2026",
        deadline_precision="month",
        eligibility=[
            "Citizen of an eligible developing country (Bangladesh included).",
            "Minimum 3 years relevant work experience for Master's applicants.",
            "Not currently studying in Australia.",
            "Meet English proficiency requirements (e.g., IELTS 6.5 overall, or equivalent).",
            "Meet all Department of Home Affairs student visa requirements.",
        ],
        application_method=[
            "Online via OASIS (Online Australia Scholarships Information System)",
            "Hard-copy applications accepted in some countries",
        ],
        best_fit="Mid-career professionals from eligible developing countries seeking fully funded study in Australia.",
        notes="Bangladesh 2027 intake: opening 1 February 2026, closing 30 April 2026. Country-specific eligibility, priority fields, and deadlines apply. Indonesia and the Philippines use country-specific portals, not OASIS. Strong preference for development-related fields of study.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Australia Awards Fellowships",
        country="Australia",
        degree_levels="Short-term professional development (2–52 weeks)",
        funding_type="Fully Funded",
        official_source_url="https://www.dfat.gov.au/people-people/australia-awards/australia-awards-fellowships",
        official_source="Department of Foreign Affairs and Trade (DFAT), Australian Government",
        eligibility_summary="Australian organisations (with ABN) partner with Overseas Counterpart Organisations (OCOs) in eligible developing countries to host Fellows. Fellows must be 18+, citizens of eligible ODA countries, not Australian citizens or permanent residents, and meet visa requirements.",
        coverage=[
            "Up to AUD 34,500 per Fellow (competitive grant to Australian organisation)",
            "Australian organisation must provide co-contribution (in-kind or financial)",
        ],
        required_documents=[
            "Online application via SmartyGrants portal",
            "Organisation ABN and legal entity details",
            "OCO details and partnership evidence",
            "Fellowship activity plan",
            "Budget (using DFAT template)",
            "Co-contribution evidence",
        ],
        deadline_precision="month",
        application_period="Round-dependent; Round 21 closed 16 January 2026; Round 22 expected to open Q4 2026",
        eligibility=[
            "Australian Host Organisation must be a legal entity with current ABN.",
            "Overseas Counterpart Organisation must operate in an eligible ODA country.",
            "Fellows must be 18+ at commencement.",
            "Fellows must not be Australian citizens or permanent residents.",
            "Fellows must be citizens of and residing in an eligible developing country.",
            "Fellows must have relevant professional experience.",
            "Fellows must be able to participate for the full duration.",
        ],
        application_method=[
            "Online via SmartyGrants portal (Australian organisations only)",
        ],
        best_fit="Australian organisations seeking to host mid-career professionals from developing countries for short-term development programs.",
        notes="Round 21 closed 16 January 2026. Round 22 expected to open in Q4 2026. Individuals cannot apply directly; applications are submitted by Australian host organisations only. Activities must include a minimum of 2 weeks in Australia, with total duration 2–52 weeks.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Australia Awards Mekong-Australia Partnership (MAP) Scholarships",
        country="Australia",
        degree_levels="Master's (coursework or research)",
        funding_type="Fully Funded",
        official_source_url="https://www.dfat.gov.au/people-to-people/australia-awards/mekong-australia-partnership",
        official_source="Department of Foreign Affairs and Trade (DFAT), Australian Government",
        eligibility_summary="Citizen of Thailand, Cambodia, Vietnam, Laos, or Myanmar; meet general Australia Awards eligibility; proposed study must fall within MAP thematic areas (water security, climate resilience, etc.).",
        coverage=[
            "Full tuition fees",
            "Return economy class airfare",
            "Establishment allowance",
            "Monthly stipend",
            "Overseas Student Health Cover (OSHC)",
            "Pre-course English (PCE) if required",
            "Exclusive access to Mekong-Leaders Network on-award enrichment program",
        ],
        required_documents=[
            "Online application via OASIS portal",
            "Academic transcripts",
            "Employment references",
            "English proficiency test results",
            "Medical examination",
            "Study plan aligned with MAP thematic areas",
        ],
        english_requirement="IELTS 6.5 overall (no band less than 6.0) or equivalent.",
        deadline_precision="month",
        application_period="Same as Australia Awards Scholarships for respective countries (e.g., 2027 intake: 1 Feb – 30 Apr 2026)",
        eligibility=[
            "Citizen of Thailand, Cambodia, Vietnam, Laos, or Myanmar.",
            "Meet general Australia Awards Scholarships eligibility requirements.",
            "Proposed Master's study or research must align with MAP thematic areas.",
            "Not currently studying in Australia.",
            "Meet English proficiency and visa requirements.",
        ],
        application_method=[
            "Online via OASIS portal (same as Australia Awards Scholarships)",
        ],
        best_fit="Mid-career professionals from Mekong subregion countries seeking Master's study in MAP thematic areas.",
        notes="MAP is a sub-program of Australia Awards Scholarships with additional Mekong-Leaders Network enrichment. Applicants from Thailand use the Thailand Australia Awards intake portal; other MAP countries use standard AAS portals. Applicants may apply for both AAS and MAP-funded scholarships in their respective countries.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Australian Government Research Training Program (RTP)",
        country="Australia",
        degree_levels="Research Doctorate, Research Master's (Higher Degree by Research)",
        funding_type="Fully Funded",
        official_source_url="https://www.education.gov.au/research-block-grants/research-training-program",
        official_source="Department of Education, Australian Government",
        eligibility_summary="Domestic or international students enrolled in an accredited research doctorate or research master's degree at an eligible Australian university. Universities administer applications competitively and may spend up to 10% of RTP funding on international students per grant year.",
        coverage=[
            "RTP Stipend: base rate AUD 34,315/year (2026); max AUD 53,608/year (2026). Universities may offer any rate within this range.",
            "RTP Fees Offset: 100% tuition fee exemption for standard program duration.",
            "RTP Allowance: relocation and thesis allowance.",
            "Part-time stipend rate is 50% of full-time rate.",
        ],
        required_documents=[
            "Apply directly to chosen Australian university's postgraduate research office.",
            "University admission application for Higher Degree by Research.",
            "Research proposal",
            "Academic transcripts",
            "CV",
            "Letters of recommendation (if required by university)",
            "English proficiency evidence (if required)",
        ],
        deadline_precision="month",
        eligibility=[
            "Enrolled or commencing an accredited research doctorate or research master's at an eligible Australian university.",
            "Meet university-specific application and selection criteria.",
            "International students: universities may award up to 10% of RTP funding to overseas students.",
        ],
        application_method=[
            "Apply directly to participating Australian university (no central application portal)",
        ],
        best_fit="Research degree students (domestic and international) seeking fully funded PhD or Master's research places at Australian universities.",
        notes="RTP is administered by individual universities, not centrally. 2026 stipend rates: base AUD 34,315/year, max AUD 53,608/year. Universities set their own application deadlines and selection processes. International students should contact university postgraduate research offices directly.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Destination Australia Program (DAP)",
        country="Australia",
        degree_levels="Certificate IV to Doctorate",
        funding_type="Partial",
        official_source_url="https://www.education.gov.au/destination-australia",
        official_source="Department of Education, Australian Government",
        eligibility_summary="Previously open to domestic and international students studying at eligible regional Australian campuses. No new scholarships are available from July 2024 onward.",
        coverage=[
            "AUD 15,000 per year (previously offered; exact amount varied by provider).",
            "Supports study and living expenses at regional campuses.",
        ],
        required_documents=[
            "Previously varied by provider.",
        ],
        deadline_precision="month",
        application_period="No further funding rounds from 1 July 2024; existing recipients continue to be supported",
        eligibility=[
            "Previously: domestic and international students at eligible regional campuses.",
            "Existing recipients: continue to meet original eligibility criteria.",
        ],
        application_method=[
            "Previously through individual tertiary education providers; no new rounds available",
        ],
        best_fit="N/A for new applicants — program closed for new awards from July 2024.",
        notes="The Australian Government announced no further funding rounds from 1 July 2024. All current Destination Australia scholarship recipients will continue to be supported for the remainder of their studies, up to four years, provided they continue to meet eligibility criteria. Individual students should direct questions to their tertiary education provider.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Melbourne International Undergraduate Scholarship",
        country="Australia",
        degree_levels="Bachelor's",
        funding_type="Partial",
        official_source_url="https://scholarships.unimelb.edu.au/awards/melbourne-international-undergraduate-scholarship",
        official_source="University of Melbourne",
        eligibility_summary="Citizen of a country with GDP per capita of USD 10,000 or less (World Bank data); received an offer for an Overseas Fee place in a bachelor degree; completed secondary school outside Australia or an Australian foundation program; not previously undertaken tertiary studies (excluding extension studies).",
        coverage=[
            "20% tuition fee sponsorship for the duration of the course (from 2027; previously 25% for scholarships awarded before 2027).",
        ],
        required_documents=[
            "Apply for admission to the University of Melbourne bachelor degree program.",
            "No separate scholarship application required; automatic consideration.",
        ],
        deadline_precision="month",
        application_period="Open for automatic consideration when applying for admission",
        eligibility=[
            "Citizen of a country with GDP per capita of USD 10,000 or less (World Bank data).",
            "Received an offer for an Overseas Fee place in a bachelor degree for commencement in the award year.",
            "Completed secondary school outside Australia or a foundation program in Australia.",
            "Not previously undertaken tertiary studies (excluding year 12 extension studies).",
        ],
        application_method=[
            "Automatic consideration upon applying for admission",
        ],
        best_fit="High-achieving international students from lower-income countries seeking undergraduate study at the University of Melbourne.",
        notes="From 2027, the scholarship provides 20% fee sponsorship (previously 25%). Number of scholarships increasing to 225 from 2027. Cannot be held with another scholarship providing fee sponsorship or discount. Selection based on final secondary school or foundation studies results. Minimum selection scores vary by qualification (e.g., IB 40, A Levels A*A*A*).",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="University of Sydney Vice-Chancellor's International Scholarships Scheme",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Partial",
        official_source_url="https://www.sydney.edu.au/scholarships/e/vice-chancellor-international-scholarships-scheme.html",
        official_source="University of Sydney",
        eligibility_summary="International student who has applied for but not yet commenced a CRICOS-registered bachelor's or coursework master's degree at the University of Sydney; must receive an unconditional offer of admission by the relevant round close date.",
        coverage=[
            "Up to AUD 60,000 (five tiers: AUD 60,000, 40,000, 20,000, 10,000, or 5,000).",
            "Payable in equal instalments per semester.",
            "Recipients of Sydney International Student Award capped at AUD 40,000 maximum.",
        ],
        required_documents=[
            "Apply for admission to the University of Sydney.",
            "No separate scholarship application required; automatic consideration for eligible students.",
        ],
        deadline_precision="month",
        application_period="Round-dependent; e.g., Semester 1 2027: Round 1 closes 17 Aug 2026, Round 2 closes 5 Oct 2026, Round 3 closes 16 Nov 2026",
        eligibility=[
            "International student.",
            "Applied for but not yet commenced a CRICOS-registered bachelor's or coursework master's degree at the University of Sydney.",
            "Received an unconditional offer of admission by the relevant round close date.",
        ],
        application_method=[
            "Automatic consideration upon receiving unconditional offer of admission",
        ],
        best_fit="Exceptional international students commencing undergraduate or postgraduate coursework at the University of Sydney.",
        notes="Five scholarship tiers awarded based on academic merit ranking. From 2026 intakes, additional $60,000 tier introduced and Sydney International Student Award cap increased to $40,000. Scholarship is one-time, awarded during first year of commencement, not renewable for subsequent years.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Annie Farrand Scholarship in Agricultural Science (International)",
        country="Australia",
        degree_levels="Bachelor's, Bachelor's (Honours)",
        funding_type="Partial",
        official_source_url="https://www.sydney.edu.au/scholarships/d/farrand-scholarship-in-agricultural-science--international-.html",
        official_source="University of Sydney",
        eligibility_summary="International student with an unconditional offer of admission to study full-time in the Bachelor of Agricultural Science or Bachelor of Agricultural Science (Honours) in the Faculty of Science at the University of Sydney. Awarded to exceptional students from diverse priority markets.",
        coverage=[
            "AUD 20,000 per annum.",
            "Tenable for up to 3 years (full-time).",
        ],
        required_documents=[
            "Apply for admission to the University of Sydney.",
            "No separate scholarship application required; automatic consideration for eligible students.",
        ],
        deadline_precision="month",
        eligibility=[
            "International student.",
            "Unconditional offer of admission for full-time study in Bachelor of Agricultural Science or Bachelor of Agricultural Science (Honours).",
            "Enrolled in the Faculty of Science at the University of Sydney.",
        ],
        application_method=[
            "Automatic consideration upon receiving unconditional offer of admission",
        ],
        best_fit="Exceptional international students from diverse priority markets pursuing Agricultural Science at the University of Sydney.",
        notes="Established in 2023 by the Estate of Annie Farrand. Open date: 1 December 2025 (for 2026 intake). Automatic consideration for eligible students.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ANU Chancellor's International Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's, Graduate Certificate",
        funding_type="Partial",
        official_source_url="https://study.anu.edu.au/scholarships/find-scholarship/anu-chancellors-international-scholarship",
        official_source="Australian National University (ANU)",
        eligibility_summary="International student (overseas student under ESOS Act) with an offer of admission to an eligible ANU program; has not previously received the Award for the same level of study. Multiple country categories apply.",
        coverage=[
            "25% or 50% tuition fee reduction for the duration of the undergraduate or postgraduate degree.",
            "Guaranteed accommodation for first year of study (if chosen).",
        ],
        required_documents=[
            "Apply for admission to ANU.",
            "No separate scholarship application required; automatic consideration.",
        ],
        deadline_precision="month",
        application_period="Open all year round; automatic consideration upon admission application",
        eligibility=[
            "International student (overseas student under ESOS Act 2000; 995 visa holders not eligible unless enrolling in eligible postgraduate program).",
            "Offer of admission to commence at ANU in an eligible program.",
            "Not previously received the Award for the same level of study.",
            "Meet program admission conditions.",
        ],
        application_method=[
            "Automatic consideration upon applying for admission",
        ],
        best_fit="High-achieving international students from diverse countries seeking undergraduate or postgraduate coursework at ANU.",
        notes="200 scholarships available. Multiple categories by citizenship (global, India, Indonesia, Vietnam, South East Asia, Europe/Central & South Americas). All eligible applicants first considered for 50% award; if not selected, considered for 25%. Cannot be deferred. Minimum GPA 5.0 required each semester. NOTE: The main scholarship page currently displays 'The scholarship is currently unavailable,' but the official ANU FAQ confirms availability for 2026 intakes. This contradictory information on the official site means current round status cannot be fully confirmed without direct university contact.",
        is_verified=False,
    ),
    ScholarshipIngestionRecord(
        name="UWA Global Excellence Scholarship",
        country="Australia",
        degree_levels="Bachelor's, Master's (coursework)",
        funding_type="Partial",
        official_source_url="https://www.uwa.edu.au/study/scholarships-and-fees/scholarships/international-scholarships/global-excellence-scholarship",
        official_source="University of Western Australia (UWA)",
        eligibility_summary="International student with an offer for an eligible undergraduate or postgraduate coursework degree at UWA for 2026; minimum equivalent ATAR 85.00 (undergraduate) or minimum WAM 65.00 (postgraduate).",
        coverage=[
            "Undergraduate: up to AUD 48,000 over 4 years (ATAR 98+ = AUD 12,000/year; 90–97.95 = AUD 10,000/year; 85–89.95 = AUD 6,000/year).",
            "Postgraduate: up to AUD 24,000 over 2 years (WAM 85+ = AUD 12,000/year; 75–84.99 = AUD 10,000/year; 65–74.99 = AUD 6,000/year).",
            "Annual tuition fee discount applied per semester.",
        ],
        required_documents=[
            "Apply for admission to an eligible UWA course.",
            "Submit final academic transcripts for scholarship assessment.",
            "No separate scholarship application required.",
        ],
        deadline_precision="month",
        application_period="Automatic consideration upon application; assessed upon final transcript submission",
        eligibility=[
            "International student (full-fee paying).",
            "Offer for an eligible undergraduate or postgraduate coursework degree at UWA for 2026.",
            "Equivalent minimum ATAR 85.00 (undergraduate) or minimum WAM 65.00 (postgraduate).",
            "Final academic transcripts submitted (conditional offers may not include scholarship).",
        ],
        application_method=[
            "Automatic consideration upon admission application and final transcript submission",
        ],
        best_fit="High-achieving international students from all countries seeking undergraduate or postgraduate coursework at UWA.",
        notes="650 scholarships allocated for 2026 intake. Scholarship reviewed annually; deferral does not guarantee same value in future years. May not be held concurrently with other UWA tuition fee reductions. Excluded programs: Juris Doctor, Doctor of Medicine, Doctor of Dental Medicine, Doctor of Optometry, UWA Micro-credentials.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Monash International Leadership Scholarship",
        country="Australia",
        degree_levels="Bachelor's (undergraduate only)",
        funding_type="Fully Funded",
        official_source_url="https://www.monash.edu/study/fees-scholarships/scholarships/find-a-scholarship/monash-international-leadership-scholarship-5571Z",
        official_source="Monash University",
        eligibility_summary="International student who has received a full, unconditional undergraduate course offer from Monash University; intends to enrol full-time in a bachelor's degree at a Monash campus in Australia.",
        coverage=[
            "100% course fees paid until minimum credit points for degree are completed.",
            "Excludes Overseas Student Health Cover (OSHC), accommodation, and living costs.",
        ],
        required_documents=[
            "Apply for admission to Monash University undergraduate program.",
            "No separate scholarship application required per official page; automatic consideration.",
        ],
        deadline_precision="month",
        application_period="Automatic consideration upon receiving course offer",
        eligibility=[
            "International student (not Australian citizen or permanent resident).",
            "Received a full, unconditional undergraduate course offer from Monash University.",
            "Intends to enrol full-time in a bachelor's degree at a Monash campus in Australia.",
        ],
        application_method=[
            "Automatic consideration upon receiving undergraduate course offer",
        ],
        best_fit="Outstanding international students commencing undergraduate study at Monash University.",
        notes="Four scholarships available per year. Recipients must maintain WAM of 70 each semester. Participation in Campus Ambassador Program from second semester required. Invitation to apply for Monash Minds leadership program. Can be deferred within the same calendar year only. Not eligible: current Monash students, Australian Year 12 students, Bachelor of Medical Science and Doctor of Medicine (MD) students, Monash Pathway program students.",
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Netherlands Fellowship Programme (NFP/OTS)",
        country="Netherlands",
        degree_levels="Master's, PhD, Short courses",
        funding_type="Fully Funded",
        official_source_url="https://www.studyinnl.org/finances/ots-scholarships",
        eligibility_summary="Employed in eligible developing country, employer nomination required, under 45",
        coverage=[
            "Tuition",
            "Living allowance",
            "Travel",
            "Insurance",
            "Visa costs",
        ],
        required_documents=[
            "Application form",
            "Employer statement",
            "Transcripts",
            "English proficiency",
            "Motivation letter",
        ],
        english_requirement="IELTS/TOEFL required by host university",
        deadline="Varies by programme — check Nuffic website",
        best_fit="Mid-career professionals sponsored by employer",
        legacy_titles=("nuffic fellowship", "netherlands fellowship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Swedish Institute Scholarship",
        country="Sweden",
        degree_levels="Master's only",
        funding_type="Fully Funded",
        official_source_url="https://si.se/en/apply/scholarships",
        eligibility_summary="Bachelor's degree, 3000 hours work experience, leadership qualities, apply to Swedish university simultaneously",
        coverage=[
            "SEK 11,000/month living costs",
            "Travel grant",
            "Insurance",
            "Tuition covered separately by university",
        ],
        required_documents=[
            "SI application",
            "University application simultaneously",
            "CV",
            "Motivation letter",
            "References",
        ],
        english_requirement="IELTS/TOEFL as per university requirement",
        deadline="Typically February each year",
        best_fit="Young professionals with leadership experience",
        legacy_titles=("swedish institute", "SI scholarship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Chinese Government Scholarship (CSC)",
        country="China",
        degree_levels="Bachelor's, Master's, PhD, Language courses",
        funding_type="Fully Funded",
        official_source_url="https://www.campuschina.org",
        eligibility_summary="Non-Chinese citizen, healthy, Bachelor's for Master's applicants, Master's for PhD applicants",
        coverage=[
            "Full tuition",
            "Accommodation",
            "Monthly stipend CNY 2,500-3,500",
            "Medical insurance",
        ],
        required_documents=[
            "CSC online application",
            "Transcripts",
            "Recommendation letters x2",
            "Physical exam",
            "HSK score (if required by university)",
        ],
        english_requirement="English or Chinese depending on programme",
        deadline="Typically March-April each year",
        best_fit="Students comfortable studying in Chinese or English medium",
        legacy_titles=("csc scholarship", "chinese government scholarship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Taiwan Scholarship Program",
        country="Taiwan",
        degree_levels="Bachelor's, Master's, PhD",
        funding_type="Fully Funded",
        official_source_url="https://www.edutwscholarship.moe.gov.tw",
        eligibility_summary="Non-Taiwan citizen, strong academic record, not currently studying in Taiwan",
        coverage=[
            "NTD 15,000-20,000/month stipend",
            "Tuition up to NTD 40,000/semester",
        ],
        required_documents=[
            "Application form",
            "Transcripts",
            "Recommendation letters x2",
            "Study plan",
            "Passport copy",
        ],
        english_requirement="English or Chinese depending on programme",
        deadline="Typically March-April, varies by embassy",
        best_fit="Students interested in Mandarin learning or STEM fields",
        legacy_titles=("taiwan scholarship", "mofa scholarship taiwan"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="SINGA Scholarship (Singapore)",
        country="Singapore",
        degree_levels="PhD only",
        funding_type="Fully Funded",
        official_source_url="https://www.a-star.edu.sg/Scholarships/for-graduate-studies/singa-award",
        eligibility_summary="Bachelor's or Master's in science/engineering, strong research aptitude, under 35",
        coverage=[
            "Full tuition at NUS/NTU/SUTD/SIMTech",
            "Monthly stipend SGD 2,200",
            "Airfare allowance",
        ],
        required_documents=[
            "Online application",
            "Transcripts",
            "Research proposal",
            "References x3",
            "GRE scores preferred",
        ],
        english_requirement="IELTS/TOEFL or English-medium degree",
        deadline="Typically June and December (2 intakes)",
        best_fit="STEM researchers targeting PhD in Singapore",
        legacy_titles=("singa award", "singapore international graduate award"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="MAECI Italian Government Scholarship",
        country="Italy",
        degree_levels="Bachelor's, Master's, PhD, Research, Language courses",
        funding_type="Partially Funded",
        official_source_url="https://www.esteri.it/en/opportunita/borse-di-studio",
        eligibility_summary="Under 28 for study grants, under 35 for research, valid passport, good academic standing",
        coverage=[
            "Monthly allowance EUR 900",
            "Exemption from university fees at public universities",
        ],
        required_documents=[
            "Online application via Universitaly portal",
            "Transcripts",
            "Motivation letter",
            "Passport",
            "Language certificate",
        ],
        english_requirement="Italian or English depending on programme",
        deadline="Typically April-May each year",
        best_fit="Students interested in Italian universities and culture",
        legacy_titles=("maeci scholarship", "italian government scholarship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="OeAD Austria Scholarship",
        country="Austria",
        degree_levels="Master's, PhD, Postdoc, Research",
        funding_type="Partially Funded",
        official_source_url="https://grants.oead.at",
        eligibility_summary="Completed degree relevant to proposed study, host institution agreement required for research grants",
        coverage=[
            "EUR 1,050-1,350/month depending on level",
            "Travel allowance",
            "Some tuition exemptions",
        ],
        required_documents=[
            "Online application",
            "Research proposal",
            "Transcripts",
            "Host institution letter",
            "References",
        ],
        english_requirement="German or English depending on programme",
        deadline="Varies by programme — check grants.oead.at",
        best_fit="Researchers and postgraduate students targeting Austrian universities",
        legacy_titles=("oead scholarship", "austria scholarship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Vanier Canada Graduate Scholarship",
        country="Canada",
        degree_levels="PhD only",
        funding_type="Fully Funded",
        official_source_url="https://vanier.gc.ca",
        eligibility_summary="Nominated by Canadian university, first year of PhD, world-class academic record, leadership",
        coverage=[
            "CAD 50,000/year for 3 years",
        ],
        required_documents=[
            "University nomination required",
            "Transcripts",
            "Research proposal",
            "References",
            "Leadership CV",
        ],
        english_requirement="As per nominating university",
        deadline="Typically October — must be nominated by university first",
        best_fit="Elite PhD researchers — cannot apply directly, must be nominated",
        notes="Cannot apply directly. Must first gain admission to a Canadian university PhD program and be nominated.",
        legacy_titles=("vanier scholarship", "vanier cgsc"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="Pearson International Scholarship (University of Toronto)",
        country="Canada",
        degree_levels="Bachelor's only",
        funding_type="Fully Funded",
        official_source_url="https://future.utoronto.ca/pearson",
        eligibility_summary="International student applying to UofT, exceptional academic achievement and leadership, community involvement",
        coverage=[
            "Full tuition",
            "Books",
            "Incidental fees",
            "Residence support for 4 years",
        ],
        required_documents=[
            "UofT application first",
            "Pearson nomination by school",
            "Essays",
            "References",
        ],
        english_requirement="As per UofT undergraduate admission",
        deadline="Typically November — must apply to UofT first",
        best_fit="Outstanding high school graduates targeting University of Toronto",
        notes="Must apply to UofT undergraduate program first. School nomination may be required.",
        legacy_titles=("pearson scholarship", "uoft pearson"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="ARES Scholarships (Belgium)",
        country="Belgium",
        degree_levels="Master's, Postgraduate specialisation",
        funding_type="Fully Funded",
        official_source_url="https://www.ares-ac.be/en/cooperation-au-developpement/bourses",
        eligibility_summary="Citizen of eligible developing country (Bangladesh included), Bachelor's, under 40, working in development sector",
        coverage=[
            "Full tuition",
            "Monthly allowance EUR 900",
            "Travel",
            "Insurance",
        ],
        required_documents=[
            "Online application",
            "Transcripts",
            "Employer letter",
            "Motivation letter",
            "References",
        ],
        english_requirement="French or English depending on programme",
        deadline="Typically February each year",
        best_fit="Development sector professionals from eligible countries",
        legacy_titles=("ares scholarship belgium", "cud scholarship"),
        is_verified=True,
    ),
    ScholarshipIngestionRecord(
        name="AECID Spanish Government Scholarship",
        country="Spain",
        degree_levels="Master's, PhD, Research",
        funding_type="Partially Funded",
        official_source_url="https://www.aecid.es/es/becas-y-lectorados",
        eligibility_summary="University degree, Spanish language proficiency for most programmes, citizen of eligible country",
        coverage=[
            "Monthly stipend EUR 1,100",
            "Some tuition support",
            "Travel allowance",
        ],
        required_documents=[
            "Online application",
            "Transcripts",
            "Spanish language certificate",
            "Motivation letter",
            "References",
        ],
        english_requirement="Spanish required for most programmes, some in English",
        deadline="Typically March-April each year",
        best_fit="Spanish-speaking applicants or those willing to learn Spanish",
        legacy_titles=("aecid scholarship", "spanish government scholarship"),
        is_verified=True,
    ),
    # === NEW United States Scholarships ===
    ScholarshipIngestionRecord(
        name="Hubert H. Humphrey Fellowship Program",
        country="USA",
        degree_levels="Non-degree professional fellowship (graduate-level study)",
        funding_type="Fully Funded",
        official_source_url="https://www.humphreyfellowship.org",
        official_source="U.S. Department of State (Bureau of Educational and Cultural Affairs)",
        deadline="Varies by country — U.S. Embassies/Fulbright Commissions must submit nominations by mid-September",
        deadline_precision="month",
        application_period="Varies by country; nominations due mid-September, fellowships begin August-September",
        eligibility_summary=(
            "Accomplished mid-level professionals from designated countries; typically 5+ years of professional "
            "experience; bachelor's degree; demonstrated leadership and commitment to public service; must be "
            "nominated by U.S. Embassy or Fulbright Commission in home country."
        ),
        eligibility=[
            "Accomplished mid-level professional from a designated Humphrey country.",
            "Typically 5 or more years of professional experience.",
            "Bachelor's degree or equivalent.",
            "Demonstrated leadership potential and commitment to public service.",
            "Must be nominated by the U.S. Embassy or Binational Fulbright Commission in home country.",
            "English proficiency sufficient for graduate-level study in the U.S.",
        ],
        coverage=[
            "Tuition and fees at host university",
            "Monthly living/maintenance allowance (includes one-time settling-in allowance)",
            "Accident and sickness health coverage",
            "Book allowance",
            "One-time computer subsidy",
            "Round-trip international air travel",
        ],
        required_documents=[
            "Online application via U.S. Embassy or Fulbright Commission",
            "Essay responses to application prompts",
            "Two letters of recommendation (one from current employer)",
            "Official transcripts in English",
            "Diploma/degree certificate",
            "CV/Resume",
        ],
        english_requirement=(
            "English proficiency sufficient for graduate-level study; demonstrated through application essays, "
            "recommendations, and transcripts. No specific test score minimum centrally required, but host "
            "university may require TOEFL/IELTS."
        ),
        application_method=[
            "Apply through U.S. Embassy Public Affairs Section or Binational Fulbright Commission in home country",
        ],
        best_fit="Mid-career professionals from designated countries seeking non-degree professional enrichment and graduate-level study in the U.S.",
        notes=(
            "10-month non-degree fellowship; not a degree program. Fellows are placed at selected U.S. universities. "
            "Awards announced in spring for fall start. Cannot combine with other U.S. government exchange programs."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="University of Miami Stamps Scholarship",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Fully Funded",
        official_source_url="https://admissions.miami.edu/undergraduate/financial-aid/scholarships/stamps/index.html",
        official_source="University of Miami",
        deadline="November 1 (Early Decision I and Early Action)",
        deadline_date=date(2026, 11, 1),
        deadline_precision="month",
        application_period="Apply via Early Decision I or Early Action for Fall 2027 entry by November 1, 2026",
        eligibility_summary=(
            "All incoming first-year students (including international) applying to University of Miami; exceptional "
            "academic achievement, leadership, and curiosity; no separate scholarship application required — "
            "considered automatically via admission application."
        ),
        eligibility=[
            "All incoming first-year students applying to University of Miami (domestic and international).",
            "Exceptional academic achievement, leadership, and curiosity.",
            "Must apply via Early Decision I or Early Action to be considered for Stamps Scholarship.",
            "Meet University of Miami admission requirements.",
        ],
        coverage=[
            "Full tuition and fees",
            "On-campus housing",
            "Meal plan",
            "University health insurance",
            "Textbooks",
            "Laptop allowance",
            "$12,000 enrichment fund (study abroad, research, internships, etc.)",
        ],
        required_documents=[
            "University of Miami admission application (Common Application)",
            "No separate scholarship application required",
            "Automatic consideration via admission review",
        ],
        english_requirement="As per University of Miami undergraduate admission requirements; international students must demonstrate English proficiency.",
        application_method=[
            "Automatic consideration via University of Miami admission application (Early Decision I or Early Action)",
        ],
        best_fit="Exceptional incoming first-year students with outstanding academic achievement and leadership seeking full funding at University of Miami.",
        notes=(
            "No separate Stamps application; must apply Early Decision I or Early Action by November 1. Renewable for up "
            "to eight semesters with minimum 3.0 GPA. Enrichment fund supports study abroad, undergraduate research, "
            "unpaid internships. Not stackable with other merit scholarships."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="American University Emerging Global Leader Scholarship",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Fully Funded",
        official_source_url="https://www.american.edu/admissions/international/au-egls-apply.cfm",
        official_source="American University",
        deadline="January 15",
        deadline_date=date(2027, 1, 15),
        deadline_precision="month",
        application_period="Fall entry; applications open for following year's cycle",
        eligibility_summary=(
            "International students who need a non-immigrant visa (F-1 or J-1) to study in the U.S.; demonstrated "
            "commitment to leadership, volunteerism, and positive civic/social change in home country; must apply "
            "via Regular Decision."
        ),
        eligibility=[
            "International student who requires a non-immigrant visa (preferably F-1 or J-1).",
            "Demonstrated commitment to leadership, volunteerism, and community service.",
            "Dedicated to positive civic and social change in home country.",
            "Still enrolled in secondary/high school and graduating by June of entry year.",
            "Must apply via Regular Decision.",
        ],
        coverage=[
            "Full tuition",
            "Room and board",
            "Renewable for up to four years",
        ],
        required_documents=[
            "Common Application or Coalition Application",
            "AU EGL Scholarship application and essays (via applicant portal)",
            "Bank letter and AU Declaration of Finances Form (minimum $4,000)",
            "Official English proficiency test scores (TOEFL, IELTS, Duolingo, PTE, or Cambridge)",
            "All standard admission documents",
        ],
        english_requirement="TOEFL, IELTS, Duolingo English, PTE, or Cambridge Assessment English Test accepted.",
        application_method=[
            "Submit Common/Coalition Application by January 15, then submit AU EGL Scholarship application and essays via applicant portal",
        ],
        best_fit="High-achieving international students demonstrating exceptional leadership and commitment to social change.",
        notes=(
            "Only two full scholarships awarded per year; up to eight partial scholarships (up to $40,000/year) also "
            "available. Separate scholarship application required after admission application. Not eligible: U.S. citizens, "
            "permanent residents, dual citizens, or students already enrolled in post-secondary studies. Full scholarship does "
            "not cover non-billable expenses such as mandatory health insurance, books, airline tickets, taxes, and miscellaneous "
            "expenses (approximately US$4,000 per year out of pocket)."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="Jefferson Scholars Foundation Scholarship",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Fully Funded",
        official_source_url="https://www.jeffersonscholars.org/scholarships",
        official_source="Jefferson Scholars Foundation (University of Virginia)",
        deadline="December 1 (all nominating regions)",
        deadline_date=date(2026, 12, 1),
        deadline_precision="month",
        application_period="Nomination portal opens August; materials due December 1; regional review December-January; final interviews late February; decisions spring",
        eligibility_summary=(
            "Exceptional high school seniors demonstrating excellence in leadership, scholarship, and engaged citizenship; "
            "must be nominated by eligible high school (U.S. schools or international partner schools); must gain admission "
            "to University of Virginia separately."
        ),
        eligibility=[
            "High school senior (or equivalent final year) with exceptional record.",
            "Demonstrate excellence in leadership, scholarship, and engaged citizenship.",
            "Must be nominated by an eligible high school (U.S. schools in invited regions or international partner schools).",
            "Must gain admission to University of Virginia through regular admissions process.",
            "International students from countries with partner programs must be nominated through those schools.",
        ],
        coverage=[
            "Full tuition, fees, room, and board for four years",
            "Books and miscellaneous expenses",
            "Supplemental enrichment experiences (travel, leadership institutes, career development)",
            "For non-Virginians: over $83,000 per year, upwards of $405,000 total",
        ],
        required_documents=[
            "Nomination materials submitted by high school counselor and student",
            "Scholastic report/transcript",
            "Extracurricular record",
            "Two essays",
            "University of Virginia admission application (separate process)",
        ],
        english_requirement="As per University of Virginia undergraduate admission requirements.",
        application_method=[
            "Nomination-only through eligible high school; no direct individual application. Must also apply to UVA through regular admissions.",
        ],
        best_fit="Exceptional student leaders from around the world seeking full funding at University of Virginia.",
        notes=(
            "No direct application — only nominated students are considered. Approximately 36 scholars selected annually "
            "from ~3,000 nominations. SAT/ACT not considered for 2026-27 selection. Must be admitted to UVA separately to "
            "receive scholarship. International students eligible through partner schools in eligible countries."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="King-Morgridge Scholars Program",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Fully Funded",
        official_source_url="https://kmsp.wisc.edu/",
        official_source="University of Wisconsin-Madison",
        deadline="November 15 (scholarship application); November 1 (UW-Madison admission)",
        deadline_date=date(2026, 11, 15),
        deadline_precision="month",
        application_period="Fall entry; admission due November 1, scholarship due November 15",
        eligibility_summary=(
            "Students from Africa, Caribbean, Latin America, South Asia, or Southeast Asia; demonstrated academic "
            "success and commitment to poverty alleviation in home country; enterprising, creative, dedicated."
        ),
        eligibility=[
            "Citizen of or from Africa, Caribbean, Latin America, South Asia, or Southeast Asia.",
            "Demonstrated academic success and leadership.",
            "Committed to applying talents toward poverty alleviation in home country.",
            "Must apply for admission to UW-Madison by November 1.",
            "Must submit separate King-Morgridge scholarship application by November 15.",
        ],
        coverage=[
            "Full tuition and fees",
            "On-campus room and board",
            "Health insurance",
            "Round-trip airfare",
            "Stipend for miscellaneous expenses",
        ],
        required_documents=[
            "UW-Madison admission application",
            "King-Morgridge scholarship application (via WiSH portal)",
            "Academic transcripts",
            "Essays demonstrating commitment to poverty alleviation",
            "Letters of recommendation",
        ],
        english_requirement="As per UW-Madison undergraduate admission requirements.",
        application_method=[
            "Apply to UW-Madison by November 1, then submit separate KMSP application via Wisconsin Scholarship Hub (WiSH) by November 15",
        ],
        best_fit="Exceptional students from Africa, Caribbean, Latin America, South Asia, and Southeast Asia committed to poverty alleviation.",
        notes=(
            "Six scholarships awarded per year. Must be admitted to UW-Madison first. Selection based on drive, academic "
            "success, and commitment to addressing poverty. Cohort-based program with leadership development."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="Brandeis University Wien International Scholarship",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Need-based (up to full tuition)",
        official_source_url="https://www.brandeis.edu/isso/programs/wien/index.html",
        official_source="Brandeis University",
        deadline="Varies by admission deadline (Early Decision I: November 1; Early Decision II/Regular Decision: January 15)",
        deadline_precision="month",
        application_period="Automatic consideration upon admission application",
        eligibility_summary=(
            "International applicants to Brandeis University undergraduate program; strong academic achievement and "
            "significant extracurricular/community involvement; must demonstrate financial need via CSS Profile."
        ),
        eligibility=[
            "International applicant to Brandeis University undergraduate program.",
            "Strong academic achievement.",
            "Significant extracurricular or community involvement.",
            "Must demonstrate financial need (CSS Profile required).",
        ],
        coverage=[
            "Up to 100% of demonstrated financial need met",
            "May include tuition, fees, housing, and other expenses based on need",
        ],
        required_documents=[
            "Common Application or Coalition Application",
            "CSS Profile and supporting income/asset documentation",
            "No separate scholarship application required",
        ],
        english_requirement="As per Brandeis undergraduate admission requirements.",
        application_method=[
            "Automatic consideration upon applying for admission to Brandeis University",
        ],
        best_fit="Internationally accomplished students with strong academics and community involvement seeking need-based funding at Brandeis.",
        notes=(
            "Need-based only; no merit scholarships. Renewable for up to eight semesters based on continued demonstrated need. "
            "Must reapply for financial aid each year by March 1. Over 894 scholars from 115 countries funded since 1958."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="University of Minnesota Global Excellence Scholarship",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Partial",
        official_source_url="https://admissions.tc.umn.edu/global-excellence-scholarships",
        official_source="University of Minnesota Twin Cities",
        deadline="Early Action 1: November 1; Regular Decision: January 1",
        deadline_date=date(2026, 11, 1),
        deadline_precision="month",
        application_period="Automatic consideration upon admission application",
        eligibility_summary=(
            "International freshmen or transfer students on F-1 visa; strong academic merit; automatic consideration "
            "upon completing admission application by deadline."
        ),
        eligibility=[
            "International student on F-1 visa.",
            "Freshmen or transfer student admitted to University of Minnesota Twin Cities.",
            "Strong academic merit (top of high school class, record of strong academic preparation).",
            "Must maintain F-1 status to renew.",
        ],
        coverage=[
            "Freshmen: $5,000–$20,000 per year for up to four years",
            "Transfer: $10,000 per year for up to three years (fall entry)",
        ],
        required_documents=[
            "University of Minnesota admission application",
            "No separate scholarship application required",
            "Automatic consideration for F-1 students who complete application by deadline",
        ],
        english_requirement="As per University of Minnesota undergraduate admission requirements.",
        application_method=[
            "Automatic consideration upon admission application (no separate application)",
        ],
        best_fit="High-achieving international students seeking merit-based funding at University of Minnesota.",
        notes=(
            "Very competitive; limited number awarded each year. Recipients notified by end of March (freshmen) or May-June "
            "(transfers). Cannot be combined with other non-U of M funding without adjustment. Does not cover full cost of attendance."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="University of Iowa International Distinction in Education Award",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Partial",
        official_source_url="https://admissions.uiowa.edu/scholarship/international-distinction-education-award-idea",
        official_source="University of Iowa",
        deadline="February 1",
        deadline_date=date(2027, 2, 1),
        deadline_precision="month",
        application_period="Automatic consideration upon admission application",
        eligibility_summary=(
            "Incoming first-year international students (non-U.S. citizens/permanent residents) graduating from high "
            "school outside the U.S.; strong academic merit; automatic consideration upon admission."
        ),
        eligibility=[
            "Incoming first-year international student (non-U.S. citizen or permanent resident).",
            "Graduate of a high school outside the U.S.",
            "Strong academic merit based on holistic review of grades and test scores.",
            "Must maintain continuous full-time enrollment (12 semester hours).",
            "Minimum 2.50 cumulative UI GPA for renewal.",
        ],
        coverage=[
            "$2,000–$15,000 per year",
            "Renewable for up to eight semesters or until bachelor's degree",
        ],
        required_documents=[
            "University of Iowa admission application",
            "No separate scholarship application required",
            "Automatic consideration for eligible students upon admission",
        ],
        english_requirement="As per University of Iowa undergraduate admission requirements.",
        application_method=[
            "Automatic consideration upon admission application",
        ],
        best_fit="High-achieving international first-year students seeking merit-based funding at University of Iowa.",
        notes=(
            "Merit-based; competitive. Renewable based on academic performance and continuous enrollment. Must remain in "
            "international student status and pay nonresident tuition."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="Clark University Global Scholars Program",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Partial",
        official_source_url="https://www.clarku.edu/financial-aid/types/scholarships/",
        official_source="Clark University",
        deadline="Varies by admission deadline (Early Decision I/EA: November 1; Early Decision II/Regular Decision: January 15)",
        deadline_precision="month",
        application_period="Separate essay required in addition to admission application",
        eligibility_summary=(
            "First-year international applicants (or U.S. citizens/permanent residents who completed secondary school "
            "outside U.S.); demonstrated leadership potential and commitment to global impact; separate Global Scholars "
            "essay required."
        ),
        eligibility=[
            "First-year applicant to Clark University.",
            "International student, or U.S. citizen/permanent resident who completed entire secondary school outside the U.S.",
            "Demonstrated potential to provide leadership in community and world.",
            "Committed to making a difference globally.",
            "Submit separate Global Scholars essay.",
        ],
        coverage=[
            "Scholarship of no less than $15,000 per year ($60,000 for four years contingent upon meeting academic standards for renewal)",
            "Guaranteed $2,500 taxable stipend for paid internship or research assistantship during summer after sophomore or junior year",
        ],
        required_documents=[
            "Clark University admission application",
            "Separate Global Scholars Program essay",
            "All standard admission documents",
        ],
        english_requirement="As per Clark University undergraduate admission requirements.",
        application_method=[
            "Apply for admission to Clark University and submit separate Global Scholars Program essay",
        ],
        best_fit="Outstanding first-year students with demonstrated global leadership potential seeking funding at Clark University.",
        notes=(
            "Clark does not offer full-cost funding for international students. Admissions process is need-aware. "
            "Separate essay required for Global Scholars consideration in addition to admission application."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="Knight-Hennessy Scholars",
        country="USA",
        degree_levels="Graduate (Master's, JD, MBA, MD, MFA, MS, DMA, PhD, and joint/dual degrees)",
        funding_type="Fully Funded",
        official_source_url="https://knight-hennessy.stanford.edu/",
        official_source="Stanford University",
        deadline="October 6",
        deadline_date=date(2026, 10, 6),
        deadline_precision="month",
        application_period="Annual cohort selection; 2027 cohort applications open",
        eligibility_summary=(
            "All citizens and residents of all countries; no restrictions by age, field of study, or career aspiration; "
            "must apply to a Stanford graduate degree program; must demonstrate leadership, independence, and civic-mindedness."
        ),
        eligibility=[
            "All citizens and residents of all countries (no nationality restrictions).",
            "Hold equivalent of U.S. bachelor's degree from recognized institution.",
            "Must apply to and be admitted to a Stanford graduate degree program.",
            "Demonstrate leadership, independence, and civic-mindedness.",
            "No quotas by discipline, program, or world region.",
        ],
        coverage=[
            "Fellowship applied directly to cover tuition and associated fees for up to three years",
            "Stipend for living and academic expenses (room, board, books, supplies, local transportation, personal expenses)",
            "Annual travel stipend for one round-trip economy ticket to and from Stanford",
        ],
        required_documents=[
            "Knight-Hennessy Scholars application",
            "Stanford graduate degree program application (separate process)",
            "Transcripts",
            "CV/Resume",
            "Essays and short answers",
            "Two recommendation letters (video encouraged)",
            "Interview (if selected as finalist)",
        ],
        english_requirement="English proficiency as required by Stanford graduate program; TOEFL/IELTS may be required depending on program.",
        application_method=[
            "Apply to Knight-Hennessy Scholars program (separate from Stanford graduate application)",
            "Must also apply to and be admitted to a Stanford graduate degree program",
        ],
        best_fit="Exceptional graduate students from around the world seeking fully funded study and leadership development at Stanford.",
        notes=(
            "Fully endowed program; funding applies to degree program listed in initial admission letter. Scholars participate "
            "in King Global Leadership Program. No requirement for institutional endorsement. Highly competitive "
            "(~80-100 scholars selected per cohort)."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="Michigan State University International Merit Scholarships",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Partial",
        official_source_url="https://admissions.msu.edu/cost-aid/scholarships/international",
        official_source="Michigan State University",
        deadline="Priority deadline November 1 for early action decision by January 15",
        deadline_precision="month",
        application_period="Automatic consideration upon admission application",
        eligibility_summary=(
            "Incoming first-year international students with non-U.S. residency status; strong academic performance; "
            "automatic consideration for most scholarships upon admission."
        ),
        eligibility=[
            "Incoming first-year student with non-U.S. residency status.",
            "Strong academic performance with consideration of curriculum rigor.",
            "Maintain international residency for tuition purposes.",
            "Enroll minimum 12 credit hours each semester.",
        ],
        coverage=[
            "President's Scholarship: $15,000 annually",
            "Provost's Scholarship: $12,000 annually",
            "Dean's Scholarship: $10,000 annually",
            "1855 Scholarship: $7,000 annually",
            "Beaumont Tower Scholarship: $5,000 annually",
            "Global Community Scholars Scholarship: $3,000 annually",
            "Honors College Excellence Scholarship: $13,000 annually (for Honors College invitees)",
        ],
        required_documents=[
            "MSU admission application",
            "Automatic consideration for most awards upon admission",
            "No separate application required for most scholarships",
        ],
        english_requirement="As per Michigan State University undergraduate admission requirements.",
        application_method=[
            "Automatic consideration upon admission application (most awards); Honors College consideration automatic for all MSU applicants",
        ],
        best_fit="High-achieving international first-year students seeking merit-based funding at Michigan State University.",
        notes=(
            "Limited number of awards; meeting criteria does not guarantee offer. Awards contingent upon maintaining international residency for "
            "tuition. Some scholarships renewable for up to eight semesters. Honors College Excellence Scholarship requires invitation to Honors College."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
    ScholarshipIngestionRecord(
        name="University of Oregon International Cultural Service Program",
        country="USA",
        degree_levels="Bachelor's (undergraduate)",
        funding_type="Partial",
        official_source_url="https://isss.uoregon.edu/icsp",
        official_source="University of Oregon",
        deadline="Not announced for next cycle",
        deadline_precision="unknown",
        application_period="Fall admission; separate ICSP application required",
        eligibility_summary=(
            "New and continuing international students at University of Oregon; financial need and academic merit; "
            "commitment to cultural service and presentations about home country."
        ),
        eligibility=[
            "New or continuing international student at University of Oregon.",
            "Demonstrate financial need and academic merit.",
            "Minimum 3.0 cumulative GPA (for new students).",
            "Commitment to completing 66–80 hours of cultural service per year.",
            "Cannot be U.S. citizen, permanent resident, or eligible for U.S. federal assistance.",
        ],
        coverage=[
            "Partial tuition scholarship (approximately 50% of tuition)",
            "Renewable annually until completion of one UO degree",
        ],
        required_documents=[
            "University of Oregon admission application",
            "Separate ICSP scholarship application",
            "Academic transcripts",
            "Proof of international student status",
        ],
        english_requirement="As per University of Oregon undergraduate admission requirements.",
        application_method=[
            "Apply for admission to University of Oregon, then submit separate ICSP application",
        ],
        best_fit="International students at University of Oregon seeking partial tuition funding and interested in cross-cultural ambassadorship.",
        notes=(
            "Recipients must give presentations about their home culture to local schools and community organizations "
            "(66-80 hours/year). Renewable annually. New students must apply for admission by January 15. Must maintain 3.0 GPA."
        ),
        is_verified=True,
        last_verified_date=date(2026, 8, 31),
    ),
)

