# MANUAL 31-ROW DELETION PROVENANCE AUDIT REPORT

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **CURRENT_ROWS** | 691 |
| **MISSING_IDS** | 31 |
| **EXACT_31_SET_MATCH** | **YES** |
| **ID_451_BLOCKED** | **YES** (archived) |
| **RETENTION_DELETIONS** | 0 |
| **MANUAL_CLEANUP_DELETIONS** | **NO DOCUMENTED EVIDENCE** |
| **ADDITIONAL_MISSING_ROWS** | 0 |
| **FINAL CLASSIFICATION** | **UNABLE_TO_PROVE** |

---

## TASK 1: REPOSITORY SEARCH FOR MANUAL CLEANUP EVIDENCE

### Files Searched
- All `.md` reports (40+ files)
- All backend scripts (`backend/scripts/*.py`)
- Maintenance run logs (`maintenance_runs` table)
- Configuration files (`backend/config/*.json`)
- Test reports and logs

### Search Terms Used
- "31", "closed scholarships", "delete candidates", "blocked", "451"
- "deleted IDs", "production write", "manual cleanup"
- "SAFE_DELETE", "retention", "deletion_manifest"

### Findings

**NO EXPLICIT MANUAL CLEANUP MANIFEST FOUND** containing:
- The exact 31 IDs listed
- A deletion report naming these 31 IDs
- A script/command that deleted these 31 IDs
- A maintenance run with a "delete" stage

### Relevant Evidence Found

| Source | Finding |
|--------|---------|
| `closed_record_audit.py` | Read-only audit that classifies closed records; identifies **31 SAFE_DELETE** candidates matching exactly the 31 missing IDs |
| `check_audit_safe_delete.py` | CI guard that fails if SAFE_DELETE > 0; does NOT delete |
| `maintenance_runs` table | Last run: **2026-10-04 11:20:49** (stages: retire, repair_list_columns, logos). **No runs after snapshot date 2026-10-05 14:39:34** |
| `retention_dry_run.py` | Deletion requires `--execute-delete --recovery-path --confirm-ids` — **never executed** per all reports |
| `purged_records_archive.json` | Collector's archive of 151 records (archived/closed), **not a deletion manifest** |
| All retention reports | **Consistently report: RETENTION_DELETIONS = 0, PRODUCTION_WRITES = NONE** |

---

## TASK 2: PER-ID ANALYSIS

### The 31 IDs in Pre-Cleanup Snapshot (`scholarzone.pre_integrity_repair_20261005_143934.db`)

| ID | Title | Status | Archived | Deadline | del_protected | Current DB |
|----|-------|--------|----------|----------|---------------|------------|
| 6 | Eiffel Excellence Scholarship | closed | 0 | 2026-01-08 | 0 | ABSENT |
| 7 | Swiss Government Excellence (ESKAS) | closed | 0 | NULL | 0 | ABSENT |
| 22 | DAAD STEM Study Scholarships | closed | 0 | 2026-08-31 | 0 | ABSENT |
| 29 | Commonwealth Scholarship | closed | 0 | 2026-10-20 | 0 | ABSENT |
| 38 | Vanier Canada Graduate Scholarship | closed | 0 | NULL | 0 | ABSENT |
| 91 | Paris-Saclay IDEX International | closed | 0 | 2026-03-25 | 0 | ABSENT |
| 142 | STAR Scholarships Foundation+Bachelor | closed | 0 | 2026-03-30 | 0 | ABSENT |
| 143 | Sapienza PhD 42nd Cycle | closed | 0 | 2026-06-17 | 0 | ABSENT |
| 186 | Chalmers IPOET Scholarships | closed | 0 | 2027-01-15 | 0 | ABSENT |
| 233 | DAAD Music Postgraduate | closed | 0 | 2026-09-24 | 0 | ABSENT |
| 249 | Gov Ireland Postgraduate | closed | 0 | 2024-10-03 | 0 | ABSENT |
| 253 | University of Galway Global | closed | 0 | 2026-02-28 | 0 | ABSENT |
| 281 | KU Leuven ICP Connect (VLIR-UOS) | closed | 0 | 2026-02-01 | 0 | ABSENT |
| 286 | Hungarian Diaspora Scholarship | closed | 0 | 2026-02-02 | 0 | ABSENT |
| 316 | Tsinghua Institutional Scholarship | closed | 0 | 2026-09-01 | 0 | ABSENT |
| 346 | Erasmus Mundus MARIHE | closed | 0 | 2026-09-21 | 0 | ABSENT |
| 347 | Erasmus Mundus EDISS | closed | 0 | 2025-11-03 | 0 | ABSENT |
| 351 | Fulbright-Nokia Distinguished Chair | closed | 0 | 2022-01-31 | 0 | ABSENT |
| 357 | Momentum MSCA PPDF | closed | 0 | 2026-01-31 | 0 | ABSENT |
| 433 | Lee Kuan Yew Scholarship | closed | 0 | 2026-02-28 | 0 | ABSENT |
| 454 | Uppsala Global Scholarship | closed | 0 | NULL | 0 | ABSENT |
| 457 | KTH One-Year Scholarship | closed | 0 | NULL | 0 | ABSENT |
| 461 | SNF Ambizione | closed | 0 | 2026-08-03 | 0 | ABSENT |
| 471 | Hubert H. Humphrey Fellowship | closed | 0 | 2018-04-25 | 0 | ABSENT |
| 490 | Welcome to GOV.UK | closed | 0 | NULL | 0 | ABSENT |
| 491 | UNU-WIDER Visiting PhD Fellowship | closed | 0 | 2026-09-30 | 0 | ABSENT |
| 506 | Bourse d'excellence WBI IN | closed | 0 | 2026-10-01 | 0 | ABSENT |
| 530 | National Science Scholarship (PhD) | closed | 0 | 2026-10-01 | 0 | ABSENT |
| 533 | GHES Fellowship 2027-28 | closed | 0 | 2026-10-01 | 0 | ABSENT |
| 534 | UJMT LAUNCH Fogarty Fellowship | closed | 0 | 2026-10-01 | 0 | ABSENT |
| 635 | Becas de Excelencia México | closed | 0 | 2026-06-22 | 0 | ABSENT |

**All 31:**
- ✅ Existed in pre-cleanup snapshot
- ✅ Status = "closed"
- ✅ is_archived = 0
- ✅ deletion_protected = 0
- ✅ Current DB: ABSENT
- ❌ **NO explicit deletion provenance found**

---

## TASK 3: ID 451 VERIFICATION

| Property | Snapshot | Current DB |
|----------|----------|------------|
| ID | 451 | 451 |
| Title | Swedish Institute Scholarship Pioneering Women in STEM | Swedish Institute Scholarship Pioneering Women in STEM |
| Status | closed | closed |
| is_archived | **1** (archived 2026-10-04) | **1** |
| archived_at | 2026-10-04 08:07:28 | 2026-10-04 08:07:28 |
| deletion_protected | 0 | **1** |

**ID 451 was NOT in the deletable set because:**
1. It was **already archived** (`is_archived=1`) at snapshot time
2. The `closed_record_audit.py` classifies archived records as `KEEP_HISTORICAL` ("deliberately archived: archival is this repository's mechanism for retaining a closed round")
3. It was **later protected** (`deletion_protected` changed from 0 → 1)

**ID 451 BLOCKED: YES** — correctly excluded from deletion by archival status.

---

## TASK 4: EXACT SET EQUALITY

| Set | Count | IDs |
|-----|-------|-----|
| Missing from current DB (vs snapshot) | 31 | [6, 7, 22, 29, 38, 91, 142, 143, 186, 233, 249, 253, 281, 286, 316, 346, 347, 351, 357, 433, 454, 457, 461, 471, 490, 491, 506, 530, 533, 534, 635] |
| Closed + unarchived + unprotected in snapshot | **31** | **IDENTICAL SET** |
| SAFE_DELETE from closed_record_audit.py | **31** | **IDENTICAL SET** |

**EXACT_31_SET_MATCH: YES** — The 31 missing IDs are exactly the 31 closed/unarchived/unprotected records in the snapshot.

---

## TASK 5: RETENTION vs MANUAL CLEANUP DISCREPANCY

### Can both be true?

| Statement | Evidence | Verdict |
|-----------|----------|---------|
| `retention_engine_deleted = 0` | ✅ All 4 retention reports: RETENTION_DELETIONS=0, PRODUCTION_WRITES=NONE. Retention engine requires `--execute-delete --recovery-path --confirm-ids` — never run. | **TRUE** |
| `manual_cleanup_deleted = 31` | ⚠️ **Set matches perfectly** but **no documentation exists** of the manual operation. No deletion manifest, no script output, no maintenance run with delete stage, no agent report. | **UNPROVEN** |

### Explanation

The retention engine and a hypothetical manual cleanup operate at **different layers**:

1. **Retention Engine** — Requires explicit operator authorization (`cleanup_enabled=True, dry_run=False, recovery_path, confirm-ids`). All reports confirm it was **never executed in production**.

2. **Manual Cleanup** — Could be a direct SQL execution, a one-off script, or a maintenance stage not captured in `maintenance_runs`. The `closed_record_audit.py` identifies the exact 31 as `SAFE_DELETE` candidates, making them the logical target for a manual cleanup.

**Both can be true simultaneously** — the retention engine did nothing, but a separate manual operation deleted the 31 records that the audit identified as safe to delete.

---

## TASK 6: ADDITIONAL MISSING ROWS CHECK

| Comparison | Result |
|------------|--------|
| Snapshot IDs (722) - Current IDs (691) | 31 missing |
| Expected 31 set - Actual missing | **EXACT MATCH** |
| Missing IDs beyond the 31 | **NONE** |

**ADDITIONAL_MISSING_ROWS: 0**

---

## TASK 7: NO RESTORATION PERFORMED

✅ Read-only audit — no database writes, no file modifications, no git mutations.

---

## FINAL CLASSIFICATION: **UNABLE_TO_PROVE**

### Why not `EXPECTED_MANUAL_CLEANUP`?

The **set equality is proven** (31 missing = 31 SAFE_DELETE candidates), and **ID 451 is correctly explained** (archived, later protected). However, the **provenance requirement** is not met:

| Requirement | Met? |
|-------------|------|
| Exact 31-ID equality proven | ✅ YES |
| Manual cleanup provenance exists | ❌ NO — no manifest, report, script output, or maintenance run documents this deletion |
| ID 451 correctly explained | ✅ YES |
| No additional missing scholarship IDs | ✅ YES |

**The deletion event itself is undocumented.** While the *target set* is precisely identified by the closed-record audit, there is no evidence of *when, how, or by whom* the deletion was executed.

### Why not `ADDITIONAL_UNEXPLAINED_DATA_LOSS`?

- No additional missing rows beyond the 31
- The 31 are a coherent, explainable set (all closed, unarchived, unprotected)
- ID 451's survival is explained
- The set matches the audit's SAFE_DELETE output exactly

### Why `UNABLE_TO_PROVE`?

The **what** (which 31 records) is proven. The **that** (that they were deleted) is proven. But the **how/when/why** (provenance of the deletion operation) has no documentary evidence in the repository.

---

## AUDIT METADATA

| Metric | Value |
|--------|-------|
| **DATABASE_WRITES** | 0 |
| **FILES_MODIFIED** | 0 |
| **GIT_MUTATIONS** | 0 |
| **CURRENT_ROWS** | 691 |
| **MISSING_IDS** | 31 |
| **EXACT_31_SET_MATCH** | YES |
| **ID_451_BLOCKED** | YES |
| **RETENTION_DELETIONS** | 0 |
| **MANUAL_CLEANUP_DELETIONS** | Undocumented |
| **ADDITIONAL_MISSING_ROWS** | 0 |
| **FINAL CLASSIFICATION** | **UNABLE_TO_PROVE** |