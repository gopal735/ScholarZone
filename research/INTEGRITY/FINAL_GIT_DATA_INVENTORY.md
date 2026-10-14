# FINAL GIT DATA INVENTORY — Premium Card Feature

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Category | Count |
|----------|-------|
| **COMMIT_AND_PUSH** | 17 files |
| **DO_NOT_COMMIT** | 50+ files (reports, scripts, temp) |
| **DATABASE_ONLY** | 1 file (backend/scholarzone.db) |
| **GENERATED_ARTIFACT** | 70+ files (research JSON output) |
| **DUPLICATE_MIRROR** | 70 files (frontend/public mirror) |
| **PRE_EXISTING_UNRELATED** | 200+ files (existing repo clutter) |
| **MANUAL_REVIEW** | 0 files |

**Key Findings:**
- `backend/scholarzone.db` is **NOT tracked** (correctly ignored by .gitignore)
- `research/premium_card/output/` is **NOT tracked** (correctly ignored by *.db pattern and manual inspection)
- `frontend/public/research/premium_card/output/` is **NOT tracked** (not in git)
- Frontend Premium Card components are **NOT tracked** (new files)
- 70 research JSON files are **GENERATED_ARTIFACTS** — mirror exists in frontend/public but should NOT be committed
- The 14 stored DB rows with JSON data are **RUNTIME STATE** — no separate migration needed

---

## DETAILED CLASSIFICATION

### 1. RESEARCH DIRECTORY: `research/premium_card/`

| File | Classification | Reason |
|------|----------------|--------|
| `FINAL_POST_COMPLETION_AUDIT.md` | **COMMIT_AND_PUSH** | Final audit record |
| `FINAL_POST_COMPLETION_AUDIT.json` | **COMMIT_AND_PUSH** | Machine-readable audit |
| `FINAL_PREMIUM_CARD_COMPLETION_REPORT.md` | **COMMIT_AND_PUSH** | Completion report |
| `FINAL_PREMIUM_CARD_COMPLETION_REPORT.json` | **COMMIT_AND_PUSH** | Machine-readable report |
| `FINAL_REPAIR_MANIFEST.json` | **COMMIT_AND_PUSH** | Repair manifest |
| `merge_report.json` | **COMMIT_AND_PUSH** | Matching provenance |
| `merge_verification_report.json` | **COMMIT_AND_PUSH** | Verification provenance |
| `reconciliation_report.json` | **COMMIT_AND_PUSH** | Reconciliation provenance |
| `phase1_fresh_detail.md` | **COMMIT_AND_PUSH** | Phase 1 documentation |
| `phase2_contamination_audit.md` | **COMMIT_AND_PUSH** | Phase 2 documentation |
| `phase3_targeted_repair_report.md` | **COMMIT_AND_PUSH** | Phase 3 documentation |
| `phase3b_concurrent_writer_audit.md` | **COMMIT_AND_PUSH** | Phase 3B documentation |
| `phase4_post_ingestion_audit.md` | **COMMIT_AND_PUSH** | Phase 4 documentation |
| `RESEARCH_AGENT_TEMPLATE.md` | **COMMIT_AND_PUSH** | Template for future |
| `research_manifest.json` | **COMMIT_AND_PUSH** | Research index |
| `research_runner.py` | **COMMIT_AND_PUSH** | Reproducible research script |
| `merge_execute.py` | **COMMIT_AND_PUSH** | Merge execution script |
| `merge_research.py` | **COMMIT_AND_PUSH** | Merge logic script |
| `phase1_fresh_detail.json` | **GENERATED_ARTIFACT** | Intermediate data |
| `phase2_contamination_audit.json` | **GENERATED_ARTIFACT** | Intermediate data |
| `phase3_targeted_repair_report.json` | **GENERATED_ARTIFACT** | Intermediate data |
| `phase3b_concurrent_writer_audit.json` | **GENERATED_ARTIFACT** | Intermediate data |
| `phase4_post_ingestion_audit.json` | **GENERATED_ARTIFACT** | Intermediate data |
| `output/scholarship_*.json` (70 files) | **GENERATED_ARTIFACT** | Research output, not for git |
| `agents/` | **DO_NOT_COMMIT** | Agent runtime artifacts |

---

### 2. FRONTEND PUBLIC MIRROR: `frontend/public/research/premium_card/output/`

| File | Classification | Reason |
|------|----------------|--------|
| `index.json` | **DUPLICATE_MIRROR** | Copy of research output |
| `scholarship_*.json` (70 files) | **DUPLICATE_MIRROR** | Copy of research output |

**Note:** These are **runtime-served static assets** for the Premium Card component. They are:
- Generated from `research/premium_card/output/`
- Served at `/research/premium_card/output/`
- **Should NOT be committed** — they are build/runtime artifacts
- The Premium Card component fetches these at runtime

---

### 3. FRONTEND COMPONENTS: `frontend/src/components/`

| File | Classification | Reason |
|------|----------------|--------|
| `PremiumScholarshipCard.jsx` | **COMMIT_AND_PUSH** | Core Premium Card component |
| `PremiumScholarshipCard.css` | **COMMIT_AND_PUSH** | Premium Card styles |
| `card/CardExpandSection.jsx` | **COMMIT_AND_PUSH** | Card sub-component |
| `card/CardLevel2QuickDecision.jsx` | **COMMIT_AND_PUSH** | Card sub-component |
| `card/CardLevel3Planning.jsx` | **COMMIT_AND_PUSH** | Card sub-component |
| `card/CardLevel4Evidence.jsx` | **COMMIT_AND_PUSH** | Card sub-component |

**Note:** These are **new files** (not in git) and are **production code** required for the Premium Card feature.

---

### 4. FRONTEND SERVICES/UTILS/HOOKS

| File | Classification | Reason |
|------|----------------|--------|
| `frontend/src/services/premiumCardResearch.js` | **COMMIT_AND_PUSH** | Premium Card data service |
| `frontend/src/utils/cardPresentation.js` | **COMMIT_AND_PUSH** | Card presentation logic |
| `frontend/src/hooks/useCountUp.js` | **COMMIT_AND_PUSH** | Animation hook |
| `frontend/src/hooks/useReveal.js` | **COMMIT_AND_PUSH** | Animation hook |
| `frontend/src/hooks/useScrollRegion.js` | **COMMIT_AND_PUSH** | Scroll hook (also used elsewhere) |

**Note:** These are **new files** (not in git) and are **production code** required for the Premium Card feature.

---

### 5. BACKEND DATABASE

| File | Classification | Reason |
|------|----------------|--------|
| `backend/scholarzone.db` | **DATABASE_ONLY** | **NOT tracked** (explicitly ignored in .gitignore) |

**Git tracking status:** `git ls-files backend/scholarzone.db` → **NO OUTPUT** (not tracked)

**Ignored by .gitignore:**
```
*.db
backend/scholarzone.db
```

**Production state:** The 14 rows with JSON data (14 target scholarships) are **runtime state** in the database. No separate migration file is needed because:
1. The JSON columns (`official_details`, `applicant_utility`, `programme_verification`) already exist in the schema
2. The data was written via normal application code paths (transactions)
3. The canonical baseline (691 rows) includes these as part of normal DB state
4. Deployments use the live DB, not a seed/migration

---

### 6. EXISTING REPO CLUTTER (PRE_EXISTING_UNRELATED)

The following are **PRE_EXISTING_UNRELATED** — they existed before Premium Card work and are unrelated:

| Pattern | Count | Action |
|---------|-------|--------|
| `*.md` reports (SCHOLARZONE_*, WAVE*, MENTOR_*, etc.) | 50+ | Already untracked, leave as-is |
| `backend/*.py` scripts (dry_run, audit, etc.) | 100+ | Already untracked, leave as-is |
| `backend/scripts/` legacy scripts | 30+ | Already untracked, leave as-is |
| `backend/tests/test_wave13_hardening.py` | 1 | Already in repo (broken import) |
| `backend/research_output/` | 20+ | Already untracked |
| `backend/config/*.pre_*` | 10+ | Already untracked |
| Root `*.json` source files (denmark_scholarships.json, etc.) | 10+ | Already untracked |
| `frontend/public/research/` (other than premium_card) | ? | Check separately |

---

## CRITICAL DETERMINATIONS

### Is `backend/scholarzone.db` tracked?
**NO** — Correctly ignored by .gitignore (`*.db`, `backend/scholarzone.db`)

### Is premium-card research JSON tracked?
**NO** — `research/premium_card/output/` is not in git ls-files

### Is `frontend/public/research/` tracked?
**NO** — Not in git ls-files

### Are frontend/public/research files required for production frontend?
**YES** — The Premium Card component fetches data from `/research/premium_card/output/scholarship_XXX.json` at runtime. These must be present in the deployed `public/` directory.

**Deployment Strategy:** The research JSON files should be copied to `frontend/public/research/premium_card/output/` as part of the **build/deploy pipeline**, NOT committed to git. They are generated artifacts.

### Should generated duplicate mirror be committed?
**NO** — `frontend/public/research/premium_card/output/` is a **DUPLICATE_MIRROR** of `research/premium_card/output/`. Committing both would duplicate 70 JSON files in git history. The canonical source is `research/premium_card/output/`; the public mirror is a build artifact.

### Is a separate production DB migration required for the 14 stored rows?
**NO** — The JSON columns (`official_details`, `applicant_utility`, `programme_verification`) already exist in the production schema. The 14 rows with data are part of the **live database state** (691-row canonical baseline). They were written via normal transactional application code. No ALTER TABLE or data migration script is needed.

---

## FILES TO COMMIT (17 files)

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
research/premium_card/research_runner.py
research/premium_card/merge_execute.py
research/premium_card/merge_research.py

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

---

## DO NOT COMMIT (50+ files - already untracked)

All existing `.md` reports, `backend/*.py` scripts, `backend/scripts/`, `backend/research_output/`, `backend/config/*.pre_*`, root `*.json` source files, and the 70 research output JSONs in `research/premium_card/output/`.

---

## DATABASE_ONLY

```
backend/scholarzone.db
```

---

## GENERATED_ARTIFACTS (70 files)

```
research/premium_card/output/scholarship_*.json (70 files)
```

---

## DUPLICATE_MIRROR (70 files)

```
frontend/public/research/premium_card/output/scholarship_*.json (70 files)
```

---

## PRODUCTION_DB_MIGRATION_REQUIRED: **NO**

**Reason:** The 14 rows with JSON data are normal runtime database state in existing columns. No schema changes, no seed data migration, no ALTER TABLE needed. The canonical baseline (691 rows) includes these rows.

---

## FINAL METRICS

| Metric | Value |
|--------|-------|
| **FILES_TO_COMMIT** | 17 (production code + audit trail) |
| **DATABASE_ONLY** | 1 (scholarzone.db) |
| **GENERATED_ARTIFACTS** | 70 (research JSON output) |
| **DO_NOT_COMMIT** | 50+ (existing untracked clutter) |
| **DUPLICATE_MIRROR** | 70 (frontend public mirror) |
| **PRE_EXISTING_UNRELATED** | 200+ (existing repo files) |
| **MANUAL_REVIEW** | 0 |
| **PRODUCTION_DB_MIGRATION_REQUIRED** | NO |
| **GIT_MUTATIONS** | 0 |
| **DATABASE_WRITES** | 0 |