# IMAGE_REVERSION_PHASE6_FINAL.md

**Mission:** determine whether the live `maintenance.logos` path reverts scholarship ID 14 after its controlled canonical repair.

**Status at time of writing: OBSERVATION WINDOW NOT YET OPEN.**

The natural scheduled maintenance cycle fires at `7 */12 * * *` — 00:07 and 12:07 UTC. This
report was generated at **09:16 UTC**, roughly 2 h 51 min before the next scheduled run.

No scheduled cycle has executed since the Phase 0–5 controlled repair at 09:09:52–09:10:08 UTC.
Therefore the post-cycle determination is **PENDING**, and this document records the pre-window
evidence plus the exact procedure that will finalise it. No result has been inferred, simulated or
anticipated. A wakeup is scheduled for 12:20 UTC, after the cycle completes.

---

## 0. Pre-Window Readiness Report (updated 09:28 UTC)

**CLASSIFICATION C — PHASE 6 STILL NOT OBSERVED.**

Current time 09:28 UTC. Nominal cron 12:07 UTC. **Zero `event=schedule` runs have occurred since the
controlled repair at 09:09:52 UTC.** Per the Phase 6 first rule, this report stops at a truthful
pre-window readiness statement. No Phase 6 outcome is asserted, and ID 14 is **not** described as
having survived a scheduled cycle.

### 0.1 Maintenance executions since the 09:22 UTC snapshot (OBSERVED FACT)

**Qualifying — `event=schedule` (natural cron): NONE.**

| run | started (UTC) | qualifies? |
|---|---|---|
| 37180621784 | 2026-10-04 05:41:37 | No — **predates the 09:09:52 repair** |
| 37135791841 | 2026-10-03 16:09:11 | No |
| 37098833320 | 2026-10-03 05:08:03 | No |

**Non-qualifying — `workflow_dispatch`:** no new runs since the 09:22 snapshot. The most recent
remains **37191466917**, created **09:13:38 UTC**, still `in_progress` at 09:29 (14m41s+), mapping
to `maintenance_runs` id **`650fb6ea619047ab`** (started 09:13:57 UTC, still `running` at capture).

Prior dispatch runs today (08:56:41 → 09:06:13) all completed before this snapshot and are likewise
inadmissible as Phase 6 evidence.

### 0.2 ID 14 — state at 09:28:55 UTC (OBSERVED FACT)

| Field | Value |
|---|---|
| `image_url` | `https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship/_jcr_content/pageimages/imageCarousel.imageformat.lightbox.1672553135.jpg` |
| `image_kind` | `program_image` |
| `image_verified_at` | `2026-10-04 09:09:52.973848+00:00` |
| `image_evaluation_status` | `None` |
| `verification_status` | `needs_review` |

**Audit events for ID 14 since the 09:09:52 repair: NONE.** ID 14's most recent audit row remains
**[68]**, the repair itself.

### 0.3 IDs 130 and 554 — no unexpected mutations (OBSERVED FACT)

| Record | `image_url` | `image_kind` | `image_verified_at` | `image_evaluation_status` | `verification_status` |
|---|---|---|---|---|---|
| 130 | `None` | `None` | `None` | `source_blocked` | `needs_review` |
| 554 | `None` | `None` | `None` | `no_official_image` | `needs_review` |

Neither has an audit row after its own repair row — **[69]** for 130 (09:09:53) and **[70]** for 554
(09:10:07). Both remain at their canonical evaluation verdicts. Not retried.

### 0.4 Audit activity is `maintenance.images` only (OBSERVED FACT)

Audit rows grew **79 → 90** between 09:22 and 09:28, last event **09:27:24 UTC**. Every observed
event is `writer_context='maintenance.images'` on unrelated records (ids 602, 607, 609, 610, 613,
621). **No `maintenance.logos` event has occurred at any point since the controlled repair.**

This matters for Phase 6: the specific writer under investigation has not executed since the repair,
so the test has not been applied — regardless of how long ID 14 retains its image.

Storage total **451**, unchanged. Public/storage invariants intact.

### 0.5 The nominal 12:07 UTC time is NOT reliable (DISPROVEN as an assumption)

Only `event=schedule` runs qualify. Observed schedule-event runs:

| run | started (UTC) | interval |
|---|---|---|
| 37180621784 | 2026-10-04 05:41:37 | 13h32m |
| 37135791841 | 2026-10-03 16:09:11 | 11h01m |
| 37098833320 | 2026-10-03 05:08:03 | 11h19m |
| 37043281952 | 2026-10-02 17:49:06 | 12h24m |
| 36968841644 | 2026-10-02 05:25:09 | 11h03m |
| 36906366989 | 2026-10-01 18:22:40 | — |

Successive intervals are **11h01m–13h32m**, not 12h. Land times drift from the nominal 00:07/12:07
by up to ~5.5 h, and only ~1 scheduled run per day appears despite a twice-daily cron. GitHub Actions
cron is best-effort and is being deferred here, most plausibly by the concurrent dispatch load.

**Consequence:** reporting "no mutation observed" at 12:20 UTC would have recorded *the absence of a
cycle* as *survival of an image* — a false negative manufactured by cron drift. The wakeup was moved
to **14:30 UTC**.

### 0.6 Concurrent dispatch runs confound the window (OBSERVED FACT)

Eight `workflow_dispatch` maintenance runs executed today between 08:56:41 and 09:13:38 UTC, one
still running. These are **not** the scheduled cycle.

They are not merely a nuisance: a dispatch-triggered `logos` execution carries the **same code** as
the cron-triggered one, so it can mutate ID 14 at any moment. Should such a run clear ID 14 with
`writer_context='maintenance.logos'`, that would be **Case D — PROVEN LIVE REVERSION WRITER**, which
is a different and weaker claim than natural-cron recurrence. Those two are kept separate throughout
this document.

### 0.7 Standing instruction carried forward

The 18 images cleared by the production `purge` execution are **not** to be restored during this
task. They remain queued for read-only investigation (exact IDs, purge predicate, public/non-public
split, recoverability, historical source evidence) as a separate step. Restoration is a distinct
decision requiring completed forensic evidence.

### 0.8 Readiness Checklist

| Requirement | Status |
|---|---|
| Qualifying `event=schedule` run since repair | **NO — window not open** |
| Audit trigger armed | YES |
| ID 14 baseline captured | YES (09:16:45, 09:22:33, 09:28:55 UTC) |
| ID 14 post-window comparison | BLOCKED — no cycle |
| Writer attribution for recurrence | BLOCKED — `logos` has not executed |
| Phase 7 entry | **NOT AUTHORISED** |

### 0.9 Containment Inspection (09:32 – 09:34 UTC)

Read-only. No stage invoked, no configuration changed, no run stopped by this investigation.

#### 0.9.1 Currently running GitHub Actions maintenance runs

| run id | event | workflow | status | started (UTC) | can execute `logos`? |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

**OBSERVED FACT: zero runs are `in_progress` at 09:32–09:34 UTC.** `gh run list --status in_progress`
returns empty across all workflows.

**Therefore no logos-capable execution is active at this instant.** This is stated explicitly rather
than inferred.

#### 0.9.2 The previously-running dispatch run was terminated before reaching `logos`

| Field | Value |
|---|---|
| run id | **37191466917** |
| event | **`workflow_dispatch`** (does not qualify for Phase 6) |
| workflow | ScholarZone scheduled maintenance |
| created | 2026-10-04 09:13:38 UTC |
| duration | 17m50s |
| final status | **`cancelled`** at 2026-10-04 09:31:28 UTC |
| mapped `maintenance_runs` id | `650fb6ea619047ab` (started 09:13:57 UTC) |

**PROVEN: this run was logos-capable and was cancelled before `logos` executed.**

Evidence:
- `STAGE_ORDER` places `"logos"` immediately after `"images"`:
  `verify, worklist, inventory, enrich, programme_details, images, logos, discover, …`
- `logos` is in the default stage set (`choices` at line 608 include `"logos"`), so a dispatch with
  no `--stage` filter includes it.
- Every audit event produced by this run was `writer_context='maintenance.images'`, the stage
  immediately **preceding** `logos`; the last was 09:29:44 UTC (row 91).
- **No `maintenance.logos` event exists at any time after the repair.**

So the run was terminated while still in `images` — approximately 1 min 44 s before its own
cancellation — and never reached the stage under investigation.

**UNKNOWN: why it was cancelled.** The workflow's concurrency group is `scholarzone-maintenance`
with `cancel-in-progress: false`, so a newer run could not have cancelled it by design. Manual
cancellation and platform-side termination are both consistent with the evidence. No cause is
asserted.

#### 0.9.3 Orphaned `maintenance_runs` row — stale record, not a live process

| Column | Value at 09:34:32 UTC |
|---|---|
| `run_id` | `650fb6ea619047ab` |
| `started_at` | 2026-10-04 09:13:57.315058+00:00 |
| `finished_at` | **`None`** |
| `status` | **`running`** |

**OBSERVED FACT:** the row still reports `running` although its Actions run reached a terminal
`cancelled` state at 09:31:28 UTC. A cancelled worker never writes a terminal status, so the row is
orphaned.

**DISPROVEN — that a worker is still alive.** Three independent signals agree: no Actions run is
`in_progress`; no audit event has occurred since 09:29:44 UTC (5 min before capture); and the
run's own status is terminal. The stale row is a reporting artefact, not a live execution, and must
not be read as an active writer.

This is a genuine, separate observation: **a cancelled maintenance run leaves a permanently
`running` row**, which would mislead any future operator or audit that counts in-flight runs by
`status = 'running'`.

#### 0.9.4 Audit events after the repair (09:09:52 UTC)

| Metric | Value at 09:34:30 UTC |
|---|---|
| Audit rows | **91** (was 71 at 09:16) |
| Last event | 2026-10-04 **09:29:44.731361+00:00** |
| Events on ID 14 | **0** — latest remains **[68]**, the repair |
| Events on ID 130 | **0** — latest remains **[69]** |
| Events on ID 554 | **0** — latest remains **[70]** |
| Distinct `writer_context` values post-repair | **`maintenance.images` only** |

Post-repair events, all on unrelated records: rows 79/81/82/83/87/88/91 on ids 602, 607, 609, 610,
613, 621 — each `image_evaluation_status, image_evaluated_at`.

**No `maintenance.logos`, `maintenance.purge` or `maintenance.add` event has occurred since the
repair.**

#### 0.9.5 ID 14 — exact latest audit row and current state

**Latest audit row for ID 14: `[68]`, 2026-10-04 09:09:52.755900+00:00, `writer_context='unknown'`,
`application_name='pgbouncer'`, `transaction_id='282716'`, `changed_fields` = image_url,
image_source_url, image_source_type, image_kind, image_verified_at (+ more).** That is the controlled
repair itself. No subsequent row exists.

State at 09:34:32 UTC: `image_url` = ETHZ `imageCarousel.imageformat.lightbox.1672553135.jpg`;
`image_kind='program_image'`; `image_verified_at=2026-10-04 09:09:52.973848+00:00`;
`image_evaluation_status=None`; `verification_status='needs_review'`.

IDs 130 and 554: `image_url=None`, `image_kind=None`, `image_verified_at=None`;
130 `source_blocked`, 554 `no_official_image`; both `needs_review`. Storage **451**, unchanged.

#### 0.9.6 Forensic confounders still live

1. **The environment is NOT frozen.** `concurrency.group = scholarzone-maintenance` with
   `cancel-in-progress: false` means new runs **queue** rather than cancel. Any actor able to
   dispatch the workflow can start a logos-capable run at any moment. Quiescence at 09:34 is a
   point-in-time observation, not a guarantee.
2. **A queued dispatch run would cancel nothing but would precede any future scheduled run**, since
   the group is shared. If a dispatch is in flight when the nominal 12:07 cron fires, the scheduled
   run will queue behind it and may land hours later — compounding the drift in 0.5.
3. **The orphaned `running` row** (0.9.3) can mask the true in-flight state.
4. **The cancelled run is itself evidence that executions are being interrupted by something outside
   this investigation**, and its cause is **UNKNOWN**.

#### 0.9.7 Standing evidentiary rule

**ID 14 being intact while `maintenance.logos` has not executed is NOT evidence that the image
survived the reversion test.** `logos` has not run since the repair. The reversion test has not been
applied, and elapsed time carries no evidential weight.

**Phase 6 remains NOT OBSERVED (Classification C). Phase 7 remains NOT AUTHORISED.**

### 0.10 Scheduler / Concurrency Forensic Audit (09:37 UTC)

Read-only. No workflow YAML, cron, concurrency setting, run, stage, database row or `do_logos`
change was made. Nothing was fixed.

#### 0.10.1 Exact concurrency configuration (OBSERVED FACT)

`.github/workflows/verification-cron.yml`:

| Scope | Line | group | cancel-in-progress |
|---|---|---|---|
| Workflow level | 81–82 | `scholarzone-maintenance` | `false` |
| Retry job level | 221–222 | `scholarzone-maintenance` | `false` |

Full concurrency-group inventory across all nine workflows:

| Workflow | group | cancel-in-progress |
|---|---|---|
| `ci.yml` | `${{ github.workflow }}-${{ github.ref }}` | `true` |
| `closed-record-audit.yml` | `closed-record-audit` | `false` |
| `deploy.yml` | `production-deployment-verification` | `true` |
| `frontend.yml` | `pages` | `false` |
| `promote-validated-scholarships.yml` | `production-promotion` | `true` |
| `verification-cron.yml` (×2) | `scholarzone-maintenance` | `false` |

**PROVEN:** `scholarzone-maintenance` is used **only** by `verification-cron.yml`. No other workflow
competes for it, so all contention on this group is internal to that single workflow.

**PROVEN:** `schedule` and `workflow_dispatch` are two triggers on the *same* workflow, and the
concurrency group is declared at **workflow level**. Both therefore share `scholarzone-maintenance`
identically. There is no separate lane for scheduled work.

**PROVEN:** with `cancel-in-progress: false`, a newly arriving run does not replace an in-progress
run — it waits. GitHub's documented behaviour is that a queued run is **pending**, and *any
previously pending run in the same group is cancelled* when another arrives. So the group admits one
active run plus at most one pending run.

#### 0.10.2 Overlap and queueing (PROVEN / DISPROVEN)

| Question | Answer |
|---|---|
| Can multiple maintenance runs overlap? | **No** — one active per group |
| Does a manual dispatch block a scheduled run? | **Yes** — identical group |
| Can a queued dispatch cancel a *pending scheduled* run? | **Yes** — documented GitHub behaviour, one pending slot per group |
| Can a queued dispatch cancel an *in-progress* scheduled run? | **No** — `cancel-in-progress: false` |

**PLAUSIBLE BUT UNPROVEN:** that today's missing expected execution was caused by a dispatch run
occupying the group at the moment the scheduled run arrived, followed by a further arrival that
cancelled it while pending. This is consistent with eight dispatch runs between 08:56:41 and
09:13:38 UTC, but no `schedule`-event run exists after 05:41:37 to examine, so the mechanism is
inferred from configuration, not witnessed.

#### 0.10.3 The 11–13.5 h drift is NOT explained by queueing — hypothesis DISPROVEN

Observed `schedule` gaps: 11h01m, 11h19m, 12h24m, 13h32m — roughly **one run per day** against a
twice-daily cron.

**DISPROVEN: queueing as the cause.** The completed scheduled runs took 10m23s–18m07s. A queue
delay bounded by ~18 minutes cannot produce an 11-hour gap. Whatever defers these runs is
multi-hour in scale and external to the concurrency group.

**PLAUSIBLE BUT UNPROVEN:** GitHub-hosted cron is best-effort and is delayed or dropped under
platform load. The repository already documents this in the workflow itself:

> "Platform limits, stated honestly: GitHub-hosted scheduled workflows can be delayed by platform
> load, and on a public repository they can be disabled after a long period of repository
> inactivity. Neither is something this file can work around."

**UNKNOWN:** the precise cause of today's drift. GitHub exposes no per-run scheduling diagnostic
through the CLI available here, and no run was queued long enough to observe directly.

#### 0.10.4 How `maintenance_runs` rows are finalised, and the exact stale-row code path

The recorder (`app/services/maintenance_run_log.py`) has one writer path for status:

- `open()` — line 111–132 — inserts the row with `status=STATUS_RUNNING` (`finished_at` NULL).
- `finish(status)` — line 135–170 — sets `finished_at`, `duration_ms` and `status`.

Its only call site is `app/jobs/scholarzone_maintenance.py:3167`:

```python
status = "ok" if not failed_count else "failed"
record_saved = True
try:
    recorder.record_counts({...})
    record_saved = recorder.finish(status)
except Exception:  # noqa: BLE001
    logger.warning("could not persist run record", exc_info=True)
```

**PROVEN — the exact path that strands a cancelled worker at `status='running'`:**
`main()` reaches line 3167 only by falling off the end of the function *after every stage has run*.
There is **no `try/finally` around the stage loop, and no handler for `KeyboardInterrupt`,
`SystemExit` or `BaseException`.** A process killed before that line therefore never writes a
terminal status, leaving `status='running'`, `finished_at=NULL` permanently.

This applies to every non-graceful termination: Actions cancellation, `timeout-minutes: 90`
expiry, SIGKILL, OOM. `650fb6ea619047ab` (cancelled 09:31:28 UTC, still `running` at 09:34:32) is
exactly this path.

#### 0.10.5 Can stale `running` rows mislead? (evaluated per audience)

| Audience | Misleading? | Evidence |
|---|---|---|
| **Scheduler decisions** | **No** | No code reads `status='running'` to gate anything. `STATUS_RUNNING` appears only at its definition (line 30) and write (line 120). It is write-only state. |
| **Maintenance monitoring** | **Yes** | A permanently `running` row implies work in flight that does not exist, and hides the fact that the run was aborted mid-stage. |
| **Operator dashboards** | **Yes** | `recent_runs()` (line 183) returns `status` verbatim, so any UI or report listing recent runs shows a run as still executing indefinitely. |
| **Forensic attribution** | **Yes — demonstrated first-hand** | `forensic_preflight.py` printed `run 650fb6ea619047ab: running` at both 09:28:58 and 09:34:32 UTC, after the run had been cancelled at 09:31:28. I identified it as stale **only** by independently cross-checking GitHub Actions. The database alone was misleading. |

**PROVEN:** stale rows do mislead. The forensic case is not hypothetical — this investigation
encountered it directly, and had the cross-check not been performed, the report would have described
a dead run as a live writer and asserted the environment was active when it was not.

#### 0.10.6 Retry-job concurrency — PLAUSIBLE BUT UNPROVEN

The retry job (line 220) carries `needs: maintain` **and** declares the same group
`scholarzone-maintenance` with `cancel-in-progress: false` as its own workflow-level group. A job
that must wait on a group its own run already holds may never acquire it.

**PLAUSIBLE BUT UNPROVEN:** the retry job may never execute. No failed maintenance run was
available to test this, and the semantics were not verified against a live run. Not fixed.

#### 0.10.7 WHAT MUST BE TRUE FOR THE NEXT SCHEDULED RUN TO BE A VALID PHASE 6 OBSERVATION?

A valid observation requires **all** of the following. Each is stated so it can be checked rather
than assumed.

1. **The run must be `event=schedule`.** A `workflow_dispatch` run does not qualify, however
   similar its code path. *Checkable:* `gh run list --event=schedule`.
2. **It must start after 2026-10-04 09:09:52 UTC**, so it post-dates the controlled repair. The
   05:41:37 run does not qualify.
3. **Its `logos` stage must actually execute.** Phase 6 tests `do_logos`. `logos` is seventh in
   `STAGE_ORDER`, after `images`, and a run cancelled or timed out before it does not qualify.
   *Checkable:* a `writer_context='maintenance.logos'` audit row, **or** an explicit record that the
   stage ran and produced zero mutations.
4. **The run must reach a terminal state with `finished_at` set.** An orphaned `running` row means
   the worker died, so stage coverage is incomplete and the observation is void.
5. **No concurrent dispatch may occupy or contend for the group during the run.** Because dispatch
   and schedule share `scholarzone-maintenance` and only one run is pending at a time, an arriving
   dispatch can cancel a pending *scheduled* run outright.
6. **The audit trigger must be armed and enforcing throughout** — table, trigger, both guards
   present, `UPDATE`/`DELETE`/`TRUNCATE` still rejected.
7. **ID 14 must be confirmed intact immediately before the cycle**, so a post-cycle comparison has a
   valid baseline. Currently satisfied: `image_kind='program_image'`,
   `image_verified_at=2026-10-04 09:09:52.973848+00:00`, latest audit row `[68]`.
8. **No `worker_dispatch` maintenance run may be in flight at observation time**, and no
   `workflow_dispatch` logos execution may occur inside the window — otherwise a Case D event
   (proven live reversion writer, *not* natural cron recurrence) contaminates the result.
9. **Storage must be 451 and the public universe unchanged** before and after, so an unrelated
   mutation is distinguishable from a target mutation.

**If conditions 1–4 cannot be evidenced, Phase 6 is NOT OBSERVED and no conclusion about survival
may be drawn.** Absence of a mutation without a qualifying cycle is uninformative.

**Contained but not frozen.** At 09:34 UTC no run was active, so no logos-capable execution existed
at that instant. New dispatch runs remain possible at any time, and shared-group contention plus
platform-level cron drift both remain unmitigated. Nothing in this audit was changed.

### 0.11 Passive Qualifying-Run Observation (09:40 UTC)

**Method: passive only.** No workflow dispatched, no maintenance stage invoked, no run stopped, no
code / YAML / cron / concurrency / `do_logos` / `do_purge` / data change. Observation was limited to
read-only GitHub Actions metadata queries.

#### 0.11.1 Qualifying-candidate enumeration (OBSERVED FACT)

Every `event=schedule` run of the maintenance workflow:

| run id | event | created (UTC) | conclusion |
|---|---|---|---|
| 37180621784 | `schedule` | 2026-10-04 **05:41:37** | success |
| 37135791841 | `schedule` | 2026-10-03 16:09:11 | success |
| 37098833320 | `schedule` | 2026-10-03 05:08:03 | success |
| 37043281952 | `schedule` | 2026-10-02 17:49:06 | success |
| 36968841644 | `schedule` | 2026-10-02 05:25:09 | success |

Most recent runs of any event, most recent first:

| run id | event | created (UTC) | conclusion |
|---|---|---|---|
| 37191466917 | `workflow_dispatch` | 2026-10-04 09:13:38 | **cancelled** (17m50s) |
| 37191067046 | `workflow_dispatch` | 2026-10-04 09:06:13 | success |
| 37190901230 | `workflow_dispatch` | 2026-10-04 09:03:11 | success |
| 37190839296 | `workflow_dispatch` | 2026-10-04 09:02:06 | success |
| 37190793058 | `workflow_dispatch` | 2026-10-04 09:01:14 | success |
| 37190757477 | `workflow_dispatch` | 2026-10-04 09:00:35 | success |

**PROVEN: no maintenance run of any kind has been created since 09:13:38 UTC.**
**PROVEN: no `event=schedule` run exists after 2026-10-04 05:41:37 UTC**, which predates the
09:09:52 repair by 3 h 28 m.

#### 0.11.2 Qualifying-criteria checklist — evaluated

| # | Criterion | Status | Basis |
|---|---|---|---|
| 1 | `event = schedule` | **FAIL for every candidate** | Newest schedule run is 05:41:37, pre-repair |
| 2 | Started after 09:09:52 UTC | **FAIL** | 05:41:37 < 09:09:52 |
| 3 | Reaches `logos` stage | **NOT REACHED / N.A.** | No run exists to evaluate |
| 4 | Terminal state + valid `finished_at` | **NOT APPLICABLE** | No run exists |
| 5 | No dispatch logos in window | **HOLDS** | No run of any kind since 09:13:38 |
| 6 | ID 14 intact immediately before logos | **NOT APPLICABLE** | No logos execution to precede |
| 7 | Audit trigger active/enforcing | **HOLDS as of 09:34:32** | Table, trigger, both guards present; U/D/T rejected |
| 8 | Storage 451 immediately before | **HOLDS as of 09:34:32** | 451 |
| 9 | Public-universe count recorded before | **HOLDS as of 09:22:33** | 366 (canonical predicate) |

#### 0.11.3 Data-freshness limitation — declared

The production database is reachable only from CI, and this phase forbids dispatching a workflow.
**The most recent authoritative database read is therefore 2026-10-04 09:34:32 UTC**, roughly six
minutes before this section was written. Criteria 7–9 are confirmed as of that timestamp and have
not been re-read since. This limitation is stated rather than papered over; it is a further reason
no conclusion could be drawn even had a qualifying run existed.

#### 0.11.4 Required result statements

| Question | Answer |
|---|---|
| **Qualifying run found?** | **NOT FOUND** |
| **Did `logos` execute?** | **NO — it did not execute** |
| **Was ID 14 cleared or did it survive?** | **NEITHER — UNDETERMINED.** `logos` never ran, so no test was applied. Reporting "survived" would be reporting the absence of a test as a pass. |
| **Writer attribution?** | **NONE POSSIBLE.** No mutation of ID 14 occurred after the repair; latest audit row remains `[68]`, the repair itself. |
| **Phase 6 classification** | **CASE E — PHASE 6 NOT OBSERVED** |
| **Is Phase 7 authorised?** | **NO — NOT AUTHORISED** |

CASE E applies on the plainest ground: there is no qualifying run to observe. Nothing was fabricated,
no run was dispatched or simulated, and no elapsed interval was treated as evidence.

#### 0.11.5 Standing evidentiary rules reaffirmed

- ID 14 holding while `maintenance.logos` has not executed is **not** evidence of survival.
- `maintenance_runs` row `650fb6ea619047ab` reading `status='running'` is **not** an active worker.
- Absence of an audit event is **not** absence of a mutation unless a qualifying cycle demonstrably
  executed the stage.

---

## 1. Observation Window

| Item | Value |
|---|---|
| Pre-window captures taken | 2026-10-04 09:16:45, 09:22:33, 09:28:55 UTC |
| Controlled repair completed | 2026-10-04 09:10:08 UTC |
| Scheduled cron | `7 */12 * * *` (nominal 00:07, 12:07 UTC) |
| Latest qualifying scheduled run | 2026-10-04 05:41:37 UTC — **predates the repair** |
| Next natural scheduled run | Nominal 12:07 UTC; see 0.5 — drift of hours observed |
| Scheduled cycles observed post-repair | **0** |
| Finalisation wakeup | 2026-10-04 **14:30 UTC** |

### Runs seen since the repair — none is the scheduled cycle

| run_id | started_at | status | Is it the natural 12:07 cycle? |
|---|---|---|---|
| `650fb6ea619047ab` | 2026-10-04 09:13:57 UTC | `running` | **No** — 09:13 is not a cron time; operator/`workflow_dispatch` triggered |
| `bac7158253c0484f` | — | `ok` | No |
| `b62a2be51ba24ec3` | — | `ok` | No |

The 09:13:57 run is explicitly **not** admissible as the Phase 6 observation: it was
dispatch-triggered, not scheduled. Using it would be equivalent to simulating the scheduler, which
this phase forbids.

No unbound image-constant `NameError` in any recent run. The `do_stats` defect fixed in Phase 1 has
not recurred.

---

## 2. Scheduled Run Identity

**PENDING** — to be captured from the 12:07 UTC run of
`.github/workflows/verification-cron.yml` ("ScholarZone scheduled maintenance") log:

- run id
- production revision (`/health` revision string)
- start / end UTC
- per-stage outcomes: `images`, `logos`, `purge`, `stats`, `auto_delete_candidate`, `purge_closed`
- `auto_delete_candidate` deleted count

---

## 3. ID 14 Before/After

### Before the observation window (09:16:45 UTC) — authoritative snapshot

| Field | Value |
|---|---|
| `image_url` | `https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship/_jcr_content/pageimages/imageCarousel.imageformat.lightbox.1672553135.jpg` |
| `image_source_url` | `https://ethz.ch/students/en/studies/financial/scholarships/excellencescholarship.html` |
| `image_source_type` | not captured in this pass (present in DB; re-read at finalisation) |
| `image_kind` | `program_image` |
| `image_alt_text` | `None` |
| `image_verified_at` | `2026-10-04 09:09:52.973848+00:00` |
| `image_evaluation_status` | `None` |
| `image_evaluated_at` | `None` |
| `verification_status` | `needs_review` |

### After the observation window

**PENDING.** Determined by the audit trail, not by reading the column alone: an unchanged column
with no audit row is the only acceptable proof that nothing ran, because the trigger records every
change and cannot be bypassed.

---

## 4. Audit Events

### ID 14 — complete history (oldest first)

| id | changed_at_utc | writer_context | application_name | txid | changed_fields | image_url after |
|---|---|---|---|---|---|---|
| 3 | 2026-10-04 08:35:23.391597 | **`unknown`** | pgbouncer | 281733 | image_url, image_source_url, image_source_type, image_kind, image_verified_at, … | ETHZ `imageCarousel…jpg` |
| 5 | 2026-10-04 08:38:28.768558 | **`maintenance.logos`** | pgbouncer | 281764 | image_url, image_source_url, image_source_type, image_alt_text, image_verified_at, image_evaluation_status, image_evaluated_at | **`None` (cleared)** |
| 68 | 2026-10-04 09:09:52.755900 | `unknown` | pgbouncer | 282716 | image_url, image_source_url, image_source_type, image_kind, image_verified_at, … | ETHZ `imageCarousel…jpg` |

Row **5** is the known live vector: an accepted `program_image` was cleared by `maintenance.logos`
3 min 5 s after being set.

Row **68** is the Phase 0–5 controlled repair, attributed `unknown` because
`ImageCoverageRunner` is invoked outside the two instrumented choke points
(`maintenance._run_stage`, `admin_image_review`). Recording it as `unknown` is the correct
outcome — the database captured an unlabelled mutation rather than losing it.

### Audit totals

| Metric | Value |
|---|---|
| Rows in audit | **71** |
| First event | 2026-10-04 08:34:18.727518 UTC |
| Last event | 2026-10-04 **09:10:08.761768** UTC — the controlled repair |
| New events since repair, as of 09:16:45 | **0** |

### Writer-context distribution (whole audit)

| writer_context | n | first | last |
|---|---|---|---|
| `maintenance.purge` | 32 | 08:39:22 | 09:01:47 |
| `maintenance.add` | 21 | 08:39:23 | 08:39:23 |
| `maintenance.logos` | 8 | 08:38:28 | 08:38:28 |
| `maintenance.images` | 2 | 08:34:18 | 08:34:19 |
| `unknown` | 8 | 08:35:23 | 09:10:08 |

---

## 5. Exact Writer Attribution

Method: a writer is named **only** when the audit row's `writer_context` identifies the execution
context **and** that context's code path is known to have run. `unknown` is reported as `UNKNOWN`.
Identity is never inferred from timing.

| Window | Mutation | writer_context | Attribution |
|---|---|---|---|
| Pre-repair, 08:35:23 | ID 14 image set | `unknown` | **UNKNOWN writer** — recorded, execution path not established |
| Pre-repair, 08:38:28 | ID 14 image cleared | `maintenance.logos` | **PROVEN**: `maintenance.logos` cleared ID 14 |
| Repair, 09:09:52 | ID 14 image set | `unknown` | Canonical `ImageCoverageRunner`, invoked by script outside instrumented stages |
| Observation window | — | — | **PENDING** |

Limitation on record: `application_name` is `pgbouncer` on every row because Neon terminates
connections through a pooler, so `client_addr` is the pooler address. Per-client IP attribution is
**not available** through this mechanism; writer context is the attribution channel.

---

## 6. ID 130 / 554 Status

Neither was mutated after the controlled repair. Both carry canonical evaluation outcomes, not
failures, and were **not** retried.

| Field | ID 130 | ID 554 |
|---|---|---|
| `image_url` | `None` | `None` |
| `image_kind` | `None` | `None` |
| `image_verified_at` | `None` | `None` |
| `image_evaluation_status` | `source_blocked` | `no_official_image` |
| `image_evaluated_at` | 2026-10-04 09:09:53.858365 UTC | 2026-10-04 09:10:08.976476 UTC |
| `image_source_url` | `None` | `https://wellcome.org/grant-funding/schemes/early-career-awards` |
| `image_alt_text` | `None` | `Wellcome` |
| `verification_status` | `needs_review` | `needs_review` |
| Audit rows from repair | 1 (id 69) | 1 (id 70) |

Both repairs produced audit events. ID 554's pre-existing `no_official_image` verdict is unchanged
apart from the fresh `image_evaluated_at` timestamp.

---

## 7. Causal Timeline

| UTC | Record | Writer | Action |
|---|---|---|---|
| 2026-10-03 ~20:30 | ID 14 | not attributable | Original incident: image set, history rows 208 + 406 written. **Audit did not yet exist.** |
| 2026-10-03 ~20:30 → 2026-10-04 | 130, 554 | not attributable | Image state lost. **No audit coverage.** |
| 2026-10-04 08:34:18 | audit live | — | First captured mutation (ID 130, `maintenance.images`) |
| 2026-10-04 08:35:23 | ID 14 | **UNKNOWN** | Image set to ETHZ `imageCarousel` |
| 2026-10-04 08:38:28 | ID 14 | **`maintenance.logos`** | **Image cleared to NULL** |
| 2026-10-04 08:38:28 | ID 130 | `maintenance.logos` | Image set to `akf.org` favicon |
| 2026-10-04 08:39:23 | ID 130 | `maintenance.add` | Image fields changed |
| 2026-10-04 09:01:47 | various | `maintenance.purge` | Last `purge` mutation before repair |
| 2026-10-04 09:09:52 | ID 14 | `unknown` (canonical runner) | **Controlled repair — image set** |
| 2026-10-04 09:09:53 | ID 130 | `unknown` (canonical runner) | Evaluation → `source_blocked` |
| 2026-10-04 09:10:08 | ID 554 | `unknown` (canonical runner) | Evaluation → `no_official_image` |
| 2026-10-04 09:13:57 | — | dispatch-triggered run | **Not** the scheduled cycle; excluded |
| **2026-10-04 12:07** | — | cron | **PENDING — observation window** |

The 08:35 → 08:38 sequence on ID 14 reproduces the original incident's shape: an image is set, then
cleared within minutes, with no verification-history row. The audit attributes the **clear** to
`maintenance.logos`; the **set** remains `UNKNOWN`.

---

## 8. Proven Findings

1. **`maintenance.logos` cleared ID 14's accepted `program_image`.** Audit row 5,
   `writer_context='maintenance.logos'`, 2026-10-04 08:38:28 UTC, txid 281764. Before/after JSON
   shows the full image field set going to NULL.
2. **The database-level audit captures every mutation, including unlabelled ones.** All three repair
   mutations produced audit rows; none escaped.
3. **Append-only is enforced.** UPDATE, DELETE and TRUNCATE on the audit table each raise
   `RestrictViolation`; row count 65 → 65 across the probe, rolled back.
4. **`TRUNCATE` was a real gap and is now closed** by a statement-level guard — row-level triggers
   never fired for it.
5. **The database audit did not exist during the original incident.** Earliest audit event is
   2026-10-04 08:34 UTC.
6. **`do_stats` was unrunnable** (`NameError: LOGO_IDENTITY_KINDS`) until fixed in Phase 1; not
   recurring.

## 9. Unproven Findings

1. That `maintenance.logos` is the **recurring** trigger. One proven clearing exists; recurrence in
   the observation window is untested.
2. That `maintenance.logos` caused the **2026-10-03** reversion. No audit coverage exists for it.
3. The identity behind the `08:35:23` `unknown` write that preceded the proven clear.
4. Whether `do_purge` contributes. It ran 32 times without touching ID 14, consistent with the
   `87ad84c` accepted-image protection.
5. Per-actor attribution from `client_addr` — unavailable behind pgbouncer.

## 10. Whether `do_logos` is the Proven Reversion Writer

**Two distinct questions, two distinct answers.**

- *Can* `maintenance.logos` clear an accepted `program_image` on ID 14? — **YES, PROVEN** by audit
  row 5.
- *Did* it clear ID 14 again in this observation window? — **PENDING.** The window has not opened.

Therefore, at this timestamp: `maintenance.logos` is classified as a **CONFIRMED LIVE UNSAFE
VECTOR** and as the **PROVEN REVERSION WRITER for the 08:38:28 event**. It is **NOT PROVEN** to be
the recurring trigger in this observation.

`do_logos` has deliberately **not** been modified. Changing it now would destroy the evidence Phase
6 exists to collect.

## 11. Phase 7 Recommendation

1. **Wait for the 12:07 UTC cycle.** Do not dispatch `logos`, `images` or `purge` manually, and do
   not simulate the scheduler — a manual invocation cannot answer whether the *scheduled* path
   reverts the record.
2. **Attribute from the audit row only.** If ID 14's image is cleared and
   `writer_context='maintenance.logos'`, classify `do_logos` as the PROVEN REVERSION WRITER for
   this observation. If the row is absent, that is a STOP condition: a mutation escaped the audit
   and the instrumentation itself is defective.
3. **Only after attribution**, bring `do_logos` under the same protection `87ad84c` gave
   `do_purge`: an accepted image (`image_verified_at` set and `image_kind` in
   `ACCEPTED_IMAGE_KINDS`) must not be cleared for merely not being a logo. Note the distinction —
   `do_logos` legitimately clears *replaced* artwork, so the fix must distinguish
   "unaccepted decoration" from "accepted image being re-evaluated", not simply disable clearing.
4. **Instrument `do_logos` with a label** if it is proven, so future events name the path rather
   than `unknown`.
5. **Extend coverage** to the remaining uninstrumented writers (`image_verifier`,
   `image_coverage_runner`, `image_discovery_orchestrator`, `audit_images`, `logo_fallback`,
   `resolve_generic_images`, `image_validator`, `verification`, `backfill_alt_text`) so legitimate
   mutations are self-identifying.
6. **Harden the audit boundary further:** the application connects as the table owner, so it could
   `DROP` a guard and rewrite history. A separate non-owner application role is the only real fix.
7. **Consider same-transaction blind spot:** a mutation reverted inside the same transaction leaves
   no audit row. `pg_stat_statements` would be needed to close that.

---

## Final Conclusion — evidence tiers kept distinct

**Observed fact.** On 2026-10-04 08:38:28 UTC, `writer_context='maintenance.logos'` cleared ID 14's
accepted `program_image` to NULL (audit row 5, txid 281764). ID 14 was canonically repaired at
09:09:52 UTC (audit row 68). As of 09:16:45 UTC — 6 min 37 s after repair — ID 14 retains its image
and the audit holds no further events.

**Proven writer.** `maintenance.logos` is the proven writer of the 08:38:28 clearing of ID 14. It is
proven capable of clearing an accepted `program_image`, a path `87ad84c` does not protect.

**Plausible hypothesis (untested).** That `do_logos` is the recurring mechanism by which ID 14's
image is reverted. Supported by one proven clearing that matches the incident's shape; not yet
demonstrated after repair.

**UNKNOWN writer.** The 08:35:23 write that set ID 14's image immediately before the proven clear is
attributed `unknown`. Its execution path is not established, and no inference is drawn.

**Original 2026-10-03 root cause: NOT IDENTIFIED.** The audit began 2026-10-04 08:34 UTC, roughly a
day after the incident. History rows 208 and 406 survive, which excludes a database rollback. The
unrecorded-writer class remains the strongest hypothesis and is **not** proven. `87ad84c` is an
independent latent-defect fix for `do_purge`; it is **not** the incident root-cause fix and is not
claimed as one.