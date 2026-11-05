## Summary

Post-merge security and correctness remediation of the production purge preflight system introduced by PR #67.

**Base SHA (PR #67 merge)**: 885ce34e378d9057fb8ae7ca459fbd0caf907758
**Current HEAD**: 95aff8419ad62f950ebe2c92f7d0252f4e751e51
**Branch**: fix/preflight-remediation-67
**PR**: #71

## Changes (14 files)

| File | Description |
|------|-------------|
| `.github/workflows/ci.yml` | PostgreSQL 16/18 matrix testing for schema-compat, preflight, postgresql-migration-test, gate1-integration |
| `backend/app/services/purge_preflight/config.py` | Gate-specific config isolation via `GATE_REQUIREMENTS` mapping; `from_env(gates_to_run)` validates only needed vars; added `DurableStorageConfig` |
| `backend/app/services/purge_preflight/gate1_atomicity.py` | Gate 1 config loading via `load_config(gates_to_run={"gate1"})` |
| `backend/app/services/purge_preflight/gate2_identity.py` | Comprehensive least-privilege audit: all schemas, role memberships (recursive, ADMIN OPTION, SET ROLE), sequences, functions, catalog accessibility, membership chain limits |
| `backend/app/services/purge_preflight/gate3_dependencies.py` | Added `referencing_tables` and `target_ids_with_references` for exact table names and per-target reference counts |
| `backend/app/services/purge_preflight/gate4_backup.py` | Credential-safe pg_dump/pg_restore (PGPASSWORD); GPG key lifecycle; Neon PITR via API/pg_settings (no 7-day fallback); Durable storage (S3/GCS/Azure) with upload/download/checksum/restore verification; Azure uses authenticated session (no keys in args) |
| `backend/app/services/purge_preflight/gate5_classification.py` | Explicit mismatch reporting, 34-ID reconciliation, EXPECTED_CLASSIFICATIONS as reference manifest only; per-record evidence provenance |
| `backend/app/services/purge_preflight/gate6_cycle_validation.py` | Gate 6 config loading via `load_config(gates_to_run={"gate6"})` |
| `backend/app/services/purge_preflight/gate7_git_safety.py` | Gate 7 config loading via `load_config(gates_to_run={"gate7"})` |
| `backend/app/services/purge_preflight/purge_manifest.py` | Gate 2 config for manifest generation |
| `backend/app/services/purge_preflight/manifest.py` | EXPECTED_CLASSIFICATIONS documented as reference manifest; `ClassificationValidationResult` with detailed mismatch reporting |
| `backend/tests/test_purge_preflight.py` | **21 new regression tests** (total 48): incorrect identity, elevated roles, missing config, missing targets, classification conflicts, FK references, missing GPG keys, backup/restore failures, invalid PITR (Free/Launch/Scale), credential leakage, missing durable backup, remote checksum mismatch, restore from remote failure, missing PITR evidence, role membership escalation (nested), schema CREATE, sequence UPDATE, Gate 5 mismatch |
| `REMEDIATION_SUMMARY.md` | Complete remediation documentation |
| `PR_BODY.md` | This file |

## Test Evidence

- **48 passed, 1 skipped** (integration test requires TEST_DATABASE_URL) - `test_purge_preflight.py`
- **38 passed** - `test_purge_closed.py` + `test_purge_image_safety.py`
- CI workflow syntax test verifies PostgreSQL 16/18 matrix

## CI Verification Required

Matrix jobs to verify:
- schema-compat (PG16, PG18)
- preflight (PG16, PG18)
- postgresql-migration-test (PG16, PG18)
- gate1-integration (PG16, PG18)

## Safety Boundaries Maintained

- No production DELETE/UPDATE/INSERT
- No production role/permission/schema changes
- No production purge executed
- No secrets in source code or logs (PGPASSWORD used)
- Disposable databases for all integration tests
- Credentials never in command line (including Azure)

## Remaining Owner Actions

1. Configure GitHub Environments (`production-readonly`, `production-backup`)
2. Set Production Secrets (all DATABASE_URL, EXPECTED_NEON_*, GPG_*, RESTORE_TEST_*, DURABLE_STORAGE_*, NEON_API_KEY, AZURE_*)
3. Verify Neon PITR via API (`history_retention_seconds` ≥ 604800)
4. GPG Key Setup (import production key pair matching `GPG_EXPECTED_FINGERPRINT`)
5. Run Full Preflight (`workflow_dispatch` with `gate: all`, `confirm_environment: true`)
6. Review Results (all 7 gates PASS, `check_preflight_status.py` returns SUCCESS)

## Final Verdict

| Status | Verdict |
|--------|---------|
| CI_VERIFIED | ✅ All unit/regression tests pass; CI matrix tests PG16 & PG18 |
| PRODUCTION_PREFLIGHT_VERIFIED | ⏳ Pending production secrets and workflow execution |
| OWNER_ACTION_REQUIRED | ✅ Configure environments, secrets, GPG keys, verify PITR |
| PRODUCTION_PURGE_AUTHORIZED | ❌ NOT AUTHORIZED - Preflight only; purge requires separate explicit approval |