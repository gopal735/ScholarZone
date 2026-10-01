"""Tests for the double-encoding repair.

The corruption is UTF-8 decoded as Latin-1 and re-encoded, so a correct name
becomes unsearchable and a programme can appear twice under two spellings.

The corrupted strings are produced programmatically rather than pasted in: a
mojibake literal is itself easy to corrupt in transit, which would make a test
assert against a different corruption than the one it means to check.
"""

from __future__ import annotations

import ast
import inspect

import pytest

from app.jobs import scholarzone_maintenance as worker


def corrupt(text: str) -> str:
    """Produce exactly the corruption the repair is meant to undo."""
    return text.encode("utf-8").decode("latin-1")


def _helper():
    def finder(node):
        for child in ast.walk(node):
            if (
                isinstance(child, ast.FunctionDef)
                and child.name == "repair_double_encoded_text"
            ):
                return child
        return None

    node = finder(ast.parse(inspect.getsource(worker)))
    assert node is not None, "repair_double_encoded_text not found"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict = {}
    exec(compile(module, "<repair>", "exec"), namespace)
    return namespace["repair_double_encoded_text"]


# The helper is nested inside main(), so it is resolved once from source.
repair = _helper()


class TestDoubleEncoding:
    @pytest.mark.parametrize(
        "clean",
        [
            "Grundförderung für Ausländer:innen",
            "Linköping",
            "Appel à projets générique",
            "Promotionsförderung für Ausländer:innen",
        ],
    )
    def test_round_trips_corrupted_text(self, clean):
        broken = corrupt(clean)
        assert broken != clean, "corrupt() produced identical text"
        assert repair(broken) == (clean, True)

    def test_repairs_curly_dash_and_quotes(self):
        clean = "Linköping – applications close 30 March"
        assert repair(corrupt(clean)) == (clean, True)

    @pytest.mark.parametrize(
        "clean",
        [
            "Grundförderung für Ausländer:innen",
            "Appel à projets générique 2027",
            " scholarships",
            "東京大学",
            "Plain ASCII title",
            "",
        ],
    )
    def test_correct_text_is_never_touched(self, clean):
        assert repair(clean) == (clean, False)

    def test_non_string_passes_through(self):
        assert repair(None) == (None, False)
        assert repair(42) == (42, False)

    def test_repair_is_idempotent(self):
        once, changed = repair(corrupt("Grundförderung"))
        assert changed is True
        twice, changed_again = repair(once)
        assert changed_again is False
        assert twice == once

    def test_double_corruption_is_only_repaired_once(self):
        # Repairing once must not leave a string that repairs again into
        # something different.
        clean = "Grundförderung für Ausländer:innen"
        once, _ = repair(corrupt(clean))
        twice, changed = repair(once)
        assert changed is False
        assert twice == clean


class TestRepairStageContract:
    def test_stage_is_wired(self):
        assert "repair_encoding" in worker.STAGE_ORDER
        assert worker.STAGE_DEPENDENCIES["repair_encoding"] == ()

    def test_dispatch_table_contains_the_stage(self):
        tree = ast.parse(inspect.getsource(worker))
        dispatched = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "stages" for t in node.targets
            ):
                if isinstance(node.value, ast.Dict):
                    dispatched = {
                        k.value
                        for k in node.value.keys
                        if isinstance(k, ast.Constant)
                    }
        assert "repair_encoding" in dispatched

    def test_runs_before_the_destructive_purge(self):
        assert worker.STAGE_ORDER.index("repair_encoding") < worker.STAGE_ORDER.index(
            "purge_closed"
        )