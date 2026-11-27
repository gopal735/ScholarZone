import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / ".github" / "scripts"))

import verify_pr_merge_trigger as trigger


def _valid_event():
    return {
        "EVENT_REPOSITORY": "gopal735/ScholarZone",
        "EVENT_ACTION": "closed",
        "EVENT_NUMBER": "107",
        "EVENT_MERGED": "true",
        "EVENT_BASE_REPOSITORY": "gopal735/ScholarZone",
        "EVENT_BASE_REF": "master",
        "EVENT_HEAD_REPOSITORY": "gopal735/ScholarZone",
        "EVENT_HEAD_REF": "feat/closed-scholarship-permanent-deletion",
        "EVENT_HEAD_SHA": "a" * 40,
        "EVENT_MERGE_SHA": "b" * 40,
    }


def test_valid_sha_rejects_whitespace():
    assert not trigger.is_valid_sha(" " + "a" * 40)
    assert not trigger.is_valid_sha("a" * 40 + " ")
    assert not trigger.is_valid_sha(" " + "a" * 40 + " ")


def test_wrong_repository_fails_closed():
    env = _valid_event()
    env["EVENT_REPOSITORY"] = "evil/repo"
    try:
        trigger.validate_event_identity(env)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure")


def test_wrong_pr_number_does_not_run():
    env = _valid_event()
    env["EVENT_NUMBER"] = "108"
    should_run, identity = trigger.validate_event_identity(env)
    assert should_run is False
    assert identity["pr_number"] == "108"


def test_wrong_pr_number_does_not_run():
    env = _valid_event()
    env["EVENT_NUMBER"] = "999"
    should_run, identity = trigger.validate_event_identity(env)
    assert should_run is False
    assert identity["pr_number"] == "999"


def test_not_merged_does_not_run():
    env = _valid_event()
    env["EVENT_MERGED"] = "false"
    should_run, identity = trigger.validate_event_identity(env)
    assert should_run is False
    assert identity["pr_number"] == "107"


def test_unmerged_pr_event_does_not_run():
    env = _valid_event()
    env["EVENT_MERGED"] = "false"
    should_run, identity = trigger.validate_event_identity(env)
    assert should_run is False
    assert identity["pr_number"] == "107"


def test_missing_event_value_fails_closed():
    env = _valid_event()
    del env["EVENT_HEAD_SHA"]
    try:
        trigger.validate_event_identity(env)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure")


def test_malformed_sha_fails_closed():
    for bad in ["", "a" * 39, "a" * 41, "z" + "a" * 39, "A" * 40]:
        env = _valid_event()
        env["EVENT_HEAD_SHA"] = bad
        try:
            trigger.validate_event_identity(env)
        except trigger.TriggerVerificationError:
            continue
        raise AssertionError(f"expected failure for {bad!r}")


def test_merged_pr_missing_merge_sha_fails_closed():
    env = _valid_event()
    del env["EVENT_MERGE_SHA"]
    try:
        trigger.validate_event_identity(env)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure for missing merge SHA")


def test_merged_pr_wrong_merge_sha_format_fails_closed():
    env = _valid_event()
    env["EVENT_MERGE_SHA"] = "not-a-sha"
    try:
        trigger.validate_event_identity(env)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure for invalid merge SHA")


def test_head_and_merge_sha_must_differ():
    env = _valid_event()
    env["EVENT_MERGE_SHA"] = env["EVENT_HEAD_SHA"]
    try:
        trigger.validate_event_identity(env)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure for equal head/merge SHA")


def test_api_metadata_mismatch_fails_closed():
    event = {
        "pr_number": "107",
        "repository": "gopal735/ScholarZone",
        "action": "closed",
        "merged": "true",
        "base_repository": "gopal735/ScholarZone",
        "base_ref": "master",
        "head_repository": "gopal735/ScholarZone",
        "head_ref": "feat/closed-scholarship-permanent-deletion",
        "head_sha": "a" * 40,
        "merge_commit_sha": "b" * 40,
    }
    api = {
        "number": 107,
        "merged": True,
        "merged_at": "2026-01-01T00:00:00Z",
        "base": {"ref": "master", "repo": {"full_name": "gopal735/ScholarZone"}},
        "head": {"ref": "feat/closed-scholarship-permanent-deletion", "sha": "c" * 40, "repo": {"full_name": "gopal735/ScholarZone"}},
        "merge_commit_sha": "b" * 40,
    }
    try:
        trigger.verify_api_identity(event, api)
    except trigger.TriggerVerificationError:
        pass
    else:
        raise AssertionError("expected failure")


def test_api_metadata_match_passes():
    sha_head = "a" * 40
    sha_merge = "b" * 40
    event = {
        "pr_number": "107",
        "repository": "gopal735/ScholarZone",
        "action": "closed",
        "merged": "true",
        "base_repository": "gopal735/ScholarZone",
        "base_ref": "master",
        "head_repository": "gopal735/ScholarZone",
        "head_ref": "feat/closed-scholarship-permanent-deletion",
        "head_sha": sha_head,
        "merge_commit_sha": sha_merge,
    }
    api = {
        "number": 107,
        "merged": True,
        "merged_at": "2026-01-01T00:00:00Z",
        "base": {"ref": "master", "repo": {"full_name": "gopal735/ScholarZone"}},
        "head": {"ref": "feat/closed-scholarship-permanent-deletion", "sha": sha_head, "repo": {"full_name": "gopal735/ScholarZone"}},
        "merge_commit_sha": sha_merge,
    }
    trigger.verify_api_identity(event, api)
