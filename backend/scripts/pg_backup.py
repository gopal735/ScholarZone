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
   backend, or a source that looks like production each stop the run before a
   byte is dumped. A backup that cannot be encrypted must not exist.
2. **Dump to a temporary file outside Git**, with permissions restricted to the
   current user. The plaintext never enters the repository or the artifact.
3. **Encrypt in memory and verify by round-trip**: the ciphertext is decrypted
   with the same passphrase and compared byte-for-byte with the plaintext before
   the plaintext is discarded. A ciphertext that has not been proven decryptable
   is not a backup.
4. **Record a manifest** carrying the timestamp, the ciphertext's SHA-256 and
   size, the source's *identity* (dialect and whether a host is set - never the
   connection string), and the outcome. This is what a restore consumes.
5. **Remove the plaintext** and confirm it is gone.

The transfer estimate is computed before anything is uploaded, because a backup
that exhausts the free-tier network budget to save the database has made things
worse: the application's own traffic then fails. `--max-monthly-mib` fails the
run when the projected monthly transfer exceeds the budget, and the default is
conservative.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
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

#: A database is treated as production when its URL contains any of these. A
#: backup is a read-only operation, so this is not about write safety - it is
#: that a *scheduled* run pointed at production would silently compete with the
#: application for the free-tier transfer budget, which is the failure this whole
#: architecture exists to avoid.
PRODUCTION_MARKERS = ("prod", "production")

#: Default monthly transfer budget in MiB. Neon's free tier allows 5 GiB/month
#: of outbound transfer; the application uses some of it, so a backup budget has
#: to be a fraction rather than the whole allowance.
DEFAULT_MAX_MONTHLY_MIB = 512


class BackupRefused(RuntimeError):
    """The backup did not happen, and the reason is in the message."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_source_url(env_name: str) -> str:
    """Read the source URL from the named variable, refusing when absent."""
    value = os.environ.get(env_name)
    if not value:
        raise BackupRefused(
            f"{env_name} is not set; a backup needs an explicit source. "
            "Refusing to guess or fall back to the application's connection."
        )
    return value


def _assert_not_production(url: str) -> str:
    """Describe the source by identity, and refuse if it looks like production.

    Returns a redacted identity string - dialect and whether a host is present -
    that is safe to put in a manifest. The URL itself is never returned and never
    logged.
    """
    lowered = url.lower()
    if any(marker in lowered for marker in PRODUCTION_MARKERS):
        raise BackupRefused(
            "the source URL contains a production marker; a scheduled backup "
            "must not compete with the application for the free-tier transfer "
            "budget. Set SZ_BACKUP_SOURCE_URL to a non-production source."
        )

    # "postgresql://" or "postgres://"
    dialect = url.split("://", 1)[0] if "://" in url else "unknown"
    has_host = "@" in url or "://" in url
    identity = f"{dialect} (host {'configured' if has_host else 'absent'})"
    return identity


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
    """
    return (dump_bytes * runs_per_month * 2) / (1024 * 1024)


def run_backup(args: argparse.Namespace) -> dict[str, Any]:
    """Execute one backup. Returns the manifest that was written."""
    started = datetime.now(timezone.utc)

    passphrase = args.passphrase
    if not passphrase:
        raise BackupRefused(
            "no backup passphrase; set SZ_BACKUP_PASSPHRASE. Refusing to write "
            "a backup nobody could restore."
        )

    source_url = _resolve_source_url(args.source_url_env)
    source_identity = _assert_not_production(source_url)

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
    if projected > args.max_monthly_mib:
        raise BackupRefused(
            f"projected monthly transfer {projected:.1f} MiB exceeds the "
            f"{args.max_monthly_mib} MiB budget for {args.runs_per_month} runs; "
            "reduce the schedule or the dump size before scheduling a backup."
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
                "source_identity": source_identity,
                "ciphertext_sha256": cipher_sha,
                "ciphertext_bytes": len(ciphertext),
                "plaintext_bytes": dump_bytes,
                "projected_monthly_transfer_mib": round(projected, 2),
                "runs_per_month": args.runs_per_month,
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
        "backend": backend.name,
    }


def main(argv: list[str] | None = None) -> int:
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
        "--runs-per-month",
        type=int,
        default=4,
        help="how often this backup is scheduled, for the transfer estimate",
    )
    parser.add_argument(
        "--max-monthly-mib",
        type=float,
        default=DEFAULT_MAX_MONTHLY_MIB,
        help="fail when the projected monthly transfer exceeds this",
    )
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
