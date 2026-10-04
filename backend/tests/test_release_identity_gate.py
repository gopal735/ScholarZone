"""Tests for the release identity gate.

The gate is only worth having if it *refuses*. These tests are therefore mostly
negative: each one constructs a situation where a naive check would have passed
and asserts the gate rejects it. A gate test suite full of happy paths proves
nothing, because the failure this exists to prevent is a gate that says yes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from release_identity_gate import (  # noqa: E402
    TARGET_PREVIEW,
    TARGET_PRODUCTION,
    DeploymentIdentity,
    GateError,
    normalise_url,
    verify,
)

FULL_SHA = "4edd154a303715442a2f0517b052259e5f113cab"
OTHER_SHA = "3ee434c01f534e2cfd72300030316cdd27c33789"
DEPLOY_URL = "https://scholarzone-fwzj-oxfgjct80-gopal735s-projects.vercel.app"
ALIAS_URL = "https://scholarzone-fwzj.vercel.app"
GIT_ALIAS_URL = "https://scholarzone-fwzj-git-master-gopal735s-projects.vercel.app"
DEPLOY_ID = "dpl_4r7L19mHjj7WvfinDw4HMVawFaJA"
PROJECT = "scholarzone-fwzj"
OTHER_PROJECT = "scholarzone"
#: A value that must never be mistaken for an identity by any code path.
SENTINEL = "SENTINEL-NOT-A-COMMIT-abcdef"


def payload(**overrides):
    """A well-formed production deployment record."""
    base = {
        "id": DEPLOY_ID,
        "name": PROJECT,
        "url": DEPLOY_URL,
        "target": TARGET_PRODUCTION,
        "gitSource": {"type": "github", "ref": "master", "sha": FULL_SHA},
    }
    base.update(overrides)
    return base


class TestAcceptsOnlyAConclusiveMatch:
    def test_a_matching_deployment_and_artefact_passes(self):
        result = verify(payload(), FULL_SHA, requested_url=DEPLOY_URL)

        assert result.ok, result.failures
        assert result.identity is not None
        assert result.identity.git_sha == FULL_SHA

    def test_a_matching_deployment_passes_with_an_expected_commit(self):
        result = verify(payload(), FULL_SHA, expected_sha=FULL_SHA)

        assert result.ok, result.failures

    def test_a_url_difference_in_scheme_or_trailing_slash_is_not_a_mismatch(self):
        result = verify(
            payload(), FULL_SHA, requested_url=DEPLOY_URL + "/"
        )

        assert result.ok, result.failures
        assert normalise_url("http://x.test/") == "https://x.test"


class TestRejectsAnAliasStandingInForADeployment:
    """A production alias answering a preview check is the failure this exists for."""

    def test_a_production_alias_cannot_satisfy_a_preview_request(self):
        result = verify(
            payload(target=TARGET_PRODUCTION),
            FULL_SHA,
            requested_url=ALIAS_URL,
            expected_target=TARGET_PREVIEW,
        )

        assert not result.ok
        assert any("environment mismatch" in failure for failure in result.failures)

    def test_a_git_master_alias_is_rejected_when_the_deployment_is_requested(self):
        result = verify(payload(), FULL_SHA, requested_url=GIT_ALIAS_URL)

        assert not result.ok
        assert any("deployment url mismatch" in f for f in result.failures)

    def test_a_preview_verification_answered_by_production_is_rejected(self):
        result = verify(
            payload(target=TARGET_PRODUCTION),
            FULL_SHA,
            expected_target=TARGET_PREVIEW,
        )

        assert not result.ok
        assert any("environment mismatch" in failure for failure in result.failures)


class TestRejectsAPrefixSha:
    @pytest.mark.parametrize("reported", [FULL_SHA[:12], FULL_SHA[:7], FULL_SHA[:8]])
    def test_a_truncated_health_revision_is_refused(self, reported):
        result = verify(payload(), reported)

        assert not result.ok
        assert any("not a full 40-character" in failure for failure in result.failures)

    @pytest.mark.parametrize("reported", [FULL_SHA.upper(), FULL_SHA + "x", " " + FULL_SHA])
    def test_a_malformed_health_revision_is_refused(self, reported):
        result = verify(payload(), reported)

        assert not result.ok

    def test_a_truncated_platform_sha_is_refused(self):
        result = verify(
            payload(gitSource={"ref": "master", "sha": FULL_SHA[:12]}), FULL_SHA
        )

        assert not result.ok
        assert any("not a full 40-character" in failure for failure in result.failures)

    def test_a_missing_revision_is_refused(self):
        result = verify(payload(), None)

        assert not result.ok
        assert any("no revision" in failure for failure in result.failures)

    def test_a_development_marker_is_not_an_identity(self):
        result = verify(payload(), "dev")

        assert not result.ok


class TestRejectsTheWrongDeployment:
    def test_a_wrong_deployment_id_is_refused(self):
        result = verify(payload(), FULL_SHA, requested_deployment_id="dpl_somethingelse")

        assert not result.ok
        assert any("deployment id mismatch" in failure for failure in result.failures)

    def test_the_wrong_commit_built_versus_reported_is_refused(self):
        result = verify(payload(), OTHER_SHA)

        assert not result.ok
        assert any("identity mismatch" in failure for failure in result.failures)

    def test_a_deployment_of_a_different_expected_commit_is_refused(self):
        result = verify(payload(), FULL_SHA, expected_sha=OTHER_SHA)

        assert not result.ok
        assert any("not the expected" in failure for failure in result.failures)

    def test_an_expected_sha_that_is_itself_a_prefix_is_refused(self):
        result = verify(payload(), FULL_SHA, expected_sha=FULL_SHA[:12])

        assert not result.ok


class TestRejectsUnusableInput:
    def test_a_payload_without_a_url_is_rejected_rather_than_crashing(self):
        result = verify({"id": "dpl_x"}, FULL_SHA)

        assert not result.ok
        assert any("no url" in failure for failure in result.failures)

    def test_a_non_object_payload_is_rejected(self):
        result = verify(["not", "a", "mapping"], FULL_SHA)  # type: ignore[arg-type]

        assert not result.ok

    def test_a_deployment_with_no_git_source_is_rejected(self):
        result = verify({"id": "dpl_x", "url": DEPLOY_URL, "target": "production"}, FULL_SHA)

        assert not result.ok
        assert any("gitSource" in failure for failure in result.failures)

    def test_a_git_source_that_is_not_an_object_is_tolerated_as_absent(self):
        identity = DeploymentIdentity.from_payload(
            {"id": "dpl_x", "url": DEPLOY_URL, "gitSource": "nonsense"}
        )

        assert identity.git_sha is None
        assert identity.git_ref is None

    def test_identity_construction_rejects_a_non_mapping(self):
        with pytest.raises(GateError):
            DeploymentIdentity.from_payload("nonsense")  # type: ignore[arg-type]


class TestBindsTheProject:
    """Two projects serve this repository from the same master branch.

    Without an explicit project binding, a perfectly valid deployment of the
    *other* project would satisfy every other check.
    """

    def test_the_expected_project_must_match(self):
        result = verify(payload(), FULL_SHA, expected_project=PROJECT)

        assert result.ok, result.failures

    def test_a_deployment_of_the_wrong_project_is_refused(self):
        result = verify(payload(), FULL_SHA, expected_project=OTHER_PROJECT)

        assert not result.ok
        assert any("project mismatch" in failure for failure in result.failures)

    def test_a_deployment_that_names_no_project_cannot_confirm_the_intent(self):
        stripped = payload()
        stripped.pop("name")

        result = verify(stripped, FULL_SHA, expected_project=PROJECT)

        assert not result.ok
        assert any("does not name a project" in f for f in result.failures)

    def test_the_project_is_carried_on_the_identity(self):
        identity = DeploymentIdentity.from_payload(payload())

        assert identity.project == PROJECT


class TestContaminationHardening:
    """A release gate must not be satisfiable by leftover local state.

    The failure this guards against is real: an earlier engagement was misled by
    stale processes and a stray ``backend/scholarzone.db``. So each case below
    asserts that some *other* piece of state cannot make a check pass.
    """

    def test_a_stale_process_reporting_another_commit_cannot_pass(self):
        """A server left over from a previous build reports the wrong SHA."""
        result = verify(payload(), OTHER_SHA)

        assert not result.ok
        assert any("identity mismatch" in failure for failure in result.failures)

    def test_a_wrong_backend_cannot_pass(self):
        result = verify(payload(), FULL_SHA, requested_url=ALIAS_URL)

        assert not result.ok
        assert any("deployment url mismatch" in f for f in result.failures)

    def test_a_unique_sentinel_value_is_never_mistaken_for_an_identity(self):
        for value in (SENTINEL, "dev", "unknown", "unproven-build"):
            result = verify(payload(), value)

            assert not result.ok, value

    def test_the_gate_consults_no_database_and_no_ambient_state(self):
        """It reads two payloads and nothing else.

        Asserted structurally: if this module ever gained a database or engine
        import, the gate's answer could start depending on which local file it
        found, which is precisely the contamination being excluded.
        """
        import inspect

        import release_identity_gate as gate_module

        source = inspect.getsource(gate_module)

        for forbidden in ("sqlalchemy", "create_engine", "sessionmaker", "sqlite"):
            assert forbidden not in source, forbidden

    def test_contamination_is_reported_in_full_rather_than_the_first_symptom(self):
        """Several wrong things at once must all be named, not just the first.

        A partially-correct release is the dangerous state: one wrong project,
        one stale process and a truncated SHA must not collapse into a single
        vague complaint that a hurried reader could talk themselves past.
        """
        result = verify(
            payload(name=OTHER_PROJECT, gitSource={"ref": "master", "sha": SENTINEL}),
            SENTINEL,
            requested_url=ALIAS_URL,
            expected_project=PROJECT,
        )

        assert not result.ok
        assert len(result.failures) >= 4


class TestAuthenticatedObservationOfAProtectedDeployment:
    """A per-deployment URL sits behind Vercel Deployment Protection.

    An anonymous read of one returns the platform's interstitial, not the
    application. The gate therefore observes it through the Vercel CLI's own
    session. Protection is a security boundary: these tests exist to prove the
    gate can *authenticate* to observe a protected deployment without ever
    weakening, disabling, or routing around that boundary.
    """

    def _cli_result(self, stdout: str, returncode: int = 0):
        class Completed:
            pass

        completed = Completed()
        completed.stdout = stdout
        completed.stderr = ""
        completed.returncode = returncode
        return completed

    def test_the_authenticated_read_parses_the_health_payload(self, monkeypatch):
        import release_identity_gate as gate_module

        captured = {}

        def fake_run(command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            return self._cli_result('noise before {"status":"ok","revision":"%s"} after' % FULL_SHA)

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: "/usr/bin/vercel")
        monkeypatch.setattr(gate_module.subprocess, "run", fake_run)

        result = gate_module.authenticated_get_json(
            f"{DEPLOY_URL}/api/health", deployment=DEPLOY_ID
        )

        assert result["revision"] == FULL_SHA
        # Read-only, shell=False, and the deployment is named explicitly.
        # The executable is the *resolved* path rather than a bare "vercel":
        # Windows' CreateProcess neither searches PATH nor appends PATHEXT, so a
        # bare name fails even though the command works from a shell.
        command = captured["command"]
        assert command[0] == "/usr/bin/vercel"
        assert command[1] == "curl"
        assert "--deployment" in command
        assert DEPLOY_ID in command
        assert captured["kwargs"]["shell"] is False
        assert "-X" not in command
        assert "--prod" not in command

    def test_it_fails_closed_when_the_cli_is_unavailable(self, monkeypatch):
        import release_identity_gate as gate_module

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: None)

        with pytest.raises(gate_module.GateError) as caught:
            gate_module.authenticated_get_json(f"{DEPLOY_URL}/api/health")

        # The message must say protection was left alone, so a reader never
        # assumes the boundary was relaxed to make this pass.
        assert "Deployment Protection" in str(caught.value)

    def test_it_fails_closed_when_authentication_fails(self, monkeypatch):
        import release_identity_gate as gate_module

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: "/usr/bin/vercel")
        monkeypatch.setattr(
            gate_module.subprocess, "run", lambda *a, **k: self._cli_result("", 1)
        )

        with pytest.raises(gate_module.GateError) as caught:
            gate_module.authenticated_get_json(f"{DEPLOY_URL}/api/health")

        assert "remains enabled" in str(caught.value)

    def test_it_never_echoes_cli_stderr_which_may_carry_a_trace(self, monkeypatch):
        """A failed authenticated read must not leak session material."""
        import release_identity_gate as gate_module

        class Completed:
            stdout = ""
            stderr = "trace-id=secret-session-material token=abc123"
            returncode = 1

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: "/usr/bin/vercel")
        monkeypatch.setattr(gate_module.subprocess, "run", lambda *a, **k: Completed())

        with pytest.raises(gate_module.GateError) as caught:
            gate_module.authenticated_get_json(f"{DEPLOY_URL}/api/health")

        message = str(caught.value)
        assert "secret-session-material" not in message
        assert "abc123" not in message

    def test_output_with_no_json_object_is_refused(self, monkeypatch):
        import release_identity_gate as gate_module

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: "/usr/bin/vercel")
        monkeypatch.setattr(
            gate_module.subprocess,
            "run",
            lambda *a, **k: self._cli_result("<html>Protected Deployment</html>"),
        )

        with pytest.raises(gate_module.GateError):
            gate_module.authenticated_get_json(f"{DEPLOY_URL}/api/health")

    def test_the_interstitial_is_never_mistaken_for_a_health_payload(self, monkeypatch):
        """The failure this patch exists to avoid.

        An unauthenticated read of a protected URL returns an HTML login page.
        If that were accepted, the gate would compare a web page against a commit.
        """
        import release_identity_gate as gate_module

        monkeypatch.setattr(gate_module.shutil, "which", lambda _name: "/usr/bin/vercel")
        monkeypatch.setattr(
            gate_module.subprocess,
            "run",
            lambda *a, **k: self._cli_result("<html>Log in to Vercel</html>"),
        )

        with pytest.raises(gate_module.GateError):
            gate_module.authenticated_get_json(f"{DEPLOY_URL}/api/health")


class TestArtefactAgreement:
    """The artefact and the running revision are two things, so they are compared."""

    def test_a_matching_artefact_and_runtime_revision_pass(self):
        result = verify(payload(), FULL_SHA, expected_artifact_sha=FULL_SHA)

        assert result.ok, result.failures

    def test_a_runtime_revision_differing_from_the_artefact_is_refused(self):
        result = verify(payload(), FULL_SHA, expected_artifact_sha=OTHER_SHA)

        assert not result.ok
        assert any("build artefact holds" in failure for failure in result.failures)

    def test_a_malformed_artefact_value_is_refused(self):
        result = verify(payload(), FULL_SHA, expected_artifact_sha=SENTINEL)

        assert not result.ok

    def test_a_truncated_runtime_revision_still_fails_with_an_artefact_supplied(self):
        result = verify(payload(), FULL_SHA[:12], expected_artifact_sha=FULL_SHA)

        assert not result.ok
        assert any("not a full 40-character" in failure for failure in result.failures)

    def test_omitting_the_artefact_does_not_silently_pass_something_else(self):
        """Without an artefact value the check is skipped, not assumed to pass.

        The SHA format and identity equality still apply, so a truncated runtime
        revision cannot slip through just because nobody supplied the artefact.
        """
        result = verify(payload(), FULL_SHA[:12])

        assert not result.ok


class TestEveryFailureIsReported:
    def test_multiple_problems_are_all_listed_not_just_the_first(self):
        result = verify(
            payload(gitSource={"ref": "master", "sha": FULL_SHA[:12]}),
            FULL_SHA[:12],
            requested_url=ALIAS_URL,
            expected_target=TARGET_PREVIEW,
        )

        assert not result.ok
        # url, target, both SHA format checks, and the mismatch set.
        assert len(result.failures) >= 4

    def test_describe_reports_the_binding_on_success(self):
        described = verify(payload(), FULL_SHA).describe()

        assert described.startswith("PASS")
        assert FULL_SHA in described
        assert DEPLOY_ID in described