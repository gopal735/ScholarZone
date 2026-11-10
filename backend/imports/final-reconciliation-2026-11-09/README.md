# Final Scholarship Catalogue Reconciliation Package

**Package date:** 2026-11-10
**Branch:** `feat/final-scholarship-catalogue-reconciliation`
**Base SHA:** `5b28ceef0480a4bd6612d1cf08c26e8629bea285`
**Pre-remediation HEAD:** `dec6dbcd65ffe98da42f0e6fff665c3c840ce04a`
**Package status:** **BLOCKED**
**Review package only:** yes
**Production import authorized:** no

This directory is the authoritative reconciliation package for PR #81. It is a
review artefact, not an import authorization. Nothing here has been executed
against a production database, and no duplicate merge has been run.

## Canonical files

| File | Records | Importable | Purpose |
|---|---:|---|---|
| `final_import_ready_scholarships.json` | 0 | yes | Canonical insert file; empty by design. |
| `final_existing_cycle_updates.json` | 11 | yes | Approved cycle updates, all DIRECT evidence. |
| `final_funding_corrections.json` | 2 | yes | Approved funding corrections, all DIRECT evidence. |
| `final_lifecycle_corrections.json` | 2 | no | Proposals only; PENDING_RESEARCH, not approved. |
| `final_source_evidence.json` | 13 | no | DIRECT evidence registry for the approved subset. |
| `operation_evidence_mapping.json` | 25 | no | 13 approved operations + 12 excluded pending operations. |
| `blocked_records.json` | 6 | no | Blocked new-insert candidates. |
| `duplicate_merge_plan.json` | 5 pairs | no | 4 archive-only plans for owner review; 1 blocked Fulbright pair. |
| `duplicate_fk_dependency_report.json` | 14 tables | no | Actual FK introspection for all dependent tables. |
| `duplicate_merge_dry_run.json` | 4 pairs | no | Isolated SQLite simulation; PostgreSQL simulation unavailable. |
| `final_database_reconciliation.json` | 1 | no | Before/after counts with archive accounting. |
| `final_reconciliation_manifest.json` | 1 | no | Package manifest and file hashes. |
| `final_import_validation_report.json` | 1 | no | Generated semantic-validation result. |

`package_baseline.json` is the committed read-only snapshot of
`backend/scholarzone.db` used by CI. The database file itself is gitignored.

## Operation counts

- Approved: **13** — 11 cycle updates, 2 funding corrections, 0 inserts, 0 lifecycle archives.
- Pending and excluded: **12** — 7 cycle, 3 funding, 2 lifecycle.
- Blocked insert candidates: **6**.
- Duplicate pairs: **5** — 4 merge-ready for owner review, 1 blocked (Fulbright 1217/1309).
- Duplicate plans approved or executed: **0**.

## Lifecycle contract

`final_lifecycle_corrections.json` uses the real `Scholarship` model contract:

```json
{
  "status": "closed",
  "is_archived": true,
  "archived_at": {"action": "PRESERVE_EXISTING", "when_null": "SET_AT_EXECUTION_TIMESTAMP"},
  "archived_reason": "..."
}
```

There is no `discontinued` status and no `corrected_status` field. The two
proposals (Vanier CGS ID 729, NFP/OTS ID 31) remain PENDING_RESEARCH, are
excluded from approved counts, and are not importable.

## Duplicate policy

The duplicate plan is archive-only:

- no record deletions,
- no `official_source_url` writes,
- no URL arrays or `json_group_array()` scalar assignments,
- no funding, degree, region, or status resolution,
- no FK reassignment.

All four merge-ready pairs have a `UNIQUE(scholarship_id)` collision in
`scholarship_supervisor_coverage` if coverage rows were reassigned, so the rows
stay attached to the archived duplicate. `scholarship_image_audit` is
append-only, has no FK, and is never reassigned.

## Count model

| State | Total | Active | Archived | Status distribution |
|---|---:|---:|---:|---|
| Baseline | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved subset | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved + lifecycle proposals | 830 | 828 | 2 | open 818, closed 8, closing-soon 4 |
| After approved + lifecycle + 4 duplicate archives | 830 | 824 | 6 | open 818, closed 8, closing-soon 4 |

Lifecycle archives (2) and duplicate archives (4) are counted separately;
6 = 2 + 4 with no double counting. Total always equals active + archived.

## Reproduce

```bash
cd backend/imports/final-reconciliation-2026-11-09
python build_canonical_package.py --baseline-only
python reconcile_duplicates.py
python build_canonical_package.py
python validate_semantics.py
python validate_semantics.py --self-test
```

`build_canonical_package.py` reads `package_baseline.json`, not a live database.
`reconcile_duplicates.py` requires the committed baseline and writes only
package JSON, never the source database.

## Legacy files

The eight unprefixed files from the superseded package were moved to
`legacy/import-files/`. They are SUPERSEDED and not importable; see
`legacy/README.md` and `legacy/import-files/manifest.json`.

## Why the package is blocked

1. Vanier CGS (729) and NFP/OTS (31) lifecycle proposals still lack DIRECT discontinuation evidence.
2. PostgreSQL duplicate-merge simulation is unavailable in this environment.
3. No duplicate merge has been executed; the 4 archive-only plans await owner approval.
4. Six new-insert candidates remain blocked for insufficient evidence or excluded region.
5. This is a review package, not production import authorization.
