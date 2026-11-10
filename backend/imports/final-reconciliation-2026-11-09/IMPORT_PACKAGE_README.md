# Import Package README

**ScholarZone final scholarship catalogue reconciliation**
**Package date:** 2026-11-10
**Status:** **BLOCKED — review package only, not import authorization**

This package supersedes the earlier 6-insert / 19-cycle / 5-funding proposal.
Those unprefixed files now live in `legacy/import-files/` and are not importable.

## 1. What is approved

Exactly **13 operations** have DIRECT evidence and `approved_for_import=true`:

### Cycle updates (11)

| Operation | Catalogue ID | Changed field | Approved value |
|---|---:|---|---|
| CYCLE-1 | 1 | `title` | Erasmus Mundus Joint Masters (EMJM) |
| CYCLE-3 | 3 | `application_period` | Annual second-quarter update; applications possible from 1 June to the stated deadline |
| CYCLE-4 | 4 | `degree` | Undergraduate Degrees (including Associate Degree), Graduate Degrees (Master's and Doctoral Degrees) |
| CYCLE-5 | 5 | `degree` | Research, teacher training, undergraduate, Japanese studies, college of technology, specialized training, and YLP students |
| CYCLE-23 | 23 | `duration` | 12 to 42 months (dependent on study programme) |
| CYCLE-231 | 231 | `title` | Study Scholarships - Postgraduate Studies in the Field of Architecture |
| CYCLE-232 | 232 | `title` | Study Scholarships - Postgraduate Studies in the Fields of Fine Art, Design, Visual Communication and Film |
| CYCLE-234 | 234 | `title` | Study Scholarships - Postgraduate Studies in the Field of the Performing Arts |
| CYCLE-516 | 516 | `degree` | Undergraduate Degrees (including Associate Degree) |
| CYCLE-1312 | 1312 | `title` | Knight-Hennessy Scholars at Stanford University |
| CYCLE-1336 | 1336 | `title` | Huayu Enrichment Scholarship Program |

### Funding corrections (2)

| Operation | Catalogue ID | Changed fields | Approved values |
|---|---:|---|---|
| FUND-3 | 3 | `tuition_coverage`, `fully_funded`, `funding` | `false`, `false`, "Partially Funded (stipend, insurance, travel; tuition not covered)" |
| FUND-1 | 1 | `fully_funded`, `funding` | `true`, "Fully Funded (participation costs + travel/visa + living allowance)" |

Every approved operation points to one of the 13 records in
`final_source_evidence.json`. Each evidence record contains a scalar https
source URL, an exact supported claim of at least 30 characters, an ISO 8601
retrieval date, and a unique `evidence_ref`.

## 2. What is not approved

- **0 new inserts.** `final_import_ready_scholarships.json` is `[]` by design.
- **12 PENDING_RESEARCH operations are excluded**: 7 cycle, 3 funding, 2 lifecycle.
- **6 new-insert candidates are blocked** in `blocked_records.json`.
- **2 lifecycle proposals are not approved**: Vanier CGS (729) and NFP/OTS (31).
- **No duplicate merge is approved or executed.**

## 3. Lifecycle proposals

`final_lifecycle_corrections.json` is a wrapper object, not a bare list. Both
proposals use the actual model contract:

```json
{
  "status": "closed",
  "is_archived": true,
  "archived_at": {
    "action": "PRESERVE_EXISTING",
    "when_null": "SET_AT_EXECUTION_TIMESTAMP"
  },
  "archived_reason": "..."
}
```

`discontinued` is not a valid package status. `corrected_status` must not be
used. Both proposals have `approved_for_import=false`,
`evidence_status=PENDING_RESEARCH`, no evidence reference, and no approved
changes.

## 4. Duplicate plan

`duplicate_merge_plan.json` contains 5 pairs:

- 4 `MERGE_READY_FOR_OWNER_REVIEW` archive-only plans (pairs 1–4),
- 1 `BLOCKED_MANUAL_REVIEW` Fulbright pair (canonical 1217, duplicate 1309).

Each merge-ready plan contains exactly one `ARCHIVE_DUPLICATE` operation writing
only `is_archived`, `archived_at`, and `archived_reason` for one row. The plan
performs **0** deletions, URL writes, funding writes, degree writes, region
writes, status changes, or FK reassignments.

`scholarship_supervisor_coverage` has `UNIQUE(scholarship_id)`. Every merge-ready
pair would collide if its coverage row were reassigned, so all duplicate-side
rows stay with the archived duplicate. `scholarship_image_audit` is append-only,
has no FK, and is never reassigned.

## 5. Foreign keys

`duplicate_fk_dependency_report.json` is based on actual database introspection:

- 14 declared dependent tables,
- 14 declared FK references,
- 10 reference rows across the 5 pair IDs,
- 5 duplicate-side rows (4 merge-ready + 1 Fulbright),
- 0 safe reassignments and 0 rows to reassign.

The old claim of 13 dependent tables and 20 FK references was wrong and is
superseded.

## 6. Dry run

`duplicate_merge_dry_run.json` records an isolated SQLite copy simulation:

- 4 pairs tested, 4 passed, 4 rows archived,
- 830/830/0 baseline → 830/826/4 after simulation,
- coverage rows unchanged at 830,
- 0 URL arrays before and after,
- 4 UNIQUE collision probes all returned `UNIQUE_COLLISION`,
- source database SHA unchanged and 0 merges executed in source.

PostgreSQL simulation is **UNAVAILABLE**: no disposable DSN, PostgreSQL
client/server, or Docker is available. This is recorded as unavailable, not as
a pass.

## 7. Count model

| State | Total | Active | Archived |
|---|---:|---:|---:|
| Baseline | 830 | 830 | 0 |
| After approved subset | 830 | 830 | 0 |
| After approved + lifecycle proposals | 830 | 828 | 2 |
| After approved + lifecycle + 4 duplicate archives | 830 | 824 | 6 |

`830 = active + archived` at every step. Lifecycle archives (2) and duplicate
archives (4) are reported separately, so the 6 archives are not double-counted.

## 8. Execution rules for a future approved run

This package must not be executed as-is.

1. Obtain explicit owner approval for each operation and each duplicate plan.
2. Capture DIRECT discontinuation evidence for the two lifecycle proposals.
3. Run the archive-only duplicate updates and UNIQUE collision probes on an
   isolated PostgreSQL 16/18 database and attach the log.
4. Import in this order if later authorized: approved cycle updates, approved
   funding corrections — never the pending or blocked records.
5. Do not delete scholarship rows, rewrite URL fields, or auto-resolve funding.
6. Do not run any production migration or production database write.

## 9. Validation

Run from this directory:

```bash
python validate_semantics.py
python validate_semantics.py --self-test
```

A passing validation means the package is internally consistent and remains
BLOCKED. It does not authorize import. `final_import_validation_report.json`
is the generated machine-readable result.
