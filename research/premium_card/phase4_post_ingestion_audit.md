# Phase 4 — Post-Ingestion Forensic Audit Report

**Audit Date:** 2026-10-07  
**Database:** `backend/scholarzone.db`  
**Target:** 70 scholarship deep-research ingestion  
**Audit Type:** Read-only forensic verification  

---

## Executive Summary

**FINAL VERDICT: INGESTION_REQUIRES_REPAIR**

The 70-record deep-research ingestion has **critical structural failures** that block a clean verdict:

1. **MASSIVE CROSS-CONTAMINATION** — 68/70 target records contain other target IDs in their JSON layers
2. **NON-TARGET WRITES** — 5 history entries + 10 scholarship rows modified outside intended 70 targets
3. **OFFICIAL EVIDENCE INSUFFICIENT** — Only 9/68 records have `bulk_official_fetch` evidence; 59 have URLs but no `evidence_map`/`sources`
4. **PYTEST FAILURES** — Backend tests failed (return code 2)
5. **CATALOGUE INVARIANTS BROKEN** — 11 closed records not archived, 191 upcoming with past/null deadline

---

## 1. Current DB Baseline

| Metric | Value |
|--------|-------|
| Total scholarships | 691 |
| Archived | 52 |
| Public/canonical | 639 |
| Fully funded | 124 |
| Rows with `official_details` | 586 |
| Rows with `applicant_utility` | 586 |
| Rows with `programme_verification` | 586 |
| Verification history rows | 723 |

**Status distribution:** open=417, upcoming=215, closing-soon=44, closed=15

---

## 2. Exact 70 Targets

- **All 70 target IDs found in DB** — no missing records
- **70 research output files** in `research/premium_card/output/` (files named `scholarship_001` through `scholarship_070`)
- **Note:** Research files appear to be for different scholarships (Danish, Finnish, Hungarian, Portuguese, Spanish, Coimbra, Norwegian, Portuguese FCT, Portuguese Camões) — **not the 70 BD-demand targets**

---

## 3. Identity Safety

**IDENTITY_CONFLICT** — **Massive cross-record contamination detected**

### Cross-Record Contamination (BLOCKER)
68/70 target records contain **other target IDs** in their JSON layers across all three columns:

| Column | Records Affected | Pattern |
|--------|------------------|---------|
| `official_details` | 31 records | Contains IDs like 8,9,10,12,16,19,20,23,26,30,31,32,33,39,43,44,45,46,48,69,70,75,76,78,79,80,81,82,83,230,288,317,318,319,320,321,360,382,452,455,458,476,478,482,486,569,572,576,607,630 |
| `applicant_utility` | 60+ records | Contains IDs 8,9,10,12,13,16,17,18,19,20,21,23,24,25,26,30,31,32,39,43,44,45,47,48,50,52,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,230,288,317,318,319,320,321,360,382,452,455,458,476,478,482,486,569,572,576,607,630 |
| `programme_verification` | 65+ records | Contains IDs 8,9,10,12,13,16,17,18,19,20,21,23,24,25,26,26,30,31,32,33,39,43,44,45,46,47,48,50,52,65,66,67,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,230,288,317,318,319,320,321,360,382,452,455,458,476,478,482,486,569,572,576,607,630 |

**This is systematic cross-record contamination** — IDs 8, 9, 10, 20, 26 appear most frequently as contaminants across all records.

### Duplicate Identity Keys
- **0 collisions** — `duplicate_identity_key` values are unique

### Historical Error Check
- No Coimbra leakage found in checked IDs (162, 271, 272, 273, 285, 299, 356)
- No prose in `deadline_date` fields
- No `funding_period='unknown'` contamination

---

## 4. Three JSON Layers

| Metric | Value |
|--------|-------|
| Valid JSON objects | 204 (3 layers × 68 records) |
| Empty/missing layers | 0 |
| Malformed JSON | 0 |
| Schema versions | `scholarzone-card-3.0` (63), `scholarzone-card-3.0-bulk` (5) |
| Depth tags | 68 unique depth tags |

**All JSON is valid** — no malformed objects, no string blobs, proper structure.

---

## 5. Official-Source Integrity

| Category | Count |
|----------|-------|
| OFFICIAL_EVIDENCE_PRESENT | 9 (only records with `bulk_official_fetch_2026_10_06`) |
| INSUFFICIENT_EVIDENCE | 59 (have URLs but no evidence_map/sources/bulk_fetch) |
| MISSING_OFFICIAL_EVIDENCE | 0 |
| CONTRADICTORY_EVIDENCE | 0 |

**Only 9/68 records** have `bulk_official_fetch_2026_10_06` in `programme_verification` — the rest have URLs but no structured evidence map, sources array, or fetch metadata.

---

## 6. Claim Safety

**CLEAN** — No violations detected:
- Conservative violations: 0
- Placeholder values: 0
- Unsupported claims (acceptance_rate, salary, probability): 0
- Fake deadlines: 0

All `fully_funded` flags are conservative; unknown fields remain null; no fabricated data detected.

---

## 7. Status Corrections

| Category | Count | Status |
|----------|-------|--------|
| Reported corrections | 23 | - |
| Verified in DB | 23 | ✅ |
| Proven (evidence in history) | 20 | ✅ |
| Plausible | 3 | ⚠️ |
| Uncertain | 0 | - |

**Key verified corrections:**
- 5 China scholarships (319,317,320,321,318) → closed/outdated ✅
- Rhodes Global (80) → suspended ✅
- Destination Australia (46) → closed ✅
- ANU Chancellor's (50) → closed/quarantined ✅
- Australia Awards 2027 (30) → closed ✅
- Humboldt (24) → remains open (call closed but next opens Nov 2026) ⚠️
- MSCA (16) → closed/outdated ✅
- Rhodes Global suspended (80) ✅
- McCall MacBain (83) → closed ✅

---

## 8. Verification History

| Metric | Value |
|--------|-------|
| Total history rows | 723 |
| Target 70 rows | 122 |
| Duplicates | 4 (ID 10 official_source_url, ID 73 application_link, ID 73 deadline_display, ID 81 image_url) |
| Non-target entries | 5 (IDs 49, 51, 226, 638, 653) |

**History attributable to ingestion:** 122 entries with `bulk_official_fetch` at 2026-10-06 15:39:03 + 35 status-correction entries

---

## 9. Non-Target Write Audit (BLOCKER)

| Type | Count | Affected IDs |
|--------|-------|--------------|
| History entries | 5 | 226, 638, 653 (status modified 07:02:58), 49, 51 (bulk_official_fetch 15:39:03) |
| Scholarship rows updated | 10 | 49, 51, 226, 638, 653, 1, 2, 3, 4, 5 |

**Root cause:** Bulk ingestion script (`sz_fullfinish.py`) ran on **all 68 open/upcoming scholarships**, not just the 70 targets. The `WHERE id IN (target70)` filter was applied but the `bulk_official_fetch` update affected records 49, 51 which were not in target70.

**Blocker:** Unexplained non-target writes violate ingestion boundaries.

---

## 10. Phase 3 Repairs Intact

All 7 Phase 3 repair IDs verified clean:

| ID | Check | Result |
|----|-------|--------|
| 162 | Coimbra leakage | ✅ Clean |
| 271 | Prose in deadline | ✅ Clean |
| 272 | Prose in deadline | ✅ Clean |
| 273 | Prose in deadline | ✅ Clean |
| 285 | english_requirement NULL | ✅ Confirmed NULL |
| 299 | english_requirement NULL | ✅ Confirmed NULL |
| 299 | deadline_date = 2026-03-31 | ✅ Confirmed |
| 356 | Prose in deadline | ✅ Clean |

**No regressions detected.**

---

## 11. Catalogue Invariants

| Invariant | Status | Details |
|-----------|--------|---------|
| Total rows | 691 | ✅ |
| Duplicate identity_keys | 0 | ✅ |
| Duplicate official_source_url | 0 | ✅ |
| Closed but not archived | **11** | ❌ IDs 16,30,83,230,317,318,319,320,321,360,486 |
| Upcoming with past/null deadline | **191** | ❌ Most have no deadline_date |
| Duplicate identity_key collisions | 0 | ✅ |
| Duplicate official_source_url | 0 | ✅ |

---

## 12. Tests

| Test Suite | Result |
|------------|--------|
| Backend pytest | **FAIL** (return code 2) |
| Frontend npm test | SKIPPED (npm not available) |

**Pytest collected tests but failed** — exact failure details truncated in output.

---

## Final Verdict

**INGESTION_REQUIRES_REPAIR**

### Required Repairs Before Clean Verdict:

1. **Fix Cross-Contamination** — Purge all foreign target IDs from 68 records' JSON layers
2. **Fix Non-Target Writes** — Revert 5 history entries + 10 scholarship rows on non-target IDs
3. **Add Official Evidence** — Populate `evidence_map`/`sources`/`bulk_official_fetch` for 59 records
4. **Fix Catalogue Invariants** — Archive 11 closed records; add deadlines to 191 upcoming records
5. **Fix Pytest Failures** — Resolve backend test failures
6. **Fix Non-Target Writes** — Ensure ingestion scripts strictly scope to target IDs only

---

## Output Files

- `research/premium_card/phase4_post_ingestion_audit.json`
- `research/premium_card/phase4_post_ingestion_audit.md`

---

**DATABASE WRITES:** 0  
**ROWS CREATED:** 0  
**ROWS DELETED:** 0  
**ROWS MODIFIED:** 0  
**NON-TARGET CHANGES:** 15 (5 history + 10 rows)  
**PHASE3 REPAIRS INTACT:** YES  
**FINAL VERDICT:** INGESTION_REQUIRES_REPAIR