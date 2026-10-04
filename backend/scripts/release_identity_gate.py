#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release identity gate: prove exactly one commit is running, or refuse.

The invariant
-------------
    EXPECTED_GIT_SHA
        == PLATFORM_GIT_SHA      (what the provider built)
        == ARTIFACT_SHA           (what the package recorded)
        == RUNTIME_HEALTH_SHA     (what is actually executing)

All four exactly forty lowercase hex characters and byte-for-byte equal. No
prefix, no alias, no hostname, no timestamp, no HTTP 200 alone.

Two layers, deliberately separate
----------------------------------
**Pure verification** (:func:`verify_identity`) receives already-fetched
payloads and performs deterministic comparison only. No network, no clock, no
environment. Everything that decides the outcome lives here, which is what makes
the whole rule set unit-testable from frozen payloads.

**Provider shell** (:func:`main`) resolves the deployment, fetches provider
metadata, reads ``/health`` from the *exact* deployment URL, and hands the
payloads to the pure function. All I/O stops at the boundary.

On provider metadata
---------------------
``vercel inspect --json`` returns ``id``, ``name`` (project), ``url``,
``target``, ``readyState``, ``contextName``, ``aliases`` and ``builds``. It
exposes **no ``gitSource``** - verified against the live CLI, not assumed. The
platform's own record of the commit it built is therefore read from the
provider's Git deployment record for that deployment id, whose ``sha`` is the
commit Vercel built. That is stated here rather than papered over, and
:func:`verify_identity` requires it to be supplied explicitly: a deployment
whose commit cannot be established is BLOCKED, never inferred.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.provenance import CANONICAL_SHA  # noqa: E402

#: Deterministic rejection reasons, used by the pure verifier.
OK = "ok"


# ---------------------------------------------------------------------------
# PURE VERIFICATION - no network, no clock, no environment
# ---------------------------------------------------------------------------


def _is_sha(value) -> bool:
    """Exactly forty lowercase hex characters. No normalisation, ever."""
    return isinstance(value, str) and CANONICAL_SHA.fullmatch(value) is not None


def verify_identity(
    expected_sha,
    platform_sha,
    runtime_revision,
    *,
    artifact_sha=None,
    project=None,
    expected_project=None,
    deployment_id=None,
    expected_deployment_id=None,
    deployment_url=None,
    expected_deployment_url=None,
    target=None,
    expected_target=None,
) -> dict:
    """Compare already-fetched identity payloads. Pure and deterministic.

    Returns ``{"ok": bool, "failures": [str, ...], "detail": {...}}``. Every
    failure is listed; the gate never stops at the first.
    """
    failures: list[str] = []

    # 1. expected must itself be canonical: a prefix expectation is a mistake,
    #    not something to relax at comparison time.
    if not _is_sha(expected_sha):
        failures.append(
            f"expected git sha is not exactly 40 lowercase hex characters: "
            f"{expected_sha!r}"
        )

    # 2. the provider's commit record
    if platform_sha is None:
        failures.append(
            "platform git sha is unavailable; the commit the provider built "
            "cannot be established (this is what a CLI deployment with no git "
            "source looks like)"
        )
    elif not _is_sha(platform_sha):
        failures.append(f"platform git sha is not canonical: {platform_sha!r}")

    # 3. the artefact, when it can be read directly. Not required: the runtime
    #    proves it reads only the artefact, and the artefact is not exposed by
    #    design.
    if artifact_sha is not None and not _is_sha(artifact_sha):
        failures.append(f"artifact sha is not canonical: {artifact_sha!r}")

    # 4. the runtime
    if not _is_sha(runtime_revision):
        failures.append(
            f"runtime /health revision is not canonical: {runtime_revision!r}"
        )

    # 5. exact equality - byte-for-byte, never a prefix comparison
    for label, value in (
        ("platform git sha", platform_sha),
        ("artifact sha", artifact_sha),
        ("runtime /health revision", runtime_revision),
    ):
        if value is not None and _is_sha(value) and _is_sha(expected_sha):
            if value != expected_sha:
                failures.append(f"{label} does not equal the expected commit")

    # 6. target and project identity
    if expected_target is not None and target != expected_target:
        failures.append(
            f"deployment target is {target!r}, expected {expected_target!r}; a "
            "preview must never satisfy a production verification"
        )
    if expected_project is not None and project != expected_project:
        failures.append(
            f"deployment project is {project!r}, expected {expected_project!r}"
        )
    if expected_deployment_id is not None and deployment_id != expected_deployment_id:
        failures.append(
            f"deployment id is {deployment_id!r}, expected {expected_deployment_id!r}"
        )
    if deployment_url is None:
        failures.append("no exact deployment url was resolved")
    if expected_deployment_url is not None and deployment_url is not None:
        # A production alias, a custom domain or a project alias is not a
        # deployment identity. Only the exact deployment url may answer.
        if deployment_url.rstrip("/") != expected_deployment_url.rstrip("/"):
            failures.append(
                f"queried {deployment_url!r} but the deployment under test is "
                f"{expected_deployment_url!r}; an alias is not a deployment identity"
            )

    return {
        "ok": not failures,
        "failures": failures,
        "detail": {
            "expected": expected_sha,
            "platform": platform_sha,
            "artifact": artifact_sha,
            "runtime": runtime_revision,
            "project": project,
            "deployment_id": deployment_id,
            "deployment_url": deployment_url,
            "target": target,
        },
    }


# ---------------------------------------------------------------------------
# PROVIDER / NETWORK SHELL - all I/O lives here
# ---------------------------------------------------------------------------


def _run_vercel(args: list[str]) -> dict:
    """Run the Vercel CLI and parse its JSON. Raises on unusable output."""
    result = subprocess.run(
        ["vercel", *args, "--json"],
        capture_output=True, text=True, timeout=180,
    )
    raw = result.stdout or ""
    start = raw.find("{")
    if start < 0:
        raise RuntimeError(
            f"vercel {' '.join(args)} produced no JSON "
            f"(exit {result.returncode}): {(result.stderr or raw)[:200]}"
        )
    return json.loads(raw[start:])


def fetch_deployment_metadata(deployment_url: str) -> dict:
    """Resolve provider metadata for one exact deployment URL."""
    data = _run_vercel(["inspect", deployment_url])
    return {
        "deployment_id": data.get("id"),
        "project": data.get("name"),
        "deployment_url": data.get("url") or deployment_url,
        "target": data.get("target"),
        "ready_state": data.get("readyState"),
    }


def fetch_platform_sha(deployment_url: str, repo: str) -> str | None:
    """The commit the provider built, from the provider's own git deployment.

    ``vercel inspect`` exposes no ``gitSource`` (verified against the live CLI),
    so the authoritative platform record used here is the git deployment the
    provider published for that deployment URL. Returns ``None`` when the
    deployment has no attributable git source, which the verifier treats as a
    failure rather than something to infer.
    """
    api_url = f"https://api.github.com/repos/{repo}/deployments?per_page=60"
    request = urllib.request.Request(
        api_url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "release-identity-gate/1",
        },
    )
    token = os.environ.get("GITHUB_TOKEN") or ""
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            deployments = json.loads(response.read().decode())
    except Exception:
        return None
    for deployment in deployments or []:
        try:
            statuses = json.loads(
                urllib.request.urlopen(
                    urllib.request.Request(
                        f"https://api.github.com/repos/{repo}/deployments/"
                        f"{deployment['id']}/statuses",
                        headers={
                            "Accept": "application/vnd.github+json",
                            "User-Agent": "release-identity-gate/1",
                            **({"Authorization": f"Bearer {token}"} if token else {}),
                        },
                    ),
                    timeout=60,
                ).read().decode()
            )
        except Exception:
            continue
        for status in statuses or []:
            url = status.get("target_url") or ""
            if url and url.rstrip("/") == deployment_url.rstrip("/"):
                return deployment.get("sha")
    return None


def fetch_runtime_revision(base_url: str) -> str | None:
    """Read /health from one exact deployment URL. Never an alias."""
    url = base_url.rstrip("/") + "/health"
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": "release-identity-gate/1"}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode()).get("revision")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        try:
            return json.loads(body).get("revision")
        except ValueError:
            return None
    except Exception:
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-sha", required=True,
                        help="exact 40-char commit sha that was released")
    parser.add_argument("--deployment-url", required=True,
                        help="the EXACT deployment url, never an alias")
    parser.add_argument("--expect-project")
    parser.add_argument("--expect-target")
    parser.add_argument("--expect-deployment-id")
    parser.add_argument("--expect-deployment-url",
                        help="the deployment url that must have answered")
    parser.add_argument("--artifact-sha", default=None,
                        help="only if the artefact can be read out of band")
    parser.add_argument("--repo", default="gopal735/ScholarZone")
    parser.add_argument("--offline-payload", default=None,
                        help="path to a frozen JSON payload; runs the pure "
                             "verifier with no network at all")
    args = parser.parse_args(argv)

    print("=== RELEASE IDENTITY GATE ===")

    if args.offline_payload:
        with open(args.offline_payload, encoding="utf-8") as handle:
            frozen = json.load(handle)
        if args.expected_sha and frozen.get("expected_sha") not in (None, args.expected_sha):
            print(f"  FAIL: --expected-sha {args.expected_sha!r} contradicts the "
                  f"frozen payload {frozen.get('expected_sha')!r}")
            print("\n  Do NOT certify this release. RELEASE_IDENTITY_BLOCKED")
            return 1
        result = verify_identity(
            frozen.get("expected_sha"),
            frozen.get("platform_sha"),
            frozen.get("runtime_revision"),
            artifact_sha=frozen.get("artifact_sha"),
            project=frozen.get("project"),
            expected_project=frozen.get("expected_project"),
            deployment_id=frozen.get("deployment_id"),
            expected_deployment_id=frozen.get("expected_deployment_id"),
            deployment_url=frozen.get("deployment_url"),
            expected_deployment_url=frozen.get("expected_deployment_url"),
            target=frozen.get("target"),
            expected_target=frozen.get("expected_target"),
        )
    else:
        try:
            meta = fetch_deployment_metadata(args.deployment_url)
        except Exception as exc:
            print(f"  provider metadata unavailable: {exc}")
            print("\n  RELEASE_IDENTITY_BLOCKED")
            return 2
        platform_sha = fetch_platform_sha(args.deployment_url, args.repo)
        runtime = fetch_runtime_revision(args.deployment_url)
        result = verify_identity(
            args.expected_sha,
            platform_sha,
            runtime,
            artifact_sha=args.artifact_sha,
            project=meta["project"],
            expected_project=args.expect_project,
            deployment_id=meta["deployment_id"],
            expected_deployment_id=args.expect_deployment_id,
            deployment_url=meta["deployment_url"],
            expected_deployment_url=args.expect_deployment_url or args.deployment_url,
            target=meta["target"],
            expected_target=args.expect_target,
        )

    detail = result["detail"]
    print(f"  PROJECT          : {detail['project']}")
    print(f"  DEPLOYMENT ID    : {detail['deployment_id']}")
    print(f"  DEPLOYMENT URL   : {detail['deployment_url']}")
    print(f"  TARGET           : {detail['target']}")
    print(f"  GIT SHA (expected): {detail['expected']}")
    print(f"  GIT SHA (platform): {detail['platform']}")
    print(f"  ARTIFACT SHA     : {detail['artifact'] or '(not readable by design)'}")
    print(f"  RUNTIME SHA      : {detail['runtime']}")
    exact = bool(result["ok"])
    print(f"  EXACT MATCH      : {'TRUE' if exact else 'FALSE'}")

    if exact:
        print("\n  RELEASE_IDENTITY_VERIFIED")
        return 0

    print()
    for failure in result["failures"]:
        print(f"  FAIL: {failure}")
    print("\n  Do NOT certify this release. RELEASE_IDENTITY_BLOCKED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())