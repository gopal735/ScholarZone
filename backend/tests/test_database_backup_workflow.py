"""The backup workflow must be deterministic on a clean runner, and the
manual-only production policy must be enforced by code, not by prose.

These are workflow-level assertions: the workflow YAML is parsed and the
steps' shell scripts are checked for the two behaviours a reviewer found
missing.

1. **`../backup-out` is created before `tee` writes into it.** The script's
   `output_dir.mkdir()` cannot run before the pipeline starts, so a clean
   runner would fail on `tee ../backup-out/result.json` and report a backup
   failure that is really a missing directory.
2. **The authorization mode is derived from the trigger, not supplied by a
   caller.** `workflow_dispatch` (a person) yields `manual`; the weekly
   schedule yields `scheduled`, in which a production source is refused by
   the script whatever the allow-list and the authorization say. There is
   no way to tell the scheduled run to be manual, and no way for the manual
   path to run against production without the recorded authorisation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "database-backup.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    if not WORKFLOW.is_file():
        pytest.skip("the encrypted backup workflow is not present")
    return WORKFLOW.read_text(encoding="utf-8")


def _run_block(text: str, marker: str) -> str:
    start = text.find(marker)
    assert start != -1, f"no step named {marker!r} in the workflow"
    end = text.find("\n      - name:", start)
    block = text[start:] if end == -1 else text[start:end]
    run_at = block.find("run: |")
    assert run_at != -1
    # Only the backup step's own script, up to the next step, so a `mkdir`
    # elsewhere in the workflow cannot satisfy the ordering assertion.
    return block[run_at:]


def _line_indexes(script: str, needle: str) -> list[int]:
    """Line numbers whose *command* contains needle, comments excluded.

    The backup step's own comment names the `tee` invocation it explains, so
    a text search would find the comment before the command and invert the
    ordering.
    """
    indexes = []
    for number, line in enumerate(script.splitlines()):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if needle in line:
            indexes.append(number)
    return indexes


def test_backup_out_is_created_before_tee(workflow_text: str):
    script = _run_block(workflow_text, "Produce the encrypted backup")
    mkdir_lines = _line_indexes(script, "mkdir -p ../backup-out")
    tee_lines = _line_indexes(script, "tee ../backup-out/result.json")
    assert mkdir_lines, "the workflow never creates ../backup-out"
    assert tee_lines, "the workflow never tees into ../backup-out"
    assert min(mkdir_lines) < min(tee_lines), "tee writes before the directory exists on a clean runner"


def test_the_authorization_mode_comes_from_the_trigger(workflow_text: str):
    script = _run_block(workflow_text, "Produce the encrypted backup")
    assert "workflow_dispatch" in script
    assert "auth_mode=manual" in script
    assert "auth_mode=scheduled" in script
    # The mode is passed to the script, not just computed and dropped.
    assert '--authorization-mode "$auth_mode"' in script
    # And it is not a caller-supplied input: the dispatch inputs block declares
    # runs_per_month and nothing else, so nobody can dispatch the scheduled
    # policy as manual.
    inputs_at = workflow_text.find("workflow_dispatch:")
    schedule_at = workflow_text.find("schedule:", inputs_at)
    inputs_block = workflow_text[inputs_at:schedule_at if schedule_at != -1 else len(workflow_text)]
    declared = re.findall(r"^\s+\"?(\w+)\"?:", inputs_block, re.M)
    # Only the estimate input is declared - and none of them is an
    # authorization or mode input.
    assert "authorization" not in declared and "authorization_mode" not in declared
    assert declared == ["inputs", "runs_per_month", "description", "required", "default"], declared
