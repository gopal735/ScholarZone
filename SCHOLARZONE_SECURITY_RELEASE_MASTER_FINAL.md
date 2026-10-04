# SCHOLARZONE — SECURITY RELEASE + PROVENANCE INTEGRATION MASTER FINAL

Every conclusion is labelled **PROVEN**, **VALIDATED**, **UNKNOWN**, or **BLOCKED**.

| | |
| --- | --- |
| `origin/master` | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| Security PR #2 | **MERGED** 2026-04-04T13:44:40Z, merge commit `ddcd9c3` |
| Provenance PR | **#5** — https://github.com/gopal735/ScholarZone/pull/5 — OPEN |
| Canonical frontend | `https://gopal735.github.io/ScholarZone/` (GitHub Pages) |
| Canonical backend | `scholarzone-fwzj` · `https://scholarzone-fwzj.vercel.app` |
| Production now | `4edd154a3037` (fwzj) · `3ee434c01f53` (scholarzone) — **both still vulnerable** |
| **Final classification** | **READY_FOR_OWNER_MERGE** |

> **The verified state in the brief was stale when work began.** PR #2 was merged
> by the owner at 13:44:40Z, mid-session, moving master from `573a983` to
> `ddcd9c3`. Every conclusion below is taken from the *current* state, re-verified
> immediately before each irreversible step.

---

## 1. Current Master

| Fact | Value | Label |
| --- | --- | --- |
| `origin/master` | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` | **PROVEN** |
| Contains the security fix (`73e6027`) | **yes** | **PROVEN** |
| Master commits the provenance PR lacks | **0** (merge-base == master tip) | **PROVEN** |
| Local `master` | `8ac1c9a` — stale, ignored | **PROVEN** |

**PROVEN.** Master was re-fetched and re-checked immediately before committing
(PHASE 9). No rebase of any shared branch was performed or needed.

## 2. PR #2 Security Integrity

| Check | Result | Label |
| --- | --- | --- |
| State | **MERGED**, merge commit `ddcd9c3` | **PROVEN** |
| Public detail calls the canonical predicate | `services/scholarships.py:55` | **PROVEN** |
| Shared loader still permissive | `repositories/scholarships.py:174` = `session.get(...)`, no predicate | **PROVEN** |
| Exactly one predicate definition | 1, `repositories/scholarships.py:25` | **PROVEN** |
| Security tests | **21 passed** | **VALIDATED** |
| Visibility + admin + pipeline regressions | **174 passed, 7 skipped** | **VALIDATED** |
| Hidden vs nonexistent | identical status **and** body | **VALIDATED** |
| Internal fields on hidden record | nothing serialised at all | **VALIDATED** |

**PROVEN.** The isolation requirement held: PR #2 contained only the fix, its
tests, and its reports. No provenance, Mentor, or infrastructure work was mixed
into it, and none was added afterwards.

## 3. Provenance-Only Extraction

| Fact | Value | Label |
| --- | --- | --- |
| Source branch | `origin/rc/revision-provenance`, base `3ee434c`, tip `d050d30` | **PROVEN** |
| Commits taken | `255ca97`, `d050d30` | **PROVEN** |
| Commit excluded | `00bc39d` — *scope mentor chip dedup* | **PROVEN** |
| Whole branch merged / cherry-picked | **no** | **PROVEN** |
| Modified files changed on master since base | **0** — verbatim port safe | **PROVEN** |

**PROVEN.** A naive `git diff master..branch` *appeared* to show Mentor
contamination, but that was an artefact of the branch's older base making landed
master work look reversed. The contamination was measured from the branch's own
commits.

## 4. Build Hook

| Fact | Value | Label |
| --- | --- | --- |
| Pre-fix project `Build Command` | **None** | **PROVEN** |
| Pre-fix root build duration | **`[0ms]`** — nothing executed | **PROVEN** |
| Now: backend `buildCommand` | `python scripts/embed_build_revision.py` | **PROVEN** |
| Now: `installCommand` | also runs the generator | **PROVEN** |
| Which file is authoritative | **repository-root** `vercel.json` (project Root Directory is `.`) | **PROVEN** |
| Structural test of the wiring | asserts the `buildCommand` invokes the generator | **PROVEN** |
| Real execution under this deployment path | — | **BLOCKED** |

## 5. Immutable Artifact

**PROVEN.** The SHA is written to `backend/app/build_revision.txt`, *inside* the
package, so it ships with the artefact. A comment in the source records why: a
file beside the package would be the first thing a bundler drops.

**PROVEN.** A platform build with a missing or malformed SHA raises, and the
build fails rather than publishing an identity-free artefact.

## 6. Runtime SHA

**PROVEN.** `build_revision()` reads the artefact **only**. It does not consult
`VERCEL_GIT_COMMIT_SHA`, `SCHOLARZONE_BUILD_REVISION`, any header, any query
parameter, any branch name, or any deployment URL.

**PROVEN.** Full 40-character SHA, never truncated. **VALIDATED** by test: with
both `VERCEL_GIT_COMMIT_SHA` and `SCHOLARZONE_BUILD_REVISION` set to a *different*
commit at runtime, the reported revision is still the embedded one.

**PROVEN.** Fail-closed: missing artefact **in production** → `/health` **503**;
corrupt artefact → always raises; missing artefact **off-platform** → `dev`, so
tests still run. Startup logs the fault rather than refusing to boot.

## 7. Health Contract

| Case | Result | Label |
| --- | --- | --- |
| 40-char embedded SHA | returned verbatim | **PROVEN** |
| 12-char artefact value | refused, 503 | **PROVEN** |
| Malformed artefact | refused | **PROVEN** |
| Missing artefact in production | 503 | **PROVEN** |
| Env override at runtime | ignored | **PROVEN** |

## 8. Deployment Gate

| | Before | After | Label |
| --- | --- | --- | --- |
| Comparison | `CURRENT = EXPECTED_SHORT` (12 chars) | `CURRENT = EXPECTED_REVISION` (`${{ github.sha }}`) | **PROVEN** |
| Accepted shape | `^[0-9a-f]{7,40}$` | `^[0-9a-f]{40}$` | **PROVEN** |

**PROVEN — strengthened, not weakened.** `EXPECTED_SHORT` removed; no relaxation
introduced.

## 9. Release Identity Gate

**PROVEN.** New `backend/scripts/release_identity_gate.py` binds deployment id,
deployment URL, `gitSource.ref`, `gitSource.sha` and runtime health SHA, requiring
exact equality on two full 40-character SHAs. It rejects an alias substituted for
a deployment, a **production** response when a **preview** was requested, a prefix
in either field, the wrong deployment id, and an expected SHA that is itself a
prefix — each with a dedicated negative test. Health is read from the deployment
the **platform** named, so a substituted alias cannot influence the result.

**PROVEN.** The verification half is a pure function; no network call sits inside
it, which is what makes those rejections directly testable.

**PROVEN.** I made the gate **stricter than my own first draft**: it had been
`.strip().lower()`-normalising the reported revision, so uppercase or
whitespace-padded values passed. Two of my tests caught it and the normalisation
was removed.

## 10. Vercel Project `scholarzone`

| Field | Value |
| --- | --- |
| Project ID | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| Production deployment | `dpl_7mp8sctf3QTLHFptVviwdc3uxBfZ` |
| `gitSource` | `type=github`, `ref=master`, `sha=3ee434c01f534e2cfd72300030316cdd27c33789` |
| Serves | `3ee434c01f53` — **vulnerable** |
| Git integration | **active** (`…-git-master-…` alias) |
| Builds | root `.` `[0ms]` |

**PROVEN.** Auto-deploys from master. **UNKNOWN** whether this is intentional or
incidental.

## 11. Vercel Project `scholarzone-fwzj`

| Field | Value |
| --- | --- |
| Project ID | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Production deployment | `dpl_4r7L19mHjj7WvfinDw4HMVawFaJA` |
| `gitSource` | `type=github`, `ref=master`, `sha=4edd154a303715442a2f0517b052259e5f113cab` |
| Serves | `4edd154a3037` — **vulnerable** |
| Git integration | **active** |
| Builds | root `.` `[0ms]` |

## 12. Canonical Frontend

**PROVEN.** `https://gopal735.github.io/ScholarZone/` — HTTP 200.
**PROVEN.** Its deployed bundle (`index-Bhvmyxum.js`, 587 KB) has
`https://scholarzone-fwzj.vercel.app/api` compiled in, with **zero** relative
`"/api"` occurrences — so it calls the canonical backend absolutely, not by
discovery.
**PROVEN.** Repo variable `SCHOLARZONE_API_URL = https://scholarzone-fwzj.vercel.app/api`.
**PROVEN.** Frontend hosting was not moved.

**VALIDATED.** Because the canonical frontend does not reference
`scholarzone.vercel.app`, the stale backend is **not** on the user-facing path.
That reduces the stale-host risk; it does not remove it, since the host remains
publicly reachable and directly callable.

## 13. Canonical Backend

**PROVEN — `scholarzone-fwzj`**, from four independent strands: the CI variable
`SCHOLARZONE_API_URL`; `FINAL_INFRA_RELEASE_DECISION.md` ("live project"); the
canonical frontend's compiled-in bundle (§12); and deployment recency.
**PROVEN — explicitly rejected as evidence:** `core/config.py:93-94` lists both
domains in `allowed_origins`, which is a CORS allow-list, not a target
declaration.

## 14. Rate Limit

**BLOCKED — `BLOCKED_BY_PLATFORM_QUOTA`.** `api-deployments-free-per-day`,
"retry in 24 hours", on both projects.
**PROVEN.** No bypass: no alternate account, no alternate project, no
undocumented API, no retries. Reads only (`vercel ls|inspect|project inspect|api`,
`gh pr checks`). **No deployment was performed.**

## 15. Merge Order

**PROVEN — the question the brief warned against guessing at, answered from
evidence:**

1. **PR #2 is already merged.** The "two merges" scenario therefore cannot arise;
   only one merge remains.
2. Both projects share **one account** (`gopal735`), so the daily quota is
   **shared**.
3. Both have **Git integration on `master`** (proven by their `-git-master-`
   aliases), so **one merge attempts two production deployments**.
4. Recent volume: ~21 deployment rows per project within the last few hours,
   which is consistent with the reported cap being reached.

**Conclusion:** merging PR #5 costs **2 deployment attempts** and produces **no
unsafe intermediate state** — master already carries the security fix, so the same
deploy that introduces provenance also ships the fix to both backends. **A combined
PR is therefore NOT required**, and creating one would only add review burden.

**Recommended order:** merge PR #5 → verify master → let normal master Git
integration deploy both projects → prove identity on both.

## 16. Post-Merge Provenance

**BLOCKED.** Cannot be executed until the quota resets. Procedure is specified in
PR #5 §8 and the reconciliation report; the required end state is:

- `gitSource.sha` (40) **==** master SHA, on **both** projects
- `/api/health` on each deployment's own URL **==** that `gitSource.sha`, exact
- both hosts converge on the security-fixed, provenance-carrying release

## 17. Production Security Proof

**BLOCKED.** Requires the deploy first. Read-only plan (no record creation, no row
modification): public id → 200; known hidden id → 404; nonexistent id → 404;
hidden and nonexistent indistinguishable in status and body.

**UNKNOWN.** Which production catalogue ids are non-public. I will **not** create
or modify production records to find out.

## 18. Browser Identity Gate

**BLOCKED for production**, correctly. With the pre-fix build, `/health` cannot
report a full SHA, so a production browser run cannot be bound to a verified
artefact identity — and PHASE 18 says to STOP in that case.

**PROVEN.** The gate exists and has been honoured: all browser work in this
engagement used an isolated database and a locally started server, with identity
checked before assertions.

## 19. Final E2E

**BLOCKED** on deployment. **VALIDATED** locally against an identical product tree
earlier: 11/11 steps, zero unexpected console errors, public detail rendering and
hidden/nonexistent both showing the same not-found page.

## 20. Exact Git Diff

```
PR #5 base : ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb
PR #5 head : f9b4778
files      : 10
diffstat   : 10 files changed, 1265 insertions(+), 61 deletions(-)
```

| File | Change |
| --- | --- |
| `backend/app/build_provenance.py` | new |
| `backend/scripts/embed_build_revision.py` | new |
| `backend/scripts/release_identity_gate.py` | new |
| `backend/tests/test_build_provenance.py` | new |
| `backend/tests/test_release_identity_gate.py` | new |
| `backend/app/main.py` | artefact-only revision, 503 fail-closed health |
| `vercel.json` (root) | backend `buildCommand` + `installCommand` |
| `.github/workflows/deploy.yml` | exact-SHA gate |
| `backend/tests/test_final_hardening.py` | updated |
| `backend/tests/test_vercel_migration.py` | updated |

**PROVEN — no forbidden scope.** No Mentor, Supervisor, Wave 1–3, Match 2.0,
Count Intelligence, Application Workspace, image pipeline, ingestion, scheduler,
frontend, Neon, or scholarship-data change. No destructive Git operation was used;
`origin/master` was never moved.

## 21. Remaining Risks

| # | Risk | Label |
| --- | --- | --- |
| 1 | **Both public backends still serve vulnerable code** until the quota resets and master deploys | **BLOCKED** |
| 2 | Real build-hook execution unproven; first deploy will answer it | **BLOCKED** |
| 3 | **Three overlapping provenance PRs (#3, #4, #5)** — merging more than one risks conflicting `main.py`/`deploy.yml` edits | **PROVEN** |
| 4 | PRs #3/#4 edit `backend/vercel.json`, not the root file the platform reads | **VALIDATED** |
| 5 | PR #3 also carries Mentor + frontend changes, breaking isolation | **PROVEN** |
| 6 | `scholarzone.vercel.app` remains public and unmonitored | **PROVEN** |
| 7 | Shared daily quota; ~21 deploys/project recently | **PROVEN** |
| 8 | Pre-existing unrestored env mutation in `test_visibility_count_consistency.py:53-55` | **PROVEN** |
| 9 | Whether Vercel's Services preset honours a per-service `buildCommand` here | **UNKNOWN** |

## 22. Final Decision

# READY_FOR_OWNER_MERGE

- **PROVEN — PR #5 is clean:** 10 files, provenance only, no forbidden scope,
  directly on current master.
- **PROVEN — PR #2 is clean and merged:** security fix verified, isolated, on master.
- **PROVEN — master verified:** `ddcd9c3`, re-checked immediately before commit.
- **PROVEN — no production deployment is required to prepare this.**
- **PROVEN — merge order is safe:** one merge, two deployment attempts, no unsafe
  intermediate state, no combined PR needed.

**Not claimed.** I am **not** claiming the release is verifiable yet. Real build
execution is unproven until a deployment runs, and the post-merge proof on both
hosts is blocked. The distinction matters: this work makes the release
*provable*, and the first deploy is what *proves* it.

**Owner actions, in order:**
1. **Close PRs #3 and #4** in favour of #5 — three overlapping provenance PRs is a
   merge hazard, and only #5 edits the authoritative `vercel.json`.
2. **Merge PR #5.**
3. **Wait for the quota reset.** Do not deploy manually while limited.
4. After reset: confirm both projects redeployed from master, then run the exact
   40-character identity proof and the read-only production security proof on
   both hosts.
5. Decide the long-term disposition of `scholarzone.vercel.app` (not required for
   this release; it is off the user-facing path but still publicly reachable).

**If the build hook turns out not to execute**, the failure is loud by design:
`/health` returns 503 and `deploy.yml` fails. That is the intended trade — a
diagnosable outage in preference to publishing a deployment that cannot name its
own commit.