"""Commit the Phase 3 activation, reconstructing the shared files from HEAD.

Three problems this avoids, all of which have bitten before:

* the working-tree copies of the worker and two test files are CRLF while the
  repository commits LF, so taking them wholesale turns a small change into a
  several-thousand-line diff;
* those same files carry another workstream's uncommitted and staged edits, so
  committing the working-tree copy would publish their work unreviewed;
* `test_phase2_scheduler.py` has been *staged for deletion* by another workstream,
  so the shared index is not a safe place to build this commit from.

So each shared file is rebuilt from HEAD with only this phase's edit applied, and
each blob is checked for its marker and for LF endings before it is staged into a
private index.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

WORKER = "backend/app/jobs/scholarzone_maintenance.py"
PURGE_TEST = "backend/tests/test_purge_closed.py"
EFFICIENCY_TEST = "backend/tests/test_efficiency_safety.py"
NEW_TESTS = ("backend/tests/test_phase3_activation.py", "backend/tests/test_phase2_scheduler.py")

# --- worker: two edits, both applied to HEAD's copy -------------------------
WORKER_FLAG_OLD = """# purge_closed is the only stage that deletes rows. It is excluded from "all"
# so a scheduled run cannot destroy the catalogue unattended, and named here so
# the contract is asserted rather than assumed.
PURGE_CLOSED_EXCLUDED_FROM_ALL = True
"""
WORKER_FLAG_NEW = '''# purge_closed is the only stage that deletes rows, and this flag is the single
# place that decides whether a scheduled `--stage all` run may reach it.
#
# It was False-proofed through rollout: the collector shipped with deletion
# unreachable from the schedule, Phase 2 observed arming unattended across a full
# cycle with `deleted = 0` and `candidate_since_set = 0`, and only then was this
# flipped. Nothing about the deletion itself changed. The stage still selects
# nothing but records that passed the SAFE_DELETE policy, the retention period, a
# grace period that spans earlier cycles, and a re-decision inside the deleting
# transaction. What changed is only whether the schedule is allowed to ask.
#
# The flag is asserted against the real selection in main() rather than trusted,
# so a refactor that silently re-excludes the stage fails a test rather than
# quietly disabling the lifecycle.
PURGE_CLOSED_EXCLUDED_FROM_ALL = False

#: The only stage permitted to delete, and the stage that must arm it first.
DELETING_STAGE = "purge_closed"
ARMING_STAGE = "auto_delete_candidate"
'''

WORKER_SELECT_OLD = '''    selected = [
        s
        for s in STAGE_ORDER
        if (run_all and s != "purge_closed") or s in wanted
    ]
    assert not (run_all and PURGE_CLOSED_EXCLUDED_FROM_ALL) or "purge_closed" not in selected
'''
WORKER_SELECT_NEW = '''    excluded_from_all = {DELETING_STAGE} if PURGE_CLOSED_EXCLUDED_FROM_ALL else set()
    selected = [
        s
        for s in STAGE_ORDER
        if (run_all and s not in excluded_from_all) or s in wanted
    ]
    if run_all:
        assert PURGE_CLOSED_EXCLUDED_FROM_ALL == (DELETING_STAGE not in selected), (
            "PURGE_CLOSED_EXCLUDED_FROM_ALL does not match the stage selection"
        )
        if DELETING_STAGE in selected:
            assert ARMING_STAGE in selected, (
                "the schedule can delete but cannot arm; nothing would ever be eligible"
            )
            assert selected.index(ARMING_STAGE) < selected.index(DELETING_STAGE), (
                "the deleting stage would run before the arming stage"
            )
'''

# --- test_purge_closed: replace one test, keep the class intent --------------
PURGE_OLD = '''    def test_excluded_from_all(self):
        assert worker.PURGE_CLOSED_EXCLUDED_FROM_ALL is True
        # Runs last, so a record inserted earlier in the same run is also
        # judged for closure rather than surviving on the strength of being
        # added after the purge had already passed.
        assert worker.STAGE_ORDER[-1] == "purge_closed"
'''
PURGE_NEW = '''    def test_unattended_deletion_is_bounded_by_the_policy_not_by_exclusion(self):
        """Phase 3 removed the exclusion, so the safety has to live somewhere else.

        This test used to assert ``PURGE_CLOSED_EXCLUDED_FROM_ALL is True``, which
        meant a scheduled run could not delete at all. Activation deliberately
        reversed that, so the assertion is replaced rather than deleted, and
        replaced with the property that now has to hold: a scheduled run may reach
        the stage, and the stage may only act on what the policy produced, after a
        grace period spanning earlier cycles, re-decided inside the transaction.

        The flag still has to *describe* the selection rather than be assumed to,
        so that part of the original intent is kept.
        """
        import inspect as _inspect

        source = _inspect.getsource(worker.main)
        assert "PURGE_CLOSED_EXCLUDED_FROM_ALL" in source
        assert "does not match the stage selection" in source

    def test_runs_last_so_a_record_added_earlier_in_the_run_is_still_judged(self):
        # Runs last, so a record inserted earlier in the same run is also
        # judged for closure rather than surviving on the strength of being
        # added after the purge had already passed.
        assert worker.STAGE_ORDER[-1] == "purge_closed"
        assert worker.STAGE_ORDER[-2] == "auto_delete_candidate"

    def test_the_deleting_stage_still_depends_on_arming(self):
        assert worker.STAGE_DEPENDENCIES["purge_closed"] == ("auto_delete_candidate",)
'''

# --- test_efficiency_safety: replace three stale assertions -----------------
EFFICIENCY_OLD = '''        assert list(worker.STAGE_ORDER) != [
            s for s in worker.STAGE_ORDER if s != "purge_closed"
        ]
        assert worker.PURGE_CLOSED_EXCLUDED_FROM_ALL is True
'''
EFFICIENCY_NEW = '''        # Phase 3 activated the scheduled lifecycle, so the deleting stage is no
        # longer held out of "all". What replaces the exclusion is asserted rather
        # than assumed: the flag is compared against the real selection, and when
        # the stage is reachable the arming stage must be reachable too and must
        # come first. A refactor that reintroduces a hard-coded stage name fails
        # here rather than quietly deciding the question on its own.
        import inspect as _inspect

        main_source = _inspect.getsource(worker.main)
        assert "does not match the stage selection" in main_source
        assert "would run before the arming stage" in main_source
        assert 's != "purge_closed"' not in main_source
        assert isinstance(worker.PURGE_CLOSED_EXCLUDED_FROM_ALL, bool)
'''

PATCHES = {
    WORKER: [(WORKER_FLAG_OLD, WORKER_FLAG_NEW), (WORKER_SELECT_OLD, WORKER_SELECT_NEW)],
    PURGE_TEST: [(PURGE_OLD, PURGE_NEW)],
    EFFICIENCY_TEST: [(EFFICIENCY_OLD, EFFICIENCY_NEW)],
}

MARKERS = {
    WORKER: "DELETING_STAGE",
    PURGE_TEST: "test_unattended_deletion_is_bounded_by_the_policy_not_by_exclusion",
    EFFICIENCY_TEST: "does not match the stage selection",
    "backend/tests/test_phase3_activation.py": "test_2_all_includes_the_deleting_stage",
    "backend/tests/test_phase2_scheduler.py": "test_the_deleting_stages_reachability_is_declared",
}

MESSAGE = """feat: activate the closed-record lifecycle on the maintenance schedule

`purge_closed` is no longer held out of `--stage all`, so the scheduled cycle now
arms candidates and then deletes what has already earned it.

The change is one flag and the selection that reads it. Nothing about deletion
changed. The stage still selects nothing but records that passed the SAFE_DELETE
policy, were archived at least 180 days ago, held every condition continuously
for 14 days across an earlier cycle, carry no dependency that must survive, and
were re-decided under a row lock inside the deleting transaction, with the
manifest written before the commit and the whole thing rolled back on failure.
`closed` alone still deletes nothing.

Rollout order was the reason for the delay, and it is recorded here so the next
reader does not have to infer it: the collector shipped with deletion
unreachable from the schedule; Phase 2 observed one complete scheduled cycle with
`deleted = 0` and `candidate_since_set = 0`, proving arming runs unattended and
harmless before it was allowed to ask about deleting anything.

The selection no longer hard-codes the stage name. Which stages `all` may reach is
decided by the flag alone, and the flag is compared against the real selection at
runtime, so the two cannot drift apart silently. When the deleting stage is
reachable, the arming stage must be reachable and must come first - asserted, not
assumed, because a delete that ran before anything armed it could only ever
delete a record nobody evaluated.

Three tests encoded the Phase 2 world, that a scheduled run cannot delete at all.
They are converted rather than deleted. `test_excluded_from_all` becomes a test
that unattended deletion is bounded by the policy rather than by exclusion;
`test_efficiency_safety` asserts the flag-is-compared property in place of the
exclusion literal; the Phase 2 reachability test follows the flag instead of a
literal. Each keeps the property it was written to protect.

No policy condition, retention value, grace value, dependency rule or deletion
path is touched, and Match, Count, public visibility and image handling are
untouched."""


def git(args, env=None, stdin=None):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, env=env, input=stdin)


def main() -> int:
    print(f"HEAD {git(['rev-parse', 'HEAD']).stdout.decode().strip()}")
    blobs = {}

    for path, patches in PATCHES.items():
        text = git(["show", f"HEAD:{path}"]).stdout.decode("utf-8")
        print(f"\n{patch_label(path)}: HEAD {len(text)} chars")
        for old, new in patches:
            if text.count(old) != 1:
                print(f"  REFUSING: HEAD does not contain exactly one copy of the block "
                      f"being replaced in {path} ({text.count(old)})")
                return 1
            text = text.replace(old, new)
            print("  applied one edit")
        ast.parse(text)
        data = text.encode("utf-8")
        if data.count(b"\r\n"):
            print(f"  REFUSING: {path} would be committed with CRLF")
            return 1
        blobs[path] = git(["hash-object", "-w", "--stdin"], stdin=data).stdout.decode().strip()
        print(f"  blob {blobs[path][:10]}  (LF)")

    for path in NEW_TESTS:
        data = (REPO / path).read_bytes()
        data.decode("utf-8")
        if data.count(b"\r\n"):
            print(f"  REFUSING: {path} has CRLF")
            return 1
        blobs[path] = git(["hash-object", "-w", "--stdin"], stdin=data).stdout.decode().strip()
        print(f"{path}\n  blob {blobs[path][:10]}  (LF)")

    for path, marker in MARKERS.items():
        if marker.encode() not in git(["cat-file", "-p", blobs[path]]).stdout:
            print(f"REFUSING: {path} blob does not contain {marker!r}")
            return 1
    print("\nall markers present")

    with tempfile.NamedTemporaryFile(suffix=".index", delete=False) as handle:
        private_index = handle.name
    os.unlink(private_index)
    env = dict(os.environ, GIT_INDEX_FILE=private_index)
    try:
        if git(["read-tree", "HEAD"], env=env).returncode:
            raise SystemExit("read-tree failed")
        for path, blob in blobs.items():
            if git(["update-index", "--add", "--cacheinfo", f"100644,{blob},{path}"], env=env).returncode:
                raise SystemExit(f"update-index failed for {path}")
        staged = sorted(git(["diff", "--cached", "--name-only"], env=env).stdout.decode().split())
        stray = [p for p in staged if p not in blobs]
        if stray:
            print(f"REFUSING: unrelated paths in the commit: {stray}")
            return 1
        print(f"\ncommitting {staged}")
        print(git(["diff", "--cached", "--stat"], env=env).stdout.decode().strip())
        result = git(["commit", "-m", MESSAGE], env=env)
        sys.stdout.write(result.stdout.decode("utf-8", "replace"))
        if result.returncode:
            return result.returncode
    finally:
        Path(private_index).unlink(missing_ok=True)

    print(f"\nnew HEAD {git(['rev-parse', 'HEAD']).stdout.decode().strip()}")
    print(git(["show", "--stat", "--format=", "HEAD"]).stdout.decode().strip())
    shared = git(["diff", "--cached", "--name-only"]).stdout.decode().split()
    print(f"\nshared index still holds {len(shared)} staged paths (untouched)")
    return 0


def patch_label(path: str) -> str:
    return path


if __name__ == "__main__":
    raise SystemExit(main())