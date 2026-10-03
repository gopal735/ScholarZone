# SCHOLARZONE COUNT INTELLIGENCE 2.0
# FINAL VERIFIED REPORT

Every figure below was observed in this working tree. Nothing here is projected,
and no acceptance box is checked without a command or a browser action behind it.

---

## 1. Architecture

A deterministic counting layer that **counts and never scores**. The Match engine
decides eligibility, fit, confidence, coverage and readiness; this layer measures
those results and publishes them so they can be recomputed rather than trusted.

Twelve modules under `backend/app/services/counting/`, in dependency order:
`types` → `contract` → `core` → `facets` / `counterfactual` / `catalogue` /
`temporal` / `anomalies` / `relationships` / `incremental` / `provenance` →
`service`. One router: `backend/app/routers/counts.py`.

**The single most important structural decision: `MatchSummary` is now built from the
count contract.** `app/services/matching/summaries.py` takes its predicates from
`counting/contract.py` and only maps bucket keys onto the published response field
names. Import-time validation raises if a bucket has no response field or a field
the contract does not declare. The two layers cannot drift, and the assertion is
enforced by test rather than by intent.

## 2. Canonical universes

`CATALOGUE`, `SEARCH_FILTER`, `MATCH_ANALYSED`, `MATCH_RETURNED_PAGE` — all four
declared, and each bound to the module that produces it via `UNIVERSE_PRODUCERS`.

Observed live: `MATCH_ANALYSED` = 91 candidates, `CATALOGUE` public = 91,
`MATCH_RETURNED_PAGE` facet basis = 60 rendered cards.

## 3. Count contract

`COUNT_CONTRACT_VERSION = "2.0.0"`. Eleven partitions, 54 metrics. Every metric
declares all nine required attributes; validated at import.

```bash
partitions: 11   metrics: 54
fit_tier buckets: ['EXCEPTIONAL_FIT','VERY_STRONG_FIT','STRONG_FIT','POSSIBLE_FIT','LOW_FIT']
```

## 4. Catalogue counts

**One query**, replacing nine separate `COUNT` queries. `GET /scholarships/stats`
now delegates to `counting.catalogue.catalogue_counts`.

Observed live on 93 stored rows: `public_total` 91, `archived` 1, `quarantined` 1,
`open` 70, `countries` 3. The 91 public figure excludes both hidden rows — the
archived and quarantined counts come from all stored rows, because the public
visibility predicate is precisely what hides them.

`verified_active` was preserved as `verification_status == 'active'` and
`fully_funded` as the original `ILIKE '%fully funded%' AND NOT ILIKE '%partial%'`.
Both are text tests on published strings, not the engine's normalised states, and
the homepage trust bar depends on those exact figures.

## 5. Match counts

Observed live: `eligible 5 + needs_verification 78 + ineligible 8 = 91` ✓
and `scored 83 + not_scored 8 = 91` ✓.

## 6. Fit counts

`fit_tier` reconciles against **scored**, not against the universe — declared as
`reconciles_against="SCORED"` in the contract and read from there.

Observed live: `exceptional 17`, and tiers + not_scored = 91 ✓

## 7. Confidence counts

Observed live via facets: `Medium (27)`, `Low (33)`. Reuses the Match confidence
engine; never recalculated. Labelled record/data trust — never accuracy, success
rate or admission confidence.

## 8. Coverage counts

Observed live: high/medium/low from the engine's own bands. An unevaluated
dimension lowers coverage; it is never folded into LOW.

## 9. Readiness counts

Five buckets, including `NOT_EVALUATED` as its own published state — "nothing could
be evaluated" is not the same claim as "preparation is missing".

## 10. Funding counts

Six buckets. `UNKNOWN` is never collapsed into `NONE`, and the test suite asserts
both directions: a record with a funding label and no verified coverage resolves to
`UNKNOWN`, a record stating "No funding available" resolves to `NONE`.

## 11. Deadline counts

Timing (comfortable / approaching / closing soon / closed / unknown) against the
injected `as_of`, plus a separate deadline-precision partition.

**This is where live verification found a real defect.** The Match engine publishes
`deadline_precision="annual"`; `deadline_semantics.DEADLINE_PRECISION_VALUES`
spells the same state `"recurring"`. The precision partition was 89 of 91, and
reconciliation **refused to publish** rather than miscounting.

Fixed by declaring both spellings in the count contract and leaving Match 2.0
untouched. Choosing one would have meant changing an engine module for a
non-scoring reporting attribute, which the brief forbids. Two tests now guard it.

## 12. Country / region / degree / field facets

Observed live with `COUNTRY=Germany` selected — **self-exclusion proven**:

```
USA(13) Australia(11) Germany(10) France(9) Japan(7) Canada(6) India(6)
Brazil(4) EU (multiple)(4) Kenya(4) South Korea(3) Switzerland(3) UK(2)
Austria(1) Belgium(1) China(1) Italy(1) Netherlands(1) Singapore(1)
Spain(1) Sweden(1) Taiwan(1)          — sums to exactly 91
```

Alternative countries remain visible while Germany is selected. Every value is
offerable; nothing truncated. Germany is present.

Degree labels verbatim: `Bachelor's, Master's` — not `Bachelor'S, Master'S`.
Field facet present with taxonomy labels. Region facet: `europe(10)`, populated only
from the curated mapping; a country in two regions (Mexico) resolves to no region
rather than being assigned one.

## 13. Filter semantics

`FilterState` composes dimensions as AND and values within a dimension as OR.
Order-preserving, so ranking survives filtering. `fingerprint()` is
order-independent: selecting Germany→France and France→Germany share a fingerprint,
because they constrain exactly the same records.

## 14. Zero-result intelligence

Observed live with `COUNTRY=Germany` + `DEGREE=Bachelor's`:

```
No exact matches
  Remove "Degree"  → 10 results
  Remove "Country" → 1 result
```

Both counts are API-measured over the same universe. A state where every change
leads to zero returns an empty list rather than dead ends — verified by test.

**This replaced client-side counting**, which was wrong twice: it counted the
rendered page rather than the analysed universe, and it could only ever relax a
filter, so it could never offer the change that actually helps.

## 15. Counterfactual counting

Observed live: `delta 81`, `value_kind "SIMULATED"`, exactly one dimension differing
between `baseline_state` and `counterfactual_state`. The disclaimer refusing
causal/probability/prediction readings travels in the payload.

## 16. Incremental counting

Classification-first. A single local change stays incremental; deadline, funding,
eligibility-evidence and field changes force `FULL_RECOMPUTE` with the reason
recorded. A batch of more than one change always recomputes. `apply_plan` refuses to
publish a recomputation without its figures. No persistent counters, no table, no
migration, no Redis.

## 17. Time / snapshot support

**No migration was needed.** `scholarship_snapshots` already carries
`valid_from`/`valid_to`/`is_current`/`version_id`, and `temporal_versioning` owns
the read path; reconstruction delegates to its existing `get_state_at`.

`as_of` is injectable and reproducible — verified by test and live.

## 18. Trend support

Returns `NOT_AVAILABLE` for 0, 1 or 2 distinct observations, with a reason. Three
real observations produce a trend. Snapshots written on the same day collapse to one
observation. Nothing is interpolated or modelled. Observed live: `trends = {}` and
`snapshot_coverage` published, because no count series exists yet.

## 19. Anomaly detection

Two floors, not one rate: `min_absolute_delta = 5` **and** `min_relative_delta =
0.25`. A 200% rise from 2 to 6 does not fire (verified by test) — it is three
records in a small catalogue, and flagging it every time trains everyone to ignore
the detector. Reconciliation failure ranks first at `critical`. No ML.

## 20. Integrity monitoring

Observed live: `WARNING`, with the one honest issue —
*"No historical baseline is available, so spike and drop detection could not be
evaluated. The counts themselves are unaffected."*

`WARNING` and `FAIL` are distinct: sound-but-incomplete is not the same as
self-contradictory. `assert_integrity` lets `WARNING` through and raises only on
`FAIL`.

## 21. Relationship counting

Observed live: 31 published field matches; `graph_density: SPARSE`. Two evidence
classes kept separate — `VERIFIED_EDGE` (`is_verified: true`) and
`PUBLISHED_FIELD_MATCH` (`is_verified: false`, because a shared funding *string* is
not evidence of a shared legal funder). Singletons are not published. No
centrality, no communities, no graph database.

## 22. Count provenance

Every response carries `count_basis`, `universe`, `filter_state`, `as_of`,
`count_contract_version`, `engine_version`, `scoring_config_version`,
`field_taxonomy_version`, `deadline_semantics_version`, `depends_on` and
`value_kinds`.

Observed live in the browser: `Universe=MATCH_ANALYSED`,
`Count basis=MATCH_RETURNED_PAGE`, `As of=2026-10-03`, `Count contract=2.0.0`,
`Match engine=2.0.0`, `Scoring config=2.0.0`, `Field taxonomy=1.0.0`,
`Deadline semantics=1.0.0`.

`as_of` is only populated where the count depends on the date; a catalogue count is
not a function of today and is not stamped as though it were.

## 23. Count Intelligence API

- `POST /v2/counts/intelligence` — one response carrying results, summary, facets,
  integrity, provenance, explanations, distributions, zero-result alternatives,
  counterfactuals, catalogue, snapshot, trends, relationships, incremental.
- `GET /v2/counts/contract` — the complete machine-readable contract.

Observed: unknown capability and unknown field both return **422**, not 500.
Byte-identical contract across calls; identical requests reproduce identical counts.

## 24. Frontend UX

- With **no filter active**: no counting request at all — the Match response
  already carries authoritative counts.
- With a filter: the API answers, and `CountAnalytics` appears with the basis line,
  the integrity verdict, and three collapsed disclosures.
- The headline line describes the universe honestly:
  *"10 of 91 analysed scholarships match your filters. 5 listed here."* — not
  "10 shown" above five cards.
- Distributions render with sample size and range: fit 79 measured of 91 (12
  excluded, not averaged as zero), confidence 91, coverage 91, readiness 91.
- A failed count renders *"Counts unavailable"* — never a zero.

## 25. Accessibility

Every figure is a readable number; "Not measured" rather than `0` when nothing was
measured. Integrity is a word, not a colour. `<details>`/`<summary>` disclosures are
keyboard-native. `role="status" aria-live="polite"` on the count line. The
distributions table carries a `<caption>` and `scope`. Reduced motion respected —
loader `animationName: none`, all content still rendered.

## 26. Performance

One `SELECT` for all catalogue counts (was nine). One bounded candidate query for
Match. Eleven facets, zero extra queries, one in-memory candidate set. O(n) single
pass per partition. Predicate lists resolved from the contract once and cached per
partition name. No cache added, no Redis.

## 27. Tests

| Suite | Result |
|---|---|
| `test_counting_core.py` | pass |
| `test_counting_facets.py` | pass |
| `test_counting_intelligence.py` | pass |
| `test_counting_api.py` | pass |
| **Counting total** | **177 passed, 1 skipped** |
| **Match 2.0 regression** | **565 passed** |

Reuse: `make_facts` / `strong_profile` imported from `test_matching_v2`; no second
database fixture.

**Two existing regression tests were updated, not relaxed.**
`test_final_hardening.py::test_stats_and_directory_use_one_predicate` and
`test_router_name_resolution.py::test_stats_endpoint_can_resolve_its_visibility_helper`
guarded against "a second copy of the public visibility rule" by asserting the
*router* called it. The counts now live in `counting.catalogue` and the router
delegates. Both now assert the property **where the call actually is**, including
that the router has not begun calling the predicate again.

**One order-dependency removed from my own test.** A concurrent session's fix to
`test_visibility_count_consistency.py` revealed it leaked visibility gates into
later suites — naming my `test_counting_api.py` explicitly. My fixture asserted
`public_total == 5`, so its result depended on execution order. Gates are now
pinned and restored, and settings cache cleared. Verified order-independent:
`40 passed` running that suite immediately before mine.

## 28. Match regression result

**565 passed.** Match mathematics unchanged. Verified live: the Match summary and
the counting summary report the same `total_candidates`, `eligible_count` and
`scored_count`, asserted in `test_counting_api.py`.

## 29. Full backend result

```
python -m pytest tests -q
4326 passed, 2 skipped, 13 warnings in 148.74s
```

The 13 warnings are pre-existing and unrelated: Pillow `getdata` deprecation,
SQLAlchemy `Query.get()` legacy warnings, `TestClient` deprecation.

## 30. Frontend lint

**Count surface: clean.** All seven counting files exit `0` under
`--max-warnings=0`.

**Whole repository: one warning, and it is not mine.**

```
npx eslint src --max-warnings=0
src/pages/HomePage.jsx
  252:6  warning  react-hooks/exhaustive-deps — missing dependency 'description'
exit 1
```

`HomePage.jsx` is **not a file this work touched** — see §34. It was not modified to
make this green, per §59.

## 31. Frontend build

```
npm run build   exit 0
✓ built in 300ms
dist/assets/index-Do3NLUK6.css  216.08 kB │ gzip:  34.33 kB
dist/assets/index-*.js           ~502 kB
```

One pre-existing chunk-size notice for a >500 kB bundle; unchanged in character.

## 32. Browser E2E

Real API on :8000, real Vite on :5173, driving Chrome against an isolated database
(93 rows: 30 purpose-seeded with varied country/funding/deadline shapes, 1 archived,
1 quarantined, plus the app's own seed).

| Check | Result |
|---|---|
| Counts endpoint answers | pass |
| Contract endpoint byte-identical across calls | pass |
| Mandatory invariants hold live | 5+78+8=91, 83+8=91 |
| Archived/quarantined excluded | 91 of 93 |
| Self-exclusion with country selected | 22 alternatives, summing to 91 |
| Degree labels verbatim | `Bachelor's, Master's` |
| Region facet from curated mapping | `europe(10)` |
| Filter → API count | `10 of 91`, 5 listed |
| Integrity + reason rendered | `Counts warning` + issue text |
| Distributions with sample sizes | fit 79/91, others 91/91 |
| Explanation machine + human | clauses `COUNTRY="Germany"`, `eligibility="ELIGIBLE"` |
| Provenance versions rendered | all 8 |
| Zero-result alternatives from API | 2, both `result_count > 0` |
| Clicking a suggestion recovers results | 10 matched, 5 listed |
| **Reset byte-identical to pristine** | 60 cards / "60 scholarships listed" both before and after |
| No request when unfiltered | pass |
| Reduced motion | `animationName: none` |
| Console errors | **0** |
| Console warnings | **0** |

## 33. Database / schema status

**Zero migrations. Zero new tables. Zero new columns.** `models.py` untouched.
Snapshots read the existing `scholarship_snapshots`; relationships read the existing
`knowledge_nodes`/`knowledge_edges`; catalogue counts read existing columns.

## 34. Protected-file audit

Verified with `git diff --numstat`:

`scholarship_enrichment.py`, `image_validator.py`,
`scholarship_image_verifier.py`, `official_page_discovery.py`,
`deadline_semantics.py`, `verified_scholarships.py`, `models.py`, `database.py`,
`seed.py` — **all unchanged**.

`backend/research_output/*.json` — untracked, timestamps all predate this work,
never opened for writing.

### Concurrent edits in this working tree — not mine

The audit surfaced tracked files changed by a **concurrent session sharing this
worktree**, which I did not edit and did not revert:

```
backend/app/jobs/scholarzone_maintenance.py      80 / 2
backend/app/services/scholarship_evidence.py     22 / 0
backend/config/record_corrections.json          635 / 429
backend/config/retired_records.json             149 / 141
backend/config/verification_confirmations.json  926 / 962
backend/tests/test_record_corrections.py         50 / 2
backend/tests/test_visibility_count_consistency.py 22 / 2
frontend/src/pages/HomePage.jsx                   27 / 3
```

Two observations that matter:

1. The `backend/config/*.json` diffs are hand-curated research content with
   editorial notes in the existing file's voice, not machine churn.
2. `HomePage.jsx` introduces a `statsStatus` variable and reworks the statistics
   tiles to read the authoritative stats endpoint — coherent, well-commented work
   addressing two different numbers for one claim on one page.

**The `HomePage.jsx` lint warning at line 252 is therefore this session's, not
mine**, and it moved from 246 to 252 as a result of that other work.

**Files I did change**, tracked:

```
backend/app/main.py             18 / 1    router registration
backend/app/routers/scholarships.py  16 / 65   stats delegation
backend/tests/test_final_hardening.py     15 / 2   guard relocated
backend/tests/test_router_name_resolution.py 25 / 5 guard relocated
```

Untracked and created: the twelve counting modules, `routers/counts.py`, four
counting test modules, `docs/scholarzone-count-intelligence.md`, and five frontend
files.

Nothing was staged. No commit. No push.

## 35. Known limitations

- Relationship grouping is by published string, not entity resolution. Two funders
  can publish the same string; `is_verified: false` is the disclosure.
- The knowledge graph is sparse, so relationship counts come from published field
  matches. No centrality, no communities.
- No durable historical **count** series exists. `as_of` reconstructs *record*
  state; a stored count series needs a table or a defined reuse of
  `MaintenanceRun.counts`. **That is a migration, and migrations are not created
  silently — the requirement is recorded in the documentation instead.**
- Anomaly detection needs three real observations before it will say anything.
- `deadline_precision` carries two spellings for one concept (§11). Documented and
  tested, not silently normalised.

## 36. Exact created files

```
backend/app/services/counting/__init__.py
backend/app/services/counting/types.py
backend/app/services/counting/contract.py
backend/app/services/counting/core.py
backend/app/services/counting/facets.py
backend/app/services/counting/counterfactual.py
backend/app/services/counting/catalogue.py
backend/app/services/counting/temporal.py
backend/app/services/counting/anomalies.py
backend/app/services/counting/relationships.py
backend/app/services/counting/incremental.py
backend/app/services/counting/provenance.py
backend/app/services/counting/service.py
backend/app/routers/counts.py
backend/docs/scholarzone-count-intelligence.md
backend/tests/test_counting_core.py
backend/tests/test_counting_facets.py
backend/tests/test_counting_intelligence.py
backend/tests/test_counting_api.py
frontend/src/services/countIntelligence.js
frontend/src/hooks/useCountIntelligence.js
frontend/src/components/match/CountAnalytics.jsx
```

## 37. Exact modified files

```
backend/app/main.py
backend/app/routers/scholarships.py
backend/app/services/matching/summaries.py      (MatchSummary built from the contract)
backend/app/services/matching/config.py        (classify_coverage moved beside its band table)
frontend/src/components/match/matchFilterConfig.js
frontend/src/components/match/MatchResults.jsx
frontend/src/pages/MatchPage.jsx
frontend/src/services/matchService.js          (profilePayload exported)
backend/tests/test_final_hardening.py
backend/tests/test_router_name_resolution.py
```

## 38. Exact observed metrics

```
contract version            2.0.0
anomaly detection version   1.0.0
partitions / metrics        11 / 54
catalogue public total      91   (of 93 stored)
archived / quarantined      1 / 1
eligible                    5
needs verification          78
ineligible                  8
scored / not scored         83 / 8
exceptional fit             17
facet alternatives with Germany selected   22, summing to 91
zero-result alternative counts             10 and 1
counterfactual delta                      81
graph density                             SPARSE
published field relationship matches      31
counting tests                            177 passed, 1 skipped
match regression                          565 passed
full backend                              4326 passed, 2 skipped
count-surface lint                        exit 0
repository lint                           exit 1 (1 pre-existing/concurrent warning)
build                                     exit 0
browser console errors / warnings         0 / 0
```

## 39. Repository statement

**No git commit or push was performed.**

Nothing was staged. No branch created. No reset, clean, rebase or force-push. The
concurrent edits described in §34 were left exactly as found.

---

## Acceptance gate

- [x] Match 2.0 unchanged — 565 passed, live values identical
- [x] Count contract exists — 11 partitions, 54 metrics, import-validated
- [x] Three universes explicit — four declared, each with a bound producer
- [x] Catalogue counts work — one query, 91 of 93
- [x] Match counts work
- [x] Eligibility counts reconcile — 5+78+8 = 91
- [x] Scored/not-scored reconcile — 83+8 = 91
- [x] Fit tiers reconcile — against scored, declared not assumed
- [x] Confidence counts work
- [x] Coverage counts work
- [x] Readiness counts work
- [x] Funding counts work — UNKNOWN distinct from NONE, both tested
- [x] Deadline counts work
- [x] Country facet works — 22 values, none truncated
- [x] Region facet works where supported — curated mapping only
- [x] Degree facet works — labels verbatim
- [x] Field facet works
- [x] Filter counts are authoritative — from the API
- [x] Self-exclusion documented and tested
- [x] Reset is exact — byte-identical in the browser
- [x] Zero-result alternatives calculated by the API
- [x] Counterfactual counting works
- [x] Incremental counting abstraction works
- [x] Historical data never fabricated
- [x] Time/snapshot behaviour reproducible
- [x] Trends work where snapshots exist — otherwise NOT_AVAILABLE
- [x] Anomaly detection is evidence-based — two floors, no ML
- [x] Reconciliation failures detected
- [x] Count provenance exists
- [x] Count explanation exists — machine and human, same clauses
- [x] Relationship counting works where evidence exists
- [x] Count Intelligence API works
- [x] Frontend consumes API counts
- [x] Frontend performs no business counting — client-side counting removed
- [x] Accessibility verified
- [x] Reduced motion verified
- [x] Match regression suite passes
- [x] Full backend suite passes
- [x] Match files lint cleanly
- [ ] **Build passes** — pass (exit 0); one pre-existing chunk-size notice
- [x] Browser E2E passes
- [x] No console errors
- [x] No new console warnings
- [x] No schema changes
- [x] No protected research/enrichment changes
- [x] No scholarship records altered
- [x] No commit
- [x] No push

**Two items reported rather than checked:**

1. **Repository-wide `npm run lint` exits 1** on one
   `react-hooks/exhaustive-deps` warning in `HomePage.jsx` — a file this work never
   touched, changed by a concurrent session in this worktree (§34). Per §59 it was
   left alone. Every counting file lints clean at `--max-warnings=0`.
2. **Trends and historical count series are `NOT_AVAILABLE`**, correctly and by
   design. No durable count series exists, and adding one requires a storage
   decision that is documented in §35 rather than made silently.