# CURRENT PRODUCTION MENTOR FIX CANDIDATE — FINAL

**No deployment. No push. No merge to master. No production, Neon, image, ingestion, scheduler, audit,
Match, Count, Applications or Wave 1–3 change.** The candidate is a **local branch only** — verified absent
from the remote.

---

## 1. Current Production Baseline

| item | value |
|---|---|
| **live production revision** | **`4edd154a303715442a2f0517b052259e5f113cab`** (`docs: record the final suite numbers and the production run`) |
| `origin/master` at close | `573a983` — **deliberately not used as a base** |
| production moved during this task | **No.** It held `4edd154` throughout, unlike the previous two phases |
| worktree base verification | clean tree created at `4edd154`, `git rev-parse HEAD` == the live sha |
| `3c6370c` / `ed58738` used as base | **No** — neither was used |

## 2. Proven Regression

`collect()` deduplicated evidence chips on a **global `(label, value)`** pair with no record owner.

| measurement (shipped code, real dataclasses) | chips per record |
|---|---|
| before the fix | `{28: 6, 61: **1**}` |
| after the fix | `{28: 6, 61: 6}` |

The second record retained only its name; Verification, Deadline, Funding, Fit and Readiness were dropped
and the freed budget consumed by profile chips.

**PROVEN, not theoretical:** **60 of 63** catalogue records share one `(verification_status, funding)`
pair; only 2 share a `(deadline_date, deadline_precision)` pair.

**Bounding fact — PROVEN:** a focused/named record sorts first, so the record the user asked about keeps
its chips; the loss falls on supporting records. **USER-VISIBLE information regression — not security,
not privacy, not data integrity.**

**Still present in production:** verified unfixed at `4edd154`.

## 3. Exact Minimal Fix

Three logic lines and one constant, all inside `collect()`'s dedup path:

```python
_STUDENT_SCOPE = "__student__"                                     # new constant
fingerprint = (entry.scholarship_id, chip.label, chip.value)       # was (chip.label, chip.value)
fingerprint = (_STUDENT_SCOPE, entry.label, entry.value)           # student chips
```

**Why `scholarship_id` is the correct owner — PROVEN.** Both `ScholarshipFacts` and `ApplicationFacts`
carry `scholarship_id`, and an application's chips *describe that scholarship*. Keying on it still
collapses "the catalogue and the workspace both evaluated this one deadline", which was the dedup's entire
purpose.

`chip.key` already encoded identity (`scholarship-{id}-funding`), so the key-based `seen` set was always
correct and is untouched. Nothing outside the dedup path changed.

## 4. Candidate Construction

| item | value |
|---|---|
| base SHA | `4edd154a303715442a2f0517b052259e5f113cab` |
| fix source | re-derived directly in the production tree (not cherry-picked from either prior candidate) |
| regression test source | blob restored from `ed58738`, **byte-identical** (`bfcefaf9…` verified) |
| **candidate SHA** | **`00d835dff9da1d63d6d8106660370b6673493291`** |
| branch | `candidate/production-4edd154-mentor-dedup` — **local only** |
| pushed? | **No** — candidate sha verified absent from `git ls-remote origin` |
| deployed? | **No** — production still `4edd154` |

## 5. Current-Production Compatibility

Eight representative files verified **byte-identical** to `4edd154` (`git hash-object` vs
`git rev-parse 4edd154:<path>`), i.e. untouched by this candidate:

`mentor/compose.py` · `mentor/context.py` `routers/mentor.py` · `tests/test_mentor.py` ·
`mentorPresentation.js` · `Navigation.css` · `jobs/scholarzone_maintenance.py` ·
`services/scholarship_ingestion.py`

Behaviour spot-checks, all present in the candidate tree:

| behaviour | evidence in candidate |
|---|---|
| defect 1 — focused application leads | `groups = [ordered_applications] if focused_application is not None …` |
| defect 2 — precision gating | `_EXACT_PRECISION = "exact"`, `def is_exact` |
| defect 3 — funding vocabulary | `def funding_word`, `def funding_is_unmeasured` |
| defect 4 — repeated gap once | `unestablished_funding: list[str] = []` in `compose.py` |
| defect 5 — chip basis not duplicated | `return entry.verification \|\| ''` |
| defect 6 — nav overflow | `flex-wrap: wrap` present in `Navigation.css` |
| `27047de` behaviour | `compose.py` byte-identical to production |

## 6. Diff/File Verification

```
$ git diff --name-status 4edd154 HEAD
M       backend/app/services/mentor/evidence.py
A       backend/tests/test_evidence_record_identity.py

$ git diff --stat 4edd154 HEAD
 backend/app/services/mentor/evidence.py        |  20 ++-
 backend/tests/test_evidence_record_identity.py | 236 +++++++++++++++++++++++++
 2 files changed, 253 insertions(+), 3 deletions(-)
```

**Files differing from production: 2** (counted programmatically). The only removed lines are the three
bare-fingerprint expressions. The local E2E harness (`backend/cand_seed.py`) was left **untracked** and is
not in the candidate.

## 7. Backend Tests

| gate | result |
|---|---|
| regression suite (candidate) | **10 passed** |
| **non-vacuity** — fix reverted via stash | **5 failed / 5 passed**, restored to **10 passed** |
| `test_mentor.py` — production's own file, unmodified | **78 passed** |
| relevant suite (15 files: mentor, dashboard, application, matching, counting, evidence) | **1046 passed, 1 skipped** |
| `py_compile` + import smoke | clean; `_STUDENT_SCOPE` resolves |

Required assertions, all covered:

1. same chip within the **same** record deduplicates — `test_the_same_record_reported_by_two_systems_collapses_to_one_deadline`, `test_two_applications_on_one_scholarship_do_not_duplicate_a_deadline`
2. same chip across **different** records stays independently visible — `test_two_records_with_identical_values_keep_their_own_chips`, `test_identical_funding_and_verification_do_not_cross_suppress`
3. named/focused keeps priority — `test_a_focused_record_keeps_priority_and_others_keep_their_chips`
4. chip budget still works — `test_the_budget_may_truncate_but_must_never_suppress`
5. **budget truncation does not masquerade as deduplication** — a truncated record keeps a *prefix*; a suppressed one keeps only its name
6. deadline precision truthful — `test_deadline_precision_wording_is_untouched`
7. application evidence correct — browser check 9, plus the two-collapse tests
8. no Mentor context regression — `test_student_evidence_is_still_appended`, full `test_mentor.py` unmodified

## 8. Frontend Tests

| gate | result |
|---|---|
| `npm test` | **163 passed** (9 files) — production baseline; the 4 chip-basis tests are **intentionally excluded** as out of scope |
| `npm run lint` | **0 errors**, 1 pre-existing `HomePage.jsx` warning |
| `npm run build` | **success** |

## 9. Browser E2E

Real local backend (uvicorn, candidate tree), **isolated local SQLite** (`cand.db`, 68 records), **real
HTTP**, **real Chromium**. Seeded a **collision pair**: `CAND Twin Alpha` (id 64) and `CAND Twin Beta`
(id 65) — identical in verification, funding and day count.

| # | check | result |
|---|---|---|
| 1 | **identical chips on twinA AND twinB both retained** | **PASS** — twinA `[Application state, Deadline]`, twinB `[Application state, Deadline]` |
| 2 | named scholarship keeps priority | **PASS** — first chip `id=65 Scholarship` |
| 3 | navigation works | **PASS** — nav present, 10 links |
| 4 | application context works | **PASS** — 5 applications created and answered from |
| 5 | dashboard works | **PASS** — 200 |
| 6 | scholarships works | **PASS** — 200 |
| 7 | match works | **PASS** — 200 |
| 8 | logout behaviour correct | **PASS** — logout 204, then mentor **401** and dashboard **401** |
| 9 | deadline precision truthful | **PASS** — month → "About 45 days left. The published date is not recorded to the day…" |
| 10 | unknown deadline stays unknown | **PASS** — "No published deadline to count down to." |
| 11 | funding `UNKNOWN` unmeasured | **PASS** — 0 Funding chips for that record |
| 12 | same-record duplicates still collapse | **PASS** — max 1 deadline chip per record |
| 13 | responsive | **PASS** — 320px: `wrap=wrap`, `right=277`, no horizontal scroll, 0 interactive overflow; 1920px clean |

**Console errors — 14, all attributed, none from the changed code:**

| count | error | attribution |
|---|---|---|
| 12 | `ERR_NAME_NOT_RESOLVED @ https://cand{1,2,3,4}.example/logo.png` | **my own E2E fixture images.** `.example` is a reserved TLD that by design does not resolve |
| 2 | `401 @ /api/mentor/message`, `401 @ /api/dashboard` | **my own deliberate post-logout probes** — these *are* the logout-protection assertions |

**Zero console errors attributable to the candidate's change.** Unlike the earlier phase, no third-party
image timeouts occurred here.

## 10. `27047de` Preservation — **PROVEN intact**

`27047de` (`fix: stop the mentor asserting a claim it never checked about a student's record`) touched
`compose.py` and `test_mentor.py`. The candidate is based on `4edd154`, which **contains** it:

- `compose.py` blob **identical** to production (hash-compared);
- its `unestablished_funding` aggregation present;
- `test_mentor.py` blob **identical** to production — so `27047de`'s tests run unmodified and
  **78 passed**, up from the 77 measured before that commit.

**No risk of reverting it**, which is precisely the hazard flagged for `3c6370c`.

## 11. Unrelated Changes Excluded

Deliberately **not** in this candidate, per the absolute rule:

| excluded | why |
|---|---|
| M1 mentor module docstring correction | documentation, not required by the dedup fix |
| M1 contract tests (`TestTheOverviewIsPublicAndTheMessageIsNot`) | separate concern |
| Vacuity guard (`TestFixturesCannotSilentlyBecomeVacuous`) | test-quality concern; production's non-vacuous fixtures were reused as instructed |
| Chip-basis presentation test (`evidenceStatusWord`) | covers defect 5, already fixed in production |
| **M2** — `ApplicationFacts.official_source_url` | deferred by instruction; verified still absent |
| `5416914`, `9ff021b`, `3bf92b6`, `27047de` | already in the production base — not re-applied |
| Any master change (`573a983` and its content) | master not used as base |
| `ed58738`, `3c6370c` | neither used as base |

**M2 verified still deferred:** `ApplicationFacts` fields are exactly
`application_id, scholarship_id, name, state, state_label, outcome, progress_percent, next_open_task,
deadline, saved, has_notes, is_listed, verification_label` — **no `official_source_url`**.

## 12. Candidate SHA

```
base      4edd154a303715442a2f0517b052259e5f113cab   (current production)
candidate 00d835dff9da1d63d6d8106660370b6673493291
branch    candidate/production-4edd154-mentor-dedup   (local only)
files     M backend/app/services/mentor/evidence.py
          A backend/tests/test_evidence_record_identity.py
stat      2 files changed, 253 insertions(+), 3 deletions(-)
```

## 13. Deployment Readiness

**GREEN — READY FOR CONTROLLED DEPLOY**, subject to one owner judgement.

Supporting evidence:
- the diff against production is **exactly 2 files**, one of them the fix and one its test;
- **all eight** representative production files are byte-identical;
- `27047de` and all six `c3aefad` fixes verified present and unmodified;
- **1046 backend / 163 frontend tests pass**; lint 0 errors; build clean;
- the regression test is **provably non-vacuous** (fails on revert);
- **13/13 browser E2E checks** pass on a real stack;
- the fix is **still needed** — unfixed at production `4edd154`.

Caveats the owner should weigh, stated plainly:
1. This candidate **diverges from `origin/master`** (`573a983`). It is the safest *delta* from what is
   live, not the newest code. Integrating it means merging this one commit forward, which will need a
   rebase and a re-run of the Mentor suites at the new tip.
2. The fix is **not urgent in the security sense** — no data, privacy or availability impact — but it is
   **user-visible and silent**, and 60 of 63 records collide, so every multi-record Mentor answer today
   is under-reporting supporting context.
3. It does **not** address M2, M1's docstring, or the vacuity guard. Those remain open by design.

## 14. Remaining Mentor Issues

| issue | classification |
|---|---|
| **M2** — application evidence cannot expose an official source URL; a `Verified` deadline chip can carry `source_url: None` | **PROVEN**, TRUST/UX HARDENING, **non-blocking**, deferred |
| **M1** — module docstring still claims "Both require a session. There is no public mentor route", contradicting the route's own docstring and the implementation | **PROVEN** documentation defect; not in this candidate |
| Vacuity guard for the Mentor fixtures | **PROVEN** absent from this candidate (production fixtures are currently non-vacuous) |
| Chip-basis presentation test (defect 5) | **PROVEN** untested; not in this candidate |
| `evidence.py` still ends without a trailing newline (pre-existing) | **PROVEN**, cosmetic |
| Sibling `self._is_non_logo_stored` `AttributeError` in `--stage images --logo-only` | **PROVEN** dead branch; **arming trap** — never fix the call without also fixing the predicate |
| `maintenance_runs` id 250 stale `status='running'` | **UNKNOWN** whether still active |

**Final classification: GREEN — READY FOR CONTROLLED DEPLOY**