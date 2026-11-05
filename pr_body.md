## Summary

This PR implements a complete secure CI preflight workflow for production expired-cycle purge (Gates 1-7).

## Changes

- **Gate 1**: Atomicity & rollback test with disposable PostgreSQL 16 (CI verified)
- **Gate 2**: Production identity verification with read-only Neon connection
- **Gate 3**: Dynamic FK dependency discovery with CASCADE check
- **Gate 4**: Encrypted pg_dump backup with GPG encryption and restore test
- **Gate 5**: Exact target ID classification (34 IDs, 18 CLOSED / 16 CLOSING_SOON)
- **Gate 6**: Current application-cycle validation with evidence-backed evidence
- **Gate 7**: Git safety (scope, secrets, mutations, worktree isolation)

## Security Features

- Read-only DB roles for Gates 2 & 3
- Separate backup role for Gate 4
- GPG encryption for backups with fingerprint verification
- No raw database dumps in artifacts
- Separate backup role with least privileges
- GPG recipient and fingerprint from secrets
- Read-only enforcement in scripts
- Fail-closed on missing configuration/identity
- Fail-closed on backup/restore failure
- Fail-closed on target-ID mismatch
- No hidden production fallback
- No unsafe CASCADE assumption
- No unencrypted backup artifact
- No production mutation in CI tests

## Schema Compatibility

- Empty database returns EMPTY with exit code 1 (not PASS)
- Missing database URL returns FAIL
- Missing table/column returns FAIL
- Connection failure returns FAIL
- Passwords redacted in logs
- Checker is read-only
- Uses postgresql+psycopg:// driver
- PostgreSQL 16 initialization via actual app init path
- Idempotency verified (second init succeeds)
- Canonical table names from SQLAlchemy models (29 tables)

## CI Validation Results (Commit a368fe8)

### Push CI (Run #597)
- backend-tests (79 passed, 1 skipped)
- frontend-tests (264 passed)
- frontend-lint (passed)
- schema-compat (PostgreSQL 16, PASS)
- preflight (PostgreSQL 16, PASS)
- import-smoke
- build-and-smoke (Docker build + smoke test)
- PostgreSQL Migration Integration Test
- Gate 1 - Atomicity Integration Test (PostgreSQL 16)
- Snapshot ID Validation
- git-integrity
- env-config

### PR CI (Run #598)
- All required jobs pass on exact HEAD SHA

### Tests
- Backend: 79 passed, 1 skipped (integration requires TEST_DATABASE_URL)
- Frontend: 264 passed
- Migration: 8 passed
- Git integrity: 25 passed
- Schema compatibility regression: 8 passed

### Gates Status
- Gate 1: CI VERIFIED (PostgreSQL 16 integration test passes)
- Gate 2: PENDING OWNER (requires SCHOLARZONE_DATABASE_URL_RO + production identity config)
- Gate 3: PENDING OWNER (requires SCHOLARZONE_DATABASE_URL_RO + production identity config)
- Gate 4: PENDING OWNER (requires SCHOLARZONE_DATABASE_URL_BACKUP + GPG keys)
- Gate 5: VERIFIED (34 IDs classified: 18 CLOSED / 16 CLOSING_SOON)
- Gate 6: VERIFIED (cycle model validated with evidence requirements)
- Gate 7: VERIFIED (Git safety confirmed via CI)

## Security Notes

- No production DELETE executed
- No production data modified
- No credentials exposed
- Separate read-only and backup roles
- Encrypted backups only in artifacts
- GPG keys not in repository
- Fail-closed on missing configuration/identity
- Fail-closed on backup/restore failure
- Fail-closed on target-ID mismatch
- No hidden production fallback
- No unsafe CASCADE assumption
- No unencrypted backup artifact
- No production mutation in CI tests

## Required Setup (Owner Actions)

Before production execution, configure GitHub Environments and secrets:

- production-readonly: SCHOLARZONE_DATABASE_URL_RO, EXPECTED_NEON_PROJECT_ID, EXPECTED_NEON_BRANCH_ID, EXPECTED_NEON_BRANCH_NAME, EXPECTED_DATABASE_NAME
- production-backup: SCHOLARZONE_DATABASE_URL_BACKUP, GPG_RECIPIENT, GPG_EXPECTED_FINGERPRINT, RESTORE_TEST_PGHOST, RESTORE_TEST_PGPORT, RESTORE_TEST_PGUSER, RESTORE_TEST_PGPASSWORD
- Neon PITR verification in console

## CI Evidence

- Push CI Run #597: https://github.com/gopal735/ScholarZone/actions/runs/41979716311
- PR CI Run #598: https://github.com/gopal735/ScholarZone/actions/runs/41979716374
- Exact HEAD SHA: a368fe8cccc4457f1583a653ef3661755dc2595d

## Safety

- No production data deleted
- No deployment
- No merge (preflight only)
- Original worktree preserved
- No production database connections in CI
- Only disposable PostgreSQL 16 services used

## Remaining Owner Actions

1. Configure GitHub Environments and secrets (production-readonly, production-backup)
2. Run workflow manually via workflow_dispatch with gate: all, confirm_environment: true
3. Review Gates 2-4 results
4. If all pass, request production deletion approval

## Safety

- No production data deleted
- No deployment
- No merge (preflight only)
- Original worktree preserved
- No production database connections in CI
- Only disposable PostgreSQL 16 services used