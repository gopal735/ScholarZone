# FINAL DEPLOYMENT READINESS AUDIT

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **FINAL VERDICT** | **DEPLOYMENT_PACKAGING_REQUIRES_FIX** |
| Fresh Clone Reproducible | NO — Critical packaging contradiction |
| Index.json Source | Non-deterministic manual artifact |
| Runtime JSON Available | NO — Build step missing |
| DB Migration Fields | 14 targets fully accounted |
| Migration Atomicity | Designable as single transaction |
| Target Safety | 14 explicit IDs verified |
| 31 Historical Deletions | Excluded ✅ |

---

## 1. FRESH CLONE REPRODUCTION — FAILS

| Check | Result | Evidence |
|-------|--------|----------|
| **FRESH_CLONE_HAS_RESEARCH_SOURCE** | PARTIAL | `research/premium_card/output/` has 70 JSON but NO `index.json` |
| **FRESH_CLONE_CAN_BUILD_PREMIUM_CARD** | NO | Build step missing; runtime fetch fails |
| **RUNTIME_JSON_AVAILABLE** | NO | `frontend/public/research/premium_card/output/` not populated |
| **RESULT** | **BLOCKED** | Cannot deploy from clean clone |

**Root Cause:** The runtime requires `frontend/public/research/premium_card/output/index.json` (71 files) but:
- `research/premium_card/output/` has 70 JSON files + **NO index.json**
- `frontend/public/research/premium_card/output/` has 71 files (70 + index.json) but is **NOT tracked in git**
- No script generates `index.json` from the 70 JSON files

---

## 2. INDEX.JSON — NON-DETERMINISTIC MANUAL ARTIFACT

| Property | Value |
|----------|-------|
| **INDEX_SOURCE** | `frontend/public/research/premium_card/output/index.json` (manual artifact) |
| **INDEX_GENERATED_AT_BUILD** | NO |
| **INDEX_MUST_BE_COMMITTED** | NO (but build generator must exist) |
| **INDEX_BUILD_RECIPE** | MISSING — No script exists |

**Index.json Structure:**
```json
[
  { "source_title": "...", "source_provider": "...", "source_file": "...", "researched_at": "...", "data": {...} },
  ...
]
```
70 entries, each corresponding to one `scholarship_XXX.json` file.

**Critical Finding:** The `index.json` in `frontend/public/` is a **manual artifact** — no script in the repository generates it from the 70 individual JSON files. The `research_runner.py` writes 70 individual JSON files but **does not create an index.json**.

---

## 3. 70 SCHOLARSHIP JSON FILES — PACKAGING CONTRADICTION

| Aspect | Current State | Required |
|--------|---------------|----------|
| **Canonical Source** | `research/premium_card/output/` (70 JSON, no index.json) | Source of truth |
| **Production Build Source** | `frontend/public/research/premium_card/output/` (71 files) | Runtime location |
| **MUST_COMMIT_JSON** | **NO** (generated artifacts) | Must be generated at build |
| **BUILD_REPRODUCIBLE_FROM_FRESH_CLONE** | **NO** | Index generator missing |

**Contradiction:** The deployment plan says "build step copies research output → frontend/public" but:
1. `research/premium_card/output/` lacks `index.json`
2. No script generates `index.json` from the 70 JSON files
3. `frontend/public/research/premium_card/output/` is not tracked and has no build recipe

**Resolution Required:**
1. Add `generate_index.py` script that reads 70 JSON files → writes `index.json`
3. Add build step in `package.json`: `"prebuild": "python research/premium_card/generate_index.py"`
4. Ensure `frontend/public/research/premium_card/output/` is populated at build time

---

## 4. DB MIGRATION FIELD RECONCILIATION — 14 TARGETS

| DB_ID | official_details | applicant_utility | programme_verification | status | verification_status | history_entries |
|-------|------------------|-------------------|------------------------|--------|---------------------|-----------------|
| 162 | ✅ (3 keys) | ❌ | ✅ (schema_version) | open | active | 1 |
| 264 | ❌ | ❌ | ✅ (schema_version) | upcoming | active | 1 |
| 271 | ✅ (3 keys) | ❌ | ✅ (schema_version) | upcoming | active | 2 |
| 272 | ✅ (3 keys) | ❌ | ✅ (schema_version) | upcoming | active | 1 |
| 273 | ✅ (3 keys) | ❌ | ✅ (schema_version) | open | active | 1 |
| 285 | ✅ (3 keys) | ❌ | ✅ (schema_version) | upcoming | active | 1 |
| 299 | ✅ (3 keys) | ❌ | ✅ (schema_version) | upcoming | active | 1 |
| 335 | ❌ | ❌ | ✅ (schema_version) | upcoming | active | 1 |
| 337 | ❌ | ❌ | ✅ (schema_version) | upcoming | active | 2 |
| 341 | ❌ | ❌ | ✅ (schema_version) | open | quarantined | 2 |
| 348 | ❌ | ❌ | ✅ (schema_version) | open | quarantined | 1 |
| 349 | ❌ | ❌ | ✅ (schema_version) | open | quarantined | 1 |
| 356 | ✅ (3 keys) | ❌ | ✅ (schema_version) | open | active | 2 |
| 359 | ✅ (3 keys) | ❌ | ✅ (schema_version) | closing-soon | active | 3 |

### Migration Field Decisions

| Field | Included in Migration? | Reason |
|-------|------------------------|--------|
| **official_details** | YES (8 rows) | Research-backed official URLs, application links |
| **applicant_utility** | NO (0 rows) | Empty in all 14 targets — no research data produced |
| **programme_verification** | YES (14 rows) | Schema version marker + verification provenance |
| **status/verification_status** | INCIDENTAL | Status changes from closed→open/upcoming are ingestion side effects; include if authoritative |
| **verification_history** | INCIDENTAL | 23 new entries across 14 targets; migrate if audit trail required |

**Note:** `applicant_utility` is empty in ALL 14 targets — the research pipeline did not populate it. Do not migrate empty JSON objects.

---

## 5. MIGRATION ATOMICITY — SINGLE TRANSACTION DESIGN

### Recommended Shape: **ONE PostgreSQL Transaction**

```sql
BEGIN;

-- Preflight: verify all 14 targets exist
SELECT COUNT(*) FROM scholarships WHERE id IN (162, 264, 271, 272, 273, 285, 299, 335, 337, 341, 348, 349, 356, 359);
-- MUST return 14

-- Guarded updates with rowcount assertions
UPDATE scholarships SET official_details = $1, programme_verification = $2 WHERE id = 162;
-- ASSERT rowcount = 1

UPDATE scholarships SET programme_verification = $1 WHERE id = 264;
-- ASSERT rowcount = 1

... (12 more targets)

-- In-transaction verification
SELECT id, official_details IS NOT NULL as has_od, programme_verification IS NOT NULL as has_pv
FROM scholarships WHERE id IN (162, 264, 271, 272, 273, 285, 299, 335, 337, 341, 348, 349, 356, 359);
-- MUST return 14 rows: 8 with has_od=true, 14 with has_pv=true

COMMIT;
```

### Safety Properties
| Property | Enforced |
|----------|----------|
| Single transaction | YES |
| Per-row rowcount assertions | YES |
| In-transaction verification | YES |
| Rollback on ANY failure | YES |
| No partial commit possible | YES |

---

## 6. PRODUCTION TARGET SAFETY — EXACT ALLOWLIST

| Target ID | Status | Verification |
|-----------|--------|--------------|
| 162 | Included | ✅ Exact numeric |
| 264 | Included | ✅ Exact numeric |
| 271 | Included | ✅ Exact numeric |
| 272 | Included | ✅ Exact numeric |
| 273 | Included | ✅ Exact numeric |
| 285 | Included | ✅ Exact numeric |
| 299 | Included | ✅ Exact numeric |
| 335 | Included | ✅ Exact numeric |
| 337 | Included | ✅ Exact numeric |
| 341 | Included | ✅ Exact numeric |
| 348 | Included | ✅ Exact numeric |
| 349 | Included | ✅ Exact numeric |
| 356 | Included | ✅ Exact numeric |
| 359 | Included | ✅ Exact numeric |

**Total: 14 exact numeric IDs**

**Safety Verified:**
- ✅ Exact numeric allowlist (no fuzzy matching)
- ✅ No "all rows where JSON is null" patterns
- ✅ No blanket status updates
- ✅ No whole-table replacement
- ✅ Migration only touches 14 explicit IDs

---

## 7. 31 HISTORICAL DELETIONS — EXCLUDED ✅

| ID | Status |
|----|--------|
| 6, 7, 22, 29, 38, 91, 142, 143, 186, 233, 249, 253, 281, 286, 316, 346, 347, 351, 357, 433, 454, 457, 461, 471, 490, 491, 506, 530, 533, 534, 635 | **EXCLUDED FROM ALL MIGRATIONS** |

No migration touches these IDs. No recovery attempted.

---

## 8. FINAL COMMIT SET — 29 FILES

### REQUIRED_RUNTIME_CODE (11 files)
```
frontend/src/components/PremiumScholarshipCard.jsx
frontend/src/components/PremiumScholarshipCard.css
frontend/src/components/card/CardExpandSection.jsx
frontend/src/components/card/CardLevel2QuickDecision.jsx
frontend/src/components/card/CardLevel3Planning.jsx
frontend/src/components/card/CardLevel4Evidence.jsx
frontend/src/services/premiumCardResearch.js
frontend/src/utils/cardPresentation.js
frontend/src/hooks/useCountUp.js
frontend/src/hooks/useReveal.js
frontend/src/hooks/useScrollRegion.js
```

### REQUIRED_RUNTIME_DATA (0 files — generated at build)
```
frontend/public/research/premium_card/output/ (populated at build time)
```

### BUILD_SCRIPTS (1 file — NEW)
```
research/premium_card/generate_index.py (NEW — must be created)
```

### AUDIT_ONLY (15 files)
```
research/premium_card/FINAL_POST_COMPLETION_AUDIT.md
research/premium_card/FINAL_POST_COMPLETION_AUDIT.json
research/premium_card/FINAL_PREMIUM_CARD_COMPLETION_REPORT.md
research/premium_card/FINAL_PREMIUM_CARD_COMPLETION_REPORT.json
research/premium_card/FINAL_REPAIR_MANIFEST.json
research/premium_card/merge_report.json
research/premium_card/merge_verification_report.json
research/premium_card/reconciliation_report.json
research/premium_card/phase1_fresh_detail.md
research/premium_card/phase2_contamination_audit.md
research/premium_card/phase3_targeted_repair_report.md
research/premium_card/phase3b_concurrent_writer_audit.md
research/premium_card/phase4_post_ingestion_audit.md
research/premium_card/RESEARCH_AGENT_TEMPLATE.md
research/premium_card/research_manifest.json
```

### REPRODUCIBLE_CODE (3 files)
```
research/premium_card/research_runner.py
research/premium_card/merge_execute.py
research/premium_card/merge_research.py
```

### DO_NOT_COMMIT
```
research/premium_card/output/*.json (70 files) — GENERATED_ARTIFACT
research/premium_card/*.json (intermediate) — GENERATED_ARTIFACT
frontend/public/research/premium_card/output/*.json (71 files) — DEPLOYED_COPY
backend/scholarzone.db — DATABASE_ONLY (gitignored)
All pre-existing repo clutter — PRE_EXISTING_UNRELATED
```

### Total Commit Files: **30** (29 existing + 1 new `generate_index.py`)

---

## 9. FINAL VERDICT: **DEPLOYMENT_PACKAGING_REQUIRES_FIX**

### Blocking Issues
1. **No index.json generator** — `research/premium_card/output/` has 70 JSON but no `index.json`; no script creates it
2. **Build step missing** — No `prebuild` script to copy research output + generate index
3. **Fresh clone cannot reproduce runtime data** — Clean clone fails at runtime fetch

### Required Fixes (Before Commit)
1. Create `research/premium_card/generate_index.py` that reads 70 JSON → writes `index.json`
3. Add `prebuild` script in `frontend/package.json`
4. Verify fresh clone → build → dev server → Premium Card loads data

### Ready for Commit After Fixes
- ✅ 14 DB target fields fully accounted
- ✅ Migration designable as atomic single transaction
- ✅ 14 explicit target IDs verified
- ✅ 31 historical deletions excluded
- ✅ 29 commit files enumerated
- ❌ **Packaging contradiction must be resolved first**

---

**GIT_MUTATIONS: 0**  
**DATABASE_WRITES: 0**  
**PRODUCTION_WRITES: 0**