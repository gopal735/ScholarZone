# REQUIRED GITHUB CONFIGURATION

Source of truth: `backend/app/services/purge_preflight/config.py`,
`backend/app/services/purge_preflight/database.py`, and the workflow files under
`.github/workflows/`. This document must not be used to override code.

## Workflow roles

- `production-purge-preflight.yml` — operator-run preflight (Gates 1-7).
- `closed-scholarship-purge-preflight.yml` — PR #107 Stage 1 preflight (merge-commit verified).
- `closed-scholarship-purge-execute.yml` — Stage 2 execution (separately authorized, not part of this prompt).

## Environments

### production-readonly
- Branch policy: `master` only (verified via GitHub API).
- Required reviewers: **none currently** (owner policy decision; see section 6).
- Secrets: `SCHOLARZONE_DATABASE_URL_RO`.
- Variables or secrets (workflows currently read via `secrets.*`): `EXPECTED_NEON_PROJECT_ID`, `EXPECTED_NEON_BRANCH_ID`, `EXPECTED_NEON_BRANCH_NAME`, `EXPECTED_DATABASE_NAME`, `EXPECTED_DATABASE_HOST`.
- Gates: 2, 3, 5, 6.

### production-backup
- Branch policy: `master` only (verified via GitHub API).
- Required reviewers: 1 (`gopal735`) (verified via GitHub API).
- Secrets: `SCHOLARZONE_DATABASE_URL_BACKUP`, `RESTORE_TEST_PGPASSWORD`, `DURABLE_STORAGE_CREDENTIAL_SECRET` (S3 only), `NEON_API_KEY`, and (for the closed workflow's GPG provisioning) `GPG_PUBLIC_KEY`, `GPG_PRIVATE_KEY`.
- Variables or secrets (workflows currently read via `secrets.*`): `GPG_RECIPIENT`, `GPG_EXPECTED_FINGERPRINT`, `RESTORE_TEST_PGHOST`, `RESTORE_TEST_PGPORT`, `RESTORE_TEST_PGUSER`, `EXPECTED_NEON_PROJECT_ID`, `EXPECTED_NEON_BRANCH_ID`, `EXPECTED_NEON_BRANCH_NAME`, `EXPECTED_DATABASE_NAME`, `EXPECTED_DATABASE_HOST`, `DURABLE_STORAGE_PROVIDER`, `DURABLE_STORAGE_BUCKET`, `DURABLE_STORAGE_REGION`, `DURABLE_STORAGE_CREDENTIAL`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`.
- Gates: 4.

### production
- Used only by Stage 2 execution. No configuration action is authorized under this prompt.

## Gate dependency matrix

| Gate | Required configuration |
|---|---|
| Gate 1 | `TEST_DATABASE_URL` (disposable local PostgreSQL only) |
| Gate 2 | `SCHOLARZONE_DATABASE_URL_RO`, `EXPECTED_NEON_PROJECT_ID`, `EXPECTED_NEON_BRANCH_ID`, `EXPECTED_NEON_BRANCH_NAME`, `EXPECTED_DATABASE_NAME` |
| Gate 3 | Same as Gate 2, plus deletion manifest artifact |
| Gate 4 | `SCHOLARZONE_DATABASE_URL_BACKUP`, `GPG_RECIPIENT`, `GPG_EXPECTED_FINGERPRINT`, `RESTORE_TEST_PGHOST`, `RESTORE_TEST_PGPORT`, `RESTORE_TEST_PGUSER`, `RESTORE_TEST_PGPASSWORD`, `DURABLE_STORAGE_PROVIDER`, `DURABLE_STORAGE_BUCKET`, `DURABLE_STORAGE_REGION`, `DURABLE_STORAGE_CREDENTIAL`, `EXPECTED_NEON_PROJECT_ID`, `EXPECTED_NEON_BRANCH_ID`, `EXPECTED_NEON_BRANCH_NAME`, `EXPECTED_DATABASE_NAME`, `EXPECTED_DATABASE_HOST`, plus `DURABLE_STORAGE_CREDENTIAL_SECRET` only when provider is `s3` |
| Gate 5 | Same as Gate 2, plus deletion manifest artifact |
| Gate 6 | Same as Gate 2, plus deletion manifest artifact |
| Gate 7 | `STAGE1_MASTER_SHA` (passed by workflow from `github.sha`); no database configuration |

## Provider-conditional durable storage

- `s3`: requires `DURABLE_STORAGE_CREDENTIAL` (access key id) and `DURABLE_STORAGE_CREDENTIAL_SECRET` (secret access key).
- `gcs`: requires `DURABLE_STORAGE_CREDENTIAL` (service account JSON path). `DURABLE_STORAGE_CREDENTIAL_SECRET` is not consumed.
- `azure`: requires `DURABLE_STORAGE_CREDENTIAL` (storage account name). Uses OIDC via `azure/login`; no client secret is supported.

## Optional / internal defaults

- `DURABLE_STORAGE_PREFIX` — internal default `purge-preflight-backups/`. Not mapped in workflows; do not override without review.
- `ARTIFACT_RETENTION_DAYS` — internal default `30`.
- `SCHOLARZONE_TEST_MODE` — internal default false. Must never be enabled in production workflows.
- `MANIFEST_PATH` — internal default `artifacts/deletion_manifest.json`.
- `NEON_API_KEY` — optional but recommended for authoritative PITR verification (Gate 4). Without it, PITR status is `UNVERIFIED`.
- `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` — required only when provider is `azure`.
- `GPG_PUBLIC_KEY`, `GPG_PRIVATE_KEY` — required only in workflows that provision an ephemeral keyring (closed preflight).

## GPG handling

- Production workflows provision an ephemeral `GNUPGHOME` (mode 700) from `GPG_PUBLIC_KEY` and `GPG_PRIVATE_KEY`.
- Keys are imported via stdin; private key material is never placed in argv.
- Fingerprint is verified after import against `GPG_EXPECTED_FINGERPRINT`.
- The ephemeral keyring is removed in an `if: always()` cleanup step.
- Private key material is never uploaded as an artifact or cached.

## Owner policy (not changed by this repository)

### production-readonly reviewers
Currently none. Recommendation: add at least one required reviewer because read-only
credentials can expose sensitive production data. Trade-off: each manual preflight
run waits for approval.

### master branch protection
Currently not enabled (API returned 404). Recommendation: enable branch protection
with pull-request requirement, no force push, no deletion, required status checks,
and restricted bypass. Preserve an emergency recovery procedure.

## Obsolete names (do not use)

The following names are not part of the current purge-preflight contract and must
not be provisioned as required secrets: `BACKUP_ENCRYPTION_PASSPHRASE`,
`BACKUP_STORAGE_BUCKET`, `BACKUP_STORAGE_CREDENTIALS`.

## Secret handling

- Never commit secrets.
- Never print secret values.
- Never share connection strings, passwords, API keys, GPG private keys, or storage credentials.
- Validate configuration privately through the gates after provisioning.
filePath">
C:\Users\GopaL\AppData\Local\Temp\kilo\audit-master-pr116\docs\operations\purge\REQUIRED_GITHUB_CONFIGURATION.md