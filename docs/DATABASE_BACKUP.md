# Encrypted database backup

The repository had no database backup. That absence was recorded by
`backend/app/services/retention_recovery.py` and it held the hard-delete release
gate: nothing could be authorised as recoverable when nothing had ever been
brought back. This is the capability that closes it.

Everything here runs on free resources. There is no new service, no plan change,
and no paid dependency.

## What it produces

One artifact per run, in a build artifact store:

| File | Contents |
| --- | --- |
| `scholarzone-<utc-timestamp>.szbak` | The encrypted dump. A short text header naming the cipher and KDF, then raw AES-256-GCM ciphertext. |
| `scholarzone-<utc-timestamp>.manifest.json` | Timestamp, ciphertext SHA-256 and size, plaintext size and digest, the source's *identity* (dialect only — never a connection string), the projected monthly transfer, and the outcome. |

The decryption passphrase lives only in the repository secret
`SZ_BACKUP_PASSPHRASE`. It is not in the artifact, not in the manifest, and not
in the logs.

## How it refuses

The script fails closed in every case where writing anything would be worse
than writing nothing. These are asserted by tests, not just documented:

- **No source URL.** `run_backup` does not guess or fall back to the
  application's connection.
- **No passphrase.** An unusable backup is refused rather than written.
- **No encryption backend.** With neither `openssl` nor `cryptography`
  available, there is no backup at all. There is no plaintext fallback.
- **A source that looks like production.** A scheduled backup that competes
  with the application for the free-tier transfer budget takes the site down to
  save the database.
- **A projected transfer over budget.** The dump size is multiplied by runs per
  month and doubled again (storing and downloading both count); over the budget
  the run stops before dumping.
- **A round-trip that does not match.** The ciphertext is decrypted and compared
  with the plaintext before the plaintext is discarded. An unverifiable backup is
  refused.

## Enabling it

Add two repository secrets. Nothing is requested in chat, and nothing is stored
in the repository:

```
SZ_BACKUP_SOURCE_URL    A NON-production PostgreSQL connection string.
                        A production-looking URL is refused by design.
SZ_BACKUP_PASSPHRASE   The encryption passphrase. Nowhere else.
```

Then either run **Actions → Database Backup (encrypted) → Run workflow**, or
wait for the Sunday 03:00 UTC schedule.

If the secrets are absent, the workflow reports "Backup not run" and exits
successfully. That is deliberate: an unconsumed capability is not a broken
build, and making it fail would train people to ignore it.

## Transfer budget

The schedule is weekly — 4 runs per month. The script projects the monthly
transfer before dumping and fails the run if it exceeds the budget (default
512 MiB, overridable from `workflow_dispatch`).

The projection is doubled on purpose. An artifact upload and one later download
are two transfers, and counting only the upload would make the budget look safer
than it is. With a dump in the low hundreds of MB, four weekly runs stay well
inside the fraction of a free-tier allowance that leaves the application room.

## Restoring

```bash
# 1. Download the artifact from the run, and note the passphrase location.
# 2. Create an isolated destination database. This repository's free-tier
#    posture forbids restoring into production, and the script refuses it.
export SZ_RESTORE_DEST_URL="postgresql://user:pass@isolated-host/recovery"
export SZ_BACKUP_PASSPHRASE="the passphrase from the secret"

cd backend
python scripts/pg_restore.py \
  --artefact ../backup-out/scholarzone-<timestamp>.szbak
```

It decrypts, checks the plaintext digest the artifact recorded, runs
`pg_restore` into the destination, and then verifies the restored database by
reading it back. The evidence it prints carries row counts, the tables present,
and the publicly visible scholarship count under the same predicate the
catalogue uses.

`backend/scripts/verify_recovery_path.py` is the release-gate's own check and
remains the authority on whether recovery is proven. This script is what feeds
it: it refuses a SQLite destination for the same reason that one does — a
round-trip through SQLite is not evidence about a PostgreSQL restore.

## Current status

**Not yet executed against a real PostgreSQL database.** No backup has been
taken, because the only reachable PostgreSQL is the production project, which
is over its free-tier quota and which this workflow refuses by design. What is
executed and passing is everything except `pg_dump` itself: the script's
orchestration, both encryption backends, the refusals, the framing, the digest
verification, the manifest, the plaintext removal, and the workflow's safety
properties — 46 tests, all against non-production data.

Taking the first real backup is a two-step operation once a non-production
source exists:

1. Set the two secrets to a non-production database.
2. Run the workflow, and record the artifact name as the first known-good
   backup.

That first artifact, once restored and verified by `pg_restore.py`, is what
turns "a backup exists" into evidence that recovery works — which is the claim
`verify_recovery_path.py` requires.
