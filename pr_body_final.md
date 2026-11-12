## Summary

**Historical Import (afda63a9):** 9 records inserted, DB IDs 1378–1386  
**Valid USA-hosted inserted:** 8 records (IDs 1378, 1379, 1380, 1382–1386)  
**Invalid historical insertion:** 1 record (ID 1381 — McDonald Fellowships 2027, no 2027 round, Europe-only hosts, not USA-hosted)  
**Skipped duplicates:** 2 (AAUW ID 473, JJ/WBGSP ID 475)  
**Current import-ready array:** 8 valid USA-hosted records  
**ID 1381 correction:** Pending explicit approval and backup/PITR verification — **no production DML executed**

---

### Reconciled Accounting

| Metric | Value |
|--------|-------|
| Historical inserts (afda63a9) | 9 (IDs 1378–1386) |
| Valid USA-hosted inserted | 8 |
| Invalid imported (ID 1381) | 1 (McDonald) |
| Skipped duplicates | 2 (AAUW ID 473, JJ/WBGSP ID 475) |
| Current import-ready records | 8 |
| USA-scope monitoring (2028-29) | 7 |

### Database Accounting (read-only verified)

| Metric | Value |
|--------|-------|
| Pre-import USA total | 55 |
| Pre-import valid USA-hosted | 54 (55 total - 1 invalid: ID 394 Tilburg University Waiver, Dutch university misclassified as USA) |
| Post-import USA total | 64 |
| Post-import valid USA-hosted | 62 |
| Historical inserts | 9 (IDs 1378–1386) |
| Valid USA-hosted inserted | 8 |
| Invalid imported | 1 (ID 1381 McDonald) |
| Delta valid (vs pre-import total 55) | +7 (62 - 55) |
| Net valid increase (vs pre-import valid 54) | +8 (62 - 54) |

**Arithmetic:** Pre-import valid = 54 (55 - 1 invalid: ID 394 Tilburg University Waiver). Valid inserted = 8. Invalid inserted = 1 (ID 1381). Post-import valid = 54 + 8 = 62. Delta valid (vs pre-import total 55) = 62 - 55 = 7. Net valid increase = 62 - 54 = 8.

### Corrections Applied
- **McDonald Fellowship (ID 1381):** Identified as invalid post-import — no 2027 round, Europe-only hosts, not USA-hosted. Controlled correction pending explicit approval + backup/PITR verification. **No UPDATE/DELETE executed.**
- **Harvard LEAD:** Eligibility corrected to "all gender identities welcome" (was "women only")
- **AAUW:** Status CLOSED (deadline Sept 17, 2026 passed). Already in DB as ID 473. fully_funded=null.
- **JJ/WBGSP:** Reclassified as multi-country (US, Europe, Africa, Oceania, Japan). Duplicate of DB ID 475.
- **Emory:** Dual deadlines preserved (ED I Nov 1, ED II/Reg Nov 15)
- **Tulane:** Status PARTIALLY_CLOSED (ED I Nov 1 & EA Nov 10 passed; Reg Dec Jan 15 open)
- **AAUW funding:** fully_funded=null (fixed grant $20–25k, tuition_coverage=false, travel_coverage=false)

### Deliverables
- `US_SCHOLARSHIP_DISCOVERY_REPORT.md` — full methodology & reconciled accounting
- `us_scholarship_candidates.json` — 11 candidates, 8 import-eligible
- `us_scholarships_import_ready.json` — 8 import-ready records
- `us_scholarship_existing_exclusions.csv` — 30 codebase + 2 DB duplicates
- `us_scholarship_source_register.csv` — 18 verified sources with correct DB IDs
- `us_scholarship_department_coverage.csv` — department/field analysis
- `us_scholarship_import_report.json` — historical_inserted=9, valid=8, invalid=1
- `research_batch_manifest.json` — audit trail with distinct historical/audit facts

### Quality Gates — All PASSED
- ✅ Backend: 6,216 passed, 15 skipped (exact-head CI Run #731)
- ✅ Frontend: 507 passed (exact-head CI Run #731)
- ✅ Frontend lint: 1 warning (pre-existing)
- ✅ Frontend build: SUCCESS (773 URLs in sitemap)
- ✅ No duplicate insertion
- ✅ No existing row updates
- ✅ Department/field/provenance persistence verified
- ✅ Funding tri-state correctness verified
- ✅ Restricted nationality eligibility preserved
- ✅ Transaction rollback safety verified

### Production Database State (read-only verified)
- Pre-import USA total: 55
- Pre-import valid USA-hosted: 54 (55 - 1 invalid: ID 394 Tilburg University Waiver)
- Post-import USA total: 64 (includes invalid ID 1381)
- Post-import valid USA-hosted: 62 (excluding ID 1381 and pre-import ID 394)
- No existing rows modified by this import

**Exact-Head CI:** Run #731 — https://github.com/gopal735/ScholarZone/actions/runs/43216189088  
**PR #92 remains OPEN and UNMERGED. No production DML executed for correction.**