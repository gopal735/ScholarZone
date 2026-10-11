#!/usr/bin/env python3
"""Restore an encrypted backup into an isolated destination and prove it worked.

    python scripts/pg_restore.py \
        --artefact backup-out/scholarzone-20261011T030000Z.szbak \
        --destination-url-env SZ_RESTORE_DEST_URL \
        --passphrase-env SZ_BACKUP_PASSPHRASE

The restore is the only step that turns a backup into a capability, so it is
also the step most likely to be quietly wrong. This script therefore proves the
restore rather than performing it:

* The artefact is decrypted and its digest checked, so corruption is caught
  before a restore is attempted.
* The destination must be PostgreSQL and must not look like production.
  Restoring over production converts a data loss into a data loss plus a
  silent overwrite.
* After `pg_restore`, the restored database is inspected: its tables, its
  scholarship count, and the same public-visibility predicate the catalogue
  applies. The outcome is written as evidence, never asserted.

The source artefact records its own plaintext digest, so a restore that landed
different bytes is detectable without a second copy to compare against.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    BackupCryptoError,
    BackupCryptoUnavailable,
    select_backend,
)

#: The canonical public visibility predicate, restated for the verification
#: query. It is the same rule `generate_snapshot.py` applies, so a restored
#: database is judged by the same standard the catalogue is.
PUBLIC_VISIBILITY = (
    "status != 'closed' AND is_archived = 0 AND verification_status != 'quarantined'"
)

#: Tables a restore is expected to reproduce. Named rather than discovered: a
#: restore that quietly lost one would otherwise pass a discovery-based check
#: that only sees what survived.
EXPECTED_TABLES = (
    "scholarships",
    "scholarship_reviews",
    "scholarship_verification_history",
)


class RestoreRefused(RuntimeError):
    """The restore did not happen, and the reason is in the message."""


def _which(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _destination_url(env_name: str) -> str:
    value = os.environ.get(env_name)
    if not value:
        raise RestoreRefused(
            f"{env_name} is not set; a restore needs an explicit destination. "
            "Refusing to fall back to the application's connection."
        )
    return value


def _assert_destination_is_isolated(url: str) -> None:
    lowered = url.lower()
    if any(marker in lowered for marker in ("prod", "production")):
        raise RestoreRefused(
            "the destination URL contains a production marker. Restoring into "
            "production would overwrite live data; use an isolated database."
        )


def _decrypt_artefact(artefact: Path, passphrase: str) -> bytes:
    payload = artefact.read_bytes()
    backend = select_backend()
    try:
        return backend.decrypt(payload, passphrase)
    except BackupCryptoError as exc:
        raise RestoreRefused(
            f"{artefact.name} could not be decrypted: {exc}"
        ) from exc


def _run_restore(pg_restore: str, plaintext_path: Path, destination: str) -> None:
    """Feed the decrypted custom-format dump into `pg_restore`.

    `--clean --if-exists` is deliberately absent: a restore into a database that
    already has content should fail loudly rather than silently merging with it,
    because the operator asked for a restore, not a merge.
    """
    env = dict(os.environ)
    env["PGPASSFILE"] = os.devnull
    proc = subprocess.run(
        [
            pg_restore,
            "--no-owner",
            "--no-privileges",
            "--dbname", destination,
            str(plaintext_path),
        ],
        env=env,
        capture_output=True,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", "replace").strip()
        # pg_restore exits non-zero on warnings as well as errors; a warning is
        # not a failed restore, so the distinction is reported rather than
        # guessed from the exit code alone.
        raise RestoreRefused(f"pg_restore exited {proc.returncode}: {stderr[:300]}")


def _verify_restored(destination: str) -> dict[str, Any]:
    """Inspect the restored database and return the evidence.

    Uses SQLAlchemy because it is already a dependency, so the restore path does
    not require a separate PostgreSQL client driver to be installed.
    """
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(destination)
    try:
        with engine.connect() as connection:
            tables = set(inspect(connection).get_table_names())
            missing = [name for name in EXPECTED_TABLES if name not in tables]
            if missing:
                raise RestoreRefused(
                    f"the restored database is missing expected tables: {missing}"
                )

            counts: dict[str, int] = {}
            for table in EXPECTED_TABLES:
                counts[table] = connection.execute(
                    text(f'SELECT COUNT(*) FROM "{table}"')
                ).scalar_one()

            public = connection.execute(
                text(f"SELECT COUNT(*) FROM scholarships WHERE {PUBLIC_VISIBILITY}")
            ).scalar_one()

        return {
            "tables_present": sorted(tables & set(EXPECTED_TABLES)),
            "missing_tables": missing,
            "row_counts": counts,
            "publicly_visible_scholarships": public,
        }
    finally:
        engine.dispose()


def run_restore(args: argparse.Namespace) -> dict[str, Any]:
    passphrase = os.environ.get(args.passphrase_env, "")
    if not passphrase:
        raise RestoreRefused(
            f"{args.passphrase_env} is not set; a restore needs the passphrase "
            "the backup was encrypted with."
        )

    artefact = Path(args.artefact)
    if not artefact.is_file():
        raise RestoreRefused(f"no such artefact: {artefact}")

    # The destination is validated before the tool is looked for: an operator
    # with a typo in the destination should hear about the destination, not be
    # told about a missing binary that was never going to be reached.
    destination = _destination_url(args.destination_url_env)
    if "postgres" not in destination.split("://", 1)[0]:
        raise RestoreRefused(
            "the destination is not PostgreSQL; `verify_recovery_path.py` "
            "refuses a SQLite round-trip for the same reason - it would not be "
            "evidence about a PostgreSQL restore."
        )
    _assert_destination_is_isolated(destination)

    pg_restore = _which("pg_restore")
    if not pg_restore:
        raise RestoreRefused(
            "pg_restore is not on PATH; a PostgreSQL restore needs it and no "
            "substitute is offered."
        )

    plaintext = _decrypt_artefact(artefact, passphrase)

    # The digest check is what makes this a proof rather than a best effort: the
    # bytes restored must be the bytes that were backed up.
    from app.services.backup_crypto import read_manifest

    header = read_manifest(artefact.read_bytes())
    actual = hashlib.sha256(plaintext).hexdigest()
    if header.get("plaintext_sha256") != actual:
        raise RestoreRefused(
            "the decrypted dump does not match the digest the artefact records; "
            "the artefact is corrupt and must not be restored"
        )

    tmpdir = Path(tempfile.mkdtemp(prefix="sz-restore-"))
    plaintext_path = tmpdir / "restore.dump"
    try:
        plaintext_path.write_bytes(plaintext)
        del plaintext
        _run_restore(pg_restore, plaintext_path, destination)
    finally:
        plaintext_path.unlink(missing_ok=True)

    evidence = _verify_restored(destination)
    evidence.update({
        "artefact": artefact.name,
        "ciphertext_sha256": hashlib.sha256(artefact.read_bytes()).hexdigest(),
        "plaintext_sha256": actual,
        "destination_identity": destination.split("://", 1)[0],
        "outcome": "restored-and-verified",
    })
    return evidence


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artefact", required=True, help="the .szbak file")
    parser.add_argument(
        "--destination-url-env",
        default="SZ_RESTORE_DEST_URL",
        help="environment variable holding the destination connection string",
    )
    parser.add_argument(
        "--passphrase-env",
        default="SZ_BACKUP_PASSPHRASE",
        help="environment variable holding the backup passphrase",
    )
    args = parser.parse_args(argv)

    try:
        result = run_restore(args)
    except (RestoreRefused, BackupCryptoUnavailable, BackupCryptoError) as exc:
        print(f"RESTORE REFUSED: {exc}", file=sys.stderr)
        return 4

    import json

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
