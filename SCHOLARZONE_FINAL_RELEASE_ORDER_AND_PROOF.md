# SCHOLARZONE_FINAL_RELEASE_ORDER_AND_PROOF.md

**Date:** 2026-10-04 · **Repository:** `gopal735/ScholarZone` · canonical branch `master`
**No merge. No deployment. No Vercel mutation. No production DB write. Security code untouched.**

Labels: **PROVEN** · **OBSERVED** · **DISPROVEN** · **UNKNOWN** · **BLOCKED_BY_PROVIDER** ·
**OWNER_ACTION_REQUIRED**

---

## 1. Security finding status — **FROZEN, NO NEW FINDING**
No brand-new evidence of a defect. Security code not modified.

## 2. Why the earlier exposure finding was withdrawn — **DISPROVEN by live re-probe**
The earlier claim was that `scholarzone.vercel.app` publicly exposed hidden IDs. Re-probed this pass:

| ID set | `scholarzone-fwzj` | `scholarzone` |
|---|---|---|
| 14, 26, 28, 33, 40, 45, 59 | **404** (all 7) | **404** (all 7) |
| public id 1 | 200 | 200 |
| nonexistent 999999 | 404 | 404 |

**PROVEN cause of the change:** both aliases were rebuilt from the **same commit `ddcd9c3`**
(`scholarzone` at 14:05:50Z, `-fwjz` at 13:44:43Z). The exposure closed via redeploy by another
actor, not by any action of mine. Identical `stats` (358/358/43), identical list IDs, identical 19-field
public shape, **zero internal-field leaks on either host**. Hidden ≡ nonexistent — no existence oracle.

## 3. Current master SHA
`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` — unchanged. **I authored 0 commits into master.**

## 4. PR #5 base / head
base `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` · head `335eee8e41b2e72140eb64e431a0a8bc885c376e`
2 commits: `f9b4778` (provenance) + `335eee8` (docs).

## 5. Exact changed-file manifest (from git, not the API)
| File | +/− | Classification |
|---|---|---|
| `backend/app/build_provenance.py` | +131 | **REQUIRED_PROVENANCE** |
| `backend/app/main.py` | +66/−32 | **REQUIRED_PROVENANCE** |
| `backend/scripts/embed_build_revision.py` | +41 | **REQUIRED_BUILD_WIRING** |
| `backend/scripts/release_identity_gate.py` | +307 | **REQUIRED_RELEASE_GATE** |
| `.github/workflows/deploy.yml` | +4/−5 | **REQUIRED_RELEASE_GATE** |
| `vercel.json` (root) | +2 | **REQUIRED_BUILD_WIRING** |
| `backend/tests/test_build_provenance.py` | +385 | **REQUIRED_TEST** |
| `backend/tests/test_release_identity_gate.py` | +208 | **REQUIRED_TEST** |
| `backend/tests/test_vercel_migration.py` | +79/−16 | **REQUIRED_TEST** |
| `backend/tests/test_final_hardening.py` | +42/−8 | **REQUIRED_TEST** |
| `BUILD_PROVENANCE_PR_FINAL.md` | +208 | **UNRELATED (documentation only)** |

**No DUPLICATE provenance implementation. No second provenance system.**

## 6. The 10-vs-11 file discrepancy — **EXPLAINED**
`1473 − 208 = 1265` and `11 − 1 = 10`, both exact. The extra file is
`BUILD_PROVENANCE_PR_FINAL.md` (**+208, 0 deletions**), added by the second commit `335eee8`
"docs: add the build provenance PR report". The earlier 10-file/+1265 measurement predates that commit.
**Nothing was deleted to make counts match** — deletions are −61 in both measurements.

## 7. No current-master revert — **PROVEN**
`merge-base(master, PR5) = ddcd9c3` = **current master exactly**; no rebase needed.
**Zero files deleted.** No Count, Match, admin-verification, dashboard, Application Workspace, supervisor,
image-trust or verification file is touched. `backend/app/database.py` is **byte-identical** to master.
The visibility predicate is untouched.

## 8. Provenance architecture — **PROVEN correct**
`FULL_COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")` — anchored, lowercase, exactly 40.
Rejects missing / short / long / uppercase / branch / tag / URL. `embed_build_revision()` raises
`ProvenanceError` on a platform build without a valid SHA; the hook **exits non-zero**, failing the build.
Artifact is `app/build_revision.txt`, shipped in the package. `read_embedded_revision()` is the only
runtime source. No truncation, no `VERCEL_GIT_COMMIT_SHA` / `_REF` / `SCHOLARZONE_BUILD_REVISION`,
no header/query/branch/alias trust.

## 9. Actual Vercel build wiring — **CORRECT LAYER, PATH UNPROVEN**
PR #5 attaches `buildCommand` + `installCommand` to **`services.backend` in the ROOT `vercel.json`** —
the authoritative config, since the Vercel `rootDirectory` is `.`. It does **not** rely on
`backend/vercel.json` (left untouched).

**UNPROVEN / BLOCKING:** the hook is `python scripts/embed_build_revision.py`. That path only resolves
if Vercel executes `buildCommand` with cwd = the **service root** (`backend/`). If it runs from the
**project root**, the path is wrong and the build hook will not execute. This cannot be settled
without a real build — and building is the thing that is gated.

**Two further observations:** the generator runs **twice** (build + install) — idempotent, but
redundant; and `on_platform()` gates fail-closed on `VERCEL=1`, so if that variable were absent the
build would silently write the development marker instead of failing.

## 10. Build execution evidence — **NONE**
No build was executed in this pass. The artifact is not yet in any deployment. **UNKNOWN** whether the
real hook fires.

## 11. Artifact evidence — **NONE IN PRODUCTION**
`git ls-tree` confirms no committed `build_revision.txt` (clean). Nothing deployed carries one.

## 12–14. gitSource.sha == artifact SHA == runtime SHA — **UNPROVEN**

| Path | Value |
|---|---|
| `gitSource.sha` (`-fwjz`) | `ddcd9c3…deb` (40) |
| `gitSource.sha` (`scholarzone`) | **`null`** — `source: cli`, ref `HEAD` |
| artifact SHA | **does not exist** (PR #5 unmerged) |
| runtime `/health` `-fwjz` | `ddcd9c3662f4` — **12 chars** |
| runtime `/health` `scholarzone` | **`unknown`** |

**PROVEN DEFECTIVE on two counts: runtime truncation to 12 characters, and one public production host
served by a CLI deployment with no git provenance at all.**

## 15. Deployment IDs
`scholarzone` → `dpl_BgX285zMhirUjni3nsCADRZXhn79` · `-fwjz` → `dpl_Fnk6fnJFbqYcFKriqwDhDr3Jbn7e`.
Both `target: production`, both built from `ddcd9c3`. **Neither was created by me.**

## 16. Host convergence — **DATA SECURE, IDENTITY NOT PROVEN**
Both hosts are secure and intentional in *behaviour*; neither is identity-proven. The non-canonical
host has **PROVEN zero** dependency — the shipped GitHub Pages bundle
(`index-Bhvmyxum.js`, 587 425 chars) hard-references **only** `scholarzone-fwzj.vercel.app`, with
**0** relative `/api`; corroborated by `SCHOLARZONE_API_URL` and all `.github` references.

## 17. Deterministic parity method — **IMPROVED**
The earlier offset-pagination proof was invalid (only 100 of 358 enumerated). This pass used
deterministic logic: identical `stats` totals, identical first-100 IDs by direct comparison, identical
19-field public shape, and explicit per-ID status for all 7 disputed IDs plus a public control and a
nonexistent control. No offset assumption is load-bearing.

## 18. Production security regression — **PASSING, with a recorded limitation**
Public → 200; hidden → 404; nonexistent → 404; hidden ≡ nonexistent; no internal fields. **Zero
production DB writes.**

## 19. Backend / frontend / E2E results
| Gate | Result |
|---|---|
| PR #5 provenance + identity gate + 2 updated files | **159 passed, 1 failed** |
| The 1 failure | `TestDiscoveryQualityGate` — **contamination**, see §20 |
| Frontend | not run — **PR #5 touches no frontend file** |
| Browser E2E | not re-run — nothing deployed, no Mentor change rebased |

## 20. Local contamination — **PROVEN REPRODUCIBLE, NOT FIXED BY PR #5**
Deterministic proof, in a **fresh** worktree:

1. discovery gate run **alone** in a clean state → **skipped**;
2. **that skipped test itself creates `backend/scholarzone.db`** (git-ignored);
3. run across **multiple test files** → the ambient ignored DB holds enough rows to push the gate past
   its "catalogue too small to be meaningful" threshold, so it **runs and fails**.

So a **release-relevant test changes its verdict based on ambient, git-ignored local state** and on
file-set ordering. PR #5 contains **no** `.gitignore` change, no isolation harness and no contamination
regression test.

**PR #5 does not close PHASE 6 / PHASE 8.**

## 21. Remaining blockers
1. **`.gitignore` gap in PR #5** — `backend/app/build_revision.txt` is **not** git-ignored. A generated
   identity could be committed stale, which the contract explicitly forbids. One additive line fixes it.
2. **Build-hook cwd unproven** — the whole chain depends on `buildCommand` running from `backend/`.
3. **Release identity gate unproven against a real deployment** — no artifact exists yet.
4. **Contamination gate absent** — §20, reproducible.
5. **`scholarzone.vercel.app`** — proven dependency-free, publicly serving an unattributable CLI
   deployment. Owner decision required.
6. **PR #1 / PR #3 / PR #4** — superseded; PR #4 and PR #3 sit on the old `573a983` base. Not rebased,
   not merged, per instruction.

## 22. Intentionally deferred
Mentor evidence, Supervisor, frontend redesign, image enrichment, Wave 1–3 — all correctly deferred.
**Wave 1–3 remains BLOCKED. No Neon write occurred.**

## 23. Production-write claims
**PROVEN: zero production database writes.** Read-only HTTP probing, git, and Vercel metadata reads only.

---

# FINAL CLASSIFICATION: `OWNER_ACTION_REQUIRED`

**Not `READY_FOR_OWNER_MERGE`.** One explicitly-mandated condition is unmet: the generated artifact is
**not git-ignored**, so PR #5 does not yet guarantee that a committed stale identity is impossible. That
is a one-line additive fix, and I did not apply it because the instruction was to audit PR #5 without
modifying it.

**Not `PROVENANCE_SCOPE_BLOCKED`** — the scope is clean: 11 files, all provenance/gate/test/doc, zero
duplicates, zero reverts, exact current-master base.

**Not `BUILD_WIRING_BLOCKED`** — the wiring is attached to the **correct authoritative layer** (root
`vercel.json`, `services.backend`). The residual risk is the unproven `buildCommand` cwd, which is
recorded rather than asserted.

**Not `RELEASE_IDENTITY_BLOCKED`** — that condition becomes true only after merge + build; it is not
the reason to hold the PR.

**Not `PROVIDER_DEPLOYMENT_BLOCKED`** — capacity was observed available; no quota error encountered.

**Not `PRODUCTION_RELEASE_VERIFIED`** — forbidden while identity is unproven and the runtime revision
is 12 characters.

## Exact owner actions, in order

1. **Add one line to `.gitignore`:** `backend/app/build_revision.txt`. Then PR #5 satisfies the
   artifact contract. *(I can prepare this on request as a single additive commit on the PR branch.)*
2. **Owner-merge PR #5.** Do not merge #4 or #3.
3. **Let the Git integration build from `master`, then read the build log** to confirm the hook executed
   and whether cwd was `backend/`. If the path failed to resolve, move the hook to a project-root path
   in the **same** root `vercel.json` — not a second config layer.
4. **Verify `gitSource.sha == artifact SHA == /health revision`, all exact 40-char.**
5. **Decide `scholarzone.vercel.app`** (section 21.5).
6. **Address contamination** so a release signal cannot depend on ambient local state.

**ONE canonical provenance implementation. ONE release identity gate. No fabricated evidence.
No destructive shortcuts. Production data never touched.**