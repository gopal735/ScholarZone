#!/usr/bin/env python3
"""Prove the real backup and restore procedure, end to end, on throwaway
PostgreSQL databases.

This drill exists to answer one question with evidence instead of hope:
*can a backup this repository produced actually be restored?*

It exercises the canonical encrypted pipeline - `backend/scripts/pg_backup.py`
and `backend/scripts/pg_restore.py` - against three disposable PostgreSQL
databases on the runner, and then tries to break it:

1. an empty source database is built with the application's real schema
   (`init_database`) and seeded with a deterministic row set;
2. a backup is taken **with restore verification into a second database**
   (`--verify-restore-into`), which is the configuration the manifest's
   `restore_verified` claim depends on;
3. the same artifact is restored into a **third, independent** database by the
   documented restore command, and the restored row counts are reconciled
   against the manifest and the source;
4. `pg_restore --list` is run against the artifact, and the negative cases
   are asserted: a gzip-wrapped custom archive is **refused** (the failure
   mode this drill was written after), a corrupted artifact fails, a wrong
   passphrase fails, and a restore into a non-empty target is refused.

A green drill is evidence about the *procedure*. It is deliberately not
evidence about production data: the drill's source is seeded here, so
production parity additionally needs a real production backup restored into
a non-production target - a separate, authorised action.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPOSITORY_ROOT / "backend"
ENCRYPTED_BACKUP = BACKEND / "scripts" / "pg_backup.py"
ENCRYPTED_RESTORE = BACKEND / "scripts" / "pg_restore.py"
PLAIN_BACKUP = REPOSITORY_ROOT / "scripts" / "pg_backup.py"

FIXTURE_ROWS = [
    ("Drill Award One", "Drillland"),
    ("Drill Award Two", "Drillland"),
    ("Drill Award Three", "Drillland"),
]

PASSPHRASE = "drill-passphrase-not-a-secret"


def _run(command: list[str], env: dict[str, str] | None = None, expect_ok: bool = True, cwd: Path | None = None):
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, env=env or os.environ.copy(), cwd=cwd
    )
    if expect_ok and completed.returncode != 0:
        raise SystemExit(
            f"command failed: {' '.join(command[:3])}...\n{completed.stdout[-500:]}\n{completed.stderr[-800:]}"
        )
    return completed


def _psql_count(uri: str, table: str) -> int:
    out = _run(["psql", uri, "-At", "-c", f'SELECT COUNT(*) FROM "{table}"'])
    return int(out.stdout.strip() or 0)


def _relations(uri: str) -> int:
    out = _run(
        [
            "psql",
            uri,
            "-At",
            "-c",
            "SELECT COUNT(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relkind IN ('r','p','v','m','S')",
        ]
    )
    return int(out.stdout.strip() or 0)


def _env(uri_map: dict[str, str]) -> dict[str, str]:
    env = dict(os.environ)
    env.update(uri_map)
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--verify-target", required=True)
    parser.add_argument("--restore-target", required=True)
    parser.add_argument("--output-dir", default="backups")
    args = parser.parse_args()

    for name, uri in (("source", args.source), ("verify target", args.verify_target), ("restore target", args.restore_target)):
        if _relations(uri) != 0:
            raise SystemExit(f"the {name} database is not empty; a drill needs disposable targets")

    # 1. Real schema through the application's own initialisation.
    seed_env = _env({"SCHOLARZONE_DATABASE_URL": args.source, "SCHOLARZONE_ENVIRONMENT": "test"})
    _run([sys.executable, "-m", "pip", "install", "-q", "-r", str(BACKEND / "requirements.txt")])
    _run(
        [sys.executable, "-c", "from app.database import init_database; init_database()"],
        cwd=BACKEND,
        env=seed_env,
    )
    seed = (
        "from app.database import get_db\n"
        "from app.models import Scholarship, ScholarshipVerificationHistory\n"
        "rows = " + repr(FIXTURE_ROWS) + "\n"
        "with next(get_db()) as db:\n"
        "    for title, country in rows:\n"
        "        record = Scholarship(title=title, country=country, degree=\"Master's\", funding=\"Full tuition\", status=\"open\")\n"
        "        db.add(record)\n"
        "        db.flush()\n"
        "        db.add(ScholarshipVerificationHistory(scholarship_id=record.id, field_name=\"title\", change_type=\"created\", verification_status=\"confirmed\"))\n"
        "    db.commit()\n"
    )
    _run([sys.executable, "-c", seed], cwd=BACKEND, env=seed_env)

    expected = _psql_count(args.source, "scholarships")
    if expected != len(FIXTURE_ROWS):
        raise SystemExit(f"seed mismatch: {expected} rows")

    # 2. The canonical encrypted backup, with restore verification.
    allow = "drill.example.org,127.0.0.1,localhost"
    host = _host_of(args.source)
    backup_env = _env(
        {
            "SCHOLARZONE_DATABASE_URL": args.source,
            "SZ_BACKUP_SOURCE_URL": args.source,
            "SZ_BACKUP_PASSPHRASE": PASSPHRASE,
            "SZ_BACKUP_ALLOWED_HOSTS": f"{allow},{host}",
            "SZ_BACKUP_RESTORE_URI": args.verify_target,
        }
    )
    out_dir = REPOSITORY_ROOT / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    result = _run(
        [
            sys.executable,
            str(ENCRYPTED_BACKUP),
            "--source-url-env",
            "SZ_BACKUP_SOURCE_URL",
            "--passphrase-env",
            "SZ_BACKUP_PASSPHRASE",
            "--output-dir",
            str(out_dir),
            "--verify-restore-into",
            args.verify_target,
        ],
        env=backup_env,
        expect_ok=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"the canonical backup refused or failed:\n{result.stdout}\n{result.stderr}")
    summary = json.loads(result.stdout)
    manifests = sorted(out_dir.glob("*.manifest.json"))
    manifest = json.loads(manifests[-1].read_text(encoding="utf-8"))
    artefact = Path(summary["artefact"])

    # The manifest must claim exactly what happened.
    if manifest.get("source_kind") != "non-production":
        raise SystemExit("the drill's source must be classified non-production")
    if manifest.get("restore_verified") is not True:
        raise SystemExit("the backup ran with a restore target, so the manifest must say restore_verified")
    evidence = manifest["restore_verification"]["table_row_counts"]
    if evidence.get("scholarships") != expected:
        raise SystemExit(
            f"restore verification counts disagree: {evidence.get('scholarships')} vs {expected}"
        )

    # 3. The same artifact restores independently, by the documented command.
    restore_env = _env(
        {
            "SZ_RESTORE_DEST_URL": args.restore_target,
            "SZ_BACKUP_PASSPHRASE": PASSPHRASE,
            "SZ_BACKUP_ALLOWED_HOSTS": f"{allow},{host},{_host_of(args.restore_target)}",
        }
    )
    restored = _run(
        [
            sys.executable,
            str(ENCRYPTED_RESTORE),
            "--artefact",
            str(artefact),
            "--destination-url-env",
            "SZ_RESTORE_DEST_URL",
            "--passphrase-env",
            "SZ_BACKUP_PASSPHRASE",
        ],
        env=restore_env,
        expect_ok=False,
    )
    if restored.returncode != 0:
        raise SystemExit(f"the documented restore command failed:\n{restored.stdout}\n{restored.stderr}")
    second = _psql_count(args.restore_target, "scholarships")
    if second != expected:
        raise SystemExit(f"second restore mismatch: {second} rows, expected {expected}")

    # 4. The negative cases: each of these must fail, or the pipeline lies.
    # 4a. A gzip-wrapped custom archive is not a pg_restore input.
    listing = _run(["pg_restore", "--list", str(artefact)], expect_ok=False)
    # The artefact is the encrypted .szbak, so --list is not the right reader
    # for it; the decrypted plaintext is what pg_restore consumes. Wrap the
    # decrypted dump in gzip and prove pg_restore refuses it - the archived
    # failure mode of an outer gzip layer.
    decrypted = _run(
        [
            sys.executable,
            "-c",
            "import sys; sys.path.insert(0, 'backend');"
            "from app.services.backup_crypto import select_backend;"
            f"data = open({str(artefact)!r},'rb').read();"
            f"open({str(out_dir / 'drill-plain.dump')!r},'wb').write(select_backend().decrypt(data, {PASSPHRASE!r}))",
        ],
        expect_ok=False,
    )
    if decrypted.returncode != 0:
        raise SystemExit("could not decrypt the artifact for the negative test")
    plain = out_dir / "drill-plain.dump"
    with open(plain, "rb") as source, gzip.open(out_dir / "wrapped.dump.gz", "wb") as sink:
        shutil.copyfileobj(source, sink)
    wrapped = _run(["pg_restore", "--list", str(out_dir / "wrapped.dump.gz")], expect_ok=False)
    if wrapped.returncode == 0:
        raise SystemExit(
            "a gzip-wrapped custom archive was accepted by pg_restore; the outer "
            "compression layer this drill refuses is apparently being unwrapped"
        )
    listing_ok = _run(["pg_restore", "--list", str(plain)], expect_ok=False)
    if listing_ok.returncode != 0:
        raise SystemExit("pg_restore --list rejected an unwrapped custom archive")

    # 4b. A corrupted artifact must fail, and must not produce a manifest
    #     that claims success.
    corrupt = out_dir / "corrupt.szbak"
    corrupt.write_bytes(artefact.read_bytes()[:-16] + b"\x00" * 16)
    corrupted = _run(
        [
            sys.executable,
            str(ENCRYPTED_RESTORE),
            "--artefact",
            str(corrupt),
            "--destination-url-env",
            "SZ_RESTORE_DEST_URL",
            "--passphrase-env",
            "SZ_BACKUP_PASSPHRASE",
        ],
        env=restore_env,
        expect_ok=False,
    )
    if corrupted.returncode == 0:
        raise SystemExit("a corrupted artifact restored successfully; corruption is not being detected")

    # 4c. A wrong passphrase must fail.
    wrong = _run(
        [
            sys.executable,
            str(ENCRYPTED_RESTORE),
            "--artefact",
            str(artefact),
            "--destination-url-env",
            "SZ_RESTORE_DEST_URL",
            "--passphrase-env",
            "SZ_WRONG_PASSPHRASE",
        ],
        env=_env(restore_env | {"SZ_WRONG_PASSPHRASE": "not-the-passphrase"}),
        expect_ok=False,
    )
    if wrong.returncode == 0:
        raise SystemExit("a wrong passphrase restored successfully; authentication is not enforced")

    # 4d. A restore into a non-empty target is refused.
    _run(["psql", args.restore_target, "-c", "CREATE TABLE IF NOT EXISTS drill_occupied (id int)"])
    nonempty = _run(
        [
            sys.executable,
            str(ENCRYPTED_RESTORE),
            "--artefact",
            str(artefact),
            "--destination-url-env",
            "SZ_RESTORE_DEST_URL",
            "--passphrase-env",
            "SZ_BACKUP_PASSPHRASE",
        ],
        env=restore_env,
        expect_ok=False,
    )
    if nonempty.returncode == 0:
        raise SystemExit("a restore into a non-empty target succeeded; the empty check is not working")

    # 5. Cleanup: remove the plaintext dump produced by the negative test.
    plain.unlink(missing_ok=True)
    (out_dir / "wrapped.dump.gz").unlink(missing_ok=True)
    corrupt.unlink(missing_ok=True)

    print(
        json.dumps(
            {
                "drill": "ok",
                "source_rows": expected,
                "manifest_count": evidence.get("scholarships"),
                "second_restore_rows": second,
                "artifact": str(artefact),
                "artifact_sha256": summary.get("ciphertext_sha256"),
                "gzip_artifact_refused": True,
                "corrupt_artifact_refused": True,
                "wrong_passphrase_refused": True,
                "non_empty_target_refused": True,
                "plaintext_removed": not plain.exists(),
            },
            indent=2,
        )
    )
    return 0


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    return urlparse(url).hostname or ""


if __name__ == "__main__":
    raise SystemExit(main())
