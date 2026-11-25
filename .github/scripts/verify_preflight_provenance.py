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
from datetime import datetime
from typing import Any, Dict, List

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

REPOSITORY = "gopal735/ScholarZone"
PR_NUMBER = 107
EXPECTED_WORKFLOW_PATH_DEFAULT = ".github/workflows/closed-scholarship-purge-preflight.yml"

REQUIRED_ARTIFACTS = [
    "gate1-atomicity-result",
    "gate2-identity-result",
    "gate3-dependencies-result",
    "gate4-backup-result",
    "gate5-classification-result",
    "gate6-cycle-validation-result",
    "gate7-git-safety-result",
    "preflight-summary",
    "deletion-manifest",
]


class ProvenanceVerificationError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def is_valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value.strip()))


def is_valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value.strip().lower()))


def _request(url: str, token: str) -> Dict[str, Any]:
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


def fetch_workflow_run(api_url: str, repository: str, run_id: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/runs/{run_id}"
    return _request(url, token)


def fetch_pr_metadata(api_url: str, repository: str, pr_number: int, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/pulls/{pr_number}"
    return _request(url, token)


def fetch_workflows_list(api_url: str, repository: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/workflows"
    return _request(url, token)


def fetch_workflow_by_id(api_url: str, repository: str, workflow_id: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/workflows/{workflow_id}"
    return _request(url, token)


def fetch_artifacts(api_url: str, repository: str, run_id: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/actions/runs/{run_id}/artifacts"
    return _request(url, token)


def fetch_compare(api_url: str, repository: str, base: str, head: str, token: str) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/repos/{repository}/compare/{base}...{head}"
    return _request(url, token)


def resolve_canonical_workflow(api_url: str, repository: str, expected_path: str, token: str) -> str:
    """Resolve the canonical workflow ID by its path. Returns workflow id as str."""
    data = fetch_workflows_list(api_url, repository, token)
    workflows = data.get("workflows", [])
    if not isinstance(workflows, list):
        raise ProvenanceVerificationError("workflows list missing or invalid")
    matches = [w for w in workflows if isinstance(w, dict) and w.get("path") == expected_path]
    if len(matches) != 1:
        raise ProvenanceVerificationError(
            f"canonical workflow path not uniquely resolved: {expected_path} (matches={len(matches)})"
        )
    wf_id = matches[0].get("id")
    if wf_id is None:
        raise ProvenanceVerificationError("canonical workflow id missing")
    # Cross-check via direct fetch
    direct = fetch_workflow_by_id(api_url, repository, str(wf_id), token)
    if direct.get("path") != expected_path:
        raise ProvenanceVerificationError("canonical workflow path mismatch on direct fetch")
    return str(wf_id)


def verify_preflight_run(
    run_data: Dict[str, Any],
    expected_repo: str,
    expected_workflow_id: str,
    expected_workflow_path: str,
    stage1_master_sha: str,
    pr_merge_commit_sha: str,
) -> None:
    """Verify Stage 1 run identity. Fail closed."""
    errors = []

    if not isinstance(run_data, dict):
        raise ProvenanceVerificationError("run data not a dict")

    # Repository identity
    repo_obj = run_data.get("repository")
    run_repo = repo_obj.get("full_name") if isinstance(repo_obj, dict) else None
    if run_repo != expected_repo:
        errors.append(f"repository mismatch: {run_repo!r} != {expected_repo!r}")

    # Workflow id mandatory
    if not expected_workflow_id:
        errors.append("expected workflow id missing")
    wf_id = run_data.get("workflow_id")
    if wf_id is None:
        errors.append("run workflow_id missing")
    elif str(wf_id) != str(expected_workflow_id):
        errors.append(f"workflow ID mismatch: {wf_id} != {expected_workflow_id}")

    # Workflow path (if present)
    run_path = run_data.get("path") or run_data.get("workflow_path")
    if run_path is not None and run_path != expected_workflow_path:
        errors.append(f"workflow path mismatch: {run_path} != {expected_workflow_path}")

    # Branch
    if run_data.get("head_branch") != "master":
        errors.append(f"branch mismatch: {run_data.get('head_branch')!r} != 'master'")

    # Event
    if run_data.get("event") != "workflow_dispatch":
        errors.append(f"event mismatch: {run_data.get('event')!r} != 'workflow_dispatch'")

    # State/completion
    status = run_data.get("status")
    if status is not None and status != "completed":
        errors.append(f"run status not completed: {status!r}")
    if run_data.get("conclusion") != "success":
        errors.append(f"run conclusion: {run_data.get('conclusion')!r} != 'success'")

    # Run attempt
    attempt = run_data.get("run_attempt")
    if not (isinstance(attempt, int) and not isinstance(attempt, bool) and attempt >= 1):
        errors.append(f"invalid run_attempt: {attempt!r}")

    # Head SHA (stage1 master)
    run_head_sha = run_data.get("head_sha", "")
    if not is_valid_sha(run_head_sha):
        errors.append(f"run head_sha invalid: {run_head_sha!r}")
    if run_head_sha != stage1_master_sha:
        errors.append(f"stage1 master SHA mismatch: run={run_head_sha} != expected={stage1_master_sha}")

    # Timestamps
    created_at = run_data.get("created_at")
    updated_at = run_data.get("updated_at")
    if not created_at:
        errors.append("created_at missing")
    if not updated_at:
        errors.append("updated_at missing")
    for ts_name, ts_val in (("created_at", created_at), ("updated_at", updated_at)):
        if ts_val:
            try:
                val = ts_val
                if val.endswith("Z"):
                    val = val[:-1] + "+00:00"
                datetime.fromisoformat(val)
            except (ValueError, TypeError):
                errors.append(f"unparseable {ts_name}: {ts_val!r}")

    if errors:
        raise ProvenanceVerificationError("preflight run verification failed: " + "; ".join(errors))


def verify_pr_merge_identity(
    pr_data: Dict[str, Any],
    pr_merge_commit_sha: str,
    stage1_master_sha: str,
    expected_repo_full: str = REPOSITORY,
    expected_pr_number: int = PR_NUMBER,
) -> None:
    """Verify PR merge identity separately from master SHA. Fail closed."""
    errors = []

    if not isinstance(pr_data, dict):
        raise ProvenanceVerificationError("PR data not a dict")

    # Repository
    base = pr_data.get("base")
    base_repo = base.get("repo", {}) if isinstance(base, dict) else {}
    if isinstance(base_repo, dict):
        full_name = base_repo.get("full_name")
        if full_name is not None and full_name != expected_repo_full:
            errors.append(f"PR repository mismatch: {full_name} != {expected_repo_full}")

    # PR number
    pr_number = pr_data.get("number")
    if pr_number is not None and pr_number != expected_pr_number:
        errors.append(f"PR number mismatch: {pr_number} != {expected_pr_number}")

    if not pr_data.get("merged"):
        errors.append("PR is not merged")

    merged_at = pr_data.get("merged_at")
    if not merged_at:
        errors.append("merged_at: missing trusted merge timestamp")
    else:
        try:
            val = merged_at
            if val.endswith("Z"):
                val = val[:-1] + "+00:00"
            datetime.fromisoformat(val)
        except (ValueError, TypeError):
            errors.append(f"unparseable merged_at: {merged_at!r}")

    api_merge_sha = pr_data.get("merge_commit_sha", "")
    if not is_valid_sha(api_merge_sha):
        errors.append(f"API merge_commit_sha invalid: {api_merge_sha!r}")

    if api_merge_sha != pr_merge_commit_sha:
        errors.append(f"PR merge SHA mismatch: api={api_merge_sha} != supplied={pr_merge_commit_sha}")

    if not is_valid_sha(pr_merge_commit_sha):
        errors.append(f"supplied PR merge SHA invalid: {pr_merge_commit_sha!r}")
    if not is_valid_sha(stage1_master_sha):
        errors.append(f"stage1 master SHA invalid: {stage1_master_sha!r}")

    if errors:
        raise ProvenanceVerificationError("PR merge identity verification failed: " + "; ".join(errors))


def verify_ancestry(api_url: str, repository: str, token: str, base_sha: str, head_sha: str) -> None:
    """Verify base_sha is an ancestor of head_sha using compare API."""
    if not is_valid_sha(base_sha) or not is_valid_sha(head_sha):
        raise ProvenanceVerificationError("invalid SHA for ancestry check")
    if base_sha == head_sha:
        return
    data = fetch_compare(api_url, repository, base_sha, head_sha, token)
    status = data.get("status")
    if status not in ("ahead", "identical"):
        raise ProvenanceVerificationError(
            f"ancestry check failed: {base_sha} is not an ancestor of {head_sha} (status={status})"
        )


def verify_artifacts(api_url: str, repository: str, run_id: str, token: str) -> None:
    """Verify Stage 1 artifacts metadata. Fail closed."""
    data = fetch_artifacts(api_url, repository, run_id, token)
    artifacts = data.get("artifacts", [])
    if not isinstance(artifacts, list):
        raise ProvenanceVerificationError("artifacts list missing or invalid")

    by_name = {}
    for a in artifacts:
        if not isinstance(a, dict):
            continue
        name = a.get("name")
        if name in by_name:
            raise ProvenanceVerificationError(f"duplicate artifact name: {name}")
        by_name[name] = a

    for req in REQUIRED_ARTIFACTS:
        if req not in by_name:
            raise ProvenanceVerificationError(f"required artifact missing: {req}")

    for name, a in by_name.items():
        wf_run = a.get("workflow_run") if isinstance(a.get("workflow_run"), dict) else {}
        if isinstance(wf_run, dict):
            rid = wf_run.get("id")
            if rid is not None and str(rid) != str(run_id):
                raise ProvenanceVerificationError(f"artifact {name} run_id mismatch: {rid} != {run_id}")
            repo_obj = wf_run.get("repository")
            if isinstance(repo_obj, dict):
                repo_full = repo_obj.get("full_name")
                if repo_full is not None and repo_full != repository:
                    raise ProvenanceVerificationError(f"artifact {name} repository mismatch: {repo_full} != {repository}")
        expired = a.get("expired")
        if expired is True:
            raise ProvenanceVerificationError(f"artifact {name} is expired")
        if a.get("id") is None:
            raise ProvenanceVerificationError(f"artifact {name} missing id")


def main() -> int:
    api_url = _env("GITHUB_API_URL", "https://api.github.com")
    token = _env("GITHUB_TOKEN")
    repository = _env("EXPECTED_REPOSITORY", REPOSITORY)
    run_id = _env("PREFLIGHT_RUN_ID")

    stage1_master_sha = _env("STAGE1_MASTER_SHA")
    pr_merge_commit_sha = _env("SUPPLIED_MERGE_SHA") or _env("MERGE_COMMIT_SHA") or _env("PR_MERGE_COMMIT_SHA")

    expected_workflow_id_supplied = _env("EXPECTED_WORKFLOW_ID")
    expected_workflow_path = _env("EXPECTED_WORKFLOW_PATH", EXPECTED_WORKFLOW_PATH_DEFAULT)

    expected_manifest_sha = _env("EXPECTED_MANIFEST_SHA256") or _env("SUPPLIED_MANIFEST_SHA")
    expected_manifest_count_raw = _env("EXPECTED_MANIFEST_COUNT") or _env("SUPPLIED_MANIFEST_COUNT")
    expected_manifest_schema_version = _env("EXPECTED_MANIFEST_SCHEMA_VERSION") or _env("SUPPLIED_MANIFEST_SCHEMA_VERSION")
    expected_manifest_reference_date = _env("EXPECTED_MANIFEST_REFERENCE_DATE") or _env("SUPPLIED_MANIFEST_REFERENCE_DATE")

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
    if not expected_manifest_sha or not is_valid_sha256(expected_manifest_sha):
        print("ERROR: invalid or missing expected manifest SHA256")
        return 1
    if not expected_manifest_count_raw:
        print("ERROR: expected manifest count not set")
        return 1
    try:
        expected_manifest_count = int(expected_manifest_count_raw)
    except (ValueError, TypeError):
        print("ERROR: invalid expected manifest count")
        return 1
    if expected_manifest_count <= 0:
        print("ERROR: expected manifest count must be positive")
        return 1
    if not expected_manifest_schema_version:
        print("ERROR: expected manifest schema version not set")
        return 1
    if not expected_manifest_reference_date:
        print("ERROR: expected manifest reference date not set")
        return 1

    try:
        canonical_wf_id = resolve_canonical_workflow(api_url, repository, expected_workflow_path, token)
        if expected_workflow_id_supplied and expected_workflow_id_supplied != canonical_wf_id:
            raise ProvenanceVerificationError(
                f"supplied workflow id {expected_workflow_id_supplied} != canonical {canonical_wf_id}"
            )
        expected_workflow_id = canonical_wf_id

        run_data = fetch_workflow_run(api_url, repository, run_id, token)
        verify_preflight_run(
            run_data,
            repository,
            expected_workflow_id,
            expected_workflow_path,
            stage1_master_sha,
            pr_merge_commit_sha,
        )

        pr_data = fetch_pr_metadata(api_url, repository, PR_NUMBER, token)
        verify_pr_merge_identity(pr_data, pr_merge_commit_sha, stage1_master_sha, repository, PR_NUMBER)

        verify_ancestry(api_url, repository, token, pr_merge_commit_sha, stage1_master_sha)

        verify_artifacts(api_url, repository, run_id, token)

    except ProvenanceVerificationError as exc:
        print(f"ERROR: {exc}")
        return 1
    except Exception as exc:
        print(f"ERROR: unexpected: {exc}")
        return 1

    print("Preflight provenance verified")
    print("should_execute=true")
    print(f"stage1_master_sha={stage1_master_sha}")
    print(f"pr_merge_commit_sha={pr_merge_commit_sha}")
    print(f"expected_manifest_sha256={expected_manifest_sha}")
    print(f"expected_manifest_count={expected_manifest_count}")
    print(f"expected_manifest_schema_version={expected_manifest_schema_version}")
    print(f"expected_manifest_reference_date={expected_manifest_reference_date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())