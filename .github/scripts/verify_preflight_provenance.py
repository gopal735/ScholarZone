#!/usr/bin/env python3
"""Verify preflight provenance for Stage 2 execution.

This script verifies that the Stage 1 preflight run and artifact
are authentic, unexpired, and match all expected values.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

SHA_RE_PATTERN = None
import re
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProvenanceVerificationError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def is_valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value.strip()))


def fetch_workflow_run(api_url: str, repository: str, run_id: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/runs/{run_id}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "scholarzone-preflight-provenance",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ProvenanceVerificationError(f"GitHub API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise ProvenanceVerificationError(f"GitHub API request failed: {exc.reason}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ProvenanceVerificationError("GitHub API returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProvenanceVerificationError("GitHub API returned an unexpected payload")
    return data


def verify_preflight_run(run_data: Dict[str, Any], expected_repo: str, expected_sha: str) -> None:
    errors = []

    if run_data.get("repository", {}).get("full_name") != expected_repo:
        errors.append(f"repository mismatch: {run_data.get('repository', {}).get('full_name')} != {expected_repo}")

    if run_data.get("head_branch") != "master":
        errors.append(f"branch mismatch: {run_data.get('head_branch')} != master")

    if run_data.get("conclusion") != "success":
        errors.append(f"run conclusion: {run_data.get('conclusion')} != success")

    if run_data.get("head_sha") != expected_sha:
        errors.append(f"head SHA mismatch: {run_data.get('head_sha')} != {expected_sha}")

    if run_data.get("event") != "workflow_dispatch":
        errors.append(f"event mismatch: {run_data.get('event')} != workflow_dispatch")

    if errors:
        raise ProvenanceVerificationError("preflight run verification failed: " + "; ".join(errors))


def main() -> int:
    api_url = _env("GITHUB_API_URL", "https://api.github.com")
    token = _env("GITHUB_TOKEN")
    repository = "gopal735/ScholarZone"
    run_id = _env("PREFLIGHT_RUN_ID")
    expected_merge_sha = _env("SUPPLIED_MERGE_SHA")

    if not run_id:
        print("ERROR: PREFLIGHT_RUN_ID not set")
        return 1
    if not token:
        print("ERROR: GITHUB_TOKEN not set")
        return 1
    if not is_valid_sha(expected_merge_sha):
        print("ERROR: invalid merge commit SHA")
        return 1

    try:
        run_data = fetch_workflow_run(api_url, repository, run_id, token)
        verify_preflight_run(run_data, repository, expected_merge_sha)
    except ProvenanceVerificationError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Preflight provenance verified")
    print("should_execute=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
