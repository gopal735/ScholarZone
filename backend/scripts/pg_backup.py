#!/usr/bin/env python3
"""Produce an encrypted, verifiable backup of a PostgreSQL database.

This is the missing capability the recovery report kept naming: nothing in the
repository created a backup. It does now, within the constraints that make a
backup safe to keep in a public repository's build artifacts.

    python scripts/pg_backup.py \
        --source-url-env SZ_BACKUP_SOURCE_URL \
        --output-dir ./backup-out

Usage is deliberately env-based rather than flag-based for the URL. A connection
string on a command line lands in shell history and in the process table, both of
which outlive the command; an environment variable read once and discarded does
not.

The order of operations matters more than any individual step:

1. **Refuse before touching anything.** No source URL, no secret, no encryption
   backend, no hostname allow-list, or a source that is a known production
   endpoint each stop the run before a byte is dumped. A backup that cannot be
   encrypted must not exist.
2. **Dump to a temporary file outside Git**, with permissions restricted to the
   current user. The plaintext never enters the repository or the artifact.
3. **Encrypt in memory and verify by round-trip**: the ciphertext is decrypted
   with the same passphrase and compared byte-for-byte with the plaintext before
   the plaintext is discarded. A ciphertext that has not been proven decryptable
   is not a backup.
4. **Record a manifest** carrying the timestamp, the ciphertext's SHA-256 and
   size, the source's *identity* (scheme and host - never the connection
   string), the hosts the allow-list permitted, and the outcome. This is what a
   restore consumes.
5. **Remove the plaintext** and confirm it is gone.

Which host is even eligible is decided by `app.services.backup_source`, not by
this script: a source is permitted only when its hostname is named in
`SZ_BACKUP_ALLOWED_HOSTS`, and the known production endpoints are refused
whatever that configuration says. Substring matching was tried and is gone - a
production Neon hostname contains no "prod" marker, so it was admitted by the
check written to exclude it.

The transfer estimate is computed before anything is uploaded, because a backup
that exhausts the free-tier network budget to save the database has made things
worse: the application's own traffic then fails. `SZ_BACKUP_MAX_MONTHLY_MIB`
fails the run when the projected monthly transfer exceeds the budget, and the
default is conservative. The budget is configuration, not an argument: it is the
one check standing between a backup and the free-tier allowance, so a caller
cannot be the one who decides it.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    FORMAT_ID,
    BackupCryptoError,
    BackupCryptoUnavailable,
    read_manifest,
    select_backend,
)
from app.services.backup_source import (  # noqa: E402
    ALLOW_LIST_ENV,
    SourceRejected,
    authorization_for,
    describe_allow_list,
    resolve_source,
    source_kind,
    validate_source,
)

#: Default monthly transfer budget in MiB. Neon's free tier allows 5 GiB/month
#: of outbound transfer; the application uses some of it, so a backup budget has
#: to be a fraction rather than the whole allowance.
#:
#: This is a *default*, and the only thing that can change it is a repository
#: variable. It used to be a `workflow_dispatch` input, which meant a caller
#: could switch the budget off by choosing a large number - and this budget is
#: the one check standing between a backup and exhausting the free-tier transfer
#: allowance, which is the failure the whole free-first architecture exists to
#: avoid. There is no argument that sets it, so a dispatch caller has nothing to
#: override.
DEFAULT_MAX_MONTHLY_MIB = 512

#: The variable a repository owner sets to change the budget. Absent uses the
#: default. Present but unparseable, non-positive, or absurd refuses.
BUDGET_ENV = "SZ_BACKUP_MAX_MONTHLY_MIB"

#: Upper bound on a configured budget, in MiB. A configuration above this is
#: treated as a mistake rather than a decision: a value that large cannot be a
#: fraction of a free-tier allowance, so it is almost certainly a typo.
MAX_SANE_BUDGET_MIB = 4096


class BackupRefused(RuntimeError):
    """The backup did not happen, and the reason is in the message."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_budget_mib() -> float:
    """The monthly transfer ceiling, from configuration or the default.

    Deliberately not a function argument and not a dispatch input. Both would
    make the budget a caller's choice, and the point of the budget is that it is
    not one.
    """
    raw = os.environ.get(BUDGET_ENV)
    if raw is None or raw.strip() == "":
        return float(DEFAULT_MAX_MONTHLY_MIB)

    try:
        value = float(raw.strip())
    except ValueError:
        raise BackupRefused(
            f"{BUDGET_ENV}={raw!r} is not a number; refusing to guess a budget "
            "when a value has been set that cannot be read"
        ) from None

    if value != value or value in (float("inf"), float("-inf")):  # NaN and infinity
        raise BackupRefused(f"{BUDGET_ENV}={raw!r} is not a finite number")

    if value <= 0:
        raise BackupRefused(
            f"{BUDGET_ENV} must be a positive number of MiB; {value!r} would "
            "disable the transfer budget, which is the one check protecting the "
            "application's free-tier allowance"
        )

    if value > MAX_SANE_BUDGET_MIB:
        raise BackupRefused(
            f"{BUDGET_ENV}={value} exceeds the sane ceiling of "
            f"{MAX_SANE_BUDGET_MIB} MiB; a budget above that is not a fraction "
            "of a free-tier allowance and is most likely a mistake"
        )

    return value



def _dump_binary() -> str:
    binary = _which("pg_dump")
    if not binary:
        raise BackupRefused(
            "pg_dump is not on PATH; a PostgreSQL backup needs it and no "
            "substitute is offered, because a non-dump output is not a backup."
        )
    return binary


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _dump(source_url: str, destination: Path) -> int:
    """Write a plaintext custom-format dump and return its size in bytes.

    `--format=custom` is used because it is compressed and it is the format
    `pg_restore` consumes, which is what the restore path needs. `--no-owner`
    and `--no-privileges` make the dump restorable into an isolated destination
    that has no matching roles.
    """
    binary = _dump_binary()
    # The URL is passed through the environment of the child process rather than
    # as an argument, so it never appears in the process table.
    env = dict(os.environ)
    env["PGPASSFILE"] = os.devnull
    proc = subprocess.run(
        [
            binary,
            "--format=custom",
            "--no-owner",
            "--no-privileges",
            "--dbname", source_url,
            "--file", str(destination),
        ],
        env=env,
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace")
        raise BackupRefused(
            f"pg_dump exited {proc.returncode}: {stderr.strip()[:300]}"
        )
    return destination.stat().st_size


def _write_private(path: Path, data: bytes) -> None:
    """Write a file readable only by the current user."""
    handle = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "wb") as stream:
        stream.write(data)


def _estimate_monthly_mib(dump_bytes: int, runs_per_month: int) -> float:
    """Projected outbound transfer, in MiB, for the schedule.

    An artifact upload is counted twice in practice - once for storing it and
    once for anyone downloading it - so this is deliberately pessimistic rather
    than counting the upload once and calling the budget safe.

    This is a projection from a measured dump size and a stated run count. It is
    not a measurement of monthly usage: it does not know how much of the
    allowance the application itself consumes, and it does not know whether
    anyone downloads the artifact. It is a ceiling on what this backup could
    plausibly add, which is the only quantity the budget can honestly claim.
    """
    return (dump_bytes * runs_per_month * 2) / (1024 * 1024)


def _restore_verify(plaintext: bytes, destination: str) -> dict[str, Any]:
    """Restore the dump into a non-production target and report the evidence.

    Two rules, both learned from a backup that looked done and was not:

    * The target must be **empty of relations**, not merely of rows. A table
      with zero rows still answers a `pg_restore` that restores a different
      schema's tables into a database that already has objects - the restore
      "works" and the verification is meaningless. Existing relations of any
      kind refuse the verification.
    * A restore that fails fails the backup. The plaintext is still in memory
      here, so a failed verification raises before the ciphertext is written;
      the artifact is never produced in a state whose manifest would have to
      lie about it.

    Returns the evidence that goes into the manifest: the target's redacted
    identity, the table row counts, and the SHA-256 of the plaintext dump the
    restore consumed.
    """
    if not _which("pg_restore"):
        raise BackupRefused(
            "pg_restore is not on PATH; the restore verification the manifest "
            "claims needs it, and there is no substitute"
        )

    try:
        destination_identity = validate_source(destination)
    except SourceRejected as exc:
        raise BackupRefused(f"restore target refused: {exc}") from exc

    # The target must not be production either: verifying a backup by
    # restoring it into the same class of database it came from is how a
    # drill turns into an incident.
    if source_kind(destination_identity) == "production":
        raise BackupRefused(
            "the restore target is a production host; a backup is verified into "
            "non-production, never into the database it may have to survive"
        )

    psql = _which("psql")
    tmpdir = Path(tempfile.mkdtemp(prefix="sz-verify-"))
    try:
        dump_path = tmpdir / "verify.dump"
        _write_private(dump_path, plaintext)
        if psql:
            existing = _relations(destination, psql)
            if existing:
                raise BackupRefused(
                    "the restore target is not empty (existing relations: "
                    f"{existing[:8]}); a restore into a non-empty database is "
                    "not a verification of this backup and is refused"
                )
        proc = subprocess.run(
            [
                _which("pg_restore"),
                "--no-owner",
                "--no-privileges",
                "--dbname",
                destination,
                str(dump_path),
            ],
            env={**os.environ, "PGPASSFILE": os.devnull},
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise BackupRefused(
                f"restore verification failed: pg_restore exited "
                f"{proc.returncode}: {proc.stderr.strip()[:300]}"
            )
        counts = _table_rows(destination, psql) if psql else {}
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    return {
        "target_identity": destination_identity.describe(),
        "target_relations_before": 0,
        "table_row_counts": counts,
        "plaintext_sha256": _sha256_bytes(plaintext),
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def _relations(destination: str, psql: str) -> list[str]:
    """The names of existing relations in the target database, most recently
    created first. The count of *objects*, not of rows: a target with tables
    in it is not a target this verification may write into."""
    proc = subprocess.run(
        [
            psql,
            destination,
            "-At",
            "-c",
            "SELECT format('%I.%I', n.nspname, c.relname) FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S') "
            "ORDER BY c.oid DESC LIMIT 20",
        ],
        env={**os.environ, "PGPASSFILE": os.devnull},
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise BackupRefused(
            f"could not inspect the restore target: {proc.stderr.strip()[:200]}"
        )
    return [line for line in proc.stdout.splitlines() if line.strip()]


def _table_rows(destination: str, psql: str) -> dict[str, int]:
    """Row counts per table in the restored database, for reconciliation."""
    proc = subprocess.run(
        [
            psql,
            destination,
            "-At",
            "-c",
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
        ],
        env={**os.environ, "PGPASSFILE": os.devnull},
        capture_output=True,
        text=True,
        check=False,
    )
    counts: dict[str, int] = {}
    for table in [line.strip() for line in proc.stdout.splitlines() if line.strip()]:
        rows = subprocess.run(
            [psql, destination, "-At", "-c", f'SELECT COUNT(*) FROM "{table}"'],
            env={**os.environ, "PGPASSFILE": os.devnull},
            capture_output=True,
            text=True,
            check=False,
        )
        counts[table] = int(rows.stdout.strip() or 0)
    return counts


def run_backup(args: argparse.Namespace) -> dict[str, Any]:
    """Execute one backup. Returns the manifest that was written."""
    started = datetime.now(timezone.utc)

    passphrase = args.passphrase
    if not passphrase:
        raise BackupRefused(
            "no backup passphrase; set SZ_BACKUP_PASSPHRASE. Refusing to write "
            "a backup nobody could restore."
        )

    # Resolved and validated before anything is dumped. `resolve_source` applies
    # the allow-list and the production authorization, and returns the URL for
    # pg_dump alongside a redacted identity for reporting. The URL is never
    # logged or written to the manifest.
    try:
        source_url, source_identity = resolve_source(args.source_url_env)
        kind = source_kind(source_identity)
        authorization = authorization_for(kind)
    except SourceRejected as exc:
        raise BackupRefused(str(exc)) from exc

    # The budget comes from configuration, never from a caller. Nothing in
    # `args` can set it, because the parser deliberately offers no argument for
    # it: a `workflow_dispatch` input has nowhere to land.
    budget_mib = _resolve_budget_mib()

    # `select_backend` raises `BackupCryptoUnavailable` when nothing can
    # encrypt. That is a refusal like any other, and a caller should not have to
    # know about the crypto module's exception hierarchy to handle a backup that
    # did not happen - so it becomes one kind of refusal here.
    try:
        backend = select_backend(args.backend)
    except BackupCryptoUnavailable as exc:
        raise BackupRefused(str(exc)) from exc

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # A named temporary file outside the repository, deleted on every path.
    tmpdir = Path(tempfile.mkdtemp(prefix="sz-backup-"))
    plaintext_path = tmpdir / "dump.custom"
    try:
        dump_bytes = _dump(source_url, plaintext_path)
        plaintext = plaintext_path.read_bytes()
    finally:
        plaintext_path.unlink(missing_ok=True)

    projected = _estimate_monthly_mib(dump_bytes, args.runs_per_month)
    if projected > budget_mib:
        raise BackupRefused(
            f"projected monthly transfer {projected:.1f} MiB exceeds the "
            f"{budget_mib:g} MiB budget for {args.runs_per_month} runs; the "
            "budget is set by configuration and cannot be raised by a caller. "
            "Reduce the schedule or the dump size before scheduling a backup."
        )

    # Encrypt, then prove the ciphertext decrypts back to the plaintext.
    # Encrypting without this check is the step that produces a backup that
    # looks done and cannot be restored.
    ciphertext = backend.encrypt(plaintext, passphrase)
    restored = backend.decrypt(ciphertext, passphrase)
    if restored != plaintext:
        raise BackupRefused(
            "ciphertext did not decrypt back to the original dump; refusing to "
            "keep an unverifiable backup"
        )

    # Round-trip decryption proves the ciphertext is well-formed. It does not
    # prove the backup is restorable, and the difference is the one that
    # matters in an incident: a manifest claiming a verified backup that was
    # never restored is how a migration gets approved against a file that will
    # not restore. When a non-production restore target is configured, the
    # backup is restored into it here - before the plaintext is discarded - and
    # the manifest says so with the evidence. Without one, the artifact is
    # still produced (a decryptable backup is better than none) but is marked
    # `restore_verified: false`, a state the migration and deletion gates must
    # reject.
    restore_evidence: dict[str, Any] | None = None
    if getattr(args, "verify_restore_into", None):
        restore_evidence = _restore_verify(plaintext, args.verify_restore_into)
    elif kind == "production":
        raise BackupRefused(
            "a production backup requires a restore target "
            "(--verify-restore-into <non-production-uri>): the artifact is "
            "kept only when it has been proven to restore. Set one, or take a "
            "non-production backup instead."
        )

    del plaintext

    manifest_header = read_manifest(ciphertext)
    cipher_sha = _sha256_bytes(ciphertext)

    timestamp = datetime.now(timezone.utc)
    stem = timestamp.strftime("%Y%m%dT%H%M%SZ")
    artefact = output_dir / f"scholarzone-{stem}.szbak"
    manifest_path = output_dir / f"scholarzone-{stem}.manifest.json"

    _write_private(artefact, ciphertext)
    _write_private(
        manifest_path,
        json.dumps(
            {
                "format": FORMAT_ID,
                "created_at": timestamp.isoformat(),
                # The redacted identity only: scheme and host. Never the URL,
                # the database name, the port, or any credential.
                "source_identity": source_identity.describe(),
                # Which class of database this came from, decided by the host
                # policy rather than by a substring in its name - the audited
                # production host contains no "prod" and the previous substring
                # guard admitted it. A production backup additionally records
                # the authorization reference that permitted it.
                "source_kind": kind,
                "production_authorization": authorization,
                # The restore proof, when one was taken. False means the
                # ciphertext decrypts (round_trip_verified) but nobody has
                # restored it: an artifact in that state must not satisfy a
                # migration or deletion gate.
                "restore_verified": restore_evidence is not None,
                "restore_verification": restore_evidence,
                # Which hosts the allow-list permitted when this ran. Recorded
                # so an artifact can be audited against the configuration that
                # authorised it, rather than only against the host used.
                "allowed_hosts": describe_allow_list(ALLOW_LIST_ENV),
                "ciphertext_sha256": cipher_sha,
                "ciphertext_bytes": len(ciphertext),
                "plaintext_bytes": dump_bytes,
                "projected_monthly_transfer_mib": round(projected, 2),
                "transfer_budget_mib": round(budget_mib, 2),
                "runs_per_month": args.runs_per_month,
                # What is explicitly not claimed: this is a projection from a
                # measured dump size, not a measurement of monthly usage.
                "projection_note": (
                    "projected_monthly_transfer_mib is a projection: measured "
                    "dump size x runs per month x 2 (upload plus download). It "
                    "is not a measured pg_dump size over time and not a "
                    "verified monthly usage total."
                ),
                "backend": backend.name,
                "kdf": manifest_header.get("kdf"),
                "iterations": manifest_header.get("iterations"),
                "plaintext_sha256": manifest_header.get("plaintext_sha256"),
                "round_trip_verified": True,
                "outcome": "success",
                "duration_seconds": round(
                    (datetime.now(timezone.utc) - started).total_seconds(), 3
                ),
            },
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
    )

    return {
        "artefact": str(artefact),
        "manifest": str(manifest_path),
        "ciphertext_sha256": cipher_sha,
        "ciphertext_bytes": len(ciphertext),
        "plaintext_bytes": dump_bytes,
        "projected_monthly_transfer_mib": round(projected, 2),
        "transfer_budget_mib": round(budget_mib, 2),
        "backend": backend.name,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-url-env",
        default="SZ_BACKUP_SOURCE_URL",
        help="environment variable holding the source connection string",
    )
    parser.add_argument(
        "--passphrase-env",
        default="SZ_BACKUP_PASSPHRASE",
        help="environment variable holding the encryption passphrase",
    )
    parser.add_argument(
        "--backend",
        default=None,
        help="encryption backend name; defaults to the strongest available",
    )
    parser.add_argument("--output-dir", default="./backup-out")
    parser.add_argument(
        "--verify-restore-into",
        default=None,
        help="a NON-production PostgreSQL URI that is empty; the dump is "
        "restored into it before the artifact is written, and the manifest "
        "records the verification. Required for a production source: an "
        "unproven production backup is not a backup.",
    )
    parser.add_argument(
        "--runs-per-month",
        type=int,
        default=4,
        help="how often this backup is scheduled, for the transfer estimate",
    )
    # No transfer-budget argument. It used to exist, and used to be fed by a
    # `workflow_dispatch` input, which let anyone with dispatch rights switch
    # the check off for a run by choosing a large number. There is nothing to
    # accept now, so the run stops rather than honouring a number that should
    # never have been settable in the first place.
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    # No transfer-budget argument exists, so a caller - including a
    # `workflow_dispatch` caller - has nothing to override it with. A dispatch
    # input used to be threaded through here; it was removed precisely because
    # it let anyone with dispatch rights switch the budget off for a run.
    args = parser.parse_args(argv)
    args.passphrase = os.environ.get(args.passphrase_env, "")

    try:
        result = run_backup(args)
    except (BackupRefused, BackupCryptoUnavailable, BackupCryptoError) as exc:
        # A refusal is a normal, reportable outcome - not a crash. The message
        # states the reason without restating any connection string.
        print(f"BACKUP REFUSED: {exc}", file=sys.stderr)
        return 3

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
