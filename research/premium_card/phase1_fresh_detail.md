# Phase 1 Fresh Read-Only Reconciliation

**Scope** — 70 premium-card research records reconciled against the authoritative 691-row `scholarships` table.

**Generated** 2026-10-06T15:13:49.250005+00:00  
**Access** READ-ONLY. sqlite3 opened via URI file:...?mode=ro&immutable=1. Database writes: 0. Git mutations: 0.

---

# Executive Summary

The intended repository was used throughout (`C:/Users/GopaL/Desktop/Projects folder/ScholarZone`, branch
`integrate/ci-tuition-p0-clean`, HEAD `bac50bf55816bfdea02df1b78c219f7df7be1771`). The database was opened
through a SQLite URI with `mode=ro&immutable=1`, so a write was physically impossible. No existing report was
overwritten; two new files were created.

Every claim from the previous run was re-derived from the data rather than accepted. Three of its headline
findings did not survive:

1. **DB 162 was a wrong match.** `research-065` (University of Coimbra, Portugal) was mapped to the
   University of **Vienna** row (Austria). The only shared signal was the English template
   "University of <X> ... Scholarships for International Students". Country, institution, domain and
   provider all conflict. `research-066` (University of Aveiro) was matched to DB 162 for the identical reason.
2. **DB 335 and DB 337 duplicate mappings were matcher errors, not legitimate duplicates.**
   - DB 335 = Aalto Excellence Scholarship: `research-009` is correct, `research-011` ("Aalto Reserve
     Scholarship") is wrong — the distinguishing token `Reserve` is absent from DB 335.
   - DB 337 = University of **Oulu**: `research-013` is correct, `research-015` is **University of Turku** and
     was never a candidate for the Oulu row. The same research-015 record was assigned to DB 337 by
     `merge_report.json` and to DB 266 by `reconciliation_report.json` — the pipeline contradicted itself
     19 minutes apart.
3. **The 14 records previously called "new" that are genuinely already in the DB** were mostly scored by a
   title-similarity threshold while ignoring provider, domain and institution evidence that was present.

Two records are worse than the previous run claimed: `research-017` reproduces a programme this database has
already retired as **NEVER-EXISTED** (`deletion_protected=1`), and `research-060` is a byte-level duplicate of
`research-036`.

---

## Verified Input State

| item | value |
|---|---|
| Database | `research/../backend/scholarzone.db` → `ScholarZone/backend/scholarzone.db` |
| Database size | 16,142,336 bytes, mtime 2026-10-06 20:07:37 |
| Table | `scholarships` |
| **Actual DB count** | **691** — `SELECT COUNT(*) FROM scholarships` |
| **Actual research count** | **70** JSON files in `research/premium_card/output/` |
| Frontend mirror | `frontend/public/research/premium_card/output/` = 71 files |
| Mirror integrity | all 70 research files **byte-identical (sha256)** to the mirror; mirror adds `index.json` (70 entries) |
| Repository HEAD | `bac50bf55816bfdea02df1b78c219f7df7be1771` |
| Branch | `integrate/ci-tuition-p0-clean` (no upstream configured; 0 ahead / 2 behind `origin/master`) |
| Working-tree state | 5 tracked modifications (ScholarshipCard.css/.jsx, ScholarshipList.css/.jsx, ScholarshipDetailsPage.jsx) — **left untouched** |
| Working-tree state | 384 untracked entries — **left untouched** |
| Approved-source domains | 20 rows in `approved_sources` |
| Database writes | **0** |
| Git mutations | **0** |

### Identity schema discovered

`scholarships` identity-bearing columns and their fill rate across 691 rows:

| column | non-empty | column | non-empty |
|---|---|---|---|
| `id` | 691 | `catalogue_url` | 498 |
| `title` | 691 | `official_updates_url` | 567 |
| `country` | 691 | `program_type` | 616 |
| `degree` | 691 | `duration` | 577 |
| `funding` | 691 | `application_period` | 614 |
| `application_link` | 691 | `deadline_display` | 640 |
| `official_source_url` | 691 | `deadline_date` | 233 |
| `official_source` | 687 | `status` / `verification_status` | 691 / 691 |

`status`: open 433, upcoming 213, closing-soon 44, closed 1. 
`verification_status`: active 543, needs_review 95, quarantined 53. 
`is_archived`: 639 false / 52 true. These three flags gate any write and are reported per record.

Research identity fields per record: `data.title`, `data.provider`, `data.official_sources[].url`,
`data.application.official_application_url`, `data.deadlines.deadline_date`, `data.funding`,
`data.eligibility.degree`, plus `source_file` batch provenance.

**Data-quality note on the Finland batch (research-006 … research-030):** all 25 records carry
`research_errors: ["No official URL provided in source file"]` and `missing_key_fields: ["official_url"]`,
`coverage_level: low`. URL matching is impossible for them, so identity rests on provider + institution + title.
Seven further records (003, 041, 043, 048, 050, 065, 068) carry `"Failed to fetch official page"`.

Encoding was verified clean: the Å in "Åbo Akademi" is stored as the correct UTF-8 bytes `C3 85`. No
mojibake exists in the research files. Any mojibake seen in console output is a terminal rendering artefact.

---

## Classification Totals

| class | meaning | count |
|---|---|---|
| **A** | CONFIRMED EXISTING MATCH | **24** |
| **B** | EXISTING MATCH WITH CONFLICT | **4** |
| **C** | UNCERTAIN EXISTING MATCH / HUMAN REVIEW | **10** |
| **D** | LIKELY NEW RECORD | **30** |
| **E** | DUPLICATE / INVALID RESEARCH RECORD | **2** |
| | **total** | **70** |

Proposed actions:

| action | count |
|---|---|
| `DUPLICATE_RESEARCH` | 2 |
| `MANUAL_REVIEW` | 14 |
| `SAFE_ENRICH_EXISTING` | 24 |
| `SAFE_NEW_RECORD_CANDIDATE` | 30 |

---

## Full 70-Record Reconciliation

Every record, ordered by research ID.

### research-001 — A (HIGH)

- **File** `scholarship_001_Danish_Government_Scholarship_at_the_Uni.json`  (batch `denmark_scholarships.json`)
- **Research title** Danish Government Scholarship at the University of Copenhagen
- **Research provider** University of Copenhagen (UCPH), funded by the Danish Ministry of Higher Education and Science
- **Research URL** `https://www.ku.dk/studies/masters/application-and-admission/scholarships`, `https://www.ku.dk/studies/masters/application-and-admission/scholarships`
- **Inferred country** Denmark
- **DB match** **271** — University of Copenhagen Danish Government Scholarship
- **Top 3 candidates** 271, 329, 270
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Danish Government Scholarship at the University of Copenhagen` vs DB `University of Copenhagen Danish Government Scholarship` — identical_after_normalisation=False, idf-jaccard=1.0, containment=1.0, seq=0.5043
- *Provider comparison* research `University of Copenhagen (UCPH), funded by the Danish Ministry of Higher Education and Science` vs DB `University of Copenhagen` — exact=False, score=0.202
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ku.dk'], aggregator_page=False, conflict=False
- *Country comparison* research=Denmark (institution_gazetteer) vs DB=Denmark → agree=True
- *Institution comparison* distinctive research tokens `['ucph', 'copenhagen', 'danish', 'higher']`, aligned `['copenhagen', 'danish']`, alignment=0.2546; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ku.dk']
  - strong title similarity (idf-jaccard 1.00, containment 1.00, seq 0.50)
  - country agrees (Denmark)
- *Conflicting evidence*
  - provider mismatch: research 'University of Copenhagen (UCPH), funded by the Danish Ministry of Higher Education and Science' vs DB 'University of Copenhagen'
- *Prior report* category=A, prior target=271, merge target=271
- *Final reasoning* Title token sets are identical (danish/government/scholarship/university/copenhagen). Registrable domain ku.dk is shared by the research URL and DB 271 official_source_url/application_link. Country and degree level (Master's) both agree. No URL conflict.

### research-002 — A (HIGH)

- **File** `scholarship_002_Danish_State_Scholarship_at_Aarhus_Unive.json`  (batch `denmark_scholarships.json`)
- **Research title** Danish State Scholarship at Aarhus University
- **Research provider** Aarhus University (AU), funded by the Danish state
- **Research URL** `https://masters.au.dk/scholarships-and-grants`, `https://masters.au.dk/scholarships-and-grants`
- **Inferred country** Denmark
- **DB match** **272** — Aarhus University Danish State Scholarship
- **Top 3 candidates** 272, 330, 268
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Danish State Scholarship at Aarhus University` vs DB `Aarhus University Danish State Scholarship` — identical_after_normalisation=False, idf-jaccard=1.0, containment=1.0, seq=0.5517
- *Provider comparison* research `Aarhus University (AU), funded by the Danish state` vs DB `Aarhus University` — exact=False, score=0.2753
- *URL comparison* exact_canonical_overlap=['masters.au.dk/scholarships-and-grants'], domain_overlap=['au.dk'], aggregator_page=False, conflict=False
- *Country comparison* research=Denmark (institution_gazetteer) vs DB=Denmark → agree=True
- *Institution comparison* distinctive research tokens `['au', 'aarhus', 'danish', 'state']`, aligned `['aarhus', 'danish', 'state']`, alignment=0.5153; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (masters.au.dk/scholarships-and-grants)
  - shared registrable domain: ['au.dk']
  - strong title similarity (idf-jaccard 1.00, containment 1.00, seq 0.55)
  - country agrees (Denmark)
- *Conflicting evidence*
  - provider mismatch: research 'Aarhus University (AU), funded by the Danish state' vs DB 'Aarhus University'
- *Prior report* category=A, prior target=272, merge target=272
- *Final reasoning* Canonical URL masters.au.dk/scholarships-and-grants is byte-identical to DB 272 official_source_url, application_link AND official_updates_url. Title token sets identical. Provider is a superset of DB provider. Country agrees.

### research-003 — A (HIGH)

- **File** `scholarship_003_Tuition_Fee_Waiver_for_International_MSc.json`  (batch `denmark_scholarships.json`)
- **Research title** Tuition Fee Waiver for International MSc Students at the Technical University of Denmark (DTU)
- **Research provider** Technical University of Denmark (DTU)
- **Research URL** `https://www.dtu.dk/english/education/graduate/fees-and-funding/tuition_fee_waivers`, `https://www.dtu.dk/english/education/graduate/fees-and-funding/tuition_fee_waivers`
- **Inferred country** Denmark
- **DB match** **269** — DTU Tuition Fee Waiver for International non-EU/EEA MSc Students
- **Top 3 candidates** 269, 331, 273
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Tuition Fee Waiver for International MSc Students at the Technical University of Denmark (DTU)` vs DB `DTU Tuition Fee Waiver for International non-EU/EEA MSc Students` — identical_after_normalisation=False, idf-jaccard=0.5058, containment=0.701, seq=0.6282
- *Provider comparison* research `Technical University of Denmark (DTU)` vs DB `Technical University of Denmark (DTU)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['dtu.dk'], aggregator_page=False, conflict=False
- *Country comparison* research=Denmark (institution_gazetteer) vs DB=Denmark → agree=True
- *Institution comparison* distinctive research tokens `['dtu', 'technical', 'msc', 'denmark']`, aligned `['dtu', 'technical', 'msc', 'denmark']`, alignment=0.5198; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['dtu.dk']
  - provider string identical
  - country agrees (Denmark)
- *Prior report* category=D, prior target=269, merge target=None
- *Final reasoning* Provider string is exactly identical (Technical University of Denmark (DTU)). Registrable domain dtu.dk shared. Degree level Master's on both sides. The prior run scored this 0.52 and called it new purely because the title differs in wording; the identity is in fact unambiguous.

### research-004 — A (HIGH)

- **File** `scholarship_004_Danish_Government_Scholarship_at_the_Uni.json`  (batch `denmark_scholarships.json`)
- **Research title** Danish Government Scholarship at the University of Southern Denmark (SDU)
- **Research provider** University of Southern Denmark (SDU), funded by the Danish government
- **Research URL** `https://www.sdu.dk/en/uddannelse/fees_and_funding/scholarships`, `https://www.sdu.dk/en/uddannelse/fees_and_funding/scholarships`
- **Inferred country** Denmark
- **DB match** **273** — University of Southern Denmark (SDU) Danish Government Scholarship
- **Top 3 candidates** 273, 268, 329
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Danish Government Scholarship at the University of Southern Denmark (SDU)` vs DB `University of Southern Denmark (SDU) Danish Government Scholarship` — identical_after_normalisation=False, idf-jaccard=1.0, containment=1.0, seq=0.5037
- *Provider comparison* research `University of Southern Denmark (SDU), funded by the Danish government` vs DB `University of Southern Denmark (SDU)` — exact=False, score=0.6166
- *URL comparison* exact_canonical_overlap=['sdu.dk/en/uddannelse/fees_and_funding/scholarships'], domain_overlap=['sdu.dk'], aggregator_page=False, conflict=False
- *Country comparison* research=Denmark (institution_gazetteer) vs DB=Denmark → agree=True
- *Institution comparison* distinctive research tokens `['southern', 'sdu', 'denmark', 'danish']`, aligned `['southern', 'sdu', 'denmark', 'danish']`, alignment=0.6802; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (sdu.dk/en/uddannelse/fees_and_funding/scholarships)
  - shared registrable domain: ['sdu.dk']
  - provider token overlap 0.62
  - strong title similarity (idf-jaccard 1.00, containment 1.00, seq 0.50)
  - country agrees (Denmark)
- *Prior report* category=A, prior target=273, merge target=273
- *Final reasoning* Canonical URL sdu.dk/en/uddannelse/fees_and_funding/scholarships is identical to DB 273 official_updates_url. Title token sets identical. Country Denmark. Degree (Bachelor's, Master's) consistent.

### research-005 — A (MEDIUM)

- **File** `scholarship_005_International_Student_Scholarship_at_Aal.json`  (batch `denmark_scholarships.json`)
- **Research title** International Student Scholarship at Aalborg University (AAU)
- **Research provider** Aalborg University (AAU), funded by the Danish government
- **Research URL** `https://www.en.aau.dk/education/apply/master/finance-and-fees/`, `https://www.en.aau.dk/education/apply/master/finance-and-fees/`
- **Inferred country** Denmark
- **DB match** **332** — Aalborg University International Student Scholarship (tuition fee waiver and monthly stipend)
- **Top 3 candidates** 332, 268, 329
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `International Student Scholarship at Aalborg University (AAU)` vs DB `Aalborg University International Student Scholarship (tuition fee waiver and monthly stipend)` — identical_after_normalisation=False, idf-jaccard=0.3355, containment=0.7089, seq=0.56
- *Provider comparison* research `Aalborg University (AAU), funded by the Danish government` vs DB `Aalborg University` — exact=False, score=0.2987
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['aau.dk'], aggregator_page=False, conflict=False
- *Country comparison* research=Denmark (institution_gazetteer) vs DB=Denmark → agree=True
- *Institution comparison* distinctive research tokens `['aau', 'aalborg', 'danish', 'funded']`, aligned `['aalborg']`, alignment=0.1782; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['aau.dk']
  - strong title similarity (idf-jaccard 0.34, containment 0.71, seq 0.56)
  - country agrees (Denmark)
- *Conflicting evidence*
  - provider mismatch: research 'Aalborg University (AAU), funded by the Danish government' vs DB 'Aalborg University'
- *Prior report* category=D, prior target=332, merge target=None
- *Final reasoning* Registrable domain aau.dk shared (www.en.aau.dk vs en.aau.dk). Provider 'Aalborg University (AAU)' is a superset of DB provider 'Aalborg University'. Every distinctive research title token appears in DB 332's title. Degree Master's on both sides.

### research-006 — A (MEDIUM)

- **File** `scholarship_006_University_of_Helsinki_RESDOC_Doctoral_R.json`  (batch `finland-scholarships.json`)
- **Research title** University of Helsinki RESDOC Doctoral Researcher Positions 2026 (30 Fully Funded PhD Positions)
- **Research provider** University of Helsinki Doctoral School (UHDS), funded by Horizon Europe MSCA COFUND and University of Helsinki
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **333** — RESDOC Doctoral Researcher Positions - Resilient and Just Systems Doctoral Project (MSCA COFUND)
- **Top 3 candidates** 334, 333, 256
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `University of Helsinki RESDOC Doctoral Researcher Positions 2026 (30 Fully Funded PhD Positions)` vs DB `University-funded doctoral researcher positions (University of Helsinki Doctoral School)` — identical_after_normalisation=False, idf-jaccard=0.4767, containment=0.5134, seq=0.6
- *Provider comparison* research `University of Helsinki Doctoral School (UHDS), funded by Horizon Europe MSCA COFUND and University of Helsinki` vs DB `University of Helsinki` — exact=False, score=0.1469
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['horizon', 'cofund', 'uhds', 'resdoc']`, aligned `[]`, alignment=0.0; degree research `['doctoral', 'phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'University of Helsinki Doctoral School (UHDS), funded by Horizon Europe MSCA COFUND and University of Helsinki' vs DB 'University of Helsinki'
- *Prior report* category=D, prior target=334, merge target=None
- *Final reasoning* The programme-distinguishing token 'RESDOC' occurs verbatim in DB 333's title ('RESDOC Doctoral Researcher Positions ... (MSCA COFUND)'), and the research provider names Horizon Europe MSCA COFUND exactly as DB 333 does. Institution (University of Helsinki) and country agree. The prior run picked DB 334, which is a DIFFERENT Helsinki doctoral scheme (university-funded, not MSCA COFUND) - a wrong-row match.

### research-007 — A (HIGH)

- **File** `scholarship_007_University-funded_Doctoral_Researcher_Po.json`  (batch `finland-scholarships.json`)
- **Research title** University-funded Doctoral Researcher Positions 2026 (Salaried PhD Positions)
- **Research provider** University of Helsinki Doctoral School (UHDS)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **334** — University-funded doctoral researcher positions (University of Helsinki Doctoral School)
- **Top 3 candidates** 334, 333, 264
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `University-funded Doctoral Researcher Positions 2026 (Salaried PhD Positions)` vs DB `University-funded doctoral researcher positions (University of Helsinki Doctoral School)` — identical_after_normalisation=False, idf-jaccard=0.4802, containment=0.6109, seq=0.6832
- *Provider comparison* research `University of Helsinki Doctoral School (UHDS)` vs DB `University of Helsinki` — exact=False, score=0.337
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['uhds', 'salaried', 'researcher', 'helsinki']`, aligned `['researcher', 'helsinki']`, alignment=0.2192; degree research `['doctoral', 'phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'University of Helsinki Doctoral School (UHDS)' vs DB 'University of Helsinki'
- *Prior report* category=D, prior target=334, merge target=None
- *Final reasoning* Research title minus the year qualifier tokenises to the same set as DB 334 'University-funded doctoral researcher positions (University of Helsinki Doctoral School)'. Institution and country agree.

### research-008 — A (MEDIUM)

- **File** `scholarship_008_University_of_Helsinki_Tuition_Fee_Waive.json`  (batch `finland-scholarships.json`)
- **Research title** University of Helsinki Tuition Fee Waivers (50% or 100%)
- **Research provider** University of Helsinki
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **264** — University of Helsinki Scholarship Programme (tuition fee waivers)
- **Top 3 candidates** 264, 334, 333
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `University of Helsinki Tuition Fee Waivers (50% or 100%)` vs DB `University of Helsinki Scholarship Programme (tuition fee waivers)` — identical_after_normalisation=False, idf-jaccard=0.5739, containment=0.6594, seq=0.7241
- *Provider comparison* research `University of Helsinki` vs DB `University of Helsinki` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['helsinki', '50', '100', 'waivers']`, aligned `['helsinki', 'waivers']`, alignment=0.3366; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Finland)
- *Prior report* category=D, prior target=264, merge target=264
- *Final reasoning* Provider string exactly identical (University of Helsinki). DB 264's program_type is 'Merit-based tuition fee waiver, 50% or 100%', which matches the research title's '(50% or 100%)' qualifier verbatim. Degree Master's agrees.

### research-009 — A (HIGH)

- **File** `scholarship_009_Aalto_University_Excellence_Scholarship_.json`  (batch `finland-scholarships.json`)
- **Research title** Aalto University Excellence Scholarship (100% Tuition Fee Waiver)
- **Research provider** Aalto University
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **335** — Aalto University Excellence Scholarship (100% tuition fee waiver)
- **Top 3 candidates** 335, 263, 264
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Aalto University Excellence Scholarship (100% Tuition Fee Waiver)` vs DB `Aalto University Excellence Scholarship (100% tuition fee waiver)` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `Aalto University` vs DB `Aalto University` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['100', 'aalto', 'waiver', 'fee']`, aligned `['100', 'aalto', 'waiver', 'fee']`, alignment=0.6445; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - title identical after normalisation
  - country agrees (Finland)
- *Prior report* category=A, prior target=335, merge target=335
- *Final reasoning* Title is identical after normalisation; provider exactly identical; country agrees. NOTE a DB-internal duplication: DB 263 ('Aalto University Excellence Scholarship') describes the same real-world scholarship with only 0.50 idf-jaccard overlap. 335 is the correct target because the title matches it exactly; the 263/335 duplication is a separate DB data-quality defect that must be resolved independently.

### research-010 — D (HIGH)

- **File** `scholarship_010_Aalto_University_Pekka_Mattila_Excellenc.json`  (batch `finland-scholarships.json`)
- **Research title** Aalto University Pekka Mattila Excellence Scholarship (€3,000 Relocation Grant)
- **Research provider** Aalto University School of Business (Nokia Foundation through Pekka Mattila memory fund)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 335, 263, 265
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Aalto University Pekka Mattila Excellence Scholarship (€3,000 Relocation Grant)` vs DB `Aalto University Excellence Scholarship (100% tuition fee waiver)` — identical_after_normalisation=False, idf-jaccard=0.1954, containment=0.2793, seq=0.7101
- *Provider comparison* research `Aalto University School of Business (Nokia Foundation through Pekka Mattila memory fund)` vs DB `Aalto University` — exact=False, score=0.131
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['000', 'relocation', 'memory', 'mattila']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'Aalto University School of Business (Nokia Foundation through Pekka Mattila memory fund)' vs DB 'Aalto University'
- *Prior report* category=D, prior target=263, merge target=None
- *Final reasoning* No DB row represents this scheme. The distinguishing tokens 'Pekka', 'Mattila' and 'Relocation' align with no DB row, and DB 263's own notes field explicitly enumerates it as a DIFFERENT scheme that must not be confused with the Excellence Scholarship: 'the Pekka Mattila Excellence Scholarship (EUR 3,000 relocation grant for the Master's Programme in Marketing and International Management)'. The prior run attached it to DB 263 at score 0.45 - right conclusion, wrong reason.

### research-011 — C (LOW)

- **File** `scholarship_011_Aalto_Reserve_Scholarship_100_Tuition_Fe.json`  (batch `finland-scholarships.json`)
- **Research title** Aalto Reserve Scholarship (100% Tuition Fee Waiver)
- **Research provider** Aalto University
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **335** — Aalto University Excellence Scholarship (100% tuition fee waiver)
- **Top 3 candidates** 335, 263, 264
- **Classification** **C**, confidence **LOW**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Aalto Reserve Scholarship (100% Tuition Fee Waiver)` vs DB `Aalto University Excellence Scholarship (100% tuition fee waiver)` — identical_after_normalisation=False, idf-jaccard=0.6822, containment=0.7952, seq=0.8
- *Provider comparison* research `Aalto University` vs DB `Aalto University` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['reserve', '100', 'aalto', 'waiver']`, aligned `['100', 'aalto', 'waiver']`, alignment=0.4582; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - strong title similarity (idf-jaccard 0.68, containment 0.80, seq 0.80)
  - country agrees (Finland)
- *Prior report* category=A, prior target=335, merge target=335
- *Final reasoning* UNRESOLVED NAME COLLISION. Provider is exactly Aalto University, but the distinguishing token 'Reserve' occurs in no DB row, so this cannot be the Excellence Scholarship. It also cannot be asserted as new: nothing in the DB confirms or denies an 'Aalto Reserve Scholarship'. The prior run committed this as a confirmed match to DB 335 (confidence 0.75) - this is one of the two duplicate mappings under investigation and it is a matcher error driven by the generic tokens '100% tuition fee waiver'.

### research-012 — C (MEDIUM)

- **File** `scholarship_012_Tampere_University_Scholarships_Tuition_.json`  (batch `finland-scholarships.json`)
- **Research title** Tampere University Scholarships (Tuition Fee Waiver + International Advancement Scholarship)
- **Research provider** Tampere University
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **336** — Tampere University tuition fee scholarship (50%) and early bird offer
- **Top 3 candidates** 265, 336, 335
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Tampere University Scholarships (Tuition Fee Waiver + International Advancement Scholarship)` vs DB `Tampere University Tuition Fee Scholarship` — identical_after_normalisation=False, idf-jaccard=0.5223, containment=0.5223, seq=0.6462
- *Provider comparison* research `Tampere University` vs DB `Tampere University` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['advancement', 'tampere', 'waiver', 'fee']`, aligned `['tampere', 'fee']`, alignment=0.3029; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Finland)
- *Prior report* category=A, prior target=265, merge target=None
- *Final reasoning* Provider exactly identical (Tampere University), but two competing DB rows exist for the Tampere tuition scholarship: DB 336 (active) and DB 265 (archived AND quarantined). The research title's third element 'International Advancement Scholarship' matches neither row's title. Row selection cannot be made automatically.

### research-013 — A (HIGH)

- **File** `scholarship_013_University_of_Oulu_Tuition_Fee_Waivers_a.json`  (batch `finland-scholarships.json`)
- **Research title** University of Oulu Tuition Fee Waivers and Early Bird Discount
- **Research provider** University of Oulu
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **337** — University of Oulu Early Bird Discount and Tuition Fee Waiver Scholarship
- **Top 3 candidates** 337, 338, 266
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `University of Oulu Tuition Fee Waivers and Early Bird Discount` vs DB `University of Oulu Early Bird Discount and Tuition Fee Waiver Scholarship` — identical_after_normalisation=False, idf-jaccard=0.7271, containment=0.8557, seq=0.563
- *Provider comparison* research `University of Oulu` vs DB `University of Oulu` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['oulu', 'waivers', 'bird', 'discount']`, aligned `['oulu', 'bird', 'discount']`, alignment=0.4494; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - strong title similarity (idf-jaccard 0.73, containment 0.86, seq 0.56)
  - country agrees (Finland)
- *Prior report* category=A, prior target=337, merge target=337
- *Final reasoning* Provider exactly identical (University of Oulu). The three distinguishing tokens 'oulu', 'bird', 'discount' all align with DB 337, whose image_alt_text is verbatim the research title ('University of Oulu Tuition Fee Waivers and Early Bird Discount - official Oulu.Fi image'). Country agrees. This is the LEGITIMATE half of the DB 337 duplicate mapping.

### research-014 — A (HIGH)

- **File** `scholarship_014_University_of_Eastern_Finland_UEF_Tuitio.json`  (batch `finland-scholarships.json`)
- **Research title** University of Eastern Finland (UEF) Tuition Waivers (30% or 50%)
- **Research provider** University of Eastern Finland
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **338** — University of Eastern Finland Early Bird Discount (30%) and Tuition Waivers
- **Top 3 candidates** 338, 264, 337
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `University of Eastern Finland (UEF) Tuition Waivers (30% or 50%)` vs DB `University of Eastern Finland Early Bird Discount (30%) and Tuition Waivers` — identical_after_normalisation=False, idf-jaccard=0.5167, containment=0.7053, seq=0.7231
- *Provider comparison* research `University of Eastern Finland` vs DB `University of Eastern Finland` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['uef', 'eastern', '30', '50']`, aligned `['eastern', '30']`, alignment=0.2983; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Finland)
- *Prior report* category=D, prior target=338, merge target=None
- *Final reasoning* Provider exactly identical (University of Eastern Finland). The percentage qualifier '(30% or 50%)' aligns with DB 338's 'Early Bird Discount (30%) and Tuition Waivers'. Country agrees.

### research-015 — C (MEDIUM)

- **File** `scholarship_015_University_of_Turku_Tuition_Fee_Waivers_.json`  (batch `finland-scholarships.json`)
- **Research title** University of Turku Tuition Fee Waivers and Early Bird Discount
- **Research provider** University of Turku
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **339** — University of Turku Merit Scholarship (50% of tuition) and Early Bird Discount
- **Top 3 candidates** 339, 266, 338
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `University of Turku Tuition Fee Waivers and Early Bird Discount` vs DB `University of Turku Merit Scholarship (50% of tuition) and Early Bird Discount` — identical_after_normalisation=False, idf-jaccard=0.5591, containment=0.7345, seq=0.7391
- *Provider comparison* research `University of Turku` vs DB `University of Turku` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['turku', 'waivers', 'bird', 'discount']`, aligned `['turku', 'bird', 'discount']`, alignment=0.4453; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - provider string identical
  - strong title similarity (idf-jaccard 0.56, containment 0.73, seq 0.74)
  - country agrees (Finland)
- *Prior report* category=A, prior target=266, merge target=337
- *Final reasoning* Provider exactly identical (University of Turku), which decisively rules out DB 337 (University of Oulu) - the target the prior merge committed to. However DB contains TWO near-identical Turku rows for this same scholarship: DB 339 (idf-jaccard 0.75 to DB 266). Both are active. Choosing between them is a human decision, so this is held for review rather than auto-enriched.

### research-016 — A (HIGH)

- **File** `scholarship_016__bo_Akademi_University_Tuition_Fee_Schol.json`  (batch `finland-scholarships.json`)
- **Research title** Åbo Akademi University Tuition Fee Scholarships (Early Commitment + Fee Waivers)
- **Research provider** Åbo Akademi University
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **340** — Åbo Akademi University tuition fee scholarship - early commitment offer and second-year reduction
- **Top 3 candidates** 340, 336, 265
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Åbo Akademi University Tuition Fee Scholarships (Early Commitment + Fee Waivers)` vs DB `Åbo Akademi University tuition fee scholarship - early commitment offer and second-year reduction` — identical_after_normalisation=False, idf-jaccard=0.5004, containment=0.808, seq=0.8187
- *Provider comparison* research `Åbo Akademi University` vs DB `Åbo Akademi University` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['abo', 'akademi', 'commitment', 'waivers']`, aligned `['abo', 'akademi', 'commitment']`, alignment=0.4494; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - provider string identical
  - strong title similarity (idf-jaccard 0.50, containment 0.81, seq 0.82)
  - country agrees (Finland)
- *Prior report* category=D, prior target=340, merge target=None
- *Final reasoning* Provider exactly identical (Abo Akademi University after accent folding). Distinguishing tokens 'abo', 'akademi', 'commitment' align; the research qualifier '(Early Commitment + Fee Waivers)' matches DB 340's 'early commitment offer and second-year reduction'. The prior run scored 0.467 and called it new because its tokenizer could not handle the A-ring character.

### research-017 — E (HIGH)

- **File** `scholarship_017_Finland_Scholarship_National_Programme_f.json`  (batch `finland-scholarships.json`)
- **Research title** Finland Scholarship (National Programme for Master's Students)
- **Research provider** Ministry of Education and Culture, Finland; administered by Finnish universities through the national Studyinfo.fi application
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **341** — Finland Scholarship (National Programme for Master's Students)
- **Top 3 candidates** 341, 262, 267
- **Classification** **E**, confidence **HIGH**
- **Proposed action** `DUPLICATE_RESEARCH`

- *Title comparison* research `Finland Scholarship (National Programme for Master's Students)` vs DB `Finland Scholarship (National Programme for Master's Students)` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `Ministry of Education and Culture, Finland; administered by Finnish universities through the national Studyinfo.fi application` vs DB `Studyinfinland.Fi` — exact=False, score=0.0945
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['studyinfo', 'fi', 'finnish', 'through']`, aligned `['fi']`, alignment=0.088; degree research `['master']` vs DB `['master']` agree=True
- *Supporting evidence*
  - title identical after normalisation
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'Ministry of Education and Culture, Finland; administered by Finnish universities through the national Studyinfo.fi application' vs DB 'Studyinfinland.Fi'
- *Prior report* category=A, prior target=341, merge target=341
- *Final reasoning* INVALID RESEARCH RECORD - reproduces a programme this database has already debunked. The title is identical to DB 341, but DB 341 is verification_status=quarantined, is_archived=1, with archived_reason 'NEVER-EXISTED: RETIRED - the awarding body's own current page denies that the programme exists' and deletion_protected=1. DB 262 independently records that Finland has 'no national government scholarship programme'. The prior run classified this as a CONFIRMED match (score 1.05) to DB 341, which would have resurrected a deliberately retired record.

### research-018 — C (MEDIUM)

- **File** `scholarship_018_Hanken_School_of_Economics_Premium_Schol.json`  (batch `finland-scholarships.json`)
- **Research title** Hanken School of Economics Premium Scholarship
- **Research provider** Hanken School of Economics (GBSN collaboration)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **342** — Hanken GBSN Honor Scholarship (GBSN Scholarship for students from developing countries)
- **Top 3 candidates** 342, 343, 265
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Hanken School of Economics Premium Scholarship` vs DB `Hanken GBSN Honor Scholarship (GBSN Scholarship for students from developing countries)` — identical_after_normalisation=False, idf-jaccard=0.1578, containment=0.342, seq=0.3817
- *Provider comparison* research `Hanken School of Economics (GBSN collaboration)` vs DB `Hanken School of Economics` — exact=False, score=0.5634
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['gbsn', 'hanken', 'premium', 'collaboration']`, aligned `['gbsn', 'hanken']`, alignment=0.3611; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - provider token overlap 0.56
  - country agrees (Finland)
- *Conflicting evidence*
  - title dissimilar (score 0.29)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* Institution matches exactly (Hanken School of Economics) and the research provider's 'GBSN collaboration' matches DB 342's GBSN Honor Scholarship. But the scholarship NAME conflicts: research says 'Premium Scholarship', DB 342 says 'GBSN Honor Scholarship'. These may be the same scheme under two names or two separate schemes; the DB cannot settle it.

### research-019 — A (MEDIUM)

- **File** `scholarship_019_Nokia_Scholarship_ICT_Doctoral_Studies_.json`  (batch `finland-scholarships.json`)
- **Research title** Nokia Scholarship (ICT Doctoral Studies)
- **Research provider** Nokia Foundation
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **343** — Nokia Scholarship
- **Top 3 candidates** 345, 344, 343
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Nokia Scholarship (ICT Doctoral Studies)` vs DB `Jorma Ollila Grant` — identical_after_normalisation=False, idf-jaccard=0.0, containment=0.0, seq=0.3571
- *Provider comparison* research `Nokia Foundation` vs DB `Nokia Foundation` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['ict', 'nokia', 'studies', 'doctoral']`, aligned `['nokia']`, alignment=0.2125; degree research `['doctoral']` vs DB `['doctoral', 'phd', 'postdoctoral']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Finland)
- *Conflicting evidence*
  - title dissimilar (score 0.27)
- *Prior report* category=D, prior target=343, merge target=None
- *Final reasoning* Provider exactly identical (Nokia Foundation). The scholarship name 'Nokia Scholarship' matches DB 343's title exactly; '(ICT Doctoral Studies)' is a qualifier and DB 343's degree is PhD, consistent. Competitor DB 344 ('Nokia Foundation Fellow') is the subject of research-020, so it is correctly excluded here.

### research-020 — A (MEDIUM)

- **File** `scholarship_020_Nokia_Foundation_Fellow_ICT_Research_Pro.json`  (batch `finland-scholarships.json`)
- **Research title** Nokia Foundation Fellow (ICT Research Project Funding)
- **Research provider** Nokia Foundation
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **344** — Nokia Foundation Fellow
- **Top 3 candidates** 344, 343, 345
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Nokia Foundation Fellow (ICT Research Project Funding)` vs DB `Nokia Foundation Fellow` — identical_after_normalisation=False, idf-jaccard=0.4118, containment=0.4118, seq=0.6133
- *Provider comparison* research `Nokia Foundation` vs DB `Nokia Foundation` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['ict', 'project', 'funding', 'nokia']`, aligned `['nokia']`, alignment=0.1565; degree research `[]` vs DB `['doctoral', 'phd', 'postdoctoral']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Finland)
- *Prior report* category=D, prior target=344, merge target=None
- *Final reasoning* Provider exactly identical (Nokia Foundation). Scholarship name 'Nokia Foundation Fellow' matches DB 344's title exactly, and the qualifier '(ICT Research Project Funding)' matches DB 344's funding 'Research Grant' and degree 'PhD, Postdoctoral'.

### research-021 — A (MEDIUM)

- **File** `scholarship_021_Jorma_Ollila_Grants_Recent_Doctorates_-_.json`  (batch `finland-scholarships.json`)
- **Research title** Jorma Ollila Grants (Recent Doctorates - International Experience)
- **Research provider** Nokia Foundation (in collaboration with KAUTE Foundation, Walter Ahlström Foundation, and Foundation for Economic Education)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **345** — Jorma Ollila Grant
- **Top 3 candidates** 345, 344, 262
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Jorma Ollila Grants (Recent Doctorates - International Experience)` vs DB `Jorma Ollila Grant` — identical_after_normalisation=False, idf-jaccard=0.2778, containment=0.3133, seq=0.45
- *Provider comparison* research `Nokia Foundation (in collaboration with KAUTE Foundation, Walter Ahlström Foundation, and Foundation for Economic Education)` vs DB `Nokia Foundation` — exact=False, score=0.1989
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['kaute', 'walter', 'recent', 'ahlstrom']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['doctoral', 'phd', 'postdoctoral']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'Nokia Foundation (in collaboration with KAUTE Foundation, Walter Ahlström Foundation, and Foundation for Economic Education)' vs DB 'Nokia Foundation'
  - title dissimilar (score 0.34)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* Scholarship name 'Jorma Ollila Grant(s)' matches DB 345's title exactly. Provider Nokia Foundation is DB 345's provider; DB 345's degree 'Postdoctoral, PhD' and funding 'Travel and Research Grant' fit 'Recent Doctorates - International Experience'. The co-funder names in the research provider (KAUTE, Walter Ahlstrom) are additional detail, not a contradiction.

### research-022 — D (HIGH)

- **File** `scholarship_022_Erasmus_Mundus_MARIHE_Scholarship_Master.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus MARIHE Scholarship (Master in Research and Innovation in Higher Education)
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 350, 349, 348
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Erasmus Mundus MARIHE Scholarship (Master in Research and Innovation in Higher Education)` vs DB `Erasmus Mundus Joint Master Scholarship - Bioceb (European Master in Biological and Chemical Engineering for a Sustainable Bioeconomy)` — identical_after_normalisation=False, idf-jaccard=0.1692, containment=0.3858, seq=0.47
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Bioceb consortium (Erasmus Mundus Joint Master)` — exact=False, score=0.4474
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=France → agree=None
- *Institution comparison* distinctive research tokens `['marihe', 'via', 'union', 'consortium']`, aligned `['consortium']`, alignment=0.0772; degree research `['master']` vs DB `['master']` agree=True
- *Conflicting evidence*
  - title dissimilar (score 0.35)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for MARIHE. The complete set of Erasmus Mundus rows in the DB is ids 1, 168 (Austria), 192 (Sweden), 284 (Belgium), 293 (Poland), 298 (Czech), 300 (Portugal), 348 (Forestry), 349 (EMCL), 350 (BioCEB). The distinguishing token 'MARIHE' appears in none of them, nor in any other DB row.

### research-023 — D (HIGH)

- **File** `scholarship_023_Erasmus_Mundus_EDISS_Scholarship_Enginee.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus EDISS Scholarship (Engineering of Data-intensive Intelligent Software Systems)
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 350, 348, 349
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Erasmus Mundus EDISS Scholarship (Engineering of Data-intensive Intelligent Software Systems)` vs DB `Erasmus Mundus Joint Master Scholarship - Bioceb (European Master in Biological and Chemical Engineering for a Sustainable Bioeconomy)` — identical_after_normalisation=False, idf-jaccard=0.1632, containment=0.2939, seq=0.4887
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Bioceb consortium (Erasmus Mundus Joint Master)` — exact=False, score=0.4474
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=France → agree=None
- *Institution comparison* distinctive research tokens `['intensive', 'intelligent', 'ediss', 'software']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['master']` agree=True
- *Conflicting evidence*
  - title dissimilar (score 0.37)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for EDISS. The distinguishing token 'EDISS' appears in no DB title, provider or URL.

### research-024 — D (HIGH)

- **File** `scholarship_024_Erasmus_Mundus_REPLAY_Scholarship_Europe.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus REPLAY Scholarship (European Game Design Masters)
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 350, 349, 348
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Erasmus Mundus REPLAY Scholarship (European Game Design Masters)` vs DB `Erasmus Mundus Joint Master Scholarship - Bioceb (European Master in Biological and Chemical Engineering for a Sustainable Bioeconomy)` — identical_after_normalisation=False, idf-jaccard=0.1669, containment=0.3657, seq=0.4688
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Bioceb consortium (Erasmus Mundus Joint Master)` — exact=False, score=0.4474
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=France → agree=None
- *Institution comparison* distinctive research tokens `['game', 'replay', 'design', 'masters']`, aligned `[]`, alignment=0.0; degree research `['master']` vs DB `['master']` agree=True
- *Conflicting evidence*
  - title dissimilar (score 0.35)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for REPLAY. The distinguishing token 'REPLAY' appears in no DB title, provider or URL.

### research-025 — C (HIGH)

- **File** `scholarship_025_Erasmus_Mundus_European_Forestry_MSc_EF_.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus European Forestry (MSc EF) Scholarship
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **348** — Erasmus Mundus European Forestry (MSc EF) Scholarship
- **Top 3 candidates** 348, 350, 284
- **Classification** **C**, confidence **HIGH**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Erasmus Mundus European Forestry (MSc EF) Scholarship` vs DB `Erasmus Mundus European Forestry (MSc EF) Scholarship` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Master Europeanforestry.Eu` — exact=False, score=0.0733
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['ef', 'forestry', 'msc', 'union']`, aligned `['ef', 'forestry', 'msc']`, alignment=0.2837; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - title identical after normalisation
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium' vs DB 'Master Europeanforestry.Eu'
- *Prior report* category=A, prior target=348, merge target=348
- *Final reasoning* Identity is CERTAIN: the title token set is identical to DB 348. It is held for review only because the target row is deliberately retired - is_archived=1, verification_status=quarantined, archived_reason 'DEAD: the recorded url does not resolve in DNS (NXDOMAIN for both apex and www). Successor: https://sites.uef.fi/europeanforestry/'. A write must not resurrect a dead-URL row; a human must decide between repointing the row to the successor and creating a new record.

### research-026 — C (HIGH)

- **File** `scholarship_026_Erasmus_Mundus_EMCL_Scholarship_European.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus EMCL Scholarship (European Master's in Clinical Linguistics)
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **349** — Erasmus Mundus EMCL Scholarship (European Master's in Clinical Linguistics)
- **Top 3 candidates** 349, 350, 348
- **Classification** **C**, confidence **HIGH**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Erasmus Mundus EMCL Scholarship (European Master's in Clinical Linguistics)` vs DB `Erasmus Mundus EMCL Scholarship (European Master's in Clinical Linguistics)` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Clinical Linguistics.Eu` — exact=False, score=0.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['emcl', 'linguistics', 'clinical', 'union']`, aligned `['emcl', 'linguistics', 'clinical']`, alignment=0.2897; degree research `['master']` vs DB `['master']` agree=True
- *Supporting evidence*
  - title identical after normalisation
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium' vs DB 'Clinical Linguistics.Eu'
- *Prior report* category=A, prior target=349, merge target=349
- *Final reasoning* Identity is CERTAIN: the title token set is identical to DB 349. Held for the same reason as research-025 - DB 349 is archived and quarantined with archived_reason 'DEAD: ... does not resolve in DNS (NXDOMAIN). Successor programme and site: EMCL-25 at https://emcl.eu/'.

### research-027 — A (MEDIUM)

- **File** `scholarship_027_Erasmus_Mundus_BioCEB_Scholarship_Bioche.json`  (batch `finland-scholarships.json`)
- **Research title** Erasmus Mundus BioCEB Scholarship (Biochemistry and Molecular Biology)
- **Research provider** European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** **350** — Erasmus Mundus Joint Master Scholarship - Bioceb (European Master in Biological and Chemical Engineering for a Sustainable Bioeconomy)
- **Top 3 candidates** 350, 348, 336
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Erasmus Mundus BioCEB Scholarship (Biochemistry and Molecular Biology)` vs DB `Erasmus Mundus Joint Master Scholarship - Bioceb (European Master in Biological and Chemical Engineering for a Sustainable Bioeconomy)` — identical_after_normalisation=False, idf-jaccard=0.211, containment=0.4704, seq=0.4949
- *Provider comparison* research `European Union (Erasmus+ Programme) via Erasmus Mundus Joint Master Degree consortium` vs DB `Bioceb consortium (Erasmus Mundus Joint Master)` — exact=False, score=0.4474
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (source_file_batch) vs DB=France → agree=None
- *Institution comparison* distinctive research tokens `['biochemistry', 'bioceb', 'molecular', 'biology']`, aligned `['bioceb']`, alignment=0.0891; degree research `[]` vs DB `['master']` agree=True
- *Conflicting evidence*
  - title dissimilar (score 0.40)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* The distinguishing token 'BioCEB' occurs in DB 350's title ('Erasmus Mundus Joint Master Scholarship - Bioceb ...'). DB 350 is active and not archived. The apparent country difference (DB 350 country=France vs the research batch being finland-scholarships.json) is NOT a conflict: the source file is only the research input grouping, the research provider is the generic Erasmus Mundus consortium, and BioCEB is a France-led joint master. The prior run scored 0.40 and called it new.

### research-028 — D (HIGH)

- **File** `scholarship_028_Aalto_University_Colfuturo_Scholarship_P.json`  (batch `finland-scholarships.json`)
- **Research title** Aalto University Colfuturo Scholarship Partnership (25% Tuition Discount for Colombian Students)
- **Research provider** Aalto University in collaboration with Colfuturo (Colombian non-profit foundation)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 335, 263, 339
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Aalto University Colfuturo Scholarship Partnership (25% Tuition Discount for Colombian Students)` vs DB `Aalto University Excellence Scholarship (100% tuition fee waiver)` — identical_after_normalisation=False, idf-jaccard=0.2008, containment=0.2815, seq=0.5548
- *Provider comparison* research `Aalto University in collaboration with Colfuturo (Colombian non-profit foundation)` vs DB `Aalto University` — exact=False, score=0.1738
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['colfuturo', 'colombian', 'profit', '25']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'Aalto University in collaboration with Colfuturo (Colombian non-profit foundation)' vs DB 'Aalto University'
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for the COLFUTURO partnership. Distinguishing tokens 'Colfuturo' and 'Colombian' appear nowhere in the DB. DB 263's notes explicitly list the COLFUTURO 25% discount as a separate Aalto scheme that must not be confused with the Excellence Scholarship.

### research-029 — D (HIGH)

- **File** `scholarship_029_Aalto_University_FUNED_Scholarship_Partn.json`  (batch `finland-scholarships.json`)
- **Research title** Aalto University FUNED Scholarship Partnership (25% Tuition Discount for Mexican Students)
- **Research provider** Aalto University in collaboration with FUNED (Mexican Foundation for Education, Technology and Science)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 335, 263, 339
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Aalto University FUNED Scholarship Partnership (25% Tuition Discount for Mexican Students)` vs DB `Aalto University Excellence Scholarship (100% tuition fee waiver)` — identical_after_normalisation=False, idf-jaccard=0.2008, containment=0.2815, seq=0.5772
- *Provider comparison* research `Aalto University in collaboration with FUNED (Mexican Foundation for Education, Technology and Science)` vs DB `Aalto University` — exact=False, score=0.1823
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['mexican', 'funed', '25', 'collaboration']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - provider mismatch: research 'Aalto University in collaboration with FUNED (Mexican Foundation for Education, Technology and Science)' vs DB 'Aalto University'
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for the FUNED partnership. Distinguishing tokens 'FUNED' and 'Mexican' appear nowhere in the DB. DB 263's notes explicitly list the FUNED 25% discount as a separate Aalto scheme.

### research-030 — D (HIGH)

- **File** `scholarship_030_Fulbright-Nokia_Distinguished_Chair_in_I.json`  (batch `finland-scholarships.json`)
- **Research title** Fulbright-Nokia Distinguished Chair in ICT
- **Research provider** Fulbright Finland Foundation (funded by Nokia Foundation and Fulbright Finland Foundation)
- **Research URL** _none — ['No official URL provided in source file']_
- **Inferred country** Finland
- **DB match** none
- **Top 3 candidates** 343, 344, 338
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Fulbright-Nokia Distinguished Chair in ICT` vs DB `Nokia Scholarship` — identical_after_normalisation=False, idf-jaccard=0.1711, containment=0.1806, seq=0.339
- *Provider comparison* research `Fulbright Finland Foundation (funded by Nokia Foundation and Fulbright Finland Foundation)` vs DB `Nokia Foundation` — exact=False, score=0.3658
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=False
- *Country comparison* research=Finland (institution_gazetteer) vs DB=Finland → agree=True
- *Institution comparison* distinctive research tokens `['chair', 'ict', 'distinguished', 'finland']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Finland)
- *Conflicting evidence*
  - title dissimilar (score 0.25)
- *Prior report* category=D, prior target=None, merge target=None
- *Final reasoning* No DB row for the Fulbright-Nokia Distinguished Chair. The complete set of Fulbright rows in the DB is ids 27, 469 (both the Foreign Student Program and both archived as mutual duplicates), 470 (U.S. Student Program), 424 (Poland), 687, 695, 696 - none is a Finland or Fulbright-Nokia chair. Distinguishing tokens 'Chair' and 'Distinguished' align nowhere.

### research-031 — A (HIGH)

- **File** `scholarship_031_Stipendium_Hungaricum_Scholarship.json`  (batch `hungary_scholarships_2026_2027.json`)
- **Research title** Stipendium Hungaricum Scholarship
- **Research provider** Tempus Public Foundation (Hungarian Government)
- **Research URL** `https://stipendiumhungaricum.hu/`, `https://stipendiumhungaricum.hu/`
- **Inferred country** Hungary
- **DB match** **285** — Stipendium Hungaricum Scholarship Programme
- **Top 3 candidates** 285, 356, 359
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Stipendium Hungaricum Scholarship` vs DB `Stipendium Hungaricum Scholarship Programme` — identical_after_normalisation=False, idf-jaccard=0.8162, containment=1.0, seq=0.8684
- *Provider comparison* research `Tempus Public Foundation (Hungarian Government)` vs DB `Hungarian Government / Tempus Public Foundation` — exact=False, score=1.0
- *URL comparison* exact_canonical_overlap=['stipendiumhungaricum.hu/'], domain_overlap=['stipendiumhungaricum.hu'], aggregator_page=True, conflict=False
- *Country comparison* research=Hungary (institution_gazetteer) vs DB=Hungary → agree=True
- *Institution comparison* distinctive research tokens `['hungaricum', 'stipendium', 'tempus', 'hungarian']`, aligned `['hungaricum', 'stipendium', 'tempus', 'hungarian']`, alignment=0.65; degree research `[]` vs DB `['bachelor', 'doctoral', 'master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (stipendiumhungaricum.hu/)
  - shared registrable domain: ['stipendiumhungaricum.hu']
  - provider fully contained in DB provider (idf-containment 1.00)
  - strong title similarity (idf-jaccard 0.82, containment 1.00, seq 0.87)
  - country agrees (Hungary)
- *Prior report* category=A, prior target=285, merge target=285
- *Final reasoning* Canonical URL stipendiumhungaricum.hu/ is identical to DB 285 official_source_url and application_link. Provider 'Tempus Public Foundation (Hungarian Government)' is fully contained in DB 285's provider. Country Hungary. Programme name is globally unique so the URL is identity-specific despite being a homepage.

### research-032 — A (HIGH)

- **File** `scholarship_032_Hungarian_Bilateral_State_Scholarships.json`  (batch `hungary_scholarships_2026_2027.json`)
- **Research title** Hungarian Bilateral State Scholarships
- **Research provider** Tempus Public Foundation / Hungarian State (Ministry of Foreign Affairs and Trade)
- **Research URL** `https://en.tka.hu/`, `https://en.tka.hu/`
- **Inferred country** Hungary
- **DB match** **356** — Hungarian Bilateral State Scholarships
- **Top 3 candidates** 356, 285, 359
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Hungarian Bilateral State Scholarships` vs DB `Hungarian Bilateral State Scholarships` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `Tempus Public Foundation / Hungarian State (Ministry of Foreign Affairs and Trade)` vs DB `Tempus Public Foundation` — exact=False, score=0.3441
- *URL comparison* exact_canonical_overlap=['en.tka.hu/'], domain_overlap=['tka.hu'], aggregator_page=False, conflict=False
- *Country comparison* research=Hungary (institution_gazetteer) vs DB=Hungary → agree=True
- *Institution comparison* distinctive research tokens `['bilateral', 'trade', 'tempus', 'hungarian']`, aligned `['bilateral', 'tempus', 'hungarian']`, alignment=0.3467; degree research `[]` vs DB `['doctoral', 'master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (en.tka.hu/)
  - shared registrable domain: ['tka.hu']
  - title identical after normalisation
  - country agrees (Hungary)
- *Conflicting evidence*
  - provider mismatch: research 'Tempus Public Foundation / Hungarian State (Ministry of Foreign Affairs and Trade)' vs DB 'Tempus Public Foundation'
- *Prior report* category=A, prior target=356, merge target=356
- *Final reasoning* Canonical URL en.tka.hu/ is identical to DB 356 official_source_url. Title token sets identical. Provider fully contained in DB 356's provider. Country Hungary.

### research-033 — D (HIGH)

- **File** `scholarship_033_Momentum_MSCA_Postdoctoral_Fellowship.json`  (batch `hungary_scholarships_2026_2027.json`)
- **Research title** Momentum MSCA Postdoctoral Fellowship
- **Research provider** Hungarian Academy of Sciences (MTA), co-funded by European Commission
- **Research URL** `https://momentummsca.mta.hu/`, `https://momentummsca.mta.hu/`
- **Inferred country** Hungary
- **DB match** none
- **Top 3 candidates** 582, 16, 629
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Momentum MSCA Postdoctoral Fellowship` vs DB `EMBO Postdoctoral Fellowships` — identical_after_normalisation=False, idf-jaccard=0.154, containment=0.2326, seq=0.7879
- *Provider comparison* research `Hungarian Academy of Sciences (MTA), co-funded by European Commission` vs DB `European Molecular Biology Organization (EMBO)` — exact=False, score=0.0846
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Hungary (institution_gazetteer) vs DB=Multiple → agree=None
- *Institution comparison* distinctive research tokens `['mta', 'momentum', 'co', 'hungarian']`, aligned `[]`, alignment=0.0; degree research `['doctoral', 'postdoctoral']` vs DB `['doctoral', 'postdoctoral']` agree=True
- *Conflicting evidence*
  - official URL domains differ (research ['mta.hu'] vs DB ['embo.org'])
  - provider mismatch: research 'Hungarian Academy of Sciences (MTA), co-funded by European Commission' vs DB 'European Molecular Biology Organization (EMBO)'
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row carries the URL momentummsca.mta.hu (registrable mta.hu) and the distinguishing tokens 'Momentum' and 'MTA' align with no DB row. DB 16 is the generic EC MSCA Postdoctoral Fellowships umbrella, which has no Momentum or Hungarian Academy of Sciences component; mapping this record onto DB 16 would erase the programme's distinguishing identity.

### research-034 — D (HIGH)

- **File** `scholarship_034_Hungarian_Diaspora_Scholarship.json`  (batch `hungary_scholarships_2026_2027.json`)
- **Research title** Hungarian Diaspora Scholarship
- **Research provider** Tempus Public Foundation (Hungarian Government)
- **Research URL** `https://diasporascholarship.hu/`, `https://diasporascholarship.hu/`
- **Inferred country** Hungary
- **DB match** none
- **Top 3 candidates** 285, 356, 359
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Hungarian Diaspora Scholarship` vs DB `Stipendium Hungaricum Scholarship Programme` — identical_after_normalisation=False, idf-jaccard=0.0549, containment=0.1197, seq=0.5205
- *Provider comparison* research `Tempus Public Foundation (Hungarian Government)` vs DB `Hungarian Government / Tempus Public Foundation` — exact=False, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Hungary (institution_gazetteer) vs DB=Hungary → agree=True
- *Institution comparison* distinctive research tokens `['diaspora', 'tempus', 'hungarian', 'public']`, aligned `['tempus', 'hungarian', 'public']`, alignment=0.5278; degree research `[]` vs DB `['bachelor', 'doctoral', 'master']` agree=True
- *Supporting evidence*
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Hungary)
- *Conflicting evidence*
  - official URL domains differ (research ['diasporascholarship.hu'] vs DB ['stipendiumhungaricum.hu'])
  - title dissimilar (score 0.39)
  - deadline text differs (research '2 February 2026, 14:00 CET (missing documents accepted until...' vs DB '15 January 2026, 14:00 CET...')
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row carries the URL diasporascholarship.hu. DB 285 (Stipendium Hungaricum) shares the provider 'Tempus Public Foundation' but is a different programme with a different deadline (15 January vs 2 February), so provider overlap alone is not identity evidence.

### research-035 — A (HIGH)

- **File** `scholarship_035_Semmelweis_Pannonia_In_Excellence_Schola.json`  (batch `hungary_scholarships_2026_2027.json`)
- **Research title** Semmelweis Pannonia In Excellence Scholarship
- **Research provider** Semmelweis University
- **Research URL** `https://semmelweis.hu/registrar/information/scholarships/semmelweis-pannonia-in-excellence-scholarship/`, `https://semmelweis.hu/registrar/information/scholarships/semmelweis-pannonia-in-excellence-scholarship/`
- **Inferred country** Hungary
- **DB match** **359** — Semmelweis Pannonia In Excellence Scholarship
- **Top 3 candidates** 359, 288, 356
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Semmelweis Pannonia In Excellence Scholarship` vs DB `Semmelweis Pannonia In Excellence Scholarship` — identical_after_normalisation=True, idf-jaccard=1.0, containment=1.0, seq=1.0
- *Provider comparison* research `Semmelweis University` vs DB `Semmelweis University` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=['semmelweis.hu/registrar/information/scholarships/semmelweis-pannonia-in-excellence-scholarship'], domain_overlap=['semmelweis.hu'], aggregator_page=False, conflict=False
- *Country comparison* research=Hungary (institution_gazetteer) vs DB=Hungary → agree=True
- *Institution comparison* distinctive research tokens `['pannonia', 'semmelweis', 'excellence', 'university']`, aligned `['pannonia', 'semmelweis', 'excellence', 'university']`, alignment=0.9183; degree research `[]` vs DB `['bachelor', 'master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (semmelweis.hu/registrar/information/scholarships/semmelweis-pannonia-in-excellence-scholarship)
  - shared registrable domain: ['semmelweis.hu']
  - provider string identical
  - title identical after normalisation
  - country agrees (Hungary)
- *Conflicting evidence*
  - deadline text differs (research '15 October 2026...' vs DB '2026-10-15...')
- *Prior report* category=A, prior target=359, merge target=359
- *Final reasoning* Canonical URL is identical to DB 359 official_source_url, application_link, catalogue_url and official_updates_url. Provider exactly identical, title token set identical, country Hungary. The prior run classified this B on a 'deadline conflict' - that was a formatting artefact only: research says '15 October 2026', DB deadline_date is 2026-10-15, the same date. Corrected to A.

### research-036 — A (MEDIUM)

- **File** `scholarship_036_MSCA_Postdoctoral_Fellowships_2026.json`  (batch `norway_scholarships.json`)
- **Research title** MSCA Postdoctoral Fellowships 2026
- **Research provider** European Commission - Marie Skłodowska-Curie Actions
- **Research URL** `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026`, `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026`
- **Inferred country** Norway
- **DB match** **16** — Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships
- **Top 3 candidates** 16, 18, 17
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `MSCA Postdoctoral Fellowships 2026` vs DB `Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships` — identical_after_normalisation=False, idf-jaccard=0.3062, containment=0.8045, seq=0.617
- *Provider comparison* research `European Commission - Marie Skłodowska-Curie Actions` vs DB `European Commission (Marie Skłodowska-Curie Actions)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ec.europa.eu'], aggregator_page=False, conflict=False
- *Country comparison* research=Norway (source_file_batch) vs DB=EU (multiple) → agree=None
- *Institution comparison* distinctive research tokens `['curie', 'marie', 'sk', 'odowska']`, aligned `['curie', 'marie', 'sk', 'odowska']`, alignment=0.4223; degree research `['doctoral', 'postdoctoral']` vs DB `['doctoral', 'postdoctoral']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ec.europa.eu']
  - provider string identical
  - strong title similarity (idf-jaccard 0.31, containment 0.80, seq 0.62)
- *Prior report* category=D, prior target=16, merge target=None
- *Final reasoning* Provider is equivalent (research 'European Commission - Marie Sklodowska-Curie Actions' vs DB 'European Commission (Marie Sklodowska-Curie Actions)'). Registrable domain ec.europa.eu shared. Degree level Postdoctoral agrees. GRANULARITY CAVEAT: the research URL is the 2026 call page (/funding/msca-postdoctoral-fellowships-2026) while DB 16 is the programme-level row (/actions/postdoctoral-fellowships); DB has no separate 2026 call row, so the programme row is the only legitimate target. DB 18 (MSCA Doctoral Networks) is a different action and is correctly excluded.

### research-037 — D (HIGH)

- **File** `scholarship_037_Fulbright_Norway_Open_Study_Research_Awa.json`  (batch `norway_scholarships.json`)
- **Research title** Fulbright Norway Open Study/Research Award 2027-2028
- **Research provider** US-Norway Fulbright Foundation
- **Research URL** `https://new-us.fulbrightonline.org/countries/europe-and-eurasia/norway/1739`, `https://new-us.fulbrightonline.org/countries/europe-and-eurasia/norway/1739`
- **Inferred country** Norwegian
- **DB match** none
- **Top 3 candidates** 469, 470, 27
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Fulbright Norway Open Study/Research Award 2027-2028` vs DB `Fulbright Foreign Student Program` — identical_after_normalisation=False, idf-jaccard=0.1057, containment=0.1366, seq=0.5176
- *Provider comparison* research `US-Norway Fulbright Foundation` vs DB `U.S. Department of State, Fulbright Program (administered by IIE and AMIDEAST)` — exact=False, score=0.2239
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['fulbrightonline.org'], aggregator_page=False, conflict=False
- *Country comparison* research=Norwegian (institution_gazetteer) vs DB=United States → agree=False
- *Institution comparison* distinctive research tokens `['open', 'us', 'norway', 'fulbright']`, aligned `['fulbright']`, alignment=0.1088; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['fulbrightonline.org']
- *Conflicting evidence*
  - provider mismatch: research 'US-Norway Fulbright Foundation' vs DB 'U.S. Department of State, Fulbright Program (administered by IIE and AMIDEAST)'
  - title dissimilar (score 0.39)
  - COUNTRY CONFLICT: research implies Norwegian but DB row is United States
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row for the Fulbright Norway awards. The research URL new-us.fulbrightonline.org/countries/europe-and-eurasia/norway/1739 is Norway-specific and appears nowhere in the DB. The DB Fulbright rows are the global/US Foreign Student Program (27, 469 - both archived as mutual duplicates), the U.S. Student Program (470), and country programmes for Poland, Canada and Mexico. Candidates 469/470 were country-rejected (Norway vs United States).

### research-038 — D (HIGH)

- **File** `scholarship_038_Fulbright_Norway_English_Teaching_Assist.json`  (batch `norway_scholarships.json`)
- **Research title** Fulbright Norway English Teaching Assistant Award 2027-2028
- **Research provider** US-Norway Fulbright Foundation
- **Research URL** `https://new-us.fulbrightonline.org/countries/europe-and-eurasia/norway/1740`, `https://new-us.fulbrightonline.org/countries/europe-and-eurasia/norway/1740`
- **Inferred country** Norwegian
- **DB match** none
- **Top 3 candidates** 470, 469, 27
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Fulbright Norway English Teaching Assistant Award 2027-2028` vs DB `Fulbright U.S. Student Program` — identical_after_normalisation=False, idf-jaccard=0.1021, containment=0.119, seq=0.4318
- *Provider comparison* research `US-Norway Fulbright Foundation` vs DB `U.S. Department of State, Fulbright Program (administered by IIE)` — exact=False, score=0.2239
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['fulbrightonline.org'], aggregator_page=False, conflict=False
- *Country comparison* research=Norwegian (institution_gazetteer) vs DB=United States → agree=False
- *Institution comparison* distinctive research tokens `['english', 'assistant', 'us', 'teaching']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['fulbrightonline.org']
- *Conflicting evidence*
  - provider mismatch: research 'US-Norway Fulbright Foundation' vs DB 'U.S. Department of State, Fulbright Program (administered by IIE)'
  - title dissimilar (score 0.32)
  - COUNTRY CONFLICT: research implies Norwegian but DB row is United States
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Same reasoning as research-037. Its URL ends /norway/1740 rather than /norway/1739 and the award type differs (English Teaching Assistant vs Open Study/Research), so 037 and 038 are two distinct award types and NOT duplicates of each other.

### research-039 — D (HIGH)

- **File** `scholarship_039_PhD_Research_Fellow_in_Machine_Learning_.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Research Fellow in Machine Learning for Cognitive Neuroscience
- **Research provider** University of Oslo (UiO)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/296254`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/296254`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 277
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Research Fellow in Machine Learning for Cognitive Neuroscience` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.064, containment=0.1017, seq=0.25
- *Provider comparison* research `University of Oslo (UiO)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.122
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['machine', 'cognitive', 'learning', 'neuroscience']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Oslo (UiO)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.19)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* A specific UiO PhD vacancy. The DB contains no University of Oslo row at all (its only 6 Norway rows are BI scholarships 274-277, NTNU 278 and NORPART 279). No DB URL matches jobbnorge.no.

### research-040 — D (HIGH)

- **File** `scholarship_040_PhD_Research_Fellow_in_Meteorology.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Research Fellow in Meteorology
- **Research provider** University of Oslo (UiO)
- **Research URL** `https://www.uio.no/english/about/vacancies/academic/`, `https://www.uio.no/english/about/vacancies/academic/`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Research Fellow in Meteorology` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.0945, containment=0.2088, seq=0.3889
- *Provider comparison* research `University of Oslo (UiO)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.122
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['meteorology', 'uio', 'oslo', 'fellow']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['uio.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Oslo (UiO)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.29)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* A specific UiO PhD vacancy; no University of Oslo row exists in the DB. The research URL uio.no/english/about/vacancies/academic/ is a generic vacancies listing that appears in no DB row.

### research-041 — C (MEDIUM)

- **File** `scholarship_041_Up_to_7_PhD_Research_Fellow_Positions_Fa.json`  (batch `norway_scholarships.json`)
- **Research title** Up to 7 PhD Research Fellow Positions (Faculty of Arts and Humanities)
- **Research provider** Norwegian University of Science and Technology (NTNU)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/job/304877/up-to-7-phd-research-fellow-positions`, `https://www.jobbnorge.no/en/available-jobs/job/304877/up-to-7-phd-research-fellow-positions`
- **Inferred country** Norway
- **DB match** **278** — NTNU PhD Positions (Salaried Employment)
- **Top 3 candidates** 278, 279, 276
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Up to 7 PhD Research Fellow Positions (Faculty of Arts and Humanities)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.1586, containment=0.2254, seq=0.4717
- *Provider comparison* research `Norwegian University of Science and Technology (NTNU)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['up', 'arts', 'faculty', 'humanities']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - title dissimilar (score 0.35)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Same institution as DB 278 (provider exactly identical, NTNU) and the research record is a multi-position faculty call ('Up to 7 PhD Research Fellow Positions'), conceptually close to the DB 278 umbrella row. But research-041 is one faculty-specific vacancy with a jobbnorge.no listing URL while DB 278 is the NTNU-wide posting page. Writing this onto DB 278 would replace umbrella content with one vacancy's content.

### research-042 — D (HIGH)

- **File** `scholarship_042_PhD_Research_Fellow_in_Political_Science.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Research Fellow in Political Science (3-4 years)
- **Research provider** University of Oslo (UiO)
- **Research URL** `https://www.uio.no/english/about/vacancies/academic/`, `https://www.uio.no/english/about/vacancies/academic/`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Research Fellow in Political Science (3-4 years)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.077, containment=0.139, seq=0.3182
- *Provider comparison* research `University of Oslo (UiO)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.122
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['years', 'political', 'uio', 'oslo']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['uio.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Oslo (UiO)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.24)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* A specific UiO PhD vacancy; no University of Oslo row exists in the DB. The research URL is the same generic UiO vacancies listing as research-040, which is a further reason not to treat the URL as identity evidence.

### research-043 — D (HIGH)

- **File** `scholarship_043_A_Wilhelmsen_Foundation_Scholarship_Prog.json`  (batch `norway_scholarships.json`)
- **Research title** A. Wilhelmsen Foundation Scholarship Programme (NTNU IMT)
- **Research provider** A. Wilhelmsen Foundation / NTNU Department of Marine Technology
- **Research URL** `https://www.ntnu.edu/imt/scolarship`, `https://www.ntnu.edu/imt/scolarship`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 275, 279
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `A. Wilhelmsen Foundation Scholarship Programme (NTNU IMT)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.1121, containment=0.2016, seq=0.1739
- *Provider comparison* research `A. Wilhelmsen Foundation / NTNU Department of Marine Technology` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.2704
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ntnu.edu'], aggregator_page=False, conflict=False
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['marine', 'imt', 'wilhelmsen', 'ntnu']`, aligned `['ntnu']`, alignment=0.1302; degree research `[]` vs DB `['phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ntnu.edu']
  - country agrees (Norway)
- *Conflicting evidence*
  - provider mismatch: research 'A. Wilhelmsen Foundation / NTNU Department of Marine Technology' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.17)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. Distinguishing tokens 'Wilhelmsen' and 'IMT' appear in no DB title, provider or URL. DB 278 is the NTNU umbrella row but is not the Wilhelmsen programme.

### research-044 — C (MEDIUM)

- **File** `scholarship_044_Erasmus_Mundus_Joint_Masters_-_Norway-li.json`  (batch `norway_scholarships.json`)
- **Research title** Erasmus Mundus Joint Masters - Norway-linked programmes (2027 intake)
- **Research provider** European Commission / Multiple Norwegian universities (NTNU, NMBU, UiT)
- **Research URL** `https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en`, `https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en`
- **Inferred country** Norway
- **DB match** **1** — Erasmus Mundus Joint Masters (EMJM)
- **Top 3 candidates** 1, 168, 192
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Erasmus Mundus Joint Masters - Norway-linked programmes (2027 intake)` vs DB `Erasmus Mundus Joint Masters (EMJM)` — identical_after_normalisation=False, idf-jaccard=0.356, containment=0.4049, seq=0.6531
- *Provider comparison* research `European Commission / Multiple Norwegian universities (NTNU, NMBU, UiT)` vs DB `European Commission (Erasmus+)` — exact=False, score=0.1704
- *URL comparison* exact_canonical_overlap=['eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en'], domain_overlap=['ec.europa.eu'], aggregator_page=False, conflict=False
- *Country comparison* research=Norway (institution_gazetteer) vs DB=EU (multiple) → agree=None
- *Institution comparison* distinctive research tokens `['uit', 'linked', 'nmbu', 'multiple']`, aligned `[]`, alignment=0.0; degree research `['master']` vs DB `['master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en)
  - shared registrable domain: ['ec.europa.eu']
- *Conflicting evidence*
  - provider mismatch: research 'European Commission / Multiple Norwegian universities (NTNU, NMBU, UiT)' vs DB 'European Commission (Erasmus+)'
- *Prior report* category=A, prior target=168, merge target=None
- *Final reasoning* CORRECTION OF A WRONG MATCH. The research URL eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en is identical to DB 1's catalogue_url, and DB 1 is the country-agnostic Erasmus Mundus umbrella row. The prior run mapped this record to DB 168 on 'exact_url_match', but DB 168 is the AUSTRIA-specific row and its title is 'Erasmus Mundus Joint Master Degrees - Austria-based'. The EACA catalogue URL is shared by every country variant in the DB (168 Austria, 192 Sweden, and DB 1 itself), so it is NOT identity-specific. There is no Norway-specific Erasmus Mundus row in the DB, so DB 1 is the only defensible target - but because the sole URL signal is a shared catalogue page, a human must confirm it.

### research-045 — A (MEDIUM)

- **File** `scholarship_045_MSCA_Postdoctoral_Fellowships_2027.json`  (batch `norway_scholarships.json`)
- **Research title** MSCA Postdoctoral Fellowships 2027
- **Research provider** European Commission - Marie Skłodowska-Curie Actions
- **Research URL** `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2027`, `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2027`
- **Inferred country** Norway
- **DB match** **16** — Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships
- **Top 3 candidates** 16, 18, 17
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `MSCA Postdoctoral Fellowships 2027` vs DB `Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships` — identical_after_normalisation=False, idf-jaccard=0.3065, containment=0.8067, seq=0.617
- *Provider comparison* research `European Commission - Marie Skłodowska-Curie Actions` vs DB `European Commission (Marie Skłodowska-Curie Actions)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ec.europa.eu'], aggregator_page=False, conflict=False
- *Country comparison* research=Norway (source_file_batch) vs DB=EU (multiple) → agree=None
- *Institution comparison* distinctive research tokens `['curie', 'marie', 'sk', 'odowska']`, aligned `['curie', 'marie', 'sk', 'odowska']`, alignment=0.4226; degree research `['doctoral', 'postdoctoral']` vs DB `['doctoral', 'postdoctoral']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ec.europa.eu']
  - provider string identical
  - strong title similarity (idf-jaccard 0.31, containment 0.81, seq 0.62)
- *Prior report* category=D, prior target=16, merge target=None
- *Final reasoning* Same programme as research-036, the 2027 call rather than the 2026 call. Provider equivalent, domain ec.europa.eu shared, degree Postdoctoral agrees. DB has no per-year rows, so DB 16 is the target. NOTE: 036 and 045 are two annual calls of one programme and legitimately share a DB target; they are not duplicates of each other.

### research-046 — D (HIGH)

- **File** `scholarship_046_VID_Specialized_University_PhD_Research_.json`  (batch `norway_scholarships.json`)
- **Research title** VID Specialized University PhD Research Fellowships in Theology and Religion
- **Research provider** VID Specialized University
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/287803`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/287803`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `VID Specialized University PhD Research Fellowships in Theology and Religion` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.0633, containment=0.1, seq=0.2105
- *Provider comparison* research `VID Specialized University` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.1107
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['vid', 'theology', 'religion', 'specialized']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'VID Specialized University' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.16)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. The distinguishing tokens 'VID' and 'Theology' appear in no DB title, provider or URL. jobbnorge.no is not present in any DB row.

### research-047 — D (HIGH)

- **File** `scholarship_047_Coimbra_Group_Scholarship_Programme_2026.json`  (batch `norway_scholarships.json`)
- **Research title** Coimbra Group Scholarship Programme 2026 (University of Bergen)
- **Research provider** Coimbra Group / University of Bergen
- **Research URL** `https://www.uib.no/en/globalchallenges/175663/uib-participates-coimbra-group-scholarship-programme`, `https://www.uib.no/en/globalchallenges/175663/uib-participates-coimbra-group-scholarship-programme`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 275, 278, 279
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Coimbra Group Scholarship Programme 2026 (University of Bergen)` vs DB `Master International Scholarship – Bergen` — identical_after_normalisation=False, idf-jaccard=0.2197, containment=0.2664, seq=0.42
- *Provider comparison* research `Coimbra Group / University of Bergen` vs DB `BI Norwegian Business School` — exact=False, score=0.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['coimbra', 'group', 'bergen', '2026']`, aligned `['bergen']`, alignment=0.2104; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['uib.no'] vs DB ['bi.no'])
  - provider mismatch: research 'Coimbra Group / University of Bergen' vs DB 'BI Norwegian Business School'
  - title dissimilar (score 0.32)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row for the Coimbra Group programme. The distinguishing token 'Coimbra' appears in no DB row (the only Coimbra reference anywhere in the DB is research-side; DB 162 is the University of Vienna, not Coimbra - see research-065). DB 275 'Master International Scholarship - Bergen' shares only the city word 'Bergen' and belongs to BI Norwegian Business School, an unrelated institution and programme.

### research-048 — D (HIGH)

- **File** `scholarship_048_NORAM_Graduate_Scholarship_Americans_to_.json`  (batch `norway_scholarships.json`)
- **Research title** NORAM Graduate Scholarship (Americans to Norway)
- **Research provider** Norway-America Association (NORAM)
- **Research URL** `https://www.noram.no/en/stipend`, `https://www.noram.no/en/stipend`
- **Inferred country** Norwegian
- **DB match** none
- **Top 3 candidates** 591, 101, 307
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `NORAM Graduate Scholarship (Americans to Norway)` vs DB `Horatio Alger Association National Scholarship` — identical_after_normalisation=False, idf-jaccard=0.0343, containment=0.0662, seq=0.4565
- *Provider comparison* research `Norway-America Association (NORAM)` vs DB `Horatio Alger Association of Distinguished Americans` — exact=False, score=0.2032
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Norwegian (institution_gazetteer) vs DB=United States → agree=False
- *Institution comparison* distinctive research tokens `['noram', 'america', 'americans', 'norway']`, aligned `['americans']`, alignment=0.1752; degree research `[]` vs DB `['bachelor']` agree=True
- *Conflicting evidence*
  - official URL domains differ (research ['noram.no'] vs DB ['horatioalger.org'])
  - provider mismatch: research 'Norway-America Association (NORAM)' vs DB 'Horatio Alger Association of Distinguished Americans'
  - title dissimilar (score 0.34)
  - COUNTRY CONFLICT: research implies Norwegian but DB row is United States
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. The distinguishing token 'NORAM' appears nowhere in the DB. The top-scoring DB row (591, Horatio Alger) was vetoed on a hard country conflict (Norway vs United States) and a disjoint domain.

### research-049 — D (HIGH)

- **File** `scholarship_049_Anglo-Norse_Society_Scholarship_NTNU_.json`  (batch `norway_scholarships.json`)
- **Research title** Anglo-Norse Society Scholarship (NTNU)
- **Research provider** Anglo-Norse Society / NTNU
- **Research URL** `https://www.anglo-norse.org.uk/scholarships-grants`, `https://www.anglo-norse.org.uk/scholarships-grants`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 276, 277
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `Anglo-Norse Society Scholarship (NTNU)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.1157, containment=0.2134, seq=0.1081
- *Provider comparison* research `Anglo-Norse Society / NTNU` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.2052
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['norse', 'anglo', 'ntnu', 'society']`, aligned `['ntnu']`, alignment=0.2134; degree research `[]` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['anglo-norse.org.uk'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'Anglo-Norse Society / NTNU' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.18)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. Distinguishing tokens 'Anglo' and 'Norse' appear in no DB title, provider or URL. Provider overlap with DB 278 rests only on the token 'NTNU', which identifies the host university rather than the programme.

### research-050 — D (HIGH)

- **File** `scholarship_050_University_of_Stavanger_PhD_Fellowship_i.json`  (batch `norway_scholarships.json`)
- **Research title** University of Stavanger PhD Fellowship in Social Studies
- **Research provider** University of Stavanger (UiS)
- **Research URL** `https://www.uis.no/en/about-uis/vacant-positions-at-uis`, `https://www.uis.no/en/about-uis/vacant-positions-at-uis`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 277
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `University of Stavanger PhD Fellowship in Social Studies` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.0819, containment=0.156, seq=0.234
- *Provider comparison* research `University of Stavanger (UiS)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.1078
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['uis', 'stavanger', 'social', 'studies']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['uis.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Stavanger (UiS)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.18)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. The distinguishing tokens 'Stavanger' and 'UiS' appear nowhere in the DB; its only 6 Norway rows cover BI, NTNU and NORPART.

### research-051 — D (HIGH)

- **File** `scholarship_051_PhD_Research_Fellow_in_Social_Anthropolo.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Research Fellow in Social Anthropology (GENMAR Project)
- **Research provider** University of Bergen (UiB)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/297493`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/297493`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Research Fellow in Social Anthropology (GENMAR Project)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.0672, containment=0.11, seq=0.2737
- *Provider comparison* research `University of Bergen (UiB)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.1128
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['uib', 'genmar', 'anthropology', 'bergen']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Bergen (UiB)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.21)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. Distinguishing tokens 'UiB' and 'GENMAR' appear in no DB title, provider or URL; the DB has no University of Bergen row.

### research-052 — D (HIGH)

- **File** `scholarship_052_NMBU_PhD_Scholarship_within_Economics_or.json`  (batch `norway_scholarships.json`)
- **Research title** NMBU PhD Scholarship within Economics or Business
- **Research provider** Norwegian University of Life Sciences (NMBU)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/294585`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/294585`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `NMBU PhD Scholarship within Economics or Business` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.0774, containment=0.1404, seq=0.3908
- *Provider comparison* research `Norwegian University of Life Sciences (NMBU)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.2503
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['life', 'nmbu', 'within', 'economics']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'Norwegian University of Life Sciences (NMBU)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.29)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. The distinguishing token 'NMBU' appears nowhere in the DB; provider overlap with DB 278 rests only on the generic 'Norwegian University' prefix.

### research-053 — D (HIGH)

- **File** `scholarship_053_PhD_Research_Fellow_in_Natural_Language_.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Research Fellow in Natural Language Processing
- **Research provider** University of Oslo (UiO)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/294517`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/294517`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 276
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Research Fellow in Natural Language Processing` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.073, containment=0.1265, seq=0.2955
- *Provider comparison* research `University of Oslo (UiO)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=False, score=0.122
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['natural', 'processing', 'uio', 'oslo']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - provider mismatch: research 'University of Oslo (UiO)' vs DB 'Norwegian University of Science and Technology (NTNU)'
  - title dissimilar (score 0.22)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* A specific UiO PhD vacancy; no University of Oslo row exists in the DB.

### research-054 — D (HIGH)

- **File** `scholarship_054_A_Wilhelmsen_Foundation_Scholarship_Prog.json`  (batch `norway_scholarships.json`)
- **Research title** A. Wilhelmsen Foundation Scholarship Programme (BI Norwegian Business School)
- **Research provider** A. Wilhelmsen Foundation / BI Norwegian Business School
- **Research URL** `https://www.bi.no/en/programmes-and-individual-courses/scholarships/a.-wilhelmsen-foundation-scholarship-programme`, `https://www.bi.no/en/programmes-and-individual-courses/scholarships/a.-wilhelmsen-foundation-scholarship-programme`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 275, 276, 274
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `A. Wilhelmsen Foundation Scholarship Programme (BI Norwegian Business School)` vs DB `Master International Scholarship – Bergen` — identical_after_normalisation=False, idf-jaccard=0.0348, containment=0.0473, seq=0.4779
- *Provider comparison* research `A. Wilhelmsen Foundation / BI Norwegian Business School` vs DB `BI Norwegian Business School` — exact=False, score=0.6658
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['bi.no'], aggregator_page=False, conflict=False
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['wilhelmsen', 'bi', 'norwegian', 'business']`, aligned `['bi', 'norwegian', 'business']`, alignment=0.4528; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['bi.no']
  - provider token overlap 0.67
  - country agrees (Norway)
- *Conflicting evidence*
  - title dissimilar (score 0.36)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row for the A. Wilhelmsen programme at BI. The distinguishing token 'Wilhelmsen' appears in no DB row. DB's four BI rows (274 Presidential, 275 Bergen, 276 International Baccalaureate, 277 Future African Leader) are four different scholarships; domain overlap with bi.no identifies the institution, not the programme. The prior run left this at B with no match.

### research-055 — C (MEDIUM)

- **File** `scholarship_055_NTNU_PhD_Research_Fellow_Positions_Multi.json`  (batch `norway_scholarships.json`)
- **Research title** NTNU PhD Research Fellow Positions (Multiple)
- **Research provider** Norwegian University of Science and Technology (NTNU)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/302451`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/302451`
- **Inferred country** Norway
- **DB match** **278** — NTNU PhD Positions (Salaried Employment)
- **Top 3 candidates** 278, 279, 277
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `NTNU PhD Research Fellow Positions (Multiple)` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.3568, containment=0.5035, seq=0.5679
- *Provider comparison* research `Norwegian University of Science and Technology (NTNU)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['multiple', 'ntnu', 'positions', 'fellow']`, aligned `['ntnu', 'positions']`, alignment=0.2511; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
- *Prior report* category=D, prior target=278, merge target=None
- *Final reasoning* Provider exactly identical (NTNU) and, unlike research-041/056, this record is itself a multi-position umbrella listing ('Positions (Multiple)'), so it is conceptually the same object as DB 278 'NTNU PhD Positions (Salaried Employment)'. Still held for review because the research URL is a single jobbnorge.no vacancy listing while DB 278's URLs are the NTNU-wide posting and vacancies pages.

### research-056 — D (HIGH)

- **File** `scholarship_056_PhD_Candidate_in_AI-Enabled_Maritime_Sys.json`  (batch `norway_scholarships.json`)
- **Research title** PhD Candidate in AI-Enabled Maritime Systems for Environmental Monitoring
- **Research provider** Norwegian University of Science and Technology (NTNU)
- **Research URL** `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/301402`, `https://www.jobbnorge.no/en/available-jobs/joblisting/pdf/301402`
- **Inferred country** Norway
- **DB match** none
- **Top 3 candidates** 278, 279, 275
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `PhD Candidate in AI-Enabled Maritime Systems for Environmental Monitoring` vs DB `NTNU PhD Positions (Salaried Employment)` — identical_after_normalisation=False, idf-jaccard=0.054, containment=0.0786, seq=0.2883
- *Provider comparison* research `Norwegian University of Science and Technology (NTNU)` vs DB `Norwegian University of Science and Technology (NTNU)` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Norway (institution_gazetteer) vs DB=Norway → agree=True
- *Institution comparison* distinctive research tokens `['monitoring', 'environmental', 'maritime', 'candidate']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - provider string identical
  - country agrees (Norway)
- *Conflicting evidence*
  - official URL domains differ (research ['jobbnorge.no'] vs DB ['ntnu.edu'])
  - title dissimilar (score 0.22)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* A single named doctoral candidate post ('PhD Candidate in AI-Enabled Maritime Systems'), not a multi-position call. This is a different object from DB 278's umbrella row, so it is not an existing match; but writing a single job vacancy into the catalogue is itself questionable. No DB row carries its jobbnorge.no URL and no UiO/NTNU-specific row exists for this post.

### research-057 — D (HIGH)

- **File** `scholarship_057_DGES_Portugal_Government_Scholarship_Stu.json`  (batch `portugal_scholarships.json`)
- **Research title** DGES Portugal Government Scholarship (Study Grant) 2026/2027
- **Research provider** Direção-Geral do Ensino Superior (DGES) / Portuguese Government
- **Research URL** `https://www.dges.gov.pt/en`, `https://www.dges.gov.pt/en`
- **Inferred country** Portugal
- **DB match** none
- **Top 3 candidates** 303, 300, 302
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `DGES Portugal Government Scholarship (Study Grant) 2026/2027` vs DB `Camoes, I.P. Portuguese Language and Culture Scholarships` — identical_after_normalisation=False, idf-jaccard=0.0, containment=0.0, seq=0.4425
- *Provider comparison* research `Direção-Geral do Ensino Superior (DGES) / Portuguese Government` vs DB `Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)` — exact=False, score=0.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=False, conflict=True
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['geral', 'dges', 'ensino', 'superior']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['master', 'phd']` agree=True
- *Supporting evidence*
  - country agrees (Portugal)
- *Conflicting evidence*
  - official URL domains differ (research ['gov.pt'] vs DB ['instituto-camoes.pt'])
  - provider mismatch: research 'Direção-Geral do Ensino Superior (DGES) / Portuguese Government' vs DB 'Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)'
  - title dissimilar (score 0.33)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row. The distinguishing tokens 'DGES' and 'Ensino' appear nowhere in the DB and the registrable domain dges.gov.pt is in no DB row. The prior run left it at B with no match.

### research-058 — A (HIGH)

- **File** `scholarship_058_FCT_PhD_Studentships_2026_Regular_Line_o.json`  (batch `portugal_scholarships.json`)
- **Research title** FCT PhD Studentships 2026 – Regular Line of Application
- **Research provider** Fundação para a Ciência e a Tecnologia (FCT)
- **Research URL** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`, `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral`
- **Inferred country** Portugal
- **DB match** **299** — 2026 Call for PhD Studentships – Regular Line of Application (FCT)
- **Top 3 candidates** 299, 529, 527
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `FCT PhD Studentships 2026 – Regular Line of Application` vs DB `2026 Call for PhD Studentships – Regular Line of Application (FCT)` — identical_after_normalisation=False, idf-jaccard=0.8782, containment=1.0, seq=0.8
- *Provider comparison* research `Fundação para a Ciência e a Tecnologia (FCT)` vs DB `Foundation for Science and Technology (FCT)` — exact=False, score=0.1894
- *URL comparison* exact_canonical_overlap=['fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral'], domain_overlap=['fct.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['regular', 'line', 'studentships', 'application']`, aligned `['regular', 'line', 'studentships', 'application']`, alignment=0.4206; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - canonical official URL identical (fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral)
  - shared registrable domain: ['fct.pt']
  - strong title similarity (idf-jaccard 0.88, containment 1.00, seq 0.80)
  - country agrees (Portugal)
- *Conflicting evidence*
  - provider mismatch: research 'Fundação para a Ciência e a Tecnologia (FCT)' vs DB 'Foundation for Science and Technology (FCT)'
- *Prior report* category=A, prior target=299, merge target=299
- *Final reasoning* Canonical URL fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-geral is identical to DB 299 official_source_url and application_link. The URL path itself encodes the specific call ('2026', 'linha de candidatura geral'), which is also stated in the title. Country Portugal. Provider differs only by language (Portuguese vs English name for FCT).

### research-059 — D (HIGH)

- **File** `scholarship_059_FCT_PhD_Studentships_2026_Specific_Line_.json`  (batch `portugal_scholarships.json`)
- **Research title** FCT PhD Studentships 2026 – Specific Line (Non-Academic Environment)
- **Research provider** Fundação para a Ciência e a Tecnologia (FCT)
- **Research URL** `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-especifica-em-ambiente-nao-academico`, `https://www.fct.pt/en/concursos/concurso-bolsas-de-doutoramento-2026-linha-de-candidatura-especifica-em-ambiente-nao-academico`
- **Inferred country** Portugal
- **DB match** none
- **Top 3 candidates** 529, 527, 299
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `FCT PhD Studentships 2026 – Specific Line (Non-Academic Environment)` vs DB `Programa RESTART — 4ª Edição (FCT research funding after parental leave)` — identical_after_normalisation=False, idf-jaccard=0.0532, containment=0.1139, seq=0.197
- *Provider comparison* research `Fundação para a Ciência e a Tecnologia (FCT)` vs DB `Fundação para a Ciência e a Tecnologia (FCT), I.P.` — exact=False, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['fct.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['environment', 'specific', 'line', 'studentships']`, aligned `[]`, alignment=0.0; degree research `['phd']` vs DB `['phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['fct.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Conflicting evidence*
  - title dissimilar (score 0.15)
  - deadline text differs (research '2026-03-31...' vs DB '2026-11-13...')
- *Prior report* category=D, prior target=299, merge target=None
- *Final reasoning* This is a DIFFERENT FCT call from research-058, not a variant of it: the URL ends '/linha-de-candidatura-especifica-em-ambiente-nao-academico' where DB 299's ends '/linha-de-candidatura-geral', and the research title names the 'Specific Line (Non-Academic Environment)'. No DB row exists for the specific line. The prior run attached this to DB 299 at score 0.407, which would have merged two distinct FCT calls into one row.

### research-060 — E (HIGH)

- **File** `scholarship_060_MSCA_Postdoctoral_Fellowships_2026_with_.json`  (batch `portugal_scholarships.json`)
- **Research title** MSCA Postdoctoral Fellowships 2026 (with Portugal as host)
- **Research provider** European Commission – Marie Skłodowska-Curie Actions / FCT (Portugal)
- **Research URL** `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026`, `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026`
- **Inferred country** Portugal
- **DB match** **16** — Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships
- **Top 3 candidates** 16, 18, 17
- **Classification** **E**, confidence **HIGH**
- **Proposed action** `DUPLICATE_RESEARCH`

- *Title comparison* research `MSCA Postdoctoral Fellowships 2026 (with Portugal as host)` vs DB `Marie Skłodowska-Curie Actions (MSCA) Postdoctoral Fellowships` — identical_after_normalisation=False, idf-jaccard=0.2429, containment=0.4778, seq=0.5
- *Provider comparison* research `European Commission – Marie Skłodowska-Curie Actions / FCT (Portugal)` vs DB `European Commission (Marie Skłodowska-Curie Actions)` — exact=False, score=0.7636
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ec.europa.eu'], aggregator_page=False, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=EU (multiple) → agree=None
- *Institution comparison* distinctive research tokens `['host', 'portugal', 'curie', 'marie']`, aligned `['curie', 'marie']`, alignment=0.1597; degree research `['doctoral', 'postdoctoral']` vs DB `['doctoral', 'postdoctoral']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ec.europa.eu']
  - provider token overlap 0.76
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* DUPLICATE RESEARCH RECORD. This record and research-036 carry the IDENTICAL official URL (marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026) and the same programme (MSCA Postdoctoral Fellowships 2026); the only textual difference is the parenthetical '(with Portugal as host)', and the two came from different input batches (norway_scholarships.json vs portugal_scholarships.json). research-036 is the canonical capture. Flagged for de-duplication rather than re-enriched.

### research-061 — A (MEDIUM)

- **File** `scholarship_061_Cam_es_I_P_Scholarship_Program_for_Annua.json`  (batch `portugal_scholarships.json`)
- **Research title** Camões I.P. – Scholarship Program for Annual Courses in Portuguese Language and Culture 2026
- **Research provider** Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)
- **Research URL** `https://www.instituto-camoes.pt/en/activity-camoes/what-we-do/scholarships/scholarships-camoes-i-p/pt-language-culture-scholarships/candidaturas-lingua-en`, `https://www.instituto-camoes.pt/en/activity-camoes/what-we-do/scholarships/scholarships-camoes-i-p/pt-language-culture-scholarships/candidaturas-lingua-en`
- **Inferred country** Portugal
- **DB match** **303** — Camoes, I.P. Portuguese Language and Culture Scholarships
- **Top 3 candidates** 303, 527, 301
- **Classification** **A**, confidence **MEDIUM**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Camões I.P. – Scholarship Program for Annual Courses in Portuguese Language and Culture 2026` vs DB `Camoes, I.P. Portuguese Language and Culture Scholarships` — identical_after_normalisation=False, idf-jaccard=0.481, containment=0.5123, seq=0.5972
- *Provider comparison* research `Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)` vs DB `Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)` — exact=False, score=0.9
- *URL comparison* exact_canonical_overlap=['instituto-camoes.pt/en/activity-camoes/what-we-do/scholarships/scholarships-camoes-i-p/pt-language-culture-scholarships/candidaturas-lingua-en'], domain_overlap=['instituto-camoes.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['annual', 'courses', 'camoes', 'lingua']`, aligned `['camoes', 'lingua']`, alignment=0.1624; degree research `[]` vs DB `['master', 'phd']` agree=True
- *Supporting evidence*
  - canonical official URL identical (instituto-camoes.pt/en/activity-camoes/what-we-do/scholarships/scholarships-camoes-i-p/pt-language-culture-scholarships/candidaturas-lingua-en)
  - shared registrable domain: ['instituto-camoes.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Prior report* category=D, prior target=303, merge target=None
- *Final reasoning* Canonical URL instituto-camoes.pt/en/activity-camoes/what-we-do/scholarships/scholarships-camoes-i-p/pt-language-culture-scholarships/candidaturas-lingua-en is identical to DB 303 official_updates_url. Provider is fully contained in DB 303's provider. Country Portugal. DB 303 is the umbrella row for this exact scheme.

### research-062 — B (MEDIUM)

- **File** `scholarship_062_Cam_es_I_P_Summer_Course_Scholarship_Pro.json`  (batch `portugal_scholarships.json`)
- **Research title** Camões I.P. – Summer Course Scholarship Program 2026 (Online and In-Person)
- **Research provider** Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)
- **Research URL** `https://www.instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_abertura_Verao_2026_ENG.pdf`, `https://www.instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_abertura_Verao_2026_ENG.pdf`
- **Inferred country** Portugal
- **DB match** **303** — Camoes, I.P. Portuguese Language and Culture Scholarships
- **Top 3 candidates** 303, 301, 302
- **Classification** **B**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Camões I.P. – Summer Course Scholarship Program 2026 (Online and In-Person)` vs DB `Camoes, I.P. Portuguese Language and Culture Scholarships` — identical_after_normalisation=False, idf-jaccard=0.0964, containment=0.1411, seq=0.512
- *Provider comparison* research `Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)` vs DB `Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)` — exact=False, score=0.9
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['instituto-camoes.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['online', 'person', 'course', 'summer']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['master', 'phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['instituto-camoes.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Conflicting evidence*
  - title dissimilar (score 0.38)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Same awarding body and same scheme family as DB 303 (provider fully contained, same registrable domain), but this is a distinct 2026 SUMMER COURSE stream with its own notice PDF, whereas DB 303's title covers Portuguese Language and Culture Scholarships generally and its own application URL is the annual-courses page. Existing umbrella match with a granularity conflict - a human must decide whether to enrich DB 303 or open a separate row.

### research-063 — B (MEDIUM)

- **File** `scholarship_063_Cam_es_I_P_Research_Scholarship_Program_.json`  (batch `portugal_scholarships.json`)
- **Research title** Camões I.P. – Research Scholarship Program 2026
- **Research provider** Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)
- **Research URL** `https://instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_abertura_INV_2026_ENG.pdf`, `https://instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_abertura_INV_2026_ENG.pdf`
- **Inferred country** Portugal
- **DB match** **303** — Camoes, I.P. Portuguese Language and Culture Scholarships
- **Top 3 candidates** 303, 304, 628
- **Classification** **B**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Camões I.P. – Research Scholarship Program 2026` vs DB `Camoes, I.P. Portuguese Language and Culture Scholarships` — identical_after_normalisation=False, idf-jaccard=0.1608, containment=0.3412, seq=0.5859
- *Provider comparison* research `Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)` vs DB `Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)` — exact=False, score=0.9
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['instituto-camoes.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['camoes', 'lingua', 'cooperacao', 'instituto']`, aligned `['camoes', 'lingua', 'cooperacao', 'instituto']`, alignment=0.5082; degree research `[]` vs DB `['master', 'phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['instituto-camoes.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Same awarding body and scheme family as DB 303, but a distinct 2026 RESEARCH stream with its own notice PDF (Aviso_abertura_INV_2026_ENG.pdf) that is not DB 303's application page. Existing umbrella match with a granularity conflict.

### research-064 — B (MEDIUM)

- **File** `scholarship_064_Cam_es_I_P_Fern_o_Mendes_Pinto_Scholarsh.json`  (batch `portugal_scholarships.json`)
- **Research title** Camões I.P. – Fernão Mendes Pinto Scholarship Program 2026
- **Research provider** Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)
- **Research URL** `https://instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_de_abertura_FMP_2026_ENG.pdf`, `https://instituto-camoes.pt/images/bolsas/bolsas_2026/Aviso_de_abertura_FMP_2026_ENG.pdf`
- **Inferred country** Portugal
- **DB match** **303** — Camoes, I.P. Portuguese Language and Culture Scholarships
- **Top 3 candidates** 303, 304, 302
- **Classification** **B**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Camões I.P. – Fernão Mendes Pinto Scholarship Program 2026` vs DB `Camoes, I.P. Portuguese Language and Culture Scholarships` — identical_after_normalisation=False, idf-jaccard=0.108, containment=0.1676, seq=0.5455
- *Provider comparison* research `Camões – Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs)` vs DB `Camões - Instituto da Cooperação e da Língua, I.P. (Ministry of Foreign Affairs, Portugal)` — exact=False, score=0.9
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['instituto-camoes.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['mendes', 'pinto', 'fernao', 'camoes']`, aligned `['camoes']`, alignment=0.0921; degree research `[]` vs DB `['master', 'phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['instituto-camoes.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Same awarding body and scheme family as DB 303, but a distinct 2026 Fernao Mendes Pinto stream with its own notice PDF. Existing umbrella match with a granularity conflict.

### research-065 — D (HIGH)

- **File** `scholarship_065_University_of_Coimbra_Merit_Scholarships.json`  (batch `portugal_scholarships.json`)
- **Research title** University of Coimbra Merit Scholarships for International Students
- **Research provider** Universidade de Coimbra (UC)
- **Research URL** `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/`, `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/`
- **Inferred country** Portugal
- **DB match** none
- **Top 3 candidates** 301, 302, 304
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `University of Coimbra Merit Scholarships for International Students` vs DB `Nova SBE Master's Scholarships and Awards (including the Nova SBE Merit Scholarship)` — identical_after_normalisation=False, idf-jaccard=0.1439, containment=0.3422, seq=0.3893
- *Provider comparison* research `Universidade de Coimbra (UC)` vs DB `Nova School of Business and Economics (Nova SBE), Universidade NOVA de Lisboa` — exact=False, score=0.2883
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['coimbra', 'uc', 'universidade', 'merit']`, aligned `['universidade', 'merit']`, alignment=0.3129; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - country agrees (Portugal)
- *Conflicting evidence*
  - official URL domains differ (research ['uc.pt'] vs DB ['novasbe.unl.pt'])
  - provider mismatch: research 'Universidade de Coimbra (UC)' vs DB 'Nova School of Business and Economics (Nova SBE), Universidade NOVA de Lisboa'
  - title dissimilar (score 0.29)
- *Prior report* category=D, prior target=162, merge target=162
- *Final reasoning* SPECIAL INVESTIGATION - THE PRIOR MATCH TO DB 162 IS A WRONG MATCH. research-065 is Universidade de Coimbra (UC), Portugal, canonical URL uc.pt/en/studyatuc/international-students/bolsas-de-merito/. DB 162 is the University of Vienna, Austria, provider 'University of Vienna', URL studieren.univie.ac.at/en/scholarships, image hosted at studieren.univie.ac.at. The two records share nothing but the generic English template 'University of <X> ... Scholarships for International Students'. Country conflict (Portugal vs Austria), institution conflict (Coimbra vs Vienna), domain conflict (uc.pt vs univie.ac.at), provider conflict, and a four-language difference in the provider string. The prior merge committed this at confidence 0.75 and proposed 2 field updates onto DB 162. No DB row represents Coimbra; the record is genuinely new.

### research-066 — D (HIGH)

- **File** `scholarship_066_University_of_Aveiro_Incentive_Scholarsh.json`  (batch `portugal_scholarships.json`)
- **Research title** University of Aveiro Incentive Scholarships for International Students 2026/2027
- **Research provider** Universidade de Aveiro (UA)
- **Research URL** `https://www.ua.pt/en/international-scholarships`, `https://www.ua.pt/en/international-scholarships`
- **Inferred country** Portugal
- **DB match** none
- **Top 3 candidates** 301, 304, 302
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `University of Aveiro Incentive Scholarships for International Students 2026/2027` vs DB `Nova SBE Master's Scholarships and Awards (including the Nova SBE Merit Scholarship)` — identical_after_normalisation=False, idf-jaccard=0.0427, containment=0.0897, seq=0.3704
- *Provider comparison* research `Universidade de Aveiro (UA)` vs DB `Nova School of Business and Economics (Nova SBE), Universidade NOVA de Lisboa` — exact=False, score=0.2724
- *URL comparison* exact_canonical_overlap=[], domain_overlap=[], aggregator_page=True, conflict=True
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['aveiro', 'ua', 'incentive', 'universidade']`, aligned `['universidade']`, alignment=0.1356; degree research `[]` vs DB `['master']` agree=True
- *Supporting evidence*
  - country agrees (Portugal)
- *Conflicting evidence*
  - official URL domains differ (research ['ua.pt'] vs DB ['novasbe.unl.pt'])
  - provider mismatch: research 'Universidade de Aveiro (UA)' vs DB 'Nova School of Business and Economics (Nova SBE), Universidade NOVA de Lisboa'
  - title dissimilar (score 0.28)
- *Prior report* category=D, prior target=162, merge target=None
- *Final reasoning* SPECIAL INVESTIGATION - THE PRIOR MATCH TO DB 162 IS A WRONG MATCH for the identical reason as research-065: 'University of Aveiro ... Scholarships for International Students' (Universidade de Aveiro, Portugal, ua.pt) was matched to the University of Vienna row on the shared template wording alone. The token 'Aveiro' appears in no DB row.

### research-067 — A (HIGH)

- **File** `scholarship_067_Nova_SBE_Merit_Scholarship_Master_s_Prog.json`  (batch `portugal_scholarships.json`)
- **Research title** Nova SBE Merit Scholarship (Master's Programs)
- **Research provider** Nova School of Business and Economics (Nova SBE) – Universidade NOVA de Lisboa
- **Research URL** `https://www.novasbe.unl.pt/en/programs/scholarships-funding/masters`, `https://www.novasbe.unl.pt/en/programs/scholarships-funding/masters`
- **Inferred country** Portugal
- **DB match** **301** — Nova SBE Master's Scholarships and Awards (including the Nova SBE Merit Scholarship)
- **Top 3 candidates** 301, 304, 302
- **Classification** **A**, confidence **HIGH**
- **Proposed action** `SAFE_ENRICH_EXISTING`

- *Title comparison* research `Nova SBE Merit Scholarship (Master's Programs)` vs DB `Nova SBE Master's Scholarships and Awards (including the Nova SBE Merit Scholarship)` — identical_after_normalisation=False, idf-jaccard=0.5361, containment=0.8061, seq=0.4127
- *Provider comparison* research `Nova School of Business and Economics (Nova SBE) – Universidade NOVA de Lisboa` vs DB `Nova School of Business and Economics (Nova SBE), Universidade NOVA de Lisboa` — exact=True, score=1.0
- *URL comparison* exact_canonical_overlap=['novasbe.unl.pt/en/programs/scholarships-funding/masters'], domain_overlap=['novasbe.unl.pt'], aggregator_page=False, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['lisboa', 'sbe', 'nova', 'universidade']`, aligned `['lisboa', 'sbe', 'nova', 'universidade']`, alignment=0.4623; degree research `['master']` vs DB `['master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (novasbe.unl.pt/en/programs/scholarships-funding/masters)
  - shared registrable domain: ['novasbe.unl.pt']
  - provider string identical
  - strong title similarity (idf-jaccard 0.54, containment 0.81, seq 0.41)
  - country agrees (Portugal)
- *Prior report* category=A, prior target=301, merge target=None
- *Final reasoning* Canonical URL novasbe.unl.pt/en/programs/scholarships-funding/masters is identical to DB 301 official_source_url and application_link. Provider string identical. Country Portugal. DB 301's title even names the Nova SBE Merit Scholarship explicitly.

### research-068 — B (MEDIUM)

- **File** `scholarship_068_ULisboa_PhD_Scholarships_under_Unite_Wid.json`  (batch `portugal_scholarships.json`)
- **Research title** ULisboa PhD Scholarships under Unite! Widening – Industry-Embedded Doctoral School
- **Research provider** University of Lisbon (ULisboa) – Unite! Widening Project
- **Research URL** `https://www.ulisboa.pt/en/info/research-scholarships-doctoral-students-under-unite-widening-initiative`, `https://www.ulisboa.pt/en/info/research-scholarships-doctoral-students-under-unite-widening-initiative`
- **Inferred country** Portugal
- **DB match** **304** — University of Lisbon International Scholarships
- **Top 3 candidates** 304, 302, 299
- **Classification** **B**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `ULisboa PhD Scholarships under Unite! Widening – Industry-Embedded Doctoral School` vs DB `University of Lisbon International Scholarships` — identical_after_normalisation=False, idf-jaccard=0.0423, containment=0.0506, seq=0.3175
- *Provider comparison* research `University of Lisbon (ULisboa) – Unite! Widening Project` vs DB `University of Lisbon` — exact=False, score=0.2421
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['ulisboa.pt'], aggregator_page=False, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['ulisboa', 'widening', 'embedded', 'unite']`, aligned `[]`, alignment=0.0; degree research `['doctoral', 'phd']` vs DB `['bachelor', 'master', 'phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['ulisboa.pt']
  - country agrees (Portugal)
- *Conflicting evidence*
  - provider mismatch: research 'University of Lisbon (ULisboa) – Unite! Widening Project' vs DB 'University of Lisbon'
  - title dissimilar (score 0.24)
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* Provider is exactly 'University of Lisbon (ULisboa) - Unite! Widening Project', whose head institution is exactly DB 304's provider 'University of Lisbon', and the registrable domain ulisboa.pt is shared with DB 304's official URLs. But research-068 is a single named project (Unite! Widening industry-embedded doctoral school) whereas DB 304 is the university-wide International Scholarships umbrella. Existing umbrella match with a granularity conflict.

### research-069 — C (MEDIUM)

- **File** `scholarship_069_Erasmus_Mundus_Joint_Masters_Programs_wi.json`  (batch `portugal_scholarships.json`)
- **Research title** Erasmus Mundus Joint Masters – Programs with Portuguese Universities (2027/2028 cycle)
- **Research provider** European Commission (Erasmus+) – Various consortia including Portuguese universities
- **Research URL** `https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters`, `https://erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters`
- **Inferred country** Portugal
- **DB match** **300** — Erasmus Mundus Joint Master Degrees — Portuguese Universities
- **Top 3 candidates** 284, 1, 300
- **Classification** **C**, confidence **MEDIUM**
- **Proposed action** `MANUAL_REVIEW`

- *Title comparison* research `Erasmus Mundus Joint Masters – Programs with Portuguese Universities (2027/2028 cycle)` vs DB `Erasmus Mundus Joint Masters Degrees (EMJMD/EMJM) Scholarships` — identical_after_normalisation=False, idf-jaccard=0.2678, containment=0.3847, seq=0.5493
- *Provider comparison* research `European Commission (Erasmus+) – Various consortia including Portuguese universities` vs DB `European Commission (Erasmus+ Programme)` — exact=False, score=0.2673
- *URL comparison* exact_canonical_overlap=['erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters'], domain_overlap=['ec.europa.eu'], aggregator_page=False, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Belgium → agree=None
- *Institution comparison* distinctive research tokens `['consortia', 'various', 'including', 'cycle']`, aligned `[]`, alignment=0.0; degree research `['master']` vs DB `['master']` agree=True
- *Supporting evidence*
  - canonical official URL identical (erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters)
  - shared registrable domain: ['ec.europa.eu']
- *Conflicting evidence*
  - provider mismatch: research 'European Commission (Erasmus+) – Various consortia including Portuguese universities' vs DB 'European Commission (Erasmus+ Programme)'
- *Prior report* category=D, prior target=300, merge target=None
- *Final reasoning* TARGET CORRECTED, EVIDENCE INSUFFICIENT. The right row is DB 300 'Erasmus Mundus Joint Master Degrees - Portuguese Universities' (title, provider and country all agree). But the research URL erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters is NOT identity-specific - it is the generic Erasmus+ page and is also DB 284's official_updates_url, where DB 284 is the BELGIUM row. The Portugal-specific variant (.../joint-masters/portugal) is DB 300's URL and appears nowhere in the research record. A naive exact-URL write would have hit the Belgium row.

### research-070 — D (HIGH)

- **File** `scholarship_070_FCT_Scientific_Employment_Stimulus_Indiv.json`  (batch `portugal_scholarships.json`)
- **Research title** FCT Scientific Employment Stimulus – Individual Call (8th Edition)
- **Research provider** Fundação para a Ciência e a Tecnologia (FCT)
- **Research URL** `https://www.fct.pt/en/concursos/concurso-estimulo-ao-emprego-cientifico-individual-8-edicao`, `https://www.fct.pt/en/concursos/concurso-estimulo-ao-emprego-cientifico-individual-8-edicao`
- **Inferred country** Portugal
- **DB match** none
- **Top 3 candidates** 529, 527, 299
- **Classification** **D**, confidence **HIGH**
- **Proposed action** `SAFE_NEW_RECORD_CANDIDATE`

- *Title comparison* research `FCT Scientific Employment Stimulus – Individual Call (8th Edition)` vs DB `Programa RESTART — 4ª Edição (FCT research funding after parental leave)` — identical_after_normalisation=False, idf-jaccard=0.0529, containment=0.1126, seq=0.2308
- *Provider comparison* research `Fundação para a Ciência e a Tecnologia (FCT)` vs DB `Fundação para a Ciência e a Tecnologia (FCT), I.P.` — exact=False, score=1.0
- *URL comparison* exact_canonical_overlap=[], domain_overlap=['fct.pt'], aggregator_page=True, conflict=False
- *Country comparison* research=Portugal (institution_gazetteer) vs DB=Portugal → agree=True
- *Institution comparison* distinctive research tokens `['individual', 'stimulus', '8th', 'edition']`, aligned `[]`, alignment=0.0; degree research `[]` vs DB `['phd']` agree=True
- *Supporting evidence*
  - shared registrable domain: ['fct.pt']
  - provider fully contained in DB provider (idf-containment 1.00)
  - country agrees (Portugal)
- *Conflicting evidence*
  - title dissimilar (score 0.17)
  - deadline text differs (research '2026-02-02...' vs DB '2026-11-13...')
- *Prior report* category=B, prior target=None, merge target=None
- *Final reasoning* No DB row for this call. The URL fct.pt/en/concursos/concurso-estimulo-ao-emprego-cientifico-individual-8-edicao identifies a distinct FCT programme from the DB's FCT rows (299 PhD regular line, 527 Portugal-Berkeley, 529 RESTART). The distinguishing tokens 'Stimulus' and '8th' align nowhere. The prior run attached it to DB 529 (Programa RESTART) at score 0.43 on provider overlap alone, which would have merged two unrelated FCT calls and, per its own report, proposed a deadline overwrite from 2026-11-13 to 2026-02-02.

---

## Existing Matches

Confirmed matches only (class **A**). Each is supported by at least two independent signals.

| research | DB | confidence | decisive evidence |
|---|---|---|---|
| research-001 | **271** | HIGH | provider exact + URL domain + title alignment |
| research-002 | **272** | HIGH | canonical URL identical |
| research-003 | **269** | HIGH | provider exact + institution/title alignment |
| research-004 | **273** | HIGH | canonical URL identical |
| research-005 | **332** | MEDIUM | provider exact + URL domain + title alignment |
| research-006 | **333** | MEDIUM | provider exact + URL domain + title alignment |
| research-007 | **334** | HIGH | provider exact + URL domain + title alignment |
| research-008 | **264** | MEDIUM | provider exact + institution/title alignment |
| research-009 | **335** | HIGH | provider exact + institution/title alignment |
| research-013 | **337** | HIGH | provider exact + institution/title alignment |
| research-014 | **338** | HIGH | provider exact + institution/title alignment |
| research-016 | **340** | HIGH | provider exact + institution/title alignment |
| research-019 | **343** | MEDIUM | provider exact + institution/title alignment |
| research-020 | **344** | MEDIUM | provider exact + institution/title alignment |
| research-021 | **345** | MEDIUM | provider exact + URL domain + title alignment |
| research-027 | **350** | MEDIUM | provider exact + URL domain + title alignment |
| research-031 | **285** | HIGH | canonical URL identical |
| research-032 | **356** | HIGH | canonical URL identical |
| research-035 | **359** | HIGH | canonical URL identical |
| research-036 | **16** | MEDIUM | provider exact + institution/title alignment |
| research-045 | **16** | MEDIUM | provider exact + institution/title alignment |
| research-058 | **299** | HIGH | canonical URL identical |
| research-061 | **303** | MEDIUM | canonical URL identical |
| research-067 | **301** | HIGH | canonical URL identical |

### A-records that share one DB row

| DB row | research records | comment |
|---|---|---|
| 16 — MSCA Postdoctoral Fellowships | research-036 (2026 call), research-045 (2027 call) | one programme row, two annual call pages; not duplicates |
| 359 — Semmelweis Pannonia | research-035 | previously mis-classified B on a false deadline conflict |

---

## Conflicts / Human Review

**Class B — existing match with conflict (4).** Identity is established but record granularity disagrees, so
enriching the umbrella row would overwrite broader content with one sub-programme's detail.

| research | DB | confidence | conflict |
|---|---|---|---|
| research-062 | 303 | MEDIUM | Same awarding body and same scheme family as DB 303 (provider fully contained, same registrable domain), but this is a distinct 2026 SUMMER COURSE stream with its own notice PDF, whereas DB 303's title covers Portuguese Language and Culture Scholarships generally and its own application URL is the annual-courses page. Existing umbrella match with a granularity conflict - a human must decide whether to enrich DB 303 or open a separate row. |
| research-063 | 303 | MEDIUM | Same awarding body and scheme family as DB 303, but a distinct 2026 RESEARCH stream with its own notice PDF (Aviso_abertura_INV_2026_ENG.pdf) that is not DB 303's application page. Existing umbrella match with a granularity conflict. |
| research-064 | 303 | MEDIUM | Same awarding body and scheme family as DB 303, but a distinct 2026 Fernao Mendes Pinto stream with its own notice PDF. Existing umbrella match with a granularity conflict. |
| research-068 | 304 | MEDIUM | Provider is exactly 'University of Lisbon (ULisboa) - Unite! Widening Project', whose head institution is exactly DB 304's provider 'University of Lisbon', and the registrable domain ulisboa.pt is shared with DB 304's official URLs. But research-068 is a single named project (Unite! Widening industry-embedded doctoral school) whereas DB 304 is the university-wide International Scholarships umbrella. Existing umbrella match with a granularity conflict. |

**Class C — uncertain / human review (10).**

| research | DB candidate | confidence | why it is not safe to write |
|---|---|---|---|
| research-011 | 335 (candidates 335, 263, 264) | LOW | UNRESOLVED NAME COLLISION. Provider is exactly Aalto University, but the distinguishing token 'Reserve' occurs in no DB row, so this cannot be the Excellence Scholarship. It also cannot be asserted as new: nothing in the DB confirms or denies an 'Aalto Reserve Scholarship'. The prior run committed this as a confirmed match to DB 335 (confidence 0.75) - this is one of the two duplicate mappings under investigation and it is a matcher error driven by the generic tokens '100% tuition fee waiver'. |
| research-012 | 336 (candidates 265, 336, 335) | MEDIUM | Provider exactly identical (Tampere University), but two competing DB rows exist for the Tampere tuition scholarship: DB 336 (active) and DB 265 (archived AND quarantined). The research title's third element 'International Advancement Scholarship' matches neither row's title. Row selection cannot be made automatically. |
| research-015 | 339 (candidates 339, 266, 338) | MEDIUM | Provider exactly identical (University of Turku), which decisively rules out DB 337 (University of Oulu) - the target the prior merge committed to. However DB contains TWO near-identical Turku rows for this same scholarship: DB 339 (idf-jaccard 0.75 to DB 266). Both are active. Choosing between them is a human decision, so this is held for review rather than auto-enriched. |
| research-018 | 342 (candidates 342, 343, 265) | MEDIUM | Institution matches exactly (Hanken School of Economics) and the research provider's 'GBSN collaboration' matches DB 342's GBSN Honor Scholarship. But the scholarship NAME conflicts: research says 'Premium Scholarship', DB 342 says 'GBSN Honor Scholarship'. These may be the same scheme under two names or two separate schemes; the DB cannot settle it. |
| research-025 | 348 (candidates 348, 350, 284) | HIGH | Identity is CERTAIN: the title token set is identical to DB 348. It is held for review only because the target row is deliberately retired - is_archived=1, verification_status=quarantined, archived_reason 'DEAD: the recorded url does not resolve in DNS (NXDOMAIN for both apex and www). Successor: https://sites.uef.fi/europeanforestry/'. A write must not resurrect a dead-URL row; a human must decide between repointing the row to the successor and creating a new record. |
| research-026 | 349 (candidates 349, 350, 348) | HIGH | Identity is CERTAIN: the title token set is identical to DB 349. Held for the same reason as research-025 - DB 349 is archived and quarantined with archived_reason 'DEAD: ... does not resolve in DNS (NXDOMAIN). Successor programme and site: EMCL-25 at https://emcl.eu/'. |
| research-041 | 278 (candidates 278, 279, 276) | MEDIUM | Same institution as DB 278 (provider exactly identical, NTNU) and the research record is a multi-position faculty call ('Up to 7 PhD Research Fellow Positions'), conceptually close to the DB 278 umbrella row. But research-041 is one faculty-specific vacancy with a jobbnorge.no listing URL while DB 278 is the NTNU-wide posting page. Writing this onto DB 278 would replace umbrella content with one vacancy's content. |
| research-044 | 1 (candidates 1, 168, 192) | MEDIUM | CORRECTION OF A WRONG MATCH. The research URL eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en is identical to DB 1's catalogue_url, and DB 1 is the country-agnostic Erasmus Mundus umbrella row. The prior run mapped this record to DB 168 on 'exact_url_match', but DB 168 is the AUSTRIA-specific row and its title is 'Erasmus Mundus Joint Master Degrees - Austria-based'. The EACA catalogue URL is shared by every country variant in the DB (168 Austria, 192 Sweden, and DB 1 itself), so it is NOT identity-specific. There is no Norway-specific Erasmus Mundus row in the DB, so DB 1 is the only defensible target - but because the sole URL signal is a shared catalogue page, a human must confirm it. |
| research-055 | 278 (candidates 278, 279, 277) | MEDIUM | Provider exactly identical (NTNU) and, unlike research-041/056, this record is itself a multi-position umbrella listing ('Positions (Multiple)'), so it is conceptually the same object as DB 278 'NTNU PhD Positions (Salaried Employment)'. Still held for review because the research URL is a single jobbnorge.no vacancy listing while DB 278's URLs are the NTNU-wide posting and vacancies pages. |
| research-069 | 300 (candidates 284, 1, 300) | MEDIUM | TARGET CORRECTED, EVIDENCE INSUFFICIENT. The right row is DB 300 'Erasmus Mundus Joint Master Degrees - Portuguese Universities' (title, provider and country all agree). But the research URL erasmus-plus.ec.europa.eu/opportunities/individuals/students/erasmus-mundus-joint-masters is NOT identity-specific - it is the generic Erasmus+ page and is also DB 284's official_updates_url, where DB 284 is the BELGIUM row. The Portugal-specific variant (.../joint-masters/portugal) is DB 300's URL and appears nowhere in the research record. A naive exact-URL write would have hit the Belgium row. |

**Class E — duplicate / invalid (2).**

| research | duplicate of / target | confidence | why |
|---|---|---|---|
| research-017 | 341 | HIGH | INVALID RESEARCH RECORD - reproduces a programme this database has already debunked. The title is identical to DB 341, but DB 341 is verification_status=quarantined, is_archived=1, with archived_reason 'NEVER-EXISTED: RETIRED - the awarding body's own current page denies that the programme exists' and deletion_protected=1. DB 262 independently records that Finland has 'no national government scholarship programme'. The prior run classified this as a CONFIRMED match (score 1.05) to DB 341, which would have resurrected a deliberately retired record. |
| research-060 | research-036 | HIGH | DUPLICATE RESEARCH RECORD. This record and research-036 carry the IDENTICAL official URL (marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026) and the same programme (MSCA Postdoctoral Fellowships 2026); the only textual difference is the parenthetical '(with Portugal as host)', and the two came from different input batches (norway_scholarships.json vs portugal_scholarships.json). research-036 is the canonical capture. Flagged for de-duplication rather than re-enriched. |

---

## New Record Candidates

Class **D** — no DB row carries sufficient identity evidence.

| research | title | country | top candidates (all rejected) |
|---|---|---|---|
| research-010 | Aalto University Pekka Mattila Excellence Scholarship (€3,000 Relocation Grant) | Finland | 335, 263, 265 |
| research-022 | Erasmus Mundus MARIHE Scholarship (Master in Research and Innovation in Higher Education) | Finland | 350, 349, 348 |
| research-023 | Erasmus Mundus EDISS Scholarship (Engineering of Data-intensive Intelligent Software Systems) | Finland | 350, 348, 349 |
| research-024 | Erasmus Mundus REPLAY Scholarship (European Game Design Masters) | Finland | 350, 349, 348 |
| research-028 | Aalto University Colfuturo Scholarship Partnership (25% Tuition Discount for Colombian Students) | Finland | 335, 263, 339 |
| research-029 | Aalto University FUNED Scholarship Partnership (25% Tuition Discount for Mexican Students) | Finland | 335, 263, 339 |
| research-030 | Fulbright-Nokia Distinguished Chair in ICT | Finland | 343, 344, 338 |
| research-033 | Momentum MSCA Postdoctoral Fellowship | Hungary | 582, 16, 629 |
| research-034 | Hungarian Diaspora Scholarship | Hungary | 285, 356, 359 |
| research-037 | Fulbright Norway Open Study/Research Award 2027-2028 | Norwegian | 469, 470, 27 |
| research-038 | Fulbright Norway English Teaching Assistant Award 2027-2028 | Norwegian | 470, 469, 27 |
| research-039 | PhD Research Fellow in Machine Learning for Cognitive Neuroscience | Norway | 278, 279, 277 |
| research-040 | PhD Research Fellow in Meteorology | Norway | 278, 279, 274 |
| research-042 | PhD Research Fellow in Political Science (3-4 years) | Norway | 278, 279, 274 |
| research-043 | A. Wilhelmsen Foundation Scholarship Programme (NTNU IMT) | Norway | 278, 275, 279 |
| research-046 | VID Specialized University PhD Research Fellowships in Theology and Religion | Norway | 278, 279, 274 |
| research-047 | Coimbra Group Scholarship Programme 2026 (University of Bergen) | Norway | 275, 278, 279 |
| research-048 | NORAM Graduate Scholarship (Americans to Norway) | Norwegian | 591, 101, 307 |
| research-049 | Anglo-Norse Society Scholarship (NTNU) | Norway | 278, 276, 277 |
| research-050 | University of Stavanger PhD Fellowship in Social Studies | Norway | 278, 279, 277 |
| research-051 | PhD Research Fellow in Social Anthropology (GENMAR Project) | Norway | 278, 279, 274 |
| research-052 | NMBU PhD Scholarship within Economics or Business | Norway | 278, 279, 274 |
| research-053 | PhD Research Fellow in Natural Language Processing | Norway | 278, 279, 276 |
| research-054 | A. Wilhelmsen Foundation Scholarship Programme (BI Norwegian Business School) | Norway | 275, 276, 274 |
| research-056 | PhD Candidate in AI-Enabled Maritime Systems for Environmental Monitoring | Norway | 278, 279, 275 |
| research-057 | DGES Portugal Government Scholarship (Study Grant) 2026/2027 | Portugal | 303, 300, 302 |
| research-059 | FCT PhD Studentships 2026 – Specific Line (Non-Academic Environment) | Portugal | 529, 527, 299 |
| research-065 | University of Coimbra Merit Scholarships for International Students | Portugal | 301, 302, 304 |
| research-066 | University of Aveiro Incentive Scholarships for International Students 2026/2027 | Portugal | 301, 304, 302 |
| research-070 | FCT Scientific Employment Stimulus – Individual Call (8th Edition) | Portugal | 529, 527, 299 |

### Caveat on the D bucket

`LIKELY NEW` is a statement about the database, not about the real world. Two sub-groups need extra caution:

- **The 25-record Finland batch (006–030)** has no official URL at all. Absence of a match there is weaker
  evidence of novelty than a URL mismatch would be. Where I classified these D, it is because the
  distinguishing programme token is absent from all 691 rows — not merely because scoring fell short.
- **The Norwegian PhD vacancies (039–056)** are third-party `jobbnorge.no` postings or generic university
  vacancy-listing pages. Several point at the same umbrella page, so URLs are not identity-specific. These are
  job advertisements, not scholarships, and whether they belong in the catalogue at all is a product
  decision, not a matching decision.

---

## Duplicate Research Records

**Within the 70 research records: one duplicate pair.**

| pair | evidence | disposition |
|---|---|---|
| `research-036` ↔ `research-060` | byte-identical official URL `https://marie-sklodowska-curie-actions.ec.europa.eu/funding/msca-postdoctoral-fellowships-2026`; same programme; differs only by the suffix “(with Portugal as host)” and by source batch (`norway_scholarships.json` vs `portugal_scholarships.json`) | `research-060` → **E / DUPLICATE_RESEARCH**; `research-036` is the canonical capture |

**Not duplicates, despite looking similar:**

- `research-036` / `research-045` / `research-060` are the 2026 and 2027 call pages of **one** programme that the
  DB stores as a single row (id 16). 036/045 share a target legitimately; only 036/060 are true duplicates.
- `research-037` vs `research-038` — distinct Fulbright Norway award types, distinct URLs (`/norway/1739` vs `/norway/1740`).
- `research-058` vs `research-059` — two **different** FCT 2026 calls (general line vs specific line), distinct URLs. Merging them, as the prior run did, would be an error.
- `research-062` / `research-063` / `research-064` — distinct Camões sub-streams with distinct notice PDFs.
- **Exact-title duplication: none.** No two of the 70 records share a normalised title.

**DB-internal duplicates found (reported, not modified).** These matter because even a correct
research→record mapping is not automatically a correct write target.

| ids | country | titles | note |
|---|---|---|---|
| 263, 335 | Finland | Aalto University Excellence Scholarship / Aalto University Excellence Scholarship (100% tuition fee waiver) | Two rows for the same real-world Aalto Excellence Scholarship. Both active. research-009 maps to 335 on an exact title match; 263 is the weaker match but is not archived, so the pair must be resolved before any enrichment. |
| 339, 266 | Finland | University of Turku Merit Scholarship (50% of tuition) and Early Bird Discount / University of Turku Merit Scholarship and Early Bird Discount | Two active rows for the same Turku scholarship (idf-jaccard 0.75). research-015 matches both; row selection is ambiguous. |
| 265, 336 | Finland | Tampere University Tuition Fee Scholarship / Tampere University tuition fee scholarship (50%) and early bird offer | Two rows for the Tampere scholarship; 265 is archived AND quarantined while 336 is active. research-012 spans both. |
| 27, 469 | United States | Fulbright Foreign Student Program / Fulbright Foreign Student Program | Both already archived and quarantined, each documenting the other as a duplicate ('DUPLICATE: id=27 and id=469 are the same single global programme'). Pre-existing, correctly retired. |
| 329, 271 | Denmark | Danish Government Scholarship / University of Copenhagen Danish Government Scholarship | Weaker duplicate of the Copenhagen row. 271 carries the full record; 329 has no deadline and a different domain (studies.ku.dk). research-001 maps to 271. |
| 330, 272 | Denmark | Danish State Scholarship / Aarhus University Danish State Scholarship | Weaker duplicate of the Aarhus row; 272 carries the full record. research-002 maps to 272. |
| 331, 269 | Denmark | Tuition Fee Waiver / DTU Tuition Fee Waiver for International non-EU/EEA MSc Students | 331 is archived AND quarantined and is the legacy duplicate of the DTU row 269. research-003 maps to 269. |
| 1, 168, 192, 284, 293, 298, 300 | EU (multiple) / Austria / Sweden / Belgium / Poland / Czech Republic / Portugal | Erasmus Mundus Joint Masters (EMJM) / Erasmus Mundus Joint Master Degrees - Austria-based / Erasmus Mundus Joint Master Degrees (Erasmus Mundus Catalogue) / Erasmus Mundus Joint Masters Degrees (EMJMD/EMJM) Scholarships / Erasmus Mundus Joint Master Degrees - Polish Universities / Erasmus Mundus Joint Master Degrees - Czech Universities / Erasmus Mundus Joint Master Degrees - Portuguese Universities | Seven overlapping Erasmus Mundus rows. DB 1 is the country-agnostic umbrella; 168/192/293/298/300 are country variants keyed by a URL path segment; 284 is a Belgium row whose official_updates_url is the GENERIC Erasmus+ page. The shared EACA catalogue URL is used by 1, 168 and 192, which is the root cause of the prior run's wrong match research-044 -> 168. |

---

## Wrong Matches

### research-065 → DB 162 — CONFIRMED WRONG MATCH

The prior audit suspected this; it is now proven.

| | research-065 | DB 162 |
|---|---|---|
| title | University of Coimbra Merit Scholarships for International Students | University of Vienna Scholarships for International Students |
| provider | Universidade de Coimbra (UC) | University of Vienna |
| country | **Portugal** | **Austria** |
| official URL | `https://www.uc.pt/en/studyatuc/international-students/bolsas-de-merito/` (uc.pt) | `https://studieren.univie.ac.at/en/scholarships` (univie.ac.at) |
| image host | ku/uc.pt | studieren.univie.ac.at |

**Evidence that this is wrong:**

1. **Country conflict** — Portugal vs Austria.
2. **Institution conflict** — "Coimbra" appears nowhere in DB 162 and "Vienna" appears nowhere in research-065.
3. **Domain conflict** — `uc.pt` vs `univie.ac.at`: disjoint registrable domains, not even a shared host.
4. **Provider conflict** — different organisations in different languages; no shared token beyond "University"/"Universidade".
5. **The only shared signal is a generic template** — "University of ‹X› … Scholarships for International Students" is exactly the wording that produces a false positive, and it is the signal the prior matcher relied on (score 0.667).
6. **No DB row represents Coimbra** — the 9 Portugal rows are ids 299, 300, 301, 302, 303, 304, 527, 529, 628.
7. **Impact if written** — `merge_report.json` committed this at confidence 0.75 and proposed **2 field updates onto DB 162** (plus 8 conflicts), i.e. a Coimbra record's values would have been written onto the Vienna row.

**Correct classification: D — LIKELY NEW RECORD** (confidence HIGH). There is no existing Coimbra row to enrich.

**The same error also hit research-066** (University of Aveiro, `ua.pt`), which the prior reconciliation
matched to DB 162 at score 0.545. Corrected to D.

### All prior wrong mappings

| research | prior target | why wrong | corrected |
|---|---|---|---|
| research-011 | 335 (confirmed) | "Aalto Reserve Scholarship" ≠ "Aalto Excellence Scholarship"; distinguishing token `Reserve` absent from DB 335 | C → 335 |
| research-015 | 337 (merge) / 266 (recon) | DB 337 is the **University of Oulu** row; the record is **University of Turku** | C → 339 |
| research-044 | 168 (confirmed) | DB 168 is the **Austria-specific** Erasmus Mundus row; the record is Norway-linked. The EACA catalogue URL is shared by ids 1, 168 and 192 | C → 1 |
| research-017 | 341 (confirmed) | DB 341 is `quarantined`, `is_archived=1`, `deletion_protected=1`, reason **NEVER-EXISTED** | E |
| research-065 | 162 (confirmed) | University of Coimbra ≠ University of Vienna | D |
| research-066 | 162 | University of Aveiro ≠ University of Vienna | D |
| research-059 | 299 | distinct FCT call (specific line) merged into the general-line row | D |
| research-070 | 529 | FCT Stimulus call merged into the RESTART row; proposed deadline overwrite 2026-11-13 → 2026-02-02 | D |

---

## Duplicate Mapping Investigation

### DB 335 — "Aalto University Excellence Scholarship (100% tuition fee waiver)"

Two research records were mapped here: **one legitimate, one a matcher error.**

| research | prior confidence | verdict | reasoning |
|---|---|---|---|
| research-009 "Aalto University Excellence Scholarship (100% Tuition Fee Waiver)" | 1.0 | **legitimate** | title identical after normalisation, provider exactly identical, country Finland |
| research-011 "Aalto Reserve Scholarship (100% Tuition Fee Waiver)" | 0.75 | **matcher error** | overlap is only the generic cluster {100%, tuition, fee, waiver, scholarship} plus the institution name. The token that distinguishes the two schemes — `Reserve` — is absent from DB 335, and DB 335's distinguishing token `Excellence` is absent from the research record. |

**Consequence.** Because the prior pipeline allowed one DB row per record, the second mapping was recorded
as a "duplicate" and research-011 was effectively **silently dropped** from enrichment
(`merge_verification_report.json` lists `duplicate_ids: ["335"]`). The correct disposition is
**MANUAL_REVIEW**, not de-duplication — a human must decide whether "Aalto Reserve Scholarship" is a distinct
Aalto scheme or a mis-naming of the Excellence Scholarship.

**Aggravating factor:** the DB itself holds two rows for this one real-world scholarship — **263** and **335**
(idf-jaccard 0.50), both active. So "335" was never an unambiguous target even for the legitimate record.

### DB 337 — "University of Oulu Early Bird Discount and Tuition Fee Waiver Scholarship"

Again **one legitimate mapping and one matcher error**, caused by matching on a generic phrase.

| research | prior confidence | verdict | reasoning |
|---|---|---|---|
| research-013 "University of Oulu Tuition Fee Waivers and Early Bird Discount" | 0.818 | **legitimate** | provider exactly identical, tokens {oulu, bird, discount} all align, and DB 337's `image_alt_text` is verbatim the research title |
| research-015 "University of Turku Tuition Fee Waivers and Early Bird Discount" | 0.727 | **matcher error** | **DB 337 is the University of Oulu row.** The research record is the University of Turku. The matcher matched the shared phrase "Tuition Fee Waivers and Early Bird Discount" and ignored the institution — the most identity-bearing field in the record |

**Correct target for research-015** is DB 339 (or DB 266) — the University of Turku rows — never DB 337.

**Proof the prior pipeline was internally unstable:** the two prior artefacts disagree *with each other* about
research-015. `merge_report.json` (14:07:26Z) assigned it to **337**; `reconciliation_report.json** (14:26:00Z)
assigned it to **266**. Same record, same inputs, two different targets, 19 minutes apart.

---

## Previous Report vs Fresh Audit

### Why `matched_existing = 16` while `category_counts.A = 17`

They are **two different matcher runs**, not one inconsistent count.

- `merge_report.json` — generated `2026-10-06T14:07:26.978796+00:00` — `matched=16`, `unmatched=54`
- `reconciliation_report.json` — generated `2026-10-06T14:26:00Z` — `category_counts {A:17, D:27, B:26}`

| membership difference | records |
|---|---|
| in merge set, **not** in reconciliation A | research-008 (→264), research-065 (→162) |
| in reconciliation A, **not** in merge set | research-012 (→265), research-044 (→168), research-067 (→301) |

`17 = 16 − 2 + 3`. The two reports differ by five records and were produced by different matching logic 19 minutes apart.

### The prior category letters do not mean what they suggest

In `reconciliation_report.json`, `"B"` means **genuinely_new** (26 records, `match_details: []`, reason
`"genuinely_new (score=[])"`) and `"D"` means **below-threshold candidate match**. The stated prior estimate
`A=17, B=26, C=0, D=27, E=0` is simply that report's `category_counts` relabelled onto this audit's alphabet.
**It is therefore not comparable with the A/B/C/D/E used here**, and "previous A=17" does not mean
"17 records were correctly matched".

### `field_updates_applied = 28` — nothing was written

`merge_verification_report.json` is self-contradictory:

```
db_total_before   : 691
db_total_after    : 691
db_rows_created   : 0
db_rows_updated   : 0
db_rows_unchanged : 691
field_updates_applied : 28     <-- inconsistent with the four lines above
```

`merge_report.json` holds 493 `proposed_fields`, 87 `conflicts` and 100 `rejected_fields`. The 28 is a subset of
proposals that passed the field-level gate, not a write count. **The pipeline's own accounting cannot be relied on
to prove a later write left the DB untouched.**

### Transition matrix — prior category → this audit

| prior category | count | → A | → B | → C | → D | → E |
|---|---|---|---|---|---|---|
| prior A | 17 | 10 | 0 | 6 | 0 | 1 |
| prior B | 26 | 1 | 4 | 1 | 20 | 0 |
| prior D | 27 | 14 | 0 | 3 | 10 | 0 |

Read: of the prior run's **17 confirmed** matches, only **10** survive — 6 became uncertain and 1 became invalid.
Of its **27** below-threshold candidates, **14** are in fact solid existing matches. Of its **26** "genuinely
new" records, **6** have a real existing match or umbrella parent.

### 14 prior-"D" records that are genuinely existing matches

| research | DB | prior score | why the prior matcher missed it |
|---|---|---|---|
| research-003 | **269** | 0.52 | exact provider `Technical University of Denmark (DTU)` + shared dtu.dk domain; title wording differed |
| research-005 | **332** | 0.43 | shared aau.dk domain + full title containment, but title jaccard was only 0.34 |
| research-006 | **333** | 0.69 | picked the wrong Helsinki doctoral row (334); DB 333 carries the `RESDOC` + `MSCA COFUND` markers |
| research-007 | **334** | 0.6 | near-identical title, provider subset |
| research-008 | **264** | 0.695 | landed 0.005 under the arbitrary 0.70 cut |
| research-014 | **338** | 0.65 | exact provider; the `30%` qualifier aligned but was not weighted |
| research-016 | **340** | 0.47 | exact provider; score depressed by an A-ring character the prior tokenizer mishandled |
| research-019 | **343** | 0.5 | scholarship name matches DB title exactly; only provider overlap was credited |
| research-020 | **344** | 0.53 | same as above |
| research-021 | **345** | 0.34 | `Jorma Ollila Grant` matches DB title exactly |
| research-027 | **350** | 0.4 | `BioCEB` matches DB 350's title |
| research-036 | **16** | 0.475 | provider overlap only; the MSCA programme match was never attempted |
| research-045 | **16** | 0.475 | same |
| research-061 | **303** | 0.425 | research URL is byte-identical to DB 303 `official_updates_url` — the matcher only compared against `official_source_url` |

### Independent verification of the prior `A=17, B=26, C=0, D=27, E=0`

**Not reproduced, and not forced to match.** Independently derived result:

| class | prior (relabelled) | fresh audit | delta |
|---|---|---|---|
| A | 17 | **24** | +7 |
| B | 26 | **4** | -22 |
| C | 0 | **10** | +10 |
| D | 27 | **30** | +3 |
| E | 0 | **2** | +2 |

The two distributions are close in total but not in composition. `C` moves 0 → 10 and `E` 0 → 2 because this
audit distinguishes *uncertain* and *invalid* outcomes, which the previous three-valued scheme had nowhere to put.
`A` falls 17 → 24 not because more records were matched, but because 14 records the prior run dismissed are now
confirmed while 7 of its 17 confirmations were withdrawn.

### Root cause of the prior run's failures

1. **A single blended similarity score with an arbitrary threshold.** `matched_score_threshold: 0.7` and
   `ambiguous_score_threshold: 0.4`. Title jaccard could single-handedly exceed the cut, so provider, domain,
   institution and country were decorative. This is what produced the Vienna/Coimbra collision.
2. **No URL specificity test.** A shared catalogue page (`eacea.ec.europa.eu/.../erasmus-mundus-catalogue_en`,
   `erasmus-plus.ec.europa.eu/.../erasmus-mundus-joint-masters`) was treated as identity evidence. Those URLs are
   shared by ids 1, 168, 192 and 284 — one of which is a Belgium row.
3. **No veto rule.** Nothing stopped a candidate when country *and* domain both conflicted.
4. **Institution not treated as identity-bearing.** "University of Turku" was matched to a University of
   Oulu row.
5. **No DB row-health gate.** A `quarantined` + `is_archived` + `deletion_protected` row was an eligible target.
6. **Two matchers, one pipeline.** `merge_report.json` and `reconciliation_report.json` disagreed on membership
   and on research-015's target.
7. **No de-duplication of the research input.** Two batches captured the same MSCA 2026 call.

---

# FINAL VERDICT

```
NOT_SAFE_FOR_WRITE
```

Identity matching is reliable only for a subset. 24 records are confirmed A, but 10 are uncertain (C), 4 are existing-umbrella matches with granularity conflicts (B), and 2 are duplicate/invalid (E). 16 records therefore cannot be written without human adjudication. Independently, 8 groups of DB rows contain internal duplicates (263/335, 339/266, 265/336, 27/469, 329/271, 330/272, 331/269 and the seven-row Erasmus Mundus family), so even a correct research-to-row mapping is not always a correct write target. The prior pipeline is demonstrably unreliable - 4 of its 17 confirmed matches were wrong, it mapped two records into DB 335 and DB 337 through title and provider shortcuts, it merged two distinct FCT calls, and its own verification report claims field_updates_applied=28 while simultaneously reporting db_rows_updated=0 and db_rows_unchanged=691. A transactional write must not proceed until the C and B records are adjudicated, the DB duplicate groups are resolved, and write accounting is made verifiable.

### Conditions that would have to hold before a write is safe

1. Adjudicate all **10 C** records (name collisions, ambiguous target rows, retired targets).
2. Decide insert-vs-enrich for all **4 B** umbrella records (Camões ×3, ULisboa).
3. Resolve the **2 E** records: reject `research-017` (never-existed programme) and drop `research-060` as a
   duplicate of `research-036`.
4. Resolve the **8 DB-internal duplicate groups** — until 263/335, 339/266 and 265/336 are merged, a correct
   research→row mapping is not necessarily a correct write target.
5. Re-verify the **691-row count and 70-record count** at write time; both were re-verified here but the DB's
   mtime (2026-10-06 20:07:37) is later than the prior pipeline's run (14:07–14:26Z), so the prior results were
   computed against a different database state.
6. Make write accounting verifiable — the prior run's `field_updates_applied` figure cannot be reconciled with
   its own `db_rows_updated` figure.

A defensible narrow alternative: write **only the 24 class-A records**, under an explicit human-approved
manifest, with the DB held under a transaction and a verified row-count and checksum delta. That subset is not
the whole reconciliation, which is why this report returns `NOT_SAFE_FOR_WRITE`.

---

## Files

**Created (new only):**

| file | bytes |
|---|---|
| `research/premium_card/phase1_fresh_detail.json` | 618,458 |
| `research/premium_card/phase1_fresh_detail.md` | (this file) |

**Modified:** none.

**Not touched:** `reconciliation_report.json`, `merge_report.json`, `merge_verification_report.json`,
`research_manifest.json`, `backend/scholarzone.db`, all 24 timestamped DB backups, the 5 unstaged frontend
modifications, the 384 untracked entries.

```
database writes: 0
git mutations  : 0
```
