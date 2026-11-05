# Post-Merge Security and Correctness Remediation of Production Purge Preflight System (PR #67)

## Base Information
- **Base SHA (PR #67 merge)**: 885ce34e378d9057fb8ae7ca459fbd0caf907758
- **Current HEAD**: 95aff8419ad62f950ebe2c92f7d0252f4e751e51
- **Branch**: fix/preflight-remediation-67
- **PR**: #71

## Files Changed (14 files)
1. `backend/app/services/purge_preflight/config.py` - Gate-specific configuration isolation + DurableStorageConfig
2. `backend/app/services/purge_preflight/gate1_atomicity.py` - Gate 1 config loading
3. `backend/app/services/purge_preflight/gate2_identity.py` - Comprehensive least-privilege audit (all schemas, role memberships, sequences, functions, SET ROLE)
4. `backend/app/services/purge_preflight/gate3_dependencies.py` - Detailed FK dependency reporting
5. `backend/app/services/purge_preflight/gate4_backup.py` - Credential-safe pg_dump/pg_restore, GPG lifecycle, Neon PITR via API/pg_settings, Durable storage (S3/GCS/Azure) with upload/download/checksum/restore verification
6. `backend/app/services/purge_preflight/gate5_classification.py` - Explicit mismatch reporting, 34-ID reconciliation, EXPECTED_CLASSIFICATIONS as reference manifest
7. `backend/app/services/purge_preflight/gate6_cycle_validation.py` - Gate 6 config loading
8. `backend/app/services/purge_preflight/gate7_git_safety.py` - Gate 7 config loading
9. `backend/app/services/purge_preflight/purge_manifest.py` - Gate 2 config for manifest generation
10. `backend/app/services/purge_preflight/manifest.py` - EXPECTED_CLASSIFICATIONS documented as reference manifest, detailed mismatch reporting
11. `.github/workflows/ci.yml` - PostgreSQL 16/18 matrix testing for all jobs
12. `backend/tests/test_purge_preflight.py` - 21 new regression tests (total 48 tests)
13. `REMEDIATION_SUMMARY.md` - This document
14. `PR_BODY.md` - PR description

---

## Root Causes Addressed

### 1. GATE-SPECIFIC CONFIGURATION (config.py)
**Problem**: `PreflightConfig.from_env()` required ALL environment variables for ALL gates, even though different gates need different configurations. Gates 2, 3, 5, 6 failed because Gate 4 GPG/backup variables were required even when not running Gate 4.

**Fix**: 
- Added `GATE_REQUIREMENTS` mapping defining required env vars per gate
- `from_env(gates_to_run)` now only validates required vars for specified gates
- Gate 1: Only `TEST_DATABASE_URL`
- Gates 2,3,5,6: Read-only URL + Neon identity vars
- Gate 4: Backup URL + GPG vars + RESTORE_TEST_* vars + DURABLE_STORAGE_* vars
- Gate 7: No database config needed
- Added `RestoreTestConfig` and `DurableStorageConfig` dataclasses

### 2. DATABASE LEAST PRIVILEGE (gate2_identity.py)
**Problem**: The `scholarzone_readonly` role was assumed safe merely because of its name. No verification of superuser, createrole, createdb, replication, bypassrls, or table-level write privileges. Only checked public schema.

**Fix**: Enhanced `_verify_role_privileges()` to comprehensively check across ALL schemas:
- Role attributes: SUPERUSER, CREATEROLE, CREATEDB, REPLICATION, BYPASSRLS (all must be FALSE)
- Table-level privileges: INSERT, UPDATE, DELETE, TRUNCATE on ALL tables in ALL schemas (all must be FALSE)
- SELECT privilege on scholarships table (must be TRUE)
- Transaction read-only enforcement: `default_transaction_read_only = on`
- Role memberships: Recursive check via pg_auth_members for inherited privileges (SUPERUSER, CREATEROLE, CREATEDB, REPLICATION, BYPASSRLS) with ADMIN OPTION detection
- Membership chain traversal limit (max 10 levels) with cycle detection
- Schema privileges: CREATE must be FALSE, USAGE must be TRUE on ALL schemas
- Sequence privileges: USAGE and UPDATE (setval) must be FALSE on ALL sequences in ALL schemas
- Function/routine EXECUTE privileges: All flagged for audit on ALL schemas
- SET ROLE exposure: Detects any role current_user can SET ROLE to
- Catalog accessibility: Verifies all required system catalogs are queryable (fail closed if not)
- Fail closed on any inaccessible catalog or incomplete privilege check

### 3. GATE 3 DEPENDENCY VERIFICATION (gate3_dependencies.py)
**Problem**: FK dependency discovery was functional but lacked detailed reporting of which specific target IDs had references in which tables.

**Fix**: Enhanced `Gate3Result` with:
- `referencing_tables`: Detailed list of each referencing table with aggregate counts
- `target_ids_with_references`: Per-target mapping of which tables reference each ID
- Clear error messages showing exact table names and reference counts

### 4. GATE 5 TARGET CLASSIFICATION (gate5_classification.py + manifest.py)
**Problem**: Classification validation used hardcoded `EXPECTED_CLASSIFICATIONS` without reporting actual database state (status, deadline, archive state, evidence provenance). Could authorize purge from static counts alone.

**Fix**: 
- `EXPECTED_CLASSIFICATIONS` documented as REFERENCE MANIFEST only (not hardcoded truth)
- `validate_classifications()` returns `ClassificationValidationResult` with:
  - `mismatches`: List of `MismatchDetail` (id, expected, actual, reason)
  - `missing_from_db`: IDs in EXPECTED but not in live DB
  - `unexpected_in_db`: IDs in live DB but not in EXPECTED
  - `category_breakdown`: Counts per category
  - `reconciliation_verified`: True only if 0 mismatches, 0 missing, 0 unexpected, correct counts, 0 blocked categories
- `run_gate5()` produces `record_classifications` with per-record details: classification, status, deadline, deadline_precision, is_archived, archived_at, archived_reason, official_source_url, evidence_provenance, classification_reason
- Gate PASS requires: `reconciliation_verified == True` (0 mismatches + 0 blocked + all 34 IDs reconciled)
- NEVER uses EXPECTED_CLASSIFICATIONS as sole authorization for purge
- Reports all 34 IDs, missing records, conflicts, unresolved references explicitly

### 5. GATE 6 CYCLE VALIDATION (gate6_cycle_validation.py)
**Problem**: Already required authoritative evidence (excerpt hash, retrieval date, reviewer, EXPIRED_VERIFIED decision). No changes needed beyond config loading update.

### 6. GATE 4 BACKUP AND RESTORE (gate4_backup.py)
**Problem**: 
- pg_dump/pg_restore passed database URLs with embedded credentials in command line
- GPG key lifecycle verification was present but could be strengthened
- PITR verification used Neon GUCs but had unconditional 7-day fallback
- No durable backup storage verification
- Remote checksum verification was local-only

**Fix**:
- `run_pg_dump()` and `run_pg_restore()` parse URL and use `PGPASSWORD` env var + explicit `-h/-p/-U/-d` flags (credentials never in command line)
- **Neon PITR Verification**: 
  - Requires `neon.project_id` and `neon.branch_id` settings to confirm Neon instance
  - Queries Neon API (`NEON_API_KEY`) for authoritative `history_retention_seconds` and `pitr_enabled`
  - Falls back to `pg_settings` for `neon.pitr_retention_days` and `neon.pitr_enabled` only if API unavailable
  - Converts seconds to days correctly (ceiling division)
  - Requires ≥7 days retention if that's the declared backup policy
  - Returns UNVERIFIED if no authoritative evidence (no API, no pg_settings)
  - **NEVER** infers production PITR from server version string alone
- **GPG Key Lifecycle**: Verifies both public and private key fingerprints match pinned value; test mode generates synthetic keys in isolated GNUPGHOME
- **Durable Storage (S3/GCS/Azure)**:
  - Upload: `aws s3 cp` / `gsutil cp` / `az storage blob upload --auth-mode login` (NO account keys in command args)
  - Azure: Uses authenticated session (`az login --identity` or service principal via env vars), never `--account-key` in command line
  - Download: Returns checksum of downloaded file for independent verification
  - Restore from durable: Full upload→download→checksum→decrypt→restore→verify path
  - `remote_checksum_verified` depends on independently verified remote object content (downloaded file checksum vs uploaded checksum sidecar)
  - Fail closed if remote storage unavailable
- `get_pitr_status()` returns 3-tuple (status, retention_days, details) - fixed tuple unpacking in run_gate4()

### 7. POSTGRESQL COMPATIBILITY (ci.yml)
**Problem**: CI only tested against PostgreSQL 16. Production uses PostgreSQL 18.

**Fix**: Added matrix strategy to `schema-compat`, `preflight`, `postgresql-migration-test`, and `gate1-integration` jobs testing both `postgres:16` and `postgres:18`. Updated workflow YAML syntax test to verify matrix configuration.

### 8. WORKFLOW SAFETY (production-purge-preflight.yml)
**Problem**: Already had good safety controls (manual trigger, confirm_environment, protected environments, check_preflight_status.py). No changes needed.

### 9. REGRESSION TESTS (test_purge_preflight.py)
**Added 21 new regression tests covering**:
1. `test_regression_incorrect_database_identity` - Gate 2 rejects wrong project/branch/db
2. `test_regression_elevated_database_role` - Gate 2 rejects SUPERUSER/CREATEDB/BYPASSRLS
3. `test_regression_missing_gate_specific_config` - Gate-specific config loading works
4. `test_regression_missing_target_ids` - Gate 5 fails on missing records
5. `test_regression_incorrect_status_deadline_classification` - All classification edge cases
6. `test_regression_unresolved_foreign_key_references` - Gate 3 fails on FK references
7. `test_regression_missing_gpg_keys` - Gate 4 fails on missing GPG keys
8. `test_regression_backup_storage_failure` - Gate 4 handles pg_dump failure
9. `test_regression_restore_failure` - Gate 4 handles pg_restore failure
10. `test_regression_invalid_pitr_evidence` - Gate 4 fails on invalid PITR (non-Neon, disabled, invalid retention)
11. `test_regression_credential_leakage` - Credentials use PGPASSWORD, not command line
12. `test_regression_postgresql_version_compatibility` - PG16/18 syntax compatibility
13. `test_regression_missing_durable_backup_config` - Gate 4 fails without DURABLE_STORAGE_* vars
14. `test_regression_remote_checksum_mismatch` - Checksum mismatch detection
15. `test_regression_restore_from_remote_backup_failure` - Restore from corrupt remote backup
16. `test_regression_missing_pitr_evidence` - Gate 4 fails when PITR evidence missing/invalid
17. `test_regression_role_membership_privilege_escalation` - Inherited SUPERUSER/CREATEROLE/CREATEDB/BYPASSRLS, nested membership
18. `test_regression_schema_create_privilege` - CREATE privilege on any schema
19. `test_regression_sequence_write_privilege` - USAGE/UPDATE on sequences
20. `test_regression_gate5_classification_mismatch` - Live classification vs expected manifest mismatch
21. `test_regression_azure_credential_safety` - Azure CLI uses authenticated session, no keys in args

---

## Test Evidence
All tests pass:
- **48 passed, 1 skipped** (integration test requires TEST_DATABASE_URL) - `test_purge_preflight.py`
- **38 passed** - `test_purge_closed.py` + `test_purge_image_safety.py`
- CI workflow syntax test verifies PostgreSQL 16/18 matrix

---

## CI Run Links
- PR #71: https://github.com/gopal735/ScholarZone/pull/71
- CI Run: https://github.com/gopal735/ScholarZone/actions/runs/42064234658 (PG16/PG18 matrix)

---

## Remaining Owner-Only Actions
1. **Configure GitHub Environments**: Ensure `production-readonly` and `production-backup` environments exist with required secrets
2. **Set Production Secrets**: 
   - `SCHOLARZONE_DATABASE_URL_RO` (read-only role)
   - `SCHOLARZONE_DATABASE_URL_BACKUP` (backup role)
   - `EXPECTED_NEON_PROJECT_ID`, `EXPECTED_NEON_BRANCH_ID`, `EXPECTED_NEON_BRANCH_NAME`, `EXPECTED_DATABASE_NAME`
   - `GPG_RECIPIENT`, `GPG_EXPECTED_FINGERPRINT`
   - `RESTORE_TEST_PGHOST`, `RESTORE_TEST_PGPORT`, `RESTORE_TEST_PGUSER`, `RESTORE_TEST_PGPASSWORD`
   - `DURABLE_STORAGE_PROVIDER` (s3|gcs|azure), `DURABLE_STORAGE_BUCKET`, `DURABLE_STORAGE_REGION`, `DURABLE_STORAGE_CREDENTIAL`, `DURABLE_STORAGE_CREDENTIAL_SECRET`
   - `NEON_API_KEY` (for authoritative PITR verification)
   - `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` (for Azure auth)
3. **Verify Neon PITR**: Confirm `neon.pitr_enabled=on` and `history_retention_seconds` ≥ 604800 (7 days) on production branch via Neon API
4. **GPG Key Setup**: Import production GPG public/private key pair matching `GPG_EXPECTED_FINGERPRINT`
5. **Run Full Preflight**: Execute `production-purge-preflight.yml` with `gate: all` and `confirm_environment: true`
6. **Review Results**: Verify all 7 gates PASS and `check_preflight_status.py` returns SUCCESS

---

## Final Verdict

### CI_VERIFIED ✅
All unit and regression tests pass. CI pipeline tests against PostgreSQL 16 and 18.

### PRODUCTION_PREFLIGHT_VERIFIED ⏳
Pending: Requires production secrets configuration and successful workflow_dispatch execution against production Neon database.

### OWNER_ACTION_REQUIRED ✅
Owner must configure environments, secrets, GPG keys, and verify PITR before preflight can be run.

### PRODUCTION_PURGE_AUTHORIZED ❌
**NOT AUTHORIZED** - This remediation only covers preflight verification. Production purge requires:
1. All 7 gates PASS in production preflight run
2. Owner approval via separate explicit workflow_dispatch
3. Separate production purge workflow with additional safeguards

---

## Safety Boundaries Maintained
- ✅ No production DELETE, UPDATE, or INSERT
- ✅ No production role or permission changes
- ✅ No production schema changes
- ✅ No production purge executed
- ✅ No workflow_dispatch against production in this PR
- ✅ No production secrets in source code or logs
- ✅ No deployment or merge
- ✅ Disposable databases used for all integration tests
- ✅ Credentials use PGPASSWORD env var, never in command line
- ✅ Azure credentials use authenticated session, never in command line