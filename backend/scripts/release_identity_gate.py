"""Bind a deployment to the commit it was built from, and refuse anything else.

This exists because a healthy response is not evidence of a correct deployment.
``/api/health`` answers 200 for a build serving the wrong commit, the wrong
project, or - if a preview check is answered by a production alias - the wrong
environment entirely. A release gate that only asks "did it come up?" therefore
cannot tell a successful release from a stale one that happens to be healthy.

The check is a set of exact equalities, deliberately unforgiving:

* the deployment resolved from the platform must be the deployment that was
  asked about, compared by identifier **and** by URL;
* the commit must be a full forty-character lowercase hex SHA, never a prefix,
  because two commits can share twelve characters and a prefix comparison will
  happily accept the wrong build;
* the SHA the platform recorded must equal the SHA the running artefact reports;
* when the caller says which environment it means, the deployment must actually
  be in that environment, so a preview verification cannot be satisfied by the
  production alias.

The verification half is a pure function over two already-fetched payloads. No
network call happens inside it, which is what allows the rejections above to be
tested directly rather than inferred from a live deployment.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping

#: Exactly forty lowercase hex characters. Anchored, so nothing is accepted by
#: prefix, by extension, or with surrounding whitespace.
FULL_COMMIT_SHA = re.compile(r"\A[0-9a-f]{40}\Z")

TARGET_PRODUCTION = "production"
TARGET_PREVIEW = "preview"


class GateError(RuntimeError):
    """A gate input could not be interpreted at all."""


@dataclass(frozen=True)
class DeploymentIdentity:
    """What the platform says it built."""

    deployment_id: str
    deployment_url: str
    target: str
    git_ref: str | None
    git_sha: str | None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DeploymentIdentity":
        if not isinstance(payload, Mapping):
            raise GateError("deployment payload is not an object")
        git_source = payload.get("gitSource") or {}
        if not isinstance(git_source, Mapping):
            git_source = {}
        url = payload.get("url")
        if not isinstance(url, str) or not url.strip():
            raise GateError("deployment payload has no url")
        return cls(
            deployment_id=str(payload.get("id") or ""),
            deployment_url=url.strip(),
            target=str(payload.get("target") or ""),
            git_ref=(str(git_source.get("ref")) if git_source.get("ref") else None),
            git_sha=(str(git_source.get("sha")) if git_source.get("sha") else None),
        )


@dataclass(frozen=True)
class GateResult:
    """The verdict, with every reason it could fail."""

    ok: bool
    failures: tuple[str, ...]
    identity: DeploymentIdentity | None
    health_revision: str | None

    def describe(self) -> str:
        if self.ok:
            return (
                f"PASS deployment={self.identity.deployment_id} "
                f"ref={self.identity.git_ref} sha={self.identity.git_sha}"
            )
        return "FAIL\n  - " + "\n  - ".join(self.failures)


def normalise_url(value: str) -> str:
    """Compare URLs without being fooled by scheme or a trailing slash."""
    text = value.strip()
    if text.endswith("/"):
        text = text[:-1]
    if text.startswith("http://"):
        text = "https://" + text[len("http://") :]
    return text


def verify(
    deployment_payload: Mapping[str, Any],
    health_revision: str | None,
    *,
    requested_url: str | None = None,
    requested_deployment_id: str | None = None,
    expected_sha: str | None = None,
    expected_target: str | None = None,
) -> GateResult:
    """Check a deployment against the revision its own artefact reports.

    ``deployment_payload`` is the platform's record for the deployment, not for
    whatever alias happened to answer. ``requested_*`` are what the caller
    believed it was verifying; a mismatch is a failure rather than a convenience,
    because it means an alias stood in for the deployment.
    """
    try:
        identity = DeploymentIdentity.from_payload(deployment_payload)
    except GateError as error:
        return GateResult(ok=False, failures=(str(error),), identity=None,
                          health_revision=health_revision)

    failures: list[str] = []

    # 1. The deployment must be identifiable at all.
    if not identity.deployment_id:
        failures.append("deployment payload has no id")
    if requested_deployment_id and identity.deployment_id != requested_deployment_id:
        failures.append(
            f"deployment id mismatch: asked for {requested_deployment_id!r}, "
            f"platform returned {identity.deployment_id!r}"
        )

    # 2. The deployment must be the one that was asked about. This is what stops
    #    a production alias from satisfying a preview verification.
    if requested_url:
        if normalise_url(identity.deployment_url) != normalise_url(requested_url):
            failures.append(
                f"deployment url mismatch: asked for {normalise_url(requested_url)!r}, "
                f"platform returned {normalise_url(identity.deployment_url)!r}"
            )

    # 3. The environment must be the one that was asked about.
    if expected_target and identity.target != expected_target:
        failures.append(
            f"environment mismatch: expected {expected_target!r}, "
            f"deployment is {identity.target!r}"
        )

    # 4. A commit identity must exist and must be a full SHA.
    if not identity.git_ref:
        failures.append("deployment has no gitSource.ref")
    if not identity.git_sha:
        failures.append("deployment has no gitSource.sha")
    elif not FULL_COMMIT_SHA.match(identity.git_sha):
        failures.append(
            f"gitSource.sha {identity.git_sha!r} is not a full 40-character "
            "lowercase commit SHA"
        )

    # 5. The running artefact must report a full SHA too.
    #
    #    Deliberately NOT normalised. Trimming whitespace or lower-casing here
    #    would mean the gate accepts a value the artefact did not literally
    #    report, which is exactly the leniency this gate exists to remove: the
    #    application writes the SHA in a known form, so anything else is either a
    #    different artefact or a hand-edited response. The comparison below stays
    #    exact for the same reason.
    revision = health_revision or ""
    if not revision:
        failures.append("health endpoint reported no revision")
    elif not FULL_COMMIT_SHA.match(revision):
        failures.append(
            f"health revision {revision!r} is not a full 40-character lowercase "
            "commit SHA; a prefix is not an identity"
        )

    # 6. The exact equality the whole gate exists for.
    if (
        identity.git_sha
        and revision
        and FULL_COMMIT_SHA.match(identity.git_sha)
        and FULL_COMMIT_SHA.match(revision)
        and identity.git_sha != revision
    ):
        failures.append(
            f"identity mismatch: platform built {identity.git_sha}, "
            f"artefact reports {revision}"
        )

    # 7. An explicitly expected commit must be the one deployed.
    if expected_sha:
        wanted = expected_sha.strip().lower()
        if not FULL_COMMIT_SHA.match(wanted):
            failures.append(f"expected sha {expected_sha!r} is not a full commit SHA")
        elif identity.git_sha != wanted:
            failures.append(
                f"deployed commit {identity.git_sha!r} is not the expected {wanted!r}"
            )

    return GateResult(
        ok=not failures,
        failures=tuple(failures),
        identity=identity,
        health_revision=health_revision,
    )


# ---------------------------------------------------------------------------
# Network shell. Kept separate from ``verify`` so the rules above stay testable
# without a platform, a token, or a deployment.
# ---------------------------------------------------------------------------


def _fetch_json(url: str, *, token: str | None, timeout: float = 30.0) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def gate(
    deployment_url: str,
    *,
    token: str | None = None,
    expected_sha: str | None = None,
    expected_target: str | None = None,
    api_base: str = "https://api.vercel.com",
    timeout: float = 30.0,
) -> GateResult:
    """Resolve a deployment from the platform and verify it end to end.

    ``deployment_url`` must be the deployment's own URL. Pointing this at an
    alias is not a shortcut: the resolved deployment URL will not match and the
    gate fails, which is the intended outcome.
    """
    url = normalise_url(deployment_url)
    if not url:
        raise GateError("a deployment url is required")

    payload = _fetch_json(f"{api_base}/v13/deployment/{url}", token=token, timeout=timeout)
    identity = DeploymentIdentity.from_payload(payload)

    # Health is read from the deployment the platform named, not from whatever
    # the caller passed, so a substituted alias cannot influence the answer.
    health_url = normalise_url(identity.deployment_url) + "/api/health"
    try:
        health = _fetch_json(health_url, token=token, timeout=timeout)
        revision = health.get("revision") if isinstance(health, Mapping) else None
    except urllib.error.URLError as error:
        revision = None
        return GateResult(
            ok=False,
            failures=(f"could not read {health_url}: {error}",),
            identity=identity,
            health_revision=None,
        )

    return verify(
        payload,
        revision,
        requested_url=url,
        expected_sha=expected_sha,
        expected_target=expected_target,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: release_identity_gate.py <deployment-url> [--sha SHA] [--target production|preview]")
        return 2

    deployment_url = args[0]
    expected_sha = None
    expected_target = None
    for index, token in enumerate(args):
        if token == "--sha" and index + 1 < len(args):
            expected_sha = args[index + 1]
        if token == "--target" and index + 1 < len(args):
            expected_target = args[index + 1]

    token = None
    try:
        import os

        token = (os.getenv("VERCEL_TOKEN") or "").strip() or None
    except Exception:  # pragma: no cover - defensive only
        token = None

    result = gate(
        deployment_url,
        token=token,
        expected_sha=expected_sha,
        expected_target=expected_target,
    )
    print(result.describe())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())