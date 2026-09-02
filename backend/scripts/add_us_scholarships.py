"""Add verified U.S. scholarships to the ScholarZone database.

Uses the existing upsert_verified_scholarships ingestion logic.
"""

from datetime import date
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import get_session_factory, init_database
from app.services.scholarship_ingestion import ScholarshipIngestionRecord, upsert_verified_scholarships


US_SCHOLARSHIPS = [
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
            "permanent residents, dual citizens, or students already enrolled in post-secondary studies."
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
        deadline="Varies by admission deadline (Early Decision I: November 1; Early Decision II/Regular Decision: January 2)",
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
        deadline="Priority deadline for freshmen (varies by admission plan); transfer priority deadline (varies)",
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
        deadline="Priority deadline for admission (typically February 1)",
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
        deadline="Varies by admission deadline (Early Decision I/EA: November 1; Early Decision II: January 15; Regular Decision: January 1)",
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
        deadline="Typically October annually (check official site for current cycle)",
        deadline_precision="month",
        application_period="Annual cohort selection; check official site for current cycle deadlines",
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
            "Limited number of awards; meeting criteria does not guarantee offer. Awards contingent upon maintaining "
            "international residency for tuition. Some scholarships renewable for up to eight semesters. Honors College "
            "Excellence Scholarship requires invitation to Honors College."
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
        deadline="January 15 for fall admission (check official site for current cycle)",
        deadline_precision="month",
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
]


def main() -> None:
    init_database()
    with get_session_factory()() as session:
        created_count, updated_count = upsert_verified_scholarships(session, US_SCHOLARSHIPS)

        # Verify results
        rows = session.scalars(
            __import__("sqlalchemy").select(__import__("app.models", fromlist=["Scholarship"]).Scholarship)
            .where(__import__("app.models", fromlist=["Scholarship"]).Scholarship.country == "USA")
        ).all()

    print(f"Created {created_count} scholarship record(s); updated {updated_count} record(s).")
    print(f"Total U.S. scholarships in database: {len(rows)}")
    for row in rows:
        print(f"  - ID={row.id} Title={row.title} Source={row.official_source_url}")


if __name__ == "__main__":
    main()
