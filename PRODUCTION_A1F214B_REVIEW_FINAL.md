# PRODUCTION REVISION REVIEW — `a1f214b` / `c3aefad`

**Read-only. No deployment, no rollback, no master change, no production data write, no maintenance
dispatch, no image repair or restoration, no Mentor/image/Wave 1–3 change.**

---

## 0. Scope note — the live revision moved during this review

| time | live revision |
|---|---|
| review opened | `a1f214b04b94` (the assigned target) |
| review closing | **`3ee434c01f53`** |

`3ee434c` is **docs-only** ("docs: add the GROUNDed AI Mentor final and security reports"). I verified at
`origin/master` that the three findings below are **all still present in the live revision**: the dedup
regression, M2, and M1. Every verdict therefore applies to what is running now, not just to the commit I
was asked to review.

---

## 1. Current Production Revision

| item | value |
|---|---|
| live revision | **`3ee434c01f53`** (`/api/health` → `ok`) |
| `origin/master` | `3ee434c` (docs-only on top of `a1f214b`) |
| assignment target | `a1f214b04b94` — still an ancestor; its code is live |
| `stats.total` / `verified_active` / `with_image` | 358 / 358 / 358 |
| subsets exceeding total | **none** |
| directory total | 358 |
| Match total / partition | 358 / 358 |
| Count contract | 200 |
| storage | 451 |
| 5xx observed | **none** |
| private data in anonymous responses | **none found** |

## 2. `c3aefad` Change Inventory

Six files, +315 / −46. Parent `5416914`.

| file | ± | area |
|---|---|---|
| `backend/app/services/mentor/compose.py` | +18/−4 | unknown-list construction |
| `backend/app/services/mentor/context.py` | +22/−8 | `DeadlineFacts.describe()`, precision handling |
| `backend/app/services/mentor/evidence.py` | +88/−16 | funding vocabulary, evidence ordering + dedup |
| `backend/tests/test_mentor.py` | +166/−16 | 8 new tests |
| `frontend/src/components/Navigation.css` | +15 | `flex-wrap` at ≤1024 |
| `frontend/src/services/mentorPresentation.js` | +7/−5 | `evidenceStatusWord` |

**Blast radius — PROVEN narrow.** The commit touches **no router, no auth, no image code, no Match, no
Count, no scheduler, no audit instrumentation, no migration, no public-data config**. Only the Mentor's
answer-shaping layer and one nav CSS rule changed.

Tests: **77 passed** at `a1f214b` (up from 69).

## 3. Six Defect Review

| # | defect | real? | fix correct? | evidence |
|---|---|---|---|---|
| 1 | a named application produced **no** application evidence — the budget was spent on scholarships first | **PROVEN real** | **PROVEN correct** | local authenticated run: 4 application chips now lead the list (`application.state`, `application.outcome`, `deadline`, `application.progress_percent`, `application.next_open_task`); `test_a_named_application_appears_even_with_many_matches` passes |
| 2 | a day count whose precision was **never recorded** was stated as exact | **PROVEN real** | **PROVEN correct** | probe on `DeadlineFacts.describe()`: `exact` → "11 days left."; `month` → "About 11 days left, based on a month-precision date."; `unknown`/`None` → "About 11 days left. The published date is not recorded to the day…" Only `exact` now licenses an unqualified count |
| 3 | funding rendered as the bare enum token `UNKNOWN` | **PROVEN real** | **PROVEN correct** | `funding_is_unmeasured` returns True for `UNKNOWN`, `unknown`, `" UNKNOWN "`, `None`; `funding_word` maps `FULL`→"Full funding." and passes catalogue prose through untouched |
| 4 | the unknown list repeated the same sentence once per record | **PROVEN real** | **PROVEN correct** | `compose.py` now aggregates into one line with a count; `test_a_repeated_gap_is_stated_once_with_a_count` passes |
| 5 | an evidence chip printed its basis twice (badge + provenance line) | **PROVEN real** | **PROVEN correct in intent, UNTESTED** | `evidenceStatusWord` now returns `entry.verification \|\| ''`. **`mentorPresentation.test.js` was not touched and contains no reference to it** |
| 6 | the utilities row overflowed the viewport (31px @1024, 4px @320) | **PROVEN real** | **PROVEN correct and live** | measured on production: at 1024 and 320 all three nav rows compute `flex-wrap: wrap`, end at `right=973`/`right=280` (inside the viewport), **zero interactive elements overflow**, `horizontalScrollPossible: false` at 320. The only element extending past the viewport is `span.app-atmosphere__wash` — `position: absolute; pointer-events: none` decoration |

**A seventh, unlisted finding — the test suite was passing vacuously. PROVEN real, PROVEN fixed.** The
commit states fixtures pinned a fixed deadline the wall clock had passed, so records were closed rounds,
were dropped from the match list, and every match-dependent assertion asserted nothing. Fixtures are now
built relative to today. This is the most valuable part of the commit: it means the other 69 tests were
weaker than they appeared, and `test_a_month_precision_deadline_is_qualified_not_stated_as_exact`'s own
comment ("Next month, so it is genuinely month-precision *and* still open") shows the awareness.

### REGRESSION introduced by `c3aefad` — **PROVEN**

Defect 1's fix added a **global** fingerprint dedup in `collect()`:

```python
fingerprint = (chip.label, chip.value)
if chip.key in seen or fingerprint in seen_values:
    continue
```

The stated intent is to collapse the *same fact about the same record* reported by two canonical systems
(catalogue deadline vs workspace deadline). The implementation keys on `(label, value)` with **no record
identity**, so chips belonging to *different records* collapse too.

Measured with the shipped `collect()` and real dataclasses:

| | chips per record |
|---|---|
| **before** (`5416914`) | `{28: 6, 61: 6}` |
| **after** (`a1f214b`) | `{28: 6, 61: 1}` |

Record 61 keeps only its name chip. Its Verification, Deadline, Funding, Fit and Readiness chips are
silently discarded, and the freed budget is consumed by profile chips instead.

**Likelihood on real data — PROVEN, not theoretical.** On the catalogue: **60 of 63 records share the same
`(verification_status, funding)` pair**; 34 share "fully funded" and 18 share "partial". Only 2 records
share a `(deadline_date, precision)` pair. So the Verification and Funding chips will routinely be
dropped for the second and subsequent records.

**Mitigation that bounds the damage — PROVEN.** A focused/named scholarship or application is sorted
first, so *the record the user asked about* keeps its chips. The loss falls on the supporting records.
So this is not "the asked record is hidden"; it is "the surrounding context is silently under-reported".

**Classification: PROVEN** (regression), and it is a **quality/grounding defect, not a security, privacy or
data-integrity defect.**

## 4. Production Runtime Verification

Unauthenticated sweep, read-only:

| code | path | note |
|---|---|---|
| 200 | `/api/health` | `ok` |
| 200 | `/api/scholarships?limit=5&page=1` | |
| 200 | `/api/scholarships/stats` | |
| 200 | `/api/scholarships/1` | |
| 200 | `POST /api/scholarships/match` | read-only query |
| 200 | `/api/v2/counts/contract` | |
| **200** | `/api/mentor/overview` | **anonymous — see §5** |
| **401** | `POST /api/mentor/message` | correctly gated |
| **401** | `/api/dashboard` | correctly gated |
| **401** | `/api/applications` | correctly gated |
| 200 | `/api/auth/session` | `{"user": null}` |

Frontend routes all **200**, including the SPA fallback for `/nonexistent-route-xyz`. Routing intact.
**Zero 5xx.**

**Authenticated flow — verified locally against the identical commit, not on production.** Creating a
production account would be a production data write, which is prohibited, so I ran the real backend and a
throwaway SQLite at `a1f214b`: register/login 200, application created, `POST /mentor/message` 200 with
`intent: APPLICATION_PROGRESS`, evidence led by the named application, and **zero console errors** in the
earlier browser pass. This is sound because `credential_present()` is **false in production** (no
`SCHOLARZONE_MENTOR_PROVIDER_KEY`), and `provider.py:160` states that in that case "the mentor runs on its
deterministic path" — the same `compose()` path (`service.py:174`) exercised locally. **Residual gap:
UNKNOWN** whether production has any environment-specific divergence, since I could not authenticate.

**Deadline grounding — intact and improved.** Production-rendered sentences are correct, and defect 2's
fix makes previously over-confident wording qualified.

**Application context — intact**, and now correctly prioritised.

## 5. M1 Assessment — **A. intentionally public static metadata**

Full anonymous payload from production:

```json
{ "supported_intents": [11 human labels], "intents": [11 enum tokens],
  "redirects": [5 canned question strings], "max_message_length": 2000,
  "assistance_available": false }
```

- No `user`, `email`, `application`, `scholarship_id`, `password`, `token`, `owner` or note data. The
  substring hits for "application"/"profile"/"deadline" are **question labels** ("Application progress",
  "Improving your profile", "What deadlines should I care about?").
- `assistance_available` is `credential_present()` — a **presence-only boolean**, explicitly documented as
  "Presence only. No endpoint, no model name, no key material." It does not leak configuration.

**And the intent is documented, contradicting only the stale module docstring.** The route docstring at the
deployed commit reads: *"Safe to call before sign-in: it contains only vocabulary, so it cannot leak
anything about an account. That is also why the private surfaces still require a session — this route has
nothing private on it to protect."*

So the implementation matches the route's stated intent, while the module docstring still asserts "Both
require a session. There is no public mentor route."

**Verdict: documentation/test mismatch. NOT a security blocker.** My earlier "false documented security
invariant" framing was too strong — the route documents itself as public on purpose. Recommended:
correct the module docstring and add a contract test asserting *overview is public and message is private*,
so both halves are pinned.

## 6. M2 Assessment — **TRUST/UX HARDENING**

Traced at `origin/master` and demonstrated end-to-end:

- `ScholarshipFacts.official_source_url` → **present**
- `ApplicationFacts.official_source_url` → **absent**
- `scholarship_evidence` sets `source_url` → **yes**; `application_evidence` → **no**; `student_evidence` → **no**

Observed chip from a real authenticated answer at the deployed commit:

```
id=1 [deadline (evaluate_deadline)] Deadline = "No published deadline to count down to."
       verification='Verified'   source_url=None
```

So **yes**: a deadline claim labelled `Verified` can appear with **no official source URL**, no source title
and no source evidence, because `application_evidence()` *structurally cannot* emit the field.

Exactly which claims are affected: every application-scoped chip — `application.state`, `application.outcome`,
`application.progress_percent`, `application.next_open_task`, and the deadline line when it comes from the
workspace rather than the catalogue.

**Classification: TRUST/UX HARDENING — not a trust blocker.** The claim is grounded in ScholarZone's own
verified catalogue rather than invented, the value is correct, and the UI links onward to the record. What
is lost is the ability to click through to the official source. It predates `c3aefad` and was **not**
addressed by it.

## 7. Image-System Status — **confirmed, no stage run**

| fact | status |
|---|---|
| scheduled maintenance uses master HEAD | **PROVEN** — `verification-cron.yml` `actions/checkout@v4` with no `ref:` |
| Vercel runtime does not run maintenance | **PROVEN** — APScheduler intentionally not started in production; "the schema is owned by the GitHub Actions maintenance pipeline"; no HTTP maintenance trigger in the served app |
| `9ff021b` in master | **yes** |
| `3bf92b6` in master | **yes** |
| both now also live in the served app | **yes**, since `a1f214b` |

No maintenance stage was dispatched and no image state was touched.

## 8. Security/Privacy Findings

| finding | classification |
|---|---|
| Anonymous `/mentor/overview` exposes only static vocabulary | **DISPROVEN** as a leak — no private data |
| `/mentor/message`, `/dashboard`, `/applications` correctly return 401 | **PROVEN** correct |
| `assistance_available` leaks only a presence boolean | **PROVEN** by design, documented |
| `c3aefad` changed authentication | **DISPROVEN** — no router touched |
| `c3aefad` changed authorization | **DISPROVEN** — none touched |
| `c3aefad` changed privacy posture | **DISPROVEN** — evidence ordering only |
| Module docstring contradicts the route docstring on route privacy | **PROVEN** documentation defect |
| `evidence_status_word` returning `''` where it used to return `basis` | **PROVEN** intended; low risk, untested |

**No security blocker found.**

## 9. Regression Findings

| finding | severity | classification |
|---|---|---|
| Global `(label, value)` dedup collapses chips across **different records**; 60/63 records collide on (verification, funding) | **medium-high**, user-visible, silent | **PROVEN** |
| Funding chip no longer gated by `evidence_is_usable(..., minimum=2)` — now `if funding:` only | very low; only affects sub-2-character funding strings | **PROVEN** (behaviour change, benign) |
| `evidence.py` ends **without a trailing newline** | cosmetic | **PROVEN** |
| Defects 2, 5, 6 have **no automated regression test** | process gap | **PROVEN** |

**No data-integrity, no outage, no 5xx regression.**

## 10. Rollback Assessment

Rolling back to `c405b49` would discard:

- six genuine Mentor fixes, four of which the commit correctly describes as making the mentor
  "confidently wrong" before — including **defect 2**, which stated an unrecorded-precision date as exact;
- the fix for **vacuous mentor tests** that had made 69 tests weaker than they appeared;
- the live `do_logos` fix and ingestion fix, both of which are independent and GREEN;
- the verified nav-overflow fix.

It would reintroduce the pre-`c3aefad` state in which a student asking about application N received ten
scholarship chips and no application.

Rollback cost **exceeds** rollback benefit. Nothing found is security-, privacy- or data-critical.

## 11. Keep-vs-Rollback Recommendation

**KEEP `a1f214b` / `3ee434c` deployed.**

- **A. Is it safe to keep?** **Yes.** No security issue, no private-data leakage, zero 5xx, all public and
  storage invariants intact (358/358/358, Match 358/358, count 200).
- **B. Is `c3aefad` safe to keep?** **Yes, with hardening.** It fixes six real defects, four of them
  grounding-correctness bugs, and repairs a vacuous test suite. It introduces one proven, high-likelihood,
  non-security regression in evidence completeness.
- **C. Is rollback necessary?** **No.**
- **D. Any proven production regression?** **One**, and it is confined to the Mentor evidence list:
  the cross-record chip collapse. No production data, availability, auth or public-contract regression.
- **E. Must be fixed before the next release:** the dedup regression, M1's docstring/test, M2's source URL,
  plus tests for defects 2, 5 and 6.
- **F. Can remain as documented technical debt:** M2 (non-blocking provenance), the missing trailing
  newline, and the funding-chip minimum-length change.

## 12. Required Next Fixes

1. **Scope the dedup to a record identity** — fingerprint on `(scholarship_id | application_id, label,
   value)` rather than `(label, value)`, so the intended same-record/two-system collapse is preserved while
   distinct records keep their chips. Add the regression test I used: two records sharing
   `(verification, funding, deadline)` must both retain a full chip set.
2. **Correct the module docstring** in `backend/app/routers/mentor.py` so it matches the route docstring,
   and add a contract test asserting `/mentor/overview` is public while `/mentor/message` requires a
   session — pinning both halves of the intended design.
3. **Thread `official_source_url` into `ApplicationFacts`** and set it in `application_evidence()`, so a
   `Verified` deadline claim can be traced to its official page.
4. **Add the missing tests:** deadline-precision qualification (defect 2), `evidenceStatusWord` (defect 5),
   and a nav-overflow assertion (defect 6).
5. Restore the trailing newline in `evidence.py`.

None of these is urgent enough to justify rolling back a release that made the mentor measurably more
truthful.

**FINAL CLASSIFICATION: KEEP_WITH_HARDENING**