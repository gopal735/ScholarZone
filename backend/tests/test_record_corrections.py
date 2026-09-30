"""Tests for the record-correction file and the correct stage.

Corrections rewrite a real record's address in place, so two things are pinned:
a correction may only write fields that exist and hold a valid URL, and it must
never be able to hide a record. Hiding is the retire stage's job, and conflating
the two would let a stale link quietly remove a live scholarship.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

CORRECTIONS_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "record_corrections.json"
)

ALLOWED_FIELDS = {
    "title",
    "official_source_url",
    "application_link",
    "official_source",
    "description",
}


@pytest.fixture(scope="module")
def corrections():
    raw = json.loads(CORRECTIONS_PATH.read_text(encoding="utf-8"))
    entries = raw.get("records") if isinstance(raw, dict) else raw
    return entries if isinstance(entries, list) else []


class TestCorrectionsFile:
    def test_file_exists_and_parses(self, corrections):
        assert isinstance(corrections, list)

    def test_every_entry_has_an_id_and_a_reason(self, corrections):
        for entry in corrections:
            assert isinstance(entry, dict), f"entry is not an object: {entry!r}"
            assert isinstance(entry.get("id"), int), f"entry has no integer id: {entry!r}"
            assert (entry.get("reason") or "").strip(), (
                f"{entry['id']} is corrected with no stated reason"
            )

    def test_entries_only_touch_writable_fields(self, corrections):
        for entry in corrections:
            unknown = set(entry) - ALLOWED_FIELDS - {"id", "reason", "flag", "source_page"}
            assert not unknown, f"{entry['id']} writes unknown fields: {sorted(unknown)}"
            assert ALLOWED_FIELDS & set(entry), f"{entry['id']} corrects nothing"

    def test_every_url_is_absolute_http(self, corrections):
        for entry in corrections:
            for field in ("official_source_url", "application_link"):
                value = (entry.get(field) or "").strip()
                if not value:
                    continue
                parsed = urlparse(value)
                assert parsed.scheme in ("http", "https"), (
                    f"{entry['id']} {field} is not http(s): {value}"
                )
                assert parsed.hostname, f"{entry['id']} {field} has no host: {value}"

    def test_ids_do_not_also_appear_in_the_retirement_file(self, corrections):
        """A record is corrected or retired, never both.

        Retiring a record whose link merely rotted removes a real scholarship
        from every applicant. The two files must not overlap.
        """
        retired_path = (
            Path(__file__).resolve().parents[1] / "config" / "retired_records.json"
        )
        raw = json.loads(retired_path.read_text(encoding="utf-8"))
        retired = raw.get("records") if isinstance(raw, dict) else raw
        retired_ids = {
            e.get("id") for e in (retired or []) if isinstance(e, dict)
        }
        overlap = {e["id"] for e in corrections} & retired_ids
        assert not overlap, f"records both corrected and retired: {sorted(overlap)}"


class TestCorrectStageWiring:
    def test_stage_is_registered_everywhere_it_is_selected(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        assert '"correct": do_correct' in source, "correct missing from the dispatch table"
        assert '"correct",' in source, "correct missing from STAGE_ORDER or argparse choices"

    def test_stage_validates_urls_with_a_name_it_imports(self):
        """Each stage body carries its own imports; none is inherited.

        do_correct validated an address with urlparse without importing it, so
        the first real run of the stage died with a NameError after the file
        had already been written. Unit tests could not see it because these
        stages are closures inside main(), so the import is pinned here.
        """
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_correct", 1)[1].split("def do_facts", 1)[0]
        assert "urlparse(" in body, "the correct stage no longer validates URLs"
        assert "from urllib.parse import urlparse" in body, (
            "the correct stage uses urlparse without importing it"
        )

    def test_stage_never_archives_or_quarantines(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_correct", 1)[1].split("def do_facts", 1)[0]
        for forbidden in ("is_archived", "verification_status", "session.delete"):
            assert forbidden not in body, (
                f"the correct stage must not touch {forbidden}; hiding a record is "
                f"the retire stage's decision, and a rotted link is not a reason"
            )
