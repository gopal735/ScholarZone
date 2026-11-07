# ScholarZone QA, CI, Security, SEO & Accessibility Audit Report

**Date:** 2026-11-07
**Branch:** feature/global-catalogue-expansion-2026-11-07
**Repository:** C:\Users\GopaL\Desktop\Projects folder\ScholarZone

---

## 1. TEST SUITE AUDIT

### 1.1 Test Counts
- **Backend (pytest):** 6,220 tests collected
- **Frontend (vitest):** 363 tests passed
- **Total:** ~6,583 tests

### 1.2 Test Categories & Coverage

| Category | Status | Notes |
|----------|--------|-------|
| Data Integrity | ✅ Well-covered | Multiple test files for counting, matching, schema, migrations |
| Lifecycle Management | ✅ Well-covered | Tests for archive, quarantine, auto-delete, retention gates |
| API Contracts | ✅ Well-covered | `test_scholarships.py`, `test_matching_api.py`, `test_api_prefix.py` |
| Database Migrations | ✅ Covered | `test_migration.py`, schema compat workflow |
| Frontend Routes | ✅ Covered | 363 vitest tests for components, pages, hooks |
| SEO | ✅ Covered | Sitemap validation in CI, structured data tests |
| Security | ⚠️ Partial | Zero-paid guard, secret scanning, but no dedicated security test suite |

### 1.3 Skipped Tests (17 locations found)

| File | Line | Reason |
|------|------|--------|
| `test_application_workspace.py` | 964 | Record not in match result set |
| `test_counting_core.py` | 212 | Record still produced fit score |
| `test_deployment_files.py` | 34, 150 | File not present |
| `test_do_logos_accepted_image.py` | 46 | ETHZ override absent |
| `test_git_integrity_regression.py` | 95, 119, 139 | Git not available |
| `test_import_regression.py` | 219 | Git not available |
| `test_mentor.py` | 1192 | No counted checklist |
| `test_purge_preflight.py` | 908, 982, 1064 | TEST_DATABASE_URL not set (integration tests) |
| `test_retention_recovery_gate.py` | 678 | No repository ledger |
| `test_supervisor_render_e2e.py` | 56 | Playwright driver not available |
| `test_test_isolation_boundary.py` | 281 | Skipif condition |
| `test_vercel_migration.py` | 207 | No CORS middleware |

**Assessment:** Most skips are conditional (missing optional dependencies like git, playwright, or test databases). The integration tests in `test_purge_preflight.py` are correctly skipped when no PostgreSQL is available - they run in CI with disposable DBs.

### 1.4 XFails
**None found** - No `@pytest.mark.xfail` markers in codebase.

### 1.5 Weak/Flaky Test Indicators
- **Dynamic test discovery:** 167 test files in backend - some may have weak assertions
- **Hardcoded expected values:** Some tests assert exact counts (e.g., `total: 752`, specific IDs) which may become brittle
- **Integration test skips:** 3 integration tests skip silently when DB unavailable - CI runs them with real DBs

### 1.6 Recommendations
1. Add `pytest --strict-markers` (already in pytest.ini)
2. Consider parametrizing hardcoded seed data expectations
3. Add explicit test for `data-sz-seo` tag cleanup on route transitions
4. Add regression test for `dangerouslySetInnerHTML` sanitization (see Security §3.4)

---

## 2. CI/CD WORKFLOW AUDIT

### 2.1 Workflow Files (14 total)

| Workflow | Trigger | Purpose | Issues |
|----------|---------|---------|--------|
| `ci.yml` | PR/push to main/master/fix branches | Main CI pipeline | ✅ Comprehensive; PostgreSQL matrix (16, 18); pipefail restored |
| `catalogue-snapshot.yml` | Push/PR to master (backend changes) | Snapshot + sitemap generation | ✅ Good; validates snapshot structure, sitemap exclusions |
| `frontend.yml` | Push to master (frontend changes) | GitHub Pages deploy | ✅ Uses repository variable for API URL |
| `deploy.yml` | Workflow_run (CI success) | Production deployment verification | ✅ Health check with revision verification |
| `zero-paid-guard.yml` | Push/PR | Dependency licensing guard | ✅ Checks for paid packages in frontend/backend |
| `production-purge-preflight.yml` | Manual (workflow_dispatch) | 7-gate production purge verification | ✅ Read-only gates; environment protection |
| `purge-ui-closed-scholarships.yml` | Manual | Destructive purge operation | ✅ Requires exact confirmation string |
| `image-audit-check.yml` | Manual | Image mutation audit verification | ✅ Read-only; uses production DB |
| `closed-record-audit.yml` | Manual | Closed record classification | ✅ Read-only with SAFE_DELETE enforcement |
| `student-dashboard-migration.yml` | Manual | Schema migration apply/validate | ✅ Dry-run by default |
| `db-state-check.yml` | Manual | Database state queries | ⚠️ Runs arbitrary scripts |
| `controlled-image-repair.yml` | Manual | Forensic image repair | ⚠️ Mutates production data |
| `minimal-test.yml` | PR | Placeholder test | ❌ Redundant (duplicates test-workflow.yml) |
| `test-workflow.yml` | PR | Placeholder test | ❌ Redundant (duplicates minimal-test.yml) |

### 2.2 Issues Found

| Severity | Issue | Workflow | Fix |
|----------|-------|----------|-----|
| **P1** | Duplicate workflows (`minimal-test.yml`, `test-workflow.yml`) | Both | Remove one; keep `test-workflow.yml` |
| **P2** | Hardcoded branch names in `ci.yml` (lines 7, 8, 13, 14) | ci.yml | Use configurable branch patterns or remove specific fix branches |
| **P2** | PostgreSQL port conflicts possible (5433-5438 all on localhost) | ci.yml, production-purge-preflight.yml | Each job uses different port - OK if sequential; but matrix runs parallel |
| **P2** | `db-state-check.yml` accepts arbitrary script input | db-state-check.yml | Restrict to allowlist of scripts |
| **P3** | `controlled-image-repair.yml` mutates production | controlled-image-repair.yml | Add `environment: production` with approval gate |
| **P3** | No `permissions` block on `controlled-image-repair.yml` | controlled-image-repair.yml | Add minimal permissions |
| **P3** | `cancel-in-progress: false` on purge workflows | purge workflows | Consider `true` for non-production, keep `false` for production |

### 2.3 Cache Key Issues
- `ci.yml`: Uses `hashFiles('backend/requirements.txt')` - good
- `ci.yml`: Uses `hashFiles('frontend/package-lock.json')` - good
- `catalogue-snapshot.yml`: Uses pip cache + npm cache - good

### 2.4 Secrets Handling
- All production workflows use `${{ secrets.* }}` - ✅ Correct
- No secrets in logs or artifacts - ✅ Verified
- `production-purge-preflight.yml` has comprehensive secret validation - ✅

---

## 3. SECURITY AUDIT

### 3.1 Dependency Vulnerabilities

#### Frontend (npm audit) - 6 vulnerabilities
| Package | Severity | CVE/GHSA | Fix |
|---------|----------|----------|-----|
| `minimatch` (via eslint) | Moderate | GHSA-g3hv-75wg-m249 | `npm audit fix --force` (breaking: eslint 9.x) |
| `undici` | High | Multiple (GHSA-4qv8-2p9j-2685, etc.) | `npm audit fix` |
| `zod` (<4.6.6) | High | GHSA-mrhx-c7xc-m3w5 | `npm audit fix` (update to ≥4.6.6) |

#### Backend (pip-audit) - 206 vulnerabilities in 13 packages
**Critical/High:**
| Package | Current | Fixed In | Notes |
|---------|---------|----------|-------|
| `aiohttp` | 3.11.16 | 3.14.4 | Multiple CVEs (2026-111063, 111750, etc.) |
| `pillow` | 12.3.0 | 13.0.0 | Multiple CVEs (CVE-2026-112895, etc.) |
| `pyjwt` | 2.10.1 | 2.15.0 | Multiple CVEs |
| `requests` | 2.32.3 | 2.33.0 | PYSEC-2026-1872 |
| `urllib3` | 2.3.0 | 2.6.3+ | Multiple CVEs |
| `werkzeug` | 3.1.3 | 3.1.9 | Multiple CVEs |
| `flask` | 3.1.0 | 3.1.3 | PYSEC-2026-1377 |
| `pypdf` | 6.19.0 | 6.21.4 | Multiple CVEs |
| `certifi` | 2025.1.31 | 2026.10.18 | PYSEC-2026-4320 |
| `brotli` | 1.2.0 | 1.2.1 | PYSEC-2026-4322 |

**Action Required:** Update `backend/requirements.txt` with fixed versions.

### 3.2 Authentication & Authorization
- ✅ **Frontend:** `ProtectedRoute` redirects unauthenticated users; `AuthContext` manages session state
- ✅ **Backend:** Session-based auth with HttpOnly, SameSite=lax cookies; scrypt password hashing (N=2^14)
- ✅ **IDOR Prevention:** `dependencies.py` resolves user from session cookie only; no user-supplied IDs accepted
- ✅ **Timing Attack Resistance:** Dummy hash for non-existent accounts in `student_auth.py`

### 3.3 Input Validation
- ✅ **Pydantic models** for all API endpoints
- ✅ **SQLAlchemy ORM** used predominantly - prevents SQL injection
- ⚠️ **Raw SQL in migrations/scripts:** Several scripts use f-strings for DDL (table/column names) - these are constants, not user input, so low risk

### 3.4 XSS Risks
| Location | Risk | Mitigation |
|----------|------|------------|
| `UnifiedAIPage.jsx:91` | `dangerouslySetInnerHTML` with AI message content | Only replaces `\n` with `<br>`; content from trusted AI service |
| `config/purged_records_archive.json` | Contains `dangerouslySetInnerHTML` in archived HTML | Archived data only, not rendered |

**Recommendation:** Add DOMPurify or similar sanitization for `UnifiedAIPage.jsx` message content as defense-in-depth.

### 3.5 Secrets & Environment
- ✅ No hardcoded secrets in codebase
- ✅ Zero-paid guard scans for DB URLs, API keys in frontend
- ✅ GitHub secrets used in workflows
- ✅ `.gitignore` excludes `.env` files

### 3.6 Rate Limiting / Abuse Surface
- ❌ **No rate limiting** on public API endpoints (`/scholarships`, `/scholarships/stats`)
- ❌ **No API key requirement** for public endpoints
- ⚠️ **Search endpoint** accepts up to 100-char queries (validated but not rate-limited)

### 3.7 Error Information Disclosure
- ✅ `InvalidCredentialsError` deliberately carries no detail (prevents account enumeration)
- ✅ Production errors return generic messages
- ⚠️ Some backend logs may contain PII - verify log sanitization

### 3.8 Public API Exposure
- ✅ Public endpoints: `/scholarships`, `/scholarships/stats`, `/scholarships/{id}`, `/health`
- ✅ Private endpoints protected by `require_user` dependency
- ⚠️ `/api/` paths disallowed in robots.txt

---

## 4. SEO & PUBLIC DISCOVERABILITY AUDIT

### 4.1 Sitemap Generation (`build-sitemap.mjs`)
- ✅ Generated from public snapshot (single source of truth)
- ✅ **782 URLs** (2 static + 780 scholarship detail pages)
- ✅ Excludes: `/admin`, `/dashboard`, `/applications`, `/login`, `/register`, `/saved`, `/compare`, `/api/`, query parameters
- ✅ `lastmod` from `last_verified_at` (780 records without verifiable date)
- ✅ Canonical URLs from `CANONICAL_ORIGIN` (configurable via `VITE_CANONICAL_ORIGIN`)
- ✅ Validation in `catalogue-snapshot.yml` CI job

### 4.2 Robots.txt
- ✅ Allows: `/`, `/scholarships`, `/scholarships/{id}`, `/match`, `/mentor`
- ✅ Disallows: Private routes, `/api/`, query variants (`/*?*`)
- ✅ References sitemap at canonical origin

### 4.3 Structured Data (JSON-LD)
| Page | Types | Quality |
|------|-------|---------|
| Home (`index.html`) | `WebSite`, `SearchAction` | ✅ Complete |
| Scholarship Detail | `ScholarArticle`, `BreadcrumbList` | ✅ No fake ratings/reviews; uses real data |
| Other pages | Injected via `data-sz-seo` pattern | ✅ Dynamic per-route |

### 4.4 Meta Tags & Social
- ✅ **Open Graph:** `og:title`, `og:description`, `og:url`, `og:type`, `og:locale`, `og:image` (when available)
- ✅ **Twitter Cards:** `summary` / `summary_large_image` based on image availability
- ✅ **Canonical:** Dynamic per page, matches sitemap
- ✅ **Robots:** `index,follow` for public; `noindex,follow` for missing/error; `noindex,nofollow` for 404

### 4.5 Issues Found
| Severity | Issue | Fix |
|----------|-------|-----|
| **P2** | HomePage has no dynamic SEO update (uses static index.html tags) | Add `useEffect` in HomePage to update counts from stats API |
| **P3** | `og:image` missing on home page (no social preview asset) | Add default social image or accept missing |
| **P3** | 780 records have no `last_verified_at` for sitemap `lastmod` | Backfill verification dates or accept omission |

### 4.6 Canonical URL Consistency
- ✅ `CANONICAL_ORIGIN` single source: `https://scholarzone-fwzj.vercel.app`
- ✅ Used in sitemap, schema, canonical tags, Open Graph
- ⚠️ Legacy references to `gopal735.github.io/ScholarZone` in comments

---

## 5. ACCESSIBILITY AUDIT

### 5.1 Strengths
| Feature | Implementation |
|---------|----------------|
| **Semantic HTML** | `<article>`, `<section>`, `<header>`, `<nav>`, `<main>`, `<aside>` used correctly |
| **Keyboard Navigation** | Focus management in sheets, modals, tables; `tabIndex` handling |
| **Visible Focus** | `:focus-visible` styles across components (App.css, theme.css, component CSS) |
| **ARIA Labels** | `aria-label`, `aria-labelledby`, `aria-describedby` on interactive elements |
| **Live Regions** | `aria-live="polite"`, `role="status"` for async updates |
| **Progress Bars** | `role="progressbar"` with `aria-valuenow/min/max` |
| **Reduced Motion** | `@media (prefers-reduced-motion: reduce)` in 30+ CSS files; `useReducedMotion` hook |
| **Screen Reader Only** | `.sz-sr-only` utility class |
| **Heading Hierarchy** | H1→H2→H3 structure in detail pages |
| **Language Attributes** | `lang="en"`, `lang="bn"` for Bengali content |

### 5.2 Issues Found
| Severity | Issue | Location |
|----------|-------|----------|
| **P2** | `dangerouslySetInnerHTML` in `UnifiedAIPage.jsx` bypasses React's escaping | `UnifiedAIPage.jsx:91` |
| **P3** | Carousel in `FeaturedStory` uses `aria-roledescription="carousel"` (non-standard) | `FeaturedStory.jsx:74` |
| **P3** | Some icon-only buttons lack `aria-label` (rely on CSS `:focus-visible`) | Various |

### 5.3 WCAG 2.1 AA Compliance Assessment
| Criterion | Status |
|-----------|--------|
| 1.1.1 Non-text Content | ✅ Alt text on images; `aria-hidden` on decorative |
| 1.3.1 Info & Relationships | ✅ Semantic HTML, ARIA labels |
| 1.4.3 Contrast (Minimum) | ⚠️ Not verified programmatically |
| 2.1.1 Keyboard | ✅ Focus management, skip links |
| 2.1.2 No Keyboard Trap | ✅ Focus trap in sheets |
| 2.4.3 Focus Order | ✅ Logical DOM order |
| 2.4.7 Focus Visible | ✅ `:focus-visible` styles |
| 3.2.1 On Focus | ✅ No unexpected changes on focus |
| 4.1.2 Name, Role, Value | ✅ ARIA roles on custom components |

---

## 6. PRIORITIZED ACTION PLAN

### P0 - Critical (Do Immediately)
1. **Update vulnerable Python dependencies** - 206 vulnerabilities including aiohttp, pillow, pyjwt
2. **Update vulnerable Node dependencies** - zod (<4.6.6), undici, minimatch
3. **Add rate limiting** to public API endpoints

### P1 - High (This Sprint)
4. **Remove duplicate CI workflows** - Delete `minimal-test.yml`
5. **Fix hardcoded branch names** in `ci.yml` (lines 7, 8, 13, 14)
6. **Add DOMPurify sanitization** for `UnifiedAIPage.jsx` AI messages
7. **Restrict `db-state-check.yml`** script input to allowlist
8. **Add `environment: production`** to `controlled-image-repair.yml`

### P2 - Medium (Next Sprint)
9. **Add dynamic SEO to HomePage** - Update meta tags from stats API
10. **Backfill `last_verified_at`** for sitemap `lastmod` values
11. **Add default `og:image`** for social sharing
12. **Programmatic contrast verification** in CI

### P3 - Low (Backlog)
13. **Parametrize hardcoded test expectations** in backend tests
14. **Add regression test** for `data-sz-seo` cleanup
15. **Review `FeaturedStory` carousel ARIA** for standard compliance
16. **Clean up legacy GitHub Pages references** in codebase comments

---

## 7. REGRESSION TEST COVERAGE FOR DEFECTS

| Defect | Regression Test Needed |
|--------|------------------------|
| XSS via `dangerouslySetInnerHTML` | Test that malicious HTML in AI message is sanitized |
| Sitemap includes excluded paths | Test validates `EXCLUDED_PREFIXES` not in output |
| SEO tags not cleaned on route change | Test `data-sz-seo` removal on unmount |
| Rate limiting bypass | Test 429 response after N requests |
| Dependency vulnerability reintroduction | `npm audit` / `pip-audit` in CI (add as gate) |
| IDOR via user-supplied ID | Test that `require_user` ignores body/query user_id |
| Account enumeration via login timing | Test constant-time response for valid/invalid emails |

---

*Report generated by AGENT E — QA, CI, Security, and SEO Audit*