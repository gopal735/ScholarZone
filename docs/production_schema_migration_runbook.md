# ScholarZone Production Schema Migration Runbook

## Current missing objects
Production inventory: NOT VERIFIED.

This runbook does not assert exact observed production object counts. Any
missing/incorrect object list must come from a fresh read-only catalog
inspection and comparison with `backend/schema_manifest.json`.

## Status values emitted by the validator
- `OK`
- `MISSING`
- `MISMATCH`
- `UNEXPECTED`
- `TABLE_MISSING` for a required parent table that is absent
- `TABLE_MISSING_SKIPPED` only for an explicitly optional object contract

## Database target verification
1. Confirm the Vercel production deployment SHA.
2. Confirm `SCHOLARZONE_DATABASE_URL` points to the intended Neon production branch.
3. Set `SCHOLARZONE_EXPECTED_DB_IDENTIFIER` and `SCHOLARZONE_EXPECTED_DB_HOST` to the exact expected values.
4. Run `migrate_schema.py --validate-only --report` in the `DB State Check` workflow.
5. The script must report `verified: true` for database identity.

Never print or commit the database URL.

## Safety gates
- `SCHOLARZONE_BACKUP_VERIFIED=true`
- `SCHOLARZONE_RESTORE_TEST_DATE` within 30 days
- `SCHOLARZONE_BACKUP_EVIDENCE_REF` non-empty
- `apply=false` for dry-run
- `apply=true` only after owner authorization

## Read-only validation
```bash
python backend/migrate_schema.py --validate-only --report
```

## Dry-run
```bash
python backend/migrate_schema.py --dry-run --report
```

## Review
Inspect the generated JSON report. Stop if any required object is `MISSING`,
`MISMATCH`, `UNEXPECTED`, or `TABLE_MISSING`. Do not treat inferred counts as
exact observations.

## Expected vs observed schema
A. Expected schema: derived from `backend/schema_manifest.json`.
B. Observed production schema: requires fresh read-only catalog inspection.
C. Missing objects: derived by comparing A and B.
D. Incorrect objects: derived from exact definition mismatches.

If no verified read-only production catalog query was performed, production
inventory remains NOT VERIFIED.

## Apply
Only after owner authorization:
```bash
python backend/migrate_schema.py --apply --report
```

## Post-migration verification
```bash
python backend/migrate_schema.py --validate-only --report
```
Smoke-test:
- `GET /scholarships/{id}/supervisors`
- `GET /api/scholarships`

## Separately managed dependency
- `scholarship_image_audit` and its trigger are managed by `backend/scripts/install_image_audit.py` and `app.image_audit`. They are not created by `migrate_schema.py`.

## Failure handling
- A failed migration rolls back the transaction.
- Re-run validation before retrying.
- Do not manually create competing schema objects.