# SCHOLARZONE — FINAL RELEASE ORDER AND PROOF

| | |
| --- | --- |
| PR | **#5** — https://github.com/gopal735/ScholarZone/pull/5 |
| Head | `01f128c880730c079d24633ad12ee333454116a5` |
| Base | `origin/master` `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| State | **OPEN · MERGEABLE** (`mergeStateStatus: UNSTABLE` — Vercel quota only) |
| Scope | **12 files, +1682 / −61** |
| Frontend | **untouched** |
| Production data | **never written** |
| **Classification** | **READY_FOR_OWNER_MERGE** |

Labels: **PROVEN**, **VALIDATED**, **UNKNOWN**, **BLOCKED**.

---

## 1. The 10-vs-11 file discrepancy — resolved

**PROVEN, and it was never a scope problem.** The report recorded a diffstat at
commit `f9b4778`. A later commit added the report itself.

| Diff | Result |
| --- | --- |
| `master..f9b4778` | **10 files changed, 1265 insertions, 61 deletions** ← what the report said |
| `master..335eee8` | **11 files changed, 1473 insertions, 61 deletions** ← what GitHub showed |
| `f9b4778..335eee8` | **1 file changed, 208 insertions** |

1265 + 208 = **1473**, and 10 + 1 = **11**. The eleventh file was
`BUILD_PROVENANCE_PR_FINAL.md` at exactly **+208** lines.

**Conclusion (PROVEN): the report was stale by exactly one commit.** No file was
added to fix a number, and nothing was deleted to make numbers match.

**The count has since moved again, legitimately.** Reconciliation found three real
gaps (§4), fixed in `01f128c`, taking the PR to **12 files / +1682 / −61**. Local
`git diff --shortstat` and live GitHub metadata now agree exactly.

## 2. Final exact changed-file list

| Path | +/− | Provenance-related | Required |
| --- | --- | --- | --- |
| `backend/app/build_provenance.py` | +148 | YES — artefact module | YES |
| `backend/scripts/embed_build_revision.py` | +41 | YES — build generator | YES |
| `backend/scripts/release_identity_gate.py` | +338 | YES — identity gate | YES |
| `backend/tests/test_build_provenance.py` | +438 | YES — provenance tests | YES |
| `backend/tests/test_release_identity_gate.py` | +307 | YES — gate tests | YES |
| `backend/tests/test_final_hardening.py` | +42 / −8 | YES — replaces a test asserting the *old wrong* behaviour | YES |
| `backend/tests/test_vercel_migration.py` | +79 / −16 | YES — build-wiring assertions | YES |
| `backend/app/main.py` | +66 / −32 | YES — artefact-only `build_revision()`, 503 fail-closed | YES |
| `vercel.json` (repository root) | +2 | YES — backend `buildCommand` + `installCommand` | YES |
| `.github/workflows/deploy.yml` | +4 / −5 | YES — exact-SHA gate | YES |
| `.gitignore` | +9 | YES — keeps the build artefact out of git | YES |
| `BUILD_PROVENANCE_PR_FINAL.md` | +208 | documentation of this PR | optional |

**PROVEN — no duplicates.** No Mentor, Supervisor, frontend, security-visibility,
image, ingestion, Match, Count, Application Workspace, auth, scheduler, or data
change. `backend/tests/test_final_hardening.py` is in scope because the port
**replaces** `test_revision_is_the_env_value_truncated`, which asserted the old,
wrong behaviour (env-var override plus twelve-character truncation).

**PROVEN — master integrity.** `git log HEAD..origin/master` is **empty**: the PR
contains all of current master. Nothing is reverted. PR #2's security fix is intact
in the PR tree (public detail calls the canonical predicate at
`services/scholarships.py:55`; the shared loader is still bare `session.get`;
exactly **one** predicate definition). Count, Match, Admin Verification,
Application Workspace, `dependencies.py` and Dashboard are present and **untouched**.

## 3. Canonical provenance architecture

**PROVEN — exactly one of each component; no competing implementation from PR #3
or #4 exists in this branch.**

| Role | Single implementation |
| --- | --- |
| Build generator | `backend/scripts/embed_build_revision.py` |
| Provenance artefact | `backend/app/build_revision.txt` |
| Runtime reader | `read_embedded_revision()` in `app/build_provenance.py` |
| `build_revision()` | `app/main.py:53` |
| Deploy gate | `.github/workflows/deploy.yml` |
| Release identity gate | `backend/scripts/release_identity_gate.py` |

**PROVEN.** No `write_build_provenance.py`, `generate_build_revision.py`, or
`app/provenance.py` from PRs #3/#4 is present.

## 4. Three real gaps found during reconciliation

The line-count mismatch prompted a re-audit, which found three genuine defects.

**4.1 The artefact was not gitignored.** It was untracked — which is not the same
as ignored. A committed copy ships inside the package, so a stale SHA or a
developer machine's `dev` marker would be presented as a real deployment's
identity and the fail-closed guarantee would quietly stop meaning anything.
**PROVEN fixed**, with tests asserting it stays ignored and untracked.

**4.2 The build accepted an uppercase SHA and lower-cased it**, on the reasoning
that case is a formatting difference rather than an identity difference. That was
wrong here: the identity gate refuses anything that is not exactly forty lowercase
hex, so normalising on the way in left the build contract and the gate contract
disagreeing — and the disagreement could only surface at verification time, after
a deployment, rather than at build time. **PROVEN fixed**: build and runtime now
read the value verbatim.

**VALIDATED — this tightened a test, it did not weaken one.** The ported
`test_an_uppercase_sha_is_normalised_not_refused` asserted the old behaviour. It
was rewritten to assert rejection, with the reasoning recorded in the test. The
boundary is stricter after this change than before it.

**4.3 The identity gate did not bind the project.** Two Vercel projects serve this
repository from the same master branch, so an otherwise-perfect deployment could
still belong to the wrong one. **PROVEN fixed**: `--project` is accepted and a
mismatch — or a payload naming no project at all, which would otherwise let "I did
not check" pass as "it matched" — is refused.

## 5. Build contract

**PROVEN.** Accepts only `^[0-9a-f]{40}$`. Refused, each with a named test: empty,
too-short, 39 chars, 41 chars, non-hex, branch name (`main`), branch ref, tag-like
`latest`, `unknown`, deployment URL, and **uppercase**. A refused platform build
writes **no artefact** and the script exits non-zero.

**PROVEN.** The artefact is generated at build time, contains the exact full SHA,
and is validated. **PROVEN** it is gitignored and never committed.

## 6. Runtime contract

**PROVEN.** Runtime reads the artefact only. Cannot be overridden by
`VERCEL_GIT_COMMIT_SHA`, `VERCEL_GIT_COMMIT_REF`, or `SCHOLARZONE_BUILD_REVISION`
(the last is no longer supported at all); nor by a request header, query parameter,
alias, URL or branch ref. Nothing is truncated.

**PROVEN.** Fail-closed: missing artefact in production → `/health` **503**; corrupt
artefact → always raises; missing artefact off-platform → `dev`. A corrupt artefact
degrading to `dev` was explicitly rejected, because that would let a broken
deployment answer `ok` on the one endpoint whose job is to notice.

## 7. Build wiring — structurally proven, execution unproven

**PROVEN.** Both Vercel projects have Root Directory `.`, so the platform reads the
**repository-root** `vercel.json`. This PR modifies that file; the backend service
gains `buildCommand: python scripts/embed_build_revision.py`, and `installCommand`
also runs it so identity is embedded even on a path that skips the build step.
`test_build_provenance.py` asserts the wiring.

**PROVEN.** Pre-fix evidence that no build ran: project `Build Command` was `None`
and live deployments show the root build at `[0ms]`.

**BLOCKED — real execution is NOT proven.** Per the brief, a configuration
declaration is not final proof. Confirming it requires an actual deployment, which
the quota prevents (§9). **VALIDATED by inspection:** PRs #3 and #4 modify
`backend/vercel.json` instead, which the root-deployed project does not read — so on
their current contents the hook would not be wired. That is inspection, not proof,
and is labelled as such.

## 8. Deploy gate and release identity gate

**PROVEN — deploy gate strengthened, not weakened.** `EXPECTED_SHORT` removed;
comparison is exact `${github.sha}`; accepted shape narrowed from `^[0-9a-f]{7,40}$`
to `^[0-9a-f]{40}$`. Wrong SHA, missing SHA, `unknown` and any non-40-char value
all fail.

**PROVEN — release identity gate** binds project, deployment id, deployment URL,
`gitSource.ref`, `gitSource.sha` and the runtime health SHA, requiring exact
equality on two full forty-character SHAs. It rejects: an alias substituted for a
deployment; a **production** response when a **preview** was requested; a prefix in
either field; the wrong deployment id; the wrong expected commit; an expected SHA
that is itself a prefix; and a payload naming no project.

**PROVEN — contamination hardening.** A stale process reporting another commit, the
wrong backend, the wrong project, or a unique sentinel value cannot pass. The gate
is asserted to consult **no database and no ambient state** (no `sqlalchemy`,
`create_engine`, `sessionmaker`, `sqlite` in the module), which is what prevents the
leftover-local-file contamination that has misled this project before. Multiple
simultaneous faults are all reported, not just the first.

## 9. Quota state

**BLOCKED — `PROVIDER_DEPLOYMENT_BLOCKED`.** `api-deployments-free-per-day`,
"retry in 24 hours", now reported on **three** projects: `rc-revprov`,
`scholarzone`, `scholarzone-fwzj`.

**PROVEN.** Checked **once**, read-only. No deploy, no retry, no dummy commit, no
throwaway project, no quota bypass. All **10 GitHub Actions checks pass**; the only
failing checks are the three Vercel quota ones.

## 10. Tests

| Suite | Result |
| --- | --- |
| Provenance + release identity gate | **79 passed** |
| Full backend — untouched master `ddcd9c3` | 4988 passed / 8 failed / 11 skipped / 13 warnings / 1 error |
| Full backend — PR #5 head | **5068 passed** / 8 failed / 11 skipped / 13 warnings / 1 error |
| Delta | **+80 passed. Zero new deterministic failures.** |
| Security (public list/detail parity, hidden, nonexistent, hidden == nonexistent) | **21 passed** |
| Count | **78 passed** |
| Match | **421 passed** |
| Frontend | **untouched** — no frontend file changed in the tree or any commit |

The 8 failures are the known pre-existing set, all in `test_neon_migration.py`
(they need the untracked `migration_export.sql`); the 1 error is
`scripts/artifact_smoke_test.py::test_endpoint`. **No test was weakened, skipped or
xfailed.**

### A pre-existing test-safety defect found, not fixed

**PROVEN.** `test_final_hardening.py::TestDiscoveryQualityGate::test_it_measures_against_the_real_catalogue`
calls `init_database()` and then asserts a rejection ratio against **the gitignored
local `backend/scholarzone.db`**. Its outcome depends on that file's contents.

Evidence it is **not** a regression from this PR:
- My diff does **not** touch `TestDiscoveryQualityGate` or that test (**PROVEN** —
  the blob differs from master only in `build_revision` tests).
- Run in a 3-file subset it **fails** here and **skips** on the untouched baseline
  worktree, because the two gitignored `scholarzone.db` files differ (512 000 vs
  696 320 bytes, both rewritten by test runs).
- Run inside the **full suite it passes**.

**VALIDATED.** This is ambient-state contamination: a test whose result depends on
untracked local data. Reported, not fixed — it is outside this release's scope and
"fixing" it would change what the discovery-quality gate proves. It joins the
previously-reported unrestored env mutation at
`test_visibility_count_consistency.py:53-55`.

## 11. Merge state

**PROVEN.** PR #5 is **OPEN** and **MERGEABLE**, base `master` `ddcd9c3`,
merge-base equals the master tip. `mergeStateStatus: UNSTABLE` reflects **only** the
quota-blocked Vercel checks, not a code problem.

**PROVEN.** PR #3 and PR #4 are **not** to be merged and remain unmerged. No
duplicate provenance implementation exists in this branch.

## 12. Post-merge deployment state — pending

**BLOCKED.** Not yet executed. No deployment was performed.

When the quota resets and the owner merges, the required proof is exact:

```
gitSource.sha  ==  build artefact SHA  ==  /health runtime SHA
```

all exact, lowercase, forty characters. Any of `12-char`, `unknown`,
`unproven-build`, or a mismatch ⇒ **STOP**, classification
`RELEASE_IDENTITY_BLOCKED`.

## 13. Production security regression — current state

**PROVEN.** The security fix is behaviourally live on **both** public backends.
Verified read-only over ids 1–120, using only public `GET` requests:

| Host | 200 | 404 | Divergences |
| --- | --- | --- | --- |
| `scholarzone-fwzj` (gitSource `ddcd9c3…`) | 75 | 45 | — |
| `scholarzone` (no gitSource) | 75 | 45 | **0** |

Identical titles and trust status on public ids. Because `scholarzone-fwzj` is
provably running the merged fix, the stale host returning 404 for the same 45
non-public records means it is behaviourally fixed too.

**UNKNOWN.** Which commit the `scholarzone` deployment contains — it has no
`gitSource`, so platform metadata cannot say. Behaviour is consistent with the
fix; identity is unproven. That is exactly the gap PR #5 closes.

**No incomplete page-set reasoning is used as proof of completeness** — the
comparison is a fixed id range against a reference host whose commit is known, not
an inference from OFFSET pages.

## 14. No production writes

**PROVEN.** No Neon write, no production record created or modified, no visibility
change, no fabricated hidden id, no schema or migration change, no deployment
retry, no quota bypass, no destructive Git command, no force push, no rebase of a
shared branch, and `origin/master` was never moved. Staging used explicit paths
only — never `git add .` or `git add -A`.

## 15. Release order

1. **Close PR #3 and PR #4** in favour of #5. Three overlapping provenance PRs is a
   merge hazard, and only #5 edits the authoritative root `vercel.json`.
2. **Merge PR #5.**
3. **Wait for the quota reset.** Do not deploy manually while limited.
4. After reset: confirm both projects redeployed from master, then run the exact
   forty-character identity proof (§12) and the read-only production security
   proof (§13) on both hosts.

One merge costs **two** production deployment attempts (one per project, same
account, both with Git integration on `master`). There is no unsafe intermediate
state, because master already carries the security fix — the same deploy that adds
provenance also ships the fix to both backends.

## 16. Final classification

# READY_FOR_OWNER_MERGE

Every merge-readiness condition is met and evidenced: scope exactly explained and
now reconciled to 12 files; current master fully contained with PR #2's security
fix intact; one canonical provenance design with no PR #3/#4 duplicates; 79
provenance/gate tests and a full suite of 5068 against a 4988 baseline with zero
new failures; build wiring structurally correct against the authoritative config;
deploy gate exact; release identity gate exact; no security regression.

**Explicitly not claimed:** that a build hook has ever executed, or that a
deployment identity has been proven. Both require a real Git-triggered deployment,
which the quota currently prevents. If the hook turns out not to execute, the
failure is loud by design — `/health` 503 and `deploy.yml` fails — which is the
correct trade against publishing a deployment that cannot name its own commit.