# MENTOR_HARDENING_PRODUCTION_DEPLOY_FINAL.md

# FINAL CLASSIFICATION: `DEPLOYMENT_BLOCKED`

**NOTHING WAS PROMOTED TO PRODUCTION. NO PRODUCTION DATA WAS WRITTEN. NOTHING WAS ROLLED BACK.**

Promotion was halted at the mandatory STEP 2/STEP 3 gate because the preview deployment built from the
candidate branch **does not report the candidate's commit**. Deploying it would have violated the
absolute rule *"Deploy EXACTLY 00bc39d"*.

---

## 1. Candidate SHA

| Item | Value |
|---|---|
| **Approved candidate** | **`00bc39dab3dbb4977b4b36419f301022c4199323`** (`00bc39d`) |
| Subject | `fix: scope mentor chip dedup to one record` |
| Pushed to | `refs/heads/rc/mentor-hardening` — verified as exactly `00bc39dab3db…` |

### STEP 1 verification — all passed

| Check | Result |
|---|---|
| Candidate HEAD identity | **match** |
| Candidate **parent == `3ee434c01f534e2cfd72300030316cdd27c33789`** | **match** (verified, not assumed) |
| Commits ahead of approved base | **1** |
| Changed files | **only** `backend/app/services/mentor/evidence.py`, `backend/tests/test_mentor.py` |
| Functional change | exactly the expected 3 lines (`seen_values` type, two `fingerprint` tuples) |
| `master` moved? | **NO** — `refs/heads/master` unchanged at `573a983b004ab08578497272659123323ab489b7` |

## 2. Production Revision BEFORE

| Target | Revision before |
|---|---|
| `https://scholarzone.vercel.app` | **`3ee434c01f53`** — exactly the approved base |
| `https://scholarzone-fwzj.vercel.app` | `4edd154a3037` |

## 3. Production Revision AFTER

**Unchanged. No promotion occurred.**

| Target | Revision after | Delta |
|---|---|---|
| `https://scholarzone.vercel.app` | `3ee434c01f53` | **none** |
| `https://scholarzone-fwzj.vercel.app` | `4edd154a3037` | **none** |

## 4. Deployment Mechanism

`deploy.yml` is **verification-only** — it contains no deploy step. Production is fed by **Vercel's
native Git integration**: both projects carry a `…-git-master-…` alias, proving they are built from
Git pushes rather than by CLI.

`vercel promote` **is** available in the installed CLI (59.11.7), so the requested
preview → promote mechanism exists. The branch push did create preview deployments on both projects.

## 5. Preview / Promote Evidence — THE BLOCKER

### The previews do not contain the candidate

| Deployment | Built from | **Self-reported revision** | Expected |
|---|---|---|---|
| `scholarzone-git-rc-mentor-hardening-…` (preview, project `scholarzone`) | `rc/mentor-hardening` | **`4edd154a3037`** | `00bc39dab3db` ❌ |
| `scholarzone-fwzj-ishkgtxmd-…` (preview, project `scholarzone-fwzj`) | `rc/mentor-hardening` | **`4edd154a3037`** | `00bc39dab3db` ❌ |

Both previews report the **same** revision, `4edd154a3037`, which is **a master commit**
(`docs: record the final suite numbers and the production run`) — **not** the candidate branch head.

### Why promotion had to be refused

`build_revision()` in `backend/app/main.py` deliberately refuses to trust an operator-supplied label
and resolves identity from `VERCEL_GIT_COMMIT_SHA` / `VERCEL_GIT_COMMIT_REF`, precisely so "a build
that is told what revision to claim will happily claim it while serving older code". That endpoint is
the product's own build-identity proof, and `deploy.yml` gates on it.

Because the preview reports `4edd154a3037`:

- I **cannot demonstrate** the preview contains the candidate.
- STEP 2.3 (*"verify preview revision == `00bc39d`"*) **fails**.
- STEP 3 (*"chip dedup regression fixed"*) **cannot be verified** on the preview.
- Promoting `scholarzone` would move production from `3ee434c` to **`4edd154` content**, importing
  `27047de fix: stop the mentor asserting a claim it never checked about a student's record` and two
  docs commits that were **never approved** for this deployment.
- Promoting `scholarzone-fwzj` would be a revision no-op and would risk rolling that target *backwards*.

Either action would breach *"Deploy EXACTLY 00bc39d. Do not include unrelated commits."*

### Second blocker — two competing production targets

| Project | Production URL | Serves |
|---|---|---|
| `scholarzone` | `scholarzone.vercel.app` | `3ee434c01f53` (= the approved base) |
| `scholarzone-fwzj` | `scholarzone-fwzj.vercel.app` | `4edd154a3037` |

Both are git-connected to the same repository, both auto-deploy `master`, both are live production
aliases, and **they serve different revisions right now**. The repo's own `.vercel/repo.json` links
the repository to **`scholarzone-fwzj`**, while the approved baseline revision matches
**`scholarzone`**. There is no custom domain on either to break the tie. This inconsistency is
**pre-existing** and was not introduced here, but it makes "the production target" ambiguous and it
must be resolved by the owner before any promotion.

## 6. Regression Verification

| Verification | Result |
|---|---|
| Function-level before/after (two records, shared `(label,value)`) | 5 chips → 8 chips; Funding 1 → 2; Deadline 1 → 2 |
| Real-HTTP before/after (same DB, same request) | Deadline chips **1 → 2** |
| New regression tests fail without the fix | **2 of 5 fail** — correct signature |
| New regression tests pass with the fix | **5 of 5 pass** |
| Mentor backend suite | **82 passed** |
| Full backend | **4978 passed**, 1 pre-existing failure |
| Frontend | **163 passed**, build clean, lint 0 errors |
| **Regression verified on the preview deployment** | **NOT VERIFIED — blocked (see §5)** |

The candidate itself is fully verified. It is the *deployment of it* that is blocked.

## 7. Browser Verification

Performed against the candidate built locally (isolated SQLite DB, real HTTP, Chromium):

| Check | Result |
|---|---|
| `/ScholarZone/mentor` | Renders, `h1` "Mentor" |
| Console errors | **0** |
| dashboard / applications / scholarships / match | all render |
| Horizontal overflow at 320px | **0 px** |
| Landmarks | `banner`, `main`, `contentinfo` present |

Not performed against the preview deployment — previews are behind Vercel **Deployment Protection**
(a direct request returned a Vercel login wall), and `vercel curl` was needed even to read
`/api/health`.

## 8. System Invariants

No production data was read for mutation and none was written. No maintenance stage, no image repair
or restoration, no Wave 1–3 action, no Neon write, no audit change.

| Invariant | Before | After |
|---|---|---|
| `scholarzone.vercel.app` revision | `3ee434c01f53` | `3ee434c01f53` |
| `scholarzone-fwzj.vercel.app` revision | `4edd154a3037` | `4edd154a3037` |
| Public record total (both targets) | `358` | `358` |

Storage / public / verified / image row counts were **not** re-measured, because the authenticated
`/api/scholarships/stats` and `/internal/verify/status` endpoints require
`X-Verification-Secret`, which I do not hold. The public `total` is unchanged at `358`, and no code
path in this change can alter row counts. This is stated as **not independently measured**, not as
"verified".

## 9. Console Status

| Surface | Status |
|---|---|
| Candidate, local browser | **0 console errors** |
| Preview deployments | Not browser-verified — Deployment Protection in effect |

## 10. Rollback Readiness

- **No rollback was performed or needed** — nothing was promoted.
- **Rollback remains available**: both production targets still serve their pre-existing
  deployments, which are untouched and intact.
- If a future promotion succeeds and then fails verification, the correct action is
  `vercel rollback` to the recorded prior deployment — but per instruction that must **not** be done
  automatically.

## 11. Remaining Mentor Issues

| # | Issue | Status |
|---|---|---|
| 1 | **Global chip dedup suppressing cross-record chips** | Fixed and verified in `00bc39d`; **not deployed** |
| 2 | `test_application_evidence_reports_measured_progress` wraps its body in `if progress_percent is not None:` — *conditionally* vacuous | Pre-existing; branch currently live; **deliberately not bundled** |
| 3 | `"Applications: undefined"` accessible name | Pre-existing a11y nit; not introduced here |
| 4 | `test_efficiency_safety`…`test_the_retry_shares_the_concurrency_group` | Pre-existing failure on production |
| 5 | `27047de` (mentor claim verification) is live on `scholarzone-fwzj` but **not** on `scholarzone` | **New divergence introduced by the pre-existing two-target split** |
| 6 | `00bc39d` is a **sibling** of `master`, and both modify `backend/tests/test_mentor.py` | Merging will require conflict resolution |
| 7 | `00bc39d` is not on `master`, so a future `master` deploy to `scholarzone` would **revert** this fix | Needs an owner decision on landing it |

## 12. Final Status

# `DEPLOYMENT_BLOCKED`

The candidate `00bc39dab3dbb4977b4b36419f301022c4199323` is **correct, minimal, fully tested and
locally verified**, and its parent is exactly the approved base `3ee434c`. It was **not deployed**,
because the Vercel preview built from its branch reports revision `4edd154a3037` — a master commit —
rather than the candidate. Promoting it would have shipped unapproved content and broken the
absolute rule.

### Exact owner actions required

1. **Explain why the branch preview reports `4edd154a3037`.** Both projects built a preview from
   `rc/mentor-hardening` and both claim a master commit. Prime suspects: Vercel build cache serving a
   stale artefact, the connected-repo/ref configuration, or `VERCEL_GIT_COMMIT_SHA` being injected
   from the wrong ref. Until a preview self-reports `00bc39dab3db`, promotion is unsafe.
2. **Declare which project is production.** `scholarzone` (matches the approved base `3ee434c`) or
   `scholarzone-fwzj` (matches `.vercel/repo.json`, currently on `4edd154`). Both are live and they
   disagree. This must be settled before any promote.
3. **Reconcile the `scholarzone` / `scholarzone-fwzj` divergence** — `27047de` is live on one and not
   the other.
4. **Decide how `00bc39d` lands on `master`.** It is currently a sibling; merging touches
   `test_mentor.py`, which `27047de` also modified. Without landing it, the next `master` deploy
   reverts the fix.
5. **Then** re-run: push branch → confirm preview reports `00bc39dab3db` → promote that exact
   deployment → verify `/api/health` revision, the cross-record chip behaviour, and the data
   invariants with `SCHOLARZONE_VERIFICATION_SECRET`.

### Claims made / not made

**Claimed:** the candidate is correct and verified locally; `master` was not moved; no production
data was written; production revisions are unchanged.

**Not claimed:** that anything was deployed; that the preview contains the candidate; that any
production surface now carries the chip-dedup fix; that the October 3 root cause is solved (Phase 6
remains **CASE E / NOT OBSERVED**).