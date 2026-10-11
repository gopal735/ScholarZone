"""The reviewed enrichment applier must write only what it was given.

The 2026-10-11 publication has to get research that had no corpus path into
the local database before the snapshot can carry it: eight active records had
no citation-backed official details, and two of them need a deadline-display
correction. `apply_publish_enrichment.py` is that write, and every property
below is about it staying narrow:

- it writes the researched columns and refuses the lifecycle columns even
  when the enrichment file names them, because a publication script changing
  a record's lifecycle status is a decision for the verification workflow;
- a record id the database does not have is a hard error, not a skip: the
  enrichment is keyed by exact DB id, and a wrong mapping must never be
  silently ignored;
- a null in the research does not blank a present value - this merge adds
  facts, it never erases them;
- re-running the same enrichment performs no writes.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
APPLIER_PATH = REPOSITORY_ROOT / "apply_publish_enrichment.py"


@pytest.fixture(scope="module")
def applier():
    """Load apply_publish_enrichment.py as a module without a package."""
    spec = importlib.util.spec_from_file_location("apply_publish_enrichment_under_test", APPLIER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def database(tmp_path: Path) -> str:
    path = tmp_path / "scholarzone.db"
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            CREATE TABLE scholarships (
                id INTEGER PRIMARY KEY,
                title TEXT,
                funding_amount NUMERIC(12, 2),
                funding_currency VARCHAR(8),
                funding_period VARCHAR(64),
                tuition_coverage BOOLEAN,
                applicant_utility TEXT,
                official_details TEXT,
                programme_verification TEXT,
                deadline_display TEXT,
                status TEXT NOT NULL,
                is_archived BOOLEAN NOT NULL DEFAULT 0,
                verification_status TEXT,
                updated_at DATETIME
            )
            """
        )
        connection.execute(
            """
            INSERT INTO scholarships (
                id, title, funding_amount, funding_currency, funding_period,
                tuition_coverage, applicant_utility, official_details,
                programme_verification, deadline_display, status, is_archived,
                verification_status, updated_at
            ) VALUES (
                4, 'University of Manitoba', 25000, 'CAD', 'per year', 0,
                NULL, NULL, NULL,
                'Due by December 1', 'open', 0, 'active', '2026-10-01 10:00:00'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
    return str(path)


def write_enrichment(tmp_path: Path, payload: dict) -> str:
    path = tmp_path / "enrichment.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return str(path)


def minimal_record(**overrides) -> dict:
    record = {
        "id": 4,
        "official": {
            "official_source_urls": ["https://umanitoba.ca/financial-aid-and-awards/entrance-awards/international-excellence-entrance-scholarship"],
            "funding_amount": 25000,
            "funding_currency": "CAD",
            "funding_period": "per year",
            "tuition_coverage": False,
        },
        "verification": {
            "source_citations": [
                "https://umanitoba.ca/financial-aid-and-awards/entrance-awards/international-excellence-entrance-scholarship"
            ],
            "confidence": 0.95,
            "last_verified_date": "2026-10-11",
        },
    }
    record.update(overrides)
    return record


def test_the_enrichment_writes_the_researched_columns(applier, database, tmp_path):
    enrichment = write_enrichment(tmp_path, {"records": [minimal_record()]})

    status = applier.apply_enrichment(database, enrichment)

    assert status == 0
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM scholarships WHERE id = 4").fetchone()
    connection.close()

    official = json.loads(row["official_details"])
    verification = json.loads(row["programme_verification"])
    assert official["official_source_urls"] == [
        "https://umanitoba.ca/financial-aid-and-awards/entrance-awards/international-excellence-entrance-scholarship"
    ]
    assert verification["confidence"] == 0.95
    assert row["funding_amount"] == 25000
    assert row["tuition_coverage"] in (0, False)


def test_a_null_research_value_never_blanks_a_present_column(applier, database, tmp_path):
    # The enrichment knows the amount but has no currency: the stored currency
    # must survive, because this merge adds facts and never erases them.
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                {
                    "id": 4,
                    "official": {
                        "official_source_urls": ["https://example.org/a"],
                        "funding_amount": 25000,
                    },
                    "verification": {"source_citations": ["https://example.org/a"]},
                }
            ]
        },
    )
    applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    row = connection.execute("SELECT funding_currency, funding_amount FROM scholarships WHERE id = 4").fetchone()
    connection.close()
    assert row[0] == "CAD"
    assert row[1] == 25000


def test_a_deadline_display_correction_is_written_verbatim(applier, database, tmp_path):
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                minimal_record(
                    deadline_display="Round two: opens December 1, 2026 - submissions due January 31, 2027 at midnight AT."
                )
            ]
        },
    )
    applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    row = connection.execute("SELECT deadline_display FROM scholarships WHERE id = 4").fetchone()
    connection.close()
    assert row[0].startswith("Round two: opens December 1, 2026")


def test_a_missing_record_id_is_a_hard_error(applier, database, tmp_path):
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                minimal_record(id=99, official={"official_source_urls": ["https://example.org/x"]})
            ]
        },
    )
    with pytest.raises(SystemExit):
        applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    count = connection.execute("SELECT COUNT(*) FROM scholarships WHERE official_details IS NOT NULL").fetchone()[0]
    connection.close()
    assert count == 0, "no write may have happened for the id that does not exist"


def test_a_lifecycle_column_in_the_enrichment_is_refused(applier, database, tmp_path):
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                {
                    "id": 4,
                    "status": "closed",
                    "verification_status": "quarantined",
                    "official": {"official_source_urls": ["https://example.org/a"]},
                    "verification": {"source_citations": ["https://example.org/a"]},
                }
            ]
        },
    )
    with pytest.raises(SystemExit):
        applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    row = connection.execute("SELECT status, verification_status, official_details FROM scholarships WHERE id = 4").fetchone()
    connection.close()
    assert row[0] == "open"
    assert row[1] == "active"
    assert row[2] is None


def test_a_non_amount_funding_value_is_refused(applier, database, tmp_path):
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                {
                    "id": 4,
                    "official": {
                        "official_source_urls": ["https://example.org/a"],
                        "funding_amount": "75%",
                    },
                    "verification": {"source_citations": ["https://example.org/a"]},
                }
            ]
        },
    )
    with pytest.raises(SystemExit):
        applier.apply_enrichment(database, enrichment)


def test_rerunning_the_same_enrichment_performs_no_writes(applier, database, tmp_path):
    enrichment = write_enrichment(tmp_path, {"records": [minimal_record()]})
    applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    first = connection.execute(
        "SELECT official_details, programme_verification FROM scholarships WHERE id = 4"
    ).fetchone()
    connection.close()

    applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    second = connection.execute(
        "SELECT official_details, programme_verification FROM scholarships WHERE id = 4"
    ).fetchone()
    connection.close()
    assert first == second


def test_a_null_field_write_withdraws_a_claim_with_its_reason(applier, database, tmp_path):
    # 587's tuition_coverage is true in the database while the awarding
    # body's page describes a cash stipend with no tuition claim. The
    # research withdraws it, and the withdrawal is only allowed with the
    # reason recorded beside it.
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE scholarships SET tuition_coverage = 1 WHERE id = 4")

    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                minimal_record(
                    null_fields=["tuition_coverage"],
                    null_reason="The official page describes a cash stipend and makes no tuition claim.",
                )
            ]
        },
    )
    status = applier.apply_enrichment(database, enrichment)

    assert status == 0
    connection = sqlite3.connect(database)
    row = connection.execute("SELECT tuition_coverage FROM scholarships WHERE id = 4").fetchone()
    connection.close()
    assert row[0] is None


def test_a_null_write_without_a_reason_is_refused(applier, database, tmp_path):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE scholarships SET tuition_coverage = 1 WHERE id = 4")

    enrichment = write_enrichment(
        tmp_path, {"records": [minimal_record(null_fields=["tuition_coverage"])]}
    )
    with pytest.raises(SystemExit):
        applier.apply_enrichment(database, enrichment)

    connection = sqlite3.connect(database)
    row = connection.execute("SELECT tuition_coverage FROM scholarships WHERE id = 4").fetchone()
    connection.close()
    assert row[0] == 1, "no write may have happened when the reason is missing"


def test_a_column_that_is_not_a_researched_funding_field_cannot_be_blanked(applier, database, tmp_path):
    enrichment = write_enrichment(
        tmp_path,
        {
            "records": [
                minimal_record(
                    null_fields=["applicant_utility"],
                    null_reason="irrelevant: this column is not withdrawable",
                )
            ]
        },
    )
    with pytest.raises(SystemExit):
        applier.apply_enrichment(database, enrichment)


def test_a_missing_database_is_a_hard_error(applier, tmp_path):
    enrichment = write_enrichment(tmp_path, {"records": [minimal_record()]})
    with pytest.raises(SystemExit):
        applier.apply_enrichment(str(tmp_path / "not-here.db"), enrichment)


def test_a_blocked_record_is_absent_from_the_reviewed_enrichment_file():
    """The two records whose sources could not be reached stay unpublished.

    96 (ENS de Lyon) has a dead official source and 350 (Bioceb) was
    unreachable; neither may be enriched from a research pass that could not
    read its awarding body. This is checked against the real, committed
    enrichment file rather than a fixture, because the file is the artifact
    the publication ships.
    """
    path = (
        REPOSITORY_ROOT
        / "backend"
        / "research_output"
        / "publish"
        / "uncited_rows_research_2026-10-11.json"
    )
    if not path.exists():
        pytest.skip("the reviewed enrichment file is not present in this checkout")

    payload = json.loads(path.read_text(encoding="utf-8"))
    applied_ids = {record["id"] for record in payload["records"]}
    # The enrichment file documents the blocked records under JSON object
    # keys, which are strings by definition.
    blocked = set(str(rid) for rid in payload["_documentation"]["blocked_records"])

    assert blocked == {"96", "350"}
    assert not (applied_ids & set(int(rid) for rid in blocked)), (
        "a blocked record must not be enriched"
    )
    # Every applied record must carry both research blobs, or there is nothing
    # to publish for it.
    for record in payload["records"]:
        assert record["official"].get("official_source_urls"), f"id {record['id']} has no official URLs"
        citations = record["verification"].get("source_citations") or []
        assert citations, f"id {record['id']} has no citations"
        assert all(url.startswith(("http://", "https://")) for url in citations)
