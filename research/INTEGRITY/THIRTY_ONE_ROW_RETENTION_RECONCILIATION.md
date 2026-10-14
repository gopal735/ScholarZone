# 31-ROW RETENTION RECONCILIATION REPORT

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **CURRENT_DB_ROWS** | 691 |
| **SNAPSHOT_BASELINE_ROWS** | 722 (all 3 snapshots consistent) |
| **MISSING_FROM_CURRENT** | 31 IDs |
| **EXPECTED_RETENTION_DELETIONS** | 22/31 match purged archive |
| **ADDITIONAL_MISSING_ROWS** | 9 IDs with no archive evidence |
| **UNEXPECTED_DELETIONS** | 9 confirmed |
| **FINAL CLASSIFICATION** | **ADDITIONAL_DATA_LOSS_DETECTED** |

---

## THE 31 MISSING IDs (Relative to Snapshot Baseline)

| ID | Title | In Purged Archive | In Retired Records | Status in Snapshot |
|----|-------|-------------------|-------------------|-------------------|
| 6 | Eiffel Excellence Scholarship | ✅ | ❌ | closed, not archived |
| 7 | Swiss Government Excellence Scholarship (ESKAS) | ✅ | ❌ | closed, not archived |
| 22 | DAAD Study Scholarships for STEM Disciplines | ✅ | ❌ | closed, not archived |
| 29 | Commonwealth Scholarship | ❌ | ❌ | closed, not archived |
| 38 | Vanier Canada Graduate Scholarship | ✅ | ❌ | closed, not archived |
| 42 | *(not in any snapshot)* | ❌ | ❌ | N/A — never existed in baseline |
| 91 | Université Paris-Saclay IDEX International Master's | ✅ | ❌ | closed, not archived |
| 142 | STAR Scholarships Foundation Year + Bachelor's | ✅ | ❌ | closed, not archived |
| 143 | Sapienza PhD 42nd Cycle | ✅ | ❌ | closed, not archived |
| 186 | Chalmers IPOET Scholarships | ❌ | ❌ | closed, not archived |
| 233 | DAAD Music Postgraduate | ❌ | ❌ | closed, not archived |
| 249 | Gov Ireland Postgraduate Scholarship | ✅ | ❌ | closed, not archived |
| 253 | University of Galway Global Scholarships | ✅ | ❌ | closed, not archived |
| 281 | KU Leuven ICP Connect (VLIR-UOS) | ✅ | ❌ | closed, not archived |
| 286 | Hungarian Diaspora Scholarship | ✅ | ❌ | closed, not archived |
| 316 | Tsinghua University Institutional Scholarship | ✅ | ❌ | closed, not archived |
| 346 | Erasmus Mundus MARIHE | ✅ | ❌ | closed, not archived |
| 347 | Erasmus Mundus EDISS | ✅ | ❌ | closed, not archived |
| 351 | Fulbright-Nokia Distinguished Chair in ICT | ✅ | ❌ | closed, not archived |
| 357 | Momentum MSCA PPDF | ❌ | ❌ | closed, not archived |
| 433 | Lee Kuan Yew Scholarship | ✅ | ❌ | closed, not archived |
| 454 | Uppsala University Global Scholarship | ✅ | ❌ | closed, not archived |
| 457 | KTH One-Year Scholarship | ✅ | ❌ | closed, not archived |
| 461 | SNF Ambizione | ✅ | ❌ | closed, not archived |
| 471 | Hubert H. Humphrey Fellowship 2027-28 | ✅ | ❌ | closed, not archived |
| 490 | Welcome to GOV.UK | ✅ | ❌ | closed, not archived |
| 491 | UNU-WIDER Visiting PhD Fellowship | ✅ | ❌ | closed, not archived |
| 506 | Bourse d'excellence WBI IN | ❌ | ❌ | closed, not archived |
| 530 | National Science Scholarship (PhD) | ❌ | ❌ | closed, not archived |
| 533 | Global Health Emerging Scholars (GHES) | ❌ | ❌ | closed, not archived |
| 534 | UJMT LAUNCH Fogarty Fellowship | ❌ | ❌ | closed, not archived |
| 635 | Becas de Excelencia Gobierno de México | ❌ | ❌ | closed, not archived |

**Note:** ID 42 appears in the original task's list of 31 but does NOT exist in any snapshot baseline. The actual missing-from-snapshot count is 30 IDs. The user's list contains 32 items (not 31 as stated).

---

## EVIDENCE ANALYSIS

### 1. Purged Records Archive (`backend/config/purged_records_archive.json`)

| Property | Value |
|----------|-------|
| `purged_at` | 2026-10-01 |
| `count` | 151 records |
| `breakdown` | status_closed: 100, archived: 147, deadline_passed: 106 |
| Type | **Collector's archive** (top-level `records` array, no `retention_batches`/`retention_runs` keys) |

**Overlap with 31 missing IDs:** 22/31 (71%)

**IDs in purged archive but STILL PRESENT in current DB:** 129/151 (85%)

This indicates the archive is a **record of archived/closed scholarships**, not a deletion manifest. The retention engine's own manifest (with `retention_batches`, `retention_summary`, `retention_runs` keys) is **absent** from this file.

### 2. Retired Records (`backend/config/retired_records.json`)

| Property | Value |
|----------|-------|
| Count | 45 records (current), 54 records (pre_wave13_hardening) |
| Overlap with 31 missing | **0/31** |

None of the 31 missing IDs are in the retired records.

### 3. Retention Execution Reports

| Report | Retention Deletions Reported |
|--------|-----------------------------|
| `COUNTRY_INTELLIGENCE_CURRENT_MASTER_INTEGRATION_FINAL.md` | `RETENTION_DELETIONS = 0` |
| `RETENTION_FIX_FINAL_REPORT.md` | `Retention deletions: 0` |
| `SCHOLARZONE_RETENTION_RECOVERY_FINAL.md` | `Production DELETE: 0`, `Total production writes: NONE` |
| `SCHOLARZONE_LIVE_ADMIN_REVIEW_RETENTION_FINAL.md` | No production deletion executed |

**All authoritative reports consistently report ZERO retention deletions.**

### 4. Retention Engine Requirements (Per `retention_dry_run.py`)

Actual deletion requires **ALL THREE**:
1. `--execute-delete` flag
2. `--recovery-path` (verified recovery source)
3. `--confirm-ids` (exact comma-separated ID list matching candidates)

No evidence exists that this was ever executed in production.

---

## RECONCILIATION AGAINST SNAPSHOTS (Excluding Intentional Deletions)

### If we exclude the 22 IDs that appear in the purged archive:

| Baseline | Calculation | Result |
|----------|-------------|--------|
| Snapshot rows | 722 | |
| Minus 22 purged-archive IDs | 722 - 22 | 700 expected |
| Current DB rows | 691 | |
| **Remaining discrepancy** | 700 - 691 | **9 additional missing rows** |

### The 9 Additional Missing IDs (No Archive Evidence)

| ID | Title | Snapshot Status |
|----|-------|-----------------|
| 29 | Commonwealth Scholarship | closed, not archived |
| 186 | Chalmers IPOET Scholarships | closed, not archived |
| 233 | DAAD Music Postgraduate | closed, not archived |
| 357 | Momentum MSCA PPDF | closed, not archived |
| 506 | Bourse d'excellence WBI IN | closed, not archived |
| 530 | National Science Scholarship (PhD) | closed, not archived |
| 533 | Global Health Emerging Scholars (GHES) | closed, not archived |
| 534 | UJMT LAUNCH Fogarty Fellowship | closed, not archived |
| 635 | Becas de Excelencia Gobierno de México | closed, not archived |

**All 9 have `status='closed'` and `is_archived=0` in the snapshot baseline.**

---

## TIMELINE ANALYSIS

| Date | Event | DB State |
|------|-------|----------|
| 2026-10-01 | Purged archive created (151 records) | Not applied to DB |
| 2026-10-04 | `wave13_local.db` snapshot | 722 rows (all 31 present) |
| 2026-10-04 | `pre_wave13_master` snapshot | 722 rows (all 31 present) |
| 2026-10-05 | `pre_integrity_repair` snapshot | 722 rows (all 31 present) |
| 2026-10-06 | Current DB modified | 691 rows (31 missing) |

**Critical finding:** The purged archive (Oct 1) predates all three snapshots (Oct 4-5), yet the snapshots still contain all 151 archived records plus the 9 additional missing IDs. The 31 deletions occurred **between Oct 5 and Oct 6** with no corresponding retention execution record.

---

## CLASSIFICATION CRITERIA CHECK

| Criterion for `EXPECTED_RETENTION_DELETIONS` | Met? | Evidence |
|---------------------------------------------|------|----------|
| All 31 IDs match known retention deletion manifest | ❌ | Purged archive has 151, not 31; no retention manifest exists |
| No additional missing rows beyond the 31 | ❌ | 9 of 31 have zero archive evidence |
| Current DB otherwise reconciles correctly | ❌ | 9 unexplained deletions remain after excluding purged archive |

| Criterion for `ADDITIONAL_DATA_LOSS_DETECTED` | Met? | Evidence |
|----------------------------------------------|------|----------|
| Unexplained missing rows beyond documented deletions | ✅ | 9 IDs missing with no archive/retired/retention record |
| No retention execution report authorizing these deletions | ✅ | All reports show 0 deletions |
| Deletions occurred after snapshot baseline | ✅ | Snapshots (Oct 4-5) have all 31; current (Oct 6) missing 31 |

| Criterion for `UNABLE_TO_PROVE` | Met? | Evidence |
|--------------------------------|------|----------|
| Insufficient evidence either way | ❌ | Evidence is sufficient: 9 IDs have zero provenance |

---

## CONCLUSION

**FINAL CLASSIFICATION: `ADDITIONAL_DATA_LOSS_DETECTED`**

### Reasoning:

1. **Only 22 of 31 missing IDs** appear in the purged records archive (which is a collector's archive of 151 closed/archived scholarships, not a retention deletion manifest)

2. **9 of the 31 missing IDs** (29, 186, 233, 357, 506, 530, 533, 534, 635) have **zero evidence** in:
   - Purged records archive
   - Retired records
   - Any retention execution report
   - Any retention manifest

3. **All authoritative retention reports** (4 separate documents) consistently report **ZERO production deletions**

4. **The retention engine** requires explicit operator authorization (`--execute-delete --recovery-path --confirm-ids`) which was never executed per the recovery report

5. **Timeline confirms** the 31 deletions occurred between Oct 5 (last snapshot) and Oct 6 (current DB), with no documented retention run in that window

6. **ID 42** in the original task list was never in the snapshot baseline, indicating the "31" figure includes a phantom ID

---

## AUDIT METADATA

| Metric | Value |
|--------|-------|
| **DATABASE_WRITES** | 0 |
| **FILES_MODIFIED** | 0 |
| **GIT_MUTATIONS** | 0 |
| **CURRENT_DB_ROWS** | 691 |
| **EXPECTED_RETENTION_DELETIONS** | 22 (matching purged archive) |
| **ADDITIONAL_MISSING_ROWS** | 9 (no archive evidence) |
| **UNEXPECTED_DELETIONS** | 9 |
| **FINAL CLASSIFICATION** | **ADDITIONAL_DATA_LOSS_DETECTED** |