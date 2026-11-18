# Database Storage Audit

**Date:** 2026-11-18
**Database:** Local SQLite (development) — NOT production
**Database File:** scholarzone.db (local development)
**Scope:** Local development environment only

## Important Scope Note

This audit measures the **local development SQLite database**, not production.
Production database (PostgreSQL) measurements require separate production
access and are not included in this report.

## Database Size

- **Total DB file size:** ~2.7 MB (local SQLite)
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
4. **Vacuum SQLite** — `VACUUM` is a write operation that can require exclusive access/locking. Document safe maintenance conditions before running on any database.

### Unsafe Without Approval
1. **VACUUM FULL** — Requires table lock, not recommended for production
2. **Record deletion** — Only after lifecycle classification and approval
3. **Schema changes** — Require migration and rollback plan

## Estimated Reclaimable Space

- **Current:** ~2.7 MB (database) + 2.2 MB (snapshot)
- **After VACUUM:** ~2.5 MB (estimated, local SQLite only)
- **After compression:** ~0.8 MB (snapshot, gzipped)
- **Total potential savings:** ~1.6 MB (60% reduction, local only)

## Production Considerations

- Production uses PostgreSQL, not SQLite
- Production storage measurements require separate access
- VACUUM FULL on PostgreSQL requires exclusive table lock
- Do not execute disruptive maintenance without approval
- Actual production savings cannot be estimated from local data

## Notes

- No CLOSED records to purge at this time
- All records are active (open/upcoming)
- Storage is minimal for a catalogue of 773 records
- Primary optimization target: frontend snapshot compression