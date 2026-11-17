# ScholarZone Production Schema Migration Runbook

## Current missing objects
- `public.official_contacts`
- `scholarships.legacy_id`
- `scholarships.image_kind` and the other 28 scholarship columns in `backend/schema_manifest.json`
- `image_reviews` and its two indexes
- Required indexes on `official_contacts`

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
Inspect the generated JSON report for missing tables, columns, indexes, and foreign keys. Stop if any object is `PRESENT_BUT_INCORRECT`.

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