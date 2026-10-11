"""The restore path: it must be able to say no.

Restoring into production, restoring a corrupt artefact, restoring into SQLite,
or restoring without a passphrase each turn a recovery into something worse.
These tests assert the refusals, which is the part that matters, plus that a
decrypted artefact matches the digest it recorded.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    BACKEND_PYTHON,
    BackupCryptoError,
    CryptographyBackend,
    select_backend,
)

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "pg_restore.py"

PASSPHRASE = "test-passphrase-not-a-secret"


def _load_module():
    spec = importlib.util.spec_from_file_location("pg_restore_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def restore():
    return _load_module()


@dataclass
class Artefact:
    """A real encrypted artefact plus the bytes it should decrypt to."""

    path: Path
    plaintext: bytes


@pytest.fixture
def artefact(tmp_path):
    """A real encrypted artefact, so the restore path is exercised for real."""
    backend = CryptographyBackend()
    if not backend.available():
        pytest.skip("the cryptography package is not installed")
    plaintext = b"-- PostgreSQL database dump\n" + b"row" * 256
    payload = backend.encrypt(plaintext, PASSPHRASE)
    path = tmp_path / "backup.szbak"
    path.write_bytes(payload)
    return Artefact(path=path, plaintext=plaintext)


class TestRefusals:
    def test_no_passphrase_is_a_refusal(self, restore, monkeypatch, tmp_path, artefact):
        monkeypatch.delenv("SZ_BACKUP_PASSPHRASE", raising=False)
        args = _args(artefact.path)
        with pytest.raises(restore.RestoreRefused, match="not set"):
            restore.run_restore(args)

    def test_a_missing_artefact_is_a_refusal(self, restore, monkeypatch, tmp_path):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        args = _args(tmp_path / "does-not-exist.szbak")
        with pytest.raises(restore.RestoreRefused, match="no such artefact"):
            restore.run_restore(args)

    def test_no_destination_is_a_refusal(self, restore, monkeypatch, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.delenv("SZ_RESTORE_DEST_URL", raising=False)
        with pytest.raises(restore.RestoreRefused, match="not set"):
            restore.run_restore(_args(artefact.path))

    @pytest.mark.parametrize("marker", ["prod", "production", "PROD"])
    def test_a_production_destination_is_refused(
        self, restore, monkeypatch, artefact, marker
    ):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"postgresql://u:p@{marker}-host/db"
        )
        with pytest.raises(restore.RestoreRefused, match="production marker"):
            restore.run_restore(_args(artefact.path))

    def test_a_sqlite_destination_is_refused(self, restore, monkeypatch, artefact, tmp_path):
        """A SQLite round-trip is not evidence about a PostgreSQL restore.

        The same refusal `verify_recovery_path.py` makes, for the same reason:
        SQLite's type affinity means a round-trip through it validates a
        different database.
        """
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        sqlite_target = tmp_path / "d.db"
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"sqlite:///{sqlite_target.as_posix()}"
        )
        with pytest.raises(restore.RestoreRefused, match="not PostgreSQL"):
            restore.run_restore(_args(artefact.path))

    def test_a_wrong_passphrase_is_refused(self, restore, monkeypatch, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", "an-entirely-wrong-passphrase")
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://u:p@staging/db")
        with pytest.raises(restore.RestoreRefused, match="could not be decrypted"):
            restore.run_restore(_args(artefact.path))

    def test_a_tampered_artefact_is_refused(self, restore, monkeypatch, tmp_path, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://u:p@staging/db")

        payload = bytearray(artefact.path.read_bytes())
        payload[-1] ^= 0xFF
        tampered = tmp_path / "tampered.szbak"
        tampered.write_bytes(bytes(payload))

        with pytest.raises(restore.RestoreRefused, match="could not be decrypted"):
            restore.run_restore(_args(tampered))

    def test_a_missing_digest_is_refused(self, restore, monkeypatch, tmp_path, artefact):
        """An artefact that does not record its digest cannot be verified."""
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://u:p@staging/db")
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")

        from app.services.backup_crypto import read_manifest

        # Strip the digest line, keeping the rest of the framing intact.
        head, body = artefact.path.read_bytes().split(b"\n\n", 1)
        lines = [
            line for line in head.decode("utf-8").splitlines()
            if not line.startswith("plaintext_sha256=")
        ]
        forged = "\n".join(lines).encode("utf-8") + b"\n\n" + body
        stripped = tmp_path / "nodigest.szbak"
        stripped.write_bytes(forged)

        # The digest check happens before the restore, so this is caught.
        with pytest.raises(restore.RestoreRefused):
            restore.run_restore(_args(stripped))

    def test_the_refusal_carries_no_connection_string(
        self, restore, monkeypatch, artefact
    ):
        url = "postgresql://user:sup3rsecret@prod-host/db"
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", url)
        with pytest.raises(restore.RestoreRefused) as caught:
            restore.run_restore(_args(artefact.path))
        assert "sup3rsecret" not in str(caught.value)
        assert "prod-host" not in str(caught.value)


class TestDecryption:
    def test_an_artefact_decrypts_to_its_original_bytes(self, restore, monkeypatch, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        plaintext = restore._decrypt_artefact(artefact.path, PASSPHRASE)
        assert plaintext == artefact.plaintext

    def test_the_recorded_digest_matches(self, restore, monkeypatch, artefact):
        """The property the whole restore proof rests on."""
        import hashlib

        from app.services.backup_crypto import read_manifest

        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        plaintext = restore._decrypt_artefact(artefact.path, PASSPHRASE)
        header = read_manifest(artefact.path.read_bytes())
        assert header["plaintext_sha256"] == hashlib.sha256(plaintext).hexdigest()


def _args(artefact: Path):
    import argparse

    return argparse.Namespace(
        artefact=str(artefact),
        destination_url_env="SZ_RESTORE_DEST_URL",
        passphrase_env="SZ_BACKUP_PASSPHRASE",
    )
