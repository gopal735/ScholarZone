"""Build provenance: the artefact, not the environment, names the build.

These tests exist because the previous implementation was wrong in a way no
test caught. It read ``VERCEL_GIT_COMMIT_SHA`` at runtime and trusted it on the
grounds that a platform identifier "cannot be falsified by hand". On this
platform it can: a preview built from ``00bc39d`` reported ``4edd154a3037`` while
Vercel's own deployment metadata recorded ``00bc39d``. Every test that existed
asserted the broken behaviour, so the defect passed a green suite.

The contract asserted here:

* The build artefact is the only source of the reported revision.
* No environment variable can override it - including the previously supported
  ``SCHOLARZONE_BUILD_REVISION``.
* No request header can influence it.
* A build on the platform with no usable commit SHA fails.
* A malformed or missing artefact fails safely rather than naming something.
* Nothing is ever truncated to a short SHA.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import build_provenance as provenance
from app.build_provenance import (
    DEVELOPMENT_MARKER,
    ProvenanceError,
    embed_build_revision,
    platform_commit_sha,
    read_embedded_revision,
)
from app.database import get_db
from app.main import app
from app.models import Base

BACKEND_ROOT = Path(__file__).resolve().parents[1]
COMMIT = "0123456789abcdef0123456789abcdef01234567"

PLATFORM_VARS = (
    "VERCEL",
    "VERCEL_GIT_COMMIT_SHA",
    "VERCEL_GIT_COMMIT_REF",
    "SCHOLARZONE_BUILD_REVISION",
)


@pytest.fixture(autouse=True)
def _clear_platform_env(monkeypatch):
    for name in PLATFORM_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def artifact(tmp_path, monkeypatch):
    """Redirect the artefact at a temporary path and restore it afterwards."""
    monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "build_revision.txt")
    return provenance.ARTIFACT


@pytest.fixture()
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'provenance.db'}")
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# --------------------------------------------------------------- embedding


class TestEmbedAtBuildTime:
    def test_a_platform_build_embeds_the_full_commit_sha(self, artifact, monkeypatch):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", COMMIT)
        assert embed_build_revision() == COMMIT
        assert artifact.read_text(encoding="utf-8").strip() == COMMIT

    def test_the_full_sha_is_written_not_a_prefix(self, artifact, monkeypatch):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", COMMIT)
        embed_build_revision()
        stored = artifact.read_text(encoding="utf-8").strip()
        assert stored == COMMIT
        assert len(stored) == 40, "a short SHA is not an identity"

    def test_local_development_embeds_the_development_marker(self, artifact, monkeypatch):
        monkeypatch.delenv("VERCEL", raising=False)
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        assert embed_build_revision() == DEVELOPMENT_MARKER
        assert artifact.read_text(encoding="utf-8").strip() == DEVELOPMENT_MARKER


# ------------------------------------------------------------ build failure


class TestBuildFailsWithoutAnIdentity:
    def test_a_platform_build_with_no_sha_is_refused(self, artifact, monkeypatch):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        with pytest.raises(ProvenanceError):
            embed_build_revision()

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("", id="empty"),
            pytest.param("abc", id="too-short"),
            pytest.param("main", id="branch-name"),
            pytest.param("latest", id="literal-latest"),
            pytest.param("unknown", id="literal-unknown"),
            pytest.param("rc/mentor-hardening", id="branch-ref"),
            pytest.param("https://scholarzone.vercel.app", id="deployment-url"),
            pytest.param("0123456789abcdef0123456789abcdef0123456", id="39-chars"),
            pytest.param("0123456789abcdef0123456789abcdef012345678", id="41-chars"),
            pytest.param("0123456789abcdef0123456789abcdef0123456g", id="non-hex"),
        ],
    )
    def test_a_malformed_sha_is_refused(self, artifact, monkeypatch, bad):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", bad)
        assert platform_commit_sha() is None
        with pytest.raises(ProvenanceError):
            embed_build_revision()

    def test_an_uppercase_sha_is_normalised_not_refused(self, artifact, monkeypatch):
        """Case is a formatting difference, not an identity difference."""
        upper = COMMIT.upper()
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", upper)
        assert platform_commit_sha() == COMMIT
        assert embed_build_revision() == COMMIT

    def test_a_refused_build_writes_no_artefact(self, artifact, monkeypatch):
        monkeypatch.setenv("VERCEL", "1")
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        with pytest.raises(ProvenanceError):
            embed_build_revision()
        assert not artifact.exists(), "a failed build must leave nothing to publish"

    @staticmethod
    def _run_build_script(tmp_path, env_extra):
        """Run the real build script against an isolated copy of the package.

        The script writes into the package it is imported from, so running it in
        place would leave a test SHA inside ``app/`` and every later assertion
        would read a developer's leftover instead of its own fixture.
        """
        package = tmp_path / "app"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        shutil.copyfile(
            BACKEND_ROOT / "app" / "build_provenance.py", package / "build_provenance.py"
        )
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        shutil.copyfile(
            BACKEND_ROOT / "scripts" / "embed_build_revision.py",
            scripts / "embed_build_revision.py",
        )
        env = {"PATH": "", "SYSTEMROOT": "", "PYTHONPATH": str(tmp_path), **env_extra}
        return subprocess.run(
            [sys.executable, str(scripts / "embed_build_revision.py")],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(tmp_path),
        )

    def test_the_build_script_exits_non_zero_without_a_sha(self, tmp_path, monkeypatch):
        """The build hook's contract is its exit status."""
        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "unused.txt")
        result = self._run_build_script(tmp_path, {"VERCEL": "1"})
        assert result.returncode == 1, result.stdout + result.stderr
        assert "BUILD FAILED" in result.stderr

    def test_the_build_script_succeeds_with_a_sha(self, tmp_path, monkeypatch):
        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "unused.txt")
        result = self._run_build_script(
            tmp_path, {"VERCEL": "1", "VERCEL_GIT_COMMIT_SHA": COMMIT}
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert COMMIT in result.stdout
        embedded = (tmp_path / "app" / "build_revision.txt").read_text(encoding="utf-8")
        assert embedded.strip() == COMMIT

    def test_the_build_script_never_touches_the_real_package(self, tmp_path, monkeypatch):
        """The shipped artefact must not be written by a test run."""
        self._run_build_script(
            tmp_path, {"VERCEL": "1", "VERCEL_GIT_COMMIT_SHA": COMMIT}
        )
        assert not (BACKEND_ROOT / "app" / "build_revision.txt").exists() or (
            BACKEND_ROOT / "app" / "build_revision.txt"
        ).read_text(encoding="utf-8").strip() != COMMIT


# ----------------------------------------------------------- reading it back


class TestReadEmbedded:
    def test_a_deployed_artefact_is_read_verbatim(self, artifact):
        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        assert read_embedded_revision() == COMMIT

    def test_the_development_marker_is_read_as_development(self, artifact):
        artifact.write_text(f"{DEVELOPMENT_MARKER}\n", encoding="utf-8")
        assert read_embedded_revision() == DEVELOPMENT_MARKER

    def test_a_missing_artefact_fails_safely(self, artifact):
        with pytest.raises(ProvenanceError):
            read_embedded_revision()

    @pytest.mark.parametrize(
        "bad",
        [
            pytest.param("main", id="branch-name"),
            pytest.param("latest", id="latest"),
            pytest.param("unknown", id="unknown"),
            pytest.param("4edd154a3037", id="twelve-char-prefix"),
            pytest.param("not-a-sha-at-all", id="garbage"),
            pytest.param("", id="empty"),
        ],
    )
    def test_a_malformed_artefact_fails_safely(self, artifact, bad):
        artifact.write_text(bad, encoding="utf-8")
        with pytest.raises(ProvenanceError):
            read_embedded_revision()


# ------------------------------------------ the runtime contract in main.py


class TestRuntimeUsesOnlyTheArtefact:
    def test_the_environment_cannot_override_the_embedded_revision(
        self, artifact, monkeypatch
    ):
        from app.main import build_revision

        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "b" * 40)
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "c" * 40)
        monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", "d" * 40)
        assert build_revision() == COMMIT

    def test_the_previously_supported_override_is_gone(self, artifact, monkeypatch):
        from app.main import build_revision

        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "b" * 40)
        assert build_revision() != "b" * 40
        assert build_revision() != ("b" * 40)[:12]

    def test_a_stale_runtime_variable_cannot_rewrite_history(
        self, artifact, monkeypatch
    ):
        """The exact failure this change exists to prevent.

        The artefact says one commit and the runtime environment claims another.
        The artefact must win, because it is what was compiled.
        """
        from app.main import build_revision

        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "4edd154a3037" + "0" * 28)
        assert build_revision() == COMMIT

    def test_health_reports_the_exact_full_sha(self, artifact, client, db):
        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["revision"] == COMMIT
        assert len(response.json()["revision"]) == 40

    def test_a_caller_cannot_influence_health(self, artifact, client, db):
        artifact.write_text(f"{COMMIT}\n", encoding="utf-8")
        response = client.get(
            "/health",
            headers={
                "X-Build-Revision": "b" * 40,
                "X-SCHOLARZONE-BUILD-REVISION": "c" * 40,
                "X-Forwarded-Host": "evil.example",
            },
        )
        assert response.status_code == 200
        assert response.json()["revision"] == COMMIT

    def test_health_fails_when_the_artefact_is_corrupt(self, artifact, client, db):
        artifact.write_text("whatever", encoding="utf-8")
        response = client.get("/health")
        assert response.status_code != 200, (
            "a corrupt artefact must not produce a healthy response"
        )

    def test_production_refuses_to_report_an_unverified_revision(
        self, artifact, monkeypatch
    ):
        from app.main import build_revision

        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "production")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", "postgresql://u:p@host/db")
        artifact.write_text("nonsense", encoding="utf-8")
        with pytest.raises(ProvenanceError):
            build_revision()

    def test_development_still_runs_without_an_artefact(self, artifact, monkeypatch):
        from app.main import build_revision

        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "development")
        assert not artifact.exists()
        assert build_revision() == DEVELOPMENT_MARKER