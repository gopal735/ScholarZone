#!/usr/bin/env python3
"""Prove the backup and restore procedures work, against a scratch database.

Run this on a machine with a disposable PostgreSQL server (GitHub's ubuntu
runners have one). It never touches production: the point is the procedure,
not the data, so the database it exercises is created empty here and seeded
with a handful of rows by this script.

The drill:

1. starts an empty scratch PostgreSQL database (the ``--scratch`` URI);
2. creates the application schema through the app's own ``init_database``
   path, so the dump exercises the real DDL;
3. seeds a deterministic row set;
4. runs ``scripts/pg_backup.py`` against it, which dumps, verifies the
   restore into the ``--restore-target`` database and records the table
   counts in a manifest;
5. independently counts the restored database and reconciles the numbers;
6. restores the same backup into a second, empty database, to prove the
   artifact is reusable rather than a one-shot;
7. fails loudly if any of that does not line up.

A green drill says: a backup of this schema can be taken, restored, and
reconciled. It says nothing about production parity, on purpose - parity
requires a production backup, which is a separate, authorised decision.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKUP_SCRIPT = REPOSITORY_ROOT / "scripts" / "pg_backup.py"

FIXTURE_ROWS = [
    ("Drill Award One", "Drillland"),
    ("Drill Award Two", "Drillland"),
    ("Drill Award Three", "Drillland"),
]


def _run(command: list[str]) -> str:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(command)}\n{completed.stderr[:800]}")
    return completed.stdout


def _psql_count(uri: str, table: str) -> int:
    out = _run(["psql", uri, "-At", "-c", f'SELECT COUNT(*) FROM "{table}"'])
    return int(out.strip() or 0)


def _psql_empty(uri: str) -> bool:
    tables = _run(
        [
            "psql",
            uri,
            "-At",
            "-c",
            "SELECT tablename FROM pg_tables WHERE schemaname='public'",
        ]
    ).strip()
    return not tables


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, help="source PostgreSQL URI (scratch)")
    parser.add_argument("--restore-target", required=True, help="empty PostgreSQL URI to restore into")
    parser.add_argument("--restore-target-2", required=True, help="a second empty PostgreSQL URI")
    parser.add_argument("--output-dir", default="backups")
    args = parser.parse_args()

    for name, uri in (
        ("source", args.scratch),
        ("restore target", args.restore_target),
        ("second restore target", args.restore_target_2),
    ):
        if not _psql_empty(uri):
            raise SystemExit(f"the {name} database is not empty: {uri.split('@')[-1]}")

    # 1-2. Build the real schema through the application's own path.
    env = dict(os.environ)
    env["SCHOLARZONE_DATABASE_URL"] = args.scratch
    env["SCHOLARZONE_ENVIRONMENT"] = "test"
    subprocess.run(
        [sys.executable, "-c", "from app.database import init_database; init_database()"],
        cwd=REPOSITORY_ROOT / "backend",
        env=env,
        check=True,
    )

    # 3. Seed deterministically.
    seed = (
        "from app.database import get_db\n"
        "from app.models import Scholarship\n"
        "rows = " + repr(FIXTURE_ROWS) + "\n"
        "with next(get_db()) as db:\n"
        "    for title, country in rows:\n"
        "        db.add(Scholarship(title=title, country=country, degree=\"Master's\", "
        "funding=\"Full tuition\", status=\"open\"))\n"
        "    db.commit()\n"
    )
    subprocess.run(
        [sys.executable, "-c", seed], cwd=REPOSITORY_ROOT / "backend", env=env, check=True
    )

    expected_scholarships = _psql_count(args.scratch, "scholarships")
    if expected_scholarships != len(FIXTURE_ROWS):
        raise SystemExit(f"seed mismatch: {expected_scholarships} rows")

    # 4. Backup with verification.
    backup_env = dict(os.environ)
    backup_env["SCHOLARZONE_DATABASE_URL"] = args.scratch
    backup_env["SZ_BACKUP_SCRATCH_URI"] = args.restore_target
    result = subprocess.run(
        [sys.executable, str(BACKUP_SCRIPT), "--output-dir", str(args.output_dir)],
        env=backup_env,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"backup script refused or failed:\n{result.stdout}\n{result.stderr}")
    summary = json.loads(result.stdout)

    # 5. Reconcile the manifest against an independent count.
    manifest_path = REPOSITORY_ROOT / args.output_dir
    manifests = sorted(manifest_path.glob("*.manifest.json"))
    latest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    verification = latest["restore_verification"]
    if not verification.get("performed"):
        raise SystemExit("the backup was not verified by a restore; the drill fails")
    restored = _psql_count(args.restore_target, "scholarships")
    declared = verification["table_row_counts"].get("scholarships")
    if restored != expected_scholarships or declared != expected_scholarships:
        raise SystemExit(
            f"reconciliation failed: source={expected_scholarships}, "
            f"restored={restored}, manifest={declared}"
        )

    # 6. The artifact restores a second time into a fresh database.
    dump = REPOSITORY_ROOT / summary["file"]
    _run(
        [
            "pg_restore",
            "--no-owner",
            "--no-privileges",
            "--dbname",
            args.restore_target_2,
            str(dump),
        ]
    )
    second = _psql_count(args.restore_target_2, "scholarships")
    if second != expected_scholarships:
        raise SystemExit(f"second restore mismatch: {second} rows (expected {expected_scholarships})")

    # 7. The sha256 in the manifest matches the artifact on disk.
    import hashlib

    digest = hashlib.sha256(dump.read_bytes()).hexdigest()
    if digest != latest["sha256"]:
        raise SystemExit("the artifact's sha256 does not match its manifest")

    print(
        json.dumps(
            {
                "drill": "ok",
                "source_rows": expected_scholarships,
                "restored_rows": restored,
                "second_restore_rows": second,
                "backup_file": str(dump),
                "sha256": digest,
                "source_identity": latest["source"]["identity"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
