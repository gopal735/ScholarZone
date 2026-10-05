# ScholarZone — Phase B Integration Final

One integrated candidate: **current master + latest verified Phase A persistence
+ verified Phase B**, with every number below produced by executing the actual
integrated tree.

## Identity

| | SHA |
|---|---|
| Current master (unchanged by this work) | `cfd0acaf00dc6bd2ec9ce30c6dbc2a128eae032b` |
| Master at task start | `fc4096f7a2aac8530f4e14495a7f21b9a97419be` (advanced during the work) |
| PR #7 head before integration | `93b65e160c307a2fdca9ded4f930d7afd5e8dce3` |
| Phase A persistence candidate | `d194768daa6eea5ee0a66191cc4d41c4dacf1053` |
| **PR #7 head after integration** | **`b55df302171486bdf1e1ca48c238411bfafa3229`** |

`origin/master` and GitHub master agree (`git ls-remote` → `cfd0acaf`), so there
is no remote-integrity split. Master was **not modified**: it is still `cfd0acaf`
after the push. PR #7 was updated with an **ordinary fast-forward push**
(`93b65e1..b55df30`) — no force-push, no history rewrite, no merge of PR #7.

## Did equivalent Phase A code already exist in PR #7? — NO

This was decided by reading both implementations, not by comparing hashes.

PR #7 shipped a Phase A core in `backend/app/services/maintenance_slot.py` that
**implements the architecture that was explicitly rejected**: the logical slot is
stored on the `maintenance_runs` row itself (`slot_status`, `slot_due_at`,
`lease_until`, `claim_owner`, `logical_source`, `transport_event`). That design
cannot answer the question the slot ledger exists to answer — a dropped trigger
writes no `MaintenanceRun`, so the one table meant to reveal a due-but-never-run
slot is empty in precisely that case. PR #7's dispatcher made this structural: it
enumerated `MaintenanceRun.slot_status`, so it could only ever see slots that had
already run.

The two Phase A cores were also mutually incompatible, so "keep both" was not
available:

| | PR #7 core | Phase A `d194768` |
|---|---|---|
| Slot id | `maint-slot-20261004T1207Z` | `maintenance:2026-10-04T12:07:00Z` |
| Claim semantics | claim whichever slot is due at `as_of` | claim a named `slot_id` |
| Storage | columns on `maintenance_runs` | dedicated `maintenance_slots` table |
| Verification | 333 lines of core tests | 43 + 57 + 16 |

**CASE B** applied: the required Phase A changes were integrated and the
superseded core removed rather than duplicated.

## Integration method

1. **Cherry-pick `d194768`** onto `93b65e16`. One conflict, in `models.py`.
2. **Resolve the conflict by preserving both intents**, never by taking a side:
   `MaintenanceSlot` kept as the authority; `MaintenanceRun.slot_id` kept as a
   nullable, **non-unique** link; the seven duplicated run-table columns
   (`slot_status`, `slot_due_at`, `logical_source`, `transport_event`,
   `claimed_at`, `lease_until`, `claim_owner`) **removed**, because two sources of
   truth for ownership is worse than either — they could silently disagree.
   `ix_maintenance_runs_slot_id` kept; `ix_maintenance_runs_slot_lease` dropped
   with the column it indexed.
3. **`database.py`**: removed `ensure_maintenance_slot_columns` (which would have
   re-`ADD COLUMN`ed the columns just removed, recreating the duplicate schema at
   runtime). `_upgrade_maintenance_slot_schema` is now the single slot-schema
   path, called once for both dialects from `init_database()`.
4. **Repointed Phase B** (`maintenance_dispatch.py`) onto the Phase A store.
   `ensure_slot`, `claim_slot`, `expire_stale_claims`, `transition_slot` — no
   second claim mechanism.
5. **Repointed the worker** (`scholarzone_maintenance.py`) to the Phase A core and
   preserved the "logical source is never inferred from transport" rule.
6. **Removed the superseded core**: `backend/app/services/maintenance_slot.py`
   (406 lines) and `backend/tests/test_maintenance_slot_core.py` (333 lines).
7. **Folded in current master** (`cfd0acaf`) with an explicit `--no-ff` merge,
   because master advanced by 3 SEO commits while the integration was being
   built. Merged rather than rebased deliberately: the Phase A and Phase B
   commits keep their identity and PR #7 updates by fast-forward. Zero file
   overlap — master touched only frontend files and
   `backend/app/data/generate_sitemap.py`.

`d194768` is **not** an ancestor of PR #7 because the cherry-pick produced a new
commit (`c0f9a0d`) carrying conflict resolution. Content equivalence was verified
instead of asserted:

    git diff d194768 <PR#7> -- maintenance_slots.py maintenance_slot_store.py \
        test_maintenance_slots.py test_maintenance_slot_persistence.py \
        test_maintenance_slot_concurrency.py
    -> IDENTICAL (5 files, byte for byte)

Only `models.py` (+23/-4) and `database.py` (+6) differ, and only in the
documented conflict resolution.

## Changed-file scope: 15 files, all Phase A / Phase B

    .github/workflows/verification-cron.yml                +20
    backend/app/database.py                               +52
    backend/app/jobs/scholarzone_maintenance.py           +69
    backend/app/main.py                                    +6
    backend/app/maintenance_slots.py                     +156
    backend/app/models.py                                 +98
    backend/app/routers/internal_maintenance.py            +93
    backend/app/services/maintenance_dispatch.py          +561
    backend/app/services/maintenance_run_log.py            +11
    backend/app/services/maintenance_slot_store.py        +460
    backend/tests/test_maintenance_dispatch_phase_b.py    +582
    backend/tests/test_maintenance_slot_concurrency.py    +407
    backend/tests/test_maintenance_slot_persistence.py    +777
    backend/tests/test_maintenance_slots.py               +198
    vercel.json                                             +8
                                                     3495 insertions, 3 deletions

No frontend, no scholarship or image data, no credentials, no provider
integrations. Master's build-provenance work (`build_provenance.py`,
`embed_build_revision.py`, `release_identity_gate.py`, `deploy.yml`) is
**untouched**, and its 184 tests pass.

## Two pre-existing Phase B defects found and fixed

Neither was caused by Phase A. Both were reproduced on PR #7's own head
(`93b65e16`, unmodified) **before** being fixed.

**1. Cross-module engine-cache leak (15 tests broken).** PR #7's dispatch fixture
called `importlib.reload(app.database)`. `get_engine()` and
`get_session_factory()` are `lru_cache`d and take **no arguments**, so their cache
key is empty. Reloading rebinds those names to new functions in the shared module
dict while every already-imported module keeps the old objects — so a later
fixture's `reset_database_connections()` clears the *new* cache and leaves the
*old* one populated. Cached engine state then leaked into unrelated modules and
broke 14 `test_stats_universe_scope.py` tests plus 1
`test_public_verification_contract.py` test with `UNIQUE constraint failed:
scholarships.id`.

Reproduced on `93b65e16` unmodified: `14 failed, 73 passed`. Replaced the reload
with an explicit `reset_database_connections()` — same isolation, none of the
cross-module damage. After: `87 passed, 0 failed`.

**2. Workflow YAML breaking the SnapDeploy guard.** PR #7's
`workflow_dispatch` input descriptions were multi-line single-quoted YAML
scalars. To Python's tokenizer that is an unterminated string, so
`_code_without_comments_or_strings` hit `except TokenError: return source` and
started flagging the historical SnapDeploy mention in the comment at the top of
the *same* workflow. Proved by tokenizing both revisions:

    master fc4096f7 workflow : tokenized OK (1285 tokens)
    PR#7 workflow           : TokenError -> test falls back to FULL source
                              (unterminated string literal, line 34)

Kept the descriptions on one line; the test itself is unchanged.

## Test results — all executed on the integrated tree `b55df30`

| Suite | Result |
|---|---|
| Phase A pure core | **43 passed** |
| Phase A persistence | **57 passed** |
| Phase A concurrency | **16 passed** |
| **Phase A total** | **116 passed** |
| **Phase B** | **43 passed** |
| **Combined maintenance** | **236 passed** |
| Provenance / release / vercel / hardening | **184 passed** |
| `py_compile` on all 10 changed Python files | **PASS** |

### Full backend regression — both sides executed

| Tree | Result |
|---|---|
| Current master `cfd0acaf` (baseline) | 8 failed, 5080 passed, 10 skipped |
| **Integrated `b55df30`** | **8 failed, 5239 passed, 10 skipped** |

**Zero new failures. +159 passed, identical 8 failures, identical 10 skips.**
No test was skipped, xfailed, deleted or weakened.

### Failure classification — all 8, none hidden

| Test | Class | Cause |
|---|---|---|
| `test_neon_migration.py::TestMigrationHeaderParsing::test_actual_migration_file_header_not_in_executable_statements` | **PRE_EXISTING** | `FileNotFoundError: backend/migration_export.sql` |
| `test_neon_migration.py::TestUtf8Encoding::test_migration_file_is_utf8` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestUtf8Encoding::test_em_dash_present_in_sql` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestUtf8Encoding::test_en_dash_present_in_sql` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestBooleanConversion::test_migration_sql_has_true_not_integers` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestBindParameterDetection::test_detect_bind_params_real_migration_file_has_none` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestValidateMigrationFile::test_validate_real_migration_file` | **PRE_EXISTING** | same |
| `test_neon_migration.py::TestValidateMigrationFile::test_validate_real_file_in_report` | **PRE_EXISTING** | same |

Identical set and identical cause on the master baseline. `backend/migration_export.sql`
is gitignored and absent from any fresh worktree. Nothing Phase A or Phase B
related. No `UNKNOWN` classifications.

### A discarded run, reported rather than hidden

An earlier integrated run showed **23 failed**. It was **invalid** and was
discarded, for two reasons I should state plainly:

1. I had edited `maintenance_slot_store.py` mid-run for the negative control, so
   part of that run executed against deliberately broken code.
2. It was run concurrently with the master baseline, which I should not have done.

The authoritative number is the later isolated run above. The 15
non-`neon` failures in that run were, separately, a **real pre-existing Phase B
defect** (the engine-cache leak above) — which is why they were reproduced on
PR #7's head and fixed rather than dismissed as an artifact.

## Concurrency and Phase A acceptance (on the integrated tree)

- **43/43** pure core.
- Mandatory races **really execute**: 8 threads, `threading.Barrier(8)`, own
  session each. Independence was *measured*, not assumed: 8 threads, **peak 8
  simultaneous pool checkouts across 8 distinct DBAPI connections** (counted via
  the engine's `connect` event), exactly **1 owner**, `attempt == 1`.
- **Negative control remains meaningful**: removing `state IN (...)` from the
  guard produces **6 failed / 10 passed** on the integrated tree. Store restored
  **byte-exact** (SHA-256 verified), no residue.
- Lease expiry, recovery, and the ORM datetime fix all still hold: mutations are
  issued against the Core `Table` (`_SLOT_TABLE`), so `synchronize_session` never
  re-evaluates a `WHERE` clause in Python; `read_slot` uses
  `populate_existing=True`; `TestAlreadyLoadedSessions` = 4 tests pass.

## Phase B acceptance — 43/43

Daily Vercel backstop (exactly one cron: `0 9 * * *` →
`/api/internal/maintenance/dispatch`); constant-time `CRON_SECRET` auth;
missing/invalid secret → **404**; bounded catch-up; missed-slot recovery;
schedule-vs-backstop race with **one winner**; one active execution per logical
slot; lease recovery; reconciliation; dispatch acceptance ≠ success; retry
classification; workflow completion handling; source attribution
(`github_schedule`, `manual`, `workflow_dispatch`, `external scheduler/backstop`
— asserted on the slot row, since a dispatched-but-not-yet-run slot has no run);
worker isolation; dispatcher never runs the worker; duplicate prevention; no
secret leakage.

**GitHub workflow invariants unchanged:**

    cron: '7 */12 * * *'      concurrency group: scholarzone-maintenance
    cancel-in-progress: false timeout-minutes: 90

## Contamination

Absent before every suite. Absent after the full regression, after the Phase A,
Phase B and combined suites when run with `SCHOLARZONE_ENVIRONMENT=test`.

It **does** appear when that variable is unset, and the creator is identified and
unrelated to this work:

    tests/test_autonomous_maintenance.py
      ::TestRunRecord::test_a_run_that_cannot_record_itself_reports_failure

It calls `worker.main([...])` without the `factory` fixture, so no
`SCHOLARZONE_DATABASE_URL` is set and `get_settings()` falls back to
`DEFAULT_DATABASE_URL` (`app/core/config.py:12`), producing a 532 KB file.
Proven both ways: `SCHOLARZONE_ENVIRONMENT` unset → created; `=test` (what CI
sets, which makes `conftest.py` default the URL to `sqlite:///:memory:`) → not
created. The test is **byte-identical on `origin/master`** — pre-existing, not
introduced here. Classified **PRE_EXISTING / ENVIRONMENTAL**, not a Phase A or
Phase B finding.

The removed file is gitignored (`.gitignore:10`), untracked, and was created by
these test runs in a throwaway worktree. Production writes: **NONE**.

## Lint and build

There is **no Python linter** in this repository — no `pyproject.toml`,
`setup.cfg`, `.flake8`, `ruff.toml` or `.pylintrc`, and no ruff/flake8/pylint/
black/mypy step in CI. The only `lint` job is frontend ESLint, out of scope.
`py_compile` passes on all 10 changed Python files.

Runnable gates, with the database URL pinned to a temp path (which also proves
the gates are not what creates the ambient file):

    import_smoke_test.py    32 passed, 0 failed
    schema_compat_check.py  SCHEMA COMPATIBILITY: PASS
    env_config_check.py     ENV CONFIG: PASS
    preflight.py            PRE-FLIGHT PASS - all gates passed

`docker build` **could not be executed — Docker is not installed on this
machine.** `preflight.py` SKIPs Docker Build, Artifact Startup, Readiness and API
Smoke for that reason and still passes. **The Docker gate is unvalidated.** This
is an environment limitation, not a code result, and is not counted as a pass.

## PostgreSQL

**POSTGRESQL_EQUIVALENCE = UNKNOWN.** Unchanged and not inferred from SQLite.
SQLite serialises writers under a database-wide lock; PostgreSQL resolves the
same guarded `UPDATE` under MVCC, where concurrent writers read the same row
version and the predicate is what rejects the loser. The guard test that fails if
the suite is ever pointed at `postgres://` is still present and still fires.

## Production writes

**NONE.** No Neon connection, no migration, no purge, no maintenance run. No
scholarship or image record touched. No deployment. Master unchanged at
`cfd0acaf`. Only PR #7's branch was pushed, by fast-forward.

## Final classification

**READY_FOR_OWNER_ACTIVATION**

- Candidate based on `cfd0acaf` (current master) — merge-base verified.
- Latest Phase A behavior integrated — 5 files byte-identical to `d194768`, plus
  documented conflict resolution in `models.py`/`database.py`.
- Phase A tests pass: 43 + 57 + 16 = 116.
- Phase B tests pass: 43. Combined maintenance: 236.
- Full regression: **zero new failures** against an executed master baseline
  (8/5239/10 vs 8/5080/10), every failure classified, no `UNKNOWN`.
- No test weakened. `py_compile` passes. All runnable build gates pass.
- No production writes.

**Not claimed:** the Docker gate is unvalidated (Docker absent), and PostgreSQL
equivalence remains UNKNOWN. Both are stated above rather than absorbed into a
pass.

Two pre-existing issues are recorded for follow-up and neither blocks
activation: the 8 obsolete `test_neon_migration.py` failures (gitignored
`migration_export.sql` missing), and `test_a_run_that_cannot_record_itself_reports_failure`
writing the ambient database when `SCHOLARZONE_ENVIRONMENT` is unset.

**PR #7 was not merged.** Head is `b55df30`, awaiting owner review.