# VERCEL_PROVENANCE_RECONCILIATION_FINAL.md

# FINAL CLASSIFICATION: `NEEDS_CONFIGURATION_FIX`

Read-only forensic audit. **No code changed. No Vercel settings changed. No merge. No deployment. No
production mutation.** `master` was not moved, rebased, or cherry-picked. No ref other than the
previously authorized `rc/mentor-hardening` push was touched.

---

## 1. Current Production Targets

Two live Vercel projects serve the same application against the **same database**, and they are
serving **different code**.

| | `scholarzone` | `scholarzone-fwzj` |
|---|---|---|
| Production alias | `https://scholarzone.vercel.app` | `https://scholarzone-fwzj.vercel.app` |
| Project ID | `prj_CKy7udubvQSf143NOsXI9LCXU5cQ` | `prj_NLC71y3rKRIOduTla785AzEOEFL5` |
| **Reported revision** | **`3ee434c01f53`** | **`4edd154a3037`** |
| Production deployment | `scholarzone-bvl7g26in-…` | `scholarzone-fwzj-oxfgjct80-…` |
| Age of latest production | ~2h | ~1h |
| **Actively receiving master deploys** | **NO** — pinned at `3ee434c` | **YES** — tracking master |
| Custom domain | none | none |
| Shared database | yes — both return `total: 358` identical records | yes |

Both are genuinely independent production targets: separate projects, separate aliases, separate
production deployment chains. This is a **pre-existing** condition, not caused by this audit.

## 2. Vercel Project Mapping

| Property | `scholarzone` | `scholarzone-fwzj` |
|---|---|---|
| Connected repo | `gopal735/ScholarZone` | `gopal735/ScholarZone` |
| Link type | `github` | `github` |
| Repo ID | `1354421070` | `1354421070` |
| Fork protection | `true` | `true` |
| **Root Directory** | `''` (repo root) | `''` (repo root) |
| Framework | `services` | `services` |
| Node | `24.x` | `24.x` |
| Build command | *(none)* | *(none)* |
| Install command | *(none)* | *(none)* |
| Ignore-build step | **none** (`vercel.json` has no `ignoreCommand`) | **none** |
| Deploy hooks | **none** | **none** |
| Local `.vercel` linkage | — | **`.vercel/repo.json` → `scholarzone-fwzj`** |

**Both projects are attached to the identical repository — same repo ID, no fork.** The mismatch is
therefore *not* a wrong-repository problem. Repo-root `vercel.json` defines only `services`
(backend `fastapi` at `backend/`, frontend `vite` at `frontend/`) and rewrites; it sets no build,
install, or ignore commands.

**Local linkage is misleading.** The checkout's `.vercel/repo.json` binds the directory to
`scholarzone-fwzj`, while the approved baseline revision `3ee434c` corresponds to `scholarzone`. An
operator trusting the local link would target the wrong project.

## 3. Deployment Provenance

### Branch previews (both created from the single authorized push)

| Field | `scholarzone` preview | `scholarzone-fwzj` preview |
|---|---|---|
| Deployment ID | `dpl_HgPpAqoXngXWntWzhmZX8mzaEsht` | `dpl_57aKPjQxEpQjYpL3GtCKNKEtyKSU` |
| Deployment URL | `scholarzone-ljx02326p-…` | `scholarzone-fwzj-ishkgtxmd-…` |
| Environment | `preview` | `preview` |
| `source` | **`git`** | **`git`** |
| `gitSource.ref` | **`rc/mentor-hardening`** | **`rc/mentor-hardening`** |
| `gitSource.sha` | **`00bc39dab3dbb4977b4b36419f301022c4199323`** | `00bc39dab3dbb4977b4b36419f301022c4199323` |
| `gitSource.type` | `github` | `github` |
| `meta.githubCommitSha` | `00bc39dab3db…` | `00bc39dab3db…` |
| `meta.githubCommitRef` | `rc/mentor-hardening` | `rc/mentor-hardening` |
| `meta.githubCommitMessage` | `fix: scope mentor chip dedup to one record` | same |
| `meta.repoPushedAt` | `1791117224000` | `1791117224000` |
| Alias | `scholarzone-git-rc-mentor-hardening-…` | — |
| Created (epoch ms) | `1791117227465` | `1791117227443` |

Both were created **22 ms apart** from one push — i.e. both projects received the same Git-triggered
build of the same commit. **Vercel's authoritative metadata states the correct commit was built.**

### Artifact distinctness (rules out build reuse)

| Deployment | Metadata SHA | Lambda digest | Size |
|---|---|---|---|
| `scholarzone` preview | `00bc39d` | `2d124cc74b08` | 68,350,942 |
| `scholarzone` production | `3ee434c` | `a4c9920a519c` | 68,345,851 |
| `scholarzone-fwzj` preview | `00bc39d` | `35b7f899ae34` | 68,350,917 |
| `scholarzone-fwzj` production | `4edd154` | `2693abdd4642` | 68,347,423 |

All four digests and all four sizes are **distinct**. Neither preview reuses the `4edd154`
production artifact. The two previews are within **25 bytes** of each other and ~3.5 KB larger than
their productions — the signature of **two builds of the same commit** under slightly different
per-project config, not two builds of `4edd154`.

### Runtime-reported identity (the anomaly)

| Endpoint | Reported revision |
|---|---|
| `scholarzone` preview `/api/health` | `4edd154a3037` |
| `scholarzone-fwzj` preview `/api/health` | `4edd154a3037` |

Verified against the **deployment-specific URLs** (not aliases), so this is not a mis-targeted
measurement. Previews are behind Vercel **Deployment Protection**; `vercel curl` was required.

## 4. Exact SHA Mismatch Cause

### Classification: **E — build-time code is incorrectly reporting the SHA**

The chain in `backend/app/main.py::build_revision()` is:

1. `VERCEL_GIT_COMMIT_SHA`
2. `VERCEL_GIT_COMMIT_REF`
3. `SCHOLARZONE_BUILD_REVISION`
4. `dev` / `unknown`

Every alternative was tested and eliminated with evidence:

| Candidate cause | Verdict | Evidence |
|---|---|---|
| **A. Wrong commit/ref deployed** | **Ruled out** | `gitSource.sha` = `00bc39dab3db…`, `ref` = `rc/mentor-hardening`, `source` = `git` on both previews |
| **B. Git integration points elsewhere** | **Ruled out** | Both projects: same repo ID `1354421070`, `gopal735/ScholarZone`, type `github`, no fork |
| **C. Existing deployment reused/selected** | **Ruled out** | All four artifact digests and sizes distinct; previews are new deployment IDs |
| **D. Ignored-build / automation** | **Ruled out** | No `ignoreCommand` in `vercel.json`, no build/install commands, no deploy hooks on either project |
| **E. Code incorrectly reporting SHA** | **CONFIRMED** | `SCHOLARZONE_BUILD_REVISION` is **absent** from both projects, so the code cannot have produced `4edd154a3037` from step 3. The only remaining source is step 1, and Vercel's own metadata contradicts the value the runtime observed |
| **F. Env-var/config override** | **Ruled out** | Full env key inventory retrieved for both projects — no `SCHOLARZONE_BUILD_REVISION` |
| **G. Other** | — | Not required; E is proven |

Env key inventory (names only, values never read) — identical on both projects apart from fwzj's extra
`DATABASE_URL`:

`SCHOLARZONE_DATABASE_URL`, `SCHOLARZONE_ENVIRONMENT`, `RESEND_API_KEY`, `NOTIFICATION_EMAIL`,
`SCHOLARZONE_VERIFICATION_SECRET` *(+ `DATABASE_URL` on fwzj)*.

### The defect, stated precisely

`build_revision()` trusts `VERCEL_GIT_COMMIT_SHA` because a platform identifier "cannot be falsified
by hand". For these **`services`-framework Python lambdas, that assumption is false**: the runtime
observed `VERCEL_GIT_COMMIT_SHA = 4edd154a3037…` while the deployment's own `gitSource.sha` was
`00bc39dab3db…`. Both previews reported the same stale value, which is the signature of a
**build-environment variable inherited from an earlier master build** rather than the commit the
lambda was compiled from.

**Cache is not invoked.** Nothing here requires a caching explanation: the artifacts are provably
distinct and the trigger metadata is provably correct. The fault is confined to the *reported build
identity*, not to what was built.

### What this does and does not prove

- **Proven:** the correct commit was requested, the trigger was Git, the artefact is distinct from
  `4edd154`, and the health endpoint's revision string is unreliable for these builds.
- **Not proven read-only:** that the running lambda actually contains the chip-dedup fix. Every code
  path that exercises the fix requires an **authenticated** mentor answer, which would mean creating
  users/applications — a data mutation, which this audit forbids.

### Correction to the previous turn

My prior report concluded the preview "does not contain the candidate" and classified the outcome as
a wrong-ref build. **That conclusion was wrong.** The metadata shows the correct commit was built; the
defect is in the reported identity. The earlier caution (do not promote) still holds, but for a
different and narrower reason: `/api/health` cannot currently prove what is running, so `deploy.yml`'s
revision gate cannot be satisfied by any deployment of this candidate.

## 5. Two-Project Divergence

| | `scholarzone` | `scholarzone-fwzj` |
|---|---|---|
| Latest production age | ~2h | ~1h |
| Tracks master | **No** — stuck at `3ee434c` while master is `573a983` | **Yes** |
| Contains `27047de` (mentor claim-verification fix) | **No** | **Yes** |
| Master commits deployed | `3ee434c` | `3bf92b6`, `c3aefad`, `3ee434c`, `27047de`, `4edd154` |

`scholarzone` has **two** deployments still marked `Production`, and has not consumed four
subsequent master commits. `scholarzone-fwzj` has consumed them.

**Operational consequence:** `27047de — fix: stop the mentor asserting a claim it never checked about
a student's record` is live on one target and absent from the other. The two surfaces present
different Mentor behaviour today.

## 6. Canonical Production Recommendation

**Recommend `scholarzone-fwzj` as the single canonical production project.**

Evidence:

1. **Repository linkage** — `.vercel/repo.json` in the checkout binds the working directory to
   `scholarzone-fwzj`.
2. **Actively receiving Git deployments** — it has consumed every master commit including
   `27047de` and `4edd154`; `scholarzone` has consumed none since `3ee434c`.
3. **Deployment history** — its latest production is ~1h old versus ~2h.
4. **Continuity** — freezing `scholarzone` means two Mentor behaviours persist indefinitely.

**Counter-evidence, stated plainly:** `scholarzone.vercel.app` is the tidier public alias and is the
target whose revision matches the base the candidate was approved against (`3ee434c`). Neither
project owns a custom domain, so alias tidiness is the only signal favouring it.

**Recommendation is conditional on one owner confirmation:** which URL real users actually reach.
The audit cannot determine this from configuration — no custom domain exists, and both serve the same
database. If users reach `scholarzone.vercel.app`, then `scholarzone-fwzj` is a shadow target and the
canonical choice inverts. **This must be answered before any deployment.**

**No configuration was changed.**

## 7. Current Master Mentor State

`origin/master` = `573a983b004ab08578497272659123323ab489b7`, four commits beyond `3ee434c`:

| Commit | Subject | Files |
|---|---|---|
| `27047de` | fix: stop the mentor asserting a claim it never checked about a student's record | `mentor/compose.py` (+11/−2), `tests/test_mentor.py` (+38/−2) |
| `4edd154` | docs: record the final suite numbers and the production run | docs only |
| `84d9d7e` | docs: correct the commit list in the final report header | docs only |
| `573a983` | docs: the wording fix is deployed and verified in production | docs only |

**Critical finding:** `master`'s `backend/app/services/mentor/evidence.py` blob is
`aab902214f3f` — **byte-identical to `3ee434c`**. Master has **not** touched the chip-dedup code, so
the candidate's fix is still absent from master and no master Mentor work is at risk from it.

The behaviours the integration must preserve are all still present on master:
`27047de` (compose.py claim verification), funding-word logic (`_FUNDING_WORDS`, `funding_word`),
exact/month/unknown deadline semantics (`DeadlineFacts.days_remaining is None` for four distinct
cases), and focused-application prioritisation (`groups` ordering in `collect()`).

## 8. 00bc39d Integration Conflicts

Read-only analysis via `git merge-tree 3ee434c 00bc39d origin/master` (textual; writes no objects,
no refs, no working-tree files).

| File | Base → candidate | Base → master | Conflict |
|---|---|---|---|
| `backend/app/services/mentor/evidence.py` | changed (3 lines) | **unchanged** (blob `aab90221` = base) | **NONE** |
| `backend/tests/test_mentor.py` | changed (+167) | changed (+38) | **resolves cleanly** |

**Real conflict markers found: 0.** `test_mentor.py` is reported "changed in both", which is
informational, not a conflict. The hunks are provably disjoint in base coordinates:

| Side | Base hunk range | Region |
|---|---|---|
| `27047de` | `@@ -1162,11 +1162,45 @@` | inside `class TestEvidenceBudget` — adds `test_progress_is_disclaimed_only_when_this_answer_did_not_read_it` |
| candidate | `@@ -32,6 +32,15 @@` | import block — adds `MentorContext`, `ScholarshipFacts`, `collect`, etc. |
| candidate | `@@ -1238,4 +1247,160 @@` | **end of file** — appends `class TestChipDedupScope` |

A 66-line gap separates the master's mid-file insertion from the candidate's EOF append. They do not
overlap and are not adjacent within merge context.

### Required semantic patch

**Zero source changes are required.** The entire integration is the candidate's own diff replayed
onto master:

```diff
--- a/backend/app/services/mentor/evidence.py      (master blob aab90221 == base, applies cleanly)
+++ b/backend/app/services/mentor/evidence.py
@@ def collect(context: MentorContext, *, limit: int = 10) -> list[EvidenceItem]:
-    seen_values: set[tuple[str, str]] = set()
+    #: (new comment block explaining the per-record scope)
+    seen_values: set[tuple[int | None, str, str]] = set()
@@
-                fingerprint = (chip.label, chip.value)
+                fingerprint = (entry.scholarship_id, chip.label, chip.value)
@@
-        fingerprint = (entry.label, entry.value)
+        fingerprint = (None, entry.label, entry.value)
```

plus, in `backend/tests/test_mentor.py`:

1. the nine-line import addition after `from app.database import get_db`;
2. the `TestChipDedupScope` class (5 tests) appended after `class TestIntentClassification`.

**Explicitly preserved, untouched by this patch:** `27047de` in `compose.py` and its test;
`_FUNDING_WORDS` / `funding_word`; `DeadlineFacts` semantics; focused-application prioritisation in
`collect()`; the chip budget and ordering; and every existing production Mentor fix.

**Verification that nothing is reverted:** the patch edits only `seen_values` and two `fingerprint`
assignments. It does not touch `compose.py`, does not alter `groups` ordering or the `limit`
truncation, and does not alter any funding or deadline logic.

## 9. Required Next Integration Steps

1. **Fix the build-identity reporting first** (the actual blocker). Either stop trusting
   `VERCEL_GIT_COMMIT_SHA` for `services` Python lambdas in favour of the deployment's own
   `gitSource.sha`, or have Vercel stop injecting a stale value. Until `/api/health` reports the
   commit that was built, `deploy.yml`'s revision gate can never pass and no promotion can be
   evidenced.
2. **Owner confirms the canonical production URL** (§6). Then retire or explicitly mark the other
   project so two Mentor behaviours cannot persist.
3. **Reconcile `scholarzone` vs `scholarzone-fwzj`** so `27047de` is live on whichever target users
   actually reach.
4. **Land the candidate on master** by fast-forwarding `master` to `00bc39d` **only if** the operator
   accepts dropping `27047de`/`4edd154` — otherwise merge `00bc39d` into `573a983`. Per analysis this
   merges cleanly with zero conflicts and zero manual resolution. **Do not rebase `master`.**
5. **Then deploy**, and verify behaviourally: an authenticated mentor answer across two records with
   identical chip values must return a chip for **each** record. That behavioural check — not
   `/api/health` — is the only trustworthy proof the fix is live.
6. **Separately**, fix the conditionally-vacuous
   `test_application_evidence_reports_measured_progress` guard, and the
   `"Applications: undefined"` accessible name.

## 10. Safety Verdict

# `NEEDS_CONFIGURATION_FIX`

**Integration itself is safe.** The candidate applies to current master with **zero conflicts and no
semantic conflict to resolve**; master's `evidence.py` is untouched from the approved base, and the
`test_mentor.py` hunks are disjoint. No master Mentor fix — `27047de`, funding-word logic, deadline
semantics, or focused prioritisation — is at risk.

**Deployment is not currently possible to evidence.** Two independent blockers:

1. `/api/health` reports a stale commit for these builds (cause **E**, proven). `deploy.yml` requires
   the reported revision to match the deployed SHA, so it will fail for *any* deployment of this
   candidate — including a correct one.
2. The canonical production target is **unconfirmed**, and the two targets currently serve different
   Mentor behaviour.

Neither blocker is caused by the candidate. Both pre-existing, both owner-resolvable.

### Claims

**Claimed:** the candidate was correctly built from the correct commit and ref; the mismatch is in
reported build identity; integration onto master is conflict-free and reverts nothing; the two
projects are independent targets with divergent Mentor behaviour.

**Not claimed:** that the previewed lambda's running code contains the chip-dedup fix (not provable
read-only); that either production surface serves it today; which URL users actually reach; that the
October 3 root cause is solved (Phase 6 remains **CASE E / NOT OBSERVED**).