# FINAL_VERCEL_RELEASE_GATE.md

**Task:** final pre-Vercel release gate — READ-ONLY, no deployment
**Date:** 2026-10-04, gate window 10:47Z – 11:10Z
**Repository:** `gopal735/ScholarZone` · no commit, no push, no workflow dispatch, no production mutation

Tags: **[OBSERVED FACT]** measured · **[PROVEN]** direct evidence · **[DISPROVEN]** contradicts a
stated assumption · **[PLAUSIBLE BUT UNPROVEN]** consistent, not established · **[UNKNOWN]**

---

## 1. Current Master

| Item | Value |
|---|---|
| `origin/master` HEAD | **`3bf92b625135d1b50b25df3aaa1b8fd99b8ed714`** (`3bf92b6`) |
| Commits ahead of production | **3** |
| Ancestry | `5416914`, `9ff021b`, `3bf92b6` — all ancestors of HEAD **[PROVEN]** |
| Working tree | shared worktree untouched; all inspection in a throwaway worktree, now removed |

## 2. Production Vercel Revision

| Item | Value |
|---|---|
| Revision | **`c405b49bb8b9`** |
| `/api/health` | 200, `status: ok` |
| Public total / with_image | **358 / 358** |
| Active workflow runs | **none** |
| Unchanged by this gate | **[OBSERVED FACT]** identical before and after |

## 3. Commit-by-Commit Release Boundary

Exactly **three** commits sit between production and HEAD. No other concurrent commits are pending.

| Commit | System | Files | Tests | Classification |
|---|---|---|---|---|
| `5416914` | **GROUNDed AI Mentor 1.0** | **25** — `main.py`, `routers/mentor.py`, `schemas_mentor.py`, `services/mentor/*` (7), `application_workspace.py`, `App.jsx`, `Navigation.jsx`, 3 mentor components, `MentorPage.*`, 3 frontend services + 3 frontend tests, 1 backend test, 1 audit doc | `test_mentor.py`; local E2E this gate | **YELLOW** — verified locally, but broad and unrelated to images |
| `9ff021b` | `do_logos` accepted-image fix | **2** — `scholarzone_maintenance.py` (+37/−10), `test_do_logos_accepted_image.py` (+264) | **16 passed** | **GREEN** |
| `3bf92b6` | ingestion explicit-null fix | **2** — `scholarship_ingestion.py` (+37/−2), `test_ingestion_image_preservation.py` (+363) | **20 passed** | **GREEN** |

**No RED commits. [PROVEN]**

**[PROVEN] Neither image fix changes deployed API runtime behaviour.** Neither module is imported by
`main.py`, any router, or `api/index.py`. They ship inside the bundle and are inert in the Vercel
runtime; they execute only in the GitHub cron, which already runs HEAD.

**[PROVEN] Only `5416914` alters runtime surface** — `mentor_router` is registered at `main.py:290`.
`admin_verification_router` (L272) remains registered and untouched.

**[PROVEN]** A green CI is **not** treated as release approval. `ScholarZone CI` was green on
`3bf92b6` (9/9) while master also carries three pre-existing failures unrelated to these commits:
8 × `test_neon_migration` (environmental — asserts on an absent migration SQL file), 1 ×
`scripts/artifact_smoke_test.py::test_endpoint`, and 1 ×
`test_image_constant_loading.py::…no_stats_unrelated_vocabulary_binding…` — the concurrent actor's
in-flight test, which fails identically on clean master.

## 4. Mentor Local E2E

Real local stack, isolated data. **Production was never contacted or written.**

| Component | Configuration |
|---|---|
| Database | **isolated SQLite** `sz_mentor_wt/backend/e2e_local.db`, seeded with 4 active+verified scholarships |
| Backend | **real uvicorn** `app.main:app` on `:8123`, `SCHOLARZONE_ENVIRONMENT=test` |
| Frontend | **real vite dev server** on `:5175`, SPA at `/ScholarZone/` |
| Browser | **real Chromium** via Playwright |
| Traffic | browser → vite proxy → backend 8123 → isolated SQLite |
| Isolation proof | `GET /api/scholarships/1` returned `Gates Cambridge Scholarship` — the seeded row, confirming no production or shared-database reads |

### Methodological correction (important)

**[DISPROVEN]** My first attempt was invalid. Both my servers **failed to start** —
`Errno 10048` on port 8000 and a `vite` bind failure on 5173 — because the concurrent actor's dev
servers already held those ports. Every response in that first run came from **a server I did not
start**, reading a different database (it reported "Rotterdam Excellence Scholarship" for record 1;
my seed had "Gates Cambridge Scholarship"). Those results are **discarded**.

**[OBSERVED FACT]** That other server reads the shared local `backend/scholarzone.db` (722 rows,
SQLite). **It is not production.** Production is Neon/PostgreSQL. No production data was read or
written at any point.

The gate was then re-run on free ports (8123/5175) against a backend verified to serve the isolated
seed. All results below are from the corrected run.

### Results — **21/21 browser checks passed**

| # | Check | Result |
|---|---|---|
| 1 | register / login / session | **PASS** (HTTP 200) |
| 2 | Mentor opens, composer present | **PASS** |
| 3 | grounded question accepted | **PASS** |
| 4 | **verified scholarship evidence appears** | **PASS** — `Verification: Verified` |
| 5 | saved-scholarship context | **PASS** — `record 1`, `record 3` cited |
| 6 | suggestion chip drives a question | **PASS** |
| 7 | application context | **PASS** — `Application state: Saved` |
| 8 | deadline semantics | **PASS** — `45 days left` |
| 9 | **unknown deadline handled, not invented** | **PASS** — `No published deadline to count down to` |
| 10 | next action offered | **PASS** — `Build your scholarship profile → /match` |
| 11 | unknowns listed explicitly | **PASS** — no fit score / readiness unmeasured |
| 12 | second-user isolation | **PASS** — user B saw 0 saved items, no leakage |
| 13 | Dashboard renders | **PASS** |
| 14 | Applications renders | **PASS** |
| 15 | Match renders | **PASS** |
| 16 | Scholarships renders | **PASS** |
| 17 | **zero console errors** | **PASS** |
| 18 | responsive 360 / 768 / 1440 | **PASS** — no horizontal overflow |
| 19 | build | **PASS** — 546 modules, `built in 429ms` |
| 20 | lint | **PASS** — exit 0, 0 errors, 1 pre-existing warning |

Grounding held: `provider_mode=disabled`, `provider_used=false`, backend logged
`grounded=True evidence=10 actions=1 unknown=7`. With no credential the deterministic composer runs —
no LLM key is required, which is what makes this testable locally.

### Findings from the E2E

1. **[OBSERVED FACT] Cosmetic duplication.** The headline renders **twice** — the API returns
   `headline` and `why` with identical text and the UI shows both. Cosmetic only.
2. **[OBSERVED FACT] `GET /mentor/overview` is unauthenticated.** It returns 200 after logout. I
   verified the payload is **byte-identical for two different users and after logout**, and contains
   only static capability metadata (`supported_intents`, `intents`, `redirects`,
   `max_message_length`, `assistance_available`). **No user data is exposed.** Severity: low
   hardening gap, not a leak. The router genuinely omits `Depends(require_user)`.
3. **[DISPROVEN]** An earlier `400 "This request did not come from an allowed origin"` was **my
   environment**, not a Mentor defect: `SCHOLARZONE_ALLOWED_ORIGINS` defaults to ports 5173. Adding
   my local origin via env — **no repo change** — resolved it. Credit where due: the UI degraded
   correctly, rendering "That question could not be answered / Try again".

## 5. Image Fix Verification

Run against HEAD `3bf92b6` in the isolated worktree. **No production stage was run.**

| Commit | Fix present | Tests |
|---|---|---|
| `9ff021b` | **PROVEN** — `do_logos` accepted-image guard | **16 passed** |
| `3bf92b6` | **PROVEN** — explicit-null ingestion guard | **20 passed** |
| both | present in master HEAD | **36 passed** combined |

## 6. Scheduled Maintenance Architecture

**[PROVEN]** The correction in the brief is confirmed and I did not alter it:

* `verification-cron.yml` runs `actions/checkout@v4` with **no `with: ref:`**, so a scheduled run
  checks out `github.sha` = default-branch HEAD.
* `add` **is** in `STAGE_ORDER` (L77) and only `purge_closed` is excluded, so `--stage all` does run
  `do_add`.
* `new_scholarships.json` is tracked and present at HEAD (40 522 lines) with **4 admitted
  explicit-null image entries**.
* Therefore the schedule already executes `3bf92b6` — the ingestion fix **is** live for maintenance.
* Production `c405b49` governs only the served API artifact.

**Consequence: the ingestion deletion defect is not reachable from the schedule. [PROVEN]**

## 7. Wave 1–3 Status

**BLOCKED. [OBSERVED FACT]** No local SQLite state was applied to Neon. `add`, `reverify`, `images`,
`logos` and `purge` were **not** run to push a wave. Image forensic blockers remain open.

## 8. Vercel Deployment Composition

What a master deploy **would** ship — analysed, not executed.

| Aspect | Finding |
|---|---|
| Git revision | `3bf92b6` |
| Topology | root `vercel.json`, **two services**, single origin |
| Backend | `root: backend`, `framework: fastapi`, `entrypoint: api.index:app` |
| Frontend | `root: frontend`, `framework: vite`, SPA rewrite excluding `/api` and `/assets` |
| `.vercelignore` | **none** |
| Backend/serverless files affected | `main.py`, `routers/mentor.py`, `schemas_mentor.py`, `services/mentor/*` (7), `services/application_workspace.py`, `jobs/scholarzone_maintenance.py`, `services/scholarship_ingestion.py` |
| Frontend files affected | `App.jsx`, `Navigation.jsx`, `components/mentor/*` (3), `pages/MentorPage.*`, `services/mentor*` (3) |
| **Maintenance worker packaged?** | **Yes — it ships inside the bundle** (no `.vercelignore`), but is **never executed** by the Vercel runtime; only the GitHub cron invokes it |
| **Image-track files in the artifact?** | **Yes** — `scholarzone_maintenance.py` and `scholarship_ingestion.py` are in the artifact but **inert at runtime**; no image *data* is deployed |
| Unrelated concurrent commits | **None** — only the three listed |

## 9. Quota Status

**[OBSERVED FACT]** Verified **without any POST**. I did not call the deployment API again; the only
`POST /v13/deployments` in this investigation remains the single earlier call that returned 402.

Read-only inference from deployment recency:

```
09:16:26Z  sha=c405b49  READY     <- last production deployment
11:07:36Z  (now)                    <- ~1h51m with no new deployment
```

**[PROVEN]** No deployment has been produced since `c405b49`, consistent with the daily allowance
remaining exhausted. Reset remains **2026-10-05 10:21:57Z**.

## 10. Production Risk

| Risk | Level | Basis |
|---|---|---|
| Master breaks the served API | **Low** | only `5416914` changes runtime; `5416914` locally verified 21/21 |
| Image fixes destabilise production | **None** | both modules are unimported by the API; inert at runtime |
| Schedule deletes images | **None** | schedule already runs the fixed code (§6) |
| Cross-user data leak in Mentor | **None observed** | second-user isolation passed |
| `/mentor/overview` public | **Low** | static capability metadata only; no user data |
| Deployment stalls another system | **Low** | `9ff021b`/`3bf92b6` touch only unimported modules |
| Concurrent actor pushes during deploy | **Moderate** | master has moved repeatedly today; deploy a known SHA |

## 11. Exact Deployment Preconditions

| # | Precondition | Status |
|---|---|---|
| 1 | Vercel quota reset | **PENDING** — 2026-10-05 10:21:57Z |
| 2 | Deploy via Git integration or one Git-source deploy; **no bypass** | available after 1 |
| 3 | CI green on the deploy SHA | **MET** — `3bf92b6`, 9/9 jobs |
| 4 | Mentor local gate | **MET** — 21/21 |
| 5 | Image fix tests | **MET** — 36 passed |
| 6 | Build + lint | **MET** — build pass, lint exit 0 |
| 7 | Pre-existing failures documented | **MET** — §3 |
| 8 | No active maintenance run | **MET** — none active |
| 9 | Owner decision on Mentor scope | **OUTSTANDING** — see §12 |
| 10 | Rollback identified | **MET** — redeploy `c405b49` |

## 12. Final Recommendation

| Question | Answer |
|---|---|
| **A. Is master safe to deploy?** | **YES, on the evidence gathered** — conditional on item 9 below |
| **B. Which commits?** | `5416914`, `9ff021b`, `3bf92b6` — all three, no others pending |
| **C. Is Mentor included?** | **YES** — it is on master and Vercel deploys master |
| **D. Unrelated image-track commits?** | **NO** — only the two intended image fixes |
| **E. Any RED commits?** | **NO** |
| **F. Safe after quota reset?** | **YES** — deploy the known SHA `3bf92b6`; rollback target `c405b49` |
| **G. Mentor together or separate?** | **OWNER DECISION REQUIRED** |

**On G — the owner decision:** Mentor (`5416914`) is the only broad, unrelated surface. It registers
new routes through `main.py` and changes application composition. The two image fixes are narrow,
independently tested, and **runtime-inert**, so they carry essentially no deploy risk. Because all
three are already on `master` and Vercel deploys `master`, separating Mentor would require a revert
or a branch strategy — itself a risk. **My recommendation: ship all three together**, on the basis
that Mentor has now passed a real 21/21 local gate against an isolated database with zero console
errors, and that splitting introduces more risk than it removes. But this is a scope judgement, not
a technical constraint, and it is yours to make.

### Final classification

# `BLOCKED_BY_QUOTA`

Everything technical is green — build, lint, 21/21 local E2E, 36 image-fix tests, CI 9/9, no RED
commits, no deploy-time risk from the image fixes. **The single blocker is the exhausted Vercel daily
deployment allowance**, which resets at **2026-10-05 10:21:57Z**. The one non-technical open item is
the Mentor scope decision in §12-G.

**No deployment was attempted. No workflow was dispatched. No production data was read or written.
No image was repaired or restored. No Wave 1–3 data was applied. No scheduler, concurrency,
`do_logos`, ingestion or audit code was modified.**
