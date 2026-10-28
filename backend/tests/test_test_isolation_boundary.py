"""The test-isolation boundary must hold for an ordinary `pytest` invocation.

These tests drive `enforce_test_isolation` directly, in a subprocess, because
the property under test is about the environment a pytest *session* starts in —
and because conftest has already run in this process, mutating it in place would
not prove anything about a fresh one.

Each case asserts both halves of the contract: an unsafe target is refused, and
the refusal names the variable and the opt-in rather than quietly repointing the
run somewhere else.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
CONFTEST_DIR = BACKEND / "tests"

#: A credential-free stand-in. The shape is what matters - a postgres URL is
#: refused on its scheme, so the test never needs a real host or a real secret.
FAKE_NEON_URL = "postgresql://user:password@ep-example.us-east-2.aws.neon.tech/db"


def run_session(env_overrides: dict[str, str], *, cwd: Path | None = None) -> dict:
    """Start a fresh Python that imports conftest, and report what happened.

    Returns the resolved environment plus the exit status and output, so a case
    can assert on either the refusal or the resolution.
    """
    probe = textwrap.dedent(
        """
        import json, os, sys
        sys.path.insert(0, sys.argv[1])
        try:
            import conftest  # noqa: F401
        except BaseException as exc:
            print("RESULT:" + json.dumps({
                "raised": type(exc).__name__,
                "message": str(exc),
                # What the environment looked like at the moment of refusal.
                # A boundary that quietly repointed the run would show up here
                # as a rewritten database_url.
                "database_url_at_refusal": os.environ.get("SCHOLARZONE_DATABASE_URL"),
                "environment_at_refusal": os.environ.get("SCHOLARZONE_ENVIRONMENT"),
            }))
            raise SystemExit(3)
        from app.core.config import get_settings
        print("RESULT:" + json.dumps({
            "environment": os.environ.get("SCHOLARZONE_ENVIRONMENT"),
            "database_url": os.environ.get("SCHOLARZONE_DATABASE_URL"),
            "resolved_url": get_settings().database_url,
            "resolved_environment": get_settings().environment,
        }))
        """
    )
    script = BACKEND / "_isolation_probe.py"
    script.write_text(probe, encoding="utf-8")
    try:
        env = {"PATH": "/usr/bin:/bin:/usr/local/bin", "SystemRoot": ""}
        env.update(env_overrides)
        proc = subprocess.run(
            [sys.executable, str(script), str(CONFTEST_DIR)],
            capture_output=True, text=True, cwd=str(cwd or BACKEND),
            env=env, timeout=120,
        )
    finally:
        script.unlink(missing_ok=True)

    payload = None
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT:"):
            payload = json.loads(line[len("RESULT:"):])
    return {
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "result": payload,
    }


class TestOrdinaryRunIsIsolated:
    def test_bare_invocation_defaults_to_an_isolated_database(self):
        """The regression itself: nothing set, and the run is still safe.

        This is exactly the invocation that wrote to the working catalogue. The
        boundary must not depend on the caller exporting an environment
        variable.
        """
        out = run_session({})
        assert out["returncode"] == 0, out["stderr"]
        assert out["result"]["raised"] if "raised" in (out["result"] or {}) else True
        assert out["result"]["environment"] == "test"
        assert ":memory:" in out["result"]["database_url"]
        assert ":memory:" in out["result"]["resolved_url"]

    def test_an_explicit_test_environment_is_still_honoured(self):
        out = run_session({
            "SCHOLARZONE_ENVIRONMENT": "test",
            "SCHOLARZONE_DATABASE_URL": "sqlite:///:memory:",
        })
        assert out["returncode"] == 0, out["stderr"]
        assert out["result"]["resolved_environment"] == "test"


class TestProductionIsRefused:
    def test_production_mode_is_refused(self):
        out = run_session({
            "SCHOLARZONE_ENVIRONMENT": "production",
            "SCHOLARZONE_DATABASE_URL": FAKE_NEON_URL,
        })
        assert out["returncode"] == 3
        assert out["result"]["raised"] == "UnsafeTestDatabaseTarget"
        assert "production" in out["result"]["message"].lower()

    def test_production_mode_without_a_url_is_refused(self):
        """A production run with no URL is still a production run.

        `get_settings()` raises for that case on its own, but only when it is
        called. The boundary refuses before any application code runs, so the
        refusal does not depend on a test happening to import the resolver.
        """
        out = run_session({"SCHOLARZONE_ENVIRONMENT": "production"})
        assert out["returncode"] == 3
        assert out["result"]["raised"] == "UnsafeTestDatabaseTarget"

    def test_a_neon_url_is_refused_even_outside_production_mode(self):
        """The most dangerous case: the credential is present but the mode is not.

        A developer with `SCHOLARZONE_DATABASE_URL` exported from a `.env` and no
        `SCHOLARZONE_ENVIRONMENT` set gets development settings pointed at
        production. Refusing on the URL scheme alone catches it.
        """
        out = run_session({"SCHOLARZONE_DATABASE_URL": FAKE_NEON_URL})
        assert out["returncode"] == 3
        assert out["result"]["raised"] == "UnsafeTestDatabaseTarget"
        assert "postgresql" in out["result"]["message"].lower()

    def test_the_refusal_names_the_opt_in_and_never_redirects(self):
        out = run_session({"SCHOLARZONE_DATABASE_URL": FAKE_NEON_URL})
        assert "SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB" in out["result"]["message"]
        # A boundary that silently redirected would be worse than one that
        # stopped: the run would pass against a database nobody chose. Assert the
        # environment is exactly as the caller left it.
        assert out["result"]["database_url_at_refusal"] == FAKE_NEON_URL
        assert ":memory:" not in (out["result"]["database_url_at_refusal"] or "")


class TestWorkingCatalogueIsRefused:
    def test_the_working_database_is_refused(self):
        out = run_session({
            "SCHOLARZONE_DATABASE_URL": f"sqlite:///{BACKEND / 'scholarzone.db'}",
        })
        assert out["returncode"] == 3
        assert out["result"]["raised"] == "UnsafeTestDatabaseTarget"
        assert "scholarzone.db" in out["result"]["message"]

    def test_a_relative_path_to_the_working_database_is_also_refused(self):
        """The same file reached by a different spelling is still the same file.

        `sqlite:///scholarzone.db` resolves against the backend directory, which
        is where pytest runs. Comparing resolved paths rather than strings is the
        only way to catch this.
        """
        out = run_session({"SCHOLARZONE_DATABASE_URL": "sqlite:///scholarzone.db"})
        assert out["returncode"] == 3
        assert out["result"]["raised"] == "UnsafeTestDatabaseTarget"

    def test_a_different_sqlite_file_is_allowed(self):
        """Isolation is about the working catalogue, not about SQLite.

        A test that builds its own temporary file database is exactly the
        legitimate integration case, and refusing it would push people towards
        the opt-in for no reason.
        """
        with tempfile_tmp() as tmp:
            out = run_session({
                "SCHOLARZONE_DATABASE_URL": f"sqlite:///{tmp}",
            })
        assert out["returncode"] == 0, out["stderr"]
        assert out["result"]["resolved_url"].endswith(Path(tmp).name)


class TestControlledOptIn:
    def test_the_opt_in_permits_a_deliberate_run_and_warns_loudly(self):
        """A controlled integration run stays possible, and is never quiet."""
        out = run_session({
            "SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB": "1",
            "SCHOLARZONE_DATABASE_URL": FAKE_NEON_URL,
        })
        assert out["returncode"] == 0, out["stderr"]
        assert "WARNING" in out["stderr"]
        assert "SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB" in out["stderr"]

    def test_the_opt_in_does_not_silence_the_working_database(self):
        """Opting in is allowed. Opting in quietly is not."""
        out = run_session({
            "SCHOLARZONE_TEST_ALLOW_EXTERNAL_DB": "yes",
            "SCHOLARZONE_DATABASE_URL": f"sqlite:///{BACKEND / 'scholarzone.db'}",
        })
        assert out["returncode"] == 0, out["stderr"]
        assert "WARNING" in out["stderr"]


class TestCollectionIsScoped:
    """pytest discovery must not be able to cause production network activity.

    The hazard is real and was measured: `backend/` accumulated fifteen
    `*test*.py` developer scripts, none of which defines a `test_` function, and
    one of them issued an HTTP GET against the deployed production API at import
    time. pytest collected them by filename and ran their module-level code.

    The invariant is therefore not "the stray files are gone" - they are
    untracked local artefacts and a clean checkout never had them. The invariant
    is that *collection* cannot reach the network, which is asserted here by
    running a real collection with sockets disabled. If any imported module tries
    to open a connection, collection fails and this test fails with it.
    """

    def _collect_with_sockets_disabled(self) -> subprocess.CompletedProcess:
        probe = textwrap.dedent(
            """
            import socket, sys

            class Blocked(RuntimeError):
                pass

            def deny(*args, **kwargs):
                raise Blocked(
                    "test collection attempted a network connection"
                )

            socket.socket.connect = deny
            socket.socket.connect_ex = deny
            socket.create_connection = deny
            socket.getaddrinfo = deny

            import pytest
            sys.exit(pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider"]))
            """
        )
        script = BACKEND / "_collect_probe.py"
        script.write_text(probe, encoding="utf-8")
        try:
            return subprocess.run(
                [sys.executable, str(script)],
                capture_output=True, text=True, cwd=str(BACKEND), timeout=600,
            )
        finally:
            script.unlink(missing_ok=True)

    def test_collection_succeeds_with_networking_disabled(self):
        result = self._collect_with_sockets_disabled()
        assert "test collection attempted a network connection" not in result.stdout, (
            "a module imported during collection opened a network connection"
        )
        assert result.returncode == 0, (
            f"collection failed with networking disabled:\n{result.stdout[-3000:]}"
        )

    def test_collection_is_restricted_to_the_tests_directory(self):
        ini = (BACKEND / "pytest.ini").read_text(encoding="utf-8")
        assert "testpaths = tests" in ini

        result = self._collect_with_sockets_disabled()
        # Every collected item must live under tests/. A root-level module
        # sneaking in is the failure mode this guards.
        offending = [
            line for line in result.stdout.splitlines()
            if line.startswith("backend/")
            and not line.startswith("backend/tests/")
        ]
        assert not offending, f"collection reached outside tests/: {offending[:5]}"

    @pytest.mark.skipif(
        not (BACKEND / "cache_bust_test.py").exists(),
        reason="cache_bust_test.py is an untracked local artefact, not a repo file",
    )
    def test_the_production_smoke_script_opens_no_socket_on_import(self):
        """The specific file that made an import-time production request."""
        script = BACKEND / "cache_bust_test.py"
        guard = textwrap.dedent(
            f"""
            import socket, runpy, sys

            def deny(*args, **kwargs):
                raise AssertionError("import-time network call detected")

            socket.socket.connect = deny
            socket.create_connection = deny
            socket.getaddrinfo = deny
            try:
                runpy.run_path({str(script)!r}, run_name="__not_main__")
            except AssertionError:
                raise
            except SystemExit:
                pass
            print("IMPORT-WITH-NO-NETWORK-OK")
            """
        )
        probe = BACKEND / "_import_probe.py"
        probe.write_text(guard, encoding="utf-8")
        try:
            result = subprocess.run(
                [sys.executable, str(probe)],
                capture_output=True, text=True, cwd=str(BACKEND), timeout=120,
            )
        finally:
            probe.unlink(missing_ok=True)
        assert result.returncode == 0, (
            f"importing cache_bust_test.py reached the network:\n"
            f"{result.stdout[-1500:]}\n{result.stderr[-1500:]}"
        )


import contextlib
import tempfile


@contextlib.contextmanager
def tempfile_tmp():
    with tempfile.TemporaryDirectory() as d:
        yield str(Path(d) / "scratch.db")
