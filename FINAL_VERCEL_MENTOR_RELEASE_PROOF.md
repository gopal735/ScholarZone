# FINAL_VERCEL_MENTOR_RELEASE_PROOF.md

# FINAL CLASSIFICATION: `BLOCKED`

**Blocking condition:** the protected preview cannot be read. Phases 5, 6, 8, 15 and 19 — the runtime
half of the provenance chain — are unproven. Build execution (Phase 2) and the canonical host
(Phase 11) were **proven** this session.

No production deployment. No production DB write. No master change. No global Deployment Protection
change. No project deleted, no alias deleted.

---

## 1. Current Master — PROVEN

| | |
|---|---|
| `origin/master` | `573a983b004ab08578497272659123323ab489b7` |
| Subject | `docs: the wording fix is deployed and verified in production` |
| Date | 2026-10-04 17:51:07 +0600 |
| Changed | **no** |

`git fetch origin --prune` run first; nothing assumed.

## 2. Mentor Candidate — PROVEN, and **not** the earlier SHA

| | |
|---|---|
| SHA | `a4d5833b4c3e16f41f11fc7b777751c9aff4ee38` |
| Subject | `fix(mentor): scope the evidence fingerprint to the record that owns the chip` |
| **Parent** | **`573a983` — i.e. directly on current master** |
| Diff | `evidence.py` (+20/−3), **new** `test_evidence_record_identity.py` (236 lines) |

**This is a different lineage from the earlier `00bc39d`.** `00bc39d`'s parent was `3ee434c` (old
production); `a4d5833` sits directly on master. It is the correct "final PR" shape.

**PROVEN conflict-free?** Not re-derived this session — the earlier conflict analysis was for the
*other* candidate. Recorded as **UNKNOWN**; must be re-checked against `a4d5833`, not `00bc39d`.

## 3. Provenance Implementation — PROVEN (A–F)

Audited at `origin/rc/revision-provenance` (commits `255ca975`, `d050d306`).

| Requirement | Status | Evidence |
|---|---|---|
| A. Build-time source is the Vercel Git SHA | **PROVEN** | reads `VERCEL_GIT_COMMIT_SHA`; build log: `Build revision embedded for platform build: 255ca975…` |
| B. Requires exactly 40 lowercase hex | **PROVEN** | `\A[0-9a-f]{40}\Z`; 10 malformed inputs rejected by test |
| C. Writes artifact into the deployed package | **VALIDATED** | `app/build_revision.txt`, inside the package |
| D. Runtime reads only the artifact | **VALIDATED** | 40 tests; no other source in `build_revision()` |
| E. Env cannot override | **VALIDATED** | `SCHOLARZONE_BUILD_REVISION` and `VERCEL_GIT_COMMIT_SHA` both proven inert |
| F. Full SHA retained, no truncation | **VALIDATED** | 40 chars asserted; old code truncated to 12 |

Wiring is asserted by tests reading `vercel.json`, so deleting it breaks a build rather than silently
disabling provenance: `buildCommand` **and** `installCommand`
(`pip install -r requirements.txt && python scripts/embed_build_revision.py`) — the latter `&&`
fails the install, therefore the build.

## 4. Actual Build Execution Proof — **PROVEN** (the key unknown, resolved)

From `vercel inspect scholarzone-6c0x9o1g8… --logs`:

```
Installing dependencies...
Installing required dependencies from backend/requirements.txt...
Running "python scripts/embed_build_revision.py"
Build revision embedded for platform build: 255ca97556c0d3ad74a93d5644ea17e7d79e2d7f
```

| Phase 2 requirement | Status |
|---|---|
| Vercel actually executes the provenance build step | **PROVEN** |
| The step receives the exact Git SHA for THAT deployment | **PROVEN** — `255ca975…`, equal to `gitSource.sha` |
| `gitSource.sha ==` generated artifact SHA | **PROVEN** |

This is no longer an inference from schema support. `buildCommand` **does** execute for this
`framework: fastapi` service. The `installCommand` addition is retained as a second, fail-closed path.

## 5. Deployment-Specific Preview Identity — PROVEN (metadata)

Identity is bound to one deployment, never an alias:

| Field | Value |
|---|---|
| Deployment ID | `dpl_8jVxtoageFxCUxp6FbLvnEVUMgAa` |
| Deployment URL | `https://scholarzone-6c0x9o1g8-gopal735s-projects.vercel.app` |
| Project | `scholarzone` |
| `gitSource.ref` | `rc/revision-provenance` |
| `gitSource.sha` | `255ca97556c0d3ad74a93d5644ea17e7d79e2d7f` |

## 6. Protected Preview Access Method — **BLOCKED**, and the tool is unsafe

**Deployment Protection was not disabled. No global setting was changed.**

Direct unauthenticated HTTPS returns a Vercel login page whose own `data-dpl-id`
(`dpl_9u7pHkKkg11CDQPLjLV9NfZVjQtD`) is **not** the deployment requested.

**`vercel curl <path> <url>` ignores the URL and answers from the linked project's PRODUCTION.**
Demonstrated directly:

| Working directory linked to | URL requested | Response |
|---|---|---|
| `scholarzone-fwzj` | preview `6c0x9o1g8` | `4edd154a3037` = **fwzj production** |
| `scholarzone` | preview `6c0x9o1g8` | `3ee434c01f53` = **scholarzone production** |

**This retires the defect I reported in earlier turns.** I claimed the runtime environment reported
a stale commit. It did not: every "mismatch" was production being returned for a preview request.
The `4edd154a3037` value is 12 characters, which the rewritten `build_revision()` cannot emit —
independent proof it never came from the preview.

**Consequence:** no trustworthy read of a protected preview is available with the current CLI and
settings. `vercel curl` also rejects `--yes` in CLI 59.11.7, so it cannot be made non-interactive.

## 7. Artifact Packaging Proof — **BLOCKED**

Build-time generation is proven (§4). That the artifact is *inside the deployed package* and read at
runtime is **not** proven: it requires reading the preview's `/api/health`.

Chain status: build source → artifact generated **PROVEN**; artifact shipped → runtime reads → health
returns — **BLOCKED**.

## 8. Health SHA Proof — **BLOCKED** on a real deployment

**VALIDATED locally only:** 40 tests prove the runtime reads the artifact, ignores env and headers,
returns the full SHA, and fails on a corrupt artifact. Per the absolute rule, a passing local test is
**not** accepted as proof of deployed behaviour.

## 9. Deploy Gate Proof — **VALIDATED** (static)

| Assertion | Value |
|---|---|
| compares `[ "$CURRENT" = "$EXPECTED_REVISION" ]` | true |
| requires exactly `^[0-9a-f]{40}$` | true |
| `EXPECTED_SHORT` removed / no `:0:12` | true / true |
| HTTP 200, `status: ok`, non-SHA refusal retained | true |

**Strictly stronger** than the previous 12-character prefix comparison. No prefix matching remains.

## 10. Vercel Project A — `scholarzone` — PROVEN

| | |
|---|---|
| Project ID | `prj_CKy7udubvQSf143NOsXI9LCXU5c5cQ`→ `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| Repository | `gopal735/ScholarZone`, repoId `1354421070` |
| Production branch | `master` (git-connected; `…-git-master-…` alias) |
| Production deployment | `scholarzone-bvl7g26in-…` |
| Served SHA | `3ee434c01f53` |
| Domains | `scholarzone.vercel.app`, `…-git-master-…`; **no custom domain** |
| Automatic deployments | connected, but **not tracking master** |

## 11. Vercel Project B — `scholarzone-fwzj` — PROVEN

| | |
|---|---|
| Project ID | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Repository | `gopal735/ScholarZone`, repoId `1354421070` |
| Production branch | `master` |
| Production deployment | `scholarzone-fwzj-oxfgjct80-…` |
| Served SHA | `4edd154a3037` |
| Domains | `scholarzone-fwzj.vercel.app`, `…-git-master-…`; **no custom domain** |
| Automatic deployments | connected and **tracking master** |
| CI target | `https://scholarzone-fwzj.vercel.app/api` |

Same repository ID on both — **not** a fork mismatch.

## 12. Canonical User Host — **PROVEN**

**`canonical_user_host = https://gopal735.github.io/ScholarZone/`**

| # | Evidence | Conclusion |
|---|---|---|
| 1 | `robots.txt` on both Vercel hosts: `Sitemap: https://gopal735.github.io/ScholarZone/sitemap.xml` | declares it canonical |
| 2 | `sitemap.xml` — **every** `<loc>` is `https://gopal735.github.io/ScholarZone/...` | SEO identity |
| 3 | `https://gopal735.github.io/ScholarZone/` → HTTP 200, `<title>ScholarZone · Where Ambition Meets Opportunity</title>`, loads `/ScholarZone/assets/index-Bhvmyxum.js` | **live application** |
| 4 | `origin/gh-pages` contains the built bundle (`assets/index-*.js`, `index.html`) | production frontend is GitHub Pages |
| 5 | Neither Vercel project has a custom domain | neither can be canonical |

Per the rule that a CI target alone is insufficient: the CI API host (`scholarzone-fwzj`) is the
**API**, not the canonical site. The Vercel projects are API/app hosts.

**Residual risk — UNKNOWN:** the canonical bundle uses **relative** `/api` paths, which on
`github.io` resolve to `github.io/ScholarZone/api`. Whether GitHub Pages rewrites those to the Vercel
API was **not** established. The canonical host may serve a static snapshot rather than a live API.
This should be checked before treating GitHub Pages as a working production surface.

## 13. Stale Host Resolution — **VALIDATED** (classification), **BLOCKED** (remediation)

| Host | Classification | Basis |
|---|---|---|
| `gopal735.github.io/ScholarZone/` | **A — canonical production** | robots + sitemap + live app + gh-pages branch |
| `scholarzone-fwzj.vercel.app` | **B — non-canonical but public (CI API target)** | CI target; tracks master |
| `scholarzone.vercel.app` | **C — stale duplicate** | pinned at `3ee434c`, missed 4 master commits incl. `27047de` |

**Divergence is real and user-visible:** `27047de` is live on `scholarzone-fwzj` and absent from
`scholarzone`.

**Remediation prepared, NOT executed** (Phase 12 requires explicit owner approval):
retire `scholarzone.vercel.app` as a public alias, or converge it to the canonical build. **No project
or alias was deleted.** No routing change was made.

## 14. Release Identity Gate — **PARTIALLY VALIDATED**

Created: `backend/scripts/verify_release_identity.py`, implementing
`verify_release_identity(expected_sha, exact_url)`.

Working, demonstrated:
- rejects a short SHA (`255ca97556c0` → *"must be a full 40-character commit SHA"*) — **PROVEN**
- resolves the exact deployment by URL — **PROVEN**
- **refuses aliases** — **PROVEN** (documented in code)
- compares `gitSource.sha` against the expected full SHA — **PROVEN** (passed for `255ca975…`)
- enforces full 40-char on the health value — implemented

Two real bugs found and fixed while self-testing: `vercel` is a `.ps1` shim invisible to
`subprocess` (now resolves `vercel.cmd`), and the API path 404s on a `https://` prefix (now strips
the scheme).

**Not validated end-to-end:** the health-read step. `vercel curl` rejects `--yes` in CLI 59.11.7, so
the gate cannot complete non-interactively. **BLOCKED** at that step.

## 15. Mentor E2E — **BLOCKED** (correctly)

Not run. Phase 13 requires the identity gate to pass first, and it does not. Running browser E2E now
would produce evidence of unknown provenance — precisely what this task exists to prevent.

## 16. Test Isolation — **PROVEN**

| Measure | Status |
|---|---|
| Subprocess tests run against an isolated copy of the package | **PROVEN** |
| Source package never mutated in place | **PROVEN** |
| Test asserts the shipped artefact is never written by a test run | **PROVEN** |
| Test artefact ≠ shipped artefact SHA | **PROVEN** |
| Embedding twice is byte-identical (idempotent) | **PROVEN** |
| Artefact deterministic — no timestamp, hostname or run id | **PROVEN** |

The earlier contamination bug (a test SHA written into the real `app/build_revision.txt`) is fixed and
now guarded by regression tests. `40 passed` in `test_build_provenance.py`.

## 17. Rate Limit — UNKNOWN

Not probed beyond observing that no new preview appeared for the `d050d306` push within ~4 minutes.
No bypass attempted: no alternate account, project, undocumented API, or promotion trick. Prior
reported reset `2026-10-05T10:21:57Z` is **UNKNOWN** as to current status.

## 18. Exact Git Diff

Provenance work, branch `rc/revision-provenance` (parent `00bc39d`):

| Commit | Content |
|---|---|
| `255ca975` | `build_provenance.py`, `embed_build_revision.py`, `test_build_provenance.py`, `main.py`, `vercel.json`, `deploy.yml`, 2 test files |
| `d050d306` | `vercel.json` `installCommand`; 4 new build-wiring tests |

| Test suite | Result |
|---|---|
| `test_build_provenance.py` | **40 passed** |
| Full backend (at `255ca975`) | **5013 passed**, 2 pre-existing failures |
| Frontend vitest / build / lint | **163 passed** / success / 0 errors |

Pre-existing failures, verified on the untouched base:
`test_efficiency_safety…test_the_retry_shares_the_concurrency_group`,
`TestDiscoveryQualityGate…test_it_measures_against_the_real_catalogue`.

## 19. Remaining Unknowns

1. **BLOCKED** — no trustworthy read of a protected preview; runtime provenance unproven on a real deployment.
2. **UNKNOWN** — does GitHub Pages rewrite `/api` to the Vercel API, or is the canonical site static?
3. **UNKNOWN** — `a4d5833` conflict status against master (analysis here was for the *other* candidate).
4. **UNKNOWN** — which Vercel project is the intended long-term API host.
5. **UNKNOWN** — rate-limit status.
6. Not done: Phase 12 remediation (needs owner approval), Phase 14–15 browser/Mentor E2E.

## 20. Final Decision — `BLOCKED`

**Proven this session (real progress, not documentation):**

- `buildCommand` **does** execute for this FastAPI service, and receives the exact deployment SHA —
  from build logs, not schema inference.
- `gitSource.sha` **==** the SHA embedded into the artifact.
- Canonical user host **==** `https://gopal735.github.io/ScholarZone/`, from four independent artifacts.
- `scholarzone.vercel.app` is a **stale duplicate** serving code four master commits behind.
- `vercel curl` **silently answers from the linked project's production**, which fully explains the
  "runtime reports the wrong SHA" finding I reported in earlier turns. **That finding was wrong and is
  withdrawn.** The original `build_revision()` may never have misreported at runtime — though
  truncating to 12 characters and trusting a mutable runtime variable remain genuine design defects,
  both now fixed and gate-enforced.

**Not proven, and required before release:**

The runtime half of the chain. The artifact is proven *generated*; it is not proven *shipped and read*
by a real deployment, because no trustworthy way to read a protected preview exists with the current
CLI and settings. Manufacturing that evidence — accepting an alias, accepting a production response
for a preview request, or accepting a 12-character prefix — is exactly what this task forbids.

**To unblock, in order:**

1. Provide a supported authenticated read for the exact preview deployment (a CI bypass token, or
   owner-side confirmation that a specific identity may reach previews). Do **not** disable protection
   globally.
2. Re-run `verify_release_identity.py` against the deployment-specific URL; require PASS.
3. Re-derive the conflict analysis for `a4d5833` against `573a983`.
4. Owner decides the canonical API host and approves the `scholarzone` retirement.
5. Only then: merge → master → production → re-run the gate → Mentor E2E.

**Merge policy:** do not merge because tests are green. The code is ready; the *infrastructure
evidence* is not.