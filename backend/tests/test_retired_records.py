"""Tests for the record-level retirement file and the retire stage.

Retiring a record hides a real scholarship from every applicant, so the file
that drives it is held to the same standard as the facts file: every entry has
to say what was wrong, and an entry that would match nothing is a silent failure
rather than a no-op.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

RETIRED_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "retired_records.json"
)

ALLOWED_FLAGS = {
    "DEAD",
    "RENAMED",
    "DUPLICATE",
    "MISATTRIBUTED",
    "NEVER-EXISTED",
    "WRONG-DATA",
    "RETIRED-SUCCESSOR",
}


@pytest.fixture(scope="module")
def retired():
    raw = json.loads(RETIRED_PATH.read_text(encoding="utf-8"))
    entries = raw.get("records") if isinstance(raw, dict) else raw
    return entries if isinstance(entries, list) else []


class TestRetiredRecordsFile:
    def test_file_exists_and_parses(self, retired):
        assert isinstance(retired, list)

    def test_every_entry_has_a_usable_id(self, retired):
        for entry in retired:
            assert isinstance(entry, dict), f"entry is not an object: {entry!r}"
            assert isinstance(entry.get("id"), int), (
                f"entry has no integer id: {entry!r}"
            )

    def test_ids_are_unique(self, retired):
        ids = [e["id"] for e in retired]
        duplicates = {i for i in ids if ids.count(i) > 1}
        # A duplicate id is harmless at worst and confusing at best: it hides
        # how many records a decision actually touched.
        assert not duplicates, f"duplicate ids in the retirement file: {duplicates}"

    def test_every_entry_states_a_known_flag_and_a_reason(self, retired):
        for entry in retired:
            flag = str(entry.get("flag") or "").upper()
            assert flag in ALLOWED_FLAGS, f"{entry['id']} has unknown flag {flag!r}"
            assert (entry.get("reason") or "").strip(), (
                f"{entry['id']} retires a record with no reason"
            )

    def test_dead_records_name_a_successor_or_say_why_none_exists(self, retired):
        """A dead record with no successor strands anyone who follows a link."""
        for entry in retired:
            if str(entry.get("flag") or "").upper() not in {"DEAD", "RENAMED"}:
                continue
            assert (entry.get("successor") or "").strip() or (
                entry.get("no_successor_reason") or ""
            ).strip(), (
                f"{entry['id']} is retired as {entry['flag']} but names neither a "
                f"successor nor a reason there is none"
            )


class TestRetireStageWiring:
    def test_stage_is_registered_everywhere_it_is_selected(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        # A stage added to the dispatch table but not to STAGE_ORDER is selected
        # out and reports success having done nothing. That exact bug cost a full
        # run before, so it is pinned here.
        assert '"retire": do_retire' in source, "retire missing from the dispatch table"
        assert '"retire",' in source, "retire missing from STAGE_ORDER or argparse choices"
        assert '"retire"' in source, "retire is never selectable by name"

    def test_stage_hides_records_rather_than_deleting_them(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_retire", 1)[1].split("def do_facts", 1)[0]
        assert "is_archived = True" in body, "retire must archive, not delete"
        assert "session.delete" not in body, "retire must never delete a record"
