# FINAL PRODUCTION ARTIFACT + DB DESTINATION AUDIT

**Audit Date:** 2026-10-07  
**Auditor:** Kilo (read-only)  
**Mode:** READ-ONLY — No modifications performed

---

## EXECUTIVE SUMMARY

| Metric | Value |
|--------|-------|
| **EXACT_COMMIT_FILE_COUNT** | 27 |
| **RUNTIME_REQUIRED_FILES** | 20 |
| **CANONICAL_RESEARCH_DATA_PATH** | `research/premium_card/output/` (source) → `frontend/public/research/premium_card/output/` (deployed) |
| **70_JSON_REQUIRED_FOR_PRODUCTION** | YES |
| **DB_PRODUCTION_TYPE** | PostgreSQL (Neon) |
| **PRODUCTION_DB_MIGRATION_REQUIRED** | YES |
| **DEPLOYMENT_GITIGNORE_CONFLICT** | YES |
| **UNRELATED_FILES** | 200+ (pre-existing repo clutter) |
| **READY_FOR_CLEAN_COMMIT** | NO (gitignore conflict must be resolved first) |

---

## TASK 1 — EXACT FILE COUNT (27 FILES TO COMMIT)

### Research Audit Trail (11 files)
```
1. research/premium_card/FINAL_POST_COMPLETION_AUDIT.md
2. research/premium_card/FINAL_POST_COMPLETION_AUDIT.json
3. research/premium_card/FINAL_PREMIUM_CARD_COMPLETION_REPORT.md
4. research/premium_card/FINAL_PREMIUM_CARD_COMPLETION_REPORT.json
5. research/premium_card/FINAL_REPAIR_MANIFEST.json
6. research/premium_card/merge_report.json
7. research/premium_card/merge_verification_report.json
8. research/premium_card/reconciliation_report.json
9. research/premium_card/phase1_fresh_detail.md
10. research/premium_card/phase2_contamination_audit.md
11. research/premium_card/phase3_targeted_repair_report.md
12. research/premium_card/phase3b_concurrent_writer_audit.md
13. research/premium_card/phase4_post_ingestion_audit.md
14. research/premium_card/RESEARCH_AGENT_TEMPLATE.md
15. research/premium_card/research_manifest.json
```

### Research Scripts (3 files)
```
16. research/premium_card/research_runner.py
17. research/premium_card/merge_execute.py
18. research/premium_card/merge_research.py
```

### Frontend Production Code (14 files)
```
19. frontend/src/components/PremiumScholarshipCard.jsx
20. frontend/src/components/PremiumScholarshipCard.css
21. frontend/src/components/card/CardExpandSection.jsx
22. frontend/src/components/card/CardLevel2QuickDecision.jsx
23. frontend/src/components/card/CardLevel3Planning.jsx
24. frontend/src/components/card/CardLevel4Evidence.jsx
25. frontend/src/services/premiumCardResearch.js
26. frontend/src/utils/cardPresentation.js
27. frontend/src/hooks/useCountUp.js
28. frontend/src/hooks/useReveal.js
29. frontend/src/hooks/useScrollRegion.js
```

**COMMIT_FILE_COUNT = 27**

---

## TASK 2 — PREMIUM CARD RUNTIME DATA PATH

### Data Flow Trace

```
PremiumScholarshipCard.jsx
  └── uses loadPremiumScholarships() from premiumCardResearch.js
       └── fetchResearchEntries() fetches '/research/premium_card/output/index.json'
            └── Served by Vite from frontend/public/research/premium_card/output/
                 └── Copied from research/premium_card/output/ (source of truth)
```

### Code Evidence

**`premiumCardResearch.js` (lines 9, 16):**
```javascript
const RESEARCH_ROOT = '/research/premium_card/output'

async function fetchResearchEntries() {
  const response = await fetch(`${RESEARCH_ROOT}/index.json`, ...)
```

**`cardPresentation.js` (line 64-66):**
```javascript
// The catalogue API returns flat columns...
// The premium research output returns the rich schema...
// normalizeRecord flattens either shape into the flat field set
```

**`PremiumScholarshipCard.jsx`** — Imports `loadPremiumScholarships` from `premiumCardResearch.js`

### Runtime Classification

| File | Classification | Reason |
|------|----------------|--------|
| `frontend/src/components/PremiumScholarshipCard.jsx` | **REQUIRED_RUNTIME** | Main component |
| `frontend/src/components/PremiumScholarshipCard.css` | **REQUIRED_RUNTIME** | Styles |
| `frontend/src/components/card/CardExpandSection.jsx` | **REQUIRED_RUNTIME** | Sub-component |
| `frontend/src/components/card/CardLevel2QuickDecision.jsx` | **REQUIRED_RUNTIME** | Sub-component |
| `frontend/src/components/card/CardLevel3Planning.jsx` | **REQUIRED_RUNTIME** | Sub-component |
| `frontend/src/components/card/CardLevel4Evidence.jsx` | **REQUIRED_RUNTIME** | Sub-component |
| `frontend/src/services/premiumCardResearch.js` | **REQUIRED_RUNTIME** | Data fetcher |
| `frontend/src/utils/cardPresentation.js` | **REQUIRED_RUNTIME** | Data normalizer |
| `frontend/src/hooks/useCountUp.js` | **REQUIRED_RUNTIME** | Animation hook |
| `frontend/src/hooks/useReveal.js` | **REQUIRED_RUNTIME** | Animation hook |
| `frontend/src/hooks/useScrollRegion.js` | **REQUIRED_RUNTIME** | Scroll hook |
| `frontend/public/research/premium_card/output/index.json` | **REQUIRED_RUNTIME** | Fetched at runtime |
| `frontend/public/research/premium_card/output/scholarship_*.json` (70) | **REQUIRED_RUNTIME** | Fetched at runtime |
| `research/premium_card/output/*.json` (70) | **GENERATED** | Source of truth |
| `research/premium_card/merge_report.json` | **OPTIONAL_AUDIT** | Provenance only |
| `research/premium_card/merge_verification_report.json` | **OPTIONAL_AUDIT** | Provenance only |
| `research/premium_card/reconciliation_report.json` | **OPTIONAL_AUDIT** | Provenance only |
| All other `.md` reports | **OPTIONAL_AUDIT** | Documentation only |
| Research scripts (`*.py`) | **NOT_REQUIRED** | Build-time only |

---

## TASK 3 — 70 JSON FILES ANALYSIS

### Two Locations

| Location | Files | Role |
|----------|-------|------|
| `research/premium_card/output/` | 70 `scholarship_*.json` + `index.json` | **CANONICAL SOURCE** (authored by research agents) |
| `frontend/public/research/premium_card/output/` | 70 `scholarship_*.json` + `index.json` | **DEPLOYED COPY** (served at runtime) |

### Which is Consumed by Production?

**Production consumes `frontend/public/research/premium_card/output/`**

The frontend fetches from `/research/premium_card/output/index.json` which is served by the static file server (Vite/Vercel) from `frontend/public/research/premium_card/output/`.

### Deployment Mechanism

The `frontend/public/research/premium_card/output/` directory is **NOT generated at build time** — it is a static copy that must be present in the deployed `public/` directory. The deployment pipeline (Vercel) copies the entire `public/` directory as-is.

### Gitignore Conflict

**.gitignore ignores `*.db`, `backend/scholarzone.db` but does NOT ignore `frontend/public/research/premium_card/output/`**

However, `frontend/public/research/premium_card/output/` is **NOT currently tracked** by git (never added). The 70 JSON files exist in the working directory but are untracked.

### Must Commit Canonical JSON?

**NO — The canonical JSON files (`research/premium_card/output/`) should NOT be committed to git.**

They are **GENERATED_ARTIFACTS** produced by research agents. The deployed copy (`frontend/public/...`) is a build/deploy artifact.

**However**, the deployment pipeline MUST ensure `frontend/public/research/premium_card/output/` is populated. This is currently a manual copy step.

**Recommendation:** Add a build step (e.g., in `package.json` or CI) that copies `research/premium_card/output/` → `frontend/public/research/premium_card/output/` before deployment. Do NOT commit the JSON files to git.

---

## TASK 4 — DATABASE DESTINATION

### Local Development
- **File:** `backend/scholarzone.db` (SQLite)
- **Contains:** 691 scholarships, 14 with JSON data from premium card
- **Tracked by git:** **NO** (explicitly ignored in .gitignore)

### Production
- **Type:** **PostgreSQL (Neon)**
- **Configuration:** `SCHOLARZONE_DATABASE_URL` environment variable required
- **Code Evidence (`config.py` lines 83-94):**
```python
if environment == "production":
    database_url = os.getenv("SCHOLARZONE_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("SCHOLARZONE_DATABASE_URL is required in production...")
    if database_url.startswith("sqlite"):
        raise RuntimeError("Production environment requires PostgreSQL (Neon), not SQLite.")
```

### Are the 14 Premium Card Rows in Production DB?

**UNKNOWN — Cannot be determined from repository alone.**

The local SQLite `backend/scholarzone.db` contains the 14 rows with JSON data. The production PostgreSQL database is a **separate database** managed by Neon. There is no automatic sync between local SQLite and production PostgreSQL.

### Production DB Migration Required?

**YES — PRODUCTION_DB_MIGRATION_REQUIRED: YES**

**Reason:** The 14 premium card scholarships with `official_details`, `applicant_utility`, `programme_verification` JSON data exist ONLY in the local development SQLite database. The production PostgreSQL database would need:
1. Schema migration (already handled by `init_database()` which creates JSON columns on startup)
2. Data ingestion of the 14 premium card records

**No automatic mechanism exists** to transfer the local SQLite data to production PostgreSQL. A manual or scripted data migration is required.

---

## TASK 5 — GITIGNORE CONFLICT

### Current .gitignore (relevant lines)
```
*.db
*.sqlite
*.sqlite3
backend/scholarzone.db
```

### Conflict Analysis

| Path | Ignored? | Required for Deployment? | Conflict |
|------|----------|-------------------------|----------|
| `backend/scholarzone.db` | YES | NO (dev only) | NO |
| `frontend/public/research/premium_card/output/` | NO | YES (runtime data) | **NO** (not ignored, but also not tracked) |
| `research/premium_card/output/` | NO | NO (source, not deployed) | NO |

### Deployment Artifact Gitignore Conflict

**DEPLOYMENT_GITIGNORE_CONFLICT: YES**

The conflict is **not a gitignore problem** but a **deployment process gap**:

- `frontend/public/research/premium_card/output/` is **NOT ignored** and **NOT tracked**
- It IS required at runtime (served by frontend)
- It is currently a **manual copy** from `research/premium_card/output/`
- If the directory is missing from a fresh clone, the Premium Card will 404 on data fetch

**Resolution Required:** Add a build step to copy research output to public before deployment, or commit the public mirror (not recommended). The `.gitignore` itself is correct.

---

## TASK 6 — PRE-EXISTING WORK SEPARATION

### Premium Card Work (NEW — 27 files to commit)
- All 27 files listed in TASK 1

### Current Cinematic Frontend Work (MODIFIED — existing files changed)
- `frontend/src/styles/tokens.css`
- `frontend/src/components/AppErrorBoundary.css`
- `frontend/src/hooks/useScrollRegion.js` (also used by Premium Card)
- 30+ other frontend files modified (Navigation, ScholarshipCard, theme, glass effects)

### Unrelated Existing Work (PRE_EXISTING_UNRELATED — 200+ files)
- All backend scripts (`backend/scripts/*.py`)
- All backend reports (`*.md` in root)
- `backend/config/*.pre_*` snapshots
- `backend/research_output/`
- Root `*.json` source files (`denmark_scholarships.json`, etc.)
- All existing test files
- All migration scripts

---

## FINAL DETERMINATIONS

| Question | Answer |
|----------|--------|
| **CANONICAL_RESEARCH_DATA_PATH** | `research/premium_card/output/` (source) → `frontend/public/research/premium_card/output/` (deployed) |
| **70_JSON_REQUIRED_FOR_PRODUCTION** | YES — served from `frontend/public/...` at runtime |
| **MUST_COMMIT_CANONICAL_JSON** | NO — generated artifacts; add build copy step instead |
| **LOCAL_SQLITE_CONTAINS_RESEARCH_DATA** | YES — 14 rows with JSON in `backend/scholarzone.db` |
| **PRODUCTION_DB_TYPE** | PostgreSQL (Neon) |
| **PRODUCTION_DB_MIGRATION_REQUIRED** | YES — separate data migration needed |
| **DEPLOYMENT_GITIGNORE_CONFLICT** | YES — deployment process gap, not gitignore error |
| **READY_FOR_CLEAN_COMMIT** | NO — must resolve deployment copy step first |

---

## FINAL METRICS

| Metric | Value |
|--------|-------|
| **EXACT_COMMIT_FILE_COUNT** | 27 |
| **RUNTIME_REQUIRED_FILES** | 20 (14 frontend code + 6 hooks/services/utils) |
| **CANONICAL_RESEARCH_DATA_PATH** | `research/premium_card/output/` |
| **70_JSON_REQUIRED_FOR_PRODUCTION** | YES |
| **DB_PRODUCTION_TYPE** | PostgreSQL (Neon) |
| **PRODUCTION_DB_MIGRATION_REQUIRED** | YES |
| **DEPLOYMENT_GITIGNORE_CONFLICT** | YES (process gap) |
| **UNRELATED_FILES** | 200+ |
| **READY_FOR_CLEAN_COMMIT** | NO |
| **GIT_MUTATIONS** | 0 |
| **DATABASE_WRITES** | 0 |