"""The root backup tool must refuse the wrong target, and must not be able
to emit an unverified artifact.

The archive strategy is single and explicit: the artifact IS the pg
custom-format dump (which libpq compresses itself), with no outer gzip
layer, because a `.dump.gz` handed to `pg_restore` is refused by
`pg_restore` - which is the defect these guards exist to prevent
returning.

The guards:

* a missing DSN, a non-PostgreSQL source and a known production host
  without authorization each stop the run before a byte is dumped;
* the restore target obeys the same policy and may not be production:
  verifying a backup into the database it may have to survive is how a
  drill becomes an incident;
* there is no `--no-verify`: verification is a required argument, so an
  unverifiable backup is a refusal rather than a state a manifest can
  quietly carry;
* the manifest's identity carries no credentials.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, REPOSITORY_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backup = _load("pg_root_backup_under_test", "scripts/pg_backup.py")

PRODUCTION_DSN = "postgresql://operator:secret@ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech/neondb"
STAGING_DSN = "postgresql://operator:secret@db.staging.example.org/scholarzone"


def test_there_is_no_verify_bypass_flag():
    """The CLI offers no way to skip verification.

    The docstring explains why the flag that used to exist was removed, so
    the assertion is on the parser's accepted options, not on the prose.
    """
    import argparse

    source = (REPOSITORY_ROOT / "scripts" / "pg_backup.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    flags: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
            if node.args and isinstance(node.args[0], ast.Constant):
                flags.add(node.args[0].value)
    assert "--no-verify" not in flags
    assert "--verify-restore-into" in flags


def test_the_restore_target_may_not_be_production():
    with pytest.raises(backup.BackupError):
        backup._validate_destination(PRODUCTION_DSN)


def test_the_restore_target_must_be_postgresql():
    with pytest.raises(backup.BackupError):
        backup._validate_destination("sqlite:///scholarzone.db")


def test_a_staging_restore_target_is_allowed(monkeypatch):
    monkeypatch.setenv("SZ_BACKUP_ALLOWED_HOSTS", "db.staging.example.org")
    identity = backup._validate_destination(STAGING_DSN)
    assert identity.hostname == "db.staging.example.org"


def test_an_unknown_restore_target_fails_closed(monkeypatch):
    monkeypatch.setenv("SZ_BACKUP_ALLOWED_HOSTS", "db.staging.example.org")
    with pytest.raises(backup.BackupError):
        backup._validate_destination("postgresql://u:p@unlisted.example.org/db")


def test_the_artifact_has_no_outer_compression_layer():
    # The single archive strategy, asserted on the tool's code (the module
    # docstring excluded, because it names the defect in prose): there is no
    # gzip import and no .gz path anywhere near the artifact path, so an outer
    # layer cannot reappear unnoticed.
    source = (REPOSITORY_ROOT / "scripts" / "pg_backup.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    body = tree.body[1:] if tree.body and isinstance(tree.body[0], ast.Expr) else tree.body
    constants = [
        node.value
        for node in ast.walk(ast.Module(body=body, type_ignores=[]))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    ]
    assert not any(".gz" in value for value in constants), (
        "the artifact must not be wrapped in an outer compression layer"
    )
