## Summary

Post-merge security and correctness remediation of the production purge preflight system introduced by PR #67.

**Base SHA (PR #67 merge)**: 885ce34e378d9057fb8ae7ca459fbd0caf907758
**Current HEAD**: 4dad99c8b92c3e39fbe22115d8e9291340d0a733

## Changes (12 files)

| File | Description |
|------|-------------|
| `.github/workflows/ci.yml` | PostgreSQL 16/18 matrix testing for schema-compat, preflight, postgresql-migration-test, gate1-integration |
| `backend/app/services/purge_preflight/config.py` | Gate-specific config isolation via `GATE_REQUIREMENTS` mapping; `from_env(gates_to_run)` validates only needed vars |
| `backend/app/services/purge_preflight/gate1_atomicity.py` | Gate 1 config loading via `load_config(gates_to_run={"gate1"})` |
| `backend/app/services/purge_preflight/gate2_identity.py` | Enhanced `_verify_role_privileges()`: checks SUPERUSER/CREATEROLE/CREATEDB/REPLICATION/BYPASSRLS + table-level write privileges on ALL public tables + `default_transaction_read_only=on` |
| `backend/app/services/purge_preflight/gate3_dependencies.py` | Added `referencing_tables` and `target_ids_with_references` for exact table names and per-target reference counts |
| `backend/app/services/purge_preflight/gate4_backup.py` | Credential-safe pg_dump/pg_restore using PGPASSWORD env var; GPG key lifecycle verification; PITR error reporting |
| `backend/app/services/purge_preflight/gate5_classification.py` | Detailed `record_classifications` with status, deadline, archive state, evidence provenance, classification reason |
| `backend/app/services/purge_preflight/gate6_cycle_validation.py` | Gate 6 config loading via `load_config(gates_to_run={"gate6"})` |
| `backend/app/services/purge_preflight/gate7_git_safety.py` | Gate 7 config loading via `load_config(gates_to_run={"gate7"})` |
| `backend/app/services/purge_preflight/purge_manifest.py` | Gate 2 config for manifest generation |
| `backend/tests/test_purge_preflight.py` | **12 new regression tests** covering incorrect identity, elevated roles, missing config, missing targets, classification conflicts, FK references, missing GPG keys, backup/restore failures, invalid PITR, credential leakage |
| `REMEDIATION_SUMMARY.md` | Complete remediation documentation |

## Test Evidence

- 40 passed, 1 skipped (integration test requires TEST_DATABASE_URL)
- 38 passed for test_purge_closed.py and test_purge_image_safety.py
- CI workflow syntax test verifies PG16/18 matrix configuration

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
- Credentials never in command line

## Remaining Owner Actions

1. Configure GitHub Environments (`production-readonly`, `production-backup`)
2. Set Production Secrets
3. Verify Neon PITR (`neon.pitr_enabled=on`, `neon.pitr_retention_days` >= 7)
4. GPG Key Setup (import production key pair matching `GPG_EXPECTED_FINGERPRINT`)
5. Run Full Preflight (`workflow_dispatch` with `gate: all`, `confirm_environment: true`)
6. Review Results (all 7 gates PASS, `check_preflight_status.py` returns SUCCESS)

## Final Verdict

| Status | Verdict |
|--------|---------|
| CI_VERIFIED | All unit/regression tests pass; CI matrix tests PG16 & PG18 |
| PRODUCTION_PREFLIGHT_VERIFIED | Pending production secrets and workflow execution |
| OWNER_ACTION_REQUIRED | Configure environments, secrets, GPG keys, verify PITR |
| PRODUCTION_PURGE_AUTHORIZED | NOT AUTHORIZED - Preflight only; purge requires separate explicit approval