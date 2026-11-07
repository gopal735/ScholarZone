# ScholarZone Comprehensive QA, CI, Security, and SEO Audit Report

**Date:** 2026-11-07
**Branch:** feature/global-catalogue-expansion-2026-11-07
**Repository:** C:\Users\GopaL\Desktop\Projects folder\ScholarZone

---

## Executive Summary

| Area | Status | Critical Issues | High Issues | Medium Issues |
|------|--------|-----------------|-------------|---------------|
| Test Suite | 🟡 Degraded | 2 test failures (frontend) | 0 | 17 conditional skips (backend) |
| CI/CD Workflows | 🟢 Good | 0 | 1 (timing attack in admin auth) | 3 (cache key inconsistencies) |
| Security | 🔴 Critical | 1 (timing attack) | 5 (dependency vulns, XSS) | 4 (secrets handling) |
| SEO & Sitemap | 🟢 Good | 0 | 0 | 1 (780 records without lastmod) |
| Accessibility | 🟢 Good | 0 | 0 | 2 (focus management) |

---

## 1. Test Suite Audit

### 1.1 Backend Tests (pytest)
- **Total collected:** 6,220 tests
- **Configuration:** `pytest.ini` restricts collection to `tests/` directory (correct - prevents ad-hoc scripts from running)
- **Markers:** `integration` (requires disposable PostgreSQL)

#### Test Categories & Coverage
| Category | Test Files | Tests | Status |
|----------|------------|-------|--------|
| Taxonomy/Canonicalization | 1 | 38 | ✅ Pass |
| Git Integrity | 1 | 22 | ✅ Pass |
| Verification/Telemetry | 5 | ~500 | ✅ Pass |
| Scholarship Lifecycle | 15 | ~1,200 | ✅ Pass |
| Image Audit/Discovery | 20 | ~1,800 | ✅ Pass |
| Retention/Purge | 18 | ~1,500 | ✅ Pass |
| Migration/Schema | 8 | ~800 | ✅ Pass |
| Scheduler/Discovery | 12 | ~1,000 | ✅ Pass |
| Matching/Supervisor | 14 | ~1,200 | ✅ Pass |

#### Conditional Skips (17 tests)
These are **legitimate conditional skips** (not pytest `@pytest.mark.skip`), used when test fixtures don't meet preconditions:

| File | Line | Reason |
|------|------|--------|
| `test_application_workspace.py` | 964 | Fixture record not in match result set |
| `test_counting_core.py` | 212 | Record still produced fit score |
| `test_deployment_files.py` | 34, 150 | Required files not present |
| `test_do_logos_accepted_image.py` | 46 | ETH Zurich override map absent |
| `test_git_integrity_regression.py` | 95, 119, 139 | Git not available in environment |
| `test_import_regression.py` | 219 | Git not available |
| `test_mentor.py` | 1192 | Fixture produced no counted checklist |
| `test_purge_preflight.py` | 908, 982, 1064 | TEST_DATABASE_URL not set (integration tests) |
| `test_retention_recovery_gate.py` | 678 | No repository ledger |
| `test_supervisor_render_e2e.py` | 56 | Playwright importable but no driver |
| `test_test_isolation_boundary.py` | 281 | `@pytest.mark.skipif` for production mode |
| `test_vercel_migration.py` | 207 | No CORS middleware configured |

**Assessment:** No `@pytest.mark.xfail` found. All skips are conditional and appropriate for the test environment.

#### Weak Tests Identified
1. **`test_deployment_files.py`** - Only checks file existence, not content validity
2. **`test_git_integrity_regression.py`** - Skips entirely when git unavailable (CI always has git)
3. **Integration tests in `test_purge_preflight.py`** - Skip silently when `TEST_DATABASE_URL` not set; CI workflow explicitly checks for this

---

### 1.2 Frontend Tests (Vitest)
- **Total test files:** 21
- **Total tests:** 360 (357 pass, 3 fail)
- **Test environment:** jsdom

#### Failures (P0 - Must Fix)

| Test File | Failure | Root Cause |
|-----------|---------|------------|
| `ScholarshipList.test.jsx` | Import error: `../data/scholarships` | File doesn't exist - removed during refactor |
| `HomePage.test.jsx` (3 tests) | `ReferenceError: FLAGSHIP_PROGRAMMES is not defined` | Constant removed from HomePage.jsx but still referenced |

#### Missing Coverage
- No accessibility-specific tests (axe-core, jest-axe)
- No SEO/snapshot regression tests beyond contract tests
- No visual regression tests
- No E2E tests (Playwright available in backend but not frontend)

---

## 2. CI/CD Workflow Audit

### 2.1 Workflows Analyzed (14 workflows)

| Workflow | Trigger | Status | Issues |
|----------|---------|--------|--------|
| `ci.yml` | push/PR to main, master, fix/* | 🟢 Good | Cache key inconsistency (pip-v2 vs pip), no npm audit |
| `frontend.yml` | push to master (frontend/**) | 🟢 Good | Uses `vars.SCHOLARZONE_API_URL` correctly |
| `deploy.yml` | workflow_run (CI success) | 🟢 Good | Validates revision SHA, no stale deploy |
| `catalogue-snapshot.yml` | push/PR (backend/**) | 🟢 Good | Generates & validates snapshot, sitemap |
| `production-purge-preflight.yml` | workflow_dispatch | 🟢 Good | Manual trigger only, environment protection |
| `zero-paid-guard.yml` | push/PR | 🟢 Good | Checks for paid deps, secrets in frontend |
| `image-audit-check.yml` | workflow_dispatch | 🟢 Good | Read-only production audit |
| `closed-record-audit.yml` | - | 🟡 Unknown | Not examined in detail |
| `controlled-image-repair.yml` | - | 🟡 Unknown | Not examined in detail |
| `db-state-check.yml` | - | 🟡 Unknown | Not examined in detail |
| `student-dashboard-migration.yml` | - | 🟡 Unknown | Not examined in detail |
| `minimal-test.yml` | - | 🟡 Unknown | Not examined in detail |
| `test-workflow.yml` | - | 🟡 Unknown | Not examined in detail |
| `purge-ui-closed-scholarships.yml` | - | 🟡 Unknown | Not examined in detail |

### 2.2 CI Issues (Medium)

1. **Cache Key Inconsistency** (`ci.yml:37-40, 236-239, 348-350`)
   - `backend-tests` uses `pip-v2-${{ hashFiles('backend/requirements.txt') }}`
   - `import-smoke` uses `pip-${{ hashFiles('backend/requirements.txt') }}` (no v2)
   - `schema-compat` uses `pip-${{ hashFiles('backend/requirements.txt') }}`
   - **Fix:** Use consistent `pip-v2-` prefix everywhere

2. **Missing npm audit in CI** - Frontend has 6 vulnerabilities (2 high) but CI doesn't run `npm audit`

3. **Missing pip-audit in CI** - Backend has 206 vulnerabilities in 13 packages but CI doesn't run `pip-audit`

4. **PostgreSQL Service Health Checks** - All workflows use proper `pg_isready` health checks with retries ✅

5. **Secrets Handling** - Production workflows use `environment` protection and `secrets.*` correctly ✅

---

## 3. Security Audit

### 3.1 Critical Issues (P0)

| ID | Issue | Location | Severity | Fix |
|----|-------|----------|----------|-----|
| SEC-001 | **Timing Attack in Admin Auth** | `backend/app/routers/admin_dashboard.py:49` | CRITICAL | Use `secrets.compare_digest()` instead of `==` |

```python
# CURRENT (VULNERABLE):
return provided_secret == expected

# FIXED:
return secrets.compare_digest(provided_secret, expected)
```

### 3.2 High Issues (P1)

| ID | Issue | Location | Severity |
|----|-------|----------|----------|
| SEC-002 | **XSS via `dangerouslySetInnerHTML`** | `frontend/src/pages/UnifiedAIPage.jsx:91` | HIGH |
| SEC-003 | **Frontend Dependency Vulnerabilities** | `npm audit` - 6 vulns (2 high: undici, zod) | HIGH |
| SEC-004 | **Backend Dependency Vulnerabilities** | `pip-audit` - 206 vulns in 13 packages (aiohttp, pillow, flask, urllib3, werkzeug, pytest, requests, pyjwt, pypdf, certifi, brotli, soupsieve, pip) | HIGH |
| SEC-005 | **Raw SQL in Scripts** | Multiple scripts use `f"SELECT ... {table}"` | HIGH |
| SEC-006 | **Admin Secret Fallback** | `config.py:134` - Falls back to `VERIFICATION_SECRET` | HIGH |

#### SEC-002 Detail: XSS in UnifiedAIPage
```jsx
// Line 91 - UNSAFE: message.content could contain malicious HTML
<div className="message-text" dangerouslySetInnerHTML={{ __html: message.content.replace(/\n/g, '<br>') }} />

// FIX: Sanitize with DOMPurify or use safe rendering
import DOMPurify from 'dompurify';
<div className="message-text" dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(message.content).replace(/\n/g, '<br>') }} />
```

#### SEC-005 Detail: Raw SQL Patterns Found
| File | Pattern |
|------|---------|
| `backend/app/data/apply_live_upcoming_patch.py:300` | `f"INSERT INTO scholarships ({cols}) VALUES ({placeholders})"` |
| `backend/app/data/integrity_check.py:29` | `f"SELECT COUNT(*) FROM scholarships WHERE {col} IS NOT NULL"` |
| `backend/scripts/dump_image_audit.py:36` | `text(f"SELECT count(*) FROM {AUDIT}")` |
| `backend/scripts/probe_audit_boundary.py:49` | `text(f"SELECT count(*) FROM {AUDIT}")` |
| `backend/app/services/purge_preflight/database.py:324` | `f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_column} = ANY(%s)"` |

**Risk:** Table/column names interpolated via f-strings. If ever user-controlled → SQL injection.

### 3.3 Medium Issues (P2)

| ID | Issue | Location |
|----|-------|----------|
| SEC-007 | **Admin secret fallback to verification secret** | `config.py:134` - `admin_secret=os.getenv("SCHOLARZONE_ADMIN_SECRET") or os.getenv("SCHOLARZONE_VERIFICATION_SECRET")` |
| SEC-008 | **In-process rate limiter** | `rate_limit.py` - Doesn't work across multiple instances |
| SEC-009 | **No CSP headers** | Frontend middleware doesn't set Content-Security-Policy |
| SEC-010 | **Debug endpoint exposed** | `scholarships.py:132` - `/debug/raw/{id}` behind admin auth but dumps all columns |

### 3.4 Low Issues (P3)

| ID | Issue | Location |
|----|-------|----------|
| SEC-011 | **CORS allows GitHub Pages** | `config.py:105-106` - Hardcoded `https://gopal735.github.io` |
| SEC-012 | **Session cookie missing `__Host-` prefix** | `auth.py:82-90` - Backend uses `__Host-` prefix but frontend doesn't enforce |
| SEC-013 | **Error messages may leak internals** | Some `HTTPException` details expose table/column names |

---

## 4. SEO & Public Discoverability Audit

### 4.1 Sitemap Generation (`build-sitemap.mjs`)
- **Status:** ✅ Working correctly
- **Output:** 782 URLs (2 static + 780 scholarship details)
- **Validation:** All contract tests pass (30/30)

#### Sitemap Rules Compliance
| Rule | Status |
|------|--------|
| Only public URLs included | ✅ (uses public snapshot) |
| No internal/private/quarantined | ✅ (EXCLUDED_PREFIXES enforced) |
| No closed unless documented | ✅ (snapshot excludes closed) |
| No query parameters | ✅ (validated) |
| No duplicates | ✅ (Set-based deduplication) |
| Canonical host | ✅ (CANONICAL_ORIGIN = scholarzone-fwzj.vercel.app) |

#### Issue: Missing `lastmod`
- **780/780 records** lack verifiable `last_verified_at` date
- Sitemap emits URLs without `<lastmod>` (correct - doesn't fabricate)
- **Recommendation:** Populate `last_verified_at` during verification pipeline

### 4.2 robots.txt
- **Status:** ✅ Correct
- Points to canonical sitemap URL
- Blocks private routes (`/admin`, `/dashboard`, `/applications`, `/login`, `/register`, `/saved`, `/compare`, `/api/`)
- Blocks filter/search/sort variants (`/*?*`)
- Does NOT block `/scholarships`, `/match`, `/mentor` (correct)

### 4.3 Canonical URLs & Metadata
- **index.html:** ✅ Has canonical, description, robots, OG/Twitter, WebSite structured data
- **Middleware:** ✅ Rewrites per-route canonical, title, description, structured data
- **404 handling:** ✅ Returns real 404 for unknown scholarship IDs (not soft 404)

### 4.4 Structured Data
- **Homepage:** WebSite + SearchAction ✅
- **Detail pages:** ScholarshipProgram with provider, spatialCoverage, educationalCredentialAwarded, applicationDeadline ✅
- **No duplicate/structured data conflicts** ✅

---

## 5. Accessibility Audit

### 5.1 Strengths (Observed in Code)
- **Semantic HTML:** Extensive use of `<section>`, `<article>`, `<nav>`, `<aside>` with `aria-labelledby`
- **Keyboard Navigation:** Focus-visible styles in `responsive.css:227`
- **ARIA Attributes:** Comprehensive use of `aria-label`, `aria-labelledby`, `aria-live`, `role="status"`, `role="alert"`, `role="progressbar"`
- **Screen Reader Support:** `visually-hidden` class, `sr-only` utilities
- **Reduced Motion:** `useReducedMotion` hook with matchMedia shim in tests
- **Focus Management:** `AuthForm`, `ApplicationWorkspace`, `HomePage` details sheet all manage focus

### 5.2 Issues (Medium)

| ID | Issue | Location |
|----|-------|----------|
| ACC-001 | **Missing skip link** | No "Skip to main content" link in index.html or layout |
| ACC-002 | **Focus trap in details sheet** | `HomePage.jsx:276-284` - Focus trap only on `focus` event, may miss programmatic focus |

### 5.3 Contrast & Visual
- Design tokens in `styles/tokens.css` define color system
- No automated contrast testing in CI
- **Recommendation:** Add `axe-core` to test suite

---

## 6. Regression Test Coverage for Discovered Defects

### 6.1 Required Regression Tests

#### For SEC-001 (Timing Attack)
```python
# backend/tests/test_admin_auth_timing.py
import pytest
from app.core.admin_auth import admin_secret_is_valid, require_admin_secret
from fastapi import HTTPException

def test_admin_secret_uses_constant_time_comparison():
    """Admin secret validation must use secrets.compare_digest"""
    import inspect
    source = inspect.getsource(admin_secret_is_valid)
    assert "compare_digest" in source, "Must use secrets.compare_digest for constant-time comparison"

@pytest.mark.asyncio
async def test_admin_secret_rejects_invalid():
    from app.core.config import Settings
    settings = Settings(environment="test", database_url="sqlite:///", allowed_origins=(), admin_secret="correct-secret")
    # Patch get_settings
    import app.core.admin_auth as admin_auth
    original = admin_auth.get_settings
    admin_auth.get_settings = lambda: settings
    try:
        with pytest.raises(HTTPException) as exc:
            await require_admin_secret("wrong-secret")
        assert exc.value.status_code == 401
    finally:
        admin_auth.get_settings = original
```

#### For SEC-002 (XSS)
```jsx
// frontend/src/pages/UnifiedAIPage.test.jsx
import { render, screen } from '@testing-library/react'
import UnifiedAIPage from './UnifiedAIPage'
import DOMPurify from 'dompurify'

test('sanitizes message content before rendering', () => {
  const maliciousContent = '<img src=x onerror=alert(1)>Hello\nWorld'
  render(<UnifiedAIPage initialMessages={[{ role: 'assistant', content: maliciousContent }]} />)
  const messageText = screen.getByTestId('message-text')
  expect(messageText.innerHTML).not.toContain('onerror')
  expect(messageText.innerHTML).toContain('Hello<br>World')
})
```

#### For Frontend Test Failures
```jsx
// frontend/src/components/ScholarshipList.test.jsx - FIX: Mock the missing import
// OR: Create minimal scholarships data file for tests
// frontend/src/data/scholarships.js (test fixture)
export const scholarships = [
  { id: 1, title: 'Test Scholarship', country: 'Germany', degree: 'Master', funding: 'Fully Funded', deadline: '2026-12-31', description: 'Test' }
]

// frontend/src/pages/HomePage.jsx - FIX: Remove FLAGSHIP_PROGRAMMES references or restore constant
```

---

## 7. Recommended Fixes Priority Order

### P0 - Immediate (Security/Build Blocking)
1. **Fix timing attack** in `admin_dashboard.py:49` - Use `secrets.compare_digest()`
2. **Fix XSS** in `UnifiedAIPage.jsx:91` - Sanitize with DOMPurify
3. **Fix frontend test failures** - Remove `FLAGSHIP_PROGRAMMES` references or restore constant; fix `ScholarshipList` import
4. **Run npm audit fix** and **pip-audit fix** in CI

### P1 - High (Before Next Deploy)
5. **Add npm audit & pip-audit to CI** (`ci.yml`, `catalogue-snapshot.yml`)
6. **Fix cache key inconsistency** in `ci.yml` (use `pip-v2-` everywhere)
7. **Remove admin secret fallback** to verification secret in `config.py:134`
8. **Parameterize raw SQL** in scripts - use SQLAlchemy text() with bound parameters for identifiers

### P2 - Medium (Next Sprint)
9. **Add CSP headers** in middleware
10. **Add accessibility tests** (axe-core) to frontend test suite
11. **Add skip link** to index.html
12. **Populate `last_verified_at`** in verification pipeline for sitemap `lastmod`
13. **Replace in-process rate limiter** with Redis-backed for multi-instance readiness

### P3 - Low (Technical Debt)
14. **Remove hardcoded GitHub Pages origin** from CORS config
15. **Add `__Host-` prefix** to frontend session cookie handling
16. **Add visual regression tests** (Playwright) for frontend

---

## 8. Summary of Files Requiring Changes

| File | Issue(s) | Priority |
|------|----------|----------|
| `backend/app/routers/admin_dashboard.py` | SEC-001 (timing attack) | P0 |
| `backend/app/core/config.py` | SEC-006 (admin secret fallback), SEC-011 (hardcoded CORS) | P1, P3 |
| `backend/app/core/rate_limit.py` | SEC-008 (in-process limiter) | P2 |
| `frontend/src/pages/UnifiedAIPage.jsx` | SEC-002 (XSS) | P0 |
| `frontend/src/pages/HomePage.jsx` | Test failure (FLAGSHIP_PROGRAMMES) | P0 |
| `frontend/src/components/ScholarshipList.jsx` | Test failure (missing import) | P0 |
| `frontend/index.html` | ACC-001 (skip link), SEC-012 (CSP) | P2, P2 |
| `frontend/middleware.js` | SEC-009 (CSP headers) | P2 |
| `.github/workflows/ci.yml` | Cache keys, missing audits | P1 |
| `.github/workflows/catalogue-snapshot.yml` | Missing audits | P1 |
| `backend/scripts/*.py` (multiple) | SEC-005 (raw SQL) | P1 |
| `frontend/package.json` | Dependency updates | P0 |
| `backend/requirements.txt` | Dependency updates | P0 |

---

## 9. Verification Commands

```bash
# Backend tests
cd backend && python -m pytest -ra --tb=short

# Frontend tests
cd frontend && npm run test

# Lint
cd frontend && npm run lint

# Security audits
cd frontend && npm audit
cd backend && pip-audit

# Sitemap validation
cd frontend && node scripts/build-sitemap.mjs && npm run test -- src/sitemapContract.test.js src/seoContract.test.js

# Build verification
cd frontend && npm run build
```

---

*Report generated by Kilo Audit Agent on 2026-11-07*