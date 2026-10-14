# DO-NOT-DUPLICATE LIST + SCOPE RULES

## 1. Already in the ScholarZone database — do NOT produce a record for these

The live database is `backend/config/programme_details.json` (362 records) plus
`backend/config/new_scholarships.json` (87 records). Read both before you start, and grep
them for your target's awarding body and name. If your target is already there — or is a
near-duplicate of something there — pick a different target in the same region.

### Confirmed already present (bachelor-capable awards)
- Stipendium Hungaricum Scholarship (Hungary) — includes Bachelor's
- Hungarian Bilateral State Scholarships; Hungarian Diaspora Scholarship
- Finland national "Finland Scholarship"; University of Helsinki Tuition Fee Waivers /
  Helsinki Scholarship Programme
- Aalto University Excellence Scholarship; Aalto Reserve Scholarship
- Tampere University Scholarships; University of Oulu Tuition Fee Waivers
- University of Eastern Finland Tuition Waivers; University of Turku Tuition Fee Waivers
- Åbo Akademi University Tuition Fee Scholarships
- Danish Government Scholarship at SDU (Vejle — includes BSc)
- Lund University Global Scholarship (covers selected Bachelor programmes)
- Switzerland: ETH Zurich ESOP; EPFL Bachelor Excellence Fellowships; EPFL Social Scholarship;
  Hans Wilsdorf, Orlando Lauti, Charles-Edouard Guillaume Foundations (EPFL)
- Portugal: DGES Portugal Government Scholarship; University of Coimbra Merit Scholarships;
  University of Aveiro Incentive Scholarships; University of Porto Merit Scholarships;
  Nova SBE Merit Scholarship; Nova SBE DGES Social Mobility; Camões Fernão Mendes Pinto
- Czechia: Václav Havel Bursary
- UK: Reach Oxford Scholarship; LSE Excellence Scholarship; Cambridge Trust International
  Scholarship; Marshall Scholarship; Chevening Scholarships
- Ireland: Trinity College Dublin Global Excellence Undergraduate Scholarship
- Italy: University of Brescia STAR Scholarships (Foundation Year + Bachelor's);
  Bocconi ISU Bocconi Scholarship / Bocconi4Access to Education
- Switzerland: University of St.Gallen (HSG) Excellence Scholarships for Bachelor Students
- Australia: Melbourne International Undergraduate Scholarship;
  UTS Vice-Chancellor's International Undergraduate Scholarship;
  VUW Undergraduate International Scholarship (Victoria University of Wellington)
- Singapore: NUS International Undergraduate Scholarship; NTU Nanyang Global Scholarship
- USA: Harvard College Need-Based Financial Aid; Yale College Need-Based Financial Aid;
  MIT Undergraduate Financial Aid; University of Chicago International Scholarships;
  University of Miami Stamps Scholarship; Trinity University International Scholarships;
  Johnson & Wales University (JWU) Global Full Tuition Scholarship;
  UT Austin International Student Scholarships; Benjamin A. Gilman International Scholarship;
  Boren Awards; Fulbright Foreign Student Program; Fulbright U.S. Student Program
- Global: Global Undergraduate Exchange Program (Global UGRAD);
  Simmons University Kotzen Scholarship; KAIST International Student Scholarship;
  Yonsei Underwood International College; MEXT Scholarship for Undergraduate Students;
  Seoul National University President Fellowship Program;
  all Chinese Government Scholarship / CSC variants; Tsinghua Institutional Scholarship;
  ICCR Atal Bihari Vajpayee General Scholarship

### Also check before writing
`backend/config/new_scholarships.json` (87 records) — this is the newest batch and the most
likely to collide. `backend/config/purged_records_archive.json` (151 records) — anything
purged was disproved, so do not resurrect it.

---

## 2. Allowed host regions — research ONLY these

- **Europe** (incl. UK, Ireland, Switzerland — minus the exclusions above)
- **United States / America**
- **Canada**
- **Australia**
- **Singapore**
- **Malaysia**

`region` must be exactly one of:
`Europe`, `United States`, `Canada`, `Australia`, `Singapore`, `Malaysia`.

---

## 3. HARD EXCLUSIONS — never produce a record for these hosts

- **Middle East** — Bahrain, Egypt, Iran, Iraq, Israel, Jordan, Kuwait, Lebanon, Oman,
  Palestine, Qatar, Saudi Arabia, Syria, Türkiye/Turkey, UAE, Yemen
- Africa
- Latin America / South America / Central America / Caribbean
- South Asia — India, Bangladesh, Pakistan, Sri Lanka, Nepal, Bhutan, Maldives, Afghanistan
- East Asia — China, Japan, Korea, Taiwan, Mongolia *(unless physically hosted in an allowed region)*
- Central Asia
- South-East Asia other than Singapore and Malaysia
- Oceania other than Australia and New Zealand

An award **hosted** in an allowed region but whose eligibility is locked to a single
excluded nationality is still out of scope. Prefer broadly-open awards.

---

## 4. Degree-level rule

Only awards that fund a **bachelor's / undergraduate degree** (or a foundation year that
leads into one).

- Skip master's-only, PhD-only, postdoc, research-fellowship, professional-certificate.
- Skip one-semester non-degree exchanges, **unless** the award funds a full bachelor's degree.
- An award covering both bachelor's and master's is **in scope** — set
  `degree_levels: "Bachelor's"` and note the master's coverage in `notes` /
  `funding_duration`.

## 5. Substitution rule

If your assigned target is excluded, dead, master's-only, or already in the database:
**do not write the file for it.** Instead pick ONE alternative bachelor's scholarship in the
same host region that is not excluded, research that, and use the same output filename.
Record the substitution in `research_notes.substitution` and in your final message.