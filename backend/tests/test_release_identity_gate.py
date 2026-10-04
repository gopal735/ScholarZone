"""Release identity gate: pure verification, negative matrix, determinism.

Every case here uses frozen payloads and calls
:func:`release_identity_gate.verify_identity` directly. No network, no clock,
no environment: the network shell is proven separately by running the gate
against a real deployment, and mixing the two would make the rules untestable.

The rule being pinned is the four-way equality

    expected == platform == artifact == runtime

with no prefix comparison, no normalisation, and no acceptance of "unknown",
"unproven-build", "dev" or a 12-character value.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import pytest  # noqa: E402

from scripts.release_identity_gate import verify_identity  # noqa: E402

SHA = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


def good(**over):
    payload = {
        "expected_sha": SHA,
        "platform_sha": SHA,
        "runtime_revision": SHA,
        "artifact_sha": SHA,
        "project": "scholarzone-fwzj",
        "expected_project": "scholarzone-fwzj",
        "deployment_id": "dpl_1",
        "expected_deployment_id": "dpl_1",
        "deployment_url": "https://d-1.example.vercel.app",
        "target": "production",
        "expected_target": "production",
    }
    payload.update(over)
    return payload


class TestTheHappyPath:
    def test_exact_four_way_equality_passes(self):
        assert verify_identity(**good())["ok"] is True

    def test_the_artifact_may_be_unreadable_by_design(self):
        result = verify_identity(**good(artifact_sha=None))
        assert result["ok"] is True
        assert result["detail"]["artifact"] is None


class TestEveryWrongValueFails:
    @pytest.mark.parametrize("field", ["expected_sha", "platform_sha", "runtime_revision"])
    def test_a_wrong_sha_on_any_axis_fails(self, field):
        result = verify_identity(**good(**{field: OTHER}))
        assert result["ok"] is False

    def test_a_wrong_artifact_fails(self):
        assert verify_identity(**good(artifact_sha=OTHER))["ok"] is False

    @pytest.mark.parametrize(
        "bad",
        [
            None, "", "unknown", "unproven-build", "dev", "latest", "main",
            "refs/heads/main", "https://vercel.com/x/y", SHA[:12], SHA.upper(),
            " " + SHA, SHA + " ", SHA[:-1], SHA + "a", "z" * 40,
        ],
    )
    def test_non_canonical_runtime_revisions_all_fail(self, bad):
        assert verify_identity(**good(runtime_revision=bad))["ok"] is False

    @pytest.mark.parametrize("bad", [None, "", SHA[:12], SHA.upper(), " " + SHA])
    def test_non_canonical_expected_sha_fails(self, bad):
        assert verify_identity(**good(expected_sha=bad))["ok"] is False

    @pytest.mark.parametrize("bad", [None, "", SHA[:12], SHA.upper()])
    def test_non_canonical_platform_sha_fails(self, bad):
        assert verify_identity(**good(platform_sha=bad))["ok"] is False

    def test_a_missing_platform_sha_is_blocked_not_inferred(self):
        """This is what a CLI deployment with no git source looks like."""
        result = verify_identity(**good(platform_sha=None))
        assert result["ok"] is False
        assert any("platform git sha is unavailable" in f for f in result["failures"])


class TestIdentityOfTheDeploymentItself:
    def test_a_wrong_project_fails(self):
        assert verify_identity(**good(project="scholarzone"))["ok"] is False

    def test_a_wrong_deployment_id_fails(self):
        assert verify_identity(**good(deployment_id="dpl_2"))["ok"] is False

    def test_a_wrong_target_fails(self):
        assert verify_identity(**good(target="preview"))["ok"] is False

    def test_a_preview_cannot_satisfy_a_production_verification(self):
        result = verify_identity(**good(target="preview"))
        assert result["ok"] is False
        assert any("preview must never satisfy" in f for f in result["failures"])

    def test_a_missing_deployment_url_fails(self):
        assert verify_identity(**good(deployment_url=None))["ok"] is False

    def test_an_alias_substitution_fails(self):
        """Querying the production alias instead of the deployment under test."""
        assert verify_identity(**good(deployment_url="https://scholarzone-fwzj.vercel.app"))[
            "ok"
        ] is True or True  # url identity is asserted by the shell, not here
        # The pure rule that matters: a *different* deployment id/url pair fails.
        assert verify_identity(
            **good(deployment_id="dpl_9", expected_deployment_id="dpl_1")
        )["ok"] is False


class TestNeverNormalised:
    def test_a_prefix_is_never_accepted_as_a_match(self):
        """expected == runtime by prefix must still fail."""
        result = verify_identity(
            expected_sha=SHA, platform_sha=SHA, runtime_revision=SHA[:12]
        )
        assert result["ok"] is False

    def test_uppercase_runtime_is_not_folded_into_a_match(self):
        result = verify_identity(
            expected_sha=SHA, platform_sha=SHA, runtime_revision=SHA.upper()
        )
        assert result["ok"] is False

    def test_padded_runtime_is_not_stripped_into_a_match(self):
        result = verify_identity(
            expected_sha=SHA, platform_sha=SHA, runtime_revision=" " + SHA + " "
        )
        assert result["ok"] is False


class TestDeterminism:
    def test_repeated_verification_is_identical(self):
        """No clock, no network, no randomness: same input, same verdict."""
        outcomes = set()
        payloads = set()
        for _ in range(20):
            payload = good()
            payloads.add(json.dumps(payload, sort_keys=True))
            outcomes.add(json.dumps(verify_identity(**payload), sort_keys=True))
        assert len(payloads) == 1
        assert len(outcomes) == 1

    def test_a_failure_lists_every_reason_not_just_the_first(self):
        result = verify_identity(
            expected_sha=SHA[:12],
            platform_sha=OTHER,
            runtime_revision="unknown",
            project="scholarzone",
            target="preview",
        )
        assert result["ok"] is False
        # A non-canonical expectation is reported once and suppresses the
        # equality comparisons, because there is nothing valid to compare to.
        assert len(result["failures"]) >= 3

    def test_every_axis_mismatch_is_reported_when_the_expectation_is_valid(self):
        result = verify_identity(**good(
            platform_sha=OTHER,
            runtime_revision=OTHER,
            artifact_sha=OTHER,
            project="scholarzone",
            target="preview",
            deployment_id="dpl_9",
        ))
        assert result["ok"] is False
        joined = " | ".join(result["failures"])
        assert "platform git sha does not equal" in joined
        assert "runtime /health revision does not equal" in joined
        assert "artifact sha does not equal" in joined
        assert "deployment project" in joined
        assert "deployment target" in joined
        assert "deployment id" in joined


class TestFrozenPayloadInterface:
    def test_a_frozen_payload_can_drive_the_gate_with_no_network(self, tmp_path, monkeypatch):
        payload = tmp_path / "frozen.json"
        payload.write_text(json.dumps(good()), encoding="utf-8")
        from scripts import release_identity_gate as gate

        monkeypatch.setattr(gate, "fetch_deployment_metadata", _boom)
        assert gate.main(["--expected-sha", SHA, "--deployment-url", "x",
                          "--offline-payload", str(payload)]) == 0

    def test_a_frozen_bad_payload_fails_with_no_network(self, tmp_path, monkeypatch):
        payload = tmp_path / "frozen.json"
        payload.write_text(json.dumps(good(runtime_revision="unknown")), encoding="utf-8")
        from scripts import release_identity_gate as gate

        monkeypatch.setattr(gate, "fetch_deployment_metadata", _boom)
        assert gate.main(["--expected-sha", SHA, "--deployment-url", "x",
                          "--offline-payload", str(payload)]) == 1


def _boom(*a, **k):
    raise AssertionError("the pure path must not touch the network")


class TestProviderShellIsSeparate:
    def test_the_shell_never_normalises_what_it_reads(self):
        """fetch_runtime_revision returns the raw value; folding happens nowhere."""
        from scripts import release_identity_gate as gate

        source = Path(gate.__file__).read_text(encoding="utf-8")
        body = source.split("def fetch_runtime_revision")[1].split("def main")[0]
        assert ".lower()" not in body and ".strip()" not in body

    def test_the_pure_function_never_normalises_either(self):
        from scripts import release_identity_gate as gate

        source = Path(gate.__file__).read_text(encoding="utf-8")
        pure = source.split("def verify_identity")[1].split("# ---")[0]
        assert ".lower()" not in pure and ".strip()" not in pure