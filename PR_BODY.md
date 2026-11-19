## Summary

This PR implements the Italy Scholarship Expansion with three coordinated deliverables:

### 1. Italy Scholarship Research & Data (Strict Inclusion Rules)
- **Only 2 records added** after verifying 30+ CLOSED 2026/27 calls against official sources
- **Valle d'Aosta Regional DSU (VDA1 & VDA2)** — OPEN (deadline: 4 Dec 2026, 12:00 CET)
  - Official source: https://www.regione.vda.it/istruzione/dirittostudio/borse_universita_valdostane/default_i.aspx
  - Verified via Playwright browser automation
- **PoliTo PhD 42nd Cycle, 3rd Session** — UPCOMING (opens 14 Jan 2027, closes 15 Feb 2027, 14:00 CET)
  - Official source: https://www.polito.it/en/education/phd-programmes/admissions-to-phd-programmes/admissions/call-for-applications
  - Verified via Playwright browser automation
- All other Italian scholarships (MAECI, Invest Your Talent, regional DSU calls, university merit) classified CLOSED or unannounced — excluded from public catalogue. Record 135 (Politecnico di Milano merit) was corrected to CLOSED effective status because its 15 Dec 2025 deadline had passed; the historical record is preserved.

### 2. Complete DSU Knowledge System (`/scholarships/italy-dsu`)
- 13-section guide covering all 20 Italian regions
- Regional agency directory with 2026/27 status, ISEE limits, universities
- ISEE / ISEE Parificato / ISPE calculation for international students
- In sede / Pendolare / Fuori sede classification
- Benefits breakdown (cash, accommodation, meals, tuition, tax, mobility)
- Application process, ranking, payments, renewal, revocation
- DSU vs MAECI vs University Merit comparison
- Admission → DSU → Visa timeline
- International applicant checklist
- Critical warnings (regional differences, Trentino exclusion, eligible≠winner)
- 20 official agency URLs + national portals
- Navigation link from all Italy scholarship detail pages

### 3. Global Scholarship Card Typography Remediation
- 38 new typography tokens in `tokens.css` for consistent card rendering
- Complete migration of `ScholarshipCard.css` to token system
- Consistent Newsreader (display) / Inter (body) font families
- Consistent weights, line heights, tracking, colors across all variants:
  - Directory, search, filtered, featured, related, saved, compare, mobile
- No page-specific overrides; all through shared tokens

### Technical Quality
- All 43 backend tests pass
- All 571 frontend tests pass (including 19 new from merged PR #101)
- Production build successful
- Snapshot/API/ledger/sitemap parity verified (773 DB records, 772 public snapshot records, 774 sitemap URLs including static URLs)
- Historical records preserved (no deletions)
- No production database writes or deployments

## Testing
```bash
# Backend
cd backend && python -m pytest tests/test_scholarships.py tests/test_scholarship_integration.py tests/test_production_seeding.py -v
# 43 passed

# Frontend
cd frontend && npm test
# 38 test files, 571 tests passed

# Build
cd frontend && npm run build
# ✓ built in 341ms
```

## Files Changed (Italy Implementation)
- `backend/scripts/insert_italy_strict.py` — Idempotent insertion script
- `backend/research_output/italy_strict_candidates.json` — 2 verified records
- `frontend/src/App.jsx` — DSU guide route
- `frontend/src/pages/ItalyDsuGuidePage.jsx/.css` — 13-section DSU guide
- `frontend/src/pages/ScholarshipDetailsPage.jsx/.css` — Italy DSU guide link
- `frontend/src/components/ScholarshipCard.css` — Token migration
- `frontend/src/styles/tokens.css` — 38 typography tokens
- `frontend/src/seoContract.test.js` — Sitemap parity test
- `frontend/public/scholarships-snapshot.json` — Regenerated (2 records)
- `frontend/public/sitemap.xml` — Regenerated (4 URLs)

## Merge Note
This branch includes a normal merge of `origin/master@6a9f38c0` (PR #101) to stay synchronized with the latest master. The merge brings AuthContext and UnifiedAIPage improvements from PR #101.

## Review Checklist
- [ ] Only OPEN/UPCOMING records added (strict inclusion rules)
- [ ] Official source URLs verified for both records
- [ ] CLOSED records excluded from public APIs, snapshot, sitemap
- [ ] DSU guide content accurate and region-specific
- [ ] Typography tokens applied consistently across all card variants
- [ ] All tests pass
- [ ] No production database writes
- [ ] Historical records preserved