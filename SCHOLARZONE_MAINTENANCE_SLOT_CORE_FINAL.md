# SCHOLARZONE_MAINTENANCE_SLOT_CORE_FINAL.md

## PARTIAL — pure core PROVEN, persistence layer NOT implemented

| | |
|---|---|
| Current master | `ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb` |
| Isolated worktree | `…\kilo\slotcore2` @ `ddcd9c3`, clean |
| Candidate SHA | **none — not committed** (see Remaining Blockers) |
| Shared worktree | untouched; another actor's local commit `8ac1c9a` preserved |
| Production writes | **NONE** |

## What is PROVEN (43 tests, executed, 0.50s)

**New file:** `backend/app/maintenance_slots.py` — pure logic, no DB, no network, no wall clock.
**New file:** `backend/tests/test_maintenance_slots.py` — 43 tests.

| Capability | Evidence |
|---|---|
| Deterministic slot identity | canonical form; **20/20 identical** on repeat; round-trip; naive datetime **rejected**; offset-aware **normalised** to UTC |
| `latest_due_slot` | 00:06→prev-day 12:07 · 00:07→00:07 · 00:08→00:07 · 12:06→00:07 · 12:07→12:07 · 12:08→12:07 · **13:00→12:07** |
| Calendar edges | month boundary, year boundary, **leap day** (`2028-02-29`, `2028-03-01`) |
| No phantom slots | `13:00` never invents a `13:07`; every result matches `SLOT_ID_RE` |
| State machine | **7 legal** transitions pass; **10 illegal** refused; terminal states have **zero** exits; no-op refused; all 7 states reachable from DUE |
| Source attribution | `external_scheduler_dispatch` ≠ `github_schedule`; all 5 sources present |
| Test isolation | ambient `backend/scholarzone.db` absent **before and after**; suite opens no engine |

The 13:00 case matters: a naive implementation would let an hourly misfire fabricate maintenance
periods that were never scheduled.

## NOT implemented — do not treat as proven

The **entire persistence layer** is absent:

- `maintenance_slots` table (models.py)
- `MaintenanceRun.slot_id` + **explicit** index
- idempotent `ALTER TABLE maintenance_runs ADD COLUMN IF NOT EXISTS slot_id` in `database.py`
- `ensure_slot`, `claim_slot`, `expire_stale_claims`
- **atomic claim, lease, recovery, idempotency, concurrency tests**

Therefore **VALIDATED LOCALLY** applies only to slot identity, state machine, and source semantics.
**Atomic claim, lease, idempotency, concurrency: NOT PROVEN.** PostgreSQL-equivalence: **UNKNOWN**
(not attempted).

Schema-evolution constraint carried forward: `create_all` creates the new table and its indexes, but
the `maintenance_runs.slot_id` column **and its index both need explicit idempotent creation** —
the codebase documents this at `database.py:170`.

## Why no candidate SHA

I ran out of budget mid-phase. Committing a branch that adds pure helpers with no persistence would
produce a "candidate" whose central claim — durable ownership — is untested. An uncommitted,
fully-passing 43-test core is more honest than a committed one that overstates completeness.

```
FINAL CLASSIFICATION:
    IMPLEMENTATION_BLOCKED

CURRENT MASTER:
    ddcd9c3662f4d3257d4f92e335fa7422e99ebdeb

MAINTENANCE_SLOTS:
    incomplete

MAINTENANCE_RUN_CORRELATION:
    incomplete

SCHEMA EVOLUTION:
    not implemented

SLOT IDENTITY:
    proven

STATE MACHINE:
    proven

ATOMIC CLAIM:
    not implemented

IDEMPOTENCY:
    not implemented

LEASE:
    not implemented

UTC SEMANTICS:
    proven

TEST ISOLATION:
    proven

CONCURRENCY:
    unknown

REGRESSION:
    not run (suite is additive; 3bf92b6 / 87ad84c untouched)

PRODUCTION WRITES:
    NONE

VERCEL CRON:
    NOT IMPLEMENTED — PHASE B

GITHUB DISPATCH:
    NOT IMPLEMENTED — PHASE B

OWNER ACTION:
    NONE FOR PHASE A

REMAINING BLOCKERS:
    1. Session budget exhausted mid-phase.
    2. Persistence layer unimplemented: table, MaintenanceRun.slot_id,
       explicit idempotent ALTER + explicit index, ensure_slot, claim_slot,
       expire_stale_claims, atomic-claim/lease/concurrency tests.
    3. Candidate not committed — worktree `…\kilo\slotcore2` holds the
       2 uncommitted files.
```

**Resumption point is exact:** `app/maintenance_slots.py` + its 43 passing tests are done and need
no rework. Everything remaining is persistence against that pure core.