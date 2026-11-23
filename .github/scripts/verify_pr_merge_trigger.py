#!/usr/bin/env python3
"""Verify the trusted merge-trigger identity for PR #107."""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, Tuple

SHA_RE = re.compile(r"^[0-9a-f]{40}$")

EXPECTED_PR_NUMBER = "107"
DEFAULT_REPOSITORY = "gopal735/ScholarZone"
DEFAULT_BASE_REPOSITORY = "gopal735/ScholarZone"
DEFAULT_HEAD_REPOSITORY = "gopal735/ScholarZone"
DEFAULT_BASE_REF = "master"
DEFAULT_HEAD_REF = "feat/closed-scholarship-permanent-deletion"
DEFAULT_API_URL = "https://api.github.com"


class TriggerVerificationError(Exception):
    pass


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def is_valid_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA_RE.fullmatch(value.strip()))


def _require(env: Dict[str, str], name: str) -> str:
    value = (env.get(name) or "").strip()
    if not value:
        raise TriggerVerificationError(f"missing required value: {name}")
    return value


def _env_from(env: Dict[str, str], name: str, default: str) -> str:
    value = (env.get(name) or "").strip()
    return value if value else default


def validate_event_identity(env: Dict[str, str]) -> Tuple[bool, Dict[str, str]]:
    repository = _require(env, "EVENT_REPOSITORY")
    if repository != _env_from(env, "EXPECTED_REPOSITORY", DEFAULT_REPOSITORY):
        raise TriggerVerificationError(f"unexpected repository: {repository!r}")

    action = _require(env, "EVENT_ACTION")
    if action != "closed":
        raise TriggerVerificationError(f"unexpected event action: {action!r}")

    number = _require(env, "EVENT_NUMBER")
    expected_number = _env_from(env, "EXPECTED_PR_NUMBER", EXPECTED_PR_NUMBER)
    if number != expected_number:
        return False, {"pr_number": number}

    merged_raw = _require(env, "EVENT_MERGED").lower()
    if merged_raw not in {"true", "false"}:
        raise TriggerVerificationError("invalid EVENT_MERGED value")
    merged = merged_raw == "true"

    base_ref = _require(env, "EVENT_BASE_REF")
    expected_base_ref = _env_from(env, "EXPECTED_BASE_REF", DEFAULT_BASE_REF)
    if base_ref != expected_base_ref:
        raise TriggerVerificationError(f"unexpected base branch: {base_ref!r}")

    base_repository = _require(env, "EVENT_BASE_REPOSITORY")
    expected_base_repository = _env_from(env, "EXPECTED_BASE_REPOSITORY", DEFAULT_BASE_REPOSITORY)
    if base_repository != expected_base_repository:
        raise TriggerVerificationError(f"unexpected base repository: {base_repository!r}")

    head_ref = _require(env, "EVENT_HEAD_REF")
    expected_head_ref = _env_from(env, "EXPECTED_HEAD_REF", DEFAULT_HEAD_REF)
    if head_ref != expected_head_ref:
        raise TriggerVerificationError(f"unexpected head branch: {head_ref!r}")

    head_repository = _require(env, "EVENT_HEAD_REPOSITORY")
    expected_head_repository = _env_from(env, "EXPECTED_HEAD_REPOSITORY", DEFAULT_HEAD_REPOSITORY)
    if head_repository != expected_head_repository:
        raise TriggerVerificationError(f"unexpected head repository: {head_repository!r}")

    head_sha = _require(env, "EVENT_HEAD_SHA")
    if not is_valid_sha(head_sha):
        raise TriggerVerificationError("invalid head SHA format")

    if not merged:
        return False, {"pr_number": number}

    merge_sha = _require(env, "EVENT_MERGE_SHA")
    if not is_valid_sha(merge_sha):
        raise TriggerVerificationError("invalid merge commit SHA format")

    if head_sha == merge_sha:
        raise TriggerVerificationError("head SHA and merge commit SHA must differ")

    identity = {
        "pr_number": number,
        "repository": repository,
        "action": action,
        "merged": "true",
        "base_repository": base_repository,
        "base_ref": base_ref,
        "head_repository": head_repository,
        "head_ref": head_ref,
        "head_sha": head_sha,
        "merge_commit_sha": merge_sha,
    }
    return True, identity


def fetch_pr_metadata(api_url: str, repository: str, pr_number: str, token: str) -> Dict[str, Any]:
    if not token:
        raise TriggerVerificationError("missing GitHub token for trusted PR metadata")
    url = f"{api_url.rstrip('/')}/repos/{repository}/pulls/{pr_number}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "scholarzone-pr107-trigger-verification",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise TriggerVerificationError(f"GitHub API request failed with HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise TriggerVerificationError(f"GitHub API request failed: {exc.reason}") from exc
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise TriggerVerificationError("GitHub API returned invalid JSON") from exc
    if not isinstance(data, dict):
        raise TriggerVerificationError("GitHub API returned an unexpected payload")
    return data


def verify_api_identity(event_identity: Dict[str, str], api_metadata: Dict[str, Any]) -> None:
    errors = []

    def mismatch(field: str, expected: str, actual: Any) -> None:
        if str(actual) != str(expected):
            errors.append(f"{field}: event={expected!r}, api={actual!r}")

    mismatch("number", event_identity["pr_number"], api_metadata.get("number"))
    mismatch("merged", "true", str(api_metadata.get("merged")).lower())
    if not api_metadata.get("merged_at"):
        errors.append("merged_at: missing trusted merge timestamp")

    base = api_metadata.get("base") or {}
    base_repo = base.get("repo") or {}
    mismatch("base repository", event_identity["base_repository"], base_repo.get("full_name"))
    mismatch("base ref", event_identity["base_ref"], base.get("ref"))

    head = api_metadata.get("head") or {}
    head_repo = head.get("repo") or {}
    mismatch("head repository", event_identity["head_repository"], head_repo.get("full_name"))
    mismatch("head ref", event_identity["head_ref"], head.get("ref"))
    mismatch("head SHA", event_identity["head_sha"], head.get("sha"))
    mismatch("merge commit SHA", event_identity["merge_commit_sha"], api_metadata.get("merge_commit_sha"))

    if errors:
        raise TriggerVerificationError("trusted PR metadata mismatch: " + "; ".join(errors))


def _write_github_outputs(values: Dict[str, str]) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as handle:
        for key, value in values.items():
            handle.write(f"{key}={value}\n")


def main() -> int:
    env = dict(os.environ)
    try:
        should_run, identity = validate_event_identity(env)
    except TriggerVerificationError as exc:
        print(f"ERROR: {exc}")
        return 1

    pr_number = identity.get("pr_number", _env("EVENT_NUMBER"))
    _write_github_outputs({"pr_number": pr_number})

    if not should_run:
        _write_github_outputs({"should_run": "false"})
        print("should_run=false")
        print(f"pr_number={pr_number}")
        return 0

    repository = identity["repository"]
    api_url = _env("GITHUB_API_URL", DEFAULT_API_URL)
    token = _env("GITHUB_TOKEN")
    try:
        api_metadata = fetch_pr_metadata(api_url, repository, pr_number, token)
        verify_api_identity(identity, api_metadata)
    except TriggerVerificationError as exc:
        print(f"ERROR: {exc}")
        return 1

    merge_sha = identity["merge_commit_sha"]
    head_sha = identity["head_sha"]
    _write_github_outputs(
        {
            "should_run": "true",
            "pr_number": pr_number,
            "merge_commit_sha": merge_sha,
            "head_sha": head_sha,
        }
    )
    print("should_run=true")
    print(f"pr_number={pr_number}")
    print(f"merge_commit_sha={merge_sha}")
    print(f"head_sha={head_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())