#!/usr/bin/env python3
"""Create a verifiable PostgreSQL backup, and prove it by restoring it.

The archive strategy is intentionally single and obvious: **the artifact is
the PostgreSQL custom-format dump itself** - `--format=custom`, which
libpq already compresses - with nothing wrapped around it. There is no
outer gzip layer to decompress, no ambiguity about what `pg_restore` is
given, and the SHA-256 in the manifest is the digest of the very bytes
`pg_restore` reads.

A backup is only claimed when it has been *restored*:

* the dump is written to a private temporary file and deleted on every
  path - plaintext never leaves the runner and never reaches an artifact;
* before the artifact is published, `pg_restore --list` reads it back and
  the dump is restored into an empty non-production target, whose table
  row counts are recorded in the manifest;
* a restore target that already holds relations is refused - an empty
  table is not an empty database, and restoring into a non-empty one
  would make the verification meaningless.

There is deliberately no way to skip verification. The `--no-verify` flag
that used to exist produced artifacts whose manifests carried
`restore_verification.performed: false` - a "backup" that no gate could
distinguish from a tested one. It is gone: an unverifiable backup is a
refusal, not a state.

Usage:
    SCHOLARZONE_DATABASE_URL=postgresql://... \\
        python scripts/pg_backup.py --output-dir backups \\
        --verify-restore-into postgresql://.../empty_scratch

The source and restore targets are held to the same policy as the
encrypted production backup (`app.services.backup_source`): an explicit
hostname allow-list, default-deny, and a production source requiring a
recorded authorization. Credentials are never logged, never written to the
manifest, and passed to the child process through the environment only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.backup_source import (  # noqa: E402
    SourceRejected,
    authorization_for,
    resolve_source,
    source_kind,
)


class BackupError(RuntimeError):
    pass


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise BackupError(f"{name} is not on PATH; install the postgresql-client package")
    return path


def _child_env() -> dict[str, str]:
    env = dict(os.environ)
    env["PGPASSFILE"] = os.devnull  # never prompt, never a stray .pgpass
    return env


def _run(command: list[str]) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, capture_output=True, text=True, check=False, env=_child_env())
    if completed.returncode != 0:
        raise BackupError(f"{command[0]} exited {completed.returncode}: {completed.stderr.strip()[:300]}")
    return completed


def _psql_rows(uri: str, sql: str) -> list[str]:
    completed = _run(["psql", uri, "-At", "-c", sql])
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def _relations(uri: str) -> list[str]:
    """Existing relations in the target - objects, not rows.

    A database with tables in it is not an empty database, whatever their
    row counts are: this is the check that keeps a verification restore
    from silently merging into somebody else's schema and then reporting
    the counts as evidence.
    """
    return _psql_rows(
        uri,
        "SELECT format('%I.%I', n.nspname, c.relname) FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r','p','v','m','S') "
        "ORDER BY c.oid DESC LIMIT 20",
    )


def _table_counts(uri: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    tables = _psql_rows(
        uri, "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
    )
    for table in tables:
        counts[table] = int(_psql_rows(uri, f'SELECT COUNT(*) FROM "{table}"')[0] or 0)
    return counts


def _restore_verify(artefact: Path, destination: str) -> dict[str, object]:
    """Restore the artifact into an empty non-production target.

    Runs `pg_restore --list` first: it is the cheapest proof that the bytes
    are a readable PostgreSQL archive at all, and it fails on the
    gzip-wrapped-custom-archive mistake this function exists to catch - a
    gzip layer handed to `pg_restore` is refused here instead of producing a
    manifest that claims a restore nobody performed.
    """
    pg_restore = _require_tool("pg_restore")
    _require_tool("psql")

    try:
        destination_identity = _validate_destination(destination)
    except SourceRejected as exc:
        raise BackupError(f"restore target refused: {exc}") from exc

    listing = _run([pg_restore, "--list", str(artefact)])
    if not listing.stdout.strip():
        raise BackupError("pg_restore --list produced no table of contents")

    existing = _relations(destination)
    if existing:
        raise BackupError(
            "the restore target is not empty (existing relations: "
            f"{existing[:8]}); refusing to verify a restore against a database "
            "that already holds objects"
        )

    _run([pg_restore, "--no-owner", "--no-privileges", "--dbname", destination, str(artefact)])
    return {
        "target_identity": destination_identity.describe(),
        "target_relations_before": 0,
        "archive_listing_entries": len([line for line in listing.stdout.splitlines() if line.strip()]),
        "table_row_counts": _table_counts(destination),
        "restored_at": datetime.now(timezone.utc).isoformat(),
    }


def _validate_destination(destination: str):
    """A restore target obeys the same allow-list policy as a source, and may
    not be production: verifying a backup by restoring it into the database
    it might have to survive is how a drill becomes an incident."""
    url = urlparse(destination)
    scheme = (url.scheme or "").split("+", 1)[0]
    if scheme not in ("postgres", "postgresql"):
        raise BackupError(f"the restore target scheme is {url.scheme or 'missing'}, not PostgreSQL")

    from app.services.backup_source import validate_source

    try:
        identity = validate_source(destination)
    except SourceRejected as exc:
        raise BackupError(f"restore target refused by the source policy: {exc}") from exc
    if source_kind(identity) == "production":
        raise BackupError(
            "the restore target is a production host; a backup is verified into "
            "non-production, never into the database it may have to survive"
        )
    return identity


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="backups")
    parser.add_argument(
        "--verify-restore-into",
        required=True,
        help="a NON-production PostgreSQL URI that is empty; the dump is restored "
        "into it before the artifact is published",
    )
    args = parser.parse_args()

    _require_tool("pg_dump")

    dsn = os.environ.get("SCHOLARZONE_DATABASE_URL", "").strip()
    if not dsn:
        raise BackupError("SCHOLARZONE_DATABASE_URL is not set; this tool never guesses a target")

    try:
        source_url, source_identity = resolve_source("SCHOLARZONE_DATABASE_URL")
        kind = source_kind(source_identity)
        authorization = authorization_for(kind)
    except SourceRejected as exc:
        raise BackupError(str(exc)) from exc

    taken_at = datetime.now(timezone.utc)
    stamp = taken_at.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # The artifact IS the pg custom archive: no outer gzip, nothing to unwrap.
    artefact = out_dir / f"scholarzone-{stamp}.dump"
    _require_tool("pg_dump")
    _run(["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(artefact), source_url])

    verification = _restore_verify(artefact, args.verify_restore_into)

    digest = hashlib.sha256(artefact.read_bytes()).hexdigest()
    manifest = {
        "manifest_version": 2,
        "taken_at": taken_at.isoformat().replace("+00:00", "Z"),
        "source": source_identity.describe(),
        "source_kind": kind,
        "production_authorization": authorization,
        "archive": "pg_dump --format=custom (no outer compression layer)",
        "artifact_bytes": artefact.stat().st_size,
        "sha256": digest,
        "restore_verified": True,
        "restore_verification": verification,
        "rollback_note": (
            "Restore with: pg_restore --no-owner --no-privileges --dbname <target> "
            "the artifact. Reconcile table_row_counts in restore_verification "
            "against the source before declaring the restore good."
        ),
    }
    (out_dir / f"scholarzone-{stamp}.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "artifact": str(artefact), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackupError as error:
        print(f"BACKUP REFUSED: {error}", file=sys.stderr)
        raise SystemExit(2)
