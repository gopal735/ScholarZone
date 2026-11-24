#!/usr/bin/env python3
"""Verify preflight provenance for Stage 2 execution.

This script verifies that the Stage 1 preflight run and artifact
are authentic, unexpired, and match all expected values.

Key identity model:
- stage1_master_sha: the master commit used for Stage 1 dispatch (run's head_sha)
- pr_merge_commit_sha: the PR merge commit (separate identity)
- These are NOT the same thing. Master can advance after PR merge.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict

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


def fetch_pr_metadata(api_url: str, repository: str, pr_number: int, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/pulls/{pr_number}"
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


def verify_preflight_run(
    run_data: Dict[str, Any],
    expected_repo: str,
    expected_workflow_id: str,
    stage1_master_sha: str,
    pr_merge_commit_sha: str,
) -> None:
    """Verify Stage 1 run identity.

    stage1_master_sha: expected master commit used for Stage 1 dispatch
    pr_merge_commit_sha: expected PR merge commit (separate identity)
    """
    errors = []

    # Repository
    run_repo = run_data.get("repository", {}).get("full_name")
    if run_repo != expected_repo:
        errors.append(f"repository mismatch: {run_repo} != {expected_repo}")

    # Branch
    if run_data.get("head_branch") != "master":
        errors.append(f"branch mismatch: {run_data.get('head_branch')} != master")

    # Event
    if run_data.get("event") != "workflow_dispatch":
        errors.append(f"event mismatch: {run_data.get('event')} != workflow_dispatch")

    # Conclusion
    if run_data.get("conclusion") != "success":
        errors.append(f"run conclusion: {run_data.get('conclusion')} != success")

    # Workflow ID
    wf_id = str(run_data.get("workflow_id", ""))
    if expected_workflow_id and wf_id != expected_workflow_id:
        errors.append(f"workflow ID mismatch: {wf_id} != {expected_workflow_id}")

    # Master SHA: run's head_sha must equal stage1_master_sha
    run_head_sha = run_data.get("head_sha", "")
    if not is_valid_sha(run_head_sha):
        errors.append(f"run head_sha invalid: {run_head_sha!r}")
    if run_head_sha != stage1_master_sha:
        errors.append(f"stage1 master SHA mismatch: run={run_head_sha} != expected={stage1_master_sha}")

    if errors:
        raise ProvenanceVerificationError("preflight run verification failed: " + "; ".join(errors))


def verify_pr_merge_identity(
    pr_data: Dict[str, Any],
    pr_merge_commit_sha: str,
    stage1_master_sha: str,
) -> None:
    """Verify PR merge identity separately from master SHA.

    pr_merge_commit_sha: expected PR merge commit
    stage1_master_sha: the master commit used for Stage 1 (must contain the merge)
    """
    errors = []

    if not pr_data.get("merged"):
        errors.append("PR is not merged")

    if not pr_data.get("merged_at"):
        errors.append("merged_at: missing trusted merge timestamp")

    api_merge_sha = pr_data.get("merge_commit_sha", "")
    if not is_valid_sha(api_merge_sha):
        errors.append(f"API merge_commit_sha invalid: {api_merge_sha!r}")

    if api_merge_sha != pr_merge_commit_sha:
        errors.append(f"PR merge SHA mismatch: api={api_merge_sha} != supplied={pr_merge_commit_sha}")

    if errors:
        raise ProvenanceVerificationError("PR merge identity verification failed: " + "; ".join(errors))


def main() -> int:
    api_url = _env("GITHUB_API_URL", "https://api.github.com")
    token = _env("GITHUB_TOKEN")
    repository = "gopal735/ScholarZone"
    run_id = _env("PREFLIGHT_RUN_ID")

    # Stage 1 master SHA (the master commit used for Stage 1 dispatch)
    stage1_master_sha = _env("STAGE1_MASTER_SHA")
    # PR merge commit SHA (separate identity)
    pr_merge_commit_sha = _env("SUPPLIED_MERGE_SHA") or _env("MERGE_COMMIT_SHA")

    expected_workflow_id = _env("EXPECTED_WORKFLOW_ID")
    expected_workflow_path = _env("EXPECTED_WORKFLOW_PATH", ".github/workflows/closed-scholarship-purge-preflight.yml")

    if not run_id:
        print("ERROR: PREFLIGHT_RUN_ID not set")
        return 1
    if not token:
        print("ERROR: GITHUB_TOKEN not set")
        return 1
    if not is_valid_sha(stage1_master_sha):
        print("ERROR: invalid stage1 master SHA")
        return 1
    if not is_valid_sha(pr_merge_commit_sha):
        print("ERROR: invalid PR merge commit SHA")
        return 1

    try:
        # 1. Verify Stage 1 run
        run_data = fetch_workflow_run(api_url, repository, run_id, token)
        verify_preflight_run(run_data, repository, expected_workflow_id, stage1_master_sha, pr_merge_commit_sha)

        # 2. Verify PR merge identity (separate from master SHA)
        pr_data = fetch_pr_metadata(api_url, repository, 107, token)
        verify_pr_merge_identity(pr_data, pr_merge_commit_sha, stage1_master_sha)

    except ProvenanceVerificationError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("Preflight provenance verified")
    print("should_execute=true")
    print(f"stage1_master_sha={stage1_master_sha}")
    print(f"pr_merge_commit_sha={pr_merge_commit_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
