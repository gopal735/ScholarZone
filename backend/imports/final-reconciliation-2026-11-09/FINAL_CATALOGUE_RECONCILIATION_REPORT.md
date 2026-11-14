# Final Catalogue Reconciliation Report

**Report date:** 2026-11-10
**Branch:** `feat/final-scholarship-catalogue-reconciliation`
**Base SHA:** `5b28ceef0480a4bd6612d1cf08c26e8629bea285`
**Pre-remediation HEAD:** `dec6dbcd65ffe98da42f0e6fff665c3c840ce04a`
**Package status:** **BLOCKED**
**Production import authorized:** no

## 1. Executive summary

The reconciliation package has been rebuilt from a read-only snapshot of the
local SQLite database (`backend/scholarzone.db`). The canonical package now
contains:

- **0 new inserts** — the canonical insert file is empty by design,
- **11 approved cycle updates**,
- **2 approved funding corrections**,
- **13 approved operations total**, every one backed by DIRECT evidence,
- **12 PENDING_RESEARCH operations excluded** from the approved set,
- **6 blocked new-insert candidates**,
- **5 duplicate pairs** — 4 archive-only plans for owner review and 1 blocked
  Fulbright pair,
- **0 duplicate plans executed**, **0 deletions**, **0 URL writes**,
  **0 funding writes**, and **0 FK reassignments**.

The package remains BLOCKED. The approved subset is internally consistent, but
lifecycle evidence is still pending, PostgreSQL duplicate simulation is
unavailable, the duplicate plans have not been executed, and six insert
candidates remain blocked.

## 2. Baseline

`package_baseline.json` is a committed snapshot of `backend/scholarzone.db` used
to keep CI reproducible. The database file itself is gitignored.

| Metric | Value |
|---|---:|
| Total scholarships | 830 |
| Active | 830 |
| Archived | 0 |
| Status `open` | 820 |
| Status `closed` | 6 |
| Status `closing-soon` | 4 |
| Database SHA256 | `c4737c7fce02c719caed1c4f95de0b2ded926e2a84c4bcbda16cddfb9b8a3adb` |
| Database size | 3,121,152 bytes |

## 3. Approved operations (13)

### 3.1 Cycle updates (11)

| Operation | ID | Field | Approved value |
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

The original CYCLE-516 proposal changed `title` to "Graduate". That claim could
not be supported, so the approved change is the supported `degree` value above.

### 3.2 Funding corrections (2)

| Operation | ID | Approved changes |
|---|---:|---|
| FUND-3 | 3 | `tuition_coverage=false`, `fully_funded=false`, funding = "Partially Funded (stipend, insurance, travel; tuition not covered)" |
| FUND-1 | 1 | `fully_funded=true`, funding = "Fully Funded (participation costs + travel/visa + living allowance)" |

FUND-3 also sets `tuition_coverage=false`; otherwise `fully_funded=false` would
contradict the existing `tuition_coverage=true`.

### 3.3 Evidence contract

Every approved operation maps to one of the 13 records in
`final_source_evidence.json`. Each record has:

- a scalar `https://` source URL,
- an exact supported claim (at least 30 characters),
- an ISO 8601 `retrieved_at` date,
- a unique `evidence_ref` whose `operation_id` matches the operation,
- a `supports_fields` list that exactly matches the changed fields,
- `approved_for_import=true`.

Live pages were re-verified on 2026-11-10 for Erasmus, DAAD programmes
50026200 / 50076777 / 57135744 / 57135742 / 50109971, GKS, MEXT,
Knight-Hennessy, and the Taiwan Huayu programme.

## 4. Pending and blocked work

### 4.1 PENDING_RESEARCH (12, excluded)

| Type | Count |
|---|---:|
| Cycle updates | 7 |
| Funding corrections | 3 |
| Lifecycle proposals | 2 |
| **Total** | **12** |

Pending operations have `approved_for_import=false`, no evidence reference, and
no approved changes. They are counted separately and never included in the 13.

### 4.2 Lifecycle proposals (2, not approved)

| Operation | ID | Programme | Proposed contract |
|---|---:|---|---|
| LIFECYCLE-729 | 729 | Vanier Canada Graduate Scholarship | `status=closed`, `is_archived=true`, preserve existing `archived_at` or set at execution, explicit `archived_reason` |
| LIFECYCLE-31 | 31 | Netherlands Fellowship Programme (NFP/OTS) | Same archive contract |

Both remain PENDING_RESEARCH because discontinuation has not been captured as
DIRECT evidence. The package does not use `corrected_status`, does not use a
`discontinued` status value, and does not delete either record.

### 4.3 Blocked inserts (6)

`blocked_records.json` contains six new-scholarship candidates that cannot be
imported because evidence is insufficient or the region is excluded. All have
`approved_for_import=false` and `final_evidence_status=BLOCKED`.

## 5. Duplicate reconciliation

### 5.1 Pairs

| Pair | Canonical | Duplicate | Classification |
|---:|---:|---:|---|
| 1 | 183 | 753 | MERGE_READY_FOR_OWNER_REVIEW |
| 2 | 270 | 1244 | MERGE_READY_FOR_OWNER_REVIEW |
| 3 | 396 | 1279 | MERGE_READY_FOR_OWNER_REVIEW |
| 4 | 482 | 1280 | MERGE_READY_FOR_OWNER_REVIEW |
| 5 | 1217 | 1309 | BLOCKED_MANUAL_REVIEW (Fulbright) |

### 5.2 Archive-only plan

Each merge-ready pair has exactly one `ARCHIVE_DUPLICATE` operation. It writes
only `is_archived`, `archived_at`, and `archived_reason` on the duplicate row,
with the idempotency predicate `WHERE id = :duplicate_id AND is_archived = 0`.
There are no `DELETE` or `INSERT` statements, no `official_source_url` writes,
no `json_group_array()` / `json_group_object()` assignments, and no funding,
degree, region, or status resolution.

The Fulbright pair is blocked because the two records are not a safe duplicate
merge: the plan cannot reconcile the programme identity without manual owner
review. It has no write operations and is not executable.

### 5.3 FK dependency reconciliation

Actual database introspection found:

| Metric | Value |
|---|---:|
| Declared dependent tables | 14 |
| Declared FK references | 14 |
| FK reference rows for the 5 pair IDs | 10 |
| Duplicate-side FK rows | 5 |
| Merge-ready duplicate-side rows | 4 |
| Fulbright duplicate-side rows | 1 |
| Safe reassignments | 0 |
| Rows to reassign | 0 |
| Unique collisions if merge-ready reassigned | 4 |
| Unique collisions if all pairs reassigned | 5 |
| Append-only non-FK table | `scholarship_image_audit` (1 row) |

The old report claimed 13 dependent tables and 20 FK references. That was
incorrect and has been replaced by the introspection-backed counts above.

All 10 pair IDs have one `scholarship_supervisor_coverage` row each. Because the
table has `UNIQUE(scholarship_id)`, reassigning a duplicate-side coverage row to
the canonical ID would collide. The plan therefore keeps all coverage rows with
the archived duplicate and performs zero reassignments.

`scholarship_image_audit` is append-only, has no FK, and its single row on
canonical ID 285 is documented separately; it is never moved or deleted.

### 5.4 Isolated SQLite dry run

| Metric | Before | After |
|---|---:|---:|
| Total | 830 | 830 |
| Active | 830 | 826 |
| Archived | 0 | 4 |
| Coverage rows | 830 | 830 |
| `official_source_url` arrays | 0 | 0 |

- 4 pairs tested, 4 passed, 4 rows archived.
- 4 uniqueness collision probes all returned `UNIQUE_COLLISION`.
- 0 rows deleted, 0 URL/funding/degree/region/status writes.
- Source database SHA unchanged; 0 merges executed in source.

**PostgreSQL simulation: UNAVAILABLE.** No disposable DSN, `psql`, PostgreSQL
service, or Docker was available. The package records this as unavailable and
does not claim a PostgreSQL pass.

## 6. Count reconciliation

| State | Total | Active | Archived | Status distribution |
|---|---:|---:|---:|---|
| Baseline | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved subset | 830 | 830 | 0 | open 820, closed 6, closing-soon 4 |
| After approved + lifecycle proposals | 830 | 828 | 2 | open 818, closed 8, closing-soon 4 |
| After approved + lifecycle + 4 duplicate archives | 830 | 824 | 6 | open 818, closed 8, closing-soon 4 |

Archive accounting: lifecycle archives = 2, duplicate archives = 4, total = 6,
and total = active + archived at every step. No archive is counted twice.
Fulbright is not included in the four duplicate archives.

## 7. Canonical and legacy files

Canonical files are prefixed with `final_` or are the named duplicate reports.
`final_import_ready_scholarships.json` is canonical and contains `[]`.
`final_existing_cycle_updates.json` contains only the 11 evidence-passing
records. `final_lifecycle_corrections.json` is a wrapper object with two
PENDING_RESEARCH proposals.

The eight old unprefixed files were moved to `legacy/import-files/`. Each is
marked `SUPERSEDED`, `importable=false`, and points to its canonical
replacement. `legacy/README.md` states that the archive is superseded and not
importable. The validator fails if any legacy file remains at the package root.

## 8. Automated validation

`validate_semantics.py` loads the canonical JSON and fails on:

- unsupported lifecycle status or missing archive fields,
- missing DIRECT evidence for an approved operation,
- a PENDING_RESEARCH operation marked approved,
- URL arrays or URL rewrites in the duplicate plan,
- an incomplete FK map or inconsistent FK totals,
- contradictory canonical and legacy files,
- inconsistent projected counts,
- manifest count or hash mismatch.

Run results:

```text
python validate_semantics.py
semantic_validation = PASS
error_count = 0
package_status = BLOCKED
postgresql_simulation = UNAVAILABLE

python validate_semantics.py --self-test
SELF-TEST PASSED: 10 mutation checks caught.
```

## 9. Blocking reasons

1. Vanier CGS (729) and NFP/OTS (31) lifecycle proposals remain PENDING_RESEARCH.
2. PostgreSQL duplicate-merge simulation is unavailable in this environment.
3. No duplicate merge has been executed; 4 archive-only plans await owner approval.
4. Six new-insert candidates remain blocked.
5. This package is a review package, not production import authorization.

## 10. Safety statement

No production database was written. No production migration was run. No
duplicate merge was executed. No scholarship record was deleted. No unrelated
feature was modified. PR #81 must not be merged on the basis of this package
alone.
