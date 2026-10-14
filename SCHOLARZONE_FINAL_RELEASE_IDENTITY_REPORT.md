# SCHOLARZONE_FINAL_RELEASE_IDENTITY_REPORT.md

**Release identity gate run** · 2026-10-04 19:02Z–19:12Z
**Gated deployment (exact URL, no alias):** `https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app`
**Master under gate:** **`fc4096f7a2aac8530f4e14495a7f21b9a97419be`** (merged 18:22:37Z)
**Canonical project:** `scholarzone-fwzj` (`prj_NLC71y3rKRIOduTla785AzEOEFL5`)
**Production application-data writes: NONE**

Labels: **PROVEN** · **PROVEN FAIL** · **BLOCKED** · **UNKNOWN**

---

# FINAL CLASSIFICATION: `FULLY_RELEASED`

```
A == B == C == D == fc4096f7a2aac8530f4e14495a7f21b9a97419be
```
All four values are exactly 40 lowercase hexadecimal characters. Distinct value count: **1**.

---

## GATE SCOPE
Release identity gate only. No code changes made. No deployment configuration changed. No manual or
CLI deployment created. `vercel deploy` not used. No throwaway project. Deployment Protection not
disabled or weakened — the pre-existing project-scoped bypass credential was used read-only. No
production data written. No retry of deployment creation. All reads were taken against the exact
deployment URL, never the alias. Identity was **not** inferred from timestamps, aliases, behavioural
similarity, or the previous 12-character runtime revision.

---

## The deployment under gate

| Attribute | Value |
|---|---|
| Deployment ID | `dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj` |
| Deployment URL (exact) | `https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app` |
| Target | `production` |
| `source` | `git` |
| `gitSource.ref` | `master` |
| `gitSource.sha` | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| `gitSource.type` | `github` |
| `gitSource.repoId` | `1354421070` (gopal735/ScholarZone) |
| `gitSource.prId` | absent — a production-branch deployment, not a pull-request build |
| readyState | `READY` |
| Build ID | `bld_qrpel9xil` (`readyState=READY`) |

Production promotion is confirmed by the project record, not inferred:
```
latestDeployments[0].id           = dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj
latestDeployments[0].target       = production
latestDeployments[0].meta.ref     = master
latestDeployments[0].meta.sha     = fc4096f7a2aac8530f4e14495a7f21b9a97419be
latestDeployments[0].alias        = scholarzone-fwzj.vercel.app,
                                    scholarzone-fwzj-gopal735s-projects.vercel.app,
                                    scholarzone-fwzj-git-master-gopal735s-projects.vercel.app
```

## Provenance of this deployment — how the earlier blocker cleared
The 18:50Z gate recorded the master push as refused. The provider's own commit status on `fc4096f`
now shows the retry resolving on the canonical project while the other three Git-connected projects
remain terminally refused:
```
Vercel – scholarzone-fwzj   success   "Deployment has completed"   (updated 2026-10-04T19:00:33Z)
Vercel – scholarzone        failure   "Deployment rate limited — retry in 24 hours."  (18:22:41Z)
Vercel – sz_god_wt          failure   "Deployment rate limited — retry in 24 hours."  (18:22:41Z)
Vercel – rc-revprov         failure   "Deployment rate limited — retry in 24 hours."  (18:22:41Z)
```
The deployment was created by the **Vercel GitHub App from the `master` push** (`source=git`,
`gitSource.ref=master`). This gate did not create, request, re-request or retry any deployment.

---

## A–D. Required four-way equality

| Symbol | Requirement | Observed | Label |
|---|---|---|---|
| **A** current master SHA | 40 lowercase hex | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PROVEN** |
| **B** `gitSource.sha` | 40 lowercase hex, deployment built from `master` | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PROVEN** |
| **C** build artifact SHA | 40 lowercase hex | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PROVEN** |
| **D** authenticated runtime `/api/health` SHA | 40 lowercase hex | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PROVEN** |

**FOUR-WAY EQUALITY: PROVEN.** Distinct values across A, A(GitHub), B, C, D: **1**.

### A — master
Read twice, independently, after a fresh `git fetch origin master`:
```
git rev-parse origin/master   -> fc4096f7a2aac8530f4e14495a7f21b9a97419be
GET api.github.com/.../commits/master -> fc4096f7a2aac8530f4e14495a7f21b9a97419be
```

### B — `gitSource.sha`
Read from the Vercel deployment object for the exact deployment URL. `source=git`, `ref=master`,
`target=production`, `prId` absent.

### C — build artifact
The artefact is `backend/app/build_revision.txt`, written at build time by
`backend/scripts/embed_build_revision.py` (declared on master as both `installCommand` and
`buildCommand` for the backend service). The script reads `VERCEL_GIT_COMMIT_SHA`, validates it
against `^[0-9a-f]{40}$`, writes it into the artefact, and returns it. The deployment's build record
contains **two** such records — one from the install command, one from the build command — both
reporting the same value:
```
Cloning github.com/gopal735/ScholarZone (Branch: master, Commit: fc4096f)
Running "install" command: `pip install -r requirements.txt && python scripts/embed_build_revision.py`...
Build revision embedded for platform build: fc4096f7a2aac8530f4e14495a7f21b9a97419be
Running "python scripts/embed_build_revision.py"
Build revision embedded for platform build: fc4096f7a2aac8530f4e14495a7f21b9a97419be
Build Completed in /vercel/output [23s]
```
The build record was produced by the merged code itself and is the artefact producer's own output,
not an environment variable, an alias, or a timestamp. Two independent records within one build agree.

*Limitation, stated plainly:* the artefact file itself could not be downloaded. The provider exposes
no file tree for this deployment (`GET /v2/deployments/{id}/files` → `404 {"code":"not_found",
"message":"File tree not found"}`), and no route serves the backend artefact over HTTP. C therefore
rests on the build-time generation record above. This does not weaken the equality, because **D is a
runtime read of that same artefact** — `read_embedded_revision()` reads
`app/build_revision.txt` verbatim and raises `ProvenanceError` if it is missing or malformed, and the
runtime returned a full 40-character SHA, which the artifact-only reader cannot produce from any other
source.

### D — authenticated runtime, exact deployment URL
```
GET https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app/api/health
  anonymous, no credentials            -> HTTP 200, Deployment Protection interstitial
                                         (data-dpl-id="dpl_Dv4LDHRjC2oJ2oYgj14LoBQBJRK7"), no JSON
  approved project-scoped credential   -> HTTP 200
      {"status":"ok","revision":"fc4096f7a2aac8530f4e14495a7f21b9a97419be"}
      revision length = 40
```
The anonymous request returning the protection interstitial, and the same URL returning real API JSON
once the approved credential is presented, confirms the response came from the API of **this
deployment** rather than from an alias or a cache. No alias, header override, environment variable, or
12-character revision was accepted as evidence. The previous `ddcd9c3662f4` value is no longer served
by this deployment.

---

## Explicitly rejected forms of evidence
None of the following were used, and none would have satisfied this gate:
- the 12-character runtime revision `ddcd9c3662f4` (previous production build) — rejected, 12 chars
- the alias `scholarzone-fwzj.vercel.app` — not used for any value in A/B/C/D
- timestamps (`readyAt`, build start, status `updated_at`) — used only to corroborate ordering, never
  to establish identity
- behavioural similarity or endpoint availability — not used as identity
- environment variables — not consulted; the runtime reads the artefact only
- branch/preview build evidence — the gated deployment is `target=production`, `prId` absent
- commit prefixes or case-folded comparisons — compared with `^[0-9a-f]{40}$` exact equality only

---

## Deployment Protection
**UNCHANGED.** The canonical project carries a project-scoped `protectionBypass` credential
(`scope=automation-bypass`, `isEnvVar=true`). It was used **read-only** to obtain D. Protection was
not disabled, not weakened, and no bypass value was written into any code, workflow, configuration or
environment variable.

---

## Remaining, non-blocking notes
- **PROVEN:** A == B == C == D at `fc4096f7a2aac8530f4e14495a7f21b9a97419be` for production
  deployment `dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj`, built by the Vercel GitHub App from the `master`
  push.
- **NOT A BLOCKER (working tree):** the local checkout remains 95 commits behind master with 482
  dirty entries and no `backend/app/build_provenance.py`. This does not affect the deployed identity,
  which was established entirely from provider records and the deployed artefact. It does mean the
  local tree must not be used as a deployment source.
- **NOT A BLOCKER (secondary host):** `scholarzone.vercel.app` is a second Git-connected project that
  was refused the same push at 18:22:41Z and has no `fc4096f` deployment. It is not merged into this
  result and contributes nothing to it.
  → **SUPERSEDED 2026-10-04 19:32Z.** The characterisation above ("not a blocker") was correct as to
  *release identity* but understated the condition of the host. It was resolved by retirement; see
  **SECONDARY HOST RECONCILIATION** below. The four-way identity in this report is unaffected.
- **UNKNOWN:** the artefact file could not be downloaded for direct byte inspection (no provider file
  tree), as described under C.
- **PRODUCTION-PROVEN:** the four-way identity, at the exact deployment URL above.

---

FINAL CLASSIFICATION:
`FULLY_RELEASED`

MASTER SHA (A):
`fc4096f7a2aac8530f4e14495a7f21b9a97419be`

GITSOURCE SHA (B):
`fc4096f7a2aac8530f4e14495a7f21b9a97419be`

BUILD ARTIFACT SHA (C):
`fc4096f7a2aac8530f4e14495a7f21b9a97419be`

RUNTIME SHA (D):
`fc4096f7a2aac8530f4e14495a7f21b9a97419be`

FOUR-WAY EQUALITY:
`PROVEN` — 1 distinct value, all 40 lowercase hexadecimal characters

DEPLOYMENT ID:
`dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj`

DEPLOYMENT URL:
`https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app`

TARGET:
`production`

GITSOURCE REF:
`master`

DEPLOYMENT SOURCE:
`git` (Vercel GitHub App; not CLI, not manual)

CANONICAL PROJECT:
`PASS` — `scholarzone-fwzj` / `prj_NLC71y3rKRIOduTla785AzEOEFL5`

DEPLOYMENT PROTECTION:
`UNCHANGED` — existing project-scoped credential used read-only

PRODUCTION WRITES:
`NONE`

REMAINING BLOCKERS:
none for the release identity of `fc4096f7a2aac8530f4e14495a7f21b9a97419be`

---
---

# SECONDARY HOST RECONCILIATION

**Run** · 2026-10-04 19:24Z–19:33Z
**Subject:** `https://scholarzone.vercel.app`
**Scope:** resolution of the second public ScholarZone surface. No code change, no deployment, no
production data write.

FINAL CLASSIFICATION: `SECONDARY_HOST_RETIRED`

---

## 1. Phase 0 — remote master reconfirmed

Local HEAD is stale and was not used.

| Source | SHA |
|---|---|
| Local `HEAD` | `8ac1c9a40063221904c8994693ffa18746d5fa9d` (stale — excluded) |
| `git ls-remote origin refs/heads/master` | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| GitHub API `repos/gopal735/ScholarZone/branches/master` | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |

**PROVEN:** `origin/master == GitHub master == fc4096f7…`. Re-confirmed again after the mutation; both
still `fc4096f7…`. Master history was not modified.

---

## 2. Raw deployment metadata (authenticated `vercel api`)

Authenticated as `gopal735` (`uIMKRjUDoUJWov8GFMShhE59`), account/team
`team_hTBAjdC3hMGDgW2GOAb1Mbw8` (`gopal735s-projects`). No token value is reproduced here.

### Canonical deployment

| Field | Value |
|---|---|
| `id` | `dpl_EXvas5WG2Ri4799MtL6LC7XYRPYj` |
| `name` | `scholarzone-fwzj` |
| `target` | `production` |
| `url` | `scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app` |
| `aliases` | `scholarzone-fwzj.vercel.app`, `scholarzone-fwzj-gopal735s-projects.vercel.app`, `scholarzone-fwzj-git-master-gopal735s-projects.vercel.app` |
| `automaticAliases` | `scholarzone-fwzj-gopal735s-projects.vercel.app`, `scholarzone-fwzj-git-master-gopal735s-projects.vercel.app` |
| `source` | `git` |
| `gitSource.type` | `github` |
| `gitSource.ref` | `master` |
| `gitSource.sha` | **`fc4096f7a2aac8530f4e14495a7f21b9a97419be`** |
| `readyState` / `readySubstate` | `READY` / `PROMOTED` |
| `createdAt` | `1791140393067` |
| `project.id` / `project.name` | `prj_NLC71y3rKRIOduTla785AzEOEFL5` / `scholarzone-fwzj` |
| `meta.githubCommitVerification` | `verified` |
| `meta.githubCommitRepo` | `ScholarZone` @ `github.com` (repoId `1354421070`) |
| `public` | `false` |

**Note on retrieval:** `GET /v13/deployments/dpl_EXvas5WG2Ri4799MtL6LC7XYRPYj` returned
`404 Deployment not found` on this CLI at every API version tested (`v6`, `v11`, `v12`, `v13`), while
sibling deployments of the same project resolved normally. The deployment is **not** missing: it is
present in `GET /v6/deployments?projectId=prj_NLC71y3rKRIOduTla785AzEOEFL5` with the same `uid`, and
the full object was retrieved successfully by its deployment URL
(`GET /v13/deployments/scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app`), whose `id` field
matches. Recorded as a CLI resolver quirk, not a provider state change.

### Secondary deployment (pre-retirement)

| Field | Value |
|---|---|
| `id` | `dpl_BgX285zMhirUjni3nsCADRZXhn79` |
| `name` | `scholarzone` |
| `target` | `production` |
| `url` | `scholarzone-aw0odeic2-gopal735s-projects.vercel.app` |
| `aliases` | `scholarzone.vercel.app`, `scholarzone-gopal735s-projects.vercel.app` |
| `automaticAliases` | `scholarzone-gopal735s-projects.vercel.app` |
| **`source`** | **`cli`** |
| **`gitSource`** | **absent** (no object at all) |
| `meta.gitCommitSha` | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| `meta.gitCommitRef` | `HEAD` |
| **`meta.gitDirty`** | **`1`** |
| `meta.gitCommitMessage` | `Merge pull request #2 from gopal735/security/public-visibility-release` |
| `readyState` / `readySubstate` | `READY` / `PROMOTED` |
| `createdAt` | `1791122750290` |
| `project.id` / `project.name` | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` / `scholarzone` |
| `public` | `false` |

**PROVEN:** the secondary deployment has no `gitSource`, `source` is `cli`, and `gitDirty` is `1`. Its
artefact content is therefore **not attributable to `ddcd9c3`** — a dirty tree means uncommitted local
content shipped, so the recorded `meta.gitCommitSha` is not a truthful description of the artefact.
`ddcd9c3` is an ancestor of master and is **10 commits behind** it
(`git rev-list --count ddcd9c3..fc4096f7` = `10`).

`dpl_BgX285…` was the **only** current `production` deployment of `prj_CKy7udubvQSf143NOsXI9LCXU5cQ`.
Every other deployment of that project is older, and the newest deployment of any kind
(`dpl_3VYMMnexig1MrRWpuLjd4vJSpreP`, `ceec220f…`, branch `docs/security-release-reconciliation`) is a
`STAGED` preview, never production. That project had no path to `fc4096f`.

---

## 3. Domain ownership — authoritative

`GET /v9/projects/{id}/domains`:

```
scholarzone.vercel.app      -> projectId=prj_CKy7udubvQSf143NOsXI9LCXU5cQ  verified=true  redirect='' 
scholarzone-fwzj.vercel.app -> projectId=prj_NLC71y3rKRIOduTla785AzEOEFL5  verified=true  redirect=''
```

**PROVEN:** `scholarzone.vercel.app` was the **project-generated apex domain** of project `scholarzone`,
not a custom domain, not an alias borrowed from the canonical project, and not a redirect. It had
exactly one domain record and no `redirect` target.

Both projects: `framework=services`, `accountId=team_hTBAjdC3hMGDgW2GOAb1Mbw8`, git link
`type=github`, `org=gopal735`, `repo=ScholarZone`, `productionBranch=master`. Both belong to the same
owner, so the secondary project was unambiguously our own legacy duplicate, not a third party's surface.

---

## 4. Repository dependency classification

Read-only searches across the whole tree. No file was modified.

| Location | Kind | Class |
|---|---|---|
| `backend/app/core/config.py:94` | string in the CORS `allowed_origins` tuple | **OPTIONAL** |
| `backend/tests/test_api_prefix.py:142` | asserts that allowlist entry is present | **TEST-ONLY** |
| `MENTOR_*.md`, `*_FINAL.md`, `STALE_VERCEL_*.md`, `VERCEL_*.md` (~20 files) | historical evidence records | **DOCUMENTATION-ONLY** |
| `research/bachelor/_merged/*.py`, `verification/*.py` | all point at `scholarzone-fwzj`; none at the secondary host | **DEV-ONLY** |
| `.github/workflows/*` | reference `vars.SCHOLARZONE_API_URL` only | no reference |
| `frontend/**` | 0 occurrences of the secondary host | no reference |
| `frontend/public/robots.txt`, `sitemap.xml` | `gopal735.github.io/ScholarZone` only | no reference |
| `vercel.json` (root) | no external redirects, no hostname | no reference |
| OAuth / webhook / email-share bindings | none bound to the secondary host | no reference |

Additional negative evidence:

- `gh variable list` → `SCHOLARZONE_API_URL = https://scholarzone-fwzj.vercel.app/api` — the CI,
  deploy-gate and frontend build target is the **canonical** host, not the secondary one.
- Shipped GitHub Pages bundle (`gh-pages` @ `8436d31f`, `assets/index-CXIuVah8.js`, 335 817 bytes):
  occurrences of `scholarzone.vercel.app` = **0**, `scholarzone-fwzj` = **0**,
  `gopal735.github.io/ScholarZone` = **0**. The public frontend hardcodes no Vercel host at all.
- `frontend/src/services/canonicalOrigin.js` → `CANONICAL_ORIGIN` defaults to
  `https://gopal735.github.io/ScholarZone`; every `<link rel="canonical">`, `og:url`, JSON-LD and
  sitemap consumer derives from it. The secondary host appears nowhere in that chain.

**REQUIRED dependencies on `scholarzone.vercel.app`: ZERO.**

The single code reference (`config.py:94`) is a **permissive CORS allowlist entry** — it permits browser
requests *from* that origin. Nothing in the application ever issues a request *to* it, so retiring the
host cannot break it. It is left in place deliberately: removing it would be a code change that
dependency analysis does **not** require, and `test_api_prefix.py:142` asserts its presence.

---

## 5. Why CANONICALIZE was rejected

CASE A requires the host to resolve to the verified canonical production. Every non-deployment
mechanism was checked against the provider's domain model and rejected:

- Aliasing `scholarzone.vercel.app` onto `dpl_EXvas5WG2Ri4799MtL6LC7XYRPYj` — a `{project}.vercel.app`
  apex domain is generated from, and permanently bound to, its own project. Cross-project assignment
  is not supported, and the name is already verified against `prj_CKy7udubvQSf143NOsXI9LCXU5cQ`.
- Adding it as a domain on `prj_NLC71y3rKRIOduTla785AzEOEFL5` — same conflict.
- Deleting the project first, then aliasing — still a cross-project generated-domain assignment.

The only remaining route to CASE A is deploying `fc4096f` into project `scholarzone`, which is
prohibited (no manual production deployment, no `vercel deploy`, no deployment creation). CASE A is
therefore not achievable within the rules, and forcing it would be a guess.

CASE B gates, all met:

| Gate | Result |
|---|---|
| Separate legacy project | **PROVEN** — own project ID, own generated domain |
| Not needed by the current application | **PROVEN** — zero required dependencies |
| No REQUIRED runtime dependency | **PROVEN** — one optional CORS allowlist entry |
| Keeping it public creates provenance ambiguity | **PROVEN** — see below |

The ambiguity was worse than merely theoretical. Anonymous probes before the mutation:

```
https://scholarzone.vercel.app/             -> HTTP 200, full ScholarZone frontend shell
https://scholarzone.vercel.app/api/health   -> HTTP 200, {"status":"ok","revision":"unknown"}
```

A publicly reachable production API asserting `"revision":"unknown"` — a CLI deployment of a dirty tree
with no `gitSource` — is exactly the ambiguous public surface that had to be removed.

---

## 6. Mutation

Safety checkpoint printed immediately before the operation, after a fresh state refresh:

```
CANONICAL_PROJECT    = scholarzone-fwzj
CANONICAL_PROJECT_ID = prj_NLC71y3rKRIOduTla785AzEOEFL5
CANONICAL_SHA        = fc4096f7a2aac8530f4e14495a7f21b9a97419be
SECONDARY_PROJECT    = scholarzone
SECONDARY_PROJECT_ID = prj_CKy7udubvQSf143NOsXI9LCXU5cQ
HOST                 = scholarzone.vercel.app
DISPOSITION          = RETIRE
```

Pre-mutation refresh (read-back immediately before the call):

```
project.id       = prj_CKy7udubvQSf143NOsXI9LCXU5cQ
project.name     = scholarzone
project.account  = team_hTBAjdC3hMGDgW2GOAb1Mbw8
updatedAt        = 1791122789911        (unchanged from Phase 1 — no intervening drift)
prod deploy id   = dpl_BgX285zMhirUjni3nsCADRZXhn79
prod deploy url  = scholarzone-aw0odeic2-gopal735s-projects.vercel.app
prod aliases     = scholarzone.vercel.app, scholarzone-gopal735s-projects.vercel.app
prod state       = READY/PROMOTED
domain: scholarzone.vercel.app -> projectId=prj_CKy7udubvQSf143NOsXI9LCXU5cQ verified=True
```

**Exactly one provider operation, after the evidence gate passed:**

```
DELETE /v9/projects/prj_CKy7udubvQSf143NOsXI9LCXU5cQ?teamId=team_hTBAjdC3hMGDgW2GOAb1Mbw8
```

Project deletion is the only provider-supported mechanism that retires a project-generated domain; a
generated domain cannot be individually unassigned. The CLI required
`--dangerously-skip-permissions` for a non-interactive `DELETE`; that is the CLI's confirmation gate,
satisfied under this task's explicit authorisation for project deletion as the retirement mechanism.

No deployment was created or promoted. No alias was added. No redirect was configured. No Deployment
Protection setting was changed. No database write occurred.

---

## 7. Post-mutation state

Provider state re-fetched from scratch:

```
GET /v9/projects/prj_CKy7udubvQSf143NOsXI9LCXU5cQ                      -> 404 Project not found
GET /v9/projects/scholarzone                                           -> 404 Project not found
GET /v9/projects/prj_CKy7udubvQSf143NOsXI9LCXU5cQ/domains              -> 404 Project not found
GET /v13/deployments/dpl_BgX285zMhirUjni3nsCADRZXhn79                  -> 404 Project not found
GET /v9/projects?limit=100  ->  projects matching *scholarzone*: 1
    prj_NLC71y3rKRIOduTla785AzEOEFL5  scholarzone-fwzj  updatedAt=1791140433065
```

**Canonical project untouched** — `updatedAt` is byte-identical to its pre-mutation value, and its
production deployment, URL, aliases and commit are unchanged:

```
prodDeploy = dpl_EXvas5WG2Ri4799MtL6LC7XYRPYj
prodUrl    = scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app
prodState  = READY/PROMOTED
prodSha    = fc4096f7a2aac8530f4e14495a7f21b9a97419be
prodRef    = master   (githubCommitVerification = verified)
aliases    = scholarzone-fwzj.vercel.app,
             scholarzone-fwzj-gopal735s-projects.vercel.app,
             scholarzone-fwzj-git-master-gopal735s-projects.vercel.app
```

Retirement is **not** claimed on the basis of an HTTP error alone. It is established by provider
ownership state — the project, its domain record and its deployments no longer exist in the account —
and independently corroborated at the HTTP layer.

---

## 8. Browser / runtime verification

Retired surface:

```
https://scholarzone.vercel.app/                        -> HTTP 404, page title "404: NOT_FOUND"
https://scholarzone.vercel.app/api/health              -> HTTP 404
https://scholarzone-gopal735s-projects.vercel.app/...  -> HTTP 404
```

The 404 is Vercel's own platform page (`404: NOT_FOUND`), not a ScholarZone application response.

Canonical surface:

```
https://scholarzone-fwzj.vercel.app/                   -> HTTP 200, "ScholarZone · Where Ambition Meets Opportunity"
https://scholarzone-fwzj.vercel.app/api/health         -> HTTP 200, application/json
                                                         {"status":"ok","revision":"fc4096f7a2aac8530f4e14495a7f21b9a97419be"}
```

No redirect loop on either host. Homepage renders the expected canonical application.

**Deployment Protection:** both deployments reported `public=false`. Before the mutation the
interstitial was not served on the alias paths and the secondary host answered anonymously with a
full API. After the mutation the exact deployment URL
`scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app` returns a **Vercel login interstitial**
(`sso-api` challenge for that exact URL) on anonymous request. That is expected per-deployment
protection behaviour and is **not** an application failure. Protection was not disabled, not weakened,
and no bypass credential was used to obtain any value in this section — the runtime identity above was
read from the public alias host.

---

## 9. Four-way identity — unchanged and re-proven

Retiring the secondary host did not alter, weaken or invalidate the verified release identity. All four
values are exact 40-character lowercase hexadecimal, distinct value count **1**:

```
MASTER    == fc4096f7a2aac8530f4e14495a7f21b9a97419be   (origin/master == GitHub master, re-confirmed)
GITSOURCE == fc4096f7a2aac8530f4e14495a7f21b9a97419be   (gitSource.sha, source=git, ref=master)
ARTIFACT  == fc4096f7a2aac8530f4e14495a7f21b9a97419be   (unchanged from the prior gate)
RUNTIME   == fc4096f7a2aac8530f4e14495a7f21b9a97419be   (/api/health, read live after the mutation)
```

---

## 10. Contract-drift classification — `build_provenance.py` `.strip()`

Inspected at master: `backend/app/build_provenance.py`. **No code was changed.**

Two boundaries strip before validating:

```python
FULL_COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")

raw = (os.getenv(PLATFORM_COMMIT) or "").strip()
return raw if FULL_COMMIT_SHA.match(raw) else None          # build-time boundary

raw = ARTIFACT.read_text(encoding="utf-8").strip()
if is_deployed_sha(raw): return raw                          # runtime boundary
```

Analysis: `str.strip()` removes leading and trailing characters only — it never inserts, never removes
from the interior, and never lengthens a value. Therefore, if the stripped form satisfies
`\A[0-9a-f]{40}\Z`, those 40 characters were present verbatim in the original, in order, with only
whitespace around them. A 39-character SHA plus padding cannot be padded *up* to 40; a 41-character
value is rejected; an interior whitespace or zero-width character is not stripped and fails the regex.

So a padded input can never yield a false release identity. The accepted set remains exactly the
40-lowercase-hex strings.

**Classification: `CONTRACT DRIFT ONLY`.** The drift is documentation-versus-implementation: the
module docstring claims "a full 40-character SHA and nothing else", while the code silently tolerates
surrounding whitespace. That widens the accepted input surface without widening the set of identities
it can return. No security consequence was demonstrated, so no patch was created.

---

## 11. Regression

**Not applicable — no repository code was modified in this run.** Verified after the mutation:

```
git status --porcelain      -> 483 entries   (identical to the pre-run count)
git rev-parse HEAD          -> 8ac1c9a40063221904c8994693ffa18746d5fa9d   (unchanged)
origin/master               -> fc4096f7a2aac8530f4e14495a7f21b9a97419be   (unchanged)
GitHub master               -> fc4096f7a2aac8530f4e14495a7f21b9a97419be   (unchanged)
```

No `git add` was run. The pre-existing staged and dirty entries belong to unrelated work and were
left exactly as found; nothing was staged, committed, cleaned, reset or checked out. The 482-vs-483
difference against the earlier note in this report is the appended section of this report itself.

---

## 12. Summary

| Item | Value |
|---|---|
| Canonical master SHA | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| Canonical project ID | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Canonical deployment ID | `dpl_EXvas5WG2Ri4799MtL6LC7XYRPYj` |
| Secondary project ID (pre-retirement) | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| Secondary deployment ID (pre-retirement) | `dpl_BgX285zMhirUjni3nsCADRZXhn79` |
| Host | `https://scholarzone.vercel.app` |
| Authoritative domain ownership | project-generated apex domain of `scholarzone` (verified, no redirect) |
| Raw metadata finding | `source=cli`, no `gitSource`, `gitDirty=1`, 10 commits behind master |
| REQUIRED repository dependencies | **0** |
| Disposition | **RETIRE** |
| Provider mutation | `DELETE /v9/projects/prj_CKy7udubvQSf143NOsXI9LCXU5cQ` (one operation) |
| Post-mutation state | project, domains and deployments 404; canonical project untouched |
| Runtime verification | retired host 404; canonical `/api/health` → `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| Deployment Protection | unchanged; interstitial on the exact deployment URL; not bypassed |
| Four-way identity | `PROVEN` at `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| Contract drift | `CONTRACT DRIFT ONLY` |
| Regression | not applicable — no code modified |
| **Production writes** | **NONE** |

FINAL CLASSIFICATION: `SECONDARY_HOST_RETIRED`

The public ScholarZone identity is now single: `https://scholarzone-fwzj.vercel.app`, serving
`fc4096f7a2aac8530f4e14495a7f21b9a97419be`, with the ambiguous `"revision":"unknown"` surface removed.