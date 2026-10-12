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
| `scholarzone-<utc-timestamp>.manifest.json` | Timestamp, ciphertext SHA-256 and size, plaintext size and digest, the source's *identity* (dialect and host only — never a connection string), the **source class** decided by host policy, the **production authorization** that admitted it, the projected monthly transfer, and the outcome. |

The archive inside the ciphertext is the **PostgreSQL custom-format dump
itself** -- `--format=custom`, which libpq compresses -- with no outer gzip
layer. There is nothing to unwrap, and the SHA-256 in the manifest is the
digest of the very bytes `pg_restore` reads. (An earlier revision of the
*drill* tool wrapped its dump in gzip and handed the resulting file straight
to `pg_restore`, which refuses it; the tool now fails on that input instead
of producing a manifest that claims a restore nobody performed, and
`scripts/restore_drill.py` asserts the refusal against a real PostgreSQL.)

The decryption passphrase lives only in the repository secret
`SZ_BACKUP_PASSPHRASE`. It is not in the artifact, not in the manifest, and not
in the logs.

## Source classification and authorization

A source is classified by *host policy*, never by a substring in its name:
the audited production host contains no "prod" and the old substring guard
admitted it. The hosts this component knows to be production are named
explicitly; a source on one of them needs a second, separate fact -- an
authorization record:

| Variable | Meaning |
| --- | --- |
| `SZ_BACKUP_SOURCE_URL` | The source connection string. In a repository secret only. |
| `SZ_BACKUP_ALLOWED_HOSTS` | Comma-separated hostnames a backup may **read** and a restore may **write**. Default-deny: an unlisted host is refused. |
| `SZ_BACKUP_PRODUCTION_AUTHORIZATION` | The operator's audit reference (who approved a production backup and when). **Required** when the source is a known production host; meaningless for a non-production source. Its value is written to the manifest, the connection string never is. |

An unknown or misconfigured source fails closed. A production source that
is allow-listed but unauthorized is refused with "not authorized", which is
a different message from "not permitted" on purpose.

## What "verified" means

Three claims, deliberately separate:

* **round-trip verified** -- the ciphertext decrypts back to the plaintext.
  Always true on a successful run.
* **restore_verified** -- the dump was *restored* into a non-production
  target during the same run (`--verify-restore-into`), and the manifest
  carries the target's identity and table row counts. A production source
  *requires* this: an unproven production backup is refused, not written.
* **drill proven** -- the whole procedure ran against disposable databases,
  including the negative cases (`scripts/restore_drill.py`).

Only the second and third say anything about whether the backup can be
brought back. An artifact with `restore_verified: false` is a decryptable
backup, and must not satisfy a migration or deletion gate.

## Retention, honestly

The artifact is stored as a **14-day build artifact**. That is a recovery
window, not a retention policy: after two weeks the artifact is gone and
what remains is the *ability* to make a new one. The passphrase lives only
in the repository secret, and the two are not stored together -- the
artifact is reachable by URL within the workflow run, the secret is not
part of it. If independent out-of-band storage were required, it would need
either a paid plan or the operator downloading the artifact by hand; this
repository will not enable either automatically.

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
SZ_BACKUP_SOURCE_URL    The PostgreSQL connection string to back up. A production source additionally requires SZ_BACKUP_PRODUCTION_AUTHORIZATION.
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
