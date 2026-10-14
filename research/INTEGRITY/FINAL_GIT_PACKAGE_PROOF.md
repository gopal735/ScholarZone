# FINAL GIT PACKAGE PROOF — READ-ONLY AUDIT

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **FINAL VERDICT** | **GIT_PACKAGE_NOT_REPRODUCIBLE** |
| Tracked Source JSON | **0** (70 files are untracked) |
| Tracked Public JSON | **0** (71 files are untracked) |
| Generator Tracked | **NO** (generate_index.mjs is untracked) |
| Prebuild Configured | **YES** (frontend/package.json modified) |
| Fresh Clone Build | **WOULD FAIL** |
| Runtime JSON Generated | **NO in fresh clone** |

---

## 1. GIT TRACKING CHECK — RESULTS

### Research Source JSON Files
```bash
git ls-files research/premium_card/output/
# NO OUTPUT — 0 files tracked
```

**Result:** **0 of 70 scholarship JSON files are tracked in git.**

The canonical research source (`research/premium_card/output/`) contains 70 `scholarship_*.json` files, but **NONE are tracked in git**.

### Frontend Public JSON Files
```bash
git ls-files frontend/public/research/premium_card/output/
# NO OUTPUT — 0 files tracked
```

**Result:** **0 of 71 runtime JSON files are tracked in git.**

The runtime destination (`frontend/public/research/premium_card/output/`) contains 71 JSON files (70 scholarship + index.json), but **NONE are tracked in git**.

---

## 2. GENERATOR TRACKING — RESULTS

| File | Git Status | Tracked? |
|------|------------|----------|
| `research/premium_card/generate_index.mjs` | `??` (untracked) | **NO** |
| `frontend/package.json` | `M` (modified) | **YES** |

| File | Git Status | Tracked? |
|------|------------|----------|
| `frontend/package.json` | `M` (has `prebuild` script) | **YES** |

**Result:** The generator script itself is **NOT tracked**. The prebuild hook in `package.json` references it, but the script doesn't exist in a fresh clone.

---

## 3. TRUE FRESH-CLONE TEST — SIMULATION

### What a fresh clone WOULD contain:
- `frontend/package.json` (with `prebuild` hook) ✅
- `frontend/src/...` Premium Card components ✅
- `research/premium_card/` directory structure ✅
- **NO** `research/premium_card/output/scholarship_*.json` files ❌
- **NO** `research/premium_card/generate_index.mjs` ❌
- **NO** `frontend/public/research/premium_card/output/` files ❌

### What would happen in a fresh clone:
```bash
cd frontend
npm install
npm run build
```

**Step 1:** `prebuild` hook runs: `node ../research/premium_card/generate_index.mjs`

**FAILURE:** `Error: Could not find module '../research/premium_card/generate_index.mjs'` — the script doesn't exist in the clone.

**Even if the script existed:** It would search for `research/premium_card/output/` and find **0 scholarship JSON files** (source data not tracked).

---

## 4. COMMIT DESIGN — EXACT REQUIREMENTS

### REQUIRED_SOURCE_DATA (70 files) — MUST BE COMMITTED
```
research/premium_card/output/scholarship_001_*.json
research/premium_card/output/scholarship_002_*.json
...
research/premium_card/output/scholarship_070_*.json
```
**70 files** — Canonical source data for Premium Card runtime

### REQUIRED_RUNTIME_CODE (11 files) — ALREADY NEW/UNTRACKED
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

### BUILD_GENERATOR (1 file) — MUST BE COMMITTED
```
research/premium_card/generate_index.mjs
```

### REQUIRED_CONFIG (1 file) — ALREADY TRACKED/MODIFIED
```
frontend/package.json (with "prebuild": "node ../research/premium_card/generate_index.mjs")
```

### AUDIT_ONLY (15 files) — OPTIONAL FOR DEPLOYMENT
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

### REPRODUCIBLE_CODE (3 files) — OPTIONAL FOR DEPLOYMENT
```
research/premium_card/research_runner.py
research/premium_card/merge_execute.py
research/premium_card/merge_research.py
```

### GENERATED_ARTIFACT (71 files) — DO NOT COMMIT
```
frontend/public/research/premium_card/output/index.json
frontend/public/research/premium_card/output/scholarship_001_*.json
...
frontend/public/research/premium_card/output/scholarship_070_*.json
```

### DO_NOT_COMMIT
- `research/premium_card/output/*.json` (70 files) — SOURCE DATA, NOT generated
- `backend/scholarzone.db` — DATABASE_ONLY
- All pre-existing repo clutter (200+ files) — PRE_EXISTING_UNRELATED

---

## 5. PRODUCTION DATABASE MIGRATION — CONFIRMED

### Migration Required: **YES**

**Target DB IDs (14):** `[162, 264, 271, 272, 273, 285, 299, 335, 337, 341, 348, 349, 356, 359]`

### Migration Fields:
| Field | Rows | Included |
|-------|------|----------|
| `official_details` | 8 rows | YES — official URLs, application links |
| `applicant_utility` | 0 rows | NO — empty in all targets |
| `programme_verification` | 14 rows | YES — schema_version marker |
| `status` / `verification_status` | 14 rows | INCIDENTAL (ingestion side effects) |
| `scholarship_verification_history` | 23 entries | INCIDENTAL |

### Migration Path:
- **Type:** PostgreSQL (Neon)
- **Strategy:** Single transaction, per-row rowcount assertions, preflight/postflight checks
- **Safety:** Explicit 14-ID allowlist, no fuzzy matching, no blanket updates
- **Historical 31 IDs:** Excluded from migration

---

## 6. FINAL VERDICT: **GIT_PACKAGE_NOT_REPRODUCIBLE**

### Why it fails:

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Source JSON in git | ❌ FAIL | 0 of 70 tracked |
| Generator in git | ❌ FAIL | `generate_index.mjs` untracked |
| Fresh clone has source data | ❌ FAIL | 0 JSON files in clone |
| Generator exists in clone | ❌ FAIL | Script not tracked |
| Fresh clone build passes | ❌ WOULD FAIL | Missing script + missing data |

### What MUST be committed to make it reproducible:

| Category | Files | Action |
|----------|-------|--------|
| **REQUIRED_SOURCE_DATA** | 70 JSON files | `git add research/premium_card/output/` |
| **BUILD_GENERATOR** | 1 file | `git add research/premium_card/generate_index.mjs` |
| **REQUIRED_RUNTIME_CODE** | 11 files | `git add frontend/src/components/PremiumScholarshipCard.jsx ...` |
| **REQUIRED_CONFIG** | 1 file | Already modified (`frontend/package.json`) |

**Total to commit for reproducibility:** **82 files** (70 source JSON + 1 generator + 11 frontend components)

---

## FINAL METRICS

| Metric | Value |
|--------|-------|
| **TRACKED_SOURCE_JSON_COUNT** | 0 |
| **TRACKED_PUBLIC_JSON_COUNT** | 0 |
| **GENERATOR_TRACKED** | NO |
| **PREBUILD_CONFIGURED** | YES |
| **FRESH_CLONE_BUILD** | WOULD FAIL |
| **RUNTIME_JSON_GENERATED** | NO (in fresh clone) |
| **PRODUCTION_DB_MIGRATION_REQUIRED** | YES |
| **FINAL_VERDICT** | **GIT_PACKAGE_NOT_REPRODUCIBLE** |
| **GIT_MUTATIONS** | 0 |
| **DATABASE_WRITES** | 0 |