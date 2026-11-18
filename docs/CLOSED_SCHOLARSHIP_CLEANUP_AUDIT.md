# Closed Scholarship Cleanup Audit

**Date:** 2026-11-18
**Audit Timestamp:** 2026-11-18T12:00:00+00:00
**Database:** Local SQLite (development) — NOT production
**Total Records:** 773

## Summary

The ScholarZone database currently contains **0 records with stored status `closed`**.
All 773 records have stored status `open` (772) or `upcoming` (1).

### Stored Status Distribution
| Status | Count |
|--------|-------|
| open | 772 |
| upcoming | 1 |
| closed | 0 |
| archived | 0 |
| quarantined | 0 |
| **Total** | **773** |

## Deadline-Aware Lifecycle Audit

**Important:** Stored status alone does not prove that all 772 "open" records
are currently accepting applications. A deadline-aware audit is required.

### Known Limitations
- The current database does not store application_open_date or application_deadline
  for most master records (only the 2 Italy records have these fields).
- Without deadline data, it is impossible to determine which "open" records
  have actually expired.
- The master baseline snapshot (771 records) also shows all as "open" with
  no deadline information.

### Recommended Actions
1. **Add deadline fields** to master records where official sources provide them.
2. **Implement automated lifecycle classification** based on deadline comparison.
3. **Re-audit** after deadline data is populated.
4. **No deletion** — All records retained as programme identities.

## Classification

No records classified as CLOSED based on stored status.
Deadline-aware classification not yet possible (missing deadline data for 771 records).

### Classification Summary (Stored Status Only)
| Category | Count | Notes |
|----------|-------|-------|
| A — Expired cycle | Unknown | Missing deadline data |
| B — Permanently discontinued | 0 | No evidence |
| C — Temporarily suspended | 0 | No evidence |
| D — Unknown/unverifiable | 771 | Missing deadline data |
| E — Invalid/duplicate | 0 | No evidence |

## Candidate Manifest

No candidates for removal. Empty manifest.

## Foreign-Key Dependencies

No dependencies to report (no CLOSED records).

## Storage Impact

No storage reclaimable from scholarship record deletion (0 CLOSED records with stored status).

## Audit Trail

- Audit date: 2026-11-18
- Database: scholarzone.db (local development)
- Total records: 773
- Stored CLOSED: 0
- Stored OPEN: 772
- Stored UPCOMING: 1
- Deadline-verified OPEN: Unknown (missing deadline data)
- Action taken: None (no candidates)
- Production purge approved: No
- Production purge executed: No