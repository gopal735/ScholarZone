"""The restore path: it must be able to say no.

Restoring into production, restoring a corrupt artefact, restoring into SQLite,
or restoring without a passphrase each turn a recovery into something worse.
These tests assert the refusals, which is the part that matters, plus that a
decrypted artefact matches the digest it recorded.

The destination is checked against the same hostname allow-list and the same
known-production deny-list the backup source uses, because writing into a
database nobody named is the same mistake as reading from one. The production
Neon hostname is refused by name: it contains no "prod" substring, so the
substring check this replaced would have let a restore overwrite production -
and naming it in the allow-list does not help, because the deny-list wins.
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

from app.services.backup_crypto import CryptographyBackend  # noqa: E402
from app.services.backup_source import ALLOW_LIST_ENV  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "pg_restore.py"

PASSPHRASE = "test-passphrase-not-a-secret"

#: The production endpoint named in the audit. No "prod" substring, which is
#: what made the old destination guard wave it through.
PRODUCTION_URL = (
    "postgresql://user:PLACEHOLDER@ep-broad-block-ayrx86zn-pooler.c-5."
    "us-east-2.aws.neon.tech/dbname"
)
PRODUCTION_HOST = "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech"

#: An isolated recovery destination a repository owner would name on purpose.
APPROVED_HOST = "recovery-isolated.example.com"


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


def _approve(monkeypatch, *hosts: str) -> None:
    """Name the hosts a restore may write to; default-deny without it."""
    monkeypatch.setenv(ALLOW_LIST_ENV, ", ".join(hosts))


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

    def test_the_audited_production_host_is_refused(
        self, restore, monkeypatch, artefact
    ):
        """Restoring over production is a data loss plus a silent overwrite.

        The deny-list beats the allow-list: naming the production endpoint in
        configuration does not make a restore into it permittable. This is the
        host the audit documented, and it spells nothing out that a substring
        check could have caught.
        """
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", PRODUCTION_URL)
        _approve(monkeypatch, PRODUCTION_HOST)
        with pytest.raises(restore.RestoreRefused, match="known production endpoint"):
            restore.run_restore(_args(artefact.path))

    def test_a_destination_the_allow_list_does_not_name_is_refused(
        self, restore, monkeypatch, artefact
    ):
        """Default-deny in the destructive direction: writes need naming too."""
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/db"
        )
        _approve(monkeypatch, "some-other-isolated-host")
        with pytest.raises(restore.RestoreRefused, match="not in"):
            restore.run_restore(_args(artefact.path))

    def test_a_missing_allow_list_refuses_the_restore(
        self, restore, monkeypatch, artefact
    ):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/db"
        )
        monkeypatch.delenv(ALLOW_LIST_ENV, raising=False)
        with pytest.raises(restore.RestoreRefused, match=ALLOW_LIST_ENV):
            restore.run_restore(_args(artefact.path))

    @pytest.mark.parametrize("value", ["", "   ", ",", " , , "])
    def test_an_allow_list_that_names_nothing_refuses_the_restore(
        self, restore, monkeypatch, artefact, value
    ):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/db"
        )
        monkeypatch.setenv(ALLOW_LIST_ENV, value)
        with pytest.raises(restore.RestoreRefused, match="not set or is empty"):
            restore.run_restore(_args(artefact.path))

    def test_a_malformed_allow_list_refuses_the_restore(
        self, restore, monkeypatch, artefact
    ):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/db"
        )
        monkeypatch.setenv(ALLOW_LIST_ENV, f"postgres://{APPROVED_HOST}/dbname")
        with pytest.raises(restore.RestoreRefused, match="not a bare hostname"):
            restore.run_restore(_args(artefact.path))

    def test_an_approved_destination_is_accepted(
        self, restore, monkeypatch, artefact
    ):
        """The positive case: a named isolated host passes the destination check."""
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL",
            f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/dbname",
        )
        _approve(monkeypatch, APPROVED_HOST)

        identity = restore._assert_destination_is_isolated(
            f"postgresql://user:PLACEHOLDER@{APPROVED_HOST}/dbname"
        )
        assert identity.describe() == f"postgresql://{APPROVED_HOST}"
        assert "PLACEHOLDER" not in identity.describe()

    def test_a_sqlite_destination_is_refused(self, restore, monkeypatch, artefact, tmp_path):
        """A SQLite round-trip is not evidence about a PostgreSQL restore.

        The same refusal `verify_recovery_path.py` makes, for the same reason:
        SQLite's type affinity means a round-trip through it validates a
        different database.
        """
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        sqlite_target = tmp_path / "d.db"
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv(
            "SZ_RESTORE_DEST_URL", f"sqlite:///{sqlite_target.as_posix()}"
        )
        _approve(monkeypatch, "backup-a.example.com")
        with pytest.raises(restore.RestoreRefused, match="not PostgreSQL"):
            restore.run_restore(_args(artefact.path))

    def test_a_wrong_passphrase_is_refused(self, restore, monkeypatch, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", "an-entirely-wrong-passphrase")
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://user:PLACEHOLDER@staging/db")
        _approve(monkeypatch, "staging")
        with pytest.raises(restore.RestoreRefused, match="could not be decrypted"):
            restore.run_restore(_args(artefact.path))

    def test_a_tampered_artefact_is_refused(self, restore, monkeypatch, tmp_path, artefact):
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://user:PLACEHOLDER@staging/db")
        _approve(monkeypatch, "staging")

        payload = bytearray(artefact.path.read_bytes())
        payload[-1] ^= 0xFF
        tampered = tmp_path / "tampered.szbak"
        tampered.write_bytes(bytes(payload))

        with pytest.raises(restore.RestoreRefused, match="could not be decrypted"):
            restore.run_restore(_args(tampered))

    def test_a_missing_digest_is_refused(self, restore, monkeypatch, tmp_path, artefact):
        """An artefact that does not record its digest cannot be verified."""
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", "postgresql://user:PLACEHOLDER@staging/db")
        _approve(monkeypatch, "staging")
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

    def test_the_refusal_carries_no_credential(
        self, restore, monkeypatch, artefact
    ):
        url = f"postgresql://user:PLACEHOLDER@not-on-the-list/dbname"
        monkeypatch.setenv("SZ_BACKUP_PASSPHRASE", PASSPHRASE)
        monkeypatch.setattr(restore, "_which", lambda name: "pg_restore")
        monkeypatch.setenv("SZ_RESTORE_DEST_URL", url)
        _approve(monkeypatch, APPROVED_HOST)
        with pytest.raises(restore.RestoreRefused) as caught:
            restore.run_restore(_args(artefact.path))

        message = str(caught.value)
        # The host is named on purpose - an operator needs to know which host
        # was refused - but the credential and the URL itself are not.
        assert "PLACEHOLDER" not in message
        assert url not in message


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
