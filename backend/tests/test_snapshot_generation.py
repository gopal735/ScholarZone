"""The public snapshot must be derived from the database, and must reconcile.

The header of ``frontend/public/scholarships-snapshot.json`` publishes counts
that nobody checks. Every failure these tests cover is a way for the header to
say one thing while the export does another:

- the excluded buckets not adding up, so a record silently vanishes without
  being counted anywhere;
- the legacy ``is_verified`` boolean being exported as the public ``verified``
  claim, which the API derives from ``verification_status`` instead, so the
  same record reads as verified on one surface and unverified on another;
- a database column that does not exist, or a database file that does not
  exist, surfacing as an opaque ``KeyError`` on row 1;
- a connection left open when the export fails;
- internal workflow columns reaching a public file.

Each test builds its own database with a different row set, so the assertions
are about the derivation and not about one particular dataset.
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPOSITORY_ROOT / "generate_snapshot.py"


@pytest.fixture(scope="module")
def generator():
    """Load generate_snapshot.py as a module without a package."""
    spec = importlib.util.spec_from_file_location("generate_snapshot_under_test", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


# The columns the export reads, with the same shapes SQLite hands back for the
# real database. Written explicitly rather than through the ORM so a test can
# also create a database that is missing one.
# The columns the export reads, with the same storage shapes SQLite hands
# back for the real database (the visibility columns are NOT NULL there, the
# lifecycle columns are VARCHAR). Written explicitly rather than through the
# ORM so a test can also create a database that is missing one or that holds a
# value the real schema forbids.
COLUMN_DEFINITIONS = {
    "id": "INTEGER PRIMARY KEY",
    "title": "VARCHAR(500)",
    "country": "VARCHAR(100)",
    "degree": "VARCHAR(200)",
    "funding": "VARCHAR(500)",
    "deadline_display": "VARCHAR(500)",
    "deadline_date": "DATE",
    "deadline_precision": "VARCHAR(20)",
    "status": "VARCHAR(20) NOT NULL",
    "is_verified": "BOOLEAN",
    "created_at": "DATETIME NOT NULL",
    "last_verified_at": "DATE",
    "verification_status": "TEXT NOT NULL",
    "official_source_url": "VARCHAR(500)",
    "official_source": "VARCHAR(200)",
    "updated_at": "DATETIME",
    "image_url": "VARCHAR(500)",
    "image_source_type": "VARCHAR(50)",
    "image_kind": "VARCHAR(50)",
    "image_source_url": "VARCHAR(500)",
    "image_verified_at": "TIMESTAMP",
    "image_alt_text": "TEXT",
    "description": "TEXT",
    "region": "TEXT",
    "duration": "TEXT",
    "application_period": "TEXT",
    "catalogue_url": "TEXT",
    "official_updates_url": "TEXT",
    "application_link": "TEXT",
    "eligibility": "TEXT",
    "eligibility_summary": "TEXT",
    "benefits": "TEXT",
    "coverage": "TEXT",
    "requirements": "TEXT",
    "documents": "TEXT",
    "english_requirement": "TEXT",
    "application_method": "TEXT",
    "selection_notes": "TEXT",
    "program_type": "TEXT",
    "best_fit": "TEXT",
    "last_verified_date": "DATE",
    "notes": "TEXT",
    "is_archived": "BOOLEAN NOT NULL DEFAULT 0",
    # Internal workflow state. Present in the real table, and the whole point
    # of the allowlist tests below.
    "verification_notes": "TEXT",
    "verified_by": "VARCHAR(100)",
    "next_verification_due": "DATE",
    "archived_at": "DATETIME",
    "archived_reason": "TEXT",
    "image_evaluation_status": "VARCHAR(30)",
    "image_evaluated_at": "DATETIME",
    "auto_delete_candidate_since": "DATETIME",
    "deletion_protected": "BOOLEAN",
}

SNAPSHOT_COLUMNS = tuple(COLUMN_DEFINITIONS)


@pytest.fixture
def public_field_set(generator):
    return set(generator.PUBLIC_FIELDS)


def make_database(path: Path, rows, *, columns=SNAPSHOT_COLUMNS) -> str:
    """Create a SQLite database holding the given rows."""
    connection = sqlite3.connect(path)
    try:
        definitions = ", ".join(
            f'"{name}" {COLUMN_DEFINITIONS.get(name, "TEXT")}' for name in columns
        )
        connection.execute(f"CREATE TABLE scholarships ({definitions})")
        placeholders = ", ".join("?" for _ in columns)
        column_list = ", ".join(f'"{name}"' for name in columns)
        for row in rows:
            connection.execute(
                f"INSERT INTO scholarships ({column_list}) VALUES ({placeholders})",
                tuple(row.get(name) for name in columns),
            )
        connection.commit()
    finally:
        connection.close()
    return str(path)


def base_row(**overrides):
    row = {
        "title": "A Scholarship",
        "country": "Canada",
        "degree": "PhD",
        "funding": "Fully Funded",
        "deadline_display": "31 December 2026",
        "deadline_date": "2026-12-31",
        "deadline_precision": "exact",
        "status": "open",
        "is_verified": 0,
        "last_verified_at": "2026-10-01",
        "verification_status": "active",
        "official_source_url": "https://example.org/1",
        "official_source": "Example University",
        "updated_at": "2026-10-01 12:00:00",
        # Distinct from updated_at. Several tests would otherwise be unable to
        # tell a recent-add ordering from a recent-update ordering, because
        # there would be nothing to tell them apart.
        "created_at": "2026-08-01 12:00:00",
        "image_url": "https://example.org/1.png",
        "image_source_type": "official_university",
        "image_kind": "official_logo",
        "image_source_url": "https://example.org/source",
        "image_verified_at": "2025-06-26 00:00:00.000000",
        "image_alt_text": None,
        "description": "A description",
        "region": None,
        "duration": None,
        "application_period": None,
        "catalogue_url": None,
        "official_updates_url": None,
        "application_link": None,
        "eligibility": '["Open to all"]',
        "eligibility_summary": None,
        "benefits": '["Tuition"]',
        "coverage": '["Tuition"]',
        "requirements": '["CV"]',
        "documents": '["CV"]',
        "english_requirement": None,
        "application_method": '["Online"]',
        "selection_notes": None,
        "program_type": None,
        "best_fit": None,
        "last_verified_date": "2026-10-01",
        "notes": None,
        "is_archived": 0,
        "verification_notes": "reviewer note",
        "verified_by": "reviewer",
        "next_verification_due": "2027-01-01",
        "archived_at": None,
        "archived_reason": None,
        "image_evaluation_status": "ok",
        "image_evaluated_at": None,
        "auto_delete_candidate_since": None,
        "deletion_protected": 0,
    }
    row.update(overrides)
    return row


def export(generator, database_path: str, tmp_path: Path) -> dict:
    output = tmp_path / "scholarships-snapshot.json"
    return generator.generate_snapshot(database_path, str(output))


# ── Metadata derived from the actual database ─────────────────────────────


def test_metadata_derives_from_the_database_not_from_constants(generator, tmp_path):
    # Two databases with different row sets produce different metadata. The
    # counts must not be literals that merely happen to match one dataset.
    first = make_database(tmp_path / "small.db", [base_row(id=1)])
    second = make_database(
        tmp_path / "larger.db",
        [
            base_row(id=1, title="One"),
            base_row(id=2, title="Two", status="closed"),
            base_row(id=3, title="Three", is_archived=1),
        ],
    )

    small = export(generator, first, tmp_path)
    larger = export(generator, second, tmp_path / "second")

    assert small["meta"]["source_record_count"] == 1
    assert small["meta"]["public_record_count"] == 1
    assert larger["meta"]["source_record_count"] == 3
    assert larger["meta"]["public_record_count"] == 1
    assert larger["meta"]["excluded"] == {"closed": 1, "archived": 1, "quarantined": 0}


def test_excluded_buckets_account_for_overlap_without_double_counting(generator, tmp_path):
    # A record that is both closed and archived is one excluded row, not two.
    make_database(
        tmp_path / "overlap.db",
        [
            base_row(id=1, title="Public"),
            base_row(id=2, title="Closed and archived", status="closed", is_archived=1),
            base_row(id=3, title="Closed only", status="closed"),
            base_row(id=4, title="Archived only", is_archived=1),
            base_row(id=5, title="Quarantined", verification_status="quarantined"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "overlap.db"), tmp_path)
    excluded = snapshot["meta"]["excluded"]

    assert excluded == {"closed": 2, "archived": 2, "quarantined": 1}
    assert sum(excluded.values()) == 5
    assert snapshot["meta"]["excluded_union"] == 4
    assert snapshot["meta"]["source_record_count"] == 5
    assert snapshot["meta"]["public_record_count"] == 1


def test_source_count_reconciles_with_public_plus_excluded_union(generator, tmp_path):
    make_database(
        tmp_path / "reconcile.db",
        [
            base_row(id=1),
            base_row(id=2, status="closed"),
            base_row(id=3, is_archived=1),
            base_row(id=4, verification_status="quarantined"),
            base_row(id=5, status="closed", verification_status="quarantined"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "reconcile.db"), tmp_path)
    meta = snapshot["meta"]

    assert meta["source_record_count"] == meta["public_record_count"] + meta["excluded_union"]


def test_a_null_visibility_column_is_an_error_not_a_silent_shrink(generator, tmp_path):
    # A NULL status makes the predicate evaluate to NULL, which a WHERE clause
    # treats as "exclude". The record would then be missing from the export
    # without appearing in any excluded bucket, and the header would lie.
    #
    # The real schema declares all three visibility columns NOT NULL, so this
    # builds a table with that constraint dropped to model the violation.
    relaxed = {
        name: ("INTEGER PRIMARY KEY" if name == "id" else definition.replace(" NOT NULL", ""))
        for name, definition in COLUMN_DEFINITIONS.items()
    }

    connection = sqlite3.connect(tmp_path / "null_status.db")
    try:
        definitions = ", ".join(f'"{name}" {relaxed[name]}' for name in SNAPSHOT_COLUMNS)
        connection.execute(f"CREATE TABLE scholarships ({definitions})")
        for record in (base_row(id=1), base_row(id=2, status=None)):
            values = tuple(record.get(name) for name in SNAPSHOT_COLUMNS)
            placeholders = ", ".join("?" for _ in SNAPSHOT_COLUMNS)
            column_list = ", ".join(f'"{name}"' for name in SNAPSHOT_COLUMNS)
            connection.execute(
                f"INSERT INTO scholarships ({column_list}) VALUES ({placeholders})",
                values,
            )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SystemExit, match="NULL status"):
        export(generator, str(tmp_path / "null_status.db"), tmp_path)


def test_a_missing_database_fails_with_the_reason(generator, tmp_path):
    missing = tmp_path / "does-not-exist.db"

    with pytest.raises(SystemExit, match="Snapshot source not found"):
        export(generator, str(missing), tmp_path)


def test_a_database_without_the_table_fails_with_the_reason(generator, tmp_path):
    empty = tmp_path / "empty.db"
    connection = sqlite3.connect(empty)
    connection.execute("CREATE TABLE something_else (id INTEGER)")
    connection.commit()
    connection.close()

    with pytest.raises(SystemExit, match="No 'scholarships' table"):
        export(generator, str(empty), tmp_path)


def test_a_missing_column_fails_with_the_reason(generator, tmp_path):
    columns = tuple(name for name in SNAPSHOT_COLUMNS if name != "deadline_date")
    make_database(tmp_path / "no_deadline.db", [base_row(id=1)], columns=columns)

    with pytest.raises(SystemExit, match="missing columns"):
        export(generator, str(tmp_path / "no_deadline.db"), tmp_path)


def test_a_failed_export_closes_the_connection(generator, tmp_path):
    # The connection is closed on every path, so a failed export cannot leak a
    # handle. Proven by holding the file lock SQLite takes and observing that a
    # later writer can still take it.
    relaxed = {
        name: ("INTEGER PRIMARY KEY" if name == "id" else definition.replace(" NOT NULL", ""))
        for name, definition in COLUMN_DEFINITIONS.items()
    }
    definitions = ", ".join(f'"{name}" {relaxed[name]}' for name in SNAPSHOT_COLUMNS)
    placeholders = ", ".join("?" for _ in SNAPSHOT_COLUMNS)
    column_list = ", ".join(f'"{name}"' for name in SNAPSHOT_COLUMNS)

    connection = sqlite3.connect(tmp_path / "boom.db")
    try:
        connection.execute(f"CREATE TABLE scholarships ({definitions})")
        for record in (base_row(id=1), base_row(id=2, status=None)):
            connection.execute(
                f"INSERT INTO scholarships ({column_list}) VALUES ({placeholders})",
                tuple(record.get(name) for name in SNAPSHOT_COLUMNS),
            )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(SystemExit):
        export(generator, str(tmp_path / "boom.db"), tmp_path)

    check = sqlite3.connect(str(tmp_path / "boom.db"), timeout=2)
    try:
        check.execute("SELECT COUNT(*) FROM scholarships")
    finally:
        check.close()


# ── Visibility and the public contract ───────────────────────────────────


def test_every_canonical_exclusion_is_excluded(generator, tmp_path):
    make_database(
        tmp_path / "visibility.db",
        [
            base_row(id=1, title="Public"),
            base_row(id=2, title="Closed", status="closed"),
            base_row(id=3, title="Archived", is_archived=1),
            base_row(id=4, title="Quarantined", verification_status="quarantined"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "visibility.db"), tmp_path)
    assert [record["title"] for record in snapshot["scholarships"]] == ["Public"]


def test_an_unverified_record_is_not_hidden_for_being_unverified(generator, tmp_path):
    # No verification or image gate is introduced here. A record that is
    # neither closed, archived nor quarantined is exported even with no
    # verification and no image, exactly as the public list serves it.
    make_database(
        tmp_path / "unverified.db",
        [
            base_row(
                id=1,
                title="Unverified, no image",
                verification_status="unverified",
                is_verified=0,
                image_url=None,
            ),
        ],
    )

    snapshot = export(generator, str(tmp_path / "unverified.db"), tmp_path)
    assert [record["title"] for record in snapshot["scholarships"]] == ["Unverified, no image"]
    assert snapshot["stats"]["with_image"] == 0


def test_verified_is_derived_from_verification_status_not_the_legacy_column(generator, tmp_path):
    # The public API derives `verified` from `verification_status == "active"`.
    # The legacy `is_verified` boolean disagrees on these rows, and exporting it
    # published a claim the API does not make.
    make_database(
        tmp_path / "verified.db",
        [
            base_row(id=1, title="Legacy says no", is_verified=0, verification_status="active"),
            base_row(id=2, title="Legacy says yes", is_verified=1, verification_status="outdated"),
            base_row(id=3, title="Legacy absent", is_verified=None, verification_status="active"),
            base_row(id=4, title="Partially verified", is_verified=1, verification_status="partial"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "verified.db"), tmp_path)
    verified = {record["title"]: record["verified"] for record in snapshot["scholarships"]}

    assert verified == {
        "Legacy says no": True,
        "Legacy says yes": False,
        "Legacy absent": True,
        "Partially verified": False,
    }
    assert snapshot["stats"]["verified_active"] == 2


def test_an_absent_verification_status_is_reported_as_unresolved(generator, tmp_path):
    # Mirrors the schema's field validator, which reports no usable status as
    # the uncertainty status rather than as active or as null.
    #
    # The real schema declares the column NOT NULL, so a blank string is the
    # reachable form of "no usable status"; the None case is covered by the
    # null-visibility test above, which treats it as a repair-me first.
    relaxed = {
        name: definition.replace(" NOT NULL", "") for name, definition in COLUMN_DEFINITIONS.items()
    }
    relaxed["id"] = "INTEGER PRIMARY KEY"

    connection = sqlite3.connect(tmp_path / "absent_status.db")
    try:
        definitions = ", ".join(f'"{name}" {relaxed[name]}' for name in SNAPSHOT_COLUMNS)
        connection.execute(f"CREATE TABLE scholarships ({definitions})")
        placeholders = ", ".join("?" for _ in SNAPSHOT_COLUMNS)
        column_list = ", ".join(f'"{name}"' for name in SNAPSHOT_COLUMNS)
        for record in (
            base_row(id=1, title="Blank status", verification_status="   "),
        ):
            connection.execute(
                f"INSERT INTO scholarships ({column_list}) VALUES ({placeholders})",
                tuple(record.get(name) for name in SNAPSHOT_COLUMNS),
            )
        connection.commit()
    finally:
        connection.close()

    snapshot = export(generator, str(tmp_path / "absent_status.db"), tmp_path)
    statuses = {record["title"]: record["verification_status"] for record in snapshot["scholarships"]}

    assert statuses == {"Blank status": "needs_review"}
    assert all(record["verified"] is False for record in snapshot["scholarships"])


def test_an_unrecognised_lifecycle_status_is_not_invented(generator, tmp_path):
    make_database(
        tmp_path / "unknown_status.db",
        [base_row(id=1, title="Weird", status="under-review")],
    )

    snapshot = export(generator, str(tmp_path / "unknown_status.db"), tmp_path)
    assert snapshot["scholarships"][0]["status"] is None


def test_records_are_exported_in_a_deterministic_order(generator, tmp_path):
    make_database(
        tmp_path / "order.db",
        [base_row(id=3, title="Third"), base_row(id=1, title="First"), base_row(id=2, title="Second")],
    )

    first = export(generator, str(tmp_path / "order.db"), tmp_path / "a")
    second = export(generator, str(tmp_path / "order.db"), tmp_path / "b")

    assert [record["id"] for record in first["scholarships"]] == [1, 2, 3]
    assert first["scholarships"] == second["scholarships"]


# ── Serialisation, dates and the public schema ───────────────────────────


def test_dates_are_normalised_to_the_shape_the_api_serialises(generator, tmp_path):
    make_database(
        tmp_path / "dates.db",
        [
            base_row(
                id=1,
                updated_at="2026-10-01 12:00:00",
                image_verified_at="2025-06-26 00:00:00.000000",
                last_verified_at="2026-10-01",
                deadline_date="2026-12-31",
            ),
        ],
    )

    snapshot = export(generator, str(tmp_path / "dates.db"), tmp_path)
    record = snapshot["scholarships"][0]

    # `updated_at` and `image_verified_at` are datetime columns, so the API
    # answers with ISO 8601; the database stores its own text shape.
    assert record["updated_at"] == "2026-10-01T12:00:00"
    assert record["image_verified_at"] == "2025-06-26T00:00:00"
    # The date-typed columns stay `YYYY-MM-DD`.
    assert record["last_verified_at"] == "2026-10-01"
    assert record["deadline_date"] == "2026-12-31"


def test_an_unparseable_timestamp_becomes_null_rather_than_raising(generator, tmp_path):
    make_database(
        tmp_path / "bad_date.db",
        [base_row(id=1, updated_at="not a date", image_verified_at="also not a date")],
    )

    snapshot = export(generator, str(tmp_path / "bad_date.db"), tmp_path)
    record = snapshot["scholarships"][0]
    assert record["updated_at"] is None
    assert record["image_verified_at"] is None


def test_list_fields_are_always_lists(generator, tmp_path):
    make_database(
        tmp_path / "lists.db",
        [
            base_row(
                id=1,
                eligibility=None,
                benefits='["Tuition", null]',
                coverage="   ",
                requirements="A single string",
                documents=None,
                application_method=None,
            ),
        ],
    )

    snapshot = export(generator, str(tmp_path / "lists.db"), tmp_path)
    record = snapshot["scholarships"][0]

    assert record["eligibility"] == []
    assert record["benefits"] == ["Tuition"]
    assert record["coverage"] == []
    assert record["requirements"] == ["A single string"]
    assert record["documents"] == []
    assert record["application_method"] == []
    # `required_documents` is an alias and stays in step with `documents`.
    assert record["required_documents"] == record["documents"]


def test_ids_keep_one_type_across_every_record(generator, tmp_path):
    make_database(tmp_path / "ids.db", [base_row(id=1), base_row(id=2)])

    snapshot = export(generator, str(tmp_path / "ids.db"), tmp_path)
    assert {type(record["id"]).__name__ for record in snapshot["scholarships"]} == {"int"}


def test_aliases_agree_with_the_fields_they_mirror(generator, tmp_path):
    make_database(
        tmp_path / "aliases.db",
        [base_row(id=1, title="Aliased", degree="MSc", funding="Stipend")],
    )

    record = export(generator, str(tmp_path / "aliases.db"), tmp_path)["scholarships"][0]
    assert record["name"] == record["title"]
    assert record["degree_levels"] == record["degree"]
    assert record["funding_type"] == record["funding"]


def test_only_public_fields_are_exported(generator, public_field_set, tmp_path):
    make_database(tmp_path / "allowlist.db", [base_row(id=1)])

    snapshot = export(generator, str(tmp_path / "allowlist.db"), tmp_path)
    for record in snapshot["scholarships"]:
        assert set(record) <= public_field_set

    # The allowlist, not a blacklist. These are the internal workflow columns
    # that must never reach a public file.
    for internal_field in (
        "verification_notes",
        "verified_by",
        "next_verification_due",
        "archived_at",
        "archived_reason",
        "image_evaluation_status",
        "image_evaluated_at",
        "auto_delete_candidate_since",
        "deletion_protected",
        "is_archived",
        "is_verified",
    ):
        assert internal_field not in public_field_set


def test_a_public_field_added_to_the_export_is_caught(generator, public_field_set):
    # The allowlist is the mechanism; this asserts the mechanism holds.
    # An internal column appearing in PUBLIC_FIELDS without someone deciding
    # to publish it is a defect, and this test fails when that happens.
    forbidden = {
        "is_archived",
        "archived_at",
        "archived_reason",
        "is_verified",
        "verified_by",
        "verification_notes",
        "next_verification_due",
        "image_evaluation_status",
        "image_evaluated_at",
        "auto_delete_candidate_since",
        "deletion_protected",
    }
    assert forbidden.isdisjoint(public_field_set)


def test_statistics_match_the_records_actually_exported(generator, tmp_path):
    make_database(
        tmp_path / "stats.db",
        [
            base_row(id=1, status="open", verification_status="active", funding="Fully Funded",
                     image_url="https://example.org/1.png", official_source="Example A"),
            base_row(id=2, status="closing-soon", verification_status="active", funding="Partial",
                     image_url=None, official_source="Example B"),
            base_row(id=3, status="upcoming", verification_status="outdated", funding="Fully Funded",
                     image_url="https://example.org/3.png", official_source=None),
        ],
    )

    snapshot = export(generator, str(tmp_path / "stats.db"), tmp_path)
    stats = snapshot["stats"]
    records = snapshot["scholarships"]

    assert stats["total"] == len(records)
    assert stats["countries"] == len({record["country"] for record in records})
    assert stats["open"] == sum(1 for record in records if record["status"] == "open")
    assert stats["closing_soon"] == sum(1 for record in records if record["status"] == "closing-soon")
    assert stats["upcoming"] == sum(1 for record in records if record["status"] == "upcoming")
    assert stats["verified_active"] == sum(1 for record in records if record["verified"])
    assert stats["with_image"] == sum(1 for record in records if record["image_url"])
    assert stats["with_official_source"] == sum(1 for record in records if record["official_source"])

    # `verified_active` is counted from the exported `verified` field, so the
    # two can never disagree about the same file.
    assert stats["verified_active"] == sum(1 for record in records if record["verified"] is True)


def test_the_written_file_round_trips_as_valid_json(generator, tmp_path):
    make_database(tmp_path / "round_trip.db", [base_row(id=1, title="Round Trip")])
    output = tmp_path / "nested" / "dir" / "snapshot.json"

    snapshot = generator.generate_snapshot(str(tmp_path / "round_trip.db"), str(output))

    assert output.exists()
    with open(output, encoding="utf-8") as handle:
        assert json.load(handle) == snapshot
    assert snapshot["meta"]["public_record_count"] == 1


def test_the_export_is_reproducible_for_the_same_database(generator, tmp_path):
    database = make_database(tmp_path / "stable.db", [base_row(id=1), base_row(id=2)])

    first = export(generator, database, tmp_path / "one")
    second = export(generator, database, tmp_path / "two")

    assert first["scholarships"] == second["scholarships"]
    assert first["meta"]["source_record_count"] == second["meta"]["source_record_count"]


def test_the_committed_snapshot_matches_the_documented_public_contract(
    generator,
    public_field_set,
):
    """The committed artifact itself holds to the same rules.

    This is the one test that reads the real file. It does not claim production
    parity - the local database is not the production database - it only
    asserts that the artifact the frontend serves satisfies the contract the
    service documents.
    """
    snapshot_path = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
    if not snapshot_path.exists():
        pytest.skip("committed snapshot is not present")

    with open(snapshot_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)

    meta = snapshot["meta"]
    assert meta["source_record_count"] == meta["public_record_count"] + meta["excluded_union"]
    assert meta["public_record_count"] == len(snapshot["scholarships"])

    for record in snapshot["scholarships"]:
        assert set(record) <= public_field_set
        # The published boolean and the status it is derived from must agree.
        assert record["verified"] == (record["verification_status"] == "active")

    stats = snapshot["stats"]
    assert stats["verified_active"] == sum(
        1 for record in snapshot["scholarships"] if record["verified"] is True
    )
    assert stats["total"] == len(snapshot["scholarships"])


# ── Sort orderings ───────────────────────────────────────────────────────
#
# Two of the repository's sort keys are not public fields: `recently-added`
# orders by `created_at`, and `recommended` (and `default`) order by the legacy
# `is_verified` boolean. The snapshot therefore carries the orderings as ID
# lists computed with the repository's own SQL. These tests pin that the
# orderings are generated, that they cover exactly the public set, and that they
# agree with the SQL the repository would run - not with a restatement of it.


def _db_order(cursor, where: str, expressions) -> list[int]:
    """Run the repository's ORDER BY expressions directly, as the comparison."""
    cursor.execute(f"SELECT id FROM scholarships WHERE {where} ORDER BY {', '.join(expressions)}")
    return [int(row[0]) for row in cursor.fetchall()]


def test_the_repository_orders_recently_added_by_created_at(generator, tmp_path):
    # The live rule. Stated here so the ordering test has something to compare
    # against that is not the generator's own copy of the rule.
    where = generator.PUBLIC_VISIBILITY_WHERE
    make_database(
        tmp_path / "created.db",
        [
            base_row(id=1, created_at="2026-01-05 09:00:00", updated_at="2026-09-01 00:00:00"),
            base_row(id=2, created_at="2026-04-01 09:00:00", updated_at="2026-08-01 00:00:00"),
            base_row(id=3, created_at="2026-02-01 09:00:00", updated_at="2026-10-01 00:00:00"),
        ],
    )

    connection = sqlite3.connect(str(tmp_path / "created.db"))
    try:
        cursor = connection.cursor()
        expected = _db_order(cursor, where, ["created_at DESC", "id ASC"])
    finally:
        connection.close()

    # created_at desc is 2 (April), 3 (Feb), 1 (Jan). updated_at desc would be
    # 3, 1, 2 - a different order, which is exactly the bug this fixes.
    assert expected == [2, 3, 1]

    snapshot = export(generator, str(tmp_path / "created.db"), tmp_path)
    assert snapshot["meta"]["sort_orders"]["recently-added"] == [2, 3, 1]


def test_snapshot_orders_match_the_rule_for_every_mode(generator, tmp_path):
    make_database(
        tmp_path / "orders.db",
        [
            base_row(
                id=1,
                title="Alpha",
                funding="Fully Funded",
                is_verified=1,
                status="open",
                created_at="2026-01-01 00:00:00",
                updated_at="2026-03-01 00:00:00",
                deadline_date="2026-06-01",
            ),
            base_row(
                id=2,
                title="Beta",
                funding="Partial",
                is_verified=0,
                status="closing-soon",
                created_at="2026-05-01 00:00:00",
                updated_at="2026-05-01 00:00:00",
                deadline_date="2027-01-01",
            ),
            base_row(
                id=3,
                title="Gamma",
                funding="Fully Funded (4-year bond)",
                is_verified=1,
                status="upcoming",
                created_at="2026-02-01 00:00:00",
                updated_at="2026-04-01 00:00:00",
                deadline_date=None,
            ),
            base_row(
                id=4,
                title="Delta",
                funding="fully funded",
                is_verified=0,
                status="open",
                created_at="2026-06-01 00:00:00",
                updated_at="2026-01-01 00:00:00",
                deadline_date="2026-05-01",
            ),
        ],
    )

    snapshot = export(generator, str(tmp_path / "orders.db"), tmp_path)
    published = snapshot["meta"]["sort_orders"]

    connection = sqlite3.connect(str(tmp_path / "orders.db"))
    try:
        cursor = connection.cursor()
        where = generator.PUBLIC_VISIBILITY_WHERE
        for mode in generator.SORT_MODES:
            expected = _db_order(cursor, where, generator.SORT_MODES[mode])
            assert published[mode] == expected, (
                f"mode {mode!r}: published {published[mode]}, rule gives {expected}"
            )
    finally:
        connection.close()


def test_every_ordering_covers_exactly_the_public_records(generator, tmp_path):
    make_database(
        tmp_path / "coverage.db",
        [
            base_row(id=1),
            base_row(id=2, status="closed"),
            base_row(id=3, is_archived=1),
            base_row(id=4, verification_status="quarantined"),
            base_row(id=5),
        ],
    )

    snapshot = export(generator, str(tmp_path / "coverage.db"), tmp_path)
    public_ids = [record["id"] for record in snapshot["scholarships"]]
    assert public_ids == [1, 5]

    for mode, order in snapshot["meta"]["sort_orders"].items():
        assert sorted(order) == public_ids, f"mode {mode!r} does not cover exactly the public set"
        assert len(order) == len(set(order)), f"mode {mode!r} repeats an id"


def test_the_ordering_coverage_guard_fires_when_the_sets_disagree(generator, tmp_path):
    # The generator refuses an ordering that does not cover exactly the records
    # it exported. The guard cannot be reached through a SORT_MODES entry alone
    # - the queries are built from the same WHERE clause - so this exercises it
    # directly, by handing it a set that disagrees with the database.
    make_database(tmp_path / "guard.db", [base_row(id=1), base_row(id=2)])
    connection = sqlite3.connect(str(tmp_path / "guard.db"))
    try:
        cursor = connection.cursor()
        with pytest.raises(AssertionError, match="does not cover exactly the public records"):
            generator._build_sort_orders(cursor, [999])
    finally:
        connection.close()


def test_orderings_are_deterministic(generator, tmp_path):
    database = make_database(
        tmp_path / "deterministic.db",
        [base_row(id=1), base_row(id=2), base_row(id=3)],
    )

    first = export(generator, database, tmp_path / "one")
    second = export(generator, database, tmp_path / "two")

    assert first["meta"]["sort_orders"] == second["meta"]["sort_orders"]
    assert sorted(first["meta"]["sort_orders"]) == first["meta"]["sort_order_modes"]


def test_the_ordering_carries_no_internal_column(generator, tmp_path):
    make_database(tmp_path / "noprivate.db", [base_row(id=1)])

    snapshot = export(generator, str(tmp_path / "noprivate.db"), tmp_path)
    orders = snapshot["meta"]["sort_orders"]

    # Only IDs, in arrays of integers. The columns the live ordering is derived
    # from must not appear anywhere in the file.
    assert all(isinstance(order, list) for order in orders.values())
    assert all(
        isinstance(entry, int)
        for order in orders.values()
        for entry in order
    )
    dumped = json.dumps(snapshot)
    for field in ("created_at", "is_verified", "verification_notes", "archived_at"):
        assert f'"{field}"' not in dumped, f"{field} leaked into the snapshot"


# ── The repeatable parity verifier ───────────────────────────────────────


@pytest.fixture
def parity_tool():
    """Load verify_snapshot_parity.py without adding a side effect on import."""
    path = REPOSITORY_ROOT / "verify_snapshot_parity.py"
    spec = importlib.util.spec_from_file_location("verify_snapshot_parity_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_verifier_passes_on_a_snapshot_it_was_generated_from(generator, parity_tool, tmp_path):
    database = make_database(
        tmp_path / "verified.db",
        [
            base_row(id=1, title="One", funding="Fully Funded"),
            base_row(id=2, title="Two", funding="Partial", status="upcoming"),
            base_row(id=3, title="Three", funding="Fully Funded", created_at="2026-05-01 00:00:00"),
        ],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    generator.generate_snapshot(database, str(snapshot_path))

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert result.ok, "\n".join(result.findings)
    assert result.checks >= 30


def test_the_verifier_detects_a_snapshot_from_a_different_database(
    generator, parity_tool, tmp_path
):
    # The snapshot is generated from one state and checked against another. The
    # counts happen to be equal here, which is the case that a count-only check
    # would miss: the records themselves differ.
    source = make_database(
        tmp_path / "source.db",
        [base_row(id=1, title="Original"), base_row(id=2, title="Also original")],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    generator.generate_snapshot(source, str(snapshot_path))

    other = make_database(
        tmp_path / "other.db",
        [base_row(id=9, title="Different record"), base_row(id=10, title="Another different")],
    )

    result = parity_tool.verify(other, str(snapshot_path), generator)

    assert not result.ok
    joined = "\n".join(result.findings)
    assert "public ID sets match exactly" in joined


def test_the_verifier_detects_a_missing_and_an_extra_record(generator, parity_tool, tmp_path):
    database = make_database(
        tmp_path / "ids.db",
        [base_row(id=1), base_row(id=2), base_row(id=3)],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # Drop one record and invent another, keeping the count identical so the
    # difference is invisible to any aggregate check.
    snapshot["scholarships"] = [
        snapshot["scholarships"][0],
        {**snapshot["scholarships"][1], "id": 999},
        snapshot["scholarships"][2],
    ]
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    findings = "\n".join(result.findings)
    assert "999" in findings
    assert "2" in findings


def test_the_verifier_detects_a_stale_hidden_record(generator, parity_tool, tmp_path):
    # A record archived after the snapshot was generated must be reported, not
    # silently served as if it were still live.
    database = make_database(tmp_path / "stale.db", [base_row(id=1), base_row(id=2)])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    generator.generate_snapshot(database, str(snapshot_path))

    connection = sqlite3.connect(database)
    try:
        connection.execute("UPDATE scholarships SET is_archived = 1 WHERE id = 2")
        connection.commit()
    finally:
        connection.close()

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    joined = "\n".join(result.findings)
    # The record is still exported although the database now hides it, so the
    # counts stop agreeing and the ID sets stop agreeing with it.
    assert "exported record count" in joined
    assert "public ID sets match exactly" in joined


def test_the_verifier_detects_a_changed_field(generator, parity_tool, tmp_path):
    database = make_database(tmp_path / "fields.db", [base_row(id=1, title="Original")])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # A value that is genuinely different from the source row, so the check
    # under test is separating the two rather than comparing a value with
    # itself.
    snapshot["scholarships"][0]["funding"] = "Partial Funding Only"
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("funding" in finding for finding in result.findings)


def test_the_verifier_detects_a_header_count_that_disagrees_with_the_database(
    generator, parity_tool, tmp_path
):
    database = make_database(
        tmp_path / "header.db",
        [base_row(id=1), base_row(id=2, status="closed")],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # The database has 2 source rows. The header now claims 1, which is also the
    # public count - so the internal arithmetic still looks self-consistent and
    # only a comparison against the database catches it.
    snapshot["meta"]["source_record_count"] = 1
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("source_record_count" in finding for finding in result.findings)


def test_the_verifier_detects_when_the_header_cannot_reconcile(generator, parity_tool, tmp_path):
    database = make_database(
        tmp_path / "unreconciled.db",
        [base_row(id=1), base_row(id=2, status="closed")],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # Now the invariant itself breaks: 2 source rows, but the header says one
    # public and no excluded union.
    snapshot["meta"]["source_record_count"] = 2
    snapshot["meta"]["public_record_count"] = 1
    snapshot["meta"]["excluded_union"] = 0
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("source reconciles" in finding for finding in result.findings)


def test_the_verifier_detects_an_internal_field(generator, parity_tool, tmp_path):
    database = make_database(tmp_path / "leak.db", [base_row(id=1)])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    snapshot["scholarships"][0]["verification_notes"] = "internal reviewer note"
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("internal workflow column" in finding for finding in result.findings)


def test_the_verifier_detects_a_stale_ordering(generator, parity_tool, tmp_path):
    database = make_database(tmp_path / "order.db", [base_row(id=1), base_row(id=2)])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    snapshot["meta"]["sort_orders"]["recently-added"] = list(
        reversed(snapshot["meta"]["sort_orders"]["recently-added"])
    )
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("recently-added" in finding for finding in result.findings)


def test_the_verifier_writes_to_neither_source(generator, parity_tool, tmp_path, capsys):
    # The tool must not mutate what it checks. Comparing the file contents
    # before and after is the only way to prove that.
    database = make_database(tmp_path / "readonly.db", [base_row(id=1), base_row(id=2)])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    generator.generate_snapshot(database, str(snapshot_path))

    db_before = Path(database).read_bytes()
    snapshot_before = Path(snapshot_path).read_bytes()

    parity_tool.verify(database, str(snapshot_path), generator)

    assert Path(database).read_bytes() == db_before
    assert Path(snapshot_path).read_bytes() == snapshot_before


def test_the_verifier_reports_no_scholarship_content(generator, parity_tool, tmp_path, capsys):
    # The output is meant to be safe to paste into a CI log or an issue. It must
    # carry IDs, field names and counts only.
    database = make_database(tmp_path / "quiet.db", [base_row(id=1, title="Unique Title 12345")])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    generator.generate_snapshot(database, str(snapshot_path))

    parsed = parity_tool.main(["--db", database, "--snapshot", str(snapshot_path)])
    captured = capsys.readouterr().out

    assert parsed == 0
    assert "Unique Title 12345" not in captured


def test_the_verifier_fails_when_parity_is_broken(generator, parity_tool, tmp_path):
    # The exit status is what makes this usable as a gate.
    database = make_database(tmp_path / "gate.db", [base_row(id=1), base_row(id=2)])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))
    snapshot["scholarships"] = snapshot["scholarships"][:1]
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    assert parity_tool.main(["--db", database, "--snapshot", str(snapshot_path)]) == 1


# ── Filter options ───────────────────────────────────────────────────────
#
# The directory's country/degree/funding/status/deadline-month menus used to be
# hardcoded lists. Against the real catalogue that meant: a Country menu of four
# entries when the catalogue carries 74 countries; a Degree menu whose three
# entries matched 1, 3 and 1 records; a Funding menu of one entry out of 88; and
# a Status menu offering `closed`, which the visibility predicate makes
# unmatchable. They are now derived from the records the snapshot exports.


def test_filter_options_are_derived_from_the_exported_records(generator, tmp_path):
    make_database(
        tmp_path / "filters.db",
        [
            base_row(id=1, title="One", country="Japan", degree="PhD", funding="Stipend",
                     status="open", deadline_date="2026-01-15"),
            base_row(id=2, title="Two", country="Japan", degree="Master", funding="Stipend",
                     status="open", deadline_date="2026-03-20"),
            base_row(id=3, title="Three", country="Sweden", degree="PhD", funding="Partial",
                     status="upcoming", deadline_date="2026-01-31"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "filters.db"), tmp_path)
    options = snapshot["meta"]["filter_options"]

    assert options["countries"] == ["Japan", "Sweden"]
    assert options["degrees"] == ["Master", "PhD"]
    assert options["funding_types"] == ["Partial", "Stipend"]
    assert options["statuses"] == ["open", "upcoming"]
    # Two January deadlines and one in March. Sorted numerically, so the list is
    # valid for the month control without further ordering.
    assert options["deadline_months"] == [1, 3]


def test_filter_options_exclude_a_status_the_visibility_rule_hides(generator, tmp_path):
    # A control that can never match is worse than one that is missing: it looks
    # like it works and returns nothing. Closed records are not in the public set,
    # so they must not appear as a selectable status.
    make_database(
        tmp_path / "statuses.db",
        [
            base_row(id=1, status="open"),
            base_row(id=2, status="closing-soon"),
            base_row(id=3, status="upcoming"),
            base_row(id=4, status="closed"),
        ],
    )

    snapshot = export(generator, str(tmp_path / "statuses.db"), tmp_path)
    options = snapshot["meta"]["filter_options"]

    assert options["statuses"] == ["closing-soon", "open", "upcoming"]
    assert "closed" not in options["statuses"]


def test_filter_options_are_deterministic(generator, tmp_path):
    database = make_database(
        tmp_path / "det.db",
        [
            base_row(id=1, country="Japan", degree="PhD"),
            base_row(id=2, country="Sweden", degree="Master"),
            base_row(id=3, country="Japan", degree="Master"),
        ],
    )

    first = export(generator, database, tmp_path / "one")
    second = export(generator, database, tmp_path / "two")

    assert first["meta"]["filter_options"] == second["meta"]["filter_options"]


def test_the_verifier_detects_a_filter_option_no_record_matches(generator, parity_tool, tmp_path):
    database = make_database(
        tmp_path / "opt.db",
        [base_row(id=1, country="Japan"), base_row(id=2, country="Sweden")],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # Europe is not a country any record holds, and was an option that could
    # only ever return nothing.
    snapshot["meta"]["filter_options"]["countries"] = ["Europe", "Japan", "Sweden"]
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("filter option 'countries'" in finding for finding in result.findings)


def test_the_verifier_detects_an_unmatchable_status_option(generator, parity_tool, tmp_path):
    database = make_database(tmp_path / "unmatchable.db", [base_row(id=1, status="open")])
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    snapshot["meta"]["filter_options"]["statuses"] = ["closed", "open"]
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any(
        "excludes" in finding or "statuses" in finding for finding in result.findings
    )


def test_the_verifier_detects_a_missing_country_option(generator, parity_tool, tmp_path):
    database = make_database(
        tmp_path / "missing.db",
        [base_row(id=1, country="Japan"), base_row(id=2, country="Sweden")],
    )
    snapshot_path = tmp_path / "out" / "snapshot.json"
    snapshot = generator.generate_snapshot(database, str(snapshot_path))

    # Japan is in the catalogue and cannot be reached from the control.
    snapshot["meta"]["filter_options"]["countries"] = ["Sweden"]
    with open(snapshot_path, "w", encoding="utf-8") as handle:
        json.dump(snapshot, handle)

    result = parity_tool.verify(database, str(snapshot_path), generator)

    assert not result.ok
    assert any("filter option 'countries'" in finding for finding in result.findings)
