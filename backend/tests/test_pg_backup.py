"""The backup orchestrator: every refusal, and one working backup.

Each "refuse" test is the important kind. A backup tool whose failure mode is
"write something plausible anyway" is worse than no backup, because it produces
an artefact nobody can restore while looking complete. So the assertions here are
about what does *not* happen.

The working-backup test uses a stub `pg_dump` that emits a small non-production
payload, so the whole path - dump, encrypt, round-trip verify, manifest, plaintext
removal - runs for real without a database.

Two of the refusals are the ones an audit asked for, and both are load-bearing
rather than defensive:

* **The production Neon hostname is refused, not filtered by naming.** The
  previous guard refused URLs containing "prod". The audited production endpoint
  is `ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech`, which contains
  no such substring, so it was admitted by the check written to exclude it. It is
  now named in a deny-list that beats the allow-list.
* **The transfer budget cannot be set by a caller.** It used to be a
  `workflow_dispatch` input, so anyone with dispatch rights could raise it for a
  run. It is now repository configuration with a default, and there is no
  argument that sets it - so a dispatch caller has nothing to override.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.backup_crypto import (  # noqa: E402
    BACKEND_PYTHON,
    select_backend,
)
from app.services.backup_source import ALLOW_LIST_ENV  # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
SCRIPT = BACKEND / "scripts" / "pg_backup.py"

#: The production endpoint named in the audit. It carries no "prod" substring,
#: which is why the old substring guard admitted it.
PRODUCTION_URL = (
    "postgresql://user:sup3rsecret@ep-broad-block-ayrx86zn-pooler.c-5."
    "us-east-2.aws.neon.tech/dbname"
)

#: An approved non-production source: named in the allow-list on purpose.
APPROVED_HOST = "backup-staging.example.com"
APPROVED_URL = f"postgresql://user:pass@{APPROVED_HOST}/dbname"


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


@pytest.fixture
def allow_approved(monkeypatch):
    """The configured state: one non-production host, named."""
    monkeypatch.setenv(ALLOW_LIST_ENV, APPROVED_HOST)


def _approve(monkeypatch, host: str = APPROVED_HOST) -> None:
    monkeypatch.setenv(ALLOW_LIST_ENV, host)


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


class TestRefusals:
    def test_no_source_url_is_a_refusal(self, backup, monkeypatch, tmp_path, passphrase):
        monkeypatch.delenv("SZ_BACKUP_SOURCE_URL", raising=False)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="not set"):
            backup.run_backup(args)

    def test_no_passphrase_is_a_refusal(self, backup, monkeypatch, tmp_path, allow_approved):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        args = _args(backup, passphrase="", output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="no backup passphrase"):
            backup.run_backup(args)

    def test_the_audited_production_host_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """The deny-list beats the allow-list: naming it changes nothing.

        This is the regression the audit asked for. The host contains no "prod"
        substring, so the guard that used to look for one admitted it.
        """
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", PRODUCTION_URL)
        _approve(monkeypatch, "ep-broad-block-ayrx86zn-pooler.c-5.us-east-2.aws.neon.tech")
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="known production endpoint"):
            backup.run_backup(args)

    def test_a_host_the_allow_list_does_not_name_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """Default-deny: an unnamed host is not a host anybody approved."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", "postgresql://u:p@some-other-host/db")
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="not in"):
            backup.run_backup(args)

    def test_a_missing_allow_list_refuses_every_source(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        """No configuration is not permission: it is a refusal to run."""
        monkeypatch.delenv(ALLOW_LIST_ENV, raising=False)
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match=ALLOW_LIST_ENV):
            backup.run_backup(args)

    @pytest.mark.parametrize("value", ["", "   ", ",", " , , "])
    def test_an_allow_list_that_names_nothing_refuses_every_source(
        self, backup, monkeypatch, tmp_path, passphrase, value
    ):
        monkeypatch.setenv(ALLOW_LIST_ENV, value)
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="not set or is empty"):
            backup.run_backup(args)

    def test_a_malformed_allow_list_refuses_the_run(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        """A half-pasted connection string must not silently match nothing."""
        monkeypatch.setenv(ALLOW_LIST_ENV, f"postgres://{APPROVED_HOST}/dbname")
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="not a bare hostname"):
            backup.run_backup(args)

    def test_no_dump_binary_is_a_refusal(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        monkeypatch.setattr(backup, "_which", lambda name: None)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="pg_dump is not on PATH"):
            backup.run_backup(args)

    def test_a_projected_transfer_over_budget_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """A backup that exhausts the free quota to save the data made things worse."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        # 96 MiB x 4 runs x 2 = 768 MiB, over the 512 MiB default.
        _stub_dump(backup, monkeypatch, payload=b"x" * (96 * 1024 * 1024))
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path,
                     runs_per_month=4)

        with pytest.raises(backup.BackupRefused, match="exceeds the"):
            backup.run_backup(args)

    def test_nothing_is_written_when_the_backup_is_refused(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", PRODUCTION_URL)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused):
            backup.run_backup(args)

        assert not any(tmp_path.iterdir()), "a refused backup left files behind"

    def test_the_refusal_message_carries_no_connection_string(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        url = "postgresql://user:sup3rsecret@staging-host/dbname"
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", url)
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused) as caught:
            backup.run_backup(args)

        message = str(caught.value)
        # The host is named on purpose - an operator needs to know which host
        # was refused - but never the credential, the database, or the URL.
        assert "sup3rsecret" not in message
        assert url not in message
        assert "dbname" not in message

    def test_no_crypto_backend_is_a_refusal(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """Encryption is not optional: without it there is no backup at all."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
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
# The transfer budget is configuration, not a caller's choice
# ---------------------------------------------------------------------------


class TestTransferBudgetIsNotCallerSet:
    def test_the_script_offers_no_budget_argument(self, backup):
        options = {
            option
            for action in backup._build_parser()._actions
            for option in action.option_strings
        }
        assert "--max-monthly-mib" not in options
        assert "--request-max-monthly-mib" not in options

    @pytest.mark.parametrize(
        "flag", ["--max-monthly-mib", "--request-max-monthly-mib"]
    )
    def test_a_caller_cannot_supply_a_budget_on_the_command_line(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved, flag
    ):
        """The audit's second finding: a dispatch input must not set the budget.

        Previously `--max-monthly-mib` was threaded from `workflow_dispatch`, so
        anyone able to press the button could raise the budget for a run. The
        argument no longer exists, so the run stops instead of accepting a
        number nobody was meant to be able to choose.
        """
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        monkeypatch.setattr(backup, "_dump", lambda url, dest: 0)
        out = tmp_path / "out"

        with pytest.raises(SystemExit):
            backup.main([
                "--source-url-env", "SZ_BACKUP_SOURCE_URL",
                "--passphrase-env", "SZ_BACKUP_PASSPHRASE",
                "--output-dir", str(out),
                flag, "999999",
            ])

        assert not out.exists() or not any(out.iterdir())

    def test_the_workflow_has_no_dispatch_budget_input(self):
        """The input is gone from the workflow, not just unused by the script."""
        import yaml

        workflow = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/database-backup.yml"
        ).read_text(encoding="utf-8")
        data = yaml.safe_load(workflow)

        assert "max_monthly_mib" not in data[True]["workflow_dispatch"]["inputs"]
        # ...and the budget is not smuggled in as an argument the script would
        # have to accept.
        assert "max-monthly-mib" not in workflow

    def test_the_workflow_passes_the_allow_list_and_the_budget_variable(self):
        """The allow-list must be configured for the run to be allowed at all."""
        import yaml

        data = yaml.safe_load(
            (
                Path(__file__).resolve().parents[2]
                / ".github/workflows/database-backup.yml"
            ).read_text(encoding="utf-8")
        )
        backup_job = data["jobs"]["backup"]
        run_step = next(
            step for step in backup_job["steps"] if step["name"] == "Produce the encrypted backup"
        )

        assert run_step["env"]["SZ_BACKUP_ALLOWED_HOSTS"] == "${{ vars.SZ_BACKUP_ALLOWED_HOSTS }}"
        assert run_step["env"]["SZ_BACKUP_MAX_MONTHLY_MIB"] == "${{ vars.SZ_BACKUP_MAX_MONTHLY_MIB }}"
        # The budget arrives as configuration through the environment.
        assert "--max-monthly-mib" not in run_step["run"]

    def test_the_default_budget_applies_when_nothing_is_configured(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.delenv(backup.BUDGET_ENV, raising=False)
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        # 192 MiB x 4 runs x 2 = 1536 MiB, over the 512 MiB default.
        _stub_dump(backup, monkeypatch, payload=b"x" * (192 * 1024 * 1024))
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path,
                     runs_per_month=4)

        with pytest.raises(backup.BackupRefused, match="512"):
            backup.run_backup(args)

    def test_a_configured_budget_is_used_when_set(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv(backup.BUDGET_ENV, "64")
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        # 32 MiB x 4 x 2 = 256 MiB: within the default, over 64.
        _stub_dump(backup, monkeypatch, payload=b"x" * (32 * 1024 * 1024))
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path,
                     runs_per_month=4)

        with pytest.raises(backup.BackupRefused, match="64"):
            backup.run_backup(args)

    @pytest.mark.parametrize("value", ["0", "-1", "plenty", "nan", "inf"])
    def test_an_invalid_budget_configuration_fails_closed(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved, value
    ):
        """A typo in the budget must disable the backup, not the budget."""
        monkeypatch.setenv(backup.BUDGET_ENV, value)
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        monkeypatch.setattr(backup, "_dump", _exploding_dump())
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match=backup.BUDGET_ENV):
            backup.run_backup(args)

    def test_an_absurd_budget_configuration_fails_closed(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """A budget that cannot be a fraction of a free tier is a mistake."""
        monkeypatch.setenv(backup.BUDGET_ENV, "999999")
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        monkeypatch.setattr(backup, "_dump", _exploding_dump())
        args = _args(backup, passphrase=passphrase, output_dir=tmp_path)

        with pytest.raises(backup.BackupRefused, match="sane ceiling"):
            backup.run_backup(args)

    def test_a_valid_budget_configuration_is_honoured(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv(backup.BUDGET_ENV, "4096")
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out",
                     runs_per_month=4)
        result = backup.run_backup(args)
        assert result["transfer_budget_mib"] == 4096


# ---------------------------------------------------------------------------
# The working path
# ---------------------------------------------------------------------------


class TestWorkingBackup:
    def test_a_backup_produces_an_artefact_and_a_manifest(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
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

    def test_the_approved_host_is_recorded_against_the_allow_list(
        self, backup, monkeypatch, tmp_path, passphrase
    ):
        """The artifact records which hosts were permitted, not just which was used."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        _approve(monkeypatch, f"{APPROVED_HOST}, backup-dr.example.com")
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)
        data = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

        assert data["allowed_hosts"] == ["backup-dr.example.com", APPROVED_HOST]
        assert data["source_identity"] == f"postgresql://{APPROVED_HOST}"

    def test_the_artefact_is_private_to_the_owner(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        """A ciphertext readable by every user on a shared runner is a leak risk."""
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)

        if os.name == "nt":
            pytest.skip("POSIX permission bits are not meaningful on Windows")
        mode = stat.S_IMODE(Path(result["artefact"]).stat().st_mode)
        assert mode == 0o600, oct(mode)

    def test_the_plaintext_is_removed(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
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
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv(
            "SZ_BACKUP_SOURCE_URL", "postgresql://user:sekret@backup-staging.example.com/db"
        )
        _stub_dump(backup, monkeypatch, payload=b"dump-data")

        args = _args(backup, passphrase=passphrase, output_dir=tmp_path / "out")
        result = backup.run_backup(args)
        data = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))

        blob = json.dumps(data)
        assert "sekret" not in blob
        assert "dbname" not in blob
        assert data["source_identity"].startswith("postgres")

    def test_the_manifest_names_the_projected_transfer(
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
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
        self, backup, monkeypatch, tmp_path, passphrase, allow_approved
    ):
        monkeypatch.setenv("SZ_BACKUP_SOURCE_URL", APPROVED_URL)
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


def _args(backup, *, passphrase, output_dir, runs_per_month=4):
    import argparse

    return argparse.Namespace(
        source_url_env="SZ_BACKUP_SOURCE_URL",
        passphrase_env="SZ_BACKUP_PASSPHRASE",
        backend=None,
        output_dir=str(output_dir),
        runs_per_month=runs_per_month,
        passphrase=passphrase,
    )


def _stub_dump(backup, monkeypatch, *, payload: bytes) -> None:
    """Make `_dump` write a fixed payload instead of calling a real pg_dump."""

    def _fake_dump(source_url: str, destination: Path) -> int:
        destination.write_bytes(payload)
        return len(payload)

    monkeypatch.setattr(backup, "_dump", _fake_dump)


def _exploding_dump():
    """A dump that must never be reached, and says so if it is."""

    def _never(source_url: str, destination: Path) -> int:
        raise AssertionError(
            "the dump ran before the budget and source checks had finished"
        )

    return _never
