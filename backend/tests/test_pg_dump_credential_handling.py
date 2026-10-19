"""pg_dump must never receive the credential in argv.

A connection string passed as `pg_dump --dbname <url>` puts the password
into the process table, where any process on the host can read it. These
tests pin the replacement: the credential travels through libpq's own
environment, the temporary pass file is created with owner-only
permissions, and it is deleted on every exit path - including the failure
path, which is the one that leaves a caller least likely to clean up.

The password used here is a deliberately-fake marker so a leak into argv
would be unmistakable in any assertion output.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]

PASSWORD = "MARKER-PASSWORD-NOT-A-REAL-SECRET"
SOURCE = f"postgresql://operator:{PASSWORD}@db.example.org:5433/scholarzone"


def _load(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


backup = _load("pg_encrypted_backup_under_test", "scripts/pg_backup.py")


class _RecordedProc:
    returncode = 0
    stdout = b""
    stderr = b""


def test_the_credential_env_creates_an_owner_only_passfile(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("PGPASSFILE", raising=False)
    env, passfile = backup._credential_env(SOURCE)
    assert passfile is not None, "a source with a password must use a pass file"
    assert passfile.exists()
    # POSIX: the mode really is owner-only. Windows has no POSIX permission
    # bits (os.chmod there only toggles the read-only flag), so on that
    # platform this test asserts the intent - that chmod was asked for
    # 0o600 - rather than a bit pattern the OS does not have.
    if os.name == "posix":
        assert oct(passfile.stat().st_mode & 0o777) == "0o600"
    else:
        seen = {}
        real_chmod = os.chmod
        monkeypatch.setattr(backup.os, "chmod", lambda p, m: (seen.setdefault("mode", m), real_chmod(p, m))[1])
        _, second = backup._credential_env(SOURCE)
        assert second is not None
        assert seen.get("mode") == 0o600, seen
        second.unlink()
    # The file holds the marker credential in pgpass form.
    body = passfile.read_text(encoding="utf-8")
    assert f"operator:{PASSWORD}" in body
    assert not any(line.strip() == PASSWORD for line in body.splitlines())
    env.pop("PGPASSFILE", None)
    passfile.unlink()


def test_the_credential_env_leaves_a_passordless_source_untouched(monkeypatch):
    monkeypatch.delenv("PGPASSFILE", raising=False)
    env, passfile = backup._credential_env("postgresql://operator@db.example.org/scholarzone")
    assert passfile is None
    assert env["PGPASSFILE"] == os.devnull


def test_dump_argv_carries_no_credential(monkeypatch, tmp_path):
    seen: dict[str, object] = {}

    def fake_run(command, env=None, capture_output=True, text=False, **kwargs):
        seen["command"] = command
        seen["env"] = env
        return _RecordedProc()

    monkeypatch.setattr(backup.subprocess, "run", fake_run)
    monkeypatch.setattr(backup, "_which", lambda name: f"/usr/bin/{name}")
    target = tmp_path / "dump.custom"
    target.write_bytes(b"x")

    backup._dump(SOURCE, target)

    command = list(seen["command"])
    flat = " ".join(str(part) for part in command)
    assert SOURCE not in flat, command
    assert PASSWORD not in flat, "the password must never appear in argv"
    # The username is passed as a flag because libpq needs one; it is not a
    # secret and the pass file is what authenticates it. The credential -
    # the password - is the argv exposure the change removes.
    if "--dbname" in command:
        dbname = str(command[command.index("--dbname") + 1])
        assert dbname == "scholarzone", dbname
        assert "@" not in dbname and "://" not in dbname and PASSWORD not in dbname
    # And the pass file pointer is in the environment, not the command.
    env = dict(seen["env"])
    assert str(env.get("PGPASSFILE", "")).endswith("pgpass-") or env.get("PGPASSFILE")


def test_dump_deletes_the_passfile_when_pg_dump_fails(monkeypatch, tmp_path):
    """The failure path is the one that leaks: prove it cleans up too."""
    created: list[Path] = []
    real_credential_env = backup._credential_env

    def tracking_credential_env(url):
        env, passfile = real_credential_env(url)
        if passfile is not None:
            created.append(passfile)
        return env, passfile

    def failing_run(command, env=None, capture_output=True, text=False, **kwargs):
        return subprocess.CompletedProcess(command, 2, b"", b"connection refused")

    monkeypatch.setattr(backup, "_credential_env", tracking_credential_env)
    monkeypatch.setattr(backup.subprocess, "run", failing_run)
    monkeypatch.setattr(backup, "_which", lambda name: f"/usr/bin/{name}")

    target = tmp_path / "dump.custom"
    try:
        backup._dump(SOURCE, target)
    except backup.BackupRefused:
        pass
    assert created, "the credential environment was never exercised"
    assert all(not path.exists() for path in created), [str(p) for p in created]


def test_the_manifest_identity_never_carries_the_credential():
    from app.services.backup_source import parse_source_url

    identity = parse_source_url(SOURCE, with_parts=True)
    described = identity.describe()
    assert PASSWORD not in described
    assert "operator" not in described
    assert described == "postgresql://db.example.org"
    # The parts exist only for the credential path, and repr hides them.
    assert PASSWORD not in repr(identity)
    assert PASSWORD not in str(identity)
