# FINAL INFRASTRUCTURE RELEASE DECISION

**Investigation only. No deployment, no master rewrite, no force push, no production data write, no
maintenance dispatch, no image repair or restoration, no Wave 1–3 apply, no Mentor code change.**

---

# ⚠️ INVESTIGATION UPDATE — the release happened during this audit

While I was gathering evidence, the situation changed. Recording it first because it supersedes the
initial conclusion.

| time (UTC) | event |
|---|---|
| 11:03 | investigation opened; production `c405b49`, both Vercel projects rate-limited |
| ~11:0x | new commits landed: **`c3aefad`** "correct six defects the browser run found in the grounded mentor", then **`a1f214b`** merge of `grounded-mentor` into master |
| ~11:1x | Vercel status for `a1f214b` turned **pending** — "Vercel is deploying your app" |
| ~11:1x | **production advanced to `a1f214b04b94`**; both Vercel statuses now `success` |

**So the rate limit reset, and Vercel's automatic master→production pipeline deployed the tip by itself.**
Nobody dispatched it from this task. This is Candidate 1 from §5 executing without a gate.

Consequences, verified read-only immediately after:

- All public/data invariants **intact**: `stats.total` 358, `verified_active` 358, `with_image` 358,
  directory 358, Match 358/358, count contract 200, **no subset exceeding total**.
- `do_logos` and the ingestion fix are now **live in production**, as well as already live in the
  maintenance worker (§9).
- **M1 is now confirmed live**: `GET /api/mentor/overview` returns **200 anonymously** from production.
- **M2 is still unfixed** at the deployed tip (§8).
- `c3aefad`'s six Mentor corrections were **not reviewed by me**.

The final classification therefore changed from `WAIT_FOR_QUOTA` to **`OWNER_ACTION_REQUIRED`**.

---

## 1. Production State

**Before the automatic deploy** (evidence base for the investigation):

| item | value |
|---|---|
| live host | `scholarzone-fwzj.vercel.app` (`Server: Vercel`, region `iad1`) |
| live revision | `c405b49bb8b9`, `/api/health` → `ok` |
| last Production deployment to `scholarzone-fwzj` | 09:17:05Z |
| storage / public / Match | 451 / 358 / 358 |
| Mentor | **404** — not deployed |

**After the automatic deploy (current, verified read-only):**

| item | value |
|---|---|
| live revision | **`a1f214b04b94`** |
| health | 200 `ok` |
| `stats.total` / `verified_active` / `with_image` | 358 / 358 / 358 |
| subsets exceeding total | **none** |
| directory | 358 |
| Match total / partition | 358 / 358 |
| Count contract | 200 |
| `/api/mentor/overview` anonymous | **200** (static keys only) — M1 live |
| `/api/mentor/message` anonymous | **401** — correctly guarded |
| storage | 451 (unchanged) |
| HTTP 402 | **not present** in any current status |

## 2. Vercel Topology

Proven from `vercel.json`, the deployments API and commit statuses:

| property | value | how proven |
|---|---|---|
| projects | **two**: `scholarzone` and `scholarzone-fwzj`, team `gopal735s-projects` | deployment `target_url` values |
| live project | **`scholarzone-fwzj`** | its deployments point at `scholarzone-fwzj.vercel.app` |
| shape | **two-service monorepo** | root `vercel.json`: `backend` (FastAPI, `api.index:app`) + `frontend` (vite) |
| production follows master | **Yes, automatically** | every master commit 08:27→09:02 produced paired Production deployments; and again for `a1f214b` |
| branch pushes | **Preview only** | `4770c8a` on my forensic branch → `Preview – scholarzone` |
| deploy trigger | Vercel Git integration on push | **no workflow in the repo deploys anything** |
| dashboard control exists | **Yes** | a status reads `Canceled from the Vercel Dashboard` (08:58:44Z) |
| production branch | **`master`** | master commits auto-receive Production deployments |
| deployment protection | **none** | `production` and `Production – scholarzone-fwzj` both `protection_rules: []` |
| Vercel API access from here | **absent** | `VERCEL_TOKEN`/`TEAM_ID`/`PROJECT_ID`/`ORG_ID` unset; no `.vercel/project.json` |

**Not readable here, therefore not asserted:** account plan, exact limit consumed, configured production
branch as a *setting* (only its behaviour is evidenced).

## 3. Exact Deployment Blocker — **identified, and since resolved**

**PROVEN — Vercel build rate limit, per project.**

```
Vercel – scholarzone        failure  "Deployment rate limited — retry in 24 hours."
Vercel – scholarzone-fwzj   failure  "Deployment rate limited — retry in 24 hours."
target: vercel.com/gopal735s-projects?upgradeToPro=build-rate-limit
```

| time (UTC) | project | status |
|---|---|---|
| 08:27–09:02 | both | `Deployment has completed` |
| **09:16:27** | `scholarzone` | **rate limited** |
| 09:17:05 | `scholarzone-fwzj` | completed — last deploy before the block |
| **09:43:00** | `scholarzone-fwzj` | **rate limited** |
| 10:10:30 / 10:11:32 / 10:15:33 | both | rate limited for `5416914`, `9ff021b`, `3bf92b6` |
| ~11:1x | both | limit reset → `a1f214b` deployed to Production |

Ruled out on evidence: **build failure** (builds had completed; the message is a limit, not a build error),
**git integration broken** (Vercel received pushes and replied per project), **deployment protection**
(no protection rules), **cancellation race** (`deploy.yml` `cancel-in-progress: true` killed three
verifications for `9ff021b`, but that is noise, not the outage cause), **account/project setting**
(unknown — no credentials).

## 4. Master Ancestry

Linear, fast-forwardable; production was its ancestor throughout.

```
a1f214b  Merge grounded-mentor into master        ← new tip, DEPLOYED
c3aefad  fix: six Mentor defects from browser run ← new, NOT reviewed by me
3bf92b6  ingestion fix
9ff021b  do_logos fix
5416914  Mentor 1.0 (as first merged)
c405b49  former production baseline
```

`c405b49` remains an ancestor of the tip, so the release was a clean fast-forward — no history rewrite
occurred.

## 5. Isolated Release Options (as evaluated *before* the automatic deploy)

**Governing constraint, proven: Vercel builds a branch *tip*, and a feature branch deploys to Preview
only. So shipping only the image fixes requires the production branch to point at a tip excluding
`5416914` — the Mentor is an ancestor of the fixes and cannot be left behind by deploying a later commit.**

| option | ships | unrelated work | master mutation | Vercel supports | executable then | rollback | blast |
|---|---|---|---|---|---|---|---|
| **A. Deploy master tip** | Mentor + both fixes | Mentor (YELLOW) | none | yes, automatic | rate-limited | redeploy `c405b49` | full app |
| **B. Branch, only `9ff021b`** | that fix | none | none | **preview only — not production** | n/a | n/a | none |
| **C. Branch, fixes only** | both fixes | none | none | **preview only — not production** | n/a | n/a | none |
| **D. Mentor separately** | Mentor | — | Mentor removed from master first | via repointed branch | no | revert | Mentor |
| **E. Redeploy existing** | `c405b49` (already live) | none | none | yes | yes, pointless | n/a | none |
| **F. Wait for reset** | nothing until triggered | — | none | yes | **yes** | redeploy | none |
| **G. Owner dashboard deploy** | owner's target | depends | none | yes | limited budget | redeploy | target |
| **H. No deploy** | nothing | — | none | n/a | **yes** | n/a | none — image fix already effective (§9) |

**A executed itself.** B and C would only ever have produced a preview URL.

## 6. do_logos Release Status — **GREEN and LIVE**

`9ff021b` verified: real-stage regression fails on the pre-fix parent with `program_image was destroyed by
do_logos`, `official_banner was destroyed by do_logos`, `ID 14 shape reoccurred`, `clear-only run silently
discarded its mutation`; 16/16 pass post-fix; 893 passed / 1 skipped across 27 related suites; CI green.
**Now deployed and serving in production** (`a1f214b` includes it).

## 7. Ingestion Release Status — **GREEN and LIVE, with the caveat standing**

`3bf92b6` addresses explicit-null ingestion overwriting a stored image; 20/20
`test_ingestion_image_preservation.py`; CI green; **now deployed**. Caveat unchanged: I verified its tests
and technical merits but did **not** review its diff line-by-line.

## 8. Mentor M1 / M2 Risk — **both still open, now in production**

Re-checked at the deployed tip `a1f214b`:

**M1 — CONFIRMED LIVE.** `@router.get("/overview")` / `def read_overview() -> dict:` still carries **no
`Depends(require_user)`**, while the module docstring still asserts "Both require a session… There is no
public mentor route." Production returns **200** with exactly
`assistance_available, intents, max_message_length, redirects, supported_intents`.
**Classification: documentation/test mismatch and acceptable static public metadata — NOT a security
blocker.** No `user`, `email`, `applications` or `profile` key is exposed. The false invariant is
nonetheless now a live, untested claim in production.

**M2 — NOT FIXED.** At `a1f214b`: `ScholarshipFacts.official_source_url` = **True**,
`ApplicationFacts.official_source_url` = **False**; `scholarship_evidence` sets `source_url` = **True**,
`application_evidence` = **False**, `student_evidence` = **False**. `c3aefad` touched `evidence.py`
substantially but did not thread the field through.
Affected: any answer grounded on an application — `application.state`, `deadline`, `progress`,
`next_open_task` — i.e. a deadline claim can be `verification: "Verified"` with a `scholarship_id` and
**no source URL**.
**Classification: UX / trust limitation, non-blocking.** The claim is grounded in ScholarZone's own
verified catalogue, not invented, and the UI links to the record.

## 9. Scheduled Maintenance Relationship — unchanged and still decisive

PROVEN: `verification-cron.yml` uses `actions/checkout@v4` with **no `ref:`** → the worker checks out
**master HEAD at run time**. No workflow deploys to Vercel, and the served app **cannot** run maintenance
(APScheduler intentionally not started in production; "the schema is owned by the GitHub Actions
maintenance pipeline").

Therefore **the Vercel revision never controlled the maintenance worker.** Both image fixes were already
effective for the only component that clears images *before* the deploy happened, and are now effective in
the served app as well. I could not verify the authenticated `/mentor/message` path in production without
creating an account, which would be a production write — so §8 rests on code inspection at the deployed sha.

## 10. Next Cron Risk

| question | answer |
|---|---|
| Nominal window | 12:07 UTC |
| Can infrastructure allow it? | **Yes** — GitHub Actions is independent of Vercel's rate limit |
| Will it use master HEAD? | **Yes** — now `a1f214b` |
| Does master contain both image fixes? | **Yes** |
| Image risk from the (now closed) stale revision | **None** — revision advanced, and it never controlled the worker |
| Residual risks | `maintenance_runs` id **250** still stale `status='running'`; `db-state-check.yml` and `controlled-image-repair.yml` remain outside the maintenance concurrency group, so a concurrent mutating script could still race a sweep |

**Nothing was dispatched or simulated.**

## 11. Safe Deployment Candidates — going forward

1. **Nothing further is required for the image fixes.** They are live in both the served app and the
   maintenance worker.
2. **Prevent recurrence:** the rate limit was consumed by ~20 deployments in ~50 minutes across two
   projects. Batch pushes, or reduce deploy frequency. The limit, not a bug, is the constraint.
3. **Fix `deploy.yml`'s cancellation race** at leisure: `cancel-in-progress: true` abandons the previous
   commit's verification on every push, destroying verification signal exactly when pushes are frequent.
4. **If Mentor must be held back next time**, the only mechanism is a release branch
   (`c405b49` + cherry-pick `9ff021b` + cherry-pick `3bf92b6`) with the Vercel **production branch**
   repointed at it — a dashboard change, not a git change, and no master rewrite is required.

## 12. Owner Actions Required

1. **Decide whether `a1f214b` stays.** The Mentor shipped without the intended gate, including six
   corrections (`c3aefad`) that **no one in this audit verified**. Rollback is a dashboard redeploy of
   `c405b49`.
2. **Review `c3aefad`** — it is the only unreviewed code now in production.
3. **Close M1:** either add `Depends(require_user)` to `/mentor/overview`, or correct the docstring and
   add a test asserting the intended contract. It is currently a false security claim in production.
4. **Close M2:** thread `official_source_url` into `ApplicationFacts` and set it in
   `application_evidence()`. Non-blocking, but it should not ship silently.
5. **Reduce deploy pressure** to avoid re-triggering the build rate limit.
6. **Fix `deploy.yml` `cancel-in-progress`** so verifications are not cancelled by later pushes.
7. **Clear `maintenance_runs` id 250** (stale `status='running'`) via the normal operational path.
8. **Put `db-state-check.yml` and `controlled-image-repair.yml` in the maintenance concurrency group** so
   future post-deploy observations are attributable.
9. **Do not "fix" the sibling `AttributeError`** without also switching the predicate to
   `ACCEPTED_IMAGE_KINDS` — arming trap, per `IMAGE_SIBLING_PATH_AUDIT_FINAL.md`.

## 13. Final Recommendation

The infrastructure question is answered: the block was a **Vercel build rate limit**, it reset on its own,
and the automatic pipeline then released the tip. Nothing in the repository caused it and nothing in the
repository could have prevented it except not pushing.

The important correction from this audit is §9: **the deployment block was never on the critical path for
image safety.** The maintenance worker runs from master HEAD, so the `do_logos` fix was protecting images
before Vercel deployed anything. My earlier framing that production was "exposed" was right about the
revision and wrong about the consequence.

Recommended now: **verify and accept, or roll back to `c405b49`** — that is a judgement about shipping
`c3aefad` unreviewed, and it belongs to the owner. Then close M1 and M2 deliberately rather than
silently, and reduce deploy pressure so the next release is a decision rather than a side effect.

**Final classification: OWNER_ACTION_REQUIRED**