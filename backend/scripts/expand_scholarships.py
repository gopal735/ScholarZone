"""Script to add new scholarship countries to additional_scholarships.py."""

# Read the original file
with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\temp_original.txt', 'r', encoding='utf-8') as f:
    content = f.read()

# Belgium scholarships
belgium_scholarships = '''
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
'''

# Hungary scholarships
hungary_scholarships = '''
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
'''

# Poland scholarships
poland_scholarships = '''
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
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
        official_source="European Commission / Polish Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes with Polish partners",
    ),
)
'''

# Czech Republic scholarships
czech_scholarships = '''
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
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
        official_source="European Commission / Czech Universities",
        is_verified=True,
        best_fit="Top-ranked international students for joint European Master's programmes with Czech partners",
    ),
)
'''

# Portugal scholarships
portugal_scholarships = '''
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
        official_source_url="https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters",
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
'''

# Combined section
combined_section = '''
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
'''

# Write the new file
new_content = content.rstrip() + belgium_scholarships + hungary_scholarships + poland_scholarships + czech_scholarships + portugal_scholarships + combined_section

with open(r'C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\app\data\additional_scholarships.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"File updated successfully. New size: {len(new_content)} chars")
