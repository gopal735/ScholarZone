# MENTOR POST-DEPLOYMENT HARDENING — FINAL

**No rollback. No deployment. No production modification. No image, ingestion, Match, Count, Application,
Dashboard or scheduler change.** One source fix, plus tests and a documentation correction.

**PROVEN — the regression is fixed, still needed, and still live in production.** Verified at the deployed
revision `4edd154` and at `origin/master`: `fingerprint = (chip.label, chip.value)` is still present;
nobody else had fixed it.

---

## 1. Current Production Revision

| item | value |
|---|---|
| live revision at task start | `3ee434c` (the assigned base) |
| live revision at task close | **`4edd154a3037`** — advanced by concurrent actors mid-task |
| `origin/master` at close | `573a983` — also advanced mid-task |
| commits landed between my base and now | `27047de` (another Mentor behaviour fix), `4edd154`, `84d9d7e` (docs) |
| rollback performed | **none** |
| deployments by me | **none** |
| production data writes | **none** |

**PROVEN:** production moved twice while this task ran. This is why the candidate is offered in two forms
(§13) and why "current master" was never assumed safe.

## 2. Proven Regression

`collect()` deduplicated evidence chips on a **global `(label, value)`** pair, ignoring which record a chip
described.

| measurement (shipped code, real dataclasses) | chips per record |
|---|---|
| **before** `5416914` | `{28: 6, 61: 6}` |
| **after** `c3aefad` | `{28: 6, 61: **1**}` |

Record 61 retained only its name; its Verification, Deadline, Funding, Fit and Readiness chips were
silently dropped and the freed budget was consumed by profile chips.

**PROVEN, and not theoretical:** **60 of 63** catalogue records share one `(verification_status, funding)`
pair (34 "fully funded", 18 "partial"); only 2 share a `(deadline_date, deadline_precision)` pair.

**Bounding fact — PROVEN:** a focused/named record is sorted first, so *the record the user asked about*
keeps its chips. The loss falls on supporting records. Classification: **USER-VISIBLE,
MEDIUM-HIGH information regression — NOT security, NOT privacy, NOT data integrity.**

## 3. Root Cause

`backend/app/services/mentor/evidence.py`, `collect()`:

```python
seen_values: set[tuple[str, str]] = set()
...
fingerprint = (chip.label, chip.value)
if chip.key in seen or fingerprint in seen_values:
    continue
```

`seen_values` is a **flat set with no owner**. The comment states the intent correctly — collapse one fact
about the same record reported by two canonical systems — but the implementation has no record dimension,
so the collapse reaches across independent records.

**PROVEN:** `chip.key` already encodes identity (`scholarship-{id}-funding`), so the key-based `seen` set
was always correct and needed no change. The regression came entirely from the added value fingerprint.

## 4. Minimal Fix

Three logic lines, in one file:

```python
_STUDENT_SCOPE = "__student__"          # new constant
fingerprint = (entry.scholarship_id, chip.label, chip.value)   # was (chip.label, chip.value)
fingerprint = (_STUDENT_SCOPE, entry.label, entry.value)       # student chips, unchanged scope
```

**Why `scholarship_id` is the correct scope — PROVEN.** Both `ScholarshipFacts` and `ApplicationFacts`
carry `scholarship_id`, and an application's chips *describe that scholarship*. Keying on it therefore
still recognises "the catalogue and the workspace both evaluated this one deadline" as the same fact,
which was the dedup's entire purpose.

Preserved and verified unchanged: focused-record priority, chip budget, ordering, all six `c3aefad` defect
fixes, evidence behaviour, deadline-precision wording, funding-`UNKNOWN` semantics, nav wrapping,
application-specific evidence prioritisation. Nothing outside `collect()` was touched.
**Not changed at all:** auth, images, ingestion, Match, Count, Dashboard, Applications, scheduler, audit.

## 5. Regression Test

`backend/tests/test_evidence_record_identity.py` — 10 tests, written **before** the fix (Task 3).

| state | result |
|---|---|
| against the buggy implementation | **5 failed, 5 passed** |
| against the fix | **10 passed** |

**PROVEN non-vacuous** — the suite fails when the fix is reverted (verified by stashing the change and
re-running: `5 failed, 5 passed`, restored to `10 passed`).

Pinned contract:
- two records with identical `(verification, funding, deadline)` each retain their own chips;
- no record is ever reduced to a bare name chip;
- identical funding/verification do not cross-suppress;
- focused priority does not suppress others;
- **the original behaviour survives**: one record's deadline reported by catalogue *and* workspace
  collapses to a single chip, including via two applications on one scholarship;
- student evidence still appended; precision wording and funding-`UNKNOWN` semantics untouched.

One assertion was corrected during this work: the first draft conflated **suppression** with **budget
truncation** at the default `limit=10` and failed spuriously. Two tests now separate them explicitly —
`limit=20` isolates suppression, and `test_the_budget_may_truncate_but_must_never_suppress` pins that a
budget-cut record keeps a *prefix* of chips rather than only its name.

## 6. Vacuous-Test Fix

The fixtures were already corrected by `c3aefad` (`TODAY = date.today()`, `FUTURE_DEADLINE = TODAY + 60d`,
`status="open"`, verified image). The remaining work was to make the condition **unrepeatable**.

`TestFixturesCannotSilentlyBecomeVacuous` — 4 tests:
1. the shared fixture is `open` with a **future** deadline and `exact` precision;
2. it satisfies `public_visibility_conditions` (an invisible fixture makes every assertion vacuous);
3. **the target record actually reaches the evidence** — asserted *before* any presentation assertion;
4. **negative control**: a closed record is absent from `build_context(...).scholarships`.

**PROVEN — and a correction worth recording.** My first negative control asserted on mentor *evidence*
and **failed**: a closed scholarship still yields application evidence, because the application exists
regardless of the listing. The vacuity mechanism is specifically `context.scholarships`, which
`build_context` sources from `dashboard.matches`. The control now asserts there and passes — and that is
why the comment in the test records that evidence alone cannot detect this.

## 7. Chip Basis Test

`frontend/src/services/mentorPresentation.test.js` — 4 new tests for `evidenceStatusWord`, which defect 5
fixed but never covered (the file previously had **no reference** to it):

- shows the verification state as the badge;
- does **not** fall back to the basis;
- never renders the basis as a second badge beside the provenance line;
- empty rather than throwing for a missing entry.

No unrelated presentation behaviour was modified.

## 8. M1 Status — **documentation only, no runtime change**

The module docstring claimed *"Both require a session. There is no public mentor route."* That
contradicted the route's own docstring (*"Safe to call before sign-in… this route has nothing private on it
to protect"*) and the implementation.

**Corrected** to state that only the answer requires a session, why the overview must be reachable before
sign-in, and that no handler accepts a user id.

`TestTheOverviewIsPublicAndTheMessageIsNot` — 4 tests pin both halves: the overview is reachable signed
out, carries **only** the five static keys, exposes no `email`/`token`/`scholarship_id`/`deadline_date`,
and `/mentor/message` still returns **401**. A fifth asserts the payload is byte-identical signed-in and
signed-out, so it cannot become user-dependent.

**PROVEN:** no runtime behaviour changed — only a docstring and tests. **Classified: documentation/test
mismatch, not a security issue** (the earlier review's characterisation stands, now with the intent made
explicit in code).

## 9. M2 Status — **unchanged, by instruction**

`ApplicationFacts` still lacks `official_source_url`; `application_evidence()` still never sets
`source_url`. A deadline chip can therefore be `verification: 'Verified'` with `source_url: None`.

**PROVEN** at the deployed revision and at `origin/master`. **NOT implemented here** — M2 remains
**TRUST/UX HARDENING, NON-BLOCKING**, and is carried to the next focused Mentor hardening pass.

## 10. Backend Tests

| suite | result |
|---|---|
| `test_evidence_record_identity.py` (new) | **10 passed** |
| `test_mentor.py` (with guard + M1 contract) | **85 passed** |
| 15 mentor/dashboard/application/matching/counting/evidence files | **1053 passed, 1 skipped** |
| mentor + regression, after rebase onto master | **96 passed** |
| py_compile / import smoke | clean |

No test was weakened, skipped or deleted. The only change to an existing test file is **additive**.

## 11. Frontend Tests

| gate | result |
|---|---|
| `npm test` | **167 passed** (9 files; was 163 — +4 new) |
| `npm run lint` | **0 errors**, 1 pre-existing `HomePage.jsx` warning |
| `npm run build` | **success** |

## 12. Browser E2E

Real local backend (uvicorn), **isolated local SQLite**, **real HTTP**, **real Chromium**. Five seeded
records including a **deliberate collision pair**: R1 "Twin Alpha" and R2 "Twin Beta" identical in
verification, funding and day count.

| # | check | result |
|---|---|---|
| 1 | open scholarship appears in the evidence | **PASS** — records 1,2,3,4,5 |
| 2 | named/focused record gets full expected evidence | **PASS** — 5 application chips |
| 3 | supporting records retain independent chips | **PASS** — 5 distinct records with evidence |
| 4 | duplicate chips within one record are deduplicated | **PASS** — max 1 deadline chip per record |
| 5 | equal chips across different records are **NOT** deduplicated | **PASS** — id1 `[Application state, Deadline]`, id2 `[Application state, Deadline]` |
| 6 | deadline precision remains truthful | **PASS** — month → "About 45 days left. The published date is not recorded to the day…" |
| 7 | unknown deadline remains unknown | **PASS** — "No published deadline to count down to." |
| 8 | funding `UNKNOWN` remains unmeasured | **PASS** — 0 Funding chips; named in *what is not known* |
| 9 | application evidence remains prioritised | **PASS** — application chips lead |
| 10 | nav does not overflow | **PASS** — 1024: `wrap=wrap`, `right=973`, no scroll, 0 interactive overflow; 320: no scroll, 0 overflow |
| 11 | zero console errors | **PASS with documented exclusions** — see below |

**Console errors (4), all excluded and attributed:**
- **1** `405 @ /api/dashboard` — **my own** deliberate `PATCH` probe; the endpoint does not accept PATCH.
- **3** `ERR_CONNECTION_TIMED_OUT @ https://www.daad.de/.../scholarship-banner-students-campus.jpg` — a
  **third-party image** on seeded record id 8, unreachable from this sandbox. **PROVEN not mine:** the E2E
  database holds my 5 records plus 63 seeded at startup, and none of my records references `daad.de`.

**Zero console errors attributable to the code I changed.**

## 13. Release Candidate

Two branches, both pushed, **master never modified**:

| branch | commit | base | purpose |
|---|---|---|---|
| `rc/mentor-evidence-record-scope` | `3c6370c` | **`3ee434c`** — the production revision at task start | minimal delta from what was live, per Task 9 |
| `rc/mentor-evidence-record-scope-on-master` | `ed58738` | `84d9d7e` (master) | rebased, for integration into master |

The rebase was clean, but `27047de` had also modified `test_mentor.py`, so **the rebased tree was
re-verified**: **96 passed** (up from 95 — `27047de`'s added test survived) and its own suite passes.
A clean rebase is not proof of correct semantics, so this was checked rather than assumed.

**Both branches are already behind master** (`573a983` at close). That is inherent to concurrent
development, not a defect in the candidate.

**No force push was used**; the rebased commit went to a new branch name so the production-based candidate
remains available for comparison.

## 14. Remaining Known Issues

| issue | classification |
|---|---|
| **M2** — application-scoped evidence cannot carry an official source URL | **PROVEN**, TRUST/UX HARDENING, non-blocking; deliberately not implemented here |
| `evidence.py` still ends without a trailing newline (pre-existing, from `c3aefad`) | **PROVEN**, cosmetic; not fixed — outside the minimal scope |
| Funding chip no longer gated by `evidence_is_usable(..., minimum=2)` (from `c3aefad`) | **PROVEN**, benign behaviour change |
| No automated test for the nav-overflow fix (defect 6) | **PROVEN** gap; verified manually in-browser instead |
| Sibling `self._is_non_logo_stored` `AttributeError` in the `--logo-only` path | **PROVEN** dead branch; **arming trap** — do not fix the call without also fixing the predicate |
| `maintenance_runs` id 250 still stale `status='running'` | **UNKNOWN** whether still active |
| Candidate branches already behind master | **PROVEN** |

## 15. Production Deployment Readiness

**Ready to integrate. Not deployed, by instruction.**

- The regression is **PROVEN**, reproduced before the fix, and demonstrably corrected after it.
- The fix is **3 logic lines in one file**, with no behavioural change outside `collect()`.
- Every guarantee the brief asked to preserve is covered by a test, including the dedup's *original*
  purpose.
- **1053 backend / 167 frontend tests pass**; lint and build clean; 11 browser E2E checks pass against a
  real stack.
- The fix is **still needed**: verified unfixed at current production `4edd154` and at `origin/master`.

**Recommended integration path:** merge `rc/mentor-evidence-record-scope-on-master` (`ed58738`) into
master — it already carries master `84d9d7e` — and re-run the Mentor suites after the merge, since master
is advancing faster than this task can track.

**Do not deploy the production-based branch** (`3c6370c`): it predates `27047de`, a Mentor behaviour fix
now in production, so promoting it would risk reverting that fix.

**PROVEN — no regression remains open in the code path this change touches.** What remains open is M2,
explicitly deferred, and the deployment decision itself, which belongs to the owner.