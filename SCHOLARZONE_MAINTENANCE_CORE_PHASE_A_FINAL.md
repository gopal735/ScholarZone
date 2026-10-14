# SCHOLARZONE — MAINTENANCE RELIABILITY CORE, PHASE A

---

## Actual master SHA
`ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` — re-fetched at start; unmoved. Branch `feat/maintenance-slot-core` from a clean isolated worktree; the shared dirty worktree was never touched.

## Candidate SHA
`d8d6697fe4a42bfdfb2d6af6438a72095be4d639`, parent `ddcd9c3`. **Not merged, not pushed, not deployed.**

## Changed files (all REQUIRED or TEST)
| file | class |
|---|---|
| `backend/app/services/maintenance_slot.py` | REQUIRED (new, 406 lines) |
| `backend/app/models.py` | REQUIRED (+35: nullable slot columns, unique index) |
| `backend/app/database.py` | MIGRATION (+57: additive idempotent `ensure_maintenance_slot_columns`) |
| `backend/tests/test_maintenance_slot_core.py` | TEST (new, 333 lines) |
| `.github/workflows/verification-cron.yml` | REQUIRED (+16: two optional inputs) |

No UNRELATED modifications.

## MaintenanceRun reuse decision — **reused and extended**
`MaintenanceRun` is the only maintenance persistence; `backend/app/services/maintenance_run_log.py` is the only writer. A new scheduler table would have been duplicate state, so the invariant it cannot represent (deterministic slot identity + unique active claim) was added as **nullable columns**. Existing rows keep `slot_id = NULL`; SQL permits many NULLs in a unique constraint, so historic data and the existing meaning of `run_id` / `status` / `stages` are untouched. No second table.

## Schema changes / migration
`slot_id` (VARCHAR 64, **unique**), `slot_status`, `slot_due_at`, `logical_source`, `transport_event`, `claimed_at`, `lease_until`, `claim_owner`. Additive, idempotent (`ADD COLUMN IF NOT EXISTS`, `CREATE UNIQUE INDEX IF NOT EXISTS`), wired into **both** `_upgrade_sqlite_schema` and `_upgrade_postgresql_schema`. **Migration validated against a temporary legacy-shaped table; NOT executed against Neon. No production backfill.**

## Slot ID definition — **PROVEN**
`maint-slot-<YYYYMMDDTHHMM>Z` for the most recent due slot at or before `as_of`. Schedule `7 */12 * * *` → `00:07Z` and `12:07Z`. Pure function of the due instant: no UUID, process id, hostname, request id or execution timestamp. A request at 12:40 resolves to the 12:07 slot. 50 repeated computations → 1 distinct id.

## State machine — **PROVEN**
`DUE, CLAIMED, DISPATCHED, RUNNING, SUCCEEDED, FAILED, EXPIRED`. Transitions declared once in `TRANSITIONS` and enforced centrally by `require_transition`. `SUCCEEDED`/`FAILED` terminal. `CLAIMED → EXPIRED` on lease lapse, `EXPIRED → CLAIMED` for explicit recovery — never a silent return to `DUE`. **8 legal transitions tested, 16 illegal transitions refused.**

## Atomic claim — **PROVEN (SQLite-verified)**
`slot_id` is nullable-UNIQUE, so the **database** is the serialisation authority; the loser of a race gets `IntegrityError` and re-reads the winner. There is no check-then-insert path. **8 concurrent threads on one slot → exactly 1 winner, 0 duplicate active owners.**
**Not production-equivalent:** verified on SQLite. PostgreSQL equivalent locking behaviour was **not** exercised (no Neon writes permitted), so the PostgreSQL claim path is UNKNOWN by execution, though the mechanism is the same unique index.

## Idempotency — **PROVEN**
`get_or_create_slot` returns the same row for repeated calls (created=True then False). Same-owner re-claim returns `already-claimed-by-owner`. A terminal slot cannot be re-claimed.

## Lease — **PROVEN**
`claimed_at` / `lease_until` / `claim_owner`. Active lease cannot be stolen (`lease-active`). Expired lease → explicit `EXPIRED`, then recoverable. Two recovery attempts after expiry → one owner.

## UTC semantics — **PROVEN**
`as_of` always injected; naive timestamps **refused** (`ValueError`). Non-UTC input normalised by instant. Boundaries tested: 00:06/00:07/00:08, 12:06/12:07/12:08/13:00, month, year, **leap day 2024-02-29**, year-end 2025-12-31T23:59. No DST logic added.

## Source attribution — **PROVEN**
`logical_source` (why) and `transport_event` (what carried it) are separate columns. `schedule → github_schedule`; an explicit `external_scheduler_dispatch` **survives** a `workflow_dispatch` transport; `manual` stays distinguishable; unknown source refused. The schema never derives one from the other.

## Workflow metadata — **PROVEN**
Two **optional** inputs (`logical_source`, `transport_event`). Preserved exactly: cron `7 */12 * * *`, concurrency group `scholarzone-maintenance`, `cancel-in-progress: false`, `timeout-minutes: 90`. YAML parses; jobs unchanged (`maintain`, `retry`). No GitHub token required.

## Contamination root cause / result — **PROVEN**
Root cause from the earlier audit: release-relevant tests could depend on ambient `backend/scholarzone.db`. Result here: every slot test uses an isolated SQLite file under `tmp_path` and the fixture **asserts `backend/scholarzone.db` presence is unchanged** before/after. Verified absent after the suite. No import-time DB creation.

## Test results
| suite | result |
|---|---|
| `test_maintenance_slot_core.py` | **57 passed** |
| slot core + `test_maintenance_worker` + `test_autonomous_maintenance` + `test_maintenance_image_constants` + `test_final_scheduler_safety` | **142 passed** |

`3bf92b6` (ingestion null-refresh) and `87ad84c` (purge accepted image) untouched and green. Public-visibility behaviour unmodified.

## Known limitations
- PostgreSQL claim path **not executed** (no Neon writes) — SQLite-verified only.
- The worker does **not yet** consume `SCHOLARZONE_LOGICAL_SOURCE` at runtime; the columns, API and workflow inputs exist, wiring the recorder is the Phase B integration point.
- Recovery sweeper (`expire_stale_claims`) is **not yet scheduled** by anything.

## Production writes
**NONE**

---

FINAL CLASSIFICATION:
READY_FOR_PHASE_B

CORE IMPLEMENTATION:
complete

MaintenanceRun:
reused (extended with nullable slot columns; no duplicate scheduler table)

ATOMIC CLAIM:
proven

IDEMPOTENCY:
proven

LEASE:
proven

UTC SLOT IDENTITY:
proven

TEST ISOLATION:
proven

CONCURRENCY:
not production-equivalent (SQLite-verified: 8 contenders → 1 winner; PostgreSQL not exercised)

PRODUCTION WRITES:
NONE

VERCEL CRON:
NOT IMPLEMENTED — PHASE B

GITHUB DISPATCH:
NOT IMPLEMENTED — PHASE B

OWNER ACTION:
NONE FOR PHASE A

REMAINING BLOCKERS:
none for Phase A; PostgreSQL-equivalent claim verification and recorder wiring deferred to Phase B