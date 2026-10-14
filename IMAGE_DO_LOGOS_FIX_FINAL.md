# IMAGE DO_LOGOS FIX — PHASE 7B FINAL

**Scope note, stated first because it changes what this phase actually was.** By the time I began, the
requested fix **already existed on `master`**, committed by another actor as `9ff021b` *"fix: do_logos
destroys images the pipeline accepted"*. I did **not** duplicate or re-author it. This phase therefore
became: **verify the existing fix is correct and complete, prove it with real-stage regression,
identify what it does not cover, and attempt deployment.** Two findings dominate — a **sibling defect of
the identical class that the fix does not cover**, and a **deployment pipeline that has been broken
since 09:18 UTC**, so the fix is committed but **not live**.

**Constraints honoured:** no repair, no restore, no image stage, no maintenance dispatch, no scheduler
change, no audit-instrumentation change, no touch of ids 14/130/554/557/564/569/603/618, no Wave 1–3
data. All production inspection was read-only. `do_purge`, ingestion and verification semantics were not
modified by me.

---

## 1. Run 250 Status — **B. cancelled/dead but stale**

`status='running'` alone was treated as a single data point, never as proof of activity.

| source | evidence |
|---|---|
| DB row (read-only probe, run `37195147331`) | `run_id=650fb6ea619047ab`, `started_at=09:13:57.315058`, **`finished_at=None`**, **`status=running`**, `worker=maintenance/1.1+runnervm8df0l+attempt1`, `dry_run=False`, `duration_ms=None`, `error_summary=None`, **`stages=[]`**, **`counts={}`** |
| GitHub Actions | run `37191466917`, `status=completed`, **`conclusion=cancelled`**, created 09:13:38, **updated 09:31:28** |
| Successor runs | **none** — no `maintenance_runs` row with `id > 250`; no `verification-cron.yml` run created after 09:13:38 |
| Production audit activity | **20** audit rows after 09:13:57, latest **09:29:44.731361**, `max_id=91`, `total=91` |

**Reasoning.** A genuinely executing worker populates `stages` as it goes — every completed run I read
carries a full per-stage array. After ~68 minutes this row still has `stages=[]` and `counts={}`, which
is the signature of a process that created its DB row and died before any stage reported. The hosting
workflow is conclusively `cancelled`/`completed` and nothing has superseded it. The 20 audit writes in
the window are **not** consistent with this run: their labels are `unknown` and `maintenance.images`,
and **no `maintenance.logos` or `maintenance.purge` write exists anywhere after 09:01:47**, so a
`--stage all` worker running inside that window would be expected to have produced them.

**Actions taken: none.** I did not edit the row and did not terminate anything — no approved operational
control authorises that, and cancellation is already complete at the GitHub layer.

**Residual uncertainty — PLAUSIBLE BUT UNPROVEN:** I cannot *prove* zero stages executed, because a
process killed mid-flight cannot flush its stage list. The 20 in-window writes are individually
attributable to other writers, but I record this as a **deployment/observation confounder** (§6 of the
Phase 6.2 report) rather than closing it out.

## 2. Proven Production Event — **OBSERVED FACT / PROVEN**

Id 14, single transaction, from `scholarship_image_audit`:

| audit_id | time | txn | writer_context | transition |
|---|---|---|---|---|
| 3 | 08:35:23.391597 | 281733 | `unknown` | `image_url` NULL → ETHZ URL (+kind, verified_at) |
| **5** | **08:38:28.768558** | **281764** | **`maintenance.logos`** | **ETHZ URL → NULL (+kind, verified_at, source_url, source_type)** |
| 68 | 09:09:52.755900 | 282716 | `unknown` | NULL → ETHZ URL (the controlled repair) |

The same transaction cleared ids **557, 558, 564, 569, 575**. Id 14's replacement was
`image_kind='program_image'` — an accepted kind that is not a logo identity mark.

## 3. Exact do_logos Defect — **PROVEN**

Pre-fix logic (`scholarzone_maintenance.py`, `do_logos`):

```python
if (row.image_kind or "") in LOGO_IDENTITY_KINDS:   # only identity marks protected
    skipped_existing += 1
else:
    row.image_url = None; ... row.image_kind = None; ...   # destroyed
```

Cleared whenever `image_url IS NOT NULL` **and** an override matched the host **and**
`image_kind NOT IN LOGO_IDENTITY_KINDS`. `ACCEPTED_IMAGE_KINDS` was never consulted, so an
`ACCEPTED_IMAGE_KINDS` member that is not an identity mark — `program_image`, `official_banner` — was
deleted purely for not being a logo, with no re-evaluation and no history row.

**A second, unfixed sibling of the same class — OBSERVED FACT.** `image_discovery_orchestrator.py`
retains:

```python
def _is_non_logo_stored(session, scholarship_id) -> bool:
    return (scholarship.image_kind or "") not in LOGO_IDENTITY_KINDS   # still LOGO-only
```

reachable via the worker's `--logo-only` flag → `do_images` (`logo_only=args.logo_only`) → orchestrator
`run()` line 658 → `_clear_stored_image(session, scholarship_id)`. **Running `--stage images
--logo-only` can still destroy an accepted `program_image`.** This is outside `do_logos`, was not in
this commit, and I did not change it (§17).

## 4. Commit Semantics — **PROVEN, and a second real defect fixed**

Pre-fix: `if attached and not args.dry_run: session.commit()`. A run whose only mutation was a
**clear** incremented neither counter, reached no commit, and silently discarded the destructive edit on
close. Whether a deletion persisted depended on whether that same run happened to attach something.

All four mutation branches, verified by reading the current code and by real execution:

| branch | mutation | counter | persists? |
|---|---|---|---|
| image present, kind **in** `ACCEPTED_IMAGE_KINDS` | **none** | `skipped_existing` | n/a — no false mutation |
| image present, kind **not** accepted | clears 8 fields | `cleared` | yes — `cleared += 1` |
| no image, `dry_run` | none | `attached` | no — `session.rollback()` |
| no image, live | attaches logo fields | `attached` | yes |

Commit gate is now `if (attached or cleared) and not args.dry_run:` — an explicit mutated-state, not an
attachment-state. `dry_run` still rolls back. **`--reset`-style false negatives do not occur here.**

## 5. Minimal Fix — **PROVEN correct and complete for `do_logos`**

`9ff021b` — two files, `+291 / −10`, no application file but the worker touched:

1. **Predicate** → `if (row.image_kind or "") in ACCEPTED_IMAGE_KINDS: skipped_existing += 1`.
   Acceptance decided **by kind**, not by `image_verified_at` — the commit's reasoning is correct: an
   accepted record can have its timestamp cleared by an unrelated path, so timestamp-gating would
   reopen the hole. This satisfies the requirement that `image_verified_at` must not be the sole
   protection signal, and `test_verified_non_accepted_image_does_not_survive_on_timestamp_alone` pins
   it.
2. **Commit semantics** → `cleared` counter + `(attached or cleared)` gate, plus
   `cleared_unaccepted` added to the stage detail for observability.
3. Incidental and correct: removed an unused `ACCEPTED_IMAGE_KINDS` import from `do_stats`, which never
   reads it.

Against every stated constraint: no hardcoded ids, no public-visibility change, no verification-semantics
change, `do_purge` untouched, ingestion untouched, scheduler and audit schema untouched.

**Not covered:** the `_is_non_logo_stored` sibling (§3).

## 6. Before / After Behavior Matrix

| stored state | pre-fix `do_logos` | post-fix `do_logos` |
|---|---|---|
| `program_image` | **DESTROYED** | **preserved** (`skipped_existing`) |
| `official_banner` | **DESTROYED** | **preserved** |
| `official_logo` / `official_government` / `official_university` | preserved | preserved |
| accepted kind, `image_verified_at` NULL | **DESTROYED** | **preserved** |
| non-accepted kind (e.g. `None`) | cleared | cleared (policy permits) |
| non-accepted kind + `image_verified_at` set | cleared (correctly) | cleared (correctly) |
| no image + override match | logo attached | logo attached |
| clear-only run | **mutation silently discarded** | mutation persists |
| `--dry-run` | nothing persisted | nothing persisted |
| no override match | untouched | untouched |

## 7. Real Execution Regression Tests — **PROVEN**

`backend/tests/test_do_logos_accepted_image.py`, **16 tests, all passing**. They import
`app.jobs.scholarzone_maintenance` and drive the **real stage** through `job.main([...])`; the predicate
is not re-implemented in the test.

All 14 required scenarios are covered: `test_accepted_kind_survives` is parametrised over
`ACCEPTED_IMAGE_KINDS` (program_image, official_banner, official_logo, official_government,
official_university); `test_accepted_kind_without_timestamp_survives`;
`test_non_accepted_image_is_still_cleared`; `test_genuine_logo_attachment_still_works`;
`test_clear_only_run_commits_its_clear`; `test_dry_run_never_persists`;
`test_no_op_run_changes_nothing`; `test_metadata_stays_coherent`;
`test_id14_failure_shape_is_prevented`; `test_real_stage_executes_without_runtime_error`. Two extra
tests beyond the required list: `test_verified_non_accepted_image_does_not_survive_on_timestamp_alone`
and `test_accepted_kinds_are_the_canonical_set`.

**Step 4 — the previous failure is preserved and demonstrated.** I ran this same file against the
pre-fix parent `5416914`: **5 failed, 11 passed**, with exactly the defect assertions:

```
AssertionError: program_image was destroyed by do_logos
AssertionError: official_banner was destroyed by do_logos
AssertionError: ID 14 shape reoccurred
AssertionError: clear-only run silently discarded its mutation
assert None is not None            (accepted kind without timestamp)
```

So both the predicate defect and the commit-semantics defect are reproduced by real-stage execution and
are genuine regression tests, not tautologies.

## 8. Full Relevant Test Results

| gate | result |
|---|---|
| `test_do_logos_accepted_image.py` (post-fix) | **16 passed** |
| same file, pre-fix parent `5416914` | **5 failed, 11 passed** — defects reproduced |
| 27 image / logo / maintenance / GC / schema / import suites | **893 passed, 1 skipped**, 0 failed (326 s) |
| Full backend suite (`pytest tests/ -x`) | **passed via CI** for `9ff021b` and `3bf92b6` |
| `py_compile` on all touched files | clean |

**Baseline failures, stated honestly:** none encountered in this phase. The 8 pre-existing
`test_neon_migration.py` failures documented in Phase 5 depend on an untracked `backend/migration_export.sql`
that does not exist in the repository and are unrelated to images; they did not appear in the 27-file
set and did not block CI for either fix commit. No test was weakened, skipped or deleted.

**Invariants verified unchanged (Step 5):** `do_purge` semantics untouched (its
`ACCEPTED_IMAGE_KINDS` logic and `test_purge_image_safety.py` pass unchanged); ingestion untouched;
verification semantics untouched; no accepted kind is cleared merely because `logo_only` runs; image
`image_url`/`image_kind` pairing stays coherent; `image_kind` is still nulled together with `image_url`
so no kind-without-image residue is created.

## 9. Production Deployment — **NOT COMPLETED (BLOCKED)**

This is the phase's failure and I am not dressing it up.

| fact | evidence |
|---|---|
| Fix is on master | `9ff021b`, ancestor of master tip `3bf92b6` |
| CI green | `9ff021b` success, `3bf92b6` success |
| **Live revision** | **`c405b49bb8b9`** — the commit *before* both fixes |
| Last successful deploy | run `37191742167` at **09:18:43Z** for `c405b49` |
| Every deploy since | `37194569424` cancelled, `37194580458` skipped, `37194690571` cancelled, `37194716581` cancelled, `37194902161` **failure**, `37195598406` **failure (mine)** |

The verifier is not a build; it polls the production URL for 40×15 s waiting for the revision to change:

```
Health HTTP response code: 200
Healthy but serving revision c405b49bb8b9, expected 3bf92b625135.
... (40 of 40 attempts) ...
::error::Timed out waiting for the expected build to go live.
```

The application was **healthy throughout on the old revision**. So the blocker is **Vercel not
promoting a build**, not a code or test failure — an infrastructure condition outside this task's tools.
Contributing factor: `deploy.yml` uses `concurrency: production-deployment-verification` with
`cancel-in-progress: true`, so each new push **cancels the previous verification**, and three
verifications for `9ff021b` were cancelled before one could finish.

I made one in-scope deployment attempt (run `37195598406`) and it failed identically. I did not
attempt to repair the deploy pipeline, which is out of scope.

**Consequence: production still runs the defective `do_logos`.** It is currently low-exposure —
no `scheduled maintenance` run has executed since 09:13:38 — but the exposure returns on the next cron
tick. I am **not** claiming this phase completed its deployment step.

## 10. Production Verification (read-only, against live `c405b49`)

| check | value |
|---|---|
| `/api/health` | `ok`, revision `c405b49bb8b9` |
| `stats.total` / `verified_active` / `with_image` | 358 / 358 / 358 |
| subsets exceeding total | **none** |
| directory total | **358** |
| Match total / partition | **358 / 358** |
| Count contract (`/api/v2/counts/contract`) | 200 |
| storage | **451** (unchanged) |
| public count movement caused by this work | **none** — 358 at 09:53 census and 358 now |

Endpoint-state notes, not treated as defects: `/api/admin/verification` → 404,
`/api/student/dashboard` → 404, `/api/applications` → 401 at the paths I probed. I did not attempt to
distinguish "wrong path" from "gated", and I make no claim about those surfaces.

Targets untouched, as required: **14** still `program_image` / verified 09:09:52; **130**
`source_blocked`, no image; **554** `no_official_image`, no image; I6 set still {557, 564, 569, 603, 618}.

## 11. Image Invariants

| invariant | status |
|---|---|
| accepted kinds never cleared merely because a logos sweep ran | **holds post-fix for `do_logos`; BROKEN on `--stage images --logo-only`** |
| `I6_image_without_kind` satisfied | **NOT satisfied** — 5 records (557, 564, 569, 603, 618) |
| `image_url` / `image_kind` pairing coherent | holds for all cleared records; the 5 I6 records have `image_url` with NULL kind |
| `do_purge` semantics | unchanged |
| ingestion semantics | unchanged by me; separately fixed in `3bf92b6`, undeployed |
| verification semantics | unchanged |
| public visibility | unchanged (358) |
| storage | unchanged (451) |

## 12. Why Natural Cron Recurrence Was Not Required — **PROVEN**

The fix does not rest on waiting for the next scheduled sweep, because the defect was already
demonstrable twice over without one:

1. **Production audit** — the exact transition occurred on id 14 (audit_id 5, txn 281764).
2. **Real-stage reproduction** — the committed test suite fails on the pre-fix parent with
   `program_image was destroyed by do_logos` and `ID 14 shape reoccurred`, driving the real
   `do_logos` through `job.main()`.

Reproducing a deterministic predicate defect in a real-stage test is strictly stronger evidence than
awaiting a 12-hourly cron tick, and it does not mutate production. As instructed, I did **not** claim
Phase 6 passed, and no natural post-repair recurrence has been observed.

## 13. Why October 3 Root Cause Remains UNKNOWN — **UNKNOWN**

The 2026-10-03 regression predates the audit table, so no audit row covers it, and
`scholarship_verification_history` records only image *set* events (`None → URL`) and never the clears —
which is precisely why the original writer went untraced. Nothing in this phase produced evidence about
October 3. The commit message in `9ff021b` cites the **October 4** id-14 event as its evidence and makes
no October 3 claim, which is the correct boundary. I am not extending the fix backwards to explain a
historical incident it was not diagnosed against.

## 14. Remaining I6 Unknown-Writer Investigation — **UNKNOWN, open**

Five records violate `I6_image_without_kind`; three are public (557, 564, 603).

| id | written at | writer_context |
|---|---|---|
| 564 | 09:19:54 | `unknown` |
| 569 | 09:20:53 | `unknown` |
| 557 | 09:21:22 | `unknown` |
| 603 | 09:24:18 | `unknown` |
| 618 | 09:25:52 | `unknown` |

Each wrote `image_url` + `image_verified_at` while leaving `image_kind` NULL. The replacement images are
also poor (557's is `down-arrow.svg`; 569's alt text is *"Etudiant qui effectue une recherche - canva
copyright"*). Per the rule, `writer_context = unknown` keeps the root cause **UNKNOWN**; I am **not**
attributing it to `87ad84c` or to any other commit. Not repaired, per instruction. This is a **live
defect that the `do_logos` fix does not address** — a writer is creating kind-less images every few
minutes and none of it is going through a labelled path.

## 15. Remaining Ingestion Defect — **fixed on master, UNVERIFIED by me, NOT live**

Master now carries `3bf92b6` *"fix: stop ingestion from deleting a stored image on a null refresh"*,
which addresses the ingestion-side image-destruction path (an upsert refreshing a row with a NULL image
and thereby clearing a stored one). It is a **separate commit** from `9ff021b`, it is **not deployed**,
and I have **not** independently reviewed its diff or tests — that is outside this phase's scope and I
will not vouch for it unverified. Its `writer_context` relationship to the `maintenance.add` clearing of
id 130 (§10 of the Phase 6.2 report) remains **UNKNOWN**; `maintenance.add`'s image write is guarded by
`not row.image_url` and cannot clear, so that clearing path is still unattributed.

## 16. Remaining Audit Limitations — unchanged from Phase 6.2

- The `scholarships` trigger is `AFTER UPDATE` **only**: `INSERT`, `DELETE` and `TRUNCATE` are unaudited.
- Rolled-back mutations leave **no** audit row (same transaction).
- `writer_context` is a self-asserted, forgeable, transaction-local `set_config` value.
- The owner escape is real: `neondb_owner` owns the table and holds `TRIGGER`; `cloud_admin` is a
  superuser, so guards can be dropped and rows rewritten. `DELETE`/`TRUNCATE` *are* trigger-blocked —
  my earlier claim to the contrary was **DISPROVEN** in Phase 6.2.
- Therefore **"no audit row ⇒ no mutation" remains invalid** and I do not use it.

## 17. Recommended Next Action

**Ordered, and none of it is a data mutation:**

1. **Restore the deployment pipeline** — this is now the highest-value action in the project. Every
   commit since 09:18:43 is undeployed, so `do_logos` **and** the ingestion fix are both absent from
   production. Check Vercel build status for `3bf92b6`; consider setting
   `cancel-in-progress: false` on the `production-deployment-verification` group so a newer push stops
   cancelling the verification that would have promoted the previous one.
2. **Confirm the fix live**, then verify read-only that `stats`/`Match`/`directory` remain 358 and storage
   451.
3. **Fix the sibling `_is_non_logo_stored` predicate** to use `ACCEPTED_IMAGE_KINDS`, mirroring the
   `do_logos` change. Until then **`--stage images --logo-only` remains a live path that can destroy an
   accepted `program_image`** — this is the same proven defect class, one function away from the fix.
4. **Decide the logos policy explicitly**: should a logos sweep ever remove an accepted non-logo image?
   Post-fix `do_logos` says no. That is a policy decision and belongs to an owner, not to a test.
5. **Investigate the `unknown` I6 writer** (§14) — it is actively writing invalid state and is
   unattributed; it will keep producing I6 records until found.
6. **Close out `maintenance_runs` id 250** through the normal operational path (an operator decision —
   I did not edit it), and clear the stale `status='running'`.
7. Add an advisory lock keyed on scholarship id in `ImageCoverageRunner` so duplicate evaluation is
   impossible regardless of workflow topology.
8. Do **not** restore the 18 purged images until §14 and §15 are resolved — restoration evidence is
   already contaminated by later deliberate re-evaluations.

---

### Classification summary

**PROVEN:** the `do_logos` predicate defect; the commit-semantics defect; both are fixed and covered by
real-stage tests that fail on the pre-fix parent; all 14 required behaviours; `do_purge`/ingestion/
verification/visibility unchanged; run 250 is a stale row from a cancelled workflow.
**DISPROVEN:** that the guard is UPDATE-only; that "audit boundary safe: NO" follows from owner
privileges; that `do_add` could have cleared id 130; that id 14 holding its image proves `logos` is safe.
**OBSERVED FACT:** production is serving `c405b49`; five I6 records written by an `unknown` writer.
**PLAUSIBLE BUT UNPROVEN:** that run 250 executed no stage at all.
**UNKNOWN:** October 3 root cause; the `unknown` writer; the id-130 clearing path; whether run 250 ran any
stage.
**BLOCKED:** Phase 7B deployment — Vercel has not promoted a build since 09:18:43Z.