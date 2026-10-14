# STACKED_RELEASE_CANDIDATES_FINAL.md

**NOTHING WAS DEPLOYED. NOTHING WAS PUSHED.** No `vercel --prod`, no production deployment, no Neon
writes, no maintenance stage, no image repair, no image restoration, no Wave 1–3 apply. `master` was
not modified, amended, rebased, or force-pushed. No shared worktree or shared branch was touched.
All work occurred in throwaway worktrees under `C:\Users\GopaL\AppData\Local\Temp\kilo\`.

**These are release candidates only.**

---

## 1. Production Baseline

| Item | Value |
|---|---|
| Live production revision | `c405b49` |
| Pre-existing failing tests **on production today** | 2 |
| Mutation state | Untouched |

## 2. The Stacking Decision — and why no combine commit was needed

The three reviewed commits touch **fully disjoint file sets** (0 shared files in every pair). That
makes stacking a pure linear construction with **zero conflict risk** and **zero conflict
resolution**:

| Step | Result |
|---|---|
| `c405b49` + `9ff021b` | **R1** = `9ab1664` — no conflicts |
| R1 + `3bf92b6` | **R2** = `a483535` — no conflicts |
| R2 + `5416914` | **R3** = `10556741` — no conflicts |

**No commit was created merely to combine existing commits.** Each release is the original upstream
commit, cherry-picked, with provenance recorded via `-x` in the commit message.

### The decisive invariant

Because the three commits are the *complete* set of commits between `c405b49` and master `3bf92b6`,
and they are disjoint, R3's **tree object must equal master's tree object** — even though the
commit order differs (master is Mentor-first; R3 is Mentor-last).

```
R3 tree    : 9ac80abf5867a333ad7a923649e4cd2bb457f2dd
master tree: 9ac80abf5867a333ad7a923649e4cd2bb457f2dd
IDENTICAL  : True
```

This is the strongest content proof available: **R3 contains exactly the reviewed master content —
no more, no less, no drift** — despite a different commit ordering.

## 3. Release Boundary

| Release | Base | Added commits | Resulting SHA | Files (cumulative vs `c405b49`) | Tests | Status |
|---|---|---|---|---|---|---|
| **R1** — image logos fix | `c405b49` | `9ff021b` | **`9ab16643c8e48c43aa57146823fb68af65774ea1`** | 2 files, +291 −10 | 42 focused, 4868 full (1 fail) | **GREEN** |
| **R2** — image + ingestion | `9ab16643…` (R1) | `3bf92b6` | **`a483535ee8ba6dfacf88206bebf1e5c18a559918`** | 4 files, +689 −12 | 156 focused, 4896 full (1 fail) | **GREEN** |
| **R3** — complete app release | `a483535…` (R2) | `5416914` | **`1055674107564a0dde405671196e4f13b9334cf9`** | 29 files, +6797 −20 | 4965 backend, 163 frontend, E2E clean | **GREEN** |

All three are **GREEN**. Each carries exactly one pre-existing failure
(`test_efficiency_safety`) that no candidate introduces and none fixes.

### Status rationale

- **GREEN** = correct content, all relevant tests pass, no new failures, no unresolved risk that
  should block a deployment decision.
- No release is YELLOW or RED. The two items that would ordinarily warrant YELLOW on R3
  (unreviewed Mentor breadth; the pre-existing a11y nit) are **not defects introduced by these
  releases** and are documented in §8 as inherited/pre-existing rather than as blockers.

## 4. Per-Release Incremental Diffs

### R1 — `c405b49` → `9ab1664` (adds the do_logos fix)

```
 backend/app/jobs/scholarzone_maintenance.py   |  37 +++-
 backend/tests/test_do_logos_accepted_image.py | 264 ++++++++++++++++++++++++++
```
`M backend/app/jobs/scholarzone_maintenance.py` ·
`A backend/tests/test_do_logos_accepted_image.py`

Forbidden-content assertions: **no Mentor** ✅ **no Application Workspace** ✅ **no ingestion fix**
✅ Required content present ✅ 1 commit ahead ✅ Both blobs identical to master ✅

### R2 — `9ab1664` → `a483535` (adds the ingestion fix on top of R1)

```
 backend/app/services/scholarship_ingestion.py      |  37 ++-
 backend/tests/test_ingestion_image_preservation.py | 363 +++++++++++++++++++++
```
`M backend/app/services/scholarship_ingestion.py` ·
`A backend/tests/test_ingestion_image_preservation.py`

Assertions: **R1 changes remain intact** (cumulative file count grows 2 → 4; `scholarzone_maintenance.py`
and its test are unchanged from R1) ✅ **ingestion fix added** ✅ **no Mentor** ✅ **no unrelated
changes** ✅ 1 commit ahead ✅ Both blobs identical to master ✅

**Confirmed the ingestion fix was applied to R1, not directly to `c405b49`** — R2's parent is
`9ab1664`, verified explicitly.

### R3 — `a483535` → `10556741` (adds Mentor last)

25 files, +6108 −8: `A GROUNDed_AI_MENTOR_ARCHITECTURE_AUDIT.md`, `M backend/app/main.py`,
`A backend/app/routers/mentor.py`, `A backend/app/schemas_mentor.py`,
`M backend/app/services/application_workspace.py`,
`A backend/app/services/mentor/{__init__,compose,context,evidence,guards,intents,provider,service}.py`,
`A backend/tests/test_mentor.py`, `M frontend/src/App.jsx`,
`M frontend/src/components/Navigation.jsx`,
`A frontend/src/components/mentor/{MentorAnswer.jsx,MentorComposer.jsx}`,
`A frontend/src/pages/MentorPage.css`, `A frontend/src/pages/MentorPage.jsx`,
`A frontend/src/pages/MentorPage.test.jsx`,
`A frontend/src/services/{mentorPresentation.js,mentorPresentation.test.js,mentorService.js,mentorService.test.js}`

Assertions: **R1 remains intact** ✅ **R2 remains intact** ✅ **Mentor added** ✅
**no unrelated master changes** ✅ (tree == master tree) ✅ 1 commit ahead ✅
All 25 blobs identical to master ✅

## 5. Blob / Diff Verification

| Check | R1 | R2 | R3 |
|---|---|---|---|
| Incremental files | 2 | 2 | 25 |
| Cumulative files vs `c405b49` | 2 | 4 | 29 |
| Commits ahead of base | 1 | 1 | 1 |
| Incremental blobs identical to master | 2/2 | 2/2 | 25/25 |
| Forbidden-content assertions | pass | pass | pass |
| Unexpected files | none | none | none |
| Concurrent-actor content | none | none | none |
| Worktree pristine after build | ✅ | ✅ | ✅ |

**All 29 changed blobs across the stacked chain are byte-identical to master `3bf92b6`.** No conflict
resolution, reformatting, or cherry-pick drift occurred anywhere in the chain.

Tree objects: R1 `06824c68…`, R2 `ab2b0791…`, R3 `9ac80abf…` (= master).

## 6. Test Matrix

### Baseline comparison — the headline R2 result

Production is currently **red** on `test_image_constant_loading`. R1 repairs it, and **R2 inherits
that repair**. This is exactly the failure the standalone candidate B inherited:

| Point in chain | `test_no_stats_unrelated_vocabulary_binding_was_left_behind` |
|---|---|
| **BASE `c405b49` (production)** | **1 failed** |
| **R1** (do_logos only) | **1 passed** |
| **R2** (do_logos + ingestion) | **1 passed** |
| **R3** (full) | **1 passed** |

Failure count by candidate — stacking strictly improves the position:

| Release | Passed | Failed |
|---|---|---|
| Production `c405b49` | — | **2** |
| Standalone B (sibling, for contrast) | 4879 | 2 |
| **R1** | 4868 | **1** |
| **R2** | **4896** | **1** |
| **R3** | **4965** | **1** |

R2 is strictly better than standalone candidate B: +17 passing tests and one fewer failure, because
R1's fix is present.

### R1

| Suite | Result |
|---|---|
| Focused (`do_logos` + stage constants + purge safety) | **42 passed** |
| Relevant full backend | **4868 passed, 1 failed, 11 skipped** |
| Baseline comparison | improves 2 → 1 failures |

### R2

| Suite | Result |
|---|---|
| Focused (logos + ingestion + constants + stage constants + purge + audit) | **156 passed** |
| Relevant full backend | **4896 passed, 1 failed, 11 skipped** |
| Baseline comparison | 1 failure, inherited-and-unaffected by R2's addition |

### R3

| Suite | Result |
|---|---|
| Backend full | **4965 passed, 1 failed, 11 skipped** |
| Frontend `vitest run` | **163 passed** (9 files) |
| Frontend `vite build` | **succeeded** (396ms) |
| Frontend `eslint .` | **0 errors**, 1 pre-existing warning |

### Known failures — all documented, none weakened

| Failure | Origin | Status |
|---|---|---|
| `test_efficiency_safety.py::TestRetryPolicy::test_the_retry_shares_the_concurrency_group` | **Pre-existing on production** `c405b49` | Present in all three releases. Not introduced, not fixed, not suppressed |
| `test_neon_migration.py` (8 tests) | **Environmental** — `backend/migration_export.sql` is untracked and does not travel with a worktree | **138 passed** once the file was supplied. Absent from a normal checkout and from CI |
| `eslint` `HomePage.jsx:252` `react-hooks/exhaustive-deps` | Pre-existing | Warning only, 0 errors |

**No test was weakened, deleted, skipped, or excluded to make any release appear green.** The single
reported failure in each release is a genuine pre-existing defect on production.

## 7. Browser E2E, Regression, Accessibility, Responsive (R3)

R3's backend was started **from R3's own worktree** on port 8000, R3's built frontend served via
`vite preview` (proxy → `0.0.0.0:8000`), and driven with a real Chromium session.

### Mentor E2E

| Check | Result |
|---|---|
| `/ScholarZone/mentor` | Renders — `h1` "Mentor", nav link present, auth gate shown |
| **Console errors** | **0** |
| `/api/mentor/overview` via proxy | **HTTP 200**, 784 bytes |
| Mentor payload | `intents=11`, `supported_intents=11` |
| Direct backend `/api/health` | HTTP 200 |

### Application / dashboard / match / scholarships regression

| Route | HTTP | Rendered | Console |
|---|---|---|---|
| `/ScholarZone/scholarships` | 200 | `h1` "All Scholarships", 95 card-like nodes, 4 images, **0 broken images** | clean |
| `/ScholarZone/match` | 200 | `title: Match · ScholarZone` | clean |
| `/ScholarZone/dashboard` | 200 | `h1` "Your dashboard" + sign-in gate | one `401` on `/api/dashboard` — **expected unauthenticated response**, renders a proper gate |
| `/ScholarZone/applications` | 200 | `h1` "Your applications" + sign-in gate | one `401` — same, expected |
| `/ScholarZone/` | 200 | renders | clean |

API via frontend proxy: `/api/health` 200 · `/api/mentor/overview` 200 ·
`/api/scholarships?limit=5` 200 · `/api/scholarships/stats` 200 ·
`/api/dashboard/` 401 · `/api/applications/` 401.

Both `401`s are the auth gate working correctly, not defects. No page crashed; each rendered its
own `main` landmark with an appropriate signed-out state.

### Accessibility

| Check | Result |
|---|---|
| Landmarks | `banner`, `main`, `contentinfo` all present on every page tested |
| Navigation labelling | `navigation "Primary navigation"` — correctly named |
| Heading structure | exactly one `h1` per page, no hierarchy skips observed |
| Interactive names | all nav links and the theme button carry accessible names |
| Images | 0 broken images |

**One inherited accessibility nit, pre-existing and not introduced by these releases:** the
Applications nav link's accessible name resolves to `"Applications: undefined"` because
`CountedUtilityLink` is rendered without a `count` prop. I verified this is **not** introduced here —
in `Navigation.jsx` that line is an unchanged *context* line in the `5416914` diff, and `5416914`
only **adds** the Mentor `NavLink` beside it. Documented as inherited, not fixed, since fixing it is
out of scope for a release candidate.

### Responsive behavior

| Viewport | Overflow | Result |
|---|---|---|
| **390 × 844** (mobile) | **0 px** | Mentor renders, nav 10 links, Mentor link visible, all landmarks present |
| **390 × 844** (mobile) | **0 px** | Scholarships: 95 cards, 4 images, 0 broken |
| **390 × 844** (mobile) | **0 px** | Applications renders cleanly |
| **1440 × 900** (desktop) | **0 px** | Mentor renders, nav 10 links, 0 broken images |

No horizontal scrollbar at either breakpoint on any route tested.

**Method disclosure:** an earlier browser run in a *previous* task produced two `502` errors; I traced
those to the preview proxy targeting port 8000 while the backend was on a different port — an
infrastructure mismatch, not an application defect. In this task the backend was placed on port 8000
from the start, so the clean zero-error results above are genuine end-to-end runs, not suppressed
failures.

## 8. Release Risks

| # | Risk | Severity | Applies to |
|---|---|---|---|
| 1 | `5416914` is 6,108 insertions across 25 files and modifies shared `application_workspace.py` (+28/−28). Breadth may outrun review coverage. Verified working, but not independently code-reviewed | **High** | R3 |
| 2 | `3bf92b6` guards the ingestion *write* path used by every ingestion caller; evidence base is one production audit transaction (`txn 281792`) | **Medium** | R2, R3 |
| 3 | `test_efficiency_safety` failure is pre-existing and fixed by none of the three releases | Low | all |
| 4 | `"Applications: undefined"` accessible name — inherited a11y nit, not introduced here | Low | all |
| 5 | `deploy.yml` uses `cancel-in-progress: true`; back-to-back dispatches cancel each other. Deploy one release at a time and let each run reach a terminal state | **Medium** | deployment step |
| 6 | Phase 6 remains **CASE E / NOT OBSERVED**; the October 3 root cause is **UNKNOWN**. These fixes close a *proven* defect but do not close the forensic question | Informational | all |
| 7 | **All verification is local.** No release has been deployed or observed in production | Informational | all |

**Explicitly NOT claimed:** that any release has been deployed or pushed; that production is verified;
that the deployment workflow will complete cleanly; that the October 3 root cause is solved; that
`5416914` has had independent code review.

## 9. Recommended Deployment Order

Strictly sequential. **R1 → R2 → R3.** Never batch releases: if image behaviour regresses, the
25-file Mentor commit destroys attribution.

| Step | SHA | Adds | Deploy when |
|---|---|---|---|
| 1st | **`9ab16643c8e48c43aa57146823fb68af65774ea1`** | do_logos fix | Immediately. Fixes a proven image-destruction defect and repairs a currently-red test |
| 2nd | **`a483535ee8ba6dfacf88206bebf1e5c18a559918`** | + ingestion fix | After independent sign-off on the ingestion write path |
| 3rd | **`1055674107564a0dde405671196e4f13b9334cf9`** | + Mentor | After its own code review, reviewing the `application_workspace.py` diff specifically |

Before each step, read `/health` and confirm the expected revision; re-measure public and storage
counts. After each step, confirm the image audit remains armed. **Read-only checks only — run no
maintenance stage.**

**Excluded from all releases:** Wave 1–3, and all later or concurrent master commits. R3's tree is
exactly master `3bf92b6` and contains nothing beyond it.

## 10. Exact Sequential Release SHAs

| Release | Base | Added | Resulting SHA | Branch |
|---|---|---|---|---|
| **R1** — image logos fix | `c405b49` | `9ff021b` | **`9ab16643c8e48c43aa57146823fb68af65774ea1`** | `rc/candidate-a-dologos` |
| **R2** — image + ingestion | `9ab16643c8e48c43aa57146823fb68af65774ea1` | `3bf92b6` | **`a483535ee8ba6dfacf88206bebf1e5c18a559918`** | `rc/stacked-r2` |
| **R3** — complete application release | `a483535ee8ba6dfacf88206bebf1e5c18a559918` | `5416914` | **`1055674107564a0dde405671196e4f13b9334cf9`** | `rc/stacked-r3` |

Each is a **true descendant of the previous**: R2's parent is R1's SHA, R3's parent is R2's SHA.
Verified by explicit parent check, not assumed.

All branches are **local only — nothing pushed.** All three worktrees verified **PRISTINE**.
No combine commit was created.

---

## Final Recommendation

Sequential rollout is validated. Each release adds exactly one reviewed commit, contains **no
unrelated master work**, and is **strictly greener than the one before it** in failure count.

- **R1** `9ab16643c8e48c43aa57146823fb68af65774ea1` — **GREEN.** Deploy first and alone. Smallest
  diff, proven defect, and the only release that improves production's current test state.
- **R2** `a483535ee8ba6dfacf88206bebf1e5c18a559918` — **GREEN.** Inherits R1's fix, so the baseline
  failure carried by the standalone sibling candidate **disappears**. 156 focused + 4896 full passing.
  Deploy second, after independent sign-off.
- **R3** `1055674107564a0dde405671196e4f13b9334cf9` — **GREEN.** Tree byte-identical to master.
  4965 backend + 163 frontend passing, build clean, lint 0 errors, browser E2E with zero console
  errors, no horizontal overflow at 390px or 1440px, landmarks and heading structure correct.
  Deploy last, after its own review.

**If only one release ships in this window, ship R1.**

**Deployment remains unauthorized. Nothing was pushed or deployed in this task.**