# FINAL PROVENANCE SEARCH REPORT — 31-ROW CLOSED-SCHOLARSHIP DELETION

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **FINAL CLASSIFICATION** | **NO_PROVENANCE_FOUND** |
| Target 31 IDs match SAFE_DELETE candidates | ✅ YES |
| Exact 31-ID set equality proven | ✅ YES |
| Documented deletion operation found | ❌ NO |
| Deletion timestamp found | ❌ NO |
| All 31 IDs match exactly | ✅ YES |
| Additional IDs deleted beyond 31 | ❌ NO |

---

## SEARCH SCOPE

### 1. ScholarZone Repository (Main + All Worktrees)
- All `.md` reports (40+ files)
- All backend scripts (`backend/scripts/*.py`)
- Maintenance run history (`maintenance_runs` table)
- Configuration files (`backend/config/*.json`)
- Test reports and CI artifacts
- SQLite WAL/journal files (none found)

### 2. Local Agent/Runtime Artifacts
- Kilo temp directories: `C:\Users\GopaL\AppData\Local\Temp\kilo\*`
  - `closed-audit-wt` (read-only audit worktree)
  - `sz-retention-fix2` (retention engine worktree)
  - `sz-retention-wt` (retention engine worktree)
  - `sz-maint` (maintenance worktree)
  - 80+ other worktrees
- PowerShell command history (`ConsoleHost_history.txt`)
- OpenCode config (`C:\Users\GopaL\.config\opencode`)
- OpenCode local data (`C:\Users\GopaL\AppData\Local\opencode`)

### Search Terms Used
- Exact ID list: `6, 7, 22, 29, 38, 91, 142, 143, 186, 233, 249, 253, 281, 286, 316, 346, 347, 351, 357, 433, 454, 457, 461, 471, 490, 491, 506, 530, 533, 534, 635`
- Phrases: `"31"`, `"closed"`, `"deleted"`, `"delete"`, `"451"`, `"deletion_protected"`, `"production write"`, `"remaining closed"`, `"delete candidates"`, `"SAFE_DELETE"`, `"DELETE FROM scholarships"`

---

## FINDINGS

### 1. What IS Documented

| Artifact | Location | Content | Relevance |
|----------|----------|---------|-----------|
| `closed_record_audit.py` | `backend/scripts/closed_record_audit.py` (all worktrees) | Read-only audit classifying closed records. Identifies **31 SAFE_DELETE** candidates matching **exactly** the 31 missing IDs. | Proves the 31 were **deletable**, not that they were **deleted** |
| `check_audit_safe_delete.py` | `backend/scripts/check_audit_safe_delete.py` | CI guard that **fails if SAFE_DELETE > 0**; does NOT delete | Proves deletions were NOT automated |
| `maintenance_runs` table | `scholarzone.db` | Last run: **2026-10-04 11:20:49** (retire, repair_list_columns, logos). **No runs after 2026-10-05 14:39:34** | Proves no maintenance deletion after snapshot |
| `purged_records_archive.json` | `backend/config/purged_records_archive.json` | Collector's archive of **151** records (archived/closed), not a deletion manifest | 22 of 31 missing IDs appear here; 129 of 151 still in DB |
| `closed_record_audit.json` | `C:\Users\GopaL\AppData\Local\Temp\kilo\audit-artifact\closed_record_audit.json` | Audit from **2026-10-03** showing **22 closed records** (different set) | Pre-dates the 31-deletion; different population |

### 2. What is NOT Documented (Critical Gaps)

| Missing Evidence | Searched | Found |
|------------------|----------|-------|
| Deletion manifest with exact 31 IDs | All reports, configs, scripts | ❌ NO |
| `DELETE FROM scholarships WHERE id IN (...)` SQL statement | All scripts, history, logs | ❌ NO |
| Maintenance run with "delete" or "purge" stage | `maintenance_runs` table | ❌ NO |
| Agent report: "Deleted 31 closed scholarships" | All `.md` reports | ❌ NO |
| Terminal command executing deletion | PowerShell history | ❌ NO |
| SQLite WAL/journal showing DELETE | Project + all worktrees | ❌ NO |
| Timestamp of deletion operation | All sources | ❌ NO |
| Operator identity who executed deletion | All sources | ❌ NO |

### 3. Retention Engine Status

| Report | Classification | Production Deletions |
|--------|----------------|---------------------|
| `SCHOLARZONE_LIVE_ADMIN_REVIEW_RETENTION_FINAL.md` | `DRY_RUN_PROVEN_HARD_DELETE_HELD` | **0** |
| `SCHOLARZONE_RETENTION_RECOVERY_FINAL.md` | `RECOVERY_PATH_REQUIRED` | **0** |
| `SCHOLARZONE_RETENTION_DRY_RUN_TEST_ISOLATION_FINAL.md` | Test isolation verified | **0** |
| `SCHOLARZONE_RETENTION_RECOVERY_FINAL.md` (recovery proof) | `NOT PROVEN` | **0** |

**All 4 authoritative retention reports state: RETENTION_DELETIONS = 0, PRODUCTION_WRITES = NONE**

The retention engine requires **all three** to execute:
1. `--execute-delete` flag
2. `--recovery-path` (verified recovery source)
3. `--confirm-ids` (exact comma-separated ID list matching candidates)

**Never executed in production** per all reports.

---

## THE 31 MISSING IDs — STATUS

### In Pre-Cleanup Snapshot (`scholarzone.pre_integrity_repair_20261005_143934.db`)

| Property | Value |
|----------|-------|
| All 31 IDs present | ✅ YES |
| All status = "closed" | ✅ YES |
| All is_archived = 0 | ✅ YES |
| All deletion_protected = 0 | ✅ YES |
| Classified as SAFE_DELETE by audit | ✅ YES (all 31) |

### In Current DB (`scholarzone.db`)

| Property | Value |
|----------|-------|
| All 31 IDs absent | ✅ YES |
| No other IDs missing | ✅ YES (exact set match) |

### ID 451 — Correctly Blocked

| Property | Snapshot | Current DB |
|----------|----------|------------|
| is_archived | **1** | **1** |
| deletion_protected | 0 | **1** (later protected) |
| In 31 missing | ❌ NO | ❌ NO |

ID 451 was **not in the deletable set** because it was already archived. The audit classifies archived records as `KEEP_HISTORICAL`.

---

## TIMELINE ANALYSIS

| Date | Event | 31 IDs Status |
|------|-------|---------------|
| 2026-10-03 | `closed_record_audit.json` generated | 22 closed records (different set) |
| 2026-10-04 11:20 | Last maintenance run (retire, repair, logos) | All 31 present |
| 2026-10-04 20:09 | `pre_wave13_master` snapshot | All 31 present (722 rows) |
| 2026-10-04 20:10 | `wave13_local.db` snapshot | All 31 present (722 rows) |
| 2026-10-05 14:39 | `pre_integrity_repair` snapshot | All 31 present (722 rows) |
| **2026-10-05 to 2026-10-06** | **Deletion window** | **31 deleted** |
| 2026-10-06 23:49 | Current DB last modified | 31 absent (691 rows) |

**Critical finding:** The 31 deletions occurred **between Oct 5 (snapshot) and Oct 6 (current DB)** with **no maintenance run, no retention run, no documented operation** in that window.

---

## CLASSIFICATION CRITERIA CHECK

| Criterion for `DOCUMENTED_MANUAL_CLEANUP` | Met? | Evidence |
|------------------------------------------|------|----------|
| Exact 31-ID equality proven | ✅ YES | Snapshot vs current DB = exact match |
| Documented deletion operation exists | ❌ NO | No manifest, script, run, report, or log |
| Deletion timestamp found | ❌ NO | Only bounded to Oct 5–6 window |
| All 31 IDs match exactly | ✅ YES | Set equality proven |
| No additional IDs deleted | ✅ YES | Zero missing beyond 31 |

**Result: NO_PROVENANCE_FOUND**

The *what* (which 31 records) and *that* (they were deleted) are proven.
The *how/when/by whom* (provenance of the deletion operation) has **zero documentary evidence**.

---

## AUDIT METADATA

| Metric | Value |
|--------|-------|
| **DATABASE_WRITES** | 0 |
| **FILES_MODIFIED** | 0 |
| **GIT_MUTATIONS** | 0 |
| **EXACT_31_SET_MATCH** | YES |
| **ID_451_BLOCKED** | YES |
| **RETENTION_DELETIONS** | 0 |
| **MANUAL_CLEANUP_DELETIONS** | Undocumented |
| **ADDITIONAL_MISSING_ROWS** | 0 |
| **FINAL CLASSIFICATION** | **NO_PROVENANCE_FOUND** |