# SCHOLARZONE MATCH 2.0 — FINAL VERIFIED REPORT

Generated after the verification described in section 24 onwards. Every number in
this report was observed in this working tree. Nothing here is projected.

---

## 1. Implementation status

Match 2.0 is implemented, tested and verified end to end against a real local API
and a real browser.

Three known defects were found and fixed rather than papered over:

1. **The sensitivity range was on the wrong scale.** It was reported as a 0–1
   fraction beside a 0–100 score, because it divided a weight-sum-of-1.0
   numerator by a weight-sum-of-100 constant. Both bounds are now on the score's
   own 0–100 scale.
2. **The language surplus was not clamped to the unit interval.** `clamp()`'s
   default bounds are 0–100, so clamping the *ratio* there let IELTS 9.0 against a
   6.5 minimum with a 2.0 range produce a language component score of 125.
3. **A stale `official_details` blob outranked the curated programme column.**
   `resolve_scholarship_field` prepended the free-form JSON, contradicting its own
   documented order, so a record could be scored against a programme the research
   pipeline had already corrected.

A fourth defect was found during browser E2E and fixed:

4. **Facet labels were title-cased.** A degree string published as
   "Bachelor's, Master's" was displayed as "Bachelor'S, Master'S" and "PhD" as
   "Phd", restyling text ScholarZone did not author. Labels are now the published
   string verbatim.

And a fifth, found by writing the tests:

5. **The natural-language parser could emit an invalid payload.** Europe expands to
   32 curated countries while the request model capped `preferred_countries` at 25,
   so the product's own documented example produced a profile that failed its own
   validation. The bound is now the size of the largest curated region.

---

## 2. Architecture

A pure engine with one impure boundary. `service.py` resolves `as_of` and loads
candidates; everything downstream is a function of its arguments. No clock, no
randomness, no session, no network and no model inside the scoring path. This is
enforced by test, not convention: the pure modules are source-scanned for
`date.today()`, `datetime.now()`, `time.time()` and for HTTP clients.

Full detail is in `backend/docs/scholarzone-match-engine.md`.

---

## 3. Exact files created

**Backend — `backend/app/services/matching/`** (all new)

| File | Role |
|---|---|
| `config.py` | Every weight, band, matrix and version; validated at import. |
| `constants.py` | Backwards-compatible re-export of `config.py`. |
| `types.py` | Pydantic v2 request/response contract. |
| `repository.py` | One bounded explicit-column candidate query. |
| `normalize.py` | Profile normalisation, Academic Profile Index. |
| `taxonomy.py` | Curated programme field taxonomy. |
| `requirements.py` | Conservative readers for published rules. |
| `academic.py` | Like-for-like academic comparison. |
| `components.py` | Field, funding, requirement, language, preference, timing. |
| `eligibility.py` | The hard gate. |
| `metrics.py` | Fit arithmetic and the public fit disclosure state model. |
| `confidence.py` | Record trust, independent of the profile. |
| `readiness.py` | Application readiness. |
| `profile_strength.py` | Profile completeness. |
| `gaps.py` | Gap classification. |
| `actions.py` | Grounded next steps. |
| `summaries.py` | Counting, reconciliation, facets. |
| `explain.py` | Reason codes and templates. |
| `nlp.py` | Deterministic free-text profile parser. |
| `engine.py` | The pipeline and the total ranking order. |
| `service.py` | The impure boundary. |

**Other backend files created**

- `backend/app/routers/match.py`
- `backend/docs/scholarzone-match-engine.md`
- `backend/tests/test_matching_engine.py`
- `backend/tests/test_matching_taxonomy.py`
- `backend/tests/test_matching_api.py`
- `backend/tests/test_matching_v2.py`

**Frontend — `frontend/src/components/match/`** (all new)

`HowThisIsCalculated.jsx`, `MatchCard.jsx`, `MatchCompare.jsx`, `MatchFilters.jsx`,
`MatchProfileForm.jsx`, `MatchReadiness.jsx`, `MatchResultSummary.jsx`,
`MatchResults.jsx`, `ProfileStrengthPanel.jsx`, `ProfileTextParser.jsx`,
`matchFilterConfig.js`

**Other frontend files created**

- `frontend/src/hooks/useMatchProfile.js`
- `frontend/src/pages/MatchPage.jsx`
- `frontend/src/pages/MatchPage.css`
- `frontend/src/services/matchService.js`

---

## 4. Exact files modified

Tracked files with a real content change, confirmed by `git diff --numstat`:

| File | Change |
|---|---|
| `backend/app/main.py` | 12 insertions, 1 deletion. Match router registered ahead of the dynamic scholarship route; CORS permits `POST`. |
| `frontend/src/App.jsx` | 2 insertions. `/match` route. |
| `frontend/src/components/Navigation.jsx` | 1 insertion. Match link. |
| `.gitignore` | 2 insertions. Pre-existing from Match 1.0. |

Everything else touched by this work is in the untracked created-file list above.

---

## 5. Database and schema status

**No schema change. No migration. No seed change.** No database model was edited.

The E2E run used an isolated SQLite file outside the repository
(`%LOCALAPPDATA%\Temp\kilo\sz-e2e.db`), created from the current models, so the
developer's own database was never opened.

The pre-existing condition of `backend/scholarzone.db` is unchanged: it predates
the `is_archived` column, so the application's own startup seed fails against it
with `sqlite3.OperationalError: no such column: scholarships.is_archived`. That is
a pre-existing local-data problem, not a Match defect, and it is why the tests use
an isolated database.

---

## 6. Fit mathematics

Seven components, exactly 100%:

| Component | Weight |
|---|---|
| Academic | 25% |
| Field | 20% |
| Funding | 20% |
| Requirements | 15% |
| Language | 10% |
| Preference | 5% |
| Timing | 5% |

```
fit     = SUM(weight x score) / SUM(weight)   over EVALUATED components only
coverage= SUM(weight of evaluated) x 100
```

A malformed weight table raises at import. It is never silently rescaled.

An unevaluated component is excluded from **both** halves of the fraction. If
nothing is evaluable, `fit_score` is `null`, never 0. An evaluated zero stays
evaluated. Only the published score is rounded, to one decimal. Contributions
sum to the score within `SUM_TOLERANCE`.

Bands: Exceptional 90–100, Very Strong 80–89.9, Strong 70–79.9, Possible
55–69.9, Low 0–54.9.

---

## 7. Eligibility behaviour

The gate runs before scoring and is never passed a fit score. `evaluate()` and
`evaluate_deadline()` accept no score parameter, which is asserted by
signature inspection in the test suite.

| Verdict | `fit_score` | `fit_label` |
|---|---|---|
| `INELIGIBLE` | `null` | `INELIGIBLE` |
| `NEEDS_VERIFICATION` | the score, if any | the band, if any |
| `ELIGIBLE` | the score, if any | the band, if any |

`suppressed_fit_score` was **removed** from `MatchResult`. The raw arithmetic
stays on the internal `PublicFit` object and is never serialised.

`fit_label` is always one of the five band keys, `INELIGIBLE` or
`NOT_EVALUATED`. Never a composed string.

Observed live, empty profile, 71 candidates: `ELIGIBLE` 36, `NEEDS_VERIFICATION`
4, `INELIGIBLE` 31. Ineligible cards rendered `N/A` with no tier;
needs-verification cards rendered their score and band.

---

## 8. Confidence

35% data completeness, 25% provenance, 25% requirement explicitness, 15%
verification freshness. Computed with no reference to the profile, so no profile
can raise it. Freshness bands 1.00 / 0.75 / 0.50 / 0.25 / 0 at 90 / 180 / 365 /
730 days. Bands: HIGH ≥ 85, MEDIUM ≥ 65, LOW below. Fit and confidence are never
multiplied together.

---

## 9. Readiness

Eligibility certainty 30%, requirement completeness 20%, language readiness 15%,
application readiness 15%, deadline readiness 20%. Unevaluated dimensions are
excluded and the rest renormalised; nothing evaluable yields `null`, not 0.
Observed live: a card with every dimension evaluated reported readiness 100 with
five checklist items.

---

## 10. Profile strength

Academic 25%, study goal 25%, language 20%, funding 20%, identity 10%. Observed
live: 70 for a fully typed profile ("Good profile"), 30 for a near-empty one.
Rendered outside the results and captioned as neither fit nor confidence.

---

## 11. Counting and reconciliation

Two named sets. Summary counts describe the **analysed universe**; facet counts
describe the **returned page**, and `MatchFacets.count_basis` says so.

Verified live on a truncated response (60 cards of 71 analysed):

```
Eligible 36 + Need verification 4 + Not eligible 31 = 71 = total_candidates
```

`assert_reconciled` raises rather than returning a dashboard that disagrees with
itself. `include_ineligible: false` removes records from the universe rather than
scoring and hiding them.

---

## 12. Facets

Country, field, degree, funding, eligibility, fit, confidence and deadline, all
driven by the API's own facet payload. No values are hardcoded in the frontend.
Observed live: `Germany (5)` filtered 60 cards to 5. Labels are the published
strings verbatim.

---

## 13. Ranking

1. eligibility state, 2. fit descending, 3. confidence descending, 4. coverage
descending, 5. deadline relevance, 6. `scholarship_id` ascending. Total order, so
the sequence is reproducible. An ineligible record cannot outrank a valid one
because its raw arithmetic is not in the public contract.

---

## 14. Explainability

Reason codes are stable and rendered through fixed templates. No language model
generates any text. Every card exposes "How this score is calculated", collapsed
by default, with per-component weight and score, coverage, evaluated counts,
effective weight, contribution and the sensitivity range. Observed live:

```
Coverage: 15% · Evaluated: 1 of 7
… could fall to 3.8; … could reach 88.8. Mathematical sensitivity range, not a prediction.
Missing information is not treated as zero.
```

---

## 15. Actions and gaps

Four gap categories, four of them, so missing data is never written up as a
failure. Actions are derived from the gaps that occurred and ordered by
consequence; a blocking condition first, "visit the official source" last and
only when a URL was published. Observed live: `Visit Official Source` rendered as
the primary action, with additional actions behind a disclosure.

---

## 16. NLP parsing

Optional, deterministic, local. Verified live with the product's own example. The
response contained six resolved interpretations, each with the phrase it matched:

```
citizenship          Bangladesh            from "I'm from Bangladesh and want a fully funded Master's in Computer Science in Europe"
intended degree level Master               from "Master's"
intended field       Computer Science      from "in Computer Science in Europe"
funding requirement  Full Funding          from "fully funded"
language credentials IELTS 7                from "IELTS 7"
preferred countries  Europe (32 countries) from "europe"
```

Nothing was calculated: zero result cards existed until the student pressed
Calculate My Matches. Nothing was written to the database — asserted by a row
count before and after.

---

## 17. Frontend UX

Quick Match with six progressive steps and an explicit "Step N of 6" indicator;
Deep Match with the optional detail; optional free-text parser with editable
confirmation; profile strength; result summary from API counts; facets with real
counts and reset; match cards with fit, eligibility, confidence, coverage, why
this matches, what may need attention, readiness, next best action and the
collapsible calculation; compare 2–3; zero-result state with calculable
alternatives; loading, empty and error states; explicit six-state machine.

The state machine is `idle | editing | validating | calculating | success | empty
| error`, named in `MATCH_STATUS` rather than inferred from which fields happen to
be populated.

### Why this matches you

The engine returns one reason per thing it established, which is the right
granularity for an audit trail and the wrong one under a heading that claims a
match. A reason such as "no academic result was supplied" was rendering next to a
tick mark. Reason codes are now split in the card: only codes that assert
something in the student's favour appear under "Why this matches you", and
everything else is reported under "What may need attention", where it belongs.

### Zero-result experience

Observed live: `No exact matches`, with `Remove "Degree" → 5 results` and
`Remove "Country" → 1 result`. Only alternatives that actually produce results
are offered.

### Reset

Observed live: reset returned the form, cleared the fields, cleared the results
and the strength panel, cleared the `sessionStorage` draft, and restored
"Step 1 of 6".

---

## 18. Accessibility

Tab order verified across 14 stops; every focusable element reported a visible
`2px solid` outline. Semantic `label`/`htmlFor` on every form control.
`aria-invalid` and `aria-describedby` on fields that fail validation.
`role="status" aria-live="polite"` on the parser confirmation and the result count.
Visually hidden text carries the state that colour also conveys, so eligibility
and completeness are never colour-only. Score values are readable numbers, with
the literal text `N/A` rather than an icon. Touch targets are at least 44px.

---

## 19. Motion and reduced motion

Under `prefers-reduced-motion: reduce`, verified live: the loader's computed
`animation-name` is `none` with a full-width bar, and all 60 cards plus the
summary still rendered with visible scores. No content depends on an animation to
become visible.

---

## 20. API endpoints and contracts

| Endpoint | Verified |
|---|---|
| `POST /api/scholarships/match` | yes, and under `/scholarships/match` too |
| `GET /api/scholarships/match/profile-options` | yes, country list complete |
| `POST /api/scholarships/match/parse-profile` | yes |

Requests are strict: unknown properties are rejected with 422, and an empty
`parse-profile` body returns the normal empty state rather than an error. The
frontend is presentation-only and recalculates no Match mathematics.

---

## 21. Performance

One bounded explicit-column query, SQL-side country filtering,
`public_visibility_conditions()` reused, O(n) scoring, no N+1, no cache, no Redis,
no new service, no new dependency.

---

## 22. Documentation

`backend/docs/scholarzone-match-engine.md` rewritten for the current
implementation: architecture, pure-engine boundary, profile normalisation,
eligibility, fit formula, weights, coverage, bands, academic comparison, field
taxonomy, funding matrix, language, requirements, timing, confidence, readiness,
profile strength, reason codes, gaps, actions, counting, facets, ranking,
versioning, determinism, privacy, API, performance and limitations.

---

## 23. Matching tests

| Suite | Result |
|---|---|
| `test_matching_v2.py` | **371 passed** |
| `test_matching_engine.py` + `test_matching_taxonomy.py` + `test_matching_api.py` + `test_matching_v2.py` | **562 passed, 1 warning** |

The one warning is a pre-existing `StarletteDeprecationWarning` about
`httpx`/`TestClient` in `test_matching_api.py`.

---

## 24. Full backend tests

```
python -m pytest tests -q
4051 passed, 1 skipped, 13 warnings in 151.12s
```

The 13 warnings are pre-existing and unrelated: Pillow `getdata` deprecation in
image analysis, SQLAlchemy `Query.get()` legacy warnings in the retry tests, and
`TestClient` deprecation notices.

---

## 25. Frontend lint

**Match surface: clean.**

```
npx eslint src/components/match src/hooks/useMatchProfile.js \
            src/pages/MatchPage.jsx src/services/matchService.js --max-warnings=0
exit 0
```

**Whole repository: one pre-existing warning, and it is the only failure.**

```
npx eslint src --max-warnings=0
src/pages/HomePage.jsx
  246:6  warning  React Hook useEffect has a missing dependency: 'description'
exit 1
```

This is reported rather than fixed. `HomePage.jsx` is not a Match file and was
not modified by this work — `git ls-files -m` does not list it. Adding
`description` to that effect's dependencies would re-run the SEO-script effect on
every render, because the value is derived from `catalogueSize`, which changes
identity on each render. Fixing it properly means restructuring an unrelated
component, which is outside this task's scope.

---

## 26. Frontend build

```
npm run build
✓ built in 286ms
dist/index.html                   0.82 kB │ gzip:   0.45 kB
dist/assets/index-Do3NLUK6.css  216.08 kB │ gzip:  34.33 kB
dist/assets/index-gR0cmG-x.js   495.71 kB │ gzip: 145.19 kB
exit 0
```

517 modules transformed.

---

## 27. Browser E2E

Against a real local API on port 8000 and the real Vite dev server on port 5173,
driving Chrome.

| Check | Result |
|---|---|
| Match page loads | pass |
| Quick Match with step indicator | pass, "Step 1 of 6" |
| Deep Match | pass, all optional fields render |
| Form validation | pass, "A percentage result cannot be above 100." and "That is longer than 120 characters." both block submission |
| Free-text parsing | pass, 6 interpretations, 0 results before confirmation |
| Calculation | pass |
| Result counts | pass, 36 + 4 + 31 = 71 |
| Truncation disclosed | pass, "Showing the 60 highest-ranked of 71" |
| Filters | pass, `Germany (5)` → 5 of 60 |
| Reset filters | pass, restores the original 60 |
| Zero-result state | pass, 2 calculable alternatives |
| Compare | pass, 3 columns × 9 factual rows, no "winner"/"best"/"guaranteed", fourth selection disabled |
| Why this matches | pass |
| Gaps | pass |
| Readiness | pass |
| How this score is calculated | pass, with effective weight, contribution and sensitivity |
| Ineligible → N/A | pass, no public tier |
| Needs verification → fit shown | pass, `78.1 / 100` "Strong Fit" |
| Deep link | pass, fields applied, URL cleaned |
| Keyboard | pass, 14 stops, visible 2px outline |
| Reduced motion | pass, loader animation `none`, 60 cards rendered |
| Empty state | pass |
| Error state | pass, message + retry, no stale results |
| Console errors | none on the Match page |
| Console warnings | none |

Regression sweep, all HTTP 200, no console errors:

| Page | Heading |
|---|---|
| Home | Find the right scholarship with confidence. |
| Scholarships | All Scholarships |
| Countries | Explore Destinations |
| Scholarship detail (`/scholarships/9`) | Erasmus Mundus Joint Masters (EMJM) |

**There is no `/stats` route in this application.** `App.jsx` defines `/`,
`/countries`, `/scholarships`, `/match`, `/scholarships/:id`, `/login`,
`/register`, `/saved`, `/compare`, `/admin` and a catch-all. The statistics
section is a region on the Home page and rendered correctly there. `/stats` was
never a route, so this is not a regression.

---

## 28. Known limitations

Accepted rather than guessed away:

- `program_type` is missing on many records, so field alignment is honestly
  unevaluated for them.
- Structured funding columns are sparse, so funding coverage is `UNKNOWN` more
  often than not.
- Missing data lowers coverage. It never becomes a zero.
- A record that publishes no rule cannot be verified against one.
- Filters and facets are English-only.
- `backend/scholarzone.db` is stale and predates `is_archived`.

---

## 29. Protected-file verification

Verified with `git diff --numstat`, `git diff-files --name-only` and
`git ls-files -m` after an index refresh. The complete set of tracked files with
a content change is:

```
.gitignore
backend/app/main.py
frontend/src/App.jsx
frontend/src/components/Navigation.jsx
```

All four are Match 2.0 files.

Confirmed untouched:

`scholarship_enrichment.py`, `image_validator.py`,
`scholarship_image_verifier.py`, `official_page_discovery.py`,
`deadline_semantics.py`, `verified_scholarships.py`, `models.py`,
`database.py`, `seed.py`, `backend/research_output/*.json`,
`frontend/src/pages/HomePage.jsx`, and every other tracked file.

`backend/research_output/*.json` is untracked, so Git cannot diff it; those files
were never opened for writing by this work. Unrelated scratch and research
artefacts already present in the working tree were left exactly as found.

---

## 30. Repository statement

**No git commit or push was performed.**

Nothing was staged. No branch was created. No reset, clean, rebase or force-push
was run. The working tree holds the finished, verified Match 2.0 implementation
and the unrelated artefacts it already had.

---

## Acceptance gate

| Item | Status |
|---|---|
| Summary counts reconcile | verified |
| Needs-verification fit behaviour correct | verified |
| Ineligible public fit suppressed | verified |
| `test_matching_v2.py` complete | 371 tests |
| Matching suite passes | 562 passed |
| Full backend suite passes | 4051 passed, 1 skipped |
| API tests pass | verified |
| Quick Match works | verified in browser |
| Deep Match works | verified in browser |
| Profile parsing works safely | verified in browser |
| Profile strength works | verified in browser |
| Results summary works | verified in browser |
| Facets work | verified in browser |
| Reset works | verified in browser |
| Compare works | verified in browser |
| Why matches works | verified in browser |
| Gaps/actions work | verified in browser |
| Readiness works | verified in browser |
| Calculation explanation works | verified in browser |
| Accessibility verified | keyboard and labelling verified in browser |
| Reduced motion verified | verified in browser |
| Frontend lint passes | **Match surface passes; repository fails on one pre-existing warning in an unmodified file** |
| Frontend build passes | verified |
| Browser E2E passes | verified |
| No console errors | verified |
| No new console warnings | verified |
| Documentation updated | verified |
| No protected research/enrichment file changed | verified |
| No schema changes | verified |
| No commit | verified |
| No push | verified |