# ScholarZone Architecture Audit Report

**Repository:** C:\Users\GopaL\Desktop\Projects folder\ScholarZone
**Branch:** feature/global-catalogue-expansion-2026-11-07
**Base SHA:** 606e233199ce8a2b279f35e5afd5d974efe3efe6
**Head SHA:** d53ccf633f9df1c5ff3be99ddd90e629df9ab522
**Audit Date:** 2026-11-07

---

## 1. Application Architecture Map

### 1.1 Canonical Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        SCHOLARZONE DATA FLOW                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

OFFICIAL SOURCES
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  RESEARCH / EVIDENCE COLLECTION (Manual + Automated)                           │
│  • backend/verification/research_ledger_*.jsonl                                 │
│  • backend/scripts/ingest_research.py                                           │
│  • backend/scripts/ingest_world_top_demand*.py                                  │
│  • backend/scripts/ingest_country_intelligence.py                               │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  INGESTION & VALIDATION                                                         │
│  • backend/app/services/scholarship_ingestion.py (ScholarshipIngestionRecord)  │
│  • Pydantic validation: URL format, image evidence, vocabulary constraints     │
│  • Duplicate official_source_url rejection (validate_catalogue)                │
│  • upsert_verified_scholarships() → database                                    │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  ORM / DATABASE LAYER                                                           │
│  • backend/app/models.py (Scholarship + 20+ related models)                    │
│  • backend/app/database.py (SQLAlchemy engine, migrations, session mgmt)       │
│  • backend/app/repositories/scholarships.py (public_visibility_conditions)     │
│  • Migrations: backend/migrations/merge_premium_card_research.sql              │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  BACKEND APIs (FastAPI)                                                         │
│  • backend/app/main.py (app factory, lifespan, middleware, health)             │
│  • backend/app/routers/scholarships.py (public directory + detail)             │
│  • backend/app/routers/match.py, counts.py, countries.py                       │
│  • backend/app/services/scholarships.py (business logic)                       │
│  • backend/app/services/counting/catalogue.py (single-query stats)             │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  STATIC SNAPSHOT GENERATION                                                     │
│  • backend/scripts/build_public_snapshot.py                                     │
│  • Output: frontend/public/scholarships-snapshot.json (2.1 MB, 500+ records)   │
│  • Uses SAME public_visibility_conditions() as live API                         │
│  • frontend/scripts/build-sitemap.mjs (generates sitemap.xml from snapshot)    │
└─────────────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (React + Vite)                                                        │
│  • frontend/src/services/scholarshipService.js (static-first API client)       │
│  • frontend/src/services/staticScholarshipService.js (snapshot reader)         │
│  • frontend/src/hooks/useScholarshipDirectory.js, useScholarshipStats.js       │
│  • frontend/src/components/card/ScholarshipCard.jsx                            │
│  • frontend/src/pages/ScholarshipsPage.jsx, ScholarshipDetailsPage.jsx         │
│  • frontend/middleware.js (Vercel Edge: per-route SEO + real 404s)             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Entry Points

| Entry Point | Type | File | Purpose |
|-------------|------|------|---------|
| `backend/app/main.py` | FastAPI app factory | Web server | HTTP API server |
| `backend/scripts/build_public_snapshot.py` | CLI script | Build-time | Generate static catalogue |
| `backend/scripts/ingest_research.py` | CLI script | Manual | Ingest research JSONL |
| `backend/scripts/ingest_country_intelligence.py` | CLI script | Scheduled | Ingest country data |
| `backend/app/jobs/scholarzone_maintenance.py` | CLI worker | GitHub Actions cron | 20-stage maintenance |
| `backend/app/services/scheduler_engine.py` | In-process scheduler | Background | Verification scheduling |
| `frontend/src/main.jsx` | React app | Browser | SPA entry |
| `frontend/middleware.js` | Edge middleware | Vercel | SEO + 404s |
| `.github/workflows/catalogue-snapshot.yml` | CI workflow | GitHub Actions | Build snapshot on push |
| `.github/workflows/ci.yml` | CI workflow | GitHub Actions | Test matrix (PG16/18) |
| `.github/workflows/production-purge-preflight.yml` | CI workflow | Manual dispatch | 7-gate production purge |
| `vercel.json` cron | Platform cron | Vercel | `/api/internal/maintenance/dispatch` |

### 1.3 Key Data Contracts

1. **ScholarshipIngestionRecord** (`backend/app/services/scholarship_ingestion.py:37`) - Canonical ingestion format
2. **ScholarshipResponse / ScholarshipDetailResponse** (`backend/app/schemas.py:67`) - Public API contract
3. **public_visibility_conditions()** (`backend/app/repositories/scholarships.py:67`) - Single source of truth for visibility
4. **ScholarshipQuery** (`backend/app/schemas.py:53`) - Validated query parameters
5. **Snapshot format** (`backend/scripts/build_public_snapshot.py:79`) - Static export contract

---

## 2. Code Quality & Structure Analysis

### 2.1 Critical Findings

| ID | File | Issue | Severity |
|----|------|-------|----------|
| CQ-001 | `backend/app/main.py:328-366` | **Unauthenticated write endpoint** `/debug/fix-null-lists` - GET request that writes to production DB with no auth (only env check) | **Critical** |
| CQ-002 | `backend/app/routers/scholarships.py:154-187` | **Duplicate unauthenticated write endpoint** `/debug/fix-null-lists` in router (admin_secret dep but still GET) | **Critical** |
| CQ-003 | `backend/app/services/lifecycle_manager.py` | **String-based lifecycle indicators** - Uses text search in notes/verification_notes for "next cycle" detection (lines 179-191) | **High** |
| CQ-004 | `frontend/src/utils/lifecycle.js` | **Different lifecycle logic** - Frontend has 6 states vs backend's 4, different precedence rules | **High** |
| CQ-005 | `backend/app/jobs/scholarzone_maintenance.py:116-153` | **Node.js subprocess for lifecycle classification** - Spawns Node to run frontend JS for classification | **High** |

### 2.2 Duplicated Logic

| Logic | Locations | Issue |
|-------|-----------|-------|
| **Lifecycle Classification** | `backend/app/services/lifecycle_manager.py` + `frontend/src/utils/lifecycle.js` | Two implementations, different states (4 vs 6), different precedence |
| **Funding/Degree Taxonomy** | `backend/app/services/taxonomy.py` + `frontend/src/services/staticScholarshipService.js` (lines 139-182) | Duplicated keyword matching logic |
| **Status Classification** | `backend/app/services/auto_delete_policy.py` + `backend/app/services/retention_contract.py` + `backend/app/services/lifecycle_manager.py` | Three overlapping state machines |
| **Image Validation** | `backend/app/services/image_validator.py` + `backend/app/services/scholarship_ingestion.py` (lines 187-267) | Ingestion re-implements evidence gate |
| **Snapshot Stats** | `backend/scripts/build_public_snapshot.py:181-230` + `backend/app/services/counting/catalogue.py` | Different counting logic for same metrics |

### 2.3 Conflicting Sources of Truth

| Domain | Conflicting Implementations |
|--------|----------------------------|
| **Lifecycle States** | Backend: 4 states (open, upcoming, closing-soon, closed). Frontend: 6 states (adds opening, unknown). Different precedence. |
| **Verification Status** | `is_verified` (legacy bool) vs `verification_status` (authoritative enum). Schema validator derives `verified` from `verification_status` but model has both. |
| **Fully Funded** | `funding` string label vs `fully_funded` tri-state bool vs `funding_details` JSON array. Ingestion computes `fully_funded` from `funding_type` but model allows explicit None. |
| **Public Visibility** | `public_visibility_conditions()` is canonical but `config.py` has obsolete `public_require_verified` flags that are documented as unused but still readable. |
| **Deadline Precision** | `deadline_precision` enum (exact/month/varies/unknown) but ingestion coerces missing to "varies" while model default is "month". |

### 2.4 Dead / Unreachable Code

| File | Code | Evidence |
|------|------|----------|
| `backend/app/main.py:328-366` | `/debug/fix-null-lists` | Only reachable in non-production; writes to DB on GET |
| `backend/app/routers/scholarships.py:154-187` | Duplicate debug endpoint | Same as above |
| `backend/app/core/config.py:136-144` | `public_require_verified` flags | Commented as "OBSOLETE - no longer filters public directory" |
| `backend/app/services/scheduler_v2.py` | Referenced in imports but file not found | Imported by `scheduler_engine.py` line 31 but doesn't exist |

### 2.5 Circular Dependency Risks

| Cycle | Files |
|-------|-------|
| `database.py` ↔ `models.py` ↔ `models_supervisor.py` | `database.py` imports `models_supervisor` for side-effect (line 14), `models.py` imports `maintenance_slots` (line 8) |
| `scholarship_ingestion.py` ↔ `image_validator.py` ↔ `scholarship_image_verifier.py` | Ingestion imports both validators; validators may import ingestion types |

### 2.6 Silent Failures / Non-Idempotent Jobs

| File | Issue |
|------|-------|
| `backend/app/jobs/scholarzone_maintenance.py:371-399` | Stage error convention: stages return `{"error": ...}` dict instead of raising; runner checks `detail.get("error")` but a stage that forgets this convention reports success |
| `backend/app/services/scholarship_ingestion.py:459-493` | `upsert_verified_scholarships` commits per-record; partial failure leaves some records inserted |
| `backend/scripts/build_public_snapshot.py:324-330` | Atomic write via temp file but no rollback if JSON serialization fails mid-write |
| `backend/app/services/retention_engine.py` | `delete_bounded` re-reads and re-classifies each row but uses separate transactions per batch |

---

## 3. Configuration & Deployment Audit

### 3.1 Environment Variables

| Variable | Required | Used In | Notes |
|----------|----------|---------|-------|
| `SCHOLARZONE_ENVIRONMENT` | Yes | `config.py`, `main.py` | `production` \| `development` \| `test` |
| `SCHOLARZONE_DATABASE_URL` | Prod only | `config.py`, `database.py` | Must be PostgreSQL in prod |
| `SCHOLARZONE_ALLOWED_ORIGINS` | No | `config.py` | Defaults to localhost + GitHub Pages + Vercel |
| `SCHOLARZONE_VERIFICATION_SECRET` | Yes | `config.py` (as admin_secret fallback) | Used for admin endpoints |
| `SCHOLARZONE_ADMIN_SECRET` | No | `config.py` | Falls back to VERIFICATION_SECRET |
| `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED` | No | `config.py` | **Obsolete** - documented as unused |
| `SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE` | No | `config.py` | **Obsolete** |
| `SCHOLARZONE_PUBLIC_ALLOW_THIRD_PARTY_IMAGE` | No | `config.py` | **Obsolete** |
| `SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED` | No | `config.py` | Gates discovery trigger |
| `VERCEL_URL` | Platform | `config.py` | Auto-added to allowed origins |
| `SCHOLARZONE_API_URL` | Deploy | `deploy.yml` | Repository variable for health checks |
| `EXPECTED_NEON_PROJECT_ID` | Gates 2-6 | `production-purge-preflight.yml` | Secret |
| `SCHOLARZONE_DATABASE_URL_RO` | Gates 2-6 | `production-purge-preflight.yml` | Read-only Neon connection |

### 3.2 Build Process & Provenance

| Aspect | Implementation | Risk |
|--------|----------------|------|
| **Build Provenance** | `backend/app/build_provenance.py` embeds `VERCEL_GIT_COMMIT_SHA` at build time into `build_revision.txt` | ✅ Strong - rejects uppercase, requires 40-char SHA |
| **Docker Build** | `Dockerfile:35` runs `embed_build_revision.py` | ⚠️ Local builds get "dev" marker; CI must run on Vercel for real SHA |
| **Health Endpoint** | `/health` returns revision + DB connectivity | ✅ Verifies both build identity and DB |
| **Static Assets** | Snapshot + sitemap committed to repo by CI | ✅ Version-controlled fallback |
| **Frontend Build** | `package.json:7` prebuild generates logos + sitemap | ⚠️ Sitemap generation depends on snapshot existing |

### 3.3 Static-First Architecture Verification

**Claim:** "Public browsing works without DB"

**Verification:**
- ✅ `scholarshipService.js` has `getStaticCatalogueMode()` defaulting to `true` in production
- ✅ `staticScholarshipService.js` reads `scholarships-snapshot.json` from `BASE_URL`
- ✅ `fetchScholarships`/`fetchScholarshipById`/`fetchScholarshipStats` all try snapshot first in static mode
- ✅ `middleware.js` serves 404 for unknown detail IDs from snapshot
- ✅ Sitemap generated from snapshot
- ⚠️ **Gap:** `useScholarshipDirectory.js` falls back to hardcoded `fallbackScholarships` (17 items) if both API and snapshot fail
- ⚠️ **Gap:** HomePage has hardcoded `FLAGSHIP_PROGRAMMES` (8 items) that are NOT from snapshot

### 3.4 Deployment Configuration

| Platform | Config | Status |
|----------|--------|--------|
| **Vercel** | `vercel.json` (root + backend + frontend) | ✅ Services + rewrites + cron |
| **Render** | `render.yaml` | ✅ Docker + health check + env vars |
| **GitHub Pages** | `catalogue-snapshot.yml` commits to `frontend/public/` | ✅ Fallback hosting |
| **GitHub Actions** | 13 workflows | ✅ Comprehensive CI + gates |

---

## 4. Operational Risks

### 4.1 Database Migration Strategy

| Risk | Details | Severity |
|------|---------|----------|
| **SQLite ↔ PostgreSQL Divergence** | `database.py` has separate `_upgrade_sqlite_schema` (lines 651-772) and `_upgrade_postgresql_schema` (lines 225-383) with duplicated column lists | **High** |
| **Migration Not Versioned** | No Alembic; startup runs `create_all` + ad-hoc `ALTER TABLE` | **High** |
| **Production Skips Migration** | `main.py:96-116` production only verifies connectivity, no schema changes | **Medium** |
| **Schema Validation Only on PG** | `_validate_postgresql_schema` (lines 386-465) raises on missing objects but SQLite has no equivalent | **Medium** |
| **Fully Funded Column Migration** | Complex SQLite table rebuild (`_migrate_fully_funded_to_nullable_sqlite`, lines 468-649) with regex on CREATE SQL | **High** |

### 4.2 Scheduler / Cron Design

| Component | Schedule | Risk |
|-----------|----------|------|
| **Vercel Cron** | `vercel.json:48-51` daily 09:00 UTC `/api/internal/maintenance/dispatch` | ⚠️ Single endpoint, no visibility into stages |
| **GitHub Actions** | `.github/workflows/*.yml` various schedules | ✅ Visible logs, manual dispatch |
| **APScheduler (Legacy)** | `main.py:284-286` explicitly NOT started in production | ✅ Documented |
| **Maintenance Slots** | `backend/app/services/maintenance_slots.py` + `maintenance_cursor.py` | ✅ Durable round-robin cursors |
| **Scheduler Engine** | `backend/app/services/scheduler_engine.py` in-process ThreadPoolExecutor | ⚠️ Not distributed; single-instance only |

### 4.3 Secret Handling

| Secret | Storage | Rotation | Risk |
|--------|---------|----------|------|
| `SCHOLARZONE_VERIFICATION_SECRET` | Vercel/Render env vars | Not documented | **Medium** - Used as admin_secret fallback |
| `SCHOLARZONE_DATABASE_URL` | Vercel/Render env vars | Not documented | **High** - Production DB credentials |
| `NEON_API_KEY` | GitHub Actions secret | Not documented | **Medium** - Gate 4 backup |
| `GPG_RECIPIENT` / `GPG_EXPECTED_FINGERPRINT` | GitHub Actions secret | Not documented | **Medium** - Gate 4 encryption |
| `AZURE_CLIENT_ID/TENANT/SUBSCRIPTION` | GitHub Actions secret | Not documented | **Medium** - Gate 4 storage |

### 4.4 Rate Limiting

| Limiter | Scope | Limit | Risk |
|---------|-------|-------|------|
| `supervisor_read_limiter` | In-process | 120/min | ⚠️ Per-instance only |
| `draft_limiter` | In-process | 20/min | ⚠️ Per-instance only |
| `outreach_write_limiter` | In-process | 60/min | ⚠️ Per-instance only |
| **Public API** | None | Unlimited | **High** - No throttling on `/scholarships` |

### 4.5 Logging of Sensitive Data

| File | Issue |
|------|-------|
| `backend/app/main.py:217-218` | `logger.exception("Unhandled application error", exc_info=exc)` - logs full traceback |
| `backend/app/jobs/scholarzone_maintenance.py:62` | `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` - all output to stdout |
| `backend/app/services/retention_engine.py` | Logs scholarship titles and IDs in audit trails |
| `backend/app/database.py:443-448` | Logs critical schema validation failures with table names |

### 4.6 Error Messages Revealing Internals

| Endpoint | Risk |
|----------|------|
| `/health` | Returns `init_error` with full exception message (line 280) |
| `/debug/raw/{id}` | Returns ALL model columns including internal fields (line 149) |
| `/scholarships/debug/fix-null-lists` | Returns raw SQL and IDs fixed |
| General 500 handler | Returns "An unexpected server error occurred." - ✅ Generic |

---

## 5. Defects Summary (Severity Ranked)

### Critical (4)

| ID | Title | File | Root Cause | Fix |
|----|-------|------|------------|-----|
| C-01 | Unauthenticated DB write endpoint | `main.py:328-366`, `scholarships.py:154-187` | Debug endpoints left in code with only env guard | Remove or protect with proper auth + POST method |
| C-02 | No rate limiting on public API | `main.py`, `routers/scholarships.py` | Never implemented | Add middleware or per-route limiters |
| C-03 | Production DB migration skipped | `main.py:96-116` | Cold-start lock contention fear | Use proper migration tool (Alembic) with lock timeout |
| C-04 | Hardcoded fallback data bypasses snapshot | `HomePage.jsx:14-174`, `useScholarshipDirectory.js:48` | Editorial examples + local fallback not from snapshot | Remove hardcoded data; rely solely on snapshot |

### High (8)

| ID | Title | File | Root Cause | Fix |
|----|-------|------|------------|-----|
| H-01 | Dual lifecycle implementations | `lifecycle_manager.py` + `lifecycle.js` | Frontend needed richer states; backend stayed simple | Unify to single contract; share via OpenAPI or generate |
| H-02 | Node.js subprocess for classification | `scholarzone_maintenance.py:116-153` | Reuse frontend logic | Port classification to Python or use shared WASM |
| H-03 | Duplicated taxonomy logic | `taxonomy.py` + `staticScholarshipService.js:139-182` | Independent implementations | Single source (backend) + generate frontend constants |
| H-04 | Three overlapping state machines | `auto_delete_policy.py`, `retention_contract.py`, `lifecycle_manager.py` | Evolved separately | Consolidate into one authoritative contract |
| H-05 | SQLite/PostgreSQL migration divergence | `database.py:225-772` | Ad-hoc startup migrations | Adopt Alembic with versioned migrations |
| H-06 | In-process rate limiters only | `rate_limit.py:80-82` | No Redis/cluster | Document limitation; plan shared-state limiter |
| H-07 | Stage error convention fragile | `scholarzone_maintenance.py:390-395` | Convention not enforced | Use exceptions; catch at runner level |
| H-08 | `scheduler_v2.py` imported but missing | `scheduler_engine.py:31` | File deleted/renamed | Fix import or restore file |

### Medium (12)

| ID | Title | File | Root Cause |
|----|-------|------|------------|
| M-01 | Obsolete config flags still readable | `config.py:136-144` | Not removed after deprecation |
| M-02 | `fully_funded` tri-state vs string label confusion | `models.py:137`, `schemas.py:150`, `ingestion.py:365-366` | Multiple representations |
| M-03 | `deadline_precision` default mismatch | `models.py:33` (month) vs `ingestion.py:358-359` (varies) | Ingestion overrides default |
| M-04 | Health endpoint returns init_error detail | `main.py:279-280` | Debug info in production |
| M-05 | Snapshot validation rejects empty array | `staticScholarshipService.js:69-70` | Legitimate empty catalogue possible |
| M-06 | Middleware excludes `/countries` from sitemap/SEO | `middleware.js:38-42`, `build-sitemap.mjs:45-52` | Design decision not re-validated |
| M-07 | `verification_contract.py` not found but imported | `schemas.py:17-21` | File missing or renamed |
| M-08 | `legacy_id` unique but nullable | `models.py:25` | SQLite allows multiple NULLs in unique column |
| M-09 | `cryptography` version range broad | `requirements.txt:11` | `>=42,<51` spans major versions |
| M-10 | `pypdf`/`pdfplumber` pinned but lazy-loaded | `requirements.txt:43-44` | Missing pins caused silent PDF skip |
| M-11 | Sitemap generation has no lastmod for many records | `build-sitemap.mjs:105-108` | `last_verified_at` often missing |
| M-12 | `PURGE_CLOSED_EXCLUDED_FROM_ALL = False` but asserted at runtime | `scholarzone_maintenance.py:97` | Config drift risk |

### Low (6)

| ID | Title | File |
|----|-------|------|
| L-01 | Debug imports script unused | `backend/scripts/debug_imports.sh` |
| L-02 | Duplicate `image_source_url` in `ScholarshipResponse` | `schemas.py:168, 186` |
| L-03 | Duplicate `image_verified_at` in `ScholarshipResponse` | `schemas.py:172, 187` |
| L-04 | Duplicate `image_alt_text` in `ScholarshipResponse` | `schemas.py:173, 188` |
| L-05 | Duplicate `last_verified_date` in `ScholarshipResponse` | `schemas.py:184, 189` |
| L-06 | Duplicate `notes` in `ScholarshipResponse` | `schemas.py:185, 190` |

---

## 6. Root Cause Analysis

### 6.1 Architectural Drift
The codebase evolved from a simple catalogue to a complex multi-surface product (public directory, student dashboard, mentor matching, supervisor discovery, admin tools). Each surface added its own state machine and validation logic rather than extending a shared core.

### 6.2 Missing Abstraction Boundaries
- **Lifecycle** implemented in 3 places (backend service, frontend utils, retention engine)
- **Funding classification** in 2 places (backend taxonomy, frontend static service)
- **Visibility rules** in config flags (obsolete) + repository function (canonical) + retention contract (reuses repository)

### 6.3 Test-Driven But Not Contract-Driven
Tests verify behavior but contracts (OpenAPI, JSON Schema, TypeScript types) are not generated from a single source. Frontend/Backend drift is caught by integration tests, not prevented by shared types.

### 6.4 Operational Debt Accumulation
- 89 scripts in `backend/scripts/` - many one-off, some production-critical
- 13 GitHub workflows - complex interdependencies
- Migration strategy never formalized (no Alembic)
- Rate limiting added only for authenticated surfaces

### 6.5 Static-First Claims Not Fully Realized
Hardcoded `FLAGSHIP_PROGRAMMES` in HomePage and `fallbackScholarships` in local data mean the "static-first" architecture has escape hatches that serve non-snapshot data.

---

## 7. Files Requiring Changes (Priority Order)

### Immediate (Critical)
1. `backend/app/main.py` - Remove `/debug/fix-null-lists` or secure it
2. `backend/app/routers/scholarships.py` - Remove duplicate debug endpoint
3. `backend/app/main.py` / `backend/app/core/rate_limit.py` - Add public API rate limiting

### Short-term (High)
4. `backend/app/services/lifecycle_manager.py` + `frontend/src/utils/lifecycle.js` - Unify lifecycle contract
5. `backend/app/jobs/scholarzone_maintenance.py` - Replace Node.js subprocess with Python classification
6. `backend/app/services/taxonomy.py` + `frontend/src/services/staticScholarshipService.js` - Single taxonomy source
7. `backend/app/database.py` - Adopt Alembic for versioned migrations
8. `backend/app/services/auto_delete_policy.py`, `retention_contract.py`, `lifecycle_manager.py` - Consolidate state machines

### Medium-term (Medium)
9. `backend/app/core/config.py` - Remove obsolete config flags
10. `backend/app/schemas.py` - Fix duplicate fields in `ScholarshipResponse`
11. `backend/app/services/scholarship_ingestion.py` - Align `deadline_precision` default with model
12. `frontend/src/pages/HomePage.jsx` - Remove hardcoded `FLAGSHIP_PROGRAMMES`
13. `frontend/src/hooks/useScholarshipDirectory.js` - Remove hardcoded `fallbackScholarships`
14. `backend/app/services/scheduler_engine.py` - Fix missing `scheduler_v2` import
15. `frontend/middleware.js` + `frontend/scripts/build-sitemap.mjs` - Re-evaluate `/countries` exclusion

### Long-term (Low)
16. `backend/scripts/` - Archive or document one-off scripts
17. `requirements.txt` - Narrow `cryptography` version range
18. `backend/app/services/verification_contract.py` - Restore missing file or fix import

---

## 8. Risk Assessment

| Risk Category | Likelihood | Impact | Overall |
|---------------|------------|--------|---------|
| **Data Loss from Unauthenticated Write** | Medium | Critical | **Critical** |
| **API Abuse / DoS** | High | High | **Critical** |
| **Schema Drift (SQLite vs PG)** | High | High | **High** |
| **Lifecycle Bugs (Frontend ≠ Backend)** | High | Medium | **High** |
| **Migration Failure in Production** | Medium | High | **High** |
| **Secret Leak via Logs/Errors** | Low | High | **Medium** |
| **Rate Limiter Bypass (Multi-instance)** | Medium | Medium | **Medium** |
| **Static-First Bypass (Hardcoded Data)** | Low | Medium | **Low** |
| **Snapshot/Sitemap Drift** | Low | Low | **Low** |

---

## 9. Recommendations Summary

1. **Immediate Security**: Remove unauthenticated write endpoints; add public API rate limiting
2. **Contract Unification**: Single lifecycle/funding/visibility contract shared via code generation
3. **Migration Formalization**: Adopt Alembic; version all schema changes; test PG migrations in CI
4. **Operational Hardening**: Shared-state rate limiter; structured logging without secrets; secret rotation policy
5. **Static-First Compliance**: Remove all hardcoded fallback data; snapshot is the only source
6. **Technical Debt Reduction**: Consolidate 3 state machines; eliminate Node.js subprocess; archive one-off scripts

---

*Report generated by AGENT A — Repository and Architecture Audit for ScholarZone*
*Read-only inspection. No files modified.*