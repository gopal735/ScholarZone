# SCHOLARZONE — FINAL SECURITY RELEASE RECONCILIATION

Every material statement is labelled **PROVEN** (directly observed/executed),
**VALIDATED** (verified by a test or an independent cross-check), **UNKNOWN**,
or **BLOCKED**.

| | |
| --- | --- |
| Report branch | `docs/security-release-reconciliation` (deliberately **not** part of PR #2) |
| `origin/master` | `573a983b004ab08578497272659123323ab489b7` |
| Security PR | **#2** — `security/public-visibility-release` @ `0b9fe00ccbaaaf16502376d0d92e1f95e4b4c467` |
| Canonical production | `scholarzone-fwzj` · `https://scholarzone-fwzj.vercel.app` |
| Production revision | `4edd154a3037` (12-char prefix — see §12) |
| **Final classification** | **NEEDS_CONFIGURATION_FIX** |

---

## 1. Executive Verdict

**PROVEN.** The security fix is complete, verified, and based directly on current
master. PR #2 stands unchanged and should merge on code grounds.

**PROVEN.** The release **cannot** be completed, for three independent reasons that
are **not** the security code:

1. **BLOCKED** — Vercel free-tier deployment quota is active on **both** projects
   ("retry in 24 hours"). Not bypassed, not retried.
2. **PROVEN** — build provenance **fails**: `/api/health` returns a **12-character
   prefix** while `gitSource.sha` is a full 40-character SHA, and **no build step
   executes at all** (root build `[0ms]`, no `buildCommand` anywhere). The
   identity gate required by PHASE 8 therefore **cannot pass by construction**.
3. **PROVEN** — `scholarzone.vercel.app` remains publicly reachable serving
   `3ee434c01f53`, an older and **vulnerable** revision.

**PROVEN.** None of these are caused by, or fixable inside, PR #2. Bundling them
would violate PHASE 3 and absolute rule 13.

**Classification: NEEDS_CONFIGURATION_FIX** — the application/Vercel configuration
still requires work, and that work is known and implementable rather than
externally prevented.

---

## 2. Current Master

| Fact | Value | Label |
| --- | --- | --- |
| `origin/master` | `573a983b004ab08578497272659123323ab489b7` | **PROVEN** |
| Local `master` | `8ac1c9a` — stale | **PROVEN** |
| Shared worktree | HEAD `8ac1c9a`, **441 dirty entries** (other actors) | **PROVEN** |
| Master moved since PR #2 was opened? | **No** | **PROVEN** |
| `merge-base(master, PR head)` | `573a983` — equals the master tip | **PROVEN** |
| Commits on master absent from PR #2 | **0** | **PROVEN** |

**VALIDATED.** Local `master` remains ~75 commits behind `origin/master`; every
conclusion in this report was taken from `origin/master` or a worktree pinned to
it, never from local `master`.

---

## 3. Security PR

| Fact | Value | Label |
| --- | --- | --- |
| PR | **#2** · OPEN · not draft · **not merged** | **PROVEN** |
| Mergeable | `MERGEABLE` | **PROVEN** |
| Base → head | `master` → `security/public-visibility-release` @ `0b9fe00ccbaaaf16502376d0d92e1f95e4b4c467` | **PROVEN** |
| Scope | 4 files, +1466 / −2 | **PROVEN** |
| GitHub Actions checks | **10 / 10 PASS** (`backend-tests`, `build-and-smoke`, `env-config`, `frontend-lint`, `frontend-tests`, `git-integrity`, `import-smoke`, `preflight`, `schema-compat`) | **PROVEN** |
| Vercel checks | **2 FAIL** — rate limited | **BLOCKED** |
| PR head vs verified candidate `38700d8` | **docs-only** delta; `git diff -- backend/ frontend/` is **empty** | **PROVEN** |

**PROVEN.** PR #1 (`release/mentor-hardening-pr`, Mentor work) belongs to another
actor and was not touched, branched from, or merged.

**Decision (PHASE 15): option A — PR #2 remains as-is.** No supporting commit was
added. PHASE 15 forbids merging unrelated infrastructure into PR #2 "merely because
Vercel is currently failing", and §12's provenance work is exactly that.

---

## 4. Vulnerability

**PROVEN.** `GET /api/scholarships/{id}` resolved its row via a bare primary-key
lookup while every other public surface used `public_visibility_conditions()`.
The catalogue had two universes and the detail page was the larger one.

**VALIDATED.** Hidden records were readable by direct id for archived,
quarantined, `needs_review`, and image-gated records. The endpoint also served as
an existence oracle: a hidden id returned a full record where a missing id
returned 404.

**PROVEN — still live in production.** Both public hosts run revisions that predate
the fix (`4edd154` and `3ee434c`).

---

## 5. Security Fix

**PROVEN.** One function, `get_scholarship_details`
(`backend/app/services/scholarships.py`), now resolves through the canonical
predicate at line 55:

```python
scholarship = session.scalar(
    select(Scholarship)
    .where(Scholarship.id == scholarship_id)
    .where(*public_visibility_conditions())
)
```

**PROVEN — structural invariants intact:**

| Invariant | Evidence | Label |
| --- | --- | --- |
| Public detail **calls** the predicate | `services/scholarships.py:55` | **PROVEN** |
| Shared loader stays **permissive** | `repositories/scholarships.py:174` = `session.get(Scholarship, scholarship_id)`, no predicate | **PROVEN** |
| Exactly **one** predicate definition repo-wide | 1 definition, `repositories/scholarships.py:25` | **PROVEN** |
| Router does not define the predicate | enforced by `test_router_name_resolution.py` | **VALIDATED** |
| Admin verification still reaches hidden records | `test_admin_verification_still_reaches_a_hidden_record`, `…_quarantined_record` | **VALIDATED** |
| Verification pipeline still reaches hidden records | `test_the_verification_pipeline_can_still_reach_a_hidden_record` | **VALIDATED** |
| Hidden vs nonexistent indistinguishable | `test_a_hidden_record_and_a_missing_record_answer_identically` | **VALIDATED** |
| No internal fields leak | `test_a_public_detail_response_carries_no_internal_field`, `test_a_hidden_record_returns_no_body_to_inspect` | **VALIDATED** |

---

## 6. Security Test Evidence

**PROVEN — run on the exact PR head `0b9fe00`:**

| Suite | Result |
| --- | --- |
| `tests/test_public_detail_visibility.py` | **21 passed** |
| Canonical visibility + admin verification + verification pipeline + router-name-resolution (8 files) | **174 passed, 7 skipped** |
| Full backend suite (at `38700d8`, code-identical) | **4988 passed / 8 failed / 11 skipped / 1 error** |
| Clean baseline, fix stashed, same tree | **4967 passed / 8 failed / 11 skipped / 1 error** |
| Delta | **+21 passed. Zero new deterministic failures.** |

**VALIDATED.** The 8 failures are the known pre-existing set, all in
`test_neon_migration.py` (they require the untracked `migration_export.sql`); the
1 error is `scripts/artifact_smoke_test.py::test_endpoint`. **No test was
weakened, skipped, or xfailed.**

**PROVEN.** Browser E2E was performed against an identical product tree earlier in
this engagement (11/11 steps, zero unexpected console errors). It was **not** re-run
in this pass, because §12 means a production browser run cannot presently be bound
to a verified artefact identity.

---

## 7. Test-Safety Boundary

| Check | Result | Label |
| --- | --- | --- |
| Fail-closed DB default | `tests/conftest.py:16-17` forces `sqlite:///:memory:` when `SCHOLARZONE_ENVIRONMENT=test` and no URL is set | **PROVEN** |
| Tests targeting production hosts | **none** — matches are assertions about `allowed_origins`, URL-rewrite fixtures, and Origin headers, never live calls | **PROVEN** |
| Import-time production HTTP | **none.** `test_vercel_migration.py` *forbids* `httpx.get`/`requests.get`/`urlopen` in the maintenance worker | **PROVEN** |
| Neon references | fake `host.neon.tech` strings in a URL-rewrite test | **PROVEN** |
| Production DB write during this work | **none** | **PROVEN** |

**PROVEN — reported, excluded from PR #2 (PHASE 7):**
`tests/test_visibility_count_consistency.py:53-55` sets three gate variables via
bare `os.environ[...]` and never restores them, leaking into later tests in the same
process. Previously proven independent of the security change (identical failure
with the fix stashed). Not incorporated into this release.

---

## 8. Vercel Project A

| Field | Value |
| --- | --- |
| Name | `scholarzone` |
| Project ID | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| Owner | `gopal735's projects` (`gopal735s-projects`) |
| Created | 01 October 2026 19:44:51 |
| Framework preset | `Services` |
| **Build Command** | **None** |
| **Install Command** | **None** |
| Output directory | `None` |
| Region / Node | `iad1` / `24.x` |
| Current production deployment | `dpl_7mp8sctf3QTLHFptVviwdc3uxBfZ` |
| Deployment URL | `https://scholarzone-bvl7g26in-gopal735s-projects.vercel.app` |
| Deployed | Sun Oct 04 2026 17:14:14 +0600 |
| State | `READY`, target `production` |
| `gitSource` | `type=github`, `ref=master`, `sha=3ee434c01f534e2cfd72300030316cdd27c33789` |
| Aliases | `scholarzone.vercel.app`, `scholarzone-gopal735s-projects.vercel.app`, `scholarzone-git-master-gopal735s-projects.vercel.app` |
| Serves | `3ee434c01f53` — **older, vulnerable** |

**PROVEN.** The `-git-master-` alias proves **Git integration on `master` is active**,
so this project auto-deploys from master.

---

## 9. Vercel Project B

| Field | Value |
| --- | --- |
| Name | **`scholarzone-fwzj`** |
| Project ID | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Owner | `gopal735's projects` |
| Created | 01 October 2026 20:02:55 |
| Framework preset | `Services` |
| **Build Command** | **None** |
| **Install Command** | **None** |
| Region / Node | `iad1` / `24.x` |
| Current production deployment | `dpl_4r7L19mHjj7WvfinDw4HMVawFaJA` |
| Deployment URL | `https://scholarzone-fwzj-oxfgjct80-gopal735s-projects.vercel.app` |
| Deployed | Sun Oct 04 2026 17:47:58 +0600 |
| State | `READY`, target `production` |
| `gitSource` | `type=github`, `ref=master`, `sha=4edd154a303715442a2f0517b052259e5f113cab` |
| Aliases | `scholarzone-fwzj.vercel.app`, `scholarzone-fwzj-gopal735s-projects.vercel.app`, `scholarzone-fwzj-git-master-gopal735s-projects.vercel.app` |
| Serves | `4edd154a3037` — **canonical, vulnerable** |

**PROVEN.** Git integration on `master` is active here too.

---

## 10. Canonical User Host

**Determination: `scholarzone-fwzj.vercel.app` is canonical.** Classification **A**.

Re-verified from *current* evidence, not from the previous pass:

| Strand | Evidence | Label |
| --- | --- | --- |
| CI target | `deploy.yml` and `admin-auth-check.yml` consume `SCHOLARZONE_API_URL`; documented as `https://scholarzone-fwzj.vercel.app/api` in `MENTOR_FINAL_PRODUCTION_GATE.md:60-61` | **PROVEN** |
| Infra decision record | `FINAL_INFRA_RELEASE_DECISION.md:72` — "live project **`scholarzone-fwzj`**"; its deployments point at `scholarzone-fwzj.vercel.app` | **PROVEN** |
| Deployment recency | fwzj deployed 17:47:58, scholarzone 17:14:14 same day | **PROVEN** |
| Task brief | states production is `4edd154`, which only fwzj serves | **PROVEN** |
| Repo linkage | `.vercel/repo.json` → `prj_NLC71y3rKRIOduTla785AzEOEFL5` (**corroborating only**) | **PROVEN** |

**PROVEN — explicitly rejected as evidence:** `backend/app/core/config.py:93-94`
lists **both** domains in `allowed_origins`. That is a CORS allow-list and proves
nothing about which host is canonical. Recorded because it is the most likely
mistake for a future reader.

**UNKNOWN.** Why a second project exists and whether it was ever intended to be
user-facing. `scholarzone` was created ~18 minutes before `scholarzone-fwzj`.

---

## 11. Stale Host Risk

**PROVEN.** `scholarzone.vercel.app` is **publicly reachable**, HTTP 200,
`Server: Vercel`, serving `3ee434c01f53`.

**PROVEN.** The two public hosts are **divergent** and both are behind master:

| Host | Serves | Relative to master |
| --- | --- | --- |
| `scholarzone-fwzj.vercel.app` | `4edd154a3037` | 1 commit behind |
| `scholarzone.vercel.app` | `3ee434c01f53` | 5 commits behind |

**PROVEN.** This exact condition is what absolute rule 9 forbids — a stale public
host left unmanaged — and it currently holds. `MENTOR_FINAL_PRODUCTION_GATE.md:149`
already records it as *"a second user-facing alias that is stale and unmonitored"*.

**Mitigating fact (PROVEN).** Both projects auto-deploy from `master`. Therefore,
once the quota resets, a merge to master pushes the security fix to **both** hosts
and the divergence resolves itself without any routing change. That is the
lowest-risk resolution and is recommended over alias surgery.

**UNKNOWN.** Whether the `scholarzone` project's auto-deploy is intentionally
maintained or has simply been happening alongside.

**No project, alias, or routing change was made.** Any such change is
**OWNER-ACTION-REQUIRED**.

---

## 12. Build Provenance

**PROVEN — provenance FAILS every requirement in PHASE 6.**

| Requirement | Observed | Verdict |
| --- | --- | --- |
| Vercel Git SHA → build-time validation | no build step runs | **FAIL** |
| Immutable packaged artefact | none exists | **FAIL** |
| Runtime reads artefact | runtime reads an **environment variable** | **FAIL** |
| Exactly 40 hex characters | `/api/health` returns **12** | **FAIL** |
| No 12-char prefixes | `build_revision()` truncates | **FAIL** |
| No runtime env override | `VERCEL_GIT_COMMIT_SHA` **is** the runtime source | **FAIL** |
| No query/header override | none found | pass |
| No branch-name fallback | none found | pass |
| No `"unknown"` fallback in production | none found | pass |
| Fail closed on missing/corrupt artefact | falls back to a dev/unknown marker | **FAIL** |

**PROVEN — root cause chain:**
1. `vercel.json` (current master) declares the backend service with **no
   `buildCommand` and no `installCommand`**.
2. `vercel project inspect` reports **Build Command: None** for both projects.
3. The deployment `Builds` block shows the root build at **`[0ms]`** — nothing runs.
4. `backend/app/main.py::build_revision()` therefore has nothing packaged to read,
   so it reads `VERCEL_GIT_COMMIT_SHA` at runtime and truncates to `raw[:12]`.

**PROVEN — the platform already has the correct value.** `gitSource.sha` is a full
40-character SHA on both deployments (§8, §9). The information is discarded by the
application, not lost by Vercel.

**VALIDATED — an implementation of the required architecture already exists, unmerged.**
`origin/rc/revision-provenance` (tip `d050d30`, author "Kilo", 2026-10-04 19:24 +0600)
contains `255ca97` *"fix: identify the deployed build from an embedded artefact, not
the runtime env"*, which introduces `backend/app/build_provenance.py` (40-hex
validation, artefact written **inside the package**, no runtime override, no
truncation, fail-closed), `backend/scripts/embed_build_revision.py`, a `buildCommand`
+ `installCommand` in `vercel.json`, and a 333-line test suite.

**PROVEN.** That branch is **unmerged** and its cumulative diff **also** modifies
`backend/app/services/mentor/evidence.py` and `backend/tests/test_mentor.py` via a
separate commit `00bc39d`. It therefore **cannot be absorbed wholesale** under
absolute rule 13. The provenance commits themselves are Mentor-free and could be
isolated — **that is the owner's call, not this task's.**

---

## 13. Deployment Identity Gate

**PROVEN — the gate FAILS.**

| Host | `gitSource.sha` (40) | `/api/health` | Equal? |
| --- | --- | --- | --- |
| `scholarzone-fwzj` | `4edd154a303715442a2f0517b052259e5f113cab` | `4edd154a3037` | **prefix only** |
| `scholarzone` | `3ee434c01f534e2cfd72300030316cdd27c33789` | `3ee434c01f53` | **prefix only** |

**PROVEN.** The required equality `gitSource.sha == /api/health` is **impossible
today**, because the health endpoint does not expose a full SHA at all. No prefix
matching, alias-only verification, or truncation workaround was accepted as
evidence.

**PROVEN.** Deployment IDs are recorded for future use:
`dpl_4r7L19mHjj7WvfinDw4HMVawFaJA` (canonical) and
`dpl_7mp8sctf3QTLHFptVviwdc3uxBfZ` (stale).

---

## 14. Protected Preview Verification

**BLOCKED.** PHASE 9 requires a real preview deployment to prove build execution
end-to-end. Creating one consumes a deployment, and the quota is active
(§16). No preview was created; protection was **not** disabled to work around it.

**PROVEN — what is already known without a preview:** the `Builds` block shows the
root build at `[0ms]` and no `buildCommand` is configured, so there is currently no
build step whose execution could be verified. PHASE 7's question — *"is a
buildCommand actually executed by this project's deployment path?"* — is answered
**no**, on evidence from live deployments rather than from the schema.

**UNKNOWN.** Whether the `buildCommand` on `rc/revision-provenance` would execute
under this project's deployment path. That requires an actual preview build to
prove, which is blocked.

---

## 15. Browser Identity Gate

**BLOCKED for production.** A browser identity gate requires asserting an exact
backend URL, an expected revision, and frontend→backend wiring **before** making
assertions. Since `/api/health` cannot report a full SHA (§13), the expected revision
cannot be pinned to a specific artefact, so a production browser run could not be
bound to verified identity. Per PHASE 10, the gate **STOPS** rather than proceeding
against an unidentified backend.

**PROVEN — the gate exists and is enforced locally.** All browser work in this
engagement was performed against an isolated SQLite database and a local uvicorn
instance started and stopped per run, with `/api/health` checked before assertions.
An earlier contamination incident (stale uvicorn/Vite processes) is the reason the
gate exists; no browser assertion in this engagement has been made against an
unidentified backend.

**VALIDATED.** Local identity anchoring: local backend reported `revision: "dev"`,
matching legitimate local mode, and the frontend was confirmed to proxy `/api` to
that exact process.

---

## 16. Rate Limit

**BLOCKED — `BLOCKED_BY_PLATFORM_QUOTA`.**

**PROVEN.** Both Vercel checks on PR #2 fail with:
*"Deployment rate limited — retry in 24 hours"*, linking to
`vercel.com/gopal735s-projects?upgradeToPro=build-rate-limit`.

**PROVEN.** Quota identifier: `api-deployments-free-per-day`.

**PROVEN — no bypass was attempted.** No alternate account, no undocumented API, no
alternate project created to evade quota, no repeated retry. State was read only
(`vercel ls`, `vercel inspect`, `vercel api /v13/deployments/{id}`, `gh pr checks`);
no `vercel --prod` or equivalent deployment command was run at any point.

**VALIDATED.** All non-deployment work continued regardless: master verification,
PR provenance, security integrity, host reconciliation, deployment provenance,
identity-gate analysis, and the full test suites.

---

## 17. Exact Git Diff

```
base    : 573a983b004ab08578497272659123323ab489b7   (origin/master)
head    : 0b9fe00ccbaaaf16502376d0d92e1f95e4b4c467   (PR #2)
files   : 4
diffstat: 4 files changed, 1466 insertions(+), 2 deletions(-)
```

| File | +/- | Role |
| --- | --- | --- |
| `backend/app/services/scholarships.py` | +32 / −2 | **the security fix** |
| `backend/tests/test_public_detail_visibility.py` | +458 / −0 | 21 regression tests |
| `PUBLIC_SCHOLARSHIP_DETAIL_VISIBILITY_FINAL.md` | +475 / −0 | documentation |
| `PUBLIC_VISIBILITY_SECURITY_RELEASE_FINAL.md` | +501 / −0 | documentation |

**PROVEN — exact security behaviour changed:** the row resolution inside
`get_scholarship_details` moves from `session.get(Scholarship, id)` to a `SELECT`
constrained by `public_visibility_conditions()`. Nothing else in the application
changes behaviour.

**PROVEN — forbidden scope, checked mechanically:**
`git diff --name-only origin/master..0b9fe00 | grep -Ei 'match|count|mentor|supervisor|application_workspace|image|ingest|logo|do_logos|scheduler|maintenance|models\.py|migrate_schema|requirements|auth'`
→ **empty.**

No Mentor, Supervisor, Wave 1–3, Match 2.0, Count Intelligence, Application
Workspace, image-pipeline, schema/migration, auth, or unrelated formatting change
is present.

**PROVEN.** No destructive Git command was used: no `git add .`, `git add -A`,
`reset --hard`, `git clean`, force push, rebase of a shared branch, or amend of
another actor's commit. `origin/master` was never moved.

---

## 18. Merge Readiness

**Code-ready — all nine gates met.**

| Gate | Status | Label |
| --- | --- | --- |
| Current master verified | `573a983`, fetched live | **PROVEN** |
| Security fix based on current master | `merge-base` = master tip; 0 master commits missing | **PROVEN** |
| Security regression tests pass | 21 passed | **VALIDATED** |
| No visibility predicate duplication | exactly 1 definition; public path calls it | **PROVEN** |
| Admin path preserved | 2 dedicated tests | **VALIDATED** |
| Verification pipeline preserved | dedicated functional test | **VALIDATED** |
| Exact hidden/nonexistent 404 behaviour | status + body asserted identical | **VALIDATED** |
| Test safety remains fail-closed | conftest `:memory:` default; no production HTTP | **PROVEN** |
| No production DB write occurred | none | **PROVEN** |

**PR #2 is merge-ready on code grounds.** All 10 GitHub Actions checks pass. The
only failing checks are the two Vercel quota checks, which are a platform
constraint rather than a code defect.

---

## 19. Deployment Readiness

**NOT met. Two of nine gates fail outright; three cannot be attempted.**

| Gate | Status | Reason | Label |
| --- | --- | --- | --- |
| Exact Vercel deployment Git SHA known | **met** | recorded for both projects | **PROVEN** |
| Build-time provenance proven | **FAIL** | no build step runs; runtime env + truncation | **PROVEN** |
| Immutable artefact proven | **FAIL** | none is produced | **PROVEN** |
| `/api/health` returns exact full SHA | **FAIL** | returns 12 chars | **PROVEN** |
| Canonical user-facing hostname proven | **met** | `scholarzone-fwzj` | **PROVEN** |
| Stale host/project risk resolved | **not resolved** | `scholarzone.vercel.app` still public and behind | **PROVEN** |
| Release identity gate passes | **FAIL** | equality impossible today | **PROVEN** |
| Browser identity gate passes | **BLOCKED** | cannot pin an artefact identity | **BLOCKED** |
| Vercel rate limit inactive | **FAIL** | active, 24h | **BLOCKED** |

**PROVEN.** A deployment made right now would be **unverifiable**: the running
artefact could not be bound to the commit that built it, so "the fix is deployed"
could not be honestly claimed even if the quota permitted it.

---

## 20. Post-Reset Procedure

**PROVEN — do not execute until the quota resets.** Owner procedure, in order.
**STOP at any failing step; never call a deployment successful on partial
evidence.**

1. Confirm quota reset: `gh pr checks 2` shows both Vercel checks no longer
   rate-limited.
2. Re-read `origin/master`. If it moved, re-verify PR #2's `merge-base` equals the
   new master tip; if not, re-cut a fresh branch from current master per PHASE 2.
3. Re-read PR #2 head/base and confirm no Mentor, image, Supervisor, Match, or
   Count changes entered it.
4. **Resolve §12 first, or accept an unverifiable release.** Recommended: land the
   Mentor-free provenance commits from `origin/rc/revision-provenance`
   (`255ca97`, `d050d30`) as their own change, then re-verify.
5. Confirm the deploy target is `scholarzone-fwzj`, and decide deliberately whether
   `scholarzone` should also receive the build (it auto-deploys from master).
6. Merge PR #2 through the normal master Git integration. Do **not** deploy the
   feature branch directly.
7. Capture `gitSource.sha` for the new deployment on both projects via
   `vercel api /v13/deployments/{id}`; require **40 hex characters**.
8. Verify `/api/health` returns that **exact 40-character SHA** on the canonical
   host. Prefix match is a **failure**.
9. Verify the canonical hostname serves it, and confirm `scholarzone.vercel.app`
   either matches or has an owner-approved disposition.
10. Run the authenticated security E2E (PHASE 10 identity gate **first**): public
    id → 200; known hidden id → 404; nonexistent id → 404; hidden and nonexistent
    indistinguishable.
11. Re-run the 21 security tests and the full backend suite on the merged tree.

---

## 21. Remaining Unknowns

| # | Unknown | Why it matters |
| --- | --- | --- |
| 1 | Whether `buildCommand` on `rc/revision-provenance` actually executes under this deployment path | Requires a real preview build (**BLOCKED**) |
| 2 | Whether `scholarzone` project is intentionally maintained | Determines whether the stale host is a bug or a duplicate (**§11**) |
| 3 | Why a second project exists | Created 18 min after the first; no repo evidence found |
| 4 | Which production catalogue ids are non-public | Needed for PHASE 18 step 10 without touching production rows |
| 5 | Whether the quota resets in 24h as stated | External; **BLOCKED** |
| 6 | Whether another actor's provenance branch will be merged, and by whom | Determines whether §12 resolves itself |
| 7 | Whether `local master` staleness (75 commits) will bite another contributor | Recurred across this engagement |

**PROVEN.** Items 4 and 7 are the only ones actionable without external input. No
production record was created or modified to answer item 4.

---

## 22. Final Decision

# NEEDS_CONFIGURATION_FIX

**Why not READY_FOR_MERGE.** That classification means "security code is clean and
current-master based", which is **true** — and PR #2 is merge-ready on those
grounds. But this engagement is a *release resolution*, and the release cannot be
completed: build provenance is unfixed, the identity gate cannot pass, and a stale
public host still serves vulnerable code. Reporting READY_FOR_MERGE alone would
understate three unresolved items.

**Why not READY_FOR_POST_RESET_DEPLOY.** That requires deployment infrastructure to
be **completely verified** with only the rate limit outstanding. It is not verified:
no build step runs, no immutable artefact exists, and `/api/health` truncates.

**Why not BLOCKED.** The security work is complete and unblocked. The remaining
items are **known, implementable configuration work** — chiefly landing the
already-written build-provenance change and disposing of the stale host — not
external prevention. The only genuinely external blocker is the Vercel quota.

**What is decided, and what is not:**

- **DECIDED (PROVEN):** PR #2 stands as-is, remains merge-ready, contains only the
  security fix plus tests and documentation, and is based on current master.
- **NOT DECIDED (PROVEN):** the release cannot ship until build provenance is fixed
  and the stale host is resolved; and it cannot be attempted at all while the quota
  is active.
- **OWNER-ACTION-REQUIRED:** landing the provenance commits; deciding the fate of
  the `scholarzone` project; executing §20 after the quota resets.

**The vulnerability remains live in production on both public hosts.** That is the
single most consequential fact in this report, and it is not resolved by anything in
PR #2 alone.