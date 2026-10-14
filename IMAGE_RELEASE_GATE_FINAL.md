# IMAGE RELEASE GATE — FINAL

**This was a release-readiness audit. Nothing was deployed. No maintenance was dispatched, no image stage
was run, no image was repaired or restored, and no production record was modified.**

---

## 1. Current Production Revision

| item | value |
|---|---|
| **live revision** | **`c405b49bb8b9`** (`/api/health` → `status: ok`) |
| last successful deploy | run `37191742167`, **09:18:43Z** |
| deploys attempted since | 6 — 3 cancelled, 1 skipped, **2 failed by timeout** |
| `stats.total` / `verified_active` | **358 / 358** |
| subsets exceeding total | **none** |
| directory total | **358** |
| Match total / partition | **358 / 358** |
| Count contract | **200** |
| storage | **451** (unchanged) |
| last maintenance run | `37191466917`, 09:13:38Z, `workflow_dispatch`, **cancelled** |

**PROVEN:** production is serving the commit *immediately before* all three undeployed commits, and has
been since 09:18Z — roughly 1 h 45 m. Public and storage invariants are stable and show no movement
caused by this audit.

## 2. Current Master Commit Graph

`origin/master` = **`3bf92b6`**. Production `c405b49` **is an ancestor** of master (`exit=0`), so the
tip is fast-forwardable. Exactly **three** commits separate them, linear, no merges:

```
* 3bf92b6  fix: stop ingestion from deleting a stored image on a null refresh
* 9ff021b  fix: do_logos destroys images the pipeline accepted
* 5416914  feat: add GROUNDed AI Mentor 1.0 as a grounded, deterministic advisor
* c405b49  (production, origin/application-workspace) Merge ... into application-workspace
```

| commit | size | files |
|---|---|---|
| `5416914` Mentor | **+6108 / −8** | **25** — backend routers/services/schemas, `main.py`, `application_workspace.py`, 7 frontend files incl. `App.jsx` and `Navigation.jsx`, 1 audit doc, 6 test files |
| `9ff021b` do_logos | +291 / −10 | **2** — `scholarzone_maintenance.py`, new test file |
| `3bf92b6` ingestion | +398 / −2 | **2** — `scholarship_ingestion.py`, new test file |

**PROVEN:** no unrelated image-track commit is in the deployment tip. The two image fixes are
single-file, tightly scoped; the Mentor is the only broad change.

## 3. Mentor Release Verification

No peer had verified it (board shows only record-verification subagents), so I performed the local
verification. **Real** backend, **real** DB, **real** HTTP, **real** browser (Chrome via Playwright).

| gate item | result | evidence |
|---|---|---|
| real local backend | **PASS** | `uvicorn app.main:app` on 127.0.0.1:8000, `Application startup complete` |
| real local DB | **PASS** | SQLite `mentor_local.db`, 24 tables, 63 seeded scholarships, 63/63 with `official_source_url` |
| real HTTP | **PASS** | 30+ assertions across two gate scripts |
| real browser | **PASS** | page renders, answer renders, 0 unexpected console errors |
| register / login | **PASS** | 200; session reflects the account |
| Mentor open | **PASS** | `/mentor` renders composer + 5 intent buttons |
| grounded answer | **PASS** | "Decide on Delft Monthly Scholarship is the highest-priority thing waiting on you." |
| evidence | **PARTIAL** | verified items with catalogue attribution + "Open this scholarship" links, but see finding M2 |
| next action | **PASS** | "Closing soon — 11 days remain on a published deadline" |
| application context | **PASS** | application created; application-scoped evidence returned |
| deadline handling | **PASS** | "46 days left"; "About 11 days left, based on a month-precision date"; **refuses** to invent a day-precision date |
| logout protection | **PASS** | HTTP **and** browser: logout 204 → session null → `/mentor/message` **401** |
| user isolation | **PASS** | user B sees **0** of A's applications; B's answer contains no A data |
| zero console errors | **PASS** | the only 2 errors were my own deliberate 401 negative probes |
| responsive | **PASS** | 390×844: **0 px horizontal overflow**, composer 301×88, submit 301×44 |
| frontend build | **PASS** | `vite build` ✓ 342 ms |
| frontend lint | **PASS** | eslint **0 errors**, 1 pre-existing `HomePage.jsx` warning unrelated to Mentor |
| unit suites | **PASS** | frontend vitest **163 passed** (9 files); backend `test_mentor.py` **69 passed** |

**M1 — PROVEN contract mismatch (low impact).** The module docstring asserts "**Both require a session.**
There is no public mentor route…", but `GET /mentor/overview` (line 128) carries **no
`Depends(require_user)`**; it answers **200 anonymously**. Impact is low — the payload is static
vocabulary (`intents`, `redirects`, `max_message_length`, `supported_intents`) with **no user data**
(verified). It is a false documented security invariant, and no test covers it.

**M2 — PROVEN provenance gap.** `ScholarshipFacts` has `official_source_url`; **`ApplicationFacts` does
not**. Therefore `application_evidence()` *structurally cannot* emit a `source_url`. In practice a
deadline claim is labelled `verification: Verified` with a `scholarship_id` but **no official source
link** — even though all 63 records have one. The UI compensates with an internal
"Open this scholarship" link, so the user can reach the record but not the official page directly.

**M3 — OBSERVED FACT.** Nav renders `Applications: undefined` when the count is absent.

**M4 — contamination.** The Playwright profile arrived holding a session for
`mentor-e2e-a@example.com` (id 1, created **10:27:57Z**) — an account I did not create, present in the
same local SQLite file. **Another actor is running Mentor E2E against this same local backend/DB.** I
re-ran the auth legs with an account I control (`gate.audit@example.test`) so my conclusions do not rest
on their data, but their concurrent writes are in the same DB.

Mentor is on the NO-TOUCH list, so **I did not fix M1–M3.**

## 4. do_logos Verification (`9ff021b`) — **GREEN, unmodified**

I did not modify it. Verified by execution, in a throwaway worktree:

| check | result |
|---|---|
| commit content | 2 files, +291/−10, no ID hardcoding, no visibility/verification/`do_purge`/ingestion change |
| real `do_logos` execution | drives `job.main([...])`; predicate not re-implemented in tests |
| accepted image preservation | `program_image`, `official_banner`, `official_logo`, `official_government`, `official_university` all survive — **16 passed** |
| accepted kind without `image_verified_at` | survives |
| clear-only commit behaviour | persists (was the silent-discard defect) |
| no-op behaviour | no destructive mutation |
| dry-run behaviour | nothing persisted |
| **pre-fix regression proof** | same file on parent `5416914`: **5 failed / 11 passed** — `program_image was destroyed by do_logos`, `official_banner was destroyed by do_logos`, `ID 14 shape reoccurred`, `clear-only run silently discarded its mutation` |
| related suites | **893 passed, 1 skipped** across 27 image/logo/maintenance/GC files |
| full backend suite | green via CI for `9ff021b` |

The fix decides acceptance **by kind**, with `image_verified_at` as corroboration only — correct, and
pinned by a test that a timestamp alone must not rescue an unaccepted image.

## 5. Sibling Path Audit — full detail in `IMAGE_SIBLING_PATH_AUDIT_FINAL.md`

**DISPROVEN — my own Phase 7B claim.** I previously said `--stage images --logo-only` "can still destroy
an accepted `program_image`". Real execution disproved it:

- `_is_non_logo_stored` exists **only** as a module-level function (line 229); **no class has that
  method**; the sole call site (line 658) uses `self.`.
- A real `logo_only` run reaching that line raises
  `AttributeError: 'ImageDiscoveryOrchestrator' object has no attribute '_is_non_logo_stored'`, which the
  surrounding `except Exception` converts to `status=ERROR` + `session.rollback()`.
- **No stored image is modified** — not `program_image`, not `official_banner`, not unaccepted artwork.
  Verified by 23/23 isolated tests with the real decision/destruction/write code.

The **predicate intent is still wrong** (ignores `ACCEPTED_IMAGE_KINDS`), so this is a live *arming trap*:
fixing only the `AttributeError` would activate a destroyer. A test pins that trap.

Exposure is low: `--logo-only` is a manual `workflow_dispatch` input, never passed by cron.

**Not fixed**, as instructed.

## 6. Deployment Blocker Analysis

**PROVEN: `deploy.yml` cannot deploy anything.** Its name says "Verification". It triggers on
`workflow_run: [ScholarZone CI]` and then only (a) validates two variables exist and (b) polls
`SCHOLARZONE_API_URL` for up to 40×15 s until `/api/health` reports the expected revision. **No workflow
in the repository references the Vercel CLI, `vercel --prod`, or any production deploy step.** CI's ten
jobs (backend-tests, frontend-lint/tests, import-smoke, git-integrity, env-config, schema-compat,
build-and-smoke, preflight) build a Docker image for smoke testing and deploy nothing.

**Therefore the only production deploy path is Vercel's own git integration**, which is outside GitHub
Actions and outside the tools available to me.

**PROVEN: a cancellation race exists, but it is not the blocker.**
`concurrency: {group: production-deployment-verification, cancel-in-progress: true}`. Every push to master
starts a verification that cancels the previous one — which is why `9ff021b` has 3 cancelled
verifications. But the two runs that were actually allowed to execute (`3bf92b6`, at 10:17 and 10:30)
both **timed out** with production healthy on `c405b49` for all 40 attempts. Production never served the
new revision. So the race creates noise; the failure to promote is upstream of it.

| question | answer | classification |
|---|---|---|
| Is Vercel quota the only blocker? | Cannot be established — no Vercel access from here. All I can prove is that **no build was promoted** while the app stayed healthy on the old revision. | **UNKNOWN** |
| Is a manual Vercel deploy possible now? | **Not by me** — no Vercel CLI/token in this environment, and doing it is out of scope for this audit. | **PROVEN not available here** |
| Does verification have a cancellation race? | **Yes** — `cancel-in-progress: true`. | **PROVEN** |
| Can `deploy.yml` falsely cancel a verification? | **Yes** — three verifications for `9ff021b` were cancelled by later pushes before any could complete. | **PROVEN** |
| Can production be safely advanced to master? | Technically yes (fast-forward). Safety is a **release-boundary** judgement — see §8. | see §8 |
| Does master contain unreviewed concurrent work? | **Yes** — `5416914` (Mentor, 25 files) is the only broad change and it carries M1–M3. The two image fixes are narrow and reviewed. | **PROVEN** |

## 7. Production Risk Window

**Next scheduled opportunity: 12:07 UTC** (cron `7 */12 * * *`; now 10:59Z, so ~68 min). Read-only
assessment of what can run against production **as it stands today (old `do_logos`)**:

| question | answer | classification |
|---|---|---|
| Can `logos` run on the next cycle? | **Yes** — `logos` is in `--stage all`, and production still has the pre-`9ff021b` `do_logos`, which deletes an accepted non-logo image whenever a host has a logo override. | **PROVEN** |
| Is there real exposure? | **Bounded.** `do_logos` only touches a record whose host matches a `config/logo_overrides` entry. It cleared 6 records in one historical execution. | **PROVEN** |
| Can `images --logo-only` run? | **Only by deliberate manual dispatch** — it is a workflow input, not a cron argument. And if dispatched today it would **error without writing**, because the branch crashes first. | **PROVEN** |
| Can any active workflow mutate images? | **Yes** — `verification-cron.yml` (schedule), `controlled-image-repair.yml` and `db-state-check.yml` (arbitrary script with production credentials, **no concurrency group**). | **PROVEN** |
| Does a containment already exist? | **Partial and incidental.** No image stage has run since 09:13Z, so there has been no exposure for ~1 h 45 m. But that is *inactivity*, not a control: nothing prevents a dispatch, and the cancelled `maintenance_runs` id **250** is still `status='running'` in the database. | **PROVEN** |

**No containment was created, and nothing was dispatched or cancelled**, per the rules.

## 8. Commit-by-Commit Release Boundary

| commit | verdict | reasoning |
|---|---|---|
| **`9ff021b`** do_logos | **GREEN** | Independently verified. Real-stage regression fails pre-fix with the exact defect assertions and passes post-fix. Fixes both the predicate and the commit-semantics defect. Single source file + test. No visibility, verification, purge, ingestion, scheduler or audit change. |
| **`3bf92b6`** ingestion | **GREEN** | 20/20 `test_ingestion_image_preservation.py` pass; CI green. Single service file + test. **Caveat:** I did **not** independently review its diff line-by-line in this phase — the verdict rests on its own tests plus CI, and it addresses the ingestion-side image destruction class. |
| **`5416914`** Mentor | **YELLOW** | Functionally verified end-to-end and genuinely good: grounded answers, explicit unknowns, honest deadline precision, logout protection, user isolation, 0 console errors, responsive, build and lint clean. **But** it is 6 108 lines across 25 files touching `main.py` and `application_workspace.py`, and it carries **M1** (a false documented security invariant — `/mentor/overview` is public), **M2** (application evidence cannot carry a source URL), **M3** (`Applications: undefined`). None is a data-loss risk; all are unresolved. Also **M4**: it is being actively exercised by another actor against a shared local DB. |

**Nothing is RED.** No commit on master must be withheld for correctness or data-safety reasons.

**Whole-tip judgement: YELLOW, not GREEN.** Not because any commit is unsafe, but because the Mentor is
large and unreviewed at the diff level by anyone, and it carries an unresolved documented-security
mismatch. Shipping `9ff021b` and `3bf92b6` is the highest-value action available; shipping the Mentor
alongside them is a separable decision.

## 9. Wave 1–3 Status

**COMPLETELY BLOCKED. No action taken.** No local SQLite data was applied to Neon; no `add`, `reverify`,
`images`, `logos` or `purge` stage was run for Wave 1–3 purposes; no Wave data was touched. Wave 1–3
remain undeployed and are **not** a precondition for shipping the image fixes — they are a separate
track that must not be bundled into this release.

## 10. Exact Preconditions for Deployment

1. **Restore the deploy path.** Identify why Vercel is not promoting builds for `3bf92b6` (build log,
   project settings, quota). Nothing else matters until production can advance.
2. **Remove the verification cancellation race**, or accept it knowingly: with
   `cancel-in-progress: true`, every push abandons the previous commit's verification. `false` would let
   verifications complete.
3. **Decide the Mentor question explicitly** — ship `9ff021b` + `3bf92b6` alone, or all three. The tip is
   linear and fast-forwardable, so a Mentor-shaped revert or a hold is possible either way.
4. **Clear `maintenance_runs` id 250** (stale `status='running'`) through the normal operational path, so
   a stuck run cannot be mistaken for activity during post-deploy observation.
5. **Close the concurrent-writer hole** before trusting any post-deploy observation:
   `db-state-check.yml` and `controlled-image-repair.yml` have **no concurrency group** and can execute
   mutating scripts against production in parallel with a maintenance sweep. Without this, a post-deploy
   cycle cannot be attributed.
6. **Resolve or formally accept M1–M3** for the Mentor.
7. **Keep the sibling path closed** — do **not** dispatch `--stage images --logo-only`, and do not "fix"
   the `AttributeError` without also fixing the predicate (arming trap, §5).

## 11. Safest Next Action

**Do not deploy yet.** In order:

1. Diagnose the Vercel non-promotion for `3bf92b6` — that is the single blocker standing between the
   current master and a live `do_logos` fix.
2. Once promotion works, deploy and verify read-only: revision, `stats`/directory/Match staying at 358,
   storage 451, and that no subset exceeds total.
3. Only then consider the Mentor, and treat M1 as the item to fix first — a documented security
   invariant that does not hold is the kind of thing that becomes a finding later.

**Contained, low-regret, and reversible:** the two image fixes are the safest thing in the repository
right now, and production is currently the *only* place still running the defective `do_logos`.

## 12. Final Decision

# BLOCKED — INFRASTRUCTURE

**Not** BLOCKED — CODE: every commit on master is either GREEN or YELLOW with no correctness or
data-safety blocker, and the one commit this phase was asked to fix is verified GREEN.

**Not** BLOCKED — DATA: public 358 / storage 451 / Match 358 stable, no subset inflation, no orphaned
state, no repair required.

**Not** BLOCKED — COORDINATION: the one unresolved concurrency hazard (`db-state-check.yml` and
`controlled-image-repair.yml` outside the maintenance concurrency group) is a *precondition for
attributing a post-deploy cycle*, not a blocker to deploying verified code.

**BLOCKED — INFRASTRUCTURE:** production has been pinned to `c405b49` since 09:18Z because no build is
being promoted to the production alias, and the only deploy mechanism (Vercel's git integration) is
outside both the repository and the tooling available here. `deploy.yml` verifies; it cannot deploy.

Secondary, and worth stating plainly: while this persists, production keeps the **defective** `do_logos`,
which the evidence proves will delete an accepted non-logo image whenever a host matches a logo override.