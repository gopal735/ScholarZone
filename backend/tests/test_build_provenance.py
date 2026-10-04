"""Build provenance: the running artefact can only claim what the build proved.

``build_revision()`` used to read ``VERCEL_GIT_COMMIT_SHA`` at runtime and
return twelve characters. That was wrong twice over: a runtime variable can be
set by a stale process while entirely different code is served, and a prefix is
not comparable to a commit, so the deployment gate could only ever compare
prefixes.

These tests pin the replacement:

* the **build** writes a full 40-character SHA into a generated module and fails
  closed on anything missing, malformed or truncated;
* the **runtime** reads only that module, and no environment variable, header or
  query string can move it.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND = Path(__file__).resolve().parents[1]
GENERATOR = BACKEND / "scripts" / "generate_build_revision.py"
ARTIFACT = BACKEND / "app" / "_build_revision.py"

VALID = "a" * 40
OTHER = "b" * 40


def run_generator(*args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GENERATOR), *args],
        capture_output=True,
        text=True,
        cwd=BACKEND,
        env=env,
    )


@pytest.fixture()
def clean_artifact():
    """Remove the generated module around a test so imports are honest."""
    if ARTIFACT.exists():
        ARTIFACT.unlink()
    yield
    if ARTIFACT.exists():
        ARTIFACT.unlink()


# --------------------------------------------------------------------- build


class TestBuildIsFailClosed:
    def test_full_sha_is_embedded_verbatim(self, clean_artifact):
        result = run_generator("--sha", VALID)
        assert result.returncode == 0, result.stderr
        assert ARTIFACT.exists()
        namespace: dict = {}
        exec(ARTIFACT.read_text(encoding="utf-8"), namespace)
        assert namespace["BUILD_REVISION"] == VALID

    def test_missing_sha_fails_the_build(self, clean_artifact):
        result = run_generator(env={"PATH": "/usr/bin:/bin"})
        assert result.returncode != 0
        assert "no commit SHA" in result.stderr
        assert not ARTIFACT.exists()

    @pytest.mark.parametrize(
        "bad",
        [
            ("a" * 12, "prefix"),
            ("a" * 7, "short"),
            ("a" * 39, "one short"),
            ("a" * 41, "one long"),
            ("main", "branch name"),
            ("ABCDEF1234" + "0" * 30, "uppercase"),
            ("g" * 40, "non-hex"),
            ("https://scholarzone.vercel.app", "deployment url"),
        ],
    )
    def test_malformed_or_truncated_sha_fails_the_build(self, clean_artifact, bad):
        value, label = bad
        result = run_generator("--sha", value)
        assert result.returncode != 0, f"{label} was accepted: {result.stdout}"
        assert not ARTIFACT.exists()

    def test_surrounding_whitespace_is_stripped_and_the_stored_value_is_clean(
        self, clean_artifact
    ):
        """A shell may hand over a trailing newline; the *stored* identity is still exact.

        What must never happen is a padded or shortened value being written
        through, so the assertion is on what lands in the artefact.
        """
        assert run_generator("--sha", "  " + VALID + "\n").returncode == 0
        namespace: dict = {}
        exec(ARTIFACT.read_text(encoding="utf-8"), namespace)
        assert namespace["BUILD_REVISION"] == VALID

    def test_uppercase_is_rejected_so_identity_is_canonical(self, clean_artifact):
        # A commit SHA is canonically lowercase; accepting uppercase would let two
        # different strings denote one commit.
        assert run_generator("--sha", ("A" * 40)).returncode != 0

    def test_local_development_can_opt_out(self, clean_artifact):
        result = run_generator("--allow-missing", env={"PATH": "/usr/bin:/bin"})
        assert result.returncode == 0
        namespace: dict = {}
        exec(ARTIFACT.read_text(encoding="utf-8"), namespace)
        assert namespace["BUILD_REVISION"] == "development"


# ------------------------------------------------------------------- runtime


@pytest.fixture()
def embedded(clean_artifact):
    """Import ``app.main`` with a generated artefact in place."""
    assert run_generator("--sha", VALID).returncode == 0
    import app._build_revision as generated

    import app.main as main_module

    importlib.reload(generated)
    importlib.reload(main_module)
    return main_module


class TestRuntimeCannotBeOverridden:
    def test_full_sha_is_reported(self, embedded, monkeypatch):
        assert embedded.build_revision() == VALID

    def test_runtime_platform_variable_cannot_override(self, embedded, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", OTHER)
        assert embedded.build_revision() == VALID, (
            "a runtime VERCEL_GIT_COMMIT_SHA must not be able to change build identity"
        )

    def test_runtime_build_revision_variable_cannot_override(self, embedded, monkeypatch):
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", OTHER)
        assert embedded.build_revision() == VALID

    def test_runtime_ref_cannot_override(self, embedded, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", "some-branch")
        assert embedded.build_revision() == VALID

    def test_no_truncation(self, embedded, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", OTHER)
        value = embedded.build_revision()
        assert len(value) == 40
        assert value != OTHER[:12]

    def test_health_returns_exactly_the_embedded_sha(self, embedded, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", OTHER)
        with TestClient(embedded.app) as client:
            response = client.get("/health")
            assert response.status_code == 200
            body = response.json()
        assert body["revision"] == VALID
        assert len(body["revision"]) == 40

    def test_request_input_cannot_influence_revision(self, embedded, monkeypatch):
        from fastapi.testclient import TestClient

        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", OTHER)
        with TestClient(embedded.app) as client:
            for path in (
                "/health?revision=deadbeef",
                "/health?VERCEL_GIT_COMMIT_SHA=" + OTHER,
            ):
                response = client.get(path)
                assert response.json()["revision"] == VALID
            response = client.get(
                "/health",
                headers={"X-Build-Revision": OTHER, "X-Forwarded-Commit": OTHER},
            )
            assert response.json()["revision"] == VALID


class TestNoArtifactIsNotAClaim:
    """Without a build artefact there is nothing to claim - and nothing to guess."""

    def test_local_checkout_reports_dev(self, clean_artifact, monkeypatch):
        import app.main as main_module

        monkeypatch.setattr(main_module, "_embedded_build_revision", lambda: None)
        monkeypatch.setattr(
            main_module, "get_settings", lambda: SimpleNamespace(environment="test")
        )
        assert main_module.build_revision() == "dev"

    def test_production_without_artifact_reports_unknown_not_a_sha(self, clean_artifact, monkeypatch):
        import app.main as main_module

        monkeypatch.setattr(main_module, "_embedded_build_revision", lambda: None)
        monkeypatch.setattr(
            main_module, "get_settings", lambda: SimpleNamespace(environment="production")
        )
        # The runtime is actively offering a SHA here. It must still be refused,
        # because there is no build artefact behind it.
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", OTHER)
        assert main_module.build_revision() == "unknown"


class TestArtifactIsNotCommitted:
    def test_generated_module_is_git_ignored(self):
        ignored = subprocess.run(
            ["git", "-C", str(BACKEND), "check-ignore", "-q", "app/_build_revision.py"],
            capture_output=True,
        )
        assert ignored.returncode == 0, (
            "the generated artefact must be git-ignored or a stale revision can be committed"
        )

    def test_build_wiring_runs_the_generator(self):
        config = json.loads((BACKEND / "vercel.json").read_text(encoding="utf-8"))
        assert "generate_build_revision.py" in config.get("buildCommand", "")