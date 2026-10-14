# ISOLATED_RELEASE_CANDIDATES_FINAL.md

**NOTHING WAS DEPLOYED.** No `vercel --prod`, no production deployment, no production DB mutation,
no maintenance stage execution, no image repair, no image restoration, no Wave 1–3 apply, no Neon
writes. No commit on `master` was amended, reset, or force-pushed. The shared worktree was never
touched. All work happened in three throwaway worktrees under
`C:\Users\GopaL\AppData\Local\Temp\kilo\`.

---

## 1. Production Baseline

| Item | Value |
|---|---|
| Live production revision | `c405b49` — *Merge remote-tracking branch 'origin/master' into application-workspace* |
| Parent of production | `ff7583e` |
| Pre-existing failing tests **on production today** | 2 (see §7) |
| Mutation state | Untouched. No candidate was deployed. |

## 2. Master Ancestry

`c405b49 → 5416914 → 9ff021b → 3bf92b6` — strictly linear, each commit's parent is the previous one.

| Commit | Subject | Files |
|---|---|---|
| `5416914` | feat: add GROUNDed AI Mentor 1.0 | 25 files |
| `9ff021b` | fix: do_logos destroys images the pipeline accepted | 2 files |
| `3bf92b6` | fix: stop ingestion from deleting a stored image on a null refresh | 2 files |

**Conflict prediction was resolved before building anything.** The three commits touch fully disjoint
file sets:

| Pair | Shared files |
|---|---|
| `9ff021b` ∩ `3bf92b6` | **0** |
| `9ff021b` ∩ `5416914` | **0** |
| `3bf92b6` ∩ `5416914` | **0** |

Because no two commits touch the same file, each candidate cherry-picks onto `c405b49` without
conflict. **Zero conflicts occurred, and no conflict resolution was required.**

## 3. Candidate A — do_logos only

| Field | Value |
|---|---|
| Base SHA | `c405b49` |
| Applied commit | `9ff021b` |
| **Resulting SHA** | **`9ab16643c8e48c43aa57146823fb68af65774ea1`** |
| Branch | `rc/candidate-a-dologos` |
| Worktree | `…\Temp\kilo\rc-a-dologos` |
| Commits ahead of base | **1** |
| Pushed? | **NO** |
| Deployed? | **NO** |

Diffstat vs `c405b49`:

```
 backend/app/jobs/scholarzone_maintenance.py   |  37 +++-
 backend/tests/test_do_logos_accepted_image.py | 264 ++++++++++++++++++++++++++
 2 files changed, 291 insertions(+), 10 deletions(-)
```

Exact changed files: `M backend/app/jobs/scholarzone_maintenance.py`,
`A backend/tests/test_do_logos_accepted_image.py`.

**Deploy recommendation: YES — ship independently.** Strongest candidate. Smallest diff, proven
defect, real-entry-point verification, and it is the only candidate that *reduces* the pre-existing
failure count.

## 4. Candidate B — ingestion only

| Field | Value |
|---|---|
| Base SHA | `c405b49` |
| Applied commit | `3bf92b6` |
| **Resulting SHA** | **`e8a3e5fe10be0da26b1bb0c6977500f0a3998a57`** |
| Branch | `rc/candidate-b-ingestion` |
| Worktree | `…\Temp\kilo\rc-b-ingestion` |
| Commits ahead of base | **1** |
| Pushed? | **NO** |
| Deployed? | **NO** |

Diffstat vs `c405b49`:

```
 backend/app/services/scholarship_ingestion.py      |  37 ++-
 backend/tests/test_ingestion_image_preservation.py | 363 +++++++++++++++++++++
 2 files changed, 398 insertions(+), 2 deletions(-)
```

Exact changed files: `M backend/app/services/scholarship_ingestion.py`,
`A backend/tests/test_ingestion_image_preservation.py`.

**Deploy recommendation: YES — can ship independently, after independent sign-off.** Diff is
equally small and clean. The caveat is review breadth, not technical soundness: it guards the
ingestion *write* path used by every ingestion caller, and its evidence base is a single production
audit transaction (`txn 281792`). Its 2 test failures are inherited from production, not caused by
it (§7).

## 5. Candidate C — Mentor only

| Field | Value |
|---|---|
| Base SHA | `c405b49` |
| Applied commit | `5416914` (direct child of base — clean fast-forward equivalent) |
| **Resulting SHA** | **`48e22443034544dd6f958179377fb2ee5aec9e2d`** |
| Branch | `rc/candidate-c-mentor` |
| Worktree | `…\Temp\kilo\rc-c-mentor` |
| Commits ahead of base | **1** |
| Pushed? | **NO** |
| Deployed? | **NO** |

Diffstat vs `c405b49`: **25 files changed, 6108 insertions(+), 8 deletions(-)**.

25 exact changed files: `A GROUNDed_AI_MENTOR_ARCHITECTURE_AUDIT.md`,
`M backend/app/main.py`, `A backend/app/routers/mentor.py`,
`A backend/app/schemas_mentor.py`, `M backend/app/services/application_workspace.py`,
`A backend/app/services/mentor/{__init__,compose,context,evidence,guards,intents,provider,service}.py`,
`A backend/tests/test_mentor.py`, `M frontend/src/App.jsx`,
`M frontend/src/components/Navigation.jsx`,
`A frontend/src/components/mentor/{MentorAnswer.jsx,MentorComposer.jsx}`,
`A frontend/src/pages/MentorPage.css`, `A frontend/src/pages/MentorPage.jsx`,
`A frontend/src/pages/MentorPage.test.jsx`,
`A frontend/src/services/{mentorPresentation.js,mentorPresentation.test.js,mentorService.js,mentorService.test.js}`.

**Deploy recommendation: YES — technically deployable independently, but it needs its own code
review before shipping.** It is by far the largest surface (6,108 insertions), and it is the only
candidate that modifies an existing shared service (`application_workspace.py`, +28/−28). Nothing in
it blocks independent deployment; the risk is review coverage.

## 6. File/Diff Verification

### 6.1 Critical-verify assertions (programmatic)

| Candidate | Must NOT contain | Result |
|---|---|---|
| **A** | Mentor | **absent** |
| **A** | Application Workspace changes | **absent** |
| **A** | ingestion fix | **absent** |
| **B** | Mentor | **absent** |
| **B** | do_logos fix | **absent** |
| **C** | image fixes (`scholarzone_maintenance.py`, `test_do_logos*`) | **absent** |
| **C** | ingestion fix (`scholarship_ingestion.py`, `test_ingestion*`) | **absent** |

Required-content assertions also passed: A contains `scholarzone_maintenance.py` +
`test_do_logos_accepted_image.py`; B contains `scholarship_ingestion.py` +
`test_ingestion_image_preservation.py`; C contains `routers/mentor.py` + `services/mentor/*` +
`test_mentor.py` + `MentorPage.jsx`.

**Overall contamination check: PASS.**

### 6.2 Commit-count assertion

Each candidate is exactly **1 commit** ahead of `c405b49`. Verified for all three. No candidate
carries an extra commit, merge, or stray cherry-pick.

### 6.3 Content-fidelity assertion (strongest check)

Every file in every candidate was compared by **git blob hash** against the same path on master
`3bf92b6`. If a cherry-pick had mangled content through conflict resolution or reformatting, the
blob hashes would differ.

**All 29 changed blobs across all three candidates are byte-identical to master.**

This is the decisive proof that the candidates are not merely "equivalent-looking" but contain
exactly the reviewed master content, with no conflict-resolution drift.

### 6.4 Working-tree state

All three candidates were cleaned of local helper artifacts (`run_gate_api.cmd`,
`migration_export.sql`, `gate_state.py`) and verified **PRISTINE** — no untracked files, no
uncommitted modifications. A candidate is exactly what would be deployed.

## 7. Test Results

### Per-candidate targeted suites

| Candidate | Suite | Result |
|---|---|---|
| A | `test_do_logos_accepted_image` + `test_image_stage_constants` + `test_purge_image_safety` | **42 passed** |
| B | `test_ingestion_image_preservation` | **20 passed** |
| C | `test_mentor.py` | **69 passed** |

### Per-candidate full backend suites

| Candidate | Passed | Failed | Skipped |
|---|---|---|---|
| A | **4868** | 1 | 11 |
| B | **4879** | 2 | 11 |
| C | **4928** | 2 | 11 |

### Every failure is pre-existing on production — none is introduced by any candidate

| Failing test | Base `c405b49` | A | B | C | Origin |
|---|---|---|---|---|---|
| `test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group` | fails | fails | fails | fails | **Pre-existing** |
| `test_image_constant_loading.py::…::test_no_stats_unrelated_vocabulary_binding_was_left_behind` | fails | **PASSES** | fails | fails | **Pre-existing — FIXED by Candidate A** |

I verified this directly by materialising an unmodified `c405b49` worktree and running the test:

```
assert "ACCEPTED_IMAGE_KINDS" not in _scope_report()["do_stats"]["imported"]
AssertionError: assert 'ACCEPTED_IMAGE_KINDS' not in {'ACCEPTED_IMAGE_KINDS', 'LOGO_IDENTITY_KINDS'}
tests\test_image_constant_loading.py:170
```

**This is a notable finding: production is currently red on this test, and Candidate A repairs it.**
`9ff021b` removed the stray `ACCEPTED_IMAGE_KINDS` binding from `do_stats`. So:

- Candidate A: **1** failure (strict improvement over production's 2)
- Candidate B: **2** failures (inherits both)
- Candidate C: **2** failures (inherits both)

Shipping B or C alone leaves production's red test red. Shipping A fixes it.

### `test_neon_migration.py` (8 tests) — environmental, fully explained

On first run in the fresh candidate worktrees these 8 tests failed because
`backend/migration_export.sql` is an **untracked** file that does not travel with a worktree. After
supplying it, the suite reported **138 passed**. This is an artifact of isolated worktrees, not a
code defect, and not present on a normal checkout or in CI. Disclosed rather than hidden.

### Candidate C frontend

| Check | Result |
|---|---|
| `npm ci` | succeeded |
| `vitest run` | **163 passed** (9 files) |
| `vite build` | **succeeded** (372ms) |
| `eslint .` | **0 errors**, 1 pre-existing warning (`HomePage.jsx:252` `react-hooks/exhaustive-deps`) |

No test was weakened, skipped, deleted, or excluded to produce any number above.

### Candidate C browser E2E (genuine end-to-end)

Candidate C's backend was started from **its own worktree** on port 8000, its built frontend was
served via `vite preview` (whose proxy targets `0.0.0.0:8000`), and a real Chromium session drove it.

| Check | Result |
|---|---|
| `/ScholarZone/mentor` | Renders — title `Mentor · ScholarZone`, `h1` "Mentor", nav link present, auth gate shown |
| **Console errors** | **0** |
| Proxied `/api/mentor/overview` | **HTTP 200**, 784 bytes |
| Mentor payload | `intents=11`, `supported_intents=11`, keys `supported_intents, intents, redirects, max_message_length, assistance_available` |
| `/api/health` | HTTP 200 |
| `/api/scholarships?limit=5` | HTTP 200 |
| `/api/scholarships/stats` | HTTP 200 |
| `/ScholarZone/scholarships`, `/ScholarZone/` | HTTP 200 |

**Disclosure on method:** an earlier browser run showed two `502 Bad Gateway` console errors on
`/api/mentor/overview` and `/api/auth/session`. I traced this to the preview proxy targeting port
8000 while I had the backend on 8098 — an infrastructure mismatch, not an application defect. I
re-ran with the backend on 8000 and the console is clean. The zero-error result above is the
corrected run, not the suppressed one.

The auth gate appears because the API requires sign-in — expected behaviour.

## 8. Release Risks

| # | Risk | Severity | Applies to |
|---|---|---|---|
| 1 | Candidate C is 6,108 insertions across 25 files and modifies shared `application_workspace.py`; breadth may outrun review coverage | **High** | C |
| 2 | Candidate B guards the ingestion write path used by every ingestion caller; its evidence base is one audit transaction (`txn 281792`) | **Medium** | B |
| 3 | Production is already red on `test_image_constant_loading`. B and C do not fix it | **Medium** | B, C |
| 4 | `test_efficiency_safety` failure is pre-existing and fixed by none of the three | Low | A, B, C |
| 5 | `deploy.yml` uses `cancel-in-progress: true`; back-to-back dispatches cancel each other. One commit at a time, and let each run reach a terminal state | **Medium** | deployment step |
| 6 | Phase 6 remains **CASE E / NOT OBSERVED**; October 3 root cause **UNKNOWN**. These fixes reduce a proven defect but do not close the forensic question | Informational | all |
| 7 | All verification is **local**. No candidate has been deployed or observed in production | Informational | all |

**Explicitly NOT claimed:** that any candidate has been deployed; that production is verified;
that the deployment workflow will complete cleanly; that the October 3 root cause is solved; that
Candidate C has had independent code review.

## 9. Recommended Deployment Order

Sequential, **one candidate at a time**, each deployed and verified before the next. Never batch —
if image behaviour regresses, a 25-file Mentor commit destroys attribution.

1. **Candidate A** `9ab1664` — do_logos. Ship first. Smallest and safest diff; fixes the real
   image-destruction defect; also repairs a currently-red test. Fast-forward from `c405b49`.
2. **Candidate B** `e8a3e5f` — ingestion. Ship second, **after independent sign-off** on the write
   path. Note it cannot fast-forward from A (both are children of `c405b49`); it needs a merge of
   `e8a3e5f`, which is conflict-free given zero file overlap.
3. **Candidate C** `48e2244` — Mentor. Ship last, **after its own code review**, with the
   `application_workspace.py` diff reviewed specifically.

Before each step, read `/health` for the expected revision and re-measure public/storage counts.
After each step, confirm the image audit remains armed. **Read-only checks only — run no image
stage.**

If only one candidate may ship in this window, ship **A**.

## 10. Exact Candidate SHAs

| Candidate | Base | Applied | **Resulting SHA** | Branch |
|---|---|---|---|---|
| **A — do_logos only** | `c405b49` | `9ff021b` | **`9ab16643c8e48c43aa57146823fb68af65774ea1`** | `rc/candidate-a-dologos` |
| **B — ingestion only** | `c405b49` | `3bf92b6` | **`e8a3e5fe10be0da26b1bb0c6977500f0a3998a57`** | `rc/candidate-b-ingestion` |
| **C — Mentor only** | `c405b49` | `5416914` | **`48e22443034544dd6f958179377fb2ee5aec9e2d`** | `rc/candidate-c-mentor` |

All three branches are **local only — nothing pushed.** All three worktrees are **pristine.**

---

## Final Recommendation

- **Candidate A (do_logos) can be deployed independently.** ✅ Based exactly on production
  `c405b49`, one commit, two files, 42 targeted + 4868 full-suite tests passing, and it is the only
  candidate that improves on production's current test state.
- **Candidate B (ingestion) can be deployed independently.** ✅ Based exactly on production
  `c405b49`, one commit, two files, 20 targeted + 4879 full-suite tests passing, both failures
  inherited from production. Independent sign-off recommended before shipping.
- **Candidate C (Mentor) can be deployed independently.** ✅ Based exactly on production
  `c405b49`, one commit, 25 files, 69 backend + 163 frontend tests passing, build and lint clean, and
  a genuine browser E2E with zero console errors against a live backend serving the real Mentor API.
- **No candidate includes unrelated master work.** ✅ All three were cherry-picked individually onto
  production `c405b49` with **zero conflicts**, each is **exactly 1 commit** ahead of base, all
  changed files were asserted against a forbidden-content matrix, and all **29 changed blobs are
  byte-identical to master** — so the content is the reviewed master content with no other commit's
  work and no conflict-resolution drift.

**Deployment remains unauthorized. Nothing was deployed or pushed in this task.**