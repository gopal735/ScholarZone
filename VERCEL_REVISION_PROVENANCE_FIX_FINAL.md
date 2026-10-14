# VERCEL_REVISION_PROVENANCE_FIX_FINAL.md

# FINAL CLASSIFICATION: `NEEDS_REWORK`

The fix is **implemented and fully verified locally**. The **acceptance test could not be
completed**, and the root cause I diagnosed in the previous turn is **retracted** — the evidence now
shows it was a measurement artefact.

No production deployment. No production database write. No Vercel production settings change. No
master rewrite. `master` is untouched at `573a983`; `00bc39d` is untouched.

---

## 1. Root Cause

### The reported root cause was wrong, and I am retracting it

The previous turn classified this as **E — "build-time code is incorrectly reporting the SHA"**, on
the basis that Vercel's metadata said `00bc39d` while `/api/health` said `4edd154a3037`.

**That classification does not survive contact with the new code.** The rewritten `build_revision()`
can emit exactly three things:

- a **40-character** full commit SHA,
- the literal `dev`,
- or it **raises**.

It has no code path that can emit a 12-character value. `4edd154a3037` is 12 characters. Therefore the
response bearing `4edd154a3037` **was not produced by the code in these previews** — it came from a
different, pre-fix deployment. The original premise ("the runtime env var disagreed with the build
metadata") is unsupported.

What I can state as fact:

1. Vercel's deployment metadata is authoritative and correct for every preview examined
   (`source: git`, `ref`, `sha` all matching the pushed commit).
2. Every artefact digest and size is distinct, so no deployment reuses another's build.
3. **Previews are behind Vercel Deployment Protection.** A direct HTTPS request for
   `/api/health` on a preview returns a Vercel login page, and the page's own
   `data-dpl-id` (`dpl_9u7pHwKkg11CDQPLjLV9NfZVjQtD`) is **not** the deployment I asked about. The
   CLI bypass path returned a different deployment's response. Neither is a trustworthy read of the
   deployment under test.

**Root cause is therefore: unverified.** The original runtime implementation may well have been
correct, and the "mismatch" an artefact of reading a protected preview. The change implemented here
is still justified — the original design trusted a mutable runtime value for a build-identity claim,
and had no test pinning it — but the specific defect I claimed to have proven was not proven.

### Independent risk found while implementing

`build_revision()` also **truncated to 12 characters**, and `deploy.yml` compared only a 12-character
prefix. That is a real defect regardless of the above: two commits can share a prefix, and the gate
would accept either. It is now fixed on both sides.

## 2. Old Verification Failure

| Property | Before | After |
|---|---|---|
| Source of the revision | runtime `VERCEL_GIT_COMMIT_SHA`, then `VERCEL_GIT_COMMIT_REF`, then `SCHOLARZONE_BUILD_REVISION` | embedded artefact only |
| Overridable by an env var | **yes**, including `SCHOLARZONE_BUILD_REVISION` | **no** |
| Overridable by a request header | no | no |
| Length reported | 12 characters | **40 characters** |
| Missing identity in production | reported `"unknown"` | **raises; `/health` returns 503** |
| Corrupt identity | silently ignored | **raises** |
| Build-time validation | none | **build fails** |

The old `"unknown"` answer was not safer than a wrong SHA — both are unverifiable, and a gate that
tolerates either has no gate. That is now a hard failure.

## 3. New Build-Time Provenance Mechanism

**New: `backend/app/build_provenance.py`**

- `platform_commit_sha()` — reads `VERCEL_GIT_COMMIT_SHA`, accepts **only** `\A[0-9a-f]{40}\Z`
  (normalising case). Rejects branch names, URLs, `latest`, `unknown`, short and long SHAs.
- `embed_build_revision()` — **build time**. Writes the validated SHA to `app/build_revision.txt`.
  On the platform (`VERCEL=1`) with no usable SHA it **raises**. Off-platform it writes `dev`.
- `read_embedded_revision()` — **runtime**. The artefact is the only source. Missing or malformed
  raises `ProvenanceError`.
- The artefact lives **inside the package**, so it ships with the code it identifies.

**New: `backend/scripts/embed_build_revision.py`** — the build hook. Exit status is the contract:
non-zero fails the build.

**`vercel.json`** — the backend service gains a build step:

```json
"buildCommand": "python scripts/embed_build_revision.py"
```

`buildCommand` is confirmed present in the official `services` schema
(`https://openapi.vercel.sh/vercel.json`), not assumed.

**Why an artefact rather than an env var:** the platform identifier is read exactly once, at build
time, and compiled into the artefact. At runtime nothing is consulted that a person, a deployment
setting, or a caller can change.

## 4. Runtime Behavior

| Situation | Result |
|---|---|
| Artefact holds a valid 40-char SHA | reported verbatim |
| Artefact holds `dev` | `"dev"` |
| Artefact **missing**, environment ≠ production | `"dev"` (developer machine; never built) |
| Artefact **missing**, environment = production | **raises** → `/health` 503 |
| Artefact **corrupt/malformed**, any environment | **raises** → `/health` 503 |

The missing/corrupt distinction is deliberate. "Nobody built this" is normal locally. "A build ran
and produced something unusable" is always wrong, so it always fails — letting a corrupt artefact
degrade to `dev` would let a broken deployment answer `ok` on the one endpoint whose job is to notice.

Local development is unaffected, and the startup log is guarded so a corrupt artefact is *reported*
rather than preventing boot — an unbootable service turns a diagnosable packaging fault into an
outage. `/health` remains the enforcement point.

## 5. Health Endpoint

`/health` now resolves the revision **before** touching the database and **independently** of it, so
a provenance failure reports `Build identity unavailable` rather than being mislabelled
`Database unreachable` — a mislabelled failure gets misdiagnosed as an outage.

A corrupt artefact now returns **503** on `/health` in any environment, which is asserted by test.

No request header is consulted; `test_a_caller_cannot_influence_health` proves that sending
`X-Build-Revision`, `X-SCHOLARZONE-BUILD-REVISION` and `X-Forwarded-Host` changes nothing.

## 6. Deploy Gate

`deploy.yml` was changed **only** in the revision comparison. Every other condition is intact —
asserted mechanically:

| Assertion | Value |
|---|---|
| `EXPECTED_SHORT` removed | **true** |
| compares `[ "$CURRENT" = "$EXPECTED_REVISION" ]` | **true** |
| requires exactly `^[0-9a-f]{40}$` | **true** |
| still requires HTTP 200 | **true** |
| still requires `status: ok` | **true** |
| still refuses a non-SHA | **true** |
| no truncation (`:0:12`) anywhere | **true** |

**This is strictly stronger.** It was `github.sha`'s first 12 characters against the reported 12
characters; it is now the complete 40-character SHA on both sides. Nothing was replaced by an HTTP
200 check, a label, a branch name, a URL, or a supplied value.

## 7. Regression Tests

**New `backend/tests/test_build_provenance.py` — 36 tests, all passing.** Covers:

- the artefact is the only runtime source;
- `SCHOLARZONE_BUILD_REVISION` **cannot** override it (the previously supported escape hatch);
- a stale `VERCEL_GIT_COMMIT_SHA` **cannot** rewrite history — the exact failure under investigation;
- no request header can influence `/health`;
- `/health` returns the exact **40-character** SHA;
- a corrupt artefact makes `/health` non-200;
- production refuses to report an unverified revision;
- development still runs with no artefact;
- build fails on a missing, empty, short, long, non-hex, branch-name, URL, `latest`, or `unknown` SHA;
- an uppercase SHA is normalised, not rejected;
- a **failed** build leaves **no** artefact behind;
- the build script's exit status, both paths, via subprocess;
- the shipped artefact is never written by a test run.

**Anti-vacuity:** the existing suites asserted the *broken* behaviour and were updated, because they
are tests of the mechanism being changed — not unrelated tests:

| Test | Was | Now |
|---|---|---|
| `test_revision_is_the_env_value_truncated` | env var wins, truncated to 12 | artefact wins, 40 chars |
| `test_platform_injected_identity_is_preferred` | runtime SHA preferred | **replaced** — artefact is the only source |
| `test_env_fallback_is_used_when_no_platform_identity` | env fallback | **replaced** — no env fallback exists |
| `test_production_without_a_revision_reports_unknown` | `"unknown"` | **raises** |
| `test_a_healthy_but_stale_container_is_not_success` | asserted `EXPECTED_SHORT` | asserts full-SHA compare |
| `test_deploy_verification_fails_a_stale_build` | asserted `{7,40}` | asserts `{40}` |

I also found and fixed a **test-isolation bug of my own**: the subprocess tests ran the real script
with `PYTHONPATH` pointed at the repository, so they wrote a test SHA into the real
`app/build_revision.txt`. They now run against an isolated copy, and a test asserts the shipped
artefact is never touched.

## 8. Fresh Preview Verification — **NOT COMPLETED**

This is the critical acceptance test and **it could not be run**.

Branch `rc/revision-provenance` was pushed (commit `255ca975…`, parent `00bc39d`), and Vercel built
preview `scholarzone-6c0x9o1g8…` with `gitSource.ref = rc/revision-provenance`,
`gitSource.sha = 255ca975…`.

Reading it back **failed**:

| Read path | Result |
|---|---|
| `vercel curl /api/health` on the preview | returned `4edd154a3037` — **provably not this code** (12 chars is impossible under the new implementation) |
| Plain HTTPS on the preview | Vercel login page; its `data-dpl-id` is `dpl_9u7pHk…`, **a different deployment** |
| `vercel logs` for the build | **no `buildCommand` output** — the embed step did not appear in logs |

So two things are unproven:

1. **That the preview serves `255ca975…` through `/api/health`.** Every available read path either
   was blocked by Deployment Protection or demonstrably reached a different deployment.
2. **That Vercel actually executed `buildCommand` for a `framework: fastapi` service.** No build-log
   evidence was found. This is the largest open risk: the schema permits `buildCommand`, but
   permitting it is not the same as honouring it for the Python builder.

**Note on the acceptance criterion as literally stated.** It asks a preview built from the Mentor
branch to report `00bc39d`. That is unachievable by construction: the artefact is written by a script
that `00bc39d` does not contain, and `00bc39d` must not be modified. The equivalent, achievable proof
is that a build of the Mentor branch **plus** this fix reports **its own** full SHA — equal to its
`gitSource.sha`, and no longer a stale `4edd154`. That proof is still outstanding.

## 9. Two-Project Production State

Recorded; **no settings changed**.

| | `scholarzone` | `scholarzone-fwzj` |
|---|---|---|
| Production alias | `https://scholarzone.vercel.app` | `https://scholarzone-fwzj.vercel.app` |
| Project ID | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| Current production SHA | `3ee434c01f53` | `4edd154a3037` |
| Git repository | `gopal735/ScholarZone` (`1354421070`) | `gopal735/ScholarZone` (`1354421070`) |
| Root directory | `''` (repo root) | `''` (repo root) |
| Production branch | `master` (both git-connected; `…-git-master-…` aliases) | same |
| Actively tracking master | **no** — pinned at `3ee434c` | **yes** |
| Contains `27047de` | no | **yes** |
| Custom domain | none | none |

Both serve the same database (`total: 358`, identical records). They remain **two independent
production targets** serving different code.

## 10. Remaining Configuration Ambiguity

**The canonical user-facing URL is `UNKNOWN`.**

It cannot be proven from available evidence: neither project owns a custom domain, both aliases are
live, and no configuration distinguishes them. Signals conflict — `.vercel/repo.json` in the checkout
binds the directory to `scholarzone-fwzj` and only that project tracks master, while the previously
approved baseline revision matches `scholarzone`. **This must be answered by the owner before any
deployment.**

Also open, and independent of this change:

- `scholarzone` vs `scholarzone-fwzj` still diverge on `27047de`.
- `00bc39d` remains a **sibling** of `master`; integrating it is conflict-free but undone.
- `test_efficiency_safety…test_the_retry_shares_the_concurrency_group` — pre-existing failure.
- `TestDiscoveryQualityGate…test_it_measures_against_the_real_catalogue` — pre-existing failure,
  **verified to fail on the untouched base** (`1 failed` on `00bc39d` with no changes).

## 11. Exact Files Changed

Commit **`255ca97556c0d3ad74a93d5644ea17e7d79e2d7f`** on `rc/revision-provenance`, parent
**`00bc39dab3dbb4977b4b36419f301022c4199323`** (unmodified).

| Status | Path | Purpose |
|---|---|---|
| **A** | `backend/app/build_provenance.py` | build-time embed, runtime read, SHA validation |
| **A** | `backend/scripts/embed_build_revision.py` | build hook; exit status is the contract |
| **A** | `backend/tests/test_build_provenance.py` | 36 regression tests |
| **M** | `backend/app/main.py` | `build_revision()` reads the artefact only; health restructured |
| **M** | `vercel.json` | `services.backend.buildCommand` |
| **M** | `.github/workflows/deploy.yml` | full-SHA comparison (stronger) |
| **M** | `backend/tests/test_final_hardening.py` | updated to the new contract |
| **M** | `backend/tests/test_vercel_migration.py` | updated to the new contract |

**No image, `do_logos`, ingestion, Match, Count, Admin, Applications, scheduler, audit or Wave 1–3
file was touched.**

### Test results

| Suite | Result |
|---|---|
| `test_build_provenance.py` | **36 passed** |
| `test_vercel_migration.py` + `test_final_hardening.py` + provenance | **129 passed, 1 failed** (pre-existing) |
| **Full backend** | **5013 passed, 11 skipped, 2 pre-existing failures** |
| Frontend `vitest` | **163 passed** (9 files) |
| Frontend `vite build` | **succeeded** |
| Frontend `eslint` | **0 errors**, 1 pre-existing warning |

No test was weakened or deleted to reach green.

## 12. Final Classification

# `NEEDS_REWORK`

**Done and trustworthy:** the implementation. Build-time embedding, strict 40-character validation,
build failure on a missing or malformed SHA, runtime that reads only the artefact with no env-var or
header override, hard failure in production, no truncation, and a **strengthened** deploy gate. 36 new
tests, 5013 backend tests passing.

**Not done:** the acceptance test. I cannot demonstrate that a preview reports the SHA it was built
from, for two independent reasons:

1. Previews are behind Deployment Protection and every read path either was blocked or reached a
   different deployment.
2. There is **no build-log evidence that Vercel executed `buildCommand` for this Python service.** If
   it did not run, no artefact exists — and the design then fails *safely* (production `/health`
   returns 503, so the deploy gate fails loudly) rather than misreporting. That is the correct
   direction to fail, but it must be confirmed rather than assumed.

**Required before this can be `READY_FOR_PRODUCTION_VERIFICATION`:**

1. Prove the backend `buildCommand` runs — via build logs, or by owner-side confirmation of Vercel's
   behaviour for `framework: fastapi` services.
2. Provide a way to read a protected preview: temporarily allow the deploy identity, or add a bypass
   token for CI, or verify through a channel that is not Deployment-Protection-gated.
3. Owner resolves the canonical production URL (§10). It is `UNKNOWN` and no deployment should be
   attempted until it is not.
4. Re-run the acceptance test: a build of the Mentor branch must report its **own** full SHA —
   equal to `gitSource.sha`, and no longer a stale `4edd154`.

### Claims

**Claimed:** the code change is complete, locally verified, and strictly strengthens the deploy
gate; the two production targets are divergent; the canonical URL is unknown; the previous root-cause
classification was wrong and is retracted.

**Not claimed:** that any preview or production deployment reports a correct revision; that Vercel
executed the build command; that the runtime env var was ever wrong; that the October 3 root cause is
solved (Phase 6 remains **CASE E / NOT OBSERVED**).