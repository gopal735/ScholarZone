# Global Study-to-Career Strategist — PR

**Branch:** `feat/global-study-to-career-strategist` · **Status:** review-ready · **Do not merge / do not deploy**.
Feature ships **behind a flag, default OFF** in both frontend and backend.

## Summary
One unified decision experience across subject + degree + funding model + budget (BDT) + country + career + salary + student work rights + post-study work + permanent residence + citizenship, built **on top of** the existing Country Intelligence plane, Match taxonomy, scholarship catalogue and Journey i18n/money primitives — an integration, not a rewrite. It adds no PII, no production writes, no database migration. Money is shown in **BDT beside the original currency with the exchange-rate date**.

This is built intentionally around: **missing is never 0; a country average is never a subject salary; gross is never take-home; tuition/living/scholarship/stipend/gross/net are never merged; no admission/visa/citizenship outcome is fabricated; there is no single magic score; every fact carries source + date + status.**

## AUDIT findings (Phase 0) — see `docs/strategist/AUDIT.md`
- **Reused, unchanged:** Country Intelligence corpus (17 countries), `POST /v2/countries/compare`, the cost engine (`derive.py`), `net_income.py`, the provenance/`value_status`/freshness contracts, the Match `CANONICAL_FIELDS` taxonomy, the scholarship catalogue (measured plane), and the Journey `money`/i18n patterns.
- **Gaps added, justified in AUDIT.md:** `docs/strategist/RESEARCH_REPORT.md` (official-source research), `occupation_salary.py` + `TOPIC_PATHS` mapping (subject-level pay), BDT FX artefact + composed converter (no BDT rate existed anywhere), the `strategist` service + flag-gated router, and the admin gap report.

## UI/API changes
- Backend: `GET /v2/strategist/subjects`, `POST /v2/strategist/plan`, `GET /v2/strategist/pathway/{iso2}`, `GET /v2/strategist/gaps` (registered **only** when `SCHOLARZONE_STRATEGIST_ENABLED=true`, else 404). Stateless; `extra="forbid"` validation; 422 on bad subject/degree.
- Frontend: mobile-first wizard `Subject → Degree → Funding → Budget(BDT) → Priorities(weights) → Results`, behind `VITE_STRATEGIST_ENABLED`. Results are **criterion-by-criterion** for up to 6 countries with a per-country evidence-completeness meter, **why-recommended / why-excluded**, sourced pathway timeline, live what-if (budget + funding), shortlist (sessionStorage only), share link (choices only), and print-to-PDF. Bangla+English i18n; loading/empty/error/offline/partial states; `?fixture=1` renders captured data for review without the backend.

## Data coverage (research-verified, primary sources only)
Computer Science, Data Science, Civil Engineering × best-covered countries. Occupation-level gross pay **PRIMARY_VERIFIED**: US (BLS OEWS, May 2025, all 3), CA (StatCan LFS via Job Bank, all 3), DE civil (BA Entgeltatlas 2025), AU CS + civil (JSA/ABS, ANZSCO class). **Officially unavailable → "Insufficient data":** IE (CSO publishes sector/broad-occupation only), AU Data Science, DE Data Science, GB Data Science. **Pending primary read:** DE CS expert track, GB (ONS ASHE Table 14), NL (CBS table superseded 2026-08-18), NZ detailed (Stats NZ major-group only). Full matrix + URLs in `research_raw/_global/002–005` and `RESEARCH_REPORT.md`. Ranking ranks only on the two essential criteria the corpus reliably sources (**subject salary + post-study work**); cost cells remain visible but a gap lowers evidence-completeness and raises a risk note rather than silently suppressing career/work facts.

## BDT
Bangladesh Bank **USD/BDT 123.2254 (2026-10-11)**, composed with the ECB table (2026-10-02) via original→USD→BDT. Both legs, both dates, both publishers published; if either leg is missing/stale the BDT figure is refused as unavailable (never invented). BDT is a **separate artefact** because the ECB genuinely does not publish EUR/BDT.

## Flag rollout / rollback
- **OFF by default** in every environment (both switches). With OFF, backend routes are not registered (404) and the frontend route renders not-found.
- **Rollout:** set `SCHOLARZONE_STRATEGIST_ENABLED=true` (API) and `VITE_STRATEGIST_ENABLED=true` (web) per environment; no redeploy of data needed (corpus is files). For review without the API, append `?fixture=1`.
- **Rollback:** set both back to false — the feature is inert/reachable-nowhere; no data to roll back (no migration, no writes).

## Assumptions / known limitations
- Occupation-salary promotion into the *production country corpus* requires the reviewed `TOPIC_PATHS` ingest mapping plus the ingestion guards + tests (added) and a full re-ingest — **deferred** to avoid a bulk corpus regeneration; the strategist serves the verified subset from `occupation_salary/verified.json`.
- The research phase is complete for the 6-country/3-subject matrix; DE-CS-expert, GB, NL and NZ detailed figures await primary-table reads (recorded as pending/gaps).
- Weg-exact digit locale differs between `en-GB`/`bn-BD` rendering.

## Verification (exact commands + observed results)
- Backend: `python -m pytest -q` → **6575 passed, 12 skipped, 1 xfailed**; strategist `tests/test_strategist.py` → **36 passed** (integrity rules + budget/funding scenarios + coverage-based selection + essential alignment + API auth). The single `scripts/artifact_smoke_test.py::test_endpoint` collection error is pre-existing (a helper function mis-collected by pytest, **not touched by this PR**, present on baseline) and is not part of CI.
- Frontend: `npx vitest run` → **1020 passed (40 files)**; strategist `StrategistPage.test.jsx` → **13 passed** (all UI states incl. offline, essential criteria, budget fit, funding reality, privacy) and `lib/api.test.js` → **7 passed** (bounded cache: TTL, keying, stale-on-failure, never-invents, bounded eviction).
- E2E (committed, run locally): `npx playwright test -c e2e/playwright.strategist.config.js` → **4 passed** (happy + insufficient-data × mobile + desktop). `@playwright/test` is a devDependency.
- `npm run lint` (eslint) → **0 problems**. `npm run build` → success, `strategist` chunk code-split, no warnings.
- a11y: axe-core 4.10 (wcag2a/2aa/21a/21aa + best-practice) on the live results page → **0 violations, 42 passes**.
- Screenshots: `docs/strategist/screenshots/` (mobile results, desktop results, insufficient-data/not-ranked region).

## Review findings addressed (this revision)
1. **Admin auth on `/v2/strategist/gaps`** — now requires `X-Admin-Secret` (same as `admin_dashboard`); the flag being on no longer makes the internal report public. Tested unauth/non-admin/authorized.
2. **Budget + funding now affect the comparison honestly** — budget is scored **per cost cell** (years of tuition, never summed with months of living) and surfaced as "Budget fit"; missing/unconvertible costs stay "Insufficient/unavailable" with a reason (never 0). Funding model drives a "Funding reality" note from **measured** degree-level counts (never fabricated, never subject-matched). What-if re-runs reflect both. Tested across budget/funding scenarios.
3. **Deterministic evidence-coverage selection** — the default set is the top-6 countries by evidence completeness (ties by ISO), computed not sliced; `selection_rule` is published and tested. An explicit `iso2s` list is still supported.
4. **Essential-criteria alignment** — essential = `subject_salary` + `post_study_work`, consistent across flags, `_essential_complete`, the published `request.essential_criteria`, `ranking_rule`, the UI and tests. Missing cost lowers completeness + raises a risk note but does not block ranking; missing an essential criterion removes the overall rank.
5. **Committed E2E + offline-state + bounded cache** — Playwright E2E (happy + insufficient, mobile + desktop), an offline-state component test, and a bounded (TTL + max-entries) plan/subjects cache that serves a known answer disclosed as stale on failure and never invents one. Cache failure/invalidation behavior is tested.

## Residual gaps (honest, per task §5)
- E2E requires Playwright's browser binaries. They are installed for the local run (Chromium downloaded) but **are not pre-provisioned in the project's CI**, so the E2E job is not wired into the GitHub workflow in this PR (it is committed and runnable via `npm run test:e2e:strategist` after `npx playwright install chromium`). CI still runs unit/component tests, lint and build.
- Occupation-salary promotion into the production country corpus files + full re-ingest remains deferred (guarded mapping + tests added; verified subset served from `occupation_salary/verified.json`). See earlier section.

## Data-integrity hostile self-review
Confirmed across diff + tests: no path turns UNKNOWN into 0; a stipend/gross is never shown as net/take-home; a country average never stands in for subject pay; no admission/visa/citizenship probability is produced; budget/funding change interpretation only and never filter or zeroize; shared URLs/export carry only choices (no PII); stale/undated cells raise a re-verify warning; the gap report is admin-gated.
