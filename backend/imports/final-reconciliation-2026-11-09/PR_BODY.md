## Summary

This PR replaces the earlier reconciliation package with a **blocked review
package** for the final scholarship catalogue reconciliation. It corrects the
lifecycle model contract, duplicate/FK handling, evidence scope, canonical file
set, projected counts, validation, and documentation.

**This is a review package. It is not production import authorization.** No
production database was written, no migration was run, and no duplicate merge
was executed.

- **Branch:** `feat/final-scholarship-catalogue-reconciliation`
- **Base SHA:** `5b28ceef0480a4bd6612d1cf08c26e8629bea285`
- **Pre-remediation HEAD:** `dec6dbcd65ffe98da42f0e6fff665c3c840ce04a`
- **Package status:** `BLOCKED`
- **Production import authorized:** `false`

## What changed

### Canonical package

The authoritative package is
`backend/imports/final-reconciliation-2026-11-09/`.

| File | Records | Importable | Purpose |
|---|---:|---|---|
| `final_import_ready_scholarships.json` | 0 | yes | Canonical insert file; empty by design |
| `final_existing_cycle_updates.json` | 11 | yes | Approved cycle updates, all DIRECT evidence |
| `final_funding_corrections.json` | 2 | yes | Approved funding corrections, all DIRECT evidence |
| `final_lifecycle_corrections.json` | 2 | no | PENDING_RESEARCH proposals, not approved |
| `final_source_evidence.json` | 13 | no | DIRECT evidence registry |
| `operation_evidence_mapping.json` | 25 | no | 13 approved + 12 excluded pending |
| `blocked_records.json` | 6 | no | Blocked insert candidates |
| `duplicate_merge_plan.json` | 5 pairs | no | 4 archive-only plans, 1 blocked Fulbright pair |
| `duplicate_fk_dependency_report.json` | 14 tables | no | Actual FK introspection |
| `duplicate_merge_dry_run.json` | 4 pairs | no | Isolated SQLite simulation |
| `final_database_reconciliation.json` | 1 | no | Before/after counts with archive accounting |
| `final_reconciliation_manifest.json` | 1 | no | Manifest and hashes |

The eight old unprefixed files were moved to `legacy/import-files/` and marked
`SUPERSEDED` / `importable=false`. `legacy/README.md` states that the archive is
not importable.

### Lifecycle contract

Lifecycle proposals now use the real `Scholarship` model contract:

- `status="closed"`,
- `is_archived=true`,
- explicit `archived_reason`,
- `archived_at` policy: preserve existing value, or set at execution when null.

The unsupported `discontinued` status and the legacy `corrected_status` field
are gone. Vanier CGS (729) and NFP/OTS (31) remain `PENDING_RESEARCH`,
`approved_for_import=false`, and are excluded from all approved counts.

### Evidence

Exactly **13 operations** are approved: 11 cycle updates (`CYCLE-1, 3, 4, 5,
23, 231, 232, 234, 516, 1312, 1336`) and 2 funding corrections (`FUND-3`,
`FUND-1`). Each has a scalar https source URL, an exact supported claim, an ISO
8601 retrieval date, and a matching evidence reference.

The original CYCLE-516 title claim ("Graduate") was unsupported and is replaced
with a supported `degree` change. FUND-3 also sets `tuition_coverage=false` so
that `fully_funded=false` is internally consistent.

The other **12 operations** are `PENDING_RESEARCH` and excluded. The six new
inserts are blocked and are not part of this package.

### Duplicate and FK remediation

- 5 pairs total: 4 `MERGE_READY_FOR_OWNER_REVIEW`, 1 `BLOCKED_MANUAL_REVIEW`
  (Fulbright canonical 1217 / duplicate 1309).
- Archive-only plans: only `is_archived`, `archived_at`, and `archived_reason`
  are written for one duplicate row.
- No deletions, URL writes, funding/degree/region/status resolution, or FK
  reassignment.
- Actual introspection: **14 dependent tables, 14 FK references, 10 reference
  rows** across the 5 pair IDs (5 duplicate-side: 4 merge-ready + 1 Fulbright).
- `scholarship_supervisor_coverage` has `UNIQUE(scholarship_id)`; all four
  merge-ready pairs would collide on reassignment, so duplicate-side coverage
  rows stay with the archived duplicate.
- `scholarship_image_audit` is append-only, has no FK, and is never reassigned.
- The old 13-table / 20-reference claim was incorrect and is superseded.

### Counts

| State | Total | Active | Archived | Status distribution |
|---|---:|---:|---:|---|
| Baseline | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved subset | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved + lifecycle proposals | 830 | 828 | 2 | open 818, closed 8, closing-soon 4 |
| After approved + lifecycle + 4 duplicate archives | 830 | 824 | 6 | open 818, closed 8, closing-soon 4 |

Lifecycle archives (2) and duplicate archives (4) are counted separately:
6 = 2 + 4, with no double counting. Total = active + archived at every step.

### Validation

`backend/imports/final-reconciliation-2026-11-09/validate_semantics.py` fails on:

- unsupported lifecycle status or missing archive fields,
- approved operation without DIRECT evidence,
- PENDING_RESEARCH operation marked approved,
- unsafe URL arrays or URL writes,
- incomplete FK map or inconsistent FK totals,
- contradictory canonical/legacy files,
- inconsistent projected counts or manifest hashes.

Local results:

```text
python validate_semantics.py
semantic_validation = PASS, error_count = 0, package_status = BLOCKED

python validate_semantics.py --self-test
SELF-TEST PASSED: 10 mutation checks caught.
```

The duplicate simulation ran on an isolated SQLite copy: 4/4 pairs passed,
830/830/0 → 830/826/4, coverage 830 → 830, 0 URL arrays, 4/4 UNIQUE collision
probes, source DB SHA unchanged. **PostgreSQL simulation is UNAVAILABLE** — no
disposable DSN, PostgreSQL client/server, or Docker is available; this is not
reported as a pass.

## Why this PR remains BLOCKED

1. Vanier CGS and NFP/OTS lifecycle proposals still lacks DIRECT evidence.
2. PostgreSQL duplicate-merge simulation is unavailable.
3. No duplicate merge has been executed; 4 archive-only plans await owner approval.
4. Six new-insert candidates remain blocked.
5. This is a review package, not production import authorization.

## Test plan

- [ ] `python backend/imports/final-reconciliation-2026-11-09/validate_semantics.py`
- [ ] `python backend/imports/final-reconciliation-2026-11-09/validate_semantics.py --self-test`
- [ ] `pytest backend/tests/test_final_reconciliation_package.py`
- [ ] Exact-HEAD CI workflow passes (see `CI_EVIDENCE.md`)

## Safety

- No production database writes
- No production migration
- No duplicate merge execution
- No scholarship record deletion
- No unrelated feature changes
- PR must not be merged on the basis of this package alone

## References

- Package: `backend/imports/final-reconciliation-2026-11-09/`
- Status: `backend/imports/final-reconciliation-2026-11-09/PACKAGE_STATUS.md`
- CI evidence: `backend/imports/final-reconciliation-2026-11-09/CI_EVIDENCE.md`
- PR: #81
