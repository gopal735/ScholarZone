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
import shutil
import subprocess
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
    project: str | None
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
            project=(str(payload.get("name")) if payload.get("name") else None),
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
    """Compare URLs without being fooled by scheme, host case, or a trailing slash.

    The platform returns a deployment's ``url`` **without a scheme**
    (``scholarzone-fwzj-qor3eneld-gopal735s-projects.vercel.app``) while a caller
    will usually pass the full ``https://`` form. Both are normalised to the same
    absolute, lower-case, slash-free form so a difference in spelling cannot be
    mistaken for a different deployment.
    """
    text = value.strip()
    if text.endswith("/"):
        text = text[:-1]
    if text.startswith("http://"):
        text = "https://" + text[len("http://") :]
    if not text.startswith("https://"):
        text = "https://" + text
    return text.lower()


def verify(
    deployment_payload: Mapping[str, Any],
    health_revision: str | None,
    *,
    requested_url: str | None = None,
    requested_deployment_id: str | None = None,
    expected_sha: str | None = None,
    expected_target: str | None = None,
    expected_project: str | None = None,
    expected_artifact_sha: str | None = None,
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

    # 4. The project must be the one that was asked about. Two Vercel projects
    #    serve this repository from the same master branch, so a deployment that
    #    is otherwise perfectly valid can still be the wrong project's.
    if expected_project is not None:
        if identity.project is None:
            failures.append(
                "deployment payload does not name a project, so the intended "
                "project cannot be confirmed"
            )
        elif identity.project != expected_project:
            failures.append(
                f"project mismatch: expected {expected_project!r}, "
                f"deployment belongs to {identity.project!r}"
            )

    # 5. A commit identity must exist and must be a full SHA.
    if not identity.git_ref:
        failures.append("deployment has no gitSource.ref")
    if not identity.git_sha:
        failures.append("deployment has no gitSource.sha")
    elif not FULL_COMMIT_SHA.match(identity.git_sha):
        failures.append(
            f"gitSource.sha {identity.git_sha!r} is not a full 40-character "
            "lowercase commit SHA"
        )

    # 6. The running artefact must report a full SHA too.
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

    # 7. The exact equality the whole gate exists for.
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

    # 8. An explicitly expected commit must be the one deployed.
    if expected_sha:
        wanted = expected_sha.strip().lower()
        if not FULL_COMMIT_SHA.match(wanted):
            failures.append(f"expected sha {expected_sha!r} is not a full commit SHA")
        elif identity.git_sha != wanted:
            failures.append(
                f"deployed commit {identity.git_sha!r} is not the expected {wanted!r}"
            )

    # 9. The build artefact and the running revision must be the same commit.
    #    These are two different things in principle - one is what the build
    #    wrote into the package, the other is what the process reads back - so
    #    agreement is asserted rather than assumed. It is only checked when the
    #    caller supplies the artefact value, because the artefact lives inside
    #    the deployment and is not observable over HTTP.
    if expected_artifact_sha is not None:
        artifact = expected_artifact_sha.strip()
        if not FULL_COMMIT_SHA.match(artifact):
            failures.append(
                f"build artefact sha {expected_artifact_sha!r} is not a full "
                "40-character commit SHA"
            )
        elif revision and FULL_COMMIT_SHA.match(revision) and artifact != revision:
            failures.append(
                f"runtime reports {revision} but the build artefact holds {artifact}"
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


def vercel_cli_available() -> bool:
    """Whether an authenticated provider-side read is possible at all."""
    return _vercel_executable() is not None


def _vercel_executable() -> str | None:
    """The resolved Vercel CLI path.

    The absolute path is required rather than the bare name: Windows'
    ``CreateProcess`` neither searches ``PATH`` nor appends ``PATHEXT``, so
    ``["vercel", ...]`` fails with a file-not-found error even though the command
    works from a shell. Resolving once also avoids picking the PowerShell
    ``.ps1`` shim, which a direct process launch cannot execute at all.
    """
    return shutil.which("vercel") or shutil.which("vercel.cmd")


def _first_json_object(text: str, require: tuple[str, ...] = ()) -> Any:
    """Pull a JSON object out of CLI output, preferring one with ``require`` keys.

    The CLI can precede its payload with banners, and a deployment record
    contains nested objects of its own. Scanning for the first balanced brace
    would therefore happily return a nested fragment - which once produced a
    record with no ``gitSource`` at all and looked like missing metadata rather
    than a parsing mistake. When ``require`` is given, the first object actually
    carrying those keys wins.
    """
    fallback: Any = None
    depth = 0
    start = -1
    for index, character in enumerate(text):
        if character == "{":
            if depth == 0:
                start = index
            depth += 1
        elif character == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                try:
                    parsed = json.loads(text[start : index + 1])
                except json.JSONDecodeError:
                    start = -1
                    continue
                if isinstance(parsed, dict):
                    if fallback is None:
                        fallback = parsed
                    if all(key in parsed for key in require):
                        return parsed
                start = -1
    if require and fallback is None:
        raise GateError(f"no JSON object carrying {list(require)} in the CLI response")
    if fallback is None:
        raise GateError("no JSON object found in the CLI response")
    return fallback


def _cli_json(
    args: list[str], *, what: str, timeout: float, require: tuple[str, ...] = ()
) -> Any:
    """Run a read-only Vercel CLI command and parse its JSON output."""
    if not vercel_cli_available():
        raise GateError(
            f"cannot read {what}: the Vercel CLI is unavailable and no API token "
            "was supplied"
        )
    try:
        completed = subprocess.run(  # noqa: S603
            [_vercel_executable(), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise GateError(f"reading {what} timed out") from error
    if completed.returncode != 0:
        raise GateError(f"could not read {what} (exit {completed.returncode})")
    return _first_json_object(completed.stdout or "", require=require)


def deployment_payload(
    reference: str, *, token: str | None, timeout: float = 30.0
) -> Any:
    """Fetch a deployment's platform record, authenticated either way.

    ``reference`` may be a deployment id or a deployment URL, and resolution is
    two steps because the two sources answer different questions:

    * ``vercel inspect`` accepts a URL *or* an id and resolves either, but its
      summary **omits ``gitSource``** - so on its own it would report a
      deployment as having no commit provenance at all, which looks like missing
      metadata rather than a thinner endpoint.
    * the REST API returns the full record including ``gitSource``, but only
      resolves an **id**; both URL forms 404.

    So the id is resolved first, then the authoritative record is fetched by id.
    Both steps go through the Vercel CLI, which authenticates with the session it
    already holds - no new credential, and none read or logged here. A token is
    used instead when the environment provides one.
    """
    if token and reference.startswith("dpl_"):
        return _fetch_json(
            f"https://api.vercel.com/v13/deployments/{reference}",
            token=token,
            timeout=timeout,
        )

    summary = _cli_json(
        ["inspect", reference, "--format", "json"],
        what=f"deployment record for {reference}",
        timeout=timeout,
        require=("id", "url"),
    )

    deployment_id = summary.get("id") if isinstance(summary, dict) else None
    if not isinstance(deployment_id, str) or not deployment_id.startswith("dpl_"):
        # Nothing to key the authoritative fetch on. Returning the summary is
        # still honest: verify() will then refuse it for the missing git source.
        return summary

    return _cli_json(
        ["api", f"/v13/deployments/{deployment_id}"],
        what=f"deployment record {deployment_id}",
        timeout=timeout,
        require=("id", "url", "gitSource"),
    )


def authenticated_get_json(
    url: str,
    *,
    deployment: str | None = None,
    timeout: float = 90.0,
) -> Any:
    """GET a protected deployment URL through the Vercel CLI's own session.

    **Deployment Protection stays enabled.** It is a security boundary and this
    function does nothing to weaken it: ``vercel curl`` performs an authenticated
    read using credentials the CLI already holds, and it is read-only. Disabling
    protection, creating a bypass exception, or making the deployment URL public
    would all be worse than reporting that the identity could not be observed.

    No credential is read, passed or logged here. The CLI authenticates with its
    own stored session, so there is nothing secret in this process to leak.

    Raises ``GateError`` when an authenticated read is not possible, so the caller
    fails closed instead of quietly falling back to an alias.
    """
    if not vercel_cli_available():
        raise GateError(
            "the Vercel CLI is not available, so a protected deployment cannot "
            "be observed; Deployment Protection is left enabled"
        )

    command = [_vercel_executable(), "curl"]
    if deployment:
        command += ["--deployment", deployment]
    command.append(url)

    try:
        # shell=False: the URL and deployment id are arguments, never a command
        # line, so a crafted value cannot inject anything.
        completed = subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise GateError(f"authenticated read of {url} timed out") from error

    if completed.returncode != 0:
        # stderr can contain a session trace; it is summarised, never echoed, so
        # nothing credential-shaped reaches a log or a report.
        raise GateError(
            f"authenticated read of {url} failed with exit code "
            f"{completed.returncode}; Deployment Protection remains enabled"
        )

    return _first_json_object(completed.stdout or "", require=("revision",))


def gate(
    deployment_url: str,
    *,
    token: str | None = None,
    expected_sha: str | None = None,
    expected_target: str | None = None,
    expected_project: str | None = None,
    expected_artifact_sha: str | None = None,
    api_base: str = "https://api.vercel.com",
    timeout: float = 30.0,
) -> GateResult:
    """Resolve a deployment from the platform and verify it end to end.

    ``deployment_url`` must be the deployment's own URL. Pointing this at an
    alias is not a shortcut: the resolved deployment URL will not match and the
    gate fails, which is the intended outcome.

    ``expected_project`` matters here because two projects serve this repository
    from the same master branch. Without it, a perfectly valid deployment of the
    *other* project would satisfy the check.
    """
    url = normalise_url(deployment_url)
    if not url:
        raise GateError("a deployment url is required")

    payload = deployment_payload(url, token=token, timeout=timeout)
    identity = DeploymentIdentity.from_payload(payload)

    # Health is read from the deployment the platform named, not from whatever
    # the caller passed, so a substituted alias cannot influence the answer.
    #
    # The request is authenticated, because a per-deployment URL sits behind
    # Deployment Protection and an anonymous read returns the platform's
    # interstitial rather than the application. Protection stays enabled: this is
    # an authenticated observation of a protected resource, not a way around it.
    health_url = normalise_url(identity.deployment_url) + "/api/health"
    try:
        health = authenticated_get_json(health_url, deployment=identity.deployment_id or None)
    except GateError as error:
        return GateResult(
            ok=False,
            failures=(str(error),),
            identity=identity,
            health_revision=None,
        )

    revision = health.get("revision") if isinstance(health, Mapping) else None

    return verify(
        payload,
        revision,
        requested_url=url,
        expected_sha=expected_sha,
        expected_target=expected_target,
        expected_project=expected_project,
        expected_artifact_sha=expected_artifact_sha,
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(
            "usage: release_identity_gate.py <deployment-url> [--sha SHA] "
            "[--artifact SHA] [--target production|preview] [--project NAME]"
        )
        return 2

    deployment_url = args[0]
    expected_sha = None
    expected_target = None
    expected_project = None
    expected_artifact_sha = None
    for index, token in enumerate(args):
        if token == "--sha" and index + 1 < len(args):
            expected_sha = args[index + 1]
        if token == "--artifact" and index + 1 < len(args):
            expected_artifact_sha = args[index + 1]
        if token == "--target" and index + 1 < len(args):
            expected_target = args[index + 1]
        if token == "--project" and index + 1 < len(args):
            expected_project = args[index + 1]

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
        expected_project=expected_project,
        expected_artifact_sha=expected_artifact_sha,
    )
    print(result.describe())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())