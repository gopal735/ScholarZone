"""The backup orchestrator: every refusal, and one working backup.

Each "refuse" test is the important kind. A backup tool whose failure mode is
"write something plausible anyway" is worse than no backup, because it produces
an artefact nobody can restore while looking complete. So the assertions here are
about what does *not* happen.

The working-backup test uses a stub `pg_dump` that emits a small non-production
payload, so the whole path - dump, encrypt, round-trip verify, manifest, plaintext
removal - runs for real without a database.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    BACKEND_PYTHON,
    CryptographyBackend,
    select_backend,
)

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "pg_backup.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pg_backup_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def backup():
    return _load_module()


@pytest.fixture
def passphrase():
    return "test-passphrase-not-a-secret"


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_no_source_url_is_a_refusal(self, backup, monkeypatch, tmp_path, passphrase):
        monkeypatch.delenv("SZ_BACKUP_SOURCE_URL", raising=False)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="not set"):
            backup.run_backup(args)

    def test_no_passphrase_is_a_refusal(self, backup, monkeypatch, tmp_path):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        args = _args(backup, passphrase="", output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="no backup passphrase"):
            backup.run_backup(args)

    @pytest.mark.parametrize("marker", ["prod", "production", "PROD"])
    def test_a_production_source_is_refused(self, backup, monkeypatch, tmp_path, marker, passphrase):
        """A scheduled backup must not compete with the app for the free quota."""
        monkeypatch.setenv(
            "SZ_BACKUP_SOURCE_URL", f"postgresql://u:p@{marker}-host/db"
        )
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="production marker"):
            backup.run_backup(args)

    def test_no_dump_binary_is_a_refusal(self, backup, monkeypatch, tmp_path, passphrase):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        monkeypatch.setattr(backup, "_which", lambda name: None)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="pg_dump is not on PATH"):
            backup.run_backup(args)

    def test_a_projected_transfer_over_budget_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        """A backup that exhausts the free quota to save the data made things worse."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        _stub_dump(backup, monkeypatch, payload=b"x" * (64 * 1024 * 1024))
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path,
                     runs_per_month=1, max_monthly_mib=64)

        with pytest.raises(backup.BackupRefused, match="exceeds the"):
            backup.run_backup(args)

    def test_nothing_is_written_when_the_backup_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@prod-host/db")
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused):
            backup.run_backup(args)

        assert not any(tmp_path.iterdir()), "a refused backup left files behind"

    def test_the_refusal_message_carries_no_connection_string(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        url = "postgresql://user:sup3rsecret@staging-host/dbname"
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", url)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused) as caught:
            backup.run_backup(args)

        message = str(caught.value)
        assert "sup3rsecret" not in message
        assert "staging-host" not in message

    def test_no_crypto_backend_is_a_refusal(self, backup, monkeypatch, tmp_path, passphrase):
        """Encryption is not optional: without it there is no backup at all."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        _stub_dump(backup, monkeypatch, payload=b"dump")

        from app.services.backup_crypto import BackupCryptoUnavailable

        def _no_backend(name=None):
            raise BackupCryptoUnavailable(
                "no encryption backend is available; install openssl or the "
                "cryptography package. Refusing to write an unencrypted backup."
            )

        monkeypatch.setattr(backup, "select_backend", _no_backend)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        # The crypto module's own exception type becomes a single refusal kind,
        # so a caller handles "the backup did not happen" in one place.
        with pytest.raises(backup.BackupRefused, match="no encryption backend"):
            backup.run_backup(args)
        assert not any(tmp_path.iterdir()), "a refused backup wrote something"


# ---------------------------------------------------------------------------
# The working path
# ---------------------------------------------------------------------------


class TestWorkingBackup:
    def test_a_backup_produces_an_artefact_and_a_manifest(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        _stub_dump(backup, monkeypatch, payload=b"-- dump\n" + b"row" * 512)

        out = tmp_path / "out"
        args = _args(backup, passphrase=passphrase, output_dir=out)
        result = backup.run_backup(args)

        artefact = Path(result["artefact"])
        manifest = Path(result["manifest"])
        assert artefact.exists() and manifest.exists()

        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["outcome"] == "success"
        assert data["round_trip_verified"] is True
        assert data["backend"] == BACKEND_PYTHON
        assert data["ciphertext_sha256"] == result["ciphertext_sha256"]
        assert data["plaintext_bytes"] > 0

    def test_the_artefact_is_private_to_the_owner(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        """A ciphertext readable by every user on a shared runner is a leak risk."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)

        if os.name == "nt":
            pytest.skip("POSIX permission bits are not meaningful on Windows")
        mode = stat.S_IMODE(Path(result["artefact"]).stat().st_mode)
        assert mode == 0o600, oct(mode)

    def test_the_plaintext_is_removed(self, backup, monkeypatch, tmp_path, passphrase):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        seen: list[Path] = []

        real_mkdtemp = backup.tempfile.mkdtemp

        def _tracking_mkdtemp(*a, **kw):
            path = real_mkdtemp(*a, **kw)
            seen.append(Path(path))
            return path

        monkeypatch.setattr(backup.tempfile, "mkdtemp", _tracking_mkdtemp)
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        backup.run_backup(args)

        assert seen, "the dump never used a temporary directory"
        leftover = [p for p in seen[0].iterdir()]
        assert leftover == [], f"plaintext left behind: {leftover}"

    def test_the_manifest_describes_the_source_without_leaking_it(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        monkeypatch.setenv(
            "SZ_BACKUP_SOURCE_URL", "postgresql://user:sekret@localhost/db"
        )
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)
        data = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

        blob = json.dumps(data)
        assert "sekret" not in blob
        assert "localhost" not in blob
        assert data["source_identity"].startswith("postgres")

    def test_the_manifest_names_the_projected_transfer(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        _stub_dump(backup, monkeypatch, payload=b"x" * (4 * 1024 * 1024))

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out",
                     runs_per_month=4)
        result = backup.run_backup(args)
        data = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

        assert data["projected_monthly_transfer_mib"] > 0
        # Doubled: storing the artefact and someone downloading it both count.
        assert data["projected_monthly_transfer_mib"] == pytest.approx(
            result["plaintext_bytes"] * 4 * 2 / (1024 * 1024), rel=0.01
        )

    def test_the_artefact_decrypts_back_to_the_dump(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@localhost/db")
        payload = b"-- dump\n" + b"payload-bytes" * 256
        _stub_dump(backup, monkeypatch, payload=payload)

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)

        backend = select_backend(BACKEND_PYTHON)
        restored = backend.decrypt(Path(result["artefact"]).read_bytes(), passphrase)
        assert restored == payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _args(backup, *, passphrase, output_dir, runs_per_month=4, max_monthly_mib=512):
    import argparse

    return argparse.Namespace(
        source_url_env="SZ_BACKUP_SOURCE_URL",
        passphrase_env="SZ_BACKUP_PASSPHRASE",
        backend=None,
        output_dir=str(output_dir),
        runs_per_month=runs_per_month,
        max_monthly_mib=max_monthly_mib,
        passphrase=passphrase,
    )


def _stub_dump(backup, monkeypatch, *, payload: bytes) -> None:
    """Make `_dump` write a fixed payload instead of calling a real pg_dump."""

    def _fake_dump(source_url: str, destination: Path) -> int:
        destination.write_bytes(payload)
        return len(payload)

    monkeypatch.setattr(backup, "_dump", _fake_dump)
