# SCHOLARZONE_FINAL_SECURITY_PROVENANCE_RELEASE.md

# FINAL CLASSIFICATION: `NEEDS_REWORK`

**The infrastructure blockers are closed.** Exact protected-preview provenance is now **PROVEN**, and
the canonical frontend is **PROVEN** to be GitHub Pages. One blocker remains and it is not a code
problem: **`scholarzone.vercel.app` still publicly serves an API on revision `3ee434c`, which predates
the security fix.** Remediation requires owner approval, which I cannot grant.

No production deployment. No production DB write. No master rewrite. Deployment Protection never
disabled. No quota bypass. No project or alias deleted.

---

## 1. Current Master — PROVEN
`origin/master` = **`573a983b004ab08578497272659123323ab489b7`** (`docs: the wording fix is deployed and
verified in production`). Fetched fresh; unmodified.

## 2. Security PR — PROVEN
| | |
|---|---|
| Branch | `origin/security/public-visibility-release` |
| Head | **`0b9fe00ccbaaaf16502376d0d92e1f95e4b4c467`** (`docs: anchor every verified figure to 38700d8 rather than the tip`) |
| Parent | `1b259b9` |
| On master | **no** |
| Diff | `scholarships.py` (+34/−2), **new** `test_public_detail_visibility.py` (458), 2 release docs |

Four files only. **No Match, Count, Mentor, Supervisor, image or Wave 1–3 change. PROVEN.**

## 3. Vulnerability — PROVEN from the diff
`GET /api/scholarships/{id}` called `get_scholarship_by_id` — a bare primary-key lookup. The detail
endpoint was therefore a **second, larger universe than its own list**: archived, quarantined,
awaiting-review and image-gate-failing records stayed fully readable by walking ids. The detail was
more permissive than the list, which is the wrong way round for a trust surface.

## 4. Security Fix — PROVEN correct
| Requirement | Status |
|---|---|
| public detail → canonical `public_visibility_conditions()` | **PROVEN** — imported from `repositories.scholarships`, not restated |
| shared permissive loader remains permissive | **PROVEN** — `get_scholarship_by_id` deliberately untouched |
| admin verifier still reaches hidden records | **PROVEN by design** — stated and preserved |
| verification pipeline still reaches hidden records | **PROVEN by design** |
| hidden ID ≡ missing ID (same status/body) | **VALIDATED** — 458-line regression suite present |
| no internal field leakage | **VALIDATED** — covered by that suite |

The rationale in the code is correct: tightening the shared loader would have broken the admin and
verification paths **without closing this hole**.

## 5. Canonical Frontend — PROVEN
**`https://gopal735.github.io/ScholarZone/`** — unchanged, not moved.
Evidence: `robots.txt` Sitemap directive; every `sitemap.xml` `<loc>`; live HTTP 200 serving
`index-Bhvmyxum.js`; `origin/gh-pages` contains the built bundle. Neither Vercel project owns a custom
domain, so neither can be the canonical frontend.

## 6. Canonical Backend — PARTIALLY PROVEN
| Evidence | Conclusion |
|---|---|
| CI target `https://scholarzone-fwzj.vercel.app/api` | **PROVEN as CI target** |
| `scholarzone-fwzj` tracks master; `scholarzone` does not | **PROVEN** — operational primary |
| Frontend bundle API base (live gh-pages JS) | **UNKNOWN** — not extracted this session |

**The canonical backend is `scholarzone-fwzj` on operational and CI evidence, but the canonical
*frontend's* configured API base was not independently extracted. Treated as UNKNOWN, not assumed.**

## 7. Vercel Project A — `scholarzone` — PROVEN
Project `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` · repo `gopal735/ScholarZone` (`1354421070`) · production
branch `master` · prod deploy `scholarzone-bvl7g26in-…` · **serves `3ee434c01f53`** · aliases
`scholarzone.vercel.app`, `…-git-master-…` · **no custom domain** · git-connected but **not tracking
master**. API exposed: **yes** (`/api/health`, `/api/scholarships`, `/api/mentor/overview` all live).
Frontend bundle served: **yes**.

## 8. Vercel Project B — `scholarzone-fwzj` — PROVEN
Project `prj_NLC71y3rKRIOduTla785AzEOEFL5` · same repo/branch · prod deploy
`scholarzone-fwzj-oxfgjct80-…` · **serves `4edd154a3037`** · aliases `scholarzone-fwzj.vercel.app`,
`…-git-master-…` · **no custom domain** · **tracking master**. CI API target.

Both share one repository ID — **not** a fork mismatch. Both expose a full API.

## 9. Build-Time Provenance — PROVEN
From real build logs of preview `dpl_8jVxtoageFxCUxp6FbLvnEVUMgAa`:
```
Installing required dependencies from backend/requirements.txt...
Running "python scripts/embed_build_revision.py"
Build revision embedded for platform build: 255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
```
`buildCommand` **does** execute for this `framework: fastapi` service — proven from logs, not inferred
from schema. `installCommand` (`pip install -r requirements.txt && python scripts/…`) retained as a
second fail-closed path.

## 10. Runtime Artifact — PROVEN
Artifact `app/build_revision.txt`, inside the package, content derived **only** from the commit SHA
(no timestamp, hostname or run id — determinism and idempotency are tested). Runtime reads that
artifact only: `VERCEL_GIT_COMMIT_SHA`, `SCHOLARZONE_BUILD_REVISION`, headers, query params, branch
names and deployment URLs are all proven inert by test. Missing **or corrupt** in production fails
closed; `/health` returns 503 rather than `"unknown"`. Full 40 chars, never truncated.

## 11. Exact Deployment Preview Proof — PROVEN
| Field | Value |
|---|---|
| Deployment ID | `dpl_8jVxtoageFxCUxp6FbLvnEVUMgAa` |
| Deployment URL | `https://scholarzone-6c0x9o1g8-gopal735s-projects.vercel.app` |
| Project | `scholarzone` |
| `gitSource.ref` | `rc/revision-provenance` |
| `gitSource.sha` | `255ca97556c0d3ad74a93d5644ea17e7d79e2d7f` |

## 12. Protected Preview Access — PROVEN (method corrected)

**The earlier failure was a wrong CLI invocation, not a protection problem.** Deployment Protection
was never disabled.

`vercel curl --help` documents `--deployment <ID|URL>`. The form I had used —
`vercel curl <path> <url>` — treats the URL as positional and is answered by the **linked project's
production**. Proven: the same preview URL returned `4edd154a3037` (fwzj production) from a
fwzj-linked directory and `3ee434c01f53` (scholarzone production) from a scholarzone-linked one.

The correct form binds the request to one deployment:
```
vercel curl /api/health --deployment dpl_8jVxtoageFxCUxp6FbLvnEVUMgAa --yes
```

## 13. SHA Equality Proof — **PROVEN** (the full chain)

```
Vercel gitSource.sha              255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
build-time embedded SHA          255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
app/build_revision.txt           255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
runtime build_revision()         255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
GET /api/health  "revision"      255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
```

**Exact 40-character equality at every link.** No prefix matching anywhere.

**Corroborating proof the new runtime is deployed:** the previous implementation returned
`raw[:12]`. A 40-character value is impossible under it. Separately, the old runtime was proven
incapable of reporting the wrong commit here — the "runtime reports stale SHA" finding from earlier
turns is **withdrawn**; it was a production response mistaken for a preview.

## 14. Browser Identity Gate — PROVEN
`backend/scripts/verify_release_identity.py` (`verify_release_identity(expected_sha, exact_url)`):

| Check | Status |
|---|---|
| rejects a truncated SHA | **PROVEN** — `255ca97556c0` → rejected |
| rejects a wrong full SHA | **PROVEN** — `0000…` → exit 1 |
| binds to one deployment ID | **PROVEN** |
| fetches exact deployment metadata | **PROVEN** |
| refuses an alias | **PROVEN** (implemented; no alias reached it) |
| exact protected-preview access | **PROVEN** — `--deployment` |
| compares exact SHA | **PROVEN** |
| fails loudly on mismatch | **PROVEN** — both negative cases exit 1 |
| **PASSES on the true deployment** | **PROVEN** — `exit=0`, "PASS: build identity and runtime provenance are the same commit" |

Asking for deployment A therefore **cannot** silently verify deployment B or production: the request is
bound by ID, and the negative tests prove it rejects rather than degrades.

## 15. Security E2E — NOT RUN (correctly)
Gated behind §14, which now passes. Not run this session: it requires the security fix merged and
deployed, and §17 forbids deploying the feature branch. **No stale uvicorn, Vite, SQLite or
cross-environment evidence was accepted.**

## 16. Rate Limit — UNKNOWN (checked once)
`/v2/user` returned empty rate-limit fields, so the state is **UNKNOWN**, not confirmed active and not
confirmed cleared. **No deployment was attempted**, so no conclusion depends on it. No quota bypass,
alternate account, alternate project or undocumented route was used.

## 17. Stale Project Remediation — PREPARED, NOT EXECUTED

`scholarzone.vercel.app` classification: **B — stale backend/API, still publicly serving the
vulnerability.** It serves `3ee434c`, which predates the security fix, and exposes a full API
(`/api/health`, `/api/scholarships`, `/api/mentor/overview` confirmed live). `27047de` is also absent
from it, so it is behaviourally divergent as well as vulnerable.

Accessible routes confirmed read-only on that host: `/api/health` 200, `/api/scholarships` 200,
`/api/mentor/overview` 200, `/api/dashboard/` 401, `/api/applications/` 401.

**Prepared, requires owner approval before any mutation:**
- **Preferred:** retire `scholarzone.vercel.app` as a public alias so no vulnerable API is reachable.
- **Acceptable:** converge it to the same security-fixed revision.
- **Unacceptable:** leaving it public on `3ee434c`.

**Nothing was deleted or modified.** Per rule 11 and Phase 10, this waits on explicit owner approval.

## 18. Exact Git Diff
Provenance work — branch `rc/revision-provenance` (parent `00bc39d`, **not merged**):

| Commit | Content |
|---|---|
| `255ca975` | `build_provenance.py`, `embed_build_revision.py`, `test_build_provenance.py`, `main.py`, `vercel.json`, `deploy.yml`, 2 updated test files |
| `d050d306` | `vercel.json` `installCommand`; 4 build-wiring tests |

| Suite | Result |
|---|---|
| `test_build_provenance.py` | **40 passed** |
| Full backend (at `255ca975`) | **5013 passed**, 2 pre-existing failures |
| Frontend vitest / build / lint | **163 passed** / success / 0 errors |

Pre-existing failures, verified on the untouched base: `test_efficiency_safety…test_the_retry_shares_the_concurrency_group`
and `TestDiscoveryQualityGate…test_it_measures_against_the_real_catalogue`.

## 19. Remaining Unknowns
1. **BLOCKING** — `scholarzone.vercel.app` publicly serves a vulnerable API; remediation needs owner approval.
2. **UNKNOWN** — rate-limit state.
3. **UNKNOWN** — the canonical frontend's configured API base (backend canonicality rests on CI + operational evidence).
4. **UNKNOWN** — whether GitHub Pages rewrites `/api` to that backend, or serves a static snapshot.
5. Not done: security E2E and browser identity gate run against a deployed security build.

## 20. Final Release Procedure
**On quota reset — in this exact order, re-reading state at each step:**
1. Re-read `origin/master`; re-read PR #2 head/base (`0b9fe00` / its base).
2. Re-read both Vercel production SHAs; confirm nothing moved.
3. Confirm the canonical backend target.
4. Re-verify the identity mechanism on a fresh preview: `verify_release_identity.py` must PASS.
5. **Owner approves** stale-`scholarzone` remediation (Phase 10).
6. Merge **PR #2 alone** to master. Do not bundle Mentor, Supervisor, Wave 1–3, Count, Match or UI.
7. Provenance ships as a **separate infrastructure PR** (Phase 17 option A) — keep review surface minimal.
8. Let the normal master Git deployment run. **Never deploy the feature branch directly.**
9. Post-deploy proof: capture the deployment Git SHA → call the canonical backend `/api/health` →
   require exact 40-char equality → confirm GitHub Pages points at it → security E2E
   (public 200, hidden 404, nonexistent 404, hidden ≡ nonexistent in status/body) → confirm admin and
   verification paths still reach hidden records.
10. If `scholarzone.vercel.app` is still public on an old revision, **do not declare the release
    complete.**

## 21. Final Decision — `NEEDS_REWORK`

**Closed this session (real proof, not documentation):**
- Exact protected-preview provenance **PROVEN**, end to end, full 40-char equality across all five links.
- The `--deployment` read method **PROVEN**; the earlier "mismatch" **withdrawn** as a mis-invocation.
- Release identity gate **PROVEN** including two negative tests and a real PASS.
- Canonical frontend **PROVEN** as GitHub Pages, unmoved.
- Security PR **PROVEN** correctly scoped, using the canonical predicate while leaving the permissive
  loader intact for admin and verification.

**The remaining blocker is not code.** `scholarzone.vercel.app` is a second, publicly reachable backend
on `3ee434c`, which predates the fix. Rule 10 forbids leaving a known-vulnerable public API unmanaged,
and Phase 10 forbids deleting or repointing it without owner-approved evidence. Both cannot be
satisfied by me alone.

**Therefore not `READY_FOR_MERGE`** — deployment infrastructure still carries a safety ambiguity (an
unmanaged vulnerable public API), even though the ambiguity is now fully documented.
**Not `READY_FOR_POST_RESET_DEPLOY`** — that additionally requires stale-backend exposure *resolved*,
and it is only documented. **Not `READY_FOR_PRODUCTION_RELEASE`** — that may only be reported after
actual production proof.

**One owner decision unblocks this:** approve retiring or converging `scholarzone.vercel.app`.
With that, and a green quota window, the path in §20 is mechanical.