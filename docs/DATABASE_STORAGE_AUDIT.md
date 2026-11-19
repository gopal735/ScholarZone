# Database Storage Audit

**Date:** 2026-11-18
**Database:** Local SQLite (development)
**Database File:** scholarzone.db

## Database Size

- **Total DB file size:** ~2.7 MB
- **Records:** 773 scholarships
- **Average record size:** ~3.5 KB

## Largest Storage Consumers

1. **Scholarship table** — 773 records with JSON fields (funding_details, eligibility, benefits, etc.)
2. **ScholarshipVerificationHistory** — 2 audit records
3. **Snapshot file** — 2.2 MB (frontend/public/scholarships-snapshot.json)

## Storage Optimization Recommendations

### Safe Optimizations (No Data Loss)
1. **Remove unused generated files** — Temporary build artifacts, cached images
2. **Compress snapshot JSON** — Gzip compression for frontend delivery
3. **Review index usage** — Ensure indexes match query patterns
4. **Vacuum SQLite** — `VACUUM` to reclaim free pages (safe, no locking)

### Unsafe Without Approval
1. **VACUUM FULL** — Requires table lock, not recommended for production
2. **Record deletion** — Only after lifecycle classification and approval
3. **Schema changes** — Require migration and rollback plan

## Estimated Reclaimable Space

- **Current:** ~2.7 MB (database) + 2.2 MB (snapshot)
- **After VACUUM:** ~2.5 MB (estimated)
- **After compression:** ~0.8 MB (snapshot, gzipped)
- **Total potential savings:** ~1.6 MB (60% reduction)

## Notes

- Stored status reflects the last verified label; effective lifecycle may differ (e.g., record 2 ICCR has stored status OPEN but its application window ended 22 Apr 2026). OPEN stored status is not proof of an active application window. Audit scope is stored-status and storage only; no deletion eligibility is inferred.
- Storage is minimal for a catalogue of 773 records
- Primary optimization target: frontend snapshot compression