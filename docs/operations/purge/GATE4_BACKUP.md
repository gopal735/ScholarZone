# GATE 4: Production Backup & Verification

## Overview
Gate 4 creates a complete, encrypted pg_dump backup of the production database, verifies its integrity, and validates restore capability.

## Implementation
**Script**: `.github/scripts/gate4_backup.py`

## Required Environment Variables
- `SCHOLARZONE_DATABASE_URL_BACKUP` - Backup role connection string
- `GPG_RECIPIENT` - GPG key ID for encryption
- `BACKUP_ENCRYPTION_PASSPHRASE` - Optional symmetric encryption passphrase

## Backup Process

### 1. pg_dump Backup
```bash
pg_dump --format=custom --compress=9 --no-owner --no-privileges --file=backup.dump
```

### 2. Encryption
```bash
gpg --trust-model always --encrypt --recipient $GPG_RECIPIENT --output backup.dump.gpg backup.dump
```

### 3. Verification
- `pg_restore --list` - Verify backup structure
- `pg_restore --data-only --table=scholarships` - Verify data rows
- SHA256 checksum of encrypted file

### 4. Encryption
```bash
gpg --trust-model always --encrypt --recipient $GPG_RECIPIENT --output backup.dump.gpg backup.dump
```

### 5. Cleanup
- Remove unencrypted `.dump` file
- Keep only `.gpg` and `.sha256` files

## Restore Test
1. Decrypt: `gpg --decrypt --output backup.dump backup.dump.gpg`
2. Create test database: `createdb restore_test_xxx`
3. Restore: `pg_restore --dbname=restore_db --no-owner --no-privileges backup.dump`
4. Verify:
   - Schema matches
   - Table counts match
   - 34 target IDs present
   - Constraints, indexes, sequences intact

## Output
Produces `gate4_result.json`:
```json
{
  "backup_file": "backup_production_pre_purge_20261103_120000.dump.gpg",
  "backup_size": "15M",
  "checksum_file": "backup.dump.gpg.sha256",
  "pitr_verified": false,
  "backup_verified": true,
  "checksum_verified": true,
  "restore_test_passed": true,
  "encryption": "GPG",
  "gpg_recipient": "backup@scholarzone.org",
  "timestamp": "2026-11-03T12:00:00Z"
}
```

## Artifacts
Uploaded to GitHub Actions (30-day retention):
- `gate4_result.json`
- `backup.dump.gpg.sha256`
- **NOT uploaded**: Raw `.dump`, decrypted files, private keys

## PITR Verification
**Manual step required:**
1. Go to Neon Console > Project > Branches > main > Point-in-Time Recovery
2. Verify `history_retention_seconds >= 604800` (7 days)
3. Record `history_retention_seconds` value
3. Document recovery window

## Restore Test Requirements
- Isolated PostgreSQL 16 service container
- Disposable test database
- Decrypt → pg_restore → verify → cleanup
- Compare source vs restored manifests
- Verify all 34 target IDs present

## Artifacts
**Uploaded (encrypted only):**
- `backup.dump.gpg` (encrypted)
- `backup.dump.gpg.sha256`

**Never uploaded:**
- Raw `.dump` files
- Decrypted files
- Private keys
- Passphrases

## Required Secrets
- `SCHOLARZONE_DATABASE_URL_BACKUP` - Backup role connection
- `GPG_RECIPIENT` - GPG key ID for encryption
- `BACKUP_ENCRYPTION_PASSPHRASE` - Optional symmetric encryption