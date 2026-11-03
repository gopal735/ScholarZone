# REQUIRED GITHUB CONFIGURATION

## Overview
This document lists all GitHub environments, secrets, and permissions required for the production purge preflight workflow.

## Required Environments

### 1. production-readonly
**Purpose:** Gates 2 (Identity) and 3 (Dependencies) - Read-only production access

**Configuration:**
- **Name:** `production-readonly`
- **URL:** `https://console.neon.tech`
- **Protection Rules:**
  - ✅ Required reviewers: 1+ required
  - ✅ Wait timer: 0 minutes
  - ✅ Deployment branch policy: `main` / `master` only
- **Secrets:**
  - `SCHOLARZONE_DATABASE_URL_RO` - Read-only Neon PostgreSQL connection string
  - `EXPECTED_NEON_PROJECT_ID` - Expected Neon project ID (e.g., `scholarzone-production`)
  - `EXPECTED_NEON_BRANCH_ID` - Expected branch ID (e.g., `br-xxxxxxxxx`)
  - `EXPECTED_NEON_BRANCH_NAME` - Expected branch name (default: `main`)
  - `EXPECTED_DATABASE_NAME` - Expected database name (e.g., `scholarzone`)

**Branch Restriction:** Only `main` / `master` branch can deploy to this environment

**Required Reviewers:** At least 1 required reviewer

### 2. production-backup
**Purpose:** Gate 4 - Production Backup & Verification

**Configuration:**
- **Name:** `production-backup`
- **URL:** `https://console.neon.tech`
- **Protection Rules:**
  - ✅ Required reviewers: 1+ required
  - ✅ Wait timer: 0 minutes
  - ✅ Deployment branch policy: `main` / `master` only
- **Secrets:**
  - `SCHOLARZONE_DATABASE_URL_BACKUP` - Backup role Neon PostgreSQL connection string
  - `GPG_RECIPIENT` - GPG key ID for encryption (e.g., `backup@scholarzone.org`)
  - `BACKUP_ENCRYPTION_PASSPHRASE` - Optional symmetric encryption passphrase
  - `BACKUP_STORAGE_BUCKET` - Optional: S3/GCS bucket for durable backup storage
  - `BACKUP_STORAGE_CREDENTIALS` - Optional: Credentials for backup storage

**Branch Restriction:** Only `main` / `master` branch can deploy to this environment

**Required Reviewers:** At least 1 required reviewer

---

## Required Secrets Summary

| Secret | Environment | Description |
|--------|-------------|-------------|
| `SCHOLARZONE_DATABASE_URL_RO` | `production-readonly` | Read-only Neon PostgreSQL connection string |
| `EXPECTED_NEON_PROJECT_ID` | `production-readonly` | Expected Neon project ID (e.g., `scholarzone-production`) |
| `EXPECTED_NEON_BRANCH_ID` | `production-readonly` | Expected Neon branch ID (e.g., `br-xxxxxxxxx`) |
| `EXPECTED_NEON_BRANCH_NAME` | `production-readonly` | Expected branch name (default: `main`) |
| `EXPECTED_DATABASE_NAME` | `production-readonly` | Expected database name (e.g., `scholarzone`) |
| `SCHOLARZONE_DATABASE_URL_BACKUP` | `production-backup` | Backup role Neon PostgreSQL connection string |
| `GPG_RECIPIENT` | `production-backup` | GPG key ID for encryption (e.g., `backup@scholarzone.org`) |
| `BACKUP_ENCRYPTION_PASSPHRASE` | `production-backup` | Optional symmetric encryption passphrase |
| `BACKUP_STORAGE_BUCKET` | `production-backup` | Optional: S3/GCS bucket for durable backup storage |
| `BACKUP_STORAGE_CREDENTIALS` | `production-backup` | Optional: Credentials for backup storage |

---

## GitHub Actions Workflow Permissions

### Workflow: `production-purge-preflight.yml`

**Permissions:**
```yaml
permissions:
  contents: read
  actions: read
  checks: write
  id-token: write  # For OIDC if needed
```

**Job Permissions:**
- Gate 2 & 3 jobs: `contents: read`, `id-token: write`
- Gate 4 job: `contents: read`
- Summary job: `contents: read`

---

## Environment Protection Rules

### production-readonly
- ✅ Required reviewers: 1+
- ✅ Wait timer: 0 minutes
- ✅ Deployment branches: `main`, `master` only
- ✅ No self-review by workflow author

### production-backup
- ✅ Required reviewers: 1+
- ✅ Wait timer: 0 minutes
- ✅ Deployment branches: `main`, `master` only
- ✅ No self-review by workflow author

---

## Workflow Dispatch Configuration

The workflow uses `workflow_dispatch` with these inputs:

```yaml
on:
  workflow_dispatch:
    inputs:
      gate:
        description: "Which gate to execute"
        required: true
        type: choice
        options:
          - "gate1-atomicity"
          - "gate2-identity"
          - "gate3-dependencies"
          - "gate4-backup"
          - "all"
      confirm_environment:
        description: "Confirm this runs against PRODUCTION Neon database"
        required: true
        type: boolean
```

---

## Branch Protection for Deployment

The workflow uses `workflow_dispatch` trigger, so it can only be triggered manually.

**Branch Restriction:** The workflow file must exist on the `main` branch to be manually dispatched.

**Branch Protection:** `main` branch should have:
- ✅ Require pull request reviews
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators
- ✅ No force pushes
- ✅ No deletions

---

## Secret Management

### Production Secrets (Never in Repository)
| Secret | Environment | Source |
|--------|-------------|--------|
| `SCHOLARZONE_DATABASE_URL_RO` | GitHub Actions Secret → `production-readonly` | Neon Dashboard → Connection String (read-only role) |
| `SCHOLARZONE_DATABASE_URL_BACKUP` | `production-backup` | Neon Dashboard → Connection String (backup role) |
| `EXPECTED_NEON_PROJECT_ID` | `production-readonly` | Neon Console → Project Settings → Project ID |
| `EXPECTED_NEON_BRANCH_ID` | `production-readonly` | Neon Console → Branches → main → Branch ID |
| `EXPECTED_NEON_BRANCH_NAME` | `production-readonly` | `main` (or actual branch name) |
| `EXPECTED_DATABASE_NAME` | `production-readonly` | Database name (e.g., `scholarzone`) |
| `SCHOLARZONE_DATABASE_URL_BACKUP` | `production-backup` | Neon Dashboard → Connection String (backup role) |
| `GPG_RECIPIENT` | `production-backup` | GPG Key ID (e.g., `backup@scholarzone.org`) |
| `BACKUP_ENCRYPTION_PASSPHRASE` | `production-backup` | High-entropy passphrase from password manager |
| `BACKUP_STORAGE_BUCKET` | `production-backup` | S3/GCS bucket name (optional) |
| `BACKUP_STORAGE_CREDENTIALS` | `production-backup` | AWS/GCP credentials for backup storage |

---

## GPG Key Management

### Generating Backup GPG Key
```bash
# Generate key (run once, store private key securely)
gpg --full-generate-key
# Key type: RSA and RSA
# Key size: 4096
# Expiration: 2y (or never)
# Name: ScholarZone Backup
# Email: backup@scholarzone.org

# Export public key
gpg --armor --export backup@scholarzone.org > backup.pub

# Export private key (store securely OFFLINE)
gpg --armor --export-secret-keys backup@scholarzone.org > backup.sec

# Get key ID
gpg --list-keys backup@scholarzone.org
# Use the key ID (e.g., ABCDEF123456) as GPG_RECIPIENT
```

### GPG Key Distribution
- **Public key:** Commit to repository or distribute to team
- **Private key:** Store in 1Password/LastPass/Bitwarden + offline backup
- **GitHub Actions:** Use `GPG_RECIPIENT` secret (key ID only)

---

## GitHub Actions Workflow Permissions

```yaml
permissions:
  contents: read
  actions: read
  checks: write
  id-token: write  # For OIDC if needed
```

**Job-specific permissions:**
- Gate 2 & 3: `contents: read`, `id-token: write`
- Gate 4: `contents: read`
- Summary: `contents: read`

---

## Branch Protection for Deployment

The workflow uses `workflow_dispatch` (manual trigger), so:

**Branch Protection for `main`:**
- ✅ Require pull request reviews (1+)
- ✅ Require status checks to pass
- ✅ Require branches to be up to date
- ✅ Include administrators
- ✅ No force pushes
- ✅ No deletions

**Branch Protection for `fix/production-expired-cycle-purge`:**
- ✅ Same as main
- ✅ This is the feature branch for the purge PR

---

## Verification Checklist Before Running

- [ ] `production-readonly` environment exists with required reviewers
- [ ] `production-backup` environment exists with required reviewers
- [ ] All 10 secrets configured in correct environments
- [ ] Branch protection rules active on `main`
- [ ] Workflow file on `main` branch (or merged PR)
- [ ] Neon PITR verified: `history_retention_seconds >= 604800`
- [ ] GPG key generated and recipient configured
- [ ] GPG private key stored in secure key service
- [ ] GPG recipient fingerprint verified
- [ ] `EXPECTED_NEON_PROJECT_ID` matches actual Neon project
- [ ] `EXPECTED_NEON_BRANCH_ID` matches actual Neon branch
- [ ] `EXPECTED_DATABASE_NAME` matches actual database name
- [ ] Workflow file on `main` branch (or merged PR)
- [ ] PR #67 open with preflight workflow

---

## Verification Commands

```bash
# Verify Neon project ID
gh api repos/gopal735/ScholarZone/secrets/SCHOLARZONE_DATABASE_URL_RO --jq '.name'

# Check environment exists
gh api repos/gopal735/ScholarZone/environments/production-readonly
gh api repos/gopal735/ScholarZone/environments/production-backup

# Check branch protection
gh api repos/gopal735/ScholarZone/branches/main/protection

# Test workflow dispatch (dry run)
gh workflow run production-purge-preflight.yml --ref fix/production-expired-cycle-purge \
  -f gate=all -f confirm_environment=true
```

---

## Security Notes

1. **Never commit secrets** to repository
2. **Use GitHub Environments** for secret isolation
3. **Rotate credentials** after purge if needed
4. **Monitor** workflow runs for unauthorized access
5. **Audit** environment access quarterly
6. **Backup GPG private key** offline in secure location
7. **Rotate** database passwords annually
8. **Review** environment access quarterly