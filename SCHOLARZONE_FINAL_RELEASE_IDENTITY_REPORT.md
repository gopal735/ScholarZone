# SCHOLARZONE — FINAL RELEASE IDENTITY REPORT

| | |
| --- | --- |
| Final classification | **PRODUCTION_IDENTITY_VERIFIED** (canonical) · **RELEASE_IDENTITY_UNPROVEN** (secondary) |
| Merge commit / current master | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| Production writes | **NONE** |
| Deployment Protection | **PRESERVED** |
| Merged by | the repository owner (not by this task) |

Labels: **PROVEN**, **VALIDATED LOCALLY**, **PRODUCTION-PROVEN**, **UNKNOWN**, **BLOCKED**.

---

## 1. LIVE PR STATE

**PROVEN** — read live from GitHub, not from any prior report.

| Field | Value |
| --- | --- |
| number | 5 |
| state | **MERGED** |
| mergedAt | `2026-04-04T18:22:37Z` |
| baseRefName / baseRefOid | `master` @ `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| headRefName / headRefOid | `release/build-provenance-only` @ `95f91ea05654742c6ed1e0888137182f92bf5884` |
| changedFiles / additions / deletions | **12 / 2131 / 73** |
| mergeCommit.oid | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |

**PROVEN** — head `95f91ea` is an ancestor of `origin/master`, and `origin/master`
**is** the merge commit. Previously reported heads (`01f128c`, `2a02251`,
`fa95f5f`) were stale and were not used.

## 2. CURRENT HEAD / CURRENT BASE

| | |
| --- | --- |
| current `origin/master` | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` |
| PR head (contained) | `95f91ea05654742c6ed1e0888137182f92bf5884` |

## 3. LIVE DIFFSTAT — one authoritative value

**PROVEN**, recomputed from git and matching GitHub exactly:

```
12 files changed, 2131 insertions(+), 73 deletions(-)
```

### Reconciliation with every previously reported diffstat

| Reported | Value | Cause of the difference |
| --- | --- | --- |
| first report | 10 files, +1265 / −61 | accurate for commit `f9b4778` |
| after the report commit | 11 files, +1473 / −61 | +208 = `BUILD_PROVENANCE_PR_FINAL.md`, the report itself |
| after reconciliation fixes | 12 files, +1682 / −61 | +9 `.gitignore`, +17 `build_provenance.py`, +31 gate, +53 provenance tests, +99 gate tests |
| **live now** | **12 files, +2131 / −73** | **+449 / −12** from three later commits: `2a02251` (authenticated observation), `fa95f5f` (merge resolution), `95f91ea` (contamination fix) |

**PROVEN — code changed after the prior report, not documentation only.** The
increase is in `backend/scripts/release_identity_gate.py`, its tests,
`test_build_provenance.py` and `test_final_hardening.py`.

## 4. COMMIT LIST — all in approved scope

| Commit | Subject | Classification |
| --- | --- | --- |
| `f9b4778` / `c4baba8` | build: prove a deployment's identity from an artefact | required provenance (duplicate pair from the branch rewrite) |
| `335eee8` / `8420fc5` | docs: add the build provenance PR report | documentation (duplicate pair) |
| `01f128c` | fix: tighten three provenance contracts | test hardening |
| `ffc73f6` | fix: close the three release-integrity blockers | test hardening |
| `2a02251` | build: observe a protected deployment authentically | required provenance (release gate) |
| `fa95f5f` | merge: reconcile concurrent provenance work | merge resolution |
| `95f91ea` | test: stop provenance tests creating `backend/scholarzone.db` | test hardening |

**PROVEN — no unrelated commit.** The duplicate pairs are the same content under
two SHAs, left by the branch rewrite; neither adds scope.

## 5. FILE MANIFEST — exactly the approved 12

**PROVEN** — `git diff --name-status ddcd9c3..fc4096f` returns precisely the
approved list and nothing else:

`.github/workflows/deploy.yml` · `.gitignore` · `BUILD_PROVENANCE_PR_FINAL.md` ·
`backend/app/build_provenance.py` · `backend/app/main.py` ·
`backend/scripts/embed_build_revision.py` · `backend/scripts/release_identity_gate.py` ·
`backend/tests/test_build_provenance.py` · `backend/tests/test_final_hardening.py` ·
`backend/tests/test_release_identity_gate.py` · `backend/tests/test_vercel_migration.py` ·
`vercel.json`

**PROVEN — no Mentor, frontend, visibility, Count, Match, image, ingestion,
scheduler, auth, model, migration or requirements change.** Release scope is clean.

## 6. PRE-MERGE TEST RESULTS

| Gate | Result |
| --- | --- |
| provenance + release gate + vercel migration + final hardening | **184 passed**, 1 warning |
| full backend suite on merged master | **5080 passed / 8 failed / 10 skipped / 13 warnings / 1 error** |
| baseline (untouched `ddcd9c3`) | 4988 passed / 8 failed / 11 skipped / 13 warnings / 1 error |
| delta | **+92 passed**, failures/warnings/error unchanged |
| `git diff --check` | **clean** |

**Failure classification — all pre-existing, none introduced:**

| Failure | Class |
| --- | --- |
| 8 × `test_neon_migration.py` | **ENVIRONMENTAL** — requires the untracked `migration_export.sql` fixture |
| 1 error `scripts/artifact_smoke_test.py::test_endpoint` | **PRE-EXISTING** — unchanged across every baseline |
| **NEW failures** | **none** |

**PROVEN — no test weakened.** No `xfail`, no `skip` added, no assertion relaxed.

**PROVEN — no contamination.** With `backend/scholarzone.db` deleted, the targeted
suites ran and did **not** recreate it; after the **full** suite it was still
absent and `git status` was clean. Commit `95f91ea` fixed this.

## 7. PROVENANCE ARCHITECTURE — singular

**PROVEN** on the merged tree: one build generator
(`backend/scripts/embed_build_revision.py`), one module
(`backend/app/build_provenance.py`), one release gate
(`backend/scripts/release_identity_gate.py`), one `build_revision()`, and
**zero** duplicates (`write_build_provenance`, `generate_build_revision`,
`app/provenance.py` all absent).

## 8. RAW SHA CONTRACT — verified, with one precise caveat

**PROVEN** — validation is `^[0-9a-f]{40}$` and there is **no `.lower()`** at either
boundary, so uppercase is refused rather than normalised. A refused platform build
writes no artefact and the script exits non-zero.

**PROVEN — artefact**: generated only by the build, **gitignored**
(`.gitignore:88`), **untracked**, and a refused input fails the build.

**VALIDATED LOCALLY — one deviation, reported rather than glossed.** Both boundaries
call `.strip()` *before* validating:

```python
raw = (os.getenv(PLATFORM_COMMIT) or "").strip()      # build_provenance.py:80
raw = ARTIFACT.read_text(encoding="utf-8").strip()     # build_provenance.py:131
```

so a **whitespace-padded** artefact or env var is accepted where the stated contract
says it should be refused. **This is not an identity risk**: after stripping, the
value must still match `^[0-9a-f]{40}$` exactly, so stripping cannot turn a
non-identity into a claim. It is stricter-contract drift, not a vulnerability. The
artefact is written as `f"{value}\n"`, so stripping one terminal newline is
intended. Reported for the record; not changed, since this is merged, owner-approved
state and the deviation cannot affect identity.

## 9. RUNTIME — artefact-only, fail-closed

**PROVEN** on the merged tree: `main.py:76` returns `read_embedded_revision()`.
The only remaining mentions of `VERCEL_GIT_COMMIT_SHA` are inside a docstring
describing what was removed. No environment variable, header, query parameter,
alias, hostname, branch or tag can supply the revision. Missing or malformed
artefact in production → **503**, fail closed.

## 10. DEPLOYMENT IDENTITY — PRODUCTION-PROVEN

**PROVEN** — read live, not from a report.

| Field | Expected | Observed | Result |
| --- | --- | --- | --- |
| A — merged/current master | 40-hex | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PRODUCTION-PROVEN** |
| B — Vercel `gitSource.sha` | == A | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PRODUCTION-PROVEN** |
| C — build artefact SHA | == A | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` | **PRODUCTION-PROVEN** |
| D — runtime `/api/health` | == A, 40 chars | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` (len 40) | **PRODUCTION-PROVEN** |

| Field | Value |
| --- | --- |
| Vercel project | `scholarzone-fwzj` |
| deployment ID | `dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj` |
| target | `production` |
| deployment URL | `https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app` |
| `gitSource.ref` | `master` |

**FOUR-WAY EQUALITY: PASS** — `A == B == C == D`, all exactly 40 lowercase hex.

### Artifact proof — why C is not inferred

**PROVEN, two independent ways.**

1. The runtime's only source is the artefact (§9). The value reported at D is
   therefore the artefact's content by construction, and the gate compares it
   against the supplied artefact SHA.
2. **Corroborating, and decisive against the old code path.** The pre-merge code
   read an environment variable and truncated it to **12** characters. A 40-character
   value **cannot** have originated from that path. Observing 40 characters proves
   the artefact path is live, not merely that a different env var was set.

**PROVEN — release gate, on the exact deployment URL, authenticated:**

```
PASS deployment=dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj ref=master
     sha=fc4096f7a2aac8530f4e14495a7f21b9a97419be
```

Run with `--sha`, `--artifact`, `--target production`, `--project scholarzone-fwzj`.
**PROVEN — repeated**, returning PASS on the **same** deployment identity with no
switch between observations.

**PROVEN — Deployment Protection PRESERVED.** An anonymous read of the *same*
deployment URL returns HTTP 200 with `content-type: text/html` and
`isAppJson=False` — the interstitial, not the application. Only the authenticated
read returns the real payload. Protection was never disabled, no exception created,
no bypass added, no CLI production deployment used.

**PROVEN — bindings.** Exact deployment ID, exact deployment URL, exact project,
exact target `production`, `gitSource.ref=master` — all verified, and the alias was
never substituted for the deployment.

## 11. SECONDARY HOST — RELEASE_IDENTITY_UNPROVEN

Inspected **separately** and not combined with the canonical proof.

| Field | Observed | Result |
| --- | --- | --- |
| deployment ID | `dpl_BgX285zMhirUjni3nsCADRZXhn79` | read-only |
| project | `scholarzone` | — |
| `gitSource.ref` / `.sha` | **empty** | **FAIL** |
| runtime `/health` | `unknown` (len 7) | **FAIL** |

**Classification: RELEASE_IDENTITY_UNPROVEN.** Required evidence is unavailable —
there is no `gitSource`, so the deployment cannot be attributed to any commit.
**Behavioural equality is not provenance equality**, and this host is not counted
toward the verified result.

## 12. QUOTA / PROVIDER STATUS

**PROVEN** — cleared. All four Vercel checks on PR #5 report "Deployment has
completed". The `api-deployments-free-per-day` limit that blocked earlier stages is
no longer active, and the deployment examined above originated from the **Git merge**
(`gitSource.ref=master`, sha = merge commit), not from a CLI deployment.

## 13. SECURITY REGRESSION

**PROVEN** — no public visibility predicate was modified by this release, and the
security fixes are ancestors of master:

| Commit | In master |
| --- | --- |
| `3bf92b6` (ingestion image preservation) | **YES** |
| `87ad84c` (`do_purge` fix) | **YES** |

**PROVEN** — PR #2's visibility fix remains in master and its 21 tests pass on the
merged tree. No production data was read or written for this verification beyond
the public `/api/health` endpoint and public `GET` routes.

## 14. PRODUCTION WRITES

**NONE.** No maintenance, purge, ingestion repair, scholarship, image, record or
visibility change. The only production-side actions were the owner's Git merge, the
resulting normal Git-integrated deployment, and read-only identity verification.

---

## 15. Final output

```
FINAL CLASSIFICATION:
    PRODUCTION_IDENTITY_VERIFIED

PR #5:
    MERGED

LIVE PR HEAD:
    95f91ea05654742c6ed1e0888137182f92bf5884

CURRENT MASTER:
    fc4096f7a2aac8530f4e14495a7f21b9a97419be

DIFFSTAT:
    12 files changed, 2131 insertions(+), 73 deletions(-)

PRE-MERGE TESTS:
    184 passed (targeted) / 5080 passed, 8 failed (all ENVIRONMENTAL, pre-existing),
    10 skipped, 1 error (pre-existing); zero new failures; no contamination

MERGE SHA:
    fc4096f7a2aac8530f4e14495a7f21b9a97419be

VERCEL PROJECT:
    scholarzone-fwzj

DEPLOYMENT ID:
    dpl_EXVAS5WG2Ri4799MtL6LC7XYRPYj

DEPLOYMENT URL:
    https://scholarzone-fwzj-qlgumqb19-gopal735s-projects.vercel.app

GITSOURCE SHA:
    fc4096f7a2aac8530f4e14495a7f21b9a97419be

ARTIFACT SHA:
    fc4096f7a2aac8530f4e14495a7f21b9a97419be

RUNTIME SHA:
    fc4096f7a2aac8530f4e14495a7f21b9a97419be

FOUR-WAY EQUALITY:
    PASS

DEPLOYMENT PROTECTION:
    PRESERVED

AUTHENTICATED RUNTIME:
    PROVEN

SECONDARY HOST:
    UNPROVEN

PRODUCTION WRITES:
    NONE

EXACT OWNER ACTION:
    Decide the disposition of scholarzone.vercel.app, which is publicly reachable
    with no gitSource and reports revision "unknown"; it cannot be attributed to any
    commit and is not covered by this verification.

REMAINING BLOCKERS:
    None for the canonical backend.
    - scholarzone.vercel.app has no gitSource and reports "unknown" - publicly
      reachable, no verifiable build identity, RELEASE_IDENTITY_UNPROVEN.
    - Contract drift, not a risk: build_provenance.py strips surrounding whitespace
      before validating at both boundaries (lines 80 and 131), so a padded value is
      accepted where the stated contract says it should be refused.
    - 8 pre-existing ENVIRONMENTAL failures in test_neon_migration.py (missing
      untracked migration_export.sql fixture).
```