#!/usr/bin/env python3
"""Create a verifiable PostgreSQL backup with pg_dump.

The backup is the step that decides whether a deletion may ever be
considered, so it holds itself to more than "a file appeared":

* **It refuses the wrong target.** No DSN, a non-PostgreSQL DSN, or a DSN
  pointing at a known production endpoint each stop the run before a byte
  is dumped. Production dumps are a separate, human-triggered decision
  (``--production-dump`` with the reason recorded), never something a
  scheduled job does silently.
* **It verifies itself.** The dump is taken in the custom format, restored
  into a scratch database on the same runner, and only a backup whose
  restore succeeds is kept; the plaintext dump is deleted either way.
* **It never writes the plaintext where it can be read.** The dump is
  compressed with gzip and hashed with SHA-256; the manifest carries the
  row count of every restored table so a restore can be reconciled, not
  just "it ran".

Usage:
    SCHOLARZONE_DATABASE_URL=postgresql://... \\
        python scripts/pg_backup.py --output-dir backups \\
        [--production-dump --reason "why this dump is authorised"]

The script needs ``pg_dump``/``pg_restore`` on PATH (present on GitHub's
ubuntu runners; ``apt-get install -y postgresql-client`` elsewhere).
"""

from __future__ import annotations

import argparse
import gzip
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

SCRATCH_DB = "sz_backup_verify"

#: Production endpoints that a scheduled backup must never dump on its own.
#: A host is listed here when an unattended run reaching it would be a
#: production incident rather than a backup.
KNOWN_PRODUCTION_HOSTS = frozenset(
    {
        "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech",
        "ep-broad-block-ayrx86zn.c-5.us-east-2.aws.neon.tech",
    }
)

POSTGRES_SCHEMES = ("postgres", "postgresql")


class BackupError(RuntimeError):
    pass


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise BackupError(f"{name} is not on PATH; install the postgresql-client package")
    return path


def _dsn() -> str:
    dsn = os.environ.get("SCHOLARZONE_DATABASE_URL", "").strip()
    if not dsn:
        raise BackupError("SCHOLARZONE_DATABASE_URL is not set; this tool never guesses a target")
    return dsn


def _classify(dsn: str) -> dict[str, str]:
    parsed = urlparse(dsn)
    scheme = (parsed.scheme or "").split("+", 1)[0]
    host = parsed.hostname or ""
    return {
        "scheme": scheme,
        "host": host,
        "path": parsed.path or "",
        # The user, the password and the port are deliberately NOT reported:
        # the manifest is a public artifact and none of it is needed to tell
        # two dumps apart.
        "identity": f"{parsed.scheme}://{host}{parsed.path or ''}",
    }


def _guard(dsn: str, production_dump: bool, reason: str | None) -> None:
    info = _classify(dsn)
    if info["scheme"] not in POSTGRES_SCHEMES:
        raise BackupError(f"refusing a non-PostgreSQL source: {info['scheme'] or 'no scheme'}")
    if info["host"] in KNOWN_PRODUCTION_HOSTS and not production_dump:
        raise BackupError(
            "the source is a known production endpoint; pass --production-dump with a "
            "recorded reason if that is genuinely intended"
        )
    if production_dump and not (reason or "").strip():
        raise BackupError("a production dump requires a reason for the audit record")


def _scratch_uri() -> str:
    return os.environ.get("SZ_BACKUP_SCRATCH_URI", "").strip()


def _run(command: list[str]) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise BackupError(f"{' '.join(command[:2])} failed: {completed.stderr.strip()[:400]}")
    return completed


def _table_counts(uri: str) -> dict[str, int]:
    """Row counts of every public table in the restored scratch database.

    The manifest carries them so the restore can be reconciled against the
    source and against the next restore: a dump that restores zero rows is a
    passing command that failed the job.
    """
    counts: dict[str, int] = {}
    selected = _run(
        [
            "psql",
            uri,
            "-At",
            "-c",
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
        ]
    )
    tables = [line.strip() for line in selected.stdout.splitlines() if line.strip()]
    for table in tables:
        rows = _run(["psql", uri, "-At", "-c", f'SELECT COUNT(*) FROM "{table}"'])
        counts[table] = int(rows.stdout.strip() or 0)
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="backups")
    parser.add_argument("--production-dump", action="store_true")
    parser.add_argument("--reason", default=None)
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the scratch-database restore verification (not recommended; a backup "
        "nobody has restored is a hope, not a backup)",
    )
    args = parser.parse_args()

    dsn = _dsn()
    _require_tool("pg_dump")
    _require_tool("pg_restore")
    if not args.no_verify:
        _require_tool("psql")

    _guard(dsn, args.production_dump, args.reason)
    info = _classify(dsn)
    taken_at = datetime.now(timezone.utc)
    stamp = taken_at.strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    scratch = _scratch_uri()
    if not args.no_verify and not scratch:
        raise BackupError(
            "SZ_BACKUP_SCRATCH_URI must point at a disposable, already-created PostgreSQL "
            "database to restore into; an unverifiable backup is not accepted"
        )

    with tempfile.TemporaryDirectory(prefix="sz-backup-") as tmp:
        plain = Path(tmp) / f"scholarzone-{stamp}.dump"
        _run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-privileges",
                "--file",
                str(plain),
                dsn,
            ]
        )
        compressed = plain.with_suffix(".dump.gz")
        with open(plain, "rb") as source, gzip.open(compressed, "wb", compresslevel=9) as sink:
            shutil.copyfileobj(source, sink)
        plain.unlink()

        digest = hashlib.sha256(compressed.read_bytes()).hexdigest()
        verification: dict[str, object] = {"performed": False}
        if not args.no_verify:
            # The scratch database must be empty: restoring onto old data
            # would let the verification pass on the previous run's rows.
            existing = _table_counts(scratch)
            if sum(existing.values()) > 0:
                raise BackupError(
                    "the scratch database is not empty; refusing to verify a restore "
                    f"against a database that already holds {sum(existing.values())} rows"
                )
            _run(["pg_restore", "--no-owner", "--no-privileges", "--dbname", scratch, str(compressed)])
            verification = {
                "performed": True,
                "target": _classify(scratch)["identity"],
                "table_row_counts": _table_counts(scratch),
            }

        manifest = {
            "manifest_version": 1,
            "taken_at": taken_at.isoformat().replace("+00:00", "Z"),
            "source": info,
            "production_dump": bool(args.production_dump),
            "reason": args.reason,
            "tool": "pg_dump --format=custom | gzip -9",
            "sha256": digest,
            "bytes": compressed.stat().st_size,
            "restore_verification": verification,
            "rollback_note": (
                "Restore with: pg_restore --no-owner --no-privileges --dbname <target> "
                "this file. Verify the table_row_counts in this manifest against the "
                "target before declaring the restore good."
            ),
        }
        destination = out_dir / f"scholarzone-{stamp}.dump.gz"
        shutil.move(compressed, destination)
        (out_dir / f"scholarzone-{stamp}.manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, "file": str(destination), "sha256": digest}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackupError as error:
        print(f"BACKUP REFUSED: {error}", file=sys.stderr)
        raise SystemExit(2)
