# Research Report — Global Study-to-Career Strategist (official evidence)

Status: **research-only, review-ready.** No corpus promotion, no UI, no merge, no deploy.
Branch/worktree: `feat/global-study-to-career-strategist` @ `C:\Users\GopaL\Desktop\Projects folder\ScholarZone-strategist` (master untouched).
Raw evidence artifacts: `backend/config/country_intelligence/research_raw/_global/002–005_*.json`.
Harvest/check date for all live lookups: **2026-10-12**.

Method note: internal `task` subagents are code-only (no live web access), so the fan-out ran as parallel live research waves (5 waves, ~26 focused official-source lookups across the launch matrix). Aggregator/employer/survey sites were excluded as substitutes for official statistics.

---

## 1. Waves and query topics
- **Wave 1** (`002`): Canada (Job Bank/StatCan LFS) for software / data-scientist / civil engineer; US (BLS) data-scientist + civil; Australia (JSA) software — revealed first gaps.
- **Wave 2** (`003`): US software (BLS); UK (ONS ASHE re-publishers); Ireland finest granularity (CSO) — first "no occupation-only" finding; Australia data-scientist.
- **Wave 3** (`004`): Germany (BA Entgeltatlas source identification); Netherlands (CBS StatLine 85517NED); New Zealand (aggrigators only in first pass).
- **Wave 4** (`005`): **primary extraction** — Germany Ingenieur/in-Bau BA median; Australia ANZSCO 4-digit class medians (2613, 2332); New Zealand Stats NZ HLFS ANZSCO dataset discovered (corrected); Ireland CSO Structure of Earnings broad-occupation confirmed; Netherlands CBS table confirmed + superseded.
- **Wave 5** (`005`): primary extraction — Germany Fachinformatiker BA median; Australia 2613 software class; US software (BLS, via 403-mitigated search lift); NZ major-group chart; NL CBS table stopgezet confirmed.

## 2. Verified facts with exact primary URLs (occupation-level salary)
Verification status: **✓ PRIMARY_VERIFIED**, **~ PENDING** (official source confirmed, exact cell not machine-extracted — do not promote), **✗ GAP** (official institution does not publish that granularity).

| Country | Subject | Occupation (code) | Value (gross) | As-of | Primary URL | Status |
|---|---|---|---|---|---|---|
| CA | CS/AI | Software developers & programmers (NOC 21232) | 48.08 CAD/h med | LFS 2023–24, wages upd. 2025-11-19 | jobbank.gc.ca wages-occupation/22548 | ✓ |
| CA | Data Science | Data scientists (NOC 21211) | 46.15 CAD/h med | LFS 2023–24 | jobbank.gc.ca wagereport/occupation/227147 | ✓ |
| CA | Civil Eng | Civil engineers (NOC 21300) | 48.56 CAD/h med | LFS 2023–24 | jobbank.gc.ca wagereport/occupation/22398 | ✓ |
| US | CS/AI | Software developers (SOC 15-1252) | 135,980 USD/yr med | OEWS May 2025 | bls.gov/ooh/.../software-developers.htm | ✓ |
| US | Data Science | Data scientists (SOC 15-2051) | 120,230 USD/yr med | OEWS May 2025 | bls.gov/ooh | ✓ |
| US | Civil Eng | Civil engineers (SOC 17-2051) | 100,840 USD/yr med | OEWS May 2025 | bls.gov/ooh/architecture-and-engineering/civil-engineers.htm | ✓ |
| DE | Civil Eng | Ingenieur/in-Bau (BA Berufsgattung, Expert) | 6,038 EUR/mo med (p25 4,932; p75 7,324) | Entgeltatlas 2025 | web.arbeitsagentur.de/entgeltatlas/beruf/58576 | ✓ |
| DE | CS/AI (vocational) | Fachinformatiker Systemintegration (BA Fachkraft) | 5,189 EUR/mo med | Entgeltatlas 2025 | web.arbeitsagentur.de/entgeltatlas/beruf/7817 | ✓ |
| DE | CS/AI (graduate) | Softwareentwickler/in (BA Expert) | — | 2025 | beruf/15260 | ~ |
| AU | CS/AI | Software & Applications Programmers (ANZSCO 2613) | 2,537 AUD/wk med | ABS SEEH May 2025 / LFS Feb 2026 | jobsandskills.gov.au .../2613 | ✓ |
| AU | Civil Eng | Civil Engineering Professionals (ANZSCO 2332) | 2,217 AUD/wk med | ABS SEEH May 2025 (2026-04-02) | jobsandskills.gov.au .../2332 | ✓ |
| GB | CS/AI | Programmers & software dev prof. (SOC 2134) | 56,914 GBP/yr med (FT) | ONS ASHE 2025 prov., Apr 2025 | ons.gov.uk ASHE Table 14 (xlsx) | ~ |
| GB | Civil Eng | Civil engineers (SOC 2121) | 51,366 GBP/yr med (FT) | ONS ASHE 2025 prov. | ons.gov.uk ASHE Table 14 | ~ |
| NL | CS/AI | Software & application developers (CBS 0811) | ~72,384 EUR/yr (6,032/mo @40h) | CBS 85517NED — **STOPGEZET 2026-08-18** | opendata.cbs.nl/.../85517NED | ~ (successor table) |
| NZ | CS/Civil | Professionals (ANZSCO major group) | 1,784 NZD/wk med (group, June 2025) | Stats NZ HLFS | stats.govt.nz / Aotearoa Data Explorer | ~ (group only) |
| IE | all | Professional occupations (1-digit SOC) | 32.99 EUR/h med (2022) | CSO SES 2022 Table 4.2 | cso.ie SEM 2022 | ✗ (broad only) |

**Cross-check note (US):** bls.gov returned HTTP 403 to direct fetch (anti-bot); the figure is from bls.gov's own OOH/OEWS page content, lifted via search — primary publisher content, but a manual re-open of the page is advised before final copy.

## 3. Occupation mappings verified (a degree ≠ one occupation)
- US: SOC 15-1252 / 15-2051 / 17-2051 (BLS OEWS). Single occupations, wage-and-salary only.
- CA: NOC 21232 / 21211 / 21300 (Job Bank; underlying StatCan LFS). Regional SAE rows excluded as ESTIMATE.
- GB: SOC 2020 2134 / 2121 (ONS ASHE, 4-digit). ASHE suppresses tiny cells (no estimation).
- DE: BA **Berufsgattung** (occupation-CLASS) medians; splits Fachkraft (vocational) vs Expert (academic) tracks — a CS Master's maps to the Expert track (figure pending).
- AU: ANZSCO **4-digit unit group** (2613, 2332). The 6-digit roles (261313, 233211) publish earnings **N/A**, so only the class level is usable. **Data Science has no clean 4-digit class** (6-digit OSCA 223234 N/A; 2241 Mathematicians is not data-science-specific → excluded).
- NL: CBS occupation hourly-wage **median by occupation class**; table superseded 2026-08-18.
- NZ: Stats NZ HLFS earnings by ANZSCO, but accessible granularity is the **1-digit major group**; detailed occupations not surfaced.
- IE: finest earnings granularity is **1-digit broad SOC** (professional); no detailed occupation.

## 4. Cells completed / pending / officially unavailable (launch matrix)
- **Completed (primary-verified, occupation-level):** CA×3, US×3, DE-civil, AU-CS, AU-civil.
- **Pending (official source confirmed, exact cell to be read):** DE-CS(expert), GB-CS, GB-civil, NL-CS (successor table), NZ-CS/civil (detailed, group level verified).
- **Officially unavailable / not sourced at subject level → "Insufficient data":** IE×3 (broad-occupation only), AU-Data-Science, DE-Data-Science, GB-Data-Science, NL-civil/data (not yet read).

## 5. Defensible launch selection (≥6 countries, ≥3 subjects)
- **Six best-covered countries by the number of PRIMARY-verified subject cells:** US (3/3), CA (3/3), DE (2/3 + CS-pending), AU (2/3: CS, civil), GB (2/3 pending primary confirm), NL (1/3 pending). **Ireland is best-covered for non-salary but has NO subject-level pay** — the strategist must show its career-pay as "Insufficient data", which is itself a test of the degradation path.
- **Three subjects:** Computer Science/AI, Data Science, Civil Engineering. CS and Civil have the widest official coverage; Data Science is thinner (US/CA only officially) and is handled by graceful "Insufficient data".
- The feature must show, per country, both the salary cell status AND whether it is a single-occupation vs occupation-CLASS figure.

## 6. Conflicting definitions / values found
- **Occupation vs occupation-class** (US/GB single SOC vs DE/AU/NL class). Flagged, not merged.
- **Period/unit** monthly (DE) vs weekly (AU/NZ) vs annual/hourly (US/GB); annualisation is a derivation to be flagged, not silently applied.
- **Basis** gross everywhere; none net — no cell supports take-home.
- **German track split** (Fachkraft vs Expert) and **social-insurance ceiling** (BBG) caveat; self-employed/civil servants excluded.
- **NL source superseded** (85517NED stopgezet 2026-08-18) — a refresh needed.

## 7. Non-salary evidence (tuition, living, scholarships, visa, funds, work rights, post-study, permits, PR, citizenship, language)
**Already present and validated** in the audited corpus (`backend/config/country_intelligence/*.json` → `education_costs`, `living_costs`, `residency.*`, `scholarship_landscape`) for all 17 countries with `Claim`/provenance, official `source_type`, `as_of`, and source URLs. Re-researching 17×N cells was **not** repeated because it already carries provenance. Residual action (deferred to a short verification wave): confirm the embedded official URLs are still live for the six launch countries, and confirm no informational pathway is worded as a guarantee. Where a residency step is absent for a country it is shown as "Insufficient data", per the contracts.

## 8. BDT conversion methodology
- **Authoritative source:** Bangladesh Bank reference rate, **USD/BDT = 123.2254, dated 2026-10-11** (`https://www.bb.org.bd/`). ECB (the corpus FX source) does **not** publish EUR/BDT, so BDT is stored as a **separate, separately-sourced, separately-dated** artefact.
- **Composition:** original currency → USD via the ECB table (as_of 2026-10-02), then USD → BDT via the Bangladesh Bank rate (as_of 2026-10-11). Both legs, both dates, both publishers published with the figure; either leg missing ⇒ BDT refused (shown as unavailable), never assumed/parity.
- **Limitation reported:** for currencies not in the ECB table there is no bridge, so BDT is unavailable for those figures (never invented).

## 9. Proposed TOPIC_PATHS / schema changes (reviewed change, with tests)
The corpus stores career pay only at country level and explicitly records "no subject-level figure". To surface occupation-level salary safely I propose adding a **new, optional section** `career.occupation_salary` (keyed by occupation slug, each value a full `Claim` with `value_status`, `basis: gross`, `as_of`, `source_id`s, `unit`, `metric`, `granularity` and optional `employment`/`demand`), **not** a bulk overwrite of existing cells. Because promotion requires a reviewed mapping edit (per the corpus docstring), ingestion is **out of scope for this research phase**.
Tests required before promotion: (a) ungranularity guard — a value with `granularity ⊅ occupation-level` cannot be stored under `occupation_salary`; (b) AGGREGATOR/CROWDSOURCED `source_type` refused for a salary claim; (c) gross-only (no `basis: net` accepted for occupation salary); (d) metric/unit required; (e) stale-after threshold + re-verify warning; (f) unit test that a missing/stale BDT leg yields "unavailable", never a number.

## 10. What I could NOT access (explicit)
- **bls.gov** direct fetch: HTTP 403 anti-bot (used publisher content via search; recommend manual re-open).
- **ONS ASHE Table 14**: xlsx download, not machine-readable here → GB figures are cross-checked-but-primary-pending.
- **BA Entgeltatlas expert software / detailed entries**: JS-rendered; exact expert cell not extracted (DE-CS expert pending).
- **NZ detailed occupation earnings**: accessible chart surfaces major-group only; detailed occupations (software/civil) not extractable without the Aotearoa Data Explorer UI.
- **CBS successor table**: 85517NED discontinued; successor table not yet read (NL figures need refresh).
- Ireland detailed-occupation earnings: confirmed not published (not an access failure).

No fabricated figures, no claimed verification that was not actually observed, and no aggregator value is presented as official.
