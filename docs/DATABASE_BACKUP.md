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
- **No hostname allow-list, or one that names nothing.** A source must be
  named in `SZ_BACKUP_ALLOWED_HOSTS` before it may be read. Default-deny: an
  unlisted host is not a host somebody approved, and an empty, missing, or
  malformed list refuses the run rather than permitting it.
- **A known production endpoint, whatever the allow-list says.** The audit
  found that a production Neon connection string -
  `ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech` - contains no
  "prod" substring, so the guard that used to look for one admitted the exact
  host it existed to exclude. It is now named in a deny-list that beats
  configuration: adding it to the allow-list changes nothing.
- **A projected transfer over budget.** The dump size is multiplied by runs per
  month and doubled again (storing and downloading both count); over the budget
  the run stops before the artifact is written.
- **A round-trip that does not match.** The ciphertext is decrypted and compared
  with the plaintext before the plaintext is discarded. An unverifiable backup is
  refused.

## Enabling it

Add two repository secrets and one repository variable. Nothing is requested in
chat, and nothing is stored in the repository:

```
SZ_BACKUP_SOURCE_URL    A NON-production PostgreSQL connection string.
SZ_BACKUP_PASSPHRASE   The encryption passphrase. Nowhere else.
SZ_BACKUP_ALLOWED_HOSTS  Comma-separated hostnames the backup may read.
                         Default-deny: the source host must be named here,
                         and the known production endpoints are refused
                         whatever this says.
```

`SZ_BACKUP_ALLOWED_HOSTS` must name a host that exists and holds the data.
Production is refused, and so is an empty recovery project: a backup of a
database with no rows is an artifact that looks like recovery and proves
nothing.

Then either run **Actions → Database Backup (encrypted) → Run workflow**, or
wait for the Sunday 03:00 UTC schedule.

If any of the three are absent, the workflow reports "Backup not run" and exits
successfully. That is deliberate: an unconsumed capability is not a broken
build, and making it fail would train people to ignore it.

## Transfer budget

The schedule is weekly — 4 runs per month. The script projects the monthly
transfer before uploading anything and fails the run if it exceeds the budget.

The budget is **configuration, not a caller's choice**. It lives in the
repository variable `SZ_BACKUP_MAX_MONTHLY_MIB`, changeable only by someone with
write access, with a built-in default of 512 MiB. There is no `workflow_dispatch`
input for it and no script argument that sets it: the one check standing between
a backup and exhausting the free-tier allowance is not something a person who
can press the button gets to change for a single run. A value that is missing
uses the default; one that is unparseable, non-positive, or implausibly large
refuses the run rather than being ignored, because a typo in the budget must not
be able to switch the budget off.

The projection is doubled on purpose. An artifact upload and one later download
are two transfers, and counting only the upload would make the budget look safer
than it is. With a dump in the low hundreds of MB, four weekly runs stay well
inside the fraction of a free-tier allowance that leaves the application room.

**What the projection is not.** `projected_monthly_transfer_mib` is a projection:
measured dump size x runs per month x 2. It is not a measured `pg_dump` size over
time, and it is not a verified monthly usage total. It does not know how much of
the allowance the application itself consumes, nor whether anyone downloads the
artifact. It is a ceiling on what this backup could plausibly add, which is the
only claim it can honestly make.

## Restoring

```bash
# 1. Download the artifact from the run, and note the passphrase location.
# 2. Create an isolated destination database. This repository's free-tier
#    posture forbids restoring into production, and the script refuses it.
#    The destination is checked against the same allow-list as the backup
#    source, so a host that is not named there is refused rather than
#    silently accepted, and the known production endpoints are refused
#    whatever it says.
export SZ_BACKUP_ALLOWED_HOSTS="the destination host"
export SZ_RESTORE_DEST_URL="postgresql://user:pass@isolated-host/recovery"
export SZ_BACKUP_PASSPHRASE="the passphrase from the secret"

cd backend
python scripts/pg_restore.py \
  --artefact ../backup-out/scholarzone-<timestamp>.szbak \
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
properties — 98 tests, all against non-production data.

Those tests include the two the security audit asked for, and both are asserted
rather than assumed:

- the production endpoint `ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech`
  is refused, even when it is named in the allow-list, while an explicitly
  approved non-production host is accepted;
- the transfer budget cannot be supplied by a caller — not by argument, and not
  by a `workflow_dispatch` input, because neither exists any more — and a
  budget configuration that is missing, malformed, non-positive, or absurd
  fails closed instead of disabling the check.

Taking the first real backup is a two-step operation once a non-production
source exists:

1. Set the two secrets and the allow-list variable to a non-production database.
2. Run the workflow, and record the artifact name as the first known-good
   backup.

That first artifact, once restored and verified by `pg_restore.py`, is what
turns "a backup exists" into evidence that recovery works — which is the claim
`verify_recovery_path.py` requires.
