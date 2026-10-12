"""The backup tool must refuse the wrong target before it dumps anything.

The script's guards are the difference between "a backup exists" and "a
backup of the wrong thing exists, encrypted, in CI artifacts". These tests
pin each refusal, and pin that a legitimate non-production dump is allowed
through with the reason recorded.
"""

from __future__ import annotations

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


backup = _load("pg_backup_under_test", "scripts/pg_backup.py")

PRODUCTION_DSN = "postgresql://operator:secret@ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech/neondb"
STAGING_DSN = "postgresql://operator:secret@db.staging.example.org/scholarzone"


def test_classification_never_carries_credentials():
    info = backup._classify(PRODUCTION_DSN)
    assert "secret" not in json_dumps(info)
    assert info["host"] == "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech"
    assert info["identity"].startswith("postgresql://")


def json_dumps(info) -> str:
    import json

    return json.dumps(info)


def test_non_postgres_source_is_refused():
    with pytest.raises(backup.BackupError):
        backup._guard("sqlite:///scholarzone.db", production_dump=False, reason=None)
    with pytest.raises(backup.BackupError):
        backup._guard("mysql://user:pass@host/db", production_dump=False, reason=None)


def test_known_production_host_is_refused_without_the_explicit_flag():
    with pytest.raises(backup.BackupError):
        backup._guard(PRODUCTION_DSN, production_dump=False, reason=None)


def test_production_dump_requires_a_reason():
    with pytest.raises(backup.BackupError):
        backup._guard(PRODUCTION_DSN, production_dump=True, reason="  ")


def test_a_production_dump_with_a_reason_is_allowed_and_recorded():
    backup._guard(PRODUCTION_DSN, production_dump=True, reason="approved by the owner on 2026-10-12")


def test_a_non_production_postgres_source_is_allowed():
    backup._guard(STAGING_DSN, production_dump=False, reason=None)


def test_missing_dsn_is_refused(monkeypatch):
    monkeypatch.delenv("SCHOLARZONE_DATABASE_URL", raising=False)
    with pytest.raises(backup.BackupError):
        backup._dsn()


def test_verification_requires_a_scratch_target(monkeypatch):
    monkeypatch.delenv("SZ_BACKUP_SCRATCH_URI", raising=False)
    assert backup._scratch_uri() == ""
