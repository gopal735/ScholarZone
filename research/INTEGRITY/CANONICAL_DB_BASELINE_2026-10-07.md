# CANONICAL DATABASE BASELINE — 2026-10-07

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No database writes, no file modifications to source, no git mutations

---

## CURRENT CANONICAL SCHOLARSHIP COUNT = 691

This baseline establishes the **canonical state** of `backend/scholarzone.db` as of 2026-10-07. The 31 missing IDs are retained as historical deletion records and are **NOT to be restored** unless separate authoritative recovery evidence is found.

---

## TASK 1 — CURRENT BASELINE

| Property | Value |
|----------|-------|
| **DB File** | `backend/scholarzone.db` |
| **SHA-256** | `a957afb0e32594df90ddce7d881dbd53790a881a559f6818866f2cc95c2eb66a` |
| **File Size** | 16,142,336 bytes (15.4 MB) |
| **Modification Timestamp** | 2026-10-06 23:49:43 UTC (epoch: 1791308983) |
| **Scholarships Row Count** | **691** |
| **Verification History Row Count** | 723 |
| **Max Scholarship ID** | 725 |
| **PRAGMA integrity_check** | `ok` |

### Status Distribution

| Status | Count |
|--------|-------|
| open | 417 |
| upcoming | 215 |
| closing-soon | 44 |
| closed | 15 |

### Verification Status Distribution

| Verification Status | Count |
|---------------------|-------|
| active | 529 |
| needs_review | 89 |
| quarantined | 51 |
| outdated | 12 |
| pending | 5 |
| conflicting | 2 |
| unverified | 1 |
| suspended | 1 |
| partial | 1 |

### Archive / Visibility

| Property | Count |
|----------|-------|
| Archived (`is_archived = 1`) | 52 |
| Public (visibility conditions met) | 361 |
| Deletion Protected (`deletion_protected = 1`) | 52 |

### Closed Scholarships Detail (15)

| ID | Title | Status | Archived | Verification Status |
|----|-------|--------|----------|---------------------|
| 16 | Marie Skłodowska-Curie Actions (MSCA) Postdoctoral... | closed | 0 | outdated |
| 30 | Australia Awards Scholarships... | closed | 0 | outdated |
| 46 | Destination Australia Program (DAP)... | closed | 1 | outdated |
| 50 | ANU Chancellor's International Scholarship... | closed | 1 | quarantined |
| 80 | Rhodes Scholarship (Global Constituency)... | closed | 1 | suspended |
| 83 | McCall MacBain Scholarships at McGill University... | closed | 0 | outdated |
| 230 | DAAD Helmut-Schmidt-Programme... | closed | 0 | outdated |
| 317 | Asian Future Leaders Scholarship Program (AFLSP) 2026... | closed | 0 | outdated |
| 318 | Atomic Energy Scholarship Program of China 2026... | closed | 0 | outdated |
| 319 | Chinese Government Scholarship (Chinese University... | closed | 0 | outdated |
| 320 | Chinese Government Scholarship (Youth of Excellence... | closed | 0 | outdated |
| 321 | Shanghai Government Scholarship at Fudan University... | closed | 0 | outdated |
| 360 | MEXT Scholarship for 2027 - Embassy Recommendation... | closed | 0 | outdated |
| 451 | Swedish Institute Scholarship Pioneering Women in STEM | closed | 1 | quarantined |
| 486 | Google PhD Fellowship Program... | closed | 0 | outdated |

---

## TASK 2 — 31-ID STATUS

### The 31 Missing IDs

```
6, 7, 22, 29, 38, 91, 142, 143, 186, 233, 249, 253,
281, 286, 316, 346, 347, 351, 357, 433, 454, 457, 461,
471, 490, 491, 506, 530, 533, 534, 635
```

### Verification Matrix

| Property | Value |
|----------|-------|
| Missing from current DB | **YES** (all 31) |
| Present in all 3 trusted snapshots | **YES** (pre_integrity_repair, wave13_local, pre_wave13_master all have 722 rows with these 31 present) |
| Exact set matches historical closed-cleanup SAFE_DELETE set | **YES** (identical to `closed_record_audit.py` SAFE_DELETE output) |
| Additional missing IDs beyond 31 | **0** |
| Documented deletion operation found | **NO** |
| Retention-engine deletion count | **0** (all 4 retention reports confirm 0) |

### ID 451 — Blocked from Deletion

| Property | Snapshot | Current DB |
|----------|----------|------------|
| ID | 451 | 451 |
| Title | Swedish Institute Scholarship Pioneering Women in STEM | Swedish Institute Scholarship Pioneering Women in STEM |
| Status | closed | closed |
| is_archived | **1** | **1** |
| archived_at | 2026-10-04 08:07:28 | 2026-10-04 08:07:28 |
| deletion_protected | 0 | **1** |

**ID 451 was correctly excluded** from the deletable set because it was already archived at snapshot time. The `closed_record_audit.py` classifies archived records as `KEEP_HISTORICAL`.

---

## TASK 3 — CANONICAL BASELINE STATEMENT

> **CURRENT CANONICAL SCHOLARSHIP COUNT = 691**
>
> The 31 missing IDs (6, 7, 22, 29, 38, 91, 142, 143, 186, 233, 249, 253, 281, 286, 316, 346, 347, 351, 357, 433, 454, 457, 461, 471, 490, 491, 506, 530, 533, 534, 635) are retained as historical deletion records and are **NOT to be restored** unless separate authoritative recovery evidence is found.

---

## TASK 4 — ACTIVE WRITER CHECK

| Process | Command | Assessment |
|---------|---------|------------|
| PID 5756 | `uvicorn app.main:app --host 127.0.0.1 --port 8000` | **Legitimate application server** |

**ACTIVE WRITERS:** **NONE** (only the standard API server running)

---

## TASK 5 — SAFETY CONFIRMATION

| Metric | Value |
|--------|-------|
| Database writes by this task | **0** |
| Data restored | **0** |
| Git mutations | **0** |

---

## FINAL CLASSIFICATION

**CANONICAL_BASELINE_ESTABLISHED**

The baseline is established. The database is intact (integrity_check = ok), no unauthorized writers are active, and the 31 missing IDs are documented as a historical provenance gap with no documented deletion operation.

---

## SNAPSHOT REFERENCE (for recovery context)

| Snapshot | File | Size | Modified | Rows |
|----------|------|------|----------|------|
| Pre-integrity repair | `scholarzone.pre_integrity_repair_20261005_143934.db` | 15,974,400 | 2026-10-05 20:39 | 722 |
| Wave13 local | `wave13_local.db` | 15,974,400 | 2026-10-04 20:10 | 722 |
| Pre-wave13 master | `pre_wave13_master_20261004_201056.db` | 15,904,768 | 2026-10-04 20:09 | 722 |

All three snapshots are consistent (722 rows, all 31 IDs present).