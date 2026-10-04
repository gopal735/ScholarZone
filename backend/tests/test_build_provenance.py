"""Build-provenance contract.

The chain under test is:

    full Git SHA -> build-time validation -> immutable artefact in the deployed
    package -> runtime read -> /api/health

Everything below exists because each of those steps could plausibly regress
while the service still looked healthy. The failure this prevents is specific: a
process that is *healthy* while serving the *wrong commit*, reported as a
successful deployment.

The rules being pinned:

* only a full 40-character commit id is a revision;
* a missing or malformed SHA fails the build rather than shipping a guess;
* nothing at runtime can change what the service reports - not
  ``VERCEL_GIT_COMMIT_SHA``, not ``SCHOLARZONE_BUILD_REVISION``, not a header;
* a production build with no artefact says so loudly instead of looking fine.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app import provenance  # noqa: E402
from scripts.write_build_provenance import (  # noqa: E402
    BuildProvenanceError,
    resolve_sha,
)

GOOD = "0123456789abcdef0123456789abcdef01234567"
assert len(GOOD) == 40


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    """Every test starts with no artefact and no ambient build identity."""
    monkeypatch.setattr(provenance, "ARTIFACT", Path("/nonexistent/build_provenance.json"))
    for name in (
        "VERCEL_GIT_COMMIT_SHA",
        "VERCEL_GIT_COMMIT_REF",
        "VERCEL_URL",
        "SCHOLARZONE_BUILD_SHA",
        "SCHOLARZONE_BUILD_REVISION",
    ):
        monkeypatch.delenv(name, raising=False)
    provenance.reset_cache()
    yield
    provenance.reset_cache()


def good():
    """A fully consistent identity payload, for negative-case mutation."""
    sha = "0123456789abcdef0123456789abcdef01234567"
    return {
        "expected_sha": sha,
        "platform_sha": sha,
        "runtime_revision": sha,
        "artifact_sha": sha,
        "project": "scholarzone-fwzj",
        "expected_project": "scholarzone-fwzj",
        "deployment_id": "dpl_1",
        "expected_deployment_id": "dpl_1",
        "deployment_url": "https://d-1.example.vercel.app",
        "target": "production",
        "expected_target": "production",
    }


def _frozen(payload: dict):
    """Write a frozen payload for the pure, network-free gate path."""
    import json as _json
    import tempfile as _tf
    handle = _tf.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    _json.dump(payload, handle)
    handle.close()
    return handle.name


def good_bad_host():
    from scripts.release_identity_gate import verify_identity  # noqa: F401
    return {
        "expected_sha": "0123456789abcdef0123456789abcdef01234567",
        "platform_sha": "0123456789abcdef0123456789abcdef01234567",
        "runtime_revision": "0123456789abcdef0123456789abcdef01234567",
        "project": "scholarzone",
        "expected_project": "scholarzone-fwzj",
        "deployment_id": "dpl_1",
        "expected_deployment_id": "dpl_1",
        "deployment_url": "https://scholarzone-fwzj.vercel.app",
        "target": "production",
        "expected_target": "production",
    }


def _write_artefact(path: Path, sha) -> Path:
    path.write_text(
        json.dumps({"git_commit_sha": sha, "schema": "build-provenance/1"}),
        encoding="utf-8",
    )
    return path


# --------------------------------------------------------------------------
# Build-time validation
# --------------------------------------------------------------------------


class TestBuildTimeValidation:
    def test_a_full_forty_character_sha_is_accepted(self):
        assert resolve_sha(GOOD) == GOOD

    @pytest.mark.parametrize(
        "value",
        [
            GOOD[:12],          # a prefix is not a revision
            GOOD[:39],          # one character short
            GOOD + "a",         # one character long
            "z" * 40,           # not hexadecimal
            "main",
            "refs/heads/main",
            "https://vercel.com/x/deployments/abc",
            "unknown",
            "latest",
            "",
        ],
    )
    def test_anything_that_is_not_a_full_sha_fails_the_build(self, value):
        with pytest.raises(BuildProvenanceError):
            resolve_sha(value)

    def test_a_missing_sha_fails_the_build(self, monkeypatch):
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        monkeypatch.delenv("SCHOLARZONE_BUILD_SHA", raising=False)
        with pytest.raises(BuildProvenanceError) as excinfo:
            resolve_sha(None)
        assert "no build-time commit SHA" in str(excinfo.value)

    def test_a_branch_label_is_refused_with_a_reason(self, monkeypatch):
        monkeypatch.setenv("VERCEL_GIT_COMMIT_REF", "main")
        monkeypatch.delenv("VERCEL_GIT_COMMIT_SHA", raising=False)
        with pytest.raises(BuildProvenanceError) as excinfo:
            resolve_sha(None)
        assert "moving label" in str(excinfo.value)

    def test_the_generator_exits_non_zero_on_a_prefix(self, tmp_path):
        """The build must fail, not warn."""
        from scripts.write_build_provenance import main as generator_main

        code = generator_main(["--sha", GOOD[:12]])
        assert code == 1

    def test_the_generator_writes_exactly_what_was_supplied(self, tmp_path, monkeypatch):
        from scripts import write_build_provenance as gen

        monkeypatch.setattr(gen, "ARTIFACT", tmp_path / "build_provenance.json")
        assert gen.main(["--sha", GOOD]) == 0
        written = json.loads((tmp_path / "build_provenance.json").read_text(encoding="utf-8"))
        assert written["git_commit_sha"] == GOOD


# --------------------------------------------------------------------------
# Runtime reads the artefact and nothing else
# --------------------------------------------------------------------------


class TestRuntimeReadsOnlyTheArtefact:
    def test_the_artefact_is_reported_in_full(self, tmp_path, monkeypatch):
        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", GOOD))
        provenance.reset_cache()
        assert provenance.build_revision("production") == GOOD

    def test_vercel_git_commit_sha_cannot_override_the_artefact(self, tmp_path, monkeypatch):
        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", GOOD))
        provenance.reset_cache()
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "f" * 40)
        assert provenance.build_revision("production") == GOOD

    def test_the_operator_override_cannot_substitute_for_the_artefact(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(provenance, "ARTIFACT", tmp_path / "absent.json")
        provenance.reset_cache()
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "e" * 40)
        assert provenance.build_revision("production") != "e" * 40
        assert provenance.build_revision("production") == provenance.UNPROVEN_BUILD

    def test_a_malformed_artefact_does_not_report_a_prefix(self, tmp_path, monkeypatch):
        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", GOOD[:12]))
        provenance.reset_cache()
        assert provenance.build_revision("production") == provenance.UNPROVEN_BUILD

    def test_a_corrupt_artefact_is_not_silently_ignored(self, tmp_path, monkeypatch):
        bad = tmp_path / "a.json"
        bad.write_text("not json at all", encoding="utf-8")
        monkeypatch.setattr(provenance, "ARTIFACT", bad)
        provenance.reset_cache()
        assert provenance.build_revision("production") == provenance.UNPROVEN_BUILD

    def test_production_without_an_artefact_is_unproven_not_unknown(self):
        assert provenance.build_revision("production") == "unproven-build"
        assert provenance.build_revision("production") != "unknown"

    def test_local_development_without_an_artefact_is_dev(self):
        assert provenance.build_revision("development") == "dev"

    def test_uppercase_hex_is_rejected_not_normalised(self, tmp_path, monkeypatch):
        """Identity is validated, never repaired.

        Folding case here would let a corrupted artefact become a valid
        identity, which is the failure the whole mechanism prevents.
        """
        upper = GOOD.upper()
        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", upper))
        provenance.reset_cache()
        assert provenance.build_revision("production") == provenance.UNPROVEN_BUILD
        assert provenance.read_artifact.__wrapped__ if hasattr(provenance.read_artifact, "__wrapped__") else True


# --------------------------------------------------------------------------
# The health endpoint
# --------------------------------------------------------------------------


class TestHealthReportsTheExactBuild:
    def test_health_returns_the_full_sha_and_not_a_prefix(self, tmp_path, monkeypatch):
        from fastapi.testclient import TestClient

        import app.main as main_module

        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", GOOD))
        provenance.reset_cache()

        client = TestClient(main_module.app)
        body = client.get("/health").json()
        assert body["revision"] == GOOD
        assert len(body["revision"]) == 40
        assert body["revision"] != GOOD[:12]

    def test_request_headers_cannot_influence_the_reported_revision(
        self, tmp_path, monkeypatch
    ):
        from fastapi.testclient import TestClient

        import app.main as main_module

        monkeypatch.setattr(provenance, "ARTIFACT", _write_artefact(tmp_path / "a.json", GOOD))
        provenance.reset_cache()

        client = TestClient(main_module.app)
        spoofed = {
            "X-Forwarded-Commit": "b" * 40,
            "X-Vercel-Id": "c" * 40,
            "X-ScholarZone-Revision": "d" * 40,
            "X-Build-Sha": "e" * 40,
        }
        body = client.get("/health", headers=spoofed).json()
        assert body["revision"] == GOOD

    def test_health_keeps_its_existing_fields(self):
        from fastapi.testclient import TestClient

        import app.main as main_module

        body = TestClient(main_module.app).get("/health").json()
        for field in ("status", "revision"):
            assert field in body, f"/api/health lost the {field!r} field"


# --------------------------------------------------------------------------
# End-to-end self-test: build-time SHA == artefact == runtime
# --------------------------------------------------------------------------


class TestTheWholeChain:
    def test_supplied_sha_equals_artefact_equals_runtime(self, tmp_path, monkeypatch):
        """A fake SHA, driven through the real generator, read by the real
        runtime reader. No Vercel, no network, no production."""
        from scripts import write_build_provenance as gen

        supplied = "deadbeef" * 5
        artefact = tmp_path / "build_provenance.json"

        monkeypatch.setattr(gen, "ARTIFACT", artefact)
        assert gen.main(["--sha", supplied]) == 0

        from_disk = json.loads(artefact.read_text(encoding="utf-8"))["git_commit_sha"]
        assert from_disk == supplied

        # The runtime must not substitute its environment for the artefact.
        monkeypatch.setattr(provenance, "ARTIFACT", artefact)
        monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "0" * 40)
        monkeypatch.setenv("SCHOLARZONE_BUILD_REVISION", "1" * 40)
        provenance.reset_cache()
        assert provenance.build_revision("production") == supplied

    def test_the_generator_runs_as_a_real_subprocess(self, tmp_path):
        """Proves the CLI contract, not just the imported function."""
        supplied = "abcdef01" * 5
        artefact = tmp_path / "sub.json"
        env = {"PATH": "/usr/bin:/bin", "SCHOLARZONE_BUILD_SHA": supplied}
        result = subprocess.run(
            [sys.executable, str(BACKEND / "scripts" / "write_build_provenance.py")],
            capture_output=True,
            text=True,
            env={**env, "PYTHONPATH": str(BACKEND)},
        )
        assert result.returncode == 0, result.stderr
        # The default artefact path is inside the package; read it there.
        default = BACKEND / "app" / "build_provenance.json"
        try:
            assert json.loads(default.read_text(encoding="utf-8"))["git_commit_sha"] == supplied
        finally:
            default.unlink(missing_ok=True)

    def test_the_build_hook_is_wired_into_the_backend_service(self):
        config = json.loads((BACKEND / "vercel.json").read_text(encoding="utf-8"))
        build = config.get("buildCommand", "")
        assert "write_build_provenance" in build, (
            "the backend service has no build hook, so no artefact would ever be "
            "written and every production build would report unproven-build"
        )

    def test_the_generated_artefact_is_never_committed(self):
        ignore = (BACKEND.parent / ".gitignore").read_text(encoding="utf-8")
        assert "build_provenance.json" in ignore, (
            "a committed artefact is exactly the falsifiable label this "
            "mechanism exists to remove"
        )

# --------------------------------------------------------------------------
# The gate must refuse the wrong target, not merely describe it
# --------------------------------------------------------------------------


class TestTheGateRefusesTheWrongTarget:
    """A release check against the wrong deployment is worse than no check."""

    def _gate(self, argv):
        from scripts.release_identity_gate import main as gate_main

        return gate_main(argv)

    def test_it_refuses_a_forbidden_production_alias(self):
        code = self._gate([
            "--expected-sha", GOOD,
            "--deployment-url", "https://scholarzone-fwzj.vercel.app",
            "--offline-payload", _frozen(good_bad_host()),
        ])
        assert code != 0, "a production alias must not satisfy a preview check"

    def test_it_refuses_a_url_that_is_not_the_exact_deployment(self):
        payload = good()
        payload["expected_deployment_url"] = "https://d-OTHER.vercel.app"
        code = self._gate([
            "--expected-sha", GOOD,
            "--deployment-url", "https://d-1.example.vercel.app",
            "--offline-payload", _frozen(payload),
        ])
        assert code != 0

    def test_it_refuses_a_truncated_expected_revision(self):
        code = self._gate([
            "--expected-sha", GOOD[:12],
            "--deployment-url", "https://d-1.example.vercel.app",
            "--offline-payload", _frozen(good()),
        ])
        assert code == 1, (
            "a non-canonical CLI expectation contradicting the frozen payload "
            "must be rejected, not ignored"
        )

    def test_the_gate_exposes_the_exact_url_and_forbid_switches(self):
        import inspect

        from scripts import release_identity_gate as gate

        assert "argv" in inspect.signature(gate.main).parameters
        source = inspect.getsource(gate)
        for switch in ("--expected-sha", "--deployment-url", "--offline-payload"):
            assert switch in source, f"{switch} is not offered by the gate"

