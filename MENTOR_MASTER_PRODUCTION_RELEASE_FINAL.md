# MENTOR_MASTER_PRODUCTION_RELEASE_FINAL.md

**Scope:** Mentor final hardening · Vercel / production identity · release reconciliation
**Date:** 2026-10-04
**No deployment performed. No merge performed. Master not rewritten.**

Labels: **PROVEN** (direct evidence) · **VALIDATED** (verified, reproducible) ·
**UNKNOWN** (not determinable from available evidence) · **BLOCKED** (cannot proceed)

---

## 1. Executive Verdict

Two coherent, reviewable units now exist and **neither is merged**:

| PR | Branch | Base | Content |
|---|---|---|---|
| **#1** | `release/mentor-hardening-pr` → `13e9765` | `573a983` | Mentor verified-claim auditability |
| **#4** | `release/build-provenance-identity` → `17920a5` | `573a983` | Immutable build identity |

**PROVEN** — production still runs `build_revision()` that reads a **runtime** env var and returns a
**12-character** prefix, and `scholarzone.vercel.app` still serves a revision **2 commits behind**
`scholarzone-fwzj.vercel.app`.

**PROVEN** — the canonical production host is **provable** (`scholarzone-fwzj.vercel.app`), but the
**stale host is publicly reachable and crawlable** and has not been reconciled.

**Not completed in this pass:** the deploy gate still compares prefixes; the reusable release
identity gate was not built; no preview or browser E2E was run because nothing was deployed.

## 2. Current Master

| Item | Value |
|---|---|
| `origin/master` at audit start | `573a983b004ab08578497272659123323ab489b7` |
| `origin/master` at report time | **`ddcd9c3`** (advanced by another actor via PR #2, public-visibility release) |
| Production revision | **`ddcd9c3662f4`** |
| Commits I authored into master | **0** |

**PROVEN** — master moved during this task. Both PRs were based on `573a983` and remain **OPEN**;
neither `13e9765` nor `17920a5` is an ancestor of current master.

**Correction to my own tooling:** an earlier ancestry check in this session reported both commits as
ancestors of master. That was a misread exit status, not a fact — verified by reading master's
history and file contents directly.

## 3. Mentor PR Integrity — **VALIDATED**

| Check | Result |
|---|---|
| Files | exactly **6** |
| Forbidden subsystems (Supervisor, Discovery, Count, Match, image, ingestion, scheduler, Wave) | **NONE** |
| `compose.py` touched | **no** → `27047de` behaviour intact |
| `_FUNDING_WORDS`, `_EXACT_PRECISION`/`is_exact`, `seen_values`, `focused_application` | all **present** |
| UI redesign / unrelated work | none |
| Test changes | **additive only** (verified with `git diff -w`: 0 lines removed) |

## 4. Provenance Root Cause — **PROVEN**

`build_revision()` did two unsafe things:

1. **Runtime-controlled** — read `VERCEL_GIT_COMMIT_SHA`, then `VERCEL_GIT_COMMIT_REF`, then
   `SCHOLARZONE_BUILD_REVISION` **at request time**. Anything able to set an environment variable
   could change what `/api/health` claims while serving different code.
2. **Truncated** — `return raw[:12]`. A 12-character prefix cannot be compared with a commit, so the
   deploy gate could only ever check a prefix — exactly the check that lets the wrong artefact pass.

Production proves it live: `revision=ddcd9c3662f4`, **length 12**.

## 5. Immutable Build SHA — **PROVEN implemented, PR #4**

- **Build time:** `backend/scripts/generate_build_revision.py` accepts only a full **40-character
  lowercase** commit SHA and writes it to a generated module inside the package.
- Wired via `buildCommand` in `backend/vercel.json`.
- Generated module is git-ignored — a committed revision would be a claim about a build that never
  happened.
- Rejects: prefixes, over-length, uppercase, non-hex, branch names, deployment URLs. Accepts a
  whitespace-padded value but stores the clean SHA.

## 6. Health Endpoint — **PROVEN**

`build_revision()` now reads **only** the generated module. No runtime variable, header or query
string can influence it. 24 tests in `test_build_provenance.py`, including:

| Requirement | Test |
|---|---|
| full 40-char SHA works | `test_full_sha_is_reported` |
| 12-char rejected as canonical | `test_malformed_or_truncated_sha_fails_the_build` |
| malformed rejected | 9 parametrized cases |
| missing fails the build | `test_missing_sha_fails_the_build` |
| runtime `VERCEL_GIT_COMMIT_SHA` cannot override | `test_runtime_platform_variable_cannot_override` |
| `SCHOLARZONE_BUILD_REVISION` cannot override | `test_runtime_build_revision_variable_cannot_override` |
| request input cannot influence | `test_request_input_cannot_influence_revision` |
| health returns exactly the embedded SHA | `test_health_returns_exactly_the_embedded_sha` |

**Three pre-existing tests asserted the defect** (runtime variable wins, truncated to 12). They were
**replaced, not relaxed** — each now asserts the inverse and documents why the old expectation was
wrong.

**PROVEN fail-closed:** production with no artefact returns `unknown` even when a runtime SHA is
offered (`test_production_without_artifact_reports_unknown_not_a_sha`).

## 7. Deployment Gate — **NOT DONE**

`deploy.yml` still performs prefix-style revision checking. **BLOCKED** — not implemented in this
pass. Until it compares the full 40-character SHA from `/api/health` against Vercel's
`gitSource.sha`, the gate cannot prove artefact identity, and the provenance fix cannot be verified
end-to-end. This is the largest remaining gap.

## 8. Release Identity Gate — **NOT DONE**

The reusable backend/frontend/fixture identity gate (to stop stale uvicorn, stale Vite, wrong
database or wrong worktree producing believable-but-invalid results) was **not built**. **BLOCKED.**

## 9. Vercel Project A — `scholarzone` — **PROVEN**

| Field | Value |
|---|---|
| id | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` |
| link | github `gopal735/ScholarZone`, productionBranch `master` |
| framework / root | `services` / root |
| production aliases | `scholarzone.vercel.app`, `scholarzone-gopal735s-projects.vercel.app`, `scholarzone-git-master-gopal735s-projects.vercel.app` |
| live revision | **`3ee434c01f53`** |
| ancestry | `3ee434c` **is an ancestor of `4edd154`** → **stale by 2 commits** |
| created | 2026-10-01 13:44:51Z |

## 10. Vercel Project B — `scholarzone-fwzj` — **PROVEN**

| Field | Value |
|---|---|
| id | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| link | github `gopal735/ScholarZone`, productionBranch `master` |
| framework / root | `services` / root |
| production aliases | `scholarzone-fwzj.vercel.app`, `scholarzone-fwzj-gopal735s-projects.vercel.app`, `scholarzone-fwzj-git-master-gopal735s-projects.vercel.app` |
| live revision | `ddcd9c3662f4` (current master) |
| created | 2026-10-01 14:02:55Z |

**PROVEN** — both projects auto-deploy from the same repository and the same production branch.
Divergence is therefore not a configuration intent that can be read off either project; it is the
result of *which commit each project last built*.

## 11. Canonical User Host — **VALIDATED**

Three independent sources agree:

| Source | Evidence |
|---|---|
| Repository variable | `SCHOLARZONE_API_URL = https://scholarzone-fwzj.vercel.app/api` |
| `.github/**` | references **only** `scholarzone-fwzj.vercel.app` |
| Freshness | `-fwzj` serves current master; `scholarzone` is 2 commits stale |

**VALIDATED: canonical deployment/API host = `scholarzone-fwzj.vercel.app`.**

**UNKNOWN — SEO canonical host is UNDECLARED.** Neither host emits `<link rel="canonical">`, and
**both** serve a public `robots.txt` and `sitemap.xml`. The application therefore does not tell a
crawler which host is authoritative, and the stale host is indexable.

## 12. Stale Alias / Project Resolution — **BLOCKED, plan only**

**PROVEN state:** `scholarzone.vercel.app` is publicly reachable, publicly crawlable, and serves a
2-commit-old revision.

**Deliberately not done:** no project, alias or domain was deleted, and no Vercel configuration was
mutated. Ownership and intent for the second project are not proven, and deleting a live public host
to make a report read clean is exactly what must not happen.

**Recommended (requires owner authorisation):**
1. Merge and deploy PRs #1 and #4 to `master` so `-fwzj` carries current code.
2. Add `<link rel="canonical">` pointing at the canonical host in `frontend/index.html`.
3. Decide `scholarzone.vercel.app`'s fate with evidence: if it was a migration leftover, decommission
   it deliberately; if it is a rollback target, document it as such. Do not guess.

## 13. Rate Limit — **UNKNOWN / not tested**

**PROVEN** — no deployment was attempted from this session, so no quota call was issued.

**PROVEN** — deployments **are** still being produced by other actors (`13:30:17Z` on `-fwzj`,
`13:15:09Z` on `scholarzone`), so the earlier exhaustion state has either reset or is not being hit
by the current path. **UNKNOWN** whether this session's own account can deploy; not tested, because
testing it would require attempting a deployment.

## 14. Test Isolation — **PROVEN a real contamination case**

A discovery quality-gate test **skipped** on clean master but **failed** in my worktree. Cause: that
worktree's git-ignored `scholarzone.db` had been **populated by earlier suite runs** (696 KB vs
512 KB), pushing the catalogue past the gate's "too small to be meaningful" skip threshold.

**PROVEN** — after removing the local database the test skipped identically to master, and the full
suite on the provenance branch shows **no** discovery failure. This is precisely the contamination
class the release identity gate (Phase 6) exists to prevent — and it is direct evidence that gate is
needed, not theoretical.

## 15. Mentor Verification — **VALIDATED** (from the PR #1 gate)

| Gate | Result |
|---|---|
| Backend mentor/evidence/workspace/dashboard | 312 passed |
| Frontend | 165 passed |
| Lint / build | exit 0 / 259 ms |
| Browser E2E | 21/22 (the one flag was a bad assertion of mine) |
| Source URL integrity | 18 checked, 0 fabrications |
| `Verified` without source | **0** across 30 claims |
| Record-scoped dedup / named-app priority | **0 duplicates** / application leads |

## 16. Exact Changed Files

**PR #4 (infrastructure, 7 files, +454 / −46):**

```
.gitignore                                    +4
backend/app/main.py                           +65/-…
backend/vercel.json                           +4/-1
backend/scripts/generate_build_revision.py     +110 (new)
backend/tests/test_build_provenance.py         +225 (new)
backend/tests/test_final_hardening.py          (defect-assertion replaced)
backend/tests/test_vercel_migration.py         (defect-assertion replaced)
```

**PR #1 (Mentor, 6 files, +576 / −11):** `routers/mentor.py`, `services/mentor/context.py`,
`services/mentor/evidence.py`, `tests/test_mentor_hardening.py` (new),
`components/mentor/MentorAnswer.jsx`, `pages/MentorPage.test.jsx`.

No image, ingestion, scheduler, audit, Match, Count, Dashboard or Wave 1–3 file in either.

## 17. PR Structure — **OPTION B, two units**

Chosen over one combined PR. The provenance work is **build/release infrastructure**; the Mentor work
is **application behaviour**. Combining them would put two unrelated subsystems in one review and
make the Mentor diff harder to read for no benefit. Both target `master` and can be merged in either
order. **Neither was merged.**

## 18. Post-Reset Deployment Procedure

```
1. Confirm master SHA and that PR #1 and PR #4 are merged.
2. Merge PR #4 FIRST - until it lands, /api/health reports a 12-char prefix
   and no deployment can prove artefact identity.
3. Merge PR #1 (Mentor) independently.
4. Let the Git integration deploy master. Do NOT deploy a branch directly:
   a non-default branch yields a preview, not production.
5. Prove provenance from two independent paths:
     Vercel deployment gitSource.sha  ==  /api/health revision   (40 chars, exact)
6. Only then accept the deployment. A prefix match is NOT acceptance.
7. Run the release identity gate, then the Mentor authenticated E2E.
8. Reconcile the stale host per section 12.
```

## 19. Remaining Risks

1. **Deploy gate still compares prefixes** — the provenance fix cannot be verified end-to-end until
   the gate compares full SHAs. **BLOCKED, highest priority.**
2. **Release identity gate does not exist** — stale-server contamination is proven possible (§14).
3. **Stale public host serves a divergent revision and is crawlable** — users and crawlers can reach
   two different products. **BLOCKED** on an ownership decision.
4. **No SEO canonical tag** on either host.
5. **PHASE 7 (anonymous/authenticated test-state audit) not performed.**
6. **No preview or post-deploy browser E2E** — nothing was deployed, by design.
7. **Master is moving** — it advanced twice during this task; both PRs may need rebasing before merge.
8. **Out of scope, still open:** purge/public `image_kind` predicate contradiction, the `unknown`
   writer behind audit rows 66–91, October 3 reversion.

## 20. Final Decision

# `NEEDS_CONFIGURATION_FIX`

**Why not `READY_FOR_PR_ONLY`:** the code units are complete and reviewable, but the *release
mechanism* is not. The deploy gate still compares prefixes, the identity gate does not exist, and a
stale public host is unreconciled — so a deployment could not be proven correct even if it succeeded.

**Why not `BLOCKED`:** nothing found is unsafe to review or merge. Both PRs are self-contained, fully
tested (4991 backend passing; failures identical to the established environmental baseline), and touch
no protected subsystem.

**Why not `READY_FOR_PRODUCTION_RELEASE`:** fails on at least four of the eleven conditions —
`/api/health` still reports 12 characters in production, the gate does not compare full SHAs, the
stale host is unreconciled, and the identity gate is absent.

**Achieved this pass:** the provenance defect is root-caused, fixed, tested and PR'd; the Mentor fix
is verified and PR'd; the canonical host is proven from three independent sources; the stale host is
identified with proof; and a real E2E contamination mode is demonstrated and explained.

**No deployment. No merge. No project or alias deleted. Master not rewritten. Production data never
touched.**