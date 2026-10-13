# Strategist Phase 0 Audit — "Global Study-to-Career Strategist"

Audited against `origin/master` at `eae054c` (Merge PR #46, bangladesh-applicant-journey).
Worktree: `C:\Users\GopaL\Desktop\Projects folder\ScholarZone-strategist`
Branch: `feat/global-study-to-career-strategist`.

This is an **integration audit**. The verdict up front: the repository already
contains most of the raw material for this feature, and it is unusually rigorous
about data integrity. The strategist is therefore assembled out of the existing
Country Intelligence plane, the existing Match taxonomy, and the existing
Bangladesh-Journey money/i18n primitives. Backend code is added **only** for
gaps verified below, each with a justification. No existing schema, endpoint,
corpus file or test is modified except where a change is required and reversible.

---

## 1. Country Intelligence plane — EXISTS, reused wholesale

`backend/app/services/country_intelligence/`

- `corpus.py` — loads and validates a curated JSON corpus at
  `backend/config/country_intelligence/*.json`. **17 countries**: AT, AU, CA, CH,
  DE, FI, FR, GB, IE, IT, JP, NL, NZ, PL, SE, SG, US. One malformed file excludes
  that country with a reason and never takes the corpus down. Files, not tables,
  by explicit design (no Alembic; production refuses to migrate).
- Each country carries sections: `education_costs`, `living_costs`,
  `one_time_costs`, `career`, `residency`, `quality_of_life`,
  `scholarship_landscape`. Every figure is a **Claim** with a `value_status`,
  optional sources, `as_of`, `basis` (gross/net), range, formula, freshness.
- `service.py` — `country_summaries`, `country_detail`, `compare_countries`,
  `calculate_cost`, `intelligence_meta`.
- `derive.py` — `derive_tuition`, `derive_living`, `derive_one_time_total`,
  `derive_total_investment`, `derive_break_even` (refuses gross income),
  `derive_roi`; every function returns a `Derivation` and **refuses rather than
  approximates**. This is exactly the integrity posture the feature requires.
- `net_income.py` — a net (take-home) figure must declare the circumstances it
  holds under (tax year, population, residency, contributions); gross is refused
  for break-even.
- `catalogue.py` — the **measured** plane: live per-country scholarship counts
  from the DB via the single public-visibility predicate. Reused for funding
  reality and coverage.
- `fx.py` — sourced, dated exchange rates (ECB, base EUR). `convert()` refuses
  any currency not in the table; never assumes parity.
- `formulas.py`, `taxonomy.py`, `provenance.py`.

**Residency coverage (verified per file):**

| Country | student permit | post-study job-seeker | work permit (EU Blue Card) | PR route | citizenship | career | cost |
|---|---|---|---|---|---|---|---|
| DE | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ |
| GB | – | ✔ | – | ✔ | – | ✔ | ✔ |
| IE | – | ✔ | – | ✔ | – | ✔ | ✔ |
| NL | – | ✔ | – | ✔ | ✔ | ✔ | ✔ |
| CA | – | ✔ | – | ✔ | – | ✔ | ✔ |
| AU | – | ✔ | – | ✔ | – | ✔ | ✔ |
| NZ | – | ✔ | – | ✔ | – | ✔ | ✔ |
| FR | – | ✔ | – | ✔ | ✔ | ✔ | ✔ |
| CH/JP/SG/AT/PL/SE/IT/FI | thin | varies | – | partial | – | partial | ✔ |
| US | – | – | – | – | – | – | ✔ |

Gaps here are **data**, not code, and are surfaced as "Insufficient data" rather
than filled.

---

## 2. `POST /v2/countries/compare` — EXISTS, extended (not rewritten)

`routers/countries.py` → `service.compare_countries`. A comparison matrix across
the countries that can answer, quoted in their own currencies:
- A row nobody can answer is dropped with a reason (never a row of zeros).
- A mixed-currency row is either converted through a **sourced** rate (published
  with rate, date, direction) or **refused** with the currencies named.
- `winner_policy`: no winner declared. `ranking_rule` published.
- `max_compare_countries = 6` already enforced in the router.

**Missing for the strategist:** the existing comparison is country-vs-country on
cost/living/salary rows. It has no subject dimension, no funding-model override,
no BDT conversion, no pathway timeline, no evidence-completeness meter, no
weighted priorities and no "why recommended / why excluded" narrative. Those are
added in the strategist service, which *calls into* this plane rather than
duplicating it.

---

## 3. Cost calculation engine — EXISTS, reused

`POST /v2/countries/calculate` → `calculate_cost` → `derive.py`. Refuses totals
when inputs are missing, keeps tuition (annual), living (annual), one-time,
break-even (needs net income) and ROI separate and named. The zero rule is
already enforced: a "sourced zero" whose only source is unarchived is published
as UNKNOWN so the total refuses (Germany bachelor tuition is the worked example).
Reused verbatim for per-country cost breakdown + funding reality.

## 4. Match engine / subject taxonomy — EXISTS, reused

`services/matching/taxonomy.py` — `CANONICAL_FIELDS` (incl. `computer_science`,
`data_science`, `civil_engineering`), `resolve_field`, `resolve_field_by_key`,
`resolve_scholarship_field`, `relate_fields`, `known_field_keys`. The catalogue
stores no normalised subject; the taxonomy maps free text to a canonical field
and returns UNRESOLVED when nothing matches. This is the subject dimension and
the rule-5 (link scholarship → subject only when the record explicitly supports
it) mechanism. Reused. The Match HTTP plane (`routers/match.py`, `services/match`)
is for scholarship matching, not country strategy, and is left untouched.

## 5. Scholarship catalogue — EXISTS, reused; **no subject column**

`app/models.py` `Scholarship`: `country`, `degree` (required), `funding` (label),
plus structured economics `funding_amount/currency/period`, `tuition_coverage`,
`living_cost_coverage`, `travel_coverage`, `fully_funded`. Field/subject lives in
`program_type` (+ `official_details`), resolved through the Match taxonomy. There
is **no dedicated subject column and no subject-level salary/demand anywhere**.
Verified: the corpus `career` section publishes only country-level figures and,
for Germany, explicitly records that "no subject-level figure" exists.

**Gap (data, not code):** No subject-level demand/salary for any country × subject.
Per the non-negotiable rule #4 this must never be inferred from country averages.
The strategist therefore renders subject-level career pay/demand as
**"Insufficient data — not sourced at occupation level"** and lists the gap in
the admin report. Nothing is fabricated.

## 6. career / residency / work-permit / citizenship data — EXISTS, reused

Residency sections carry, per country, structured claims for the pathway:
`student_residence_permit.duration`, `job_seeker_residence_permit.duration`
(post-study), `eu_blue_card` (work permit incl. salary thresholds),
`permanent_residence.*` (routes), `citizenship.*` (residence years, language,
dual). Not every country has every step; each present step already carries
`source_ids`, `as_of`, notes. The strategist assembles these into the pathway
timeline and marks absent steps "Insufficient data".

## 7. Provenance / source freshness / value_status contracts — EXISTS, reused

`provenance.py`: `VALUE_STATUS` (OFFICIAL_*, UNIVERSITY_OFFICIAL,
INSTITUTIONAL_REPORT, CROWDSOURCED, AGGREGATOR, ESTIMATE, DERIVED, CONFLICTING,
UNVERIFIED, REFUSED, UNKNOWN), `FRESHNESS` (CURRENT/STALE/UNDATED),
`DEFAULT_STALE_AFTER_DAYS = 730` (configurable, pure function of the reference
date), `resolve_freshness`, `Claim.to_dict`. The check that a secondary source
can never be labelled official is enforced at load. UNKNOWN carries a mandatory
reason; CONFLICTING preserves each side; REFUSED is distinct from UNKNOWN.
Reused unchanged; the strategist surfaces `freshness` and source links on every
step.

## 8. `current /countries UI` — EXISTS

`frontend/src/pages/CountryPage.jsx` (and `ComparePage.jsx`) render the country
grid using `countryImages`, `countryThemes`, measured counts via
`fetchScholarships`. This is the current, working surface. The strategist is a
**new, separate, flag-gated route** and does not disturb it.

## 9. Cross-cutting frontend primitives — EXISTS, reused

- Feature flag pattern: `features/<name>/index.js` exports `enabled`; `App.jsx`
  renders routes/nav only when true (`consistency-auditor` is the reference).
- Lazy loading: `React.lazy` + `Suspense` fallback (`journey` is the reference).
- i18n: `features/journey/i18n/{strings.js,useJourneyI18n.js}` with modes
  `bn` / `en` / `both`, Bangla digits normalisation, `bn-BD` / `en-GB` locale.
- Money: `features/journey/lib/money.js` — `normalizeAmount`,
  `normalizeBanglaDigits`, `amountToNumber`, `convertToBdt` (never falls back to
  a remembered rate), `sumAmounts`. Reused for BDT formatting.

---

## What is MISSING (verified) and what we ADD, with justification

| # | Gap | Where | Addition | Why code (not config) |
|---|---|---|---|---|
| A | No BDT exchange rate exists anywhere; the ECB table (verified) does not publish BDT, and BDT display is a core requirement. | `fx.py`, corpus fx dir | Curated, dated, separately-sourced **Bangladesh Bank** reference rate (`fx/bdt.json`) + a composed `to_bdt` helper in `fx.py` that publishes both sources/dates and refuses when either leg is absent. | A sourced rate with provenance cannot be invented at render time; but it needs an auditable artefact + a conversion path that never assumes a rate. Existing single-source `FxTable` is unchanged. |
| B | No unified subject × degree × funding × country decision experience combining the above with pathway timeline, evidence completeness, weighted priorities, why-explained. | new | `services/strategist/` — a pure, side-effect-free service that reads the corpus + measured plane and composes the plan, ranking, pathway and explanations. | This is the feature itself. It reuses the plane (never re-implements counting/derivation/provenance) and keeps every separation the contracts enforce. |
| C | No way to request that plan over HTTP. | new | `routers/strategist.py` (stateless), + `GET /v2/strategist/subjects`, `GET /v2/strategist/coverage`, admin `GET /v2/strategist/gaps` (country × subject evidence matrix). Registered behind a feature flag. | Thin router, no business logic (matches `countries.py`). |
| D | No feature switch for the strategist. | `core/config.py` | `strat_enabled` setting, default **OFF** (`SCHOLARZONE_STRATEGIST_ENABLED`); router registered only when on. | Mirrors existing flag discipline (`supervisor_discovery_enabled`); ships inert. |
| E | No admin view of which country × subject pairs lack evidence. | `strategist` service | Gap report derived from the coverage matrix. | Research prioritisation is an explicit deliverable. |

Everything else is reuse. Backend additions are additive; no migration is
introduced (verified: the corpus is files, and `main.py` production startup
refuses to migrate). Backward-compatible and reversible: the strategist routes
are new paths behind a default-OFF flag, so the change is inert by default and a
revert is a single route/flag removal.
