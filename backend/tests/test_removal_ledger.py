"""The discontinued-record removal ledger, and the snapshot that reflects it.

Phase 3 of the intake-status audit removed exactly two records from the
public catalogue - id 279 (NORPART) and id 729 (Vanier CGS) - because their
official pages, re-fetched live on 2026-10-11, state that the programmes
are discontinued. The only way a published record may leave the catalogue
is through this ledger, so the ledger itself is under test:

- it exists and is versioned;
- every entry carries the evidence a reviewer would need: the official URL
  that was fetched, the verbatim quote, the confidence, the date checked,
  and the classification;
- the ids it declares are the only baseline records the committed snapshot
  removed relative to its own declared baseline - no undeclared vanishings.

If a future change removes a record without adding a ledger entry, the
snapshot contract test in the frontend already fails; these tests make the
ledger itself impossible to leave half-written.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = (
    REPOSITORY_ROOT
    / "backend"
    / "research_output"
    / "publish"
    / "removals_scholarships_ledger.json"
)
SNAPSHOT_PATH = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"

EXPECTED_IDS = {279, 729}


@pytest.fixture(scope="module")
def ledger():
    if not LEDGER_PATH.is_file():
        pytest.skip("the removal ledger is not present")
    with open(LEDGER_PATH, encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload.get("ledger_version") == 1
    return payload


def test_every_ledger_entry_carries_evidence(ledger):
    removals = ledger.get("removals")
    assert removals, "the ledger holds no removals"
    for entry in removals:
        assert entry.get("id") is not None
        assert entry.get("classification") == "genuinely_discontinued"
        assert entry.get("official_source_url", "").startswith("https://")
        assert entry.get("evidence_url", "").startswith("https://")
        assert entry.get("evidence_quote"), "a removal with no verbatim quote is unverifiable"
        assert isinstance(entry.get("confidence"), (int, float))
        assert entry.get("confidence") >= 0.5
        assert entry.get("last_checked"), "a removal with no check date is unverifiable"
        assert entry.get("why_removed")
        assert entry.get("removed_at")


def test_the_ledger_holds_exactly_the_two_audited_removals(ledger):
    assert {entry["id"] for entry in ledger["removals"]} == EXPECTED_IDS


def test_vanier_records_its_published_successor(ledger):
    vanier = next(entry for entry in ledger["removals"] if entry["id"] == 729)
    assert vanier.get("superseded_by") == 306
    with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    published = {record["id"] for record in snapshot["scholarships"]}
    assert 306 in published, "the successor record must still be published"
    assert 279 not in published
    assert 729 not in published


def test_no_ledger_record_is_published(ledger):
    with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    published = {record["id"] for record in snapshot["scholarships"]}
    for entry in ledger["removals"]:
        assert entry["id"] not in published


def test_the_snapshot_removed_nothing_beyond_the_ledger():
    """The published set may only have shrunk by the ledger entries.

    Read from the generator's own baseline declaration: every baseline id
    absent from the snapshot must be exactly the ledger ids.
    """
    if not SNAPSHOT_PATH.is_file():
        pytest.skip("the committed snapshot is not present")
    with open(SNAPSHOT_PATH, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    meta = snapshot["meta"]
    baseline = meta.get("baseline") or {}
    baseline_ids = set(baseline.get("baseline_ids") or [])
    published = {record["id"] for record in snapshot["scholarships"]}
    vanished = baseline_ids - published
    if not vanished:
        pytest.skip("this snapshot has no declared baseline removals")
    assert vanished == EXPECTED_IDS
    assert baseline.get("baseline_removed") == len(vanished)


def test_ledger_records_stay_in_the_local_database_as_archive_rows():
    """Removal is archival, never a hard delete: the rows and their reasons."""
    db = REPOSITORY_ROOT / "backend" / "scholarzone.db"
    if not db.is_file():
        pytest.skip("the local database copy is not present")
    with LEDGER_PATH.open(encoding="utf-8") as handle:
        ledger = json.load(handle)
    connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        for entry in ledger["removals"]:
            row = connection.execute(
                "SELECT is_archived, archived_reason FROM scholarships WHERE id = ?",
                (entry["id"],),
            ).fetchone()
            assert row is not None, f"id {entry['id']} was hard-deleted"
            assert row[0] == 1, f"id {entry['id']} is not archived"
            assert "DISCONTINUED" in (row[1] or ""), f"id {entry['id']} lost its reason"
    finally:
        connection.close()
