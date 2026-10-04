"""Tests for the database-level image mutation audit.

The image regression on scholarships 14, 130 and 554 reverted with no
verification-history row and no recorded maintenance run. These tests pin the
guarantee that closes that gap: every mutation of a tracked image field leaves
an append-only database record, whoever made it.

The trigger is exercised through SQLite, which is what the project's test suite
runs on. The audited fields, the null-safe comparison and the append-only guard
are identical in the PostgreSQL DDL; the PostgreSQL statements are additionally
asserted structurally, since no PostgreSQL server is available in CI here.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.image_audit import (
    AUDIT_TABLE,
    TRACKED_IMAGE_FIELDS,
    UNATTRIBUTED,
    audit_trigger_is_installed,
    create_image_audit_schema,
    image_writer,
    instrument_engine_for_writer_context,
    postgresql_audit_ddl,
    sanitize_writer_context,
)
from app.models import Base, Scholarship

instrument_engine_for_writer_context()

VERIFIED_AT = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
EVALUATED_AT = datetime(2026, 3, 2, 12, 0, tzinfo=timezone.utc)
IMAGE_URL = "https://ethz.ch/etc.clientlibs/ethz/clientlibs/site/resources/images/imageCarousel-inner-2.jpg"

_row_counter = 0


@pytest.fixture()
def session():
    """A session on a database carrying the real audit trigger."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_image_audit_schema(connection)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        yield s
    engine.dispose()


def make_row(session, **image_fields) -> int:
    """Insert a throwaway row.

    ``official_source_url`` is unique, so a counter keeps multi-row tests from
    colliding on the same value.
    """
    global _row_counter
    _row_counter += 1
    row = Scholarship(
        title="Test programme",
        country="CH",
        degree="masters",
        funding="full",
        official_source_url=f"https://ethz.ch/en/studies/master-{_row_counter}.html",
        verification_status="active",
        is_verified=True,
        **image_fields,
    )
    session.add(row)
    session.commit()
    return row.id


def audit_rows(session) -> list:
    return list(session.execute(
        text(f"SELECT * FROM {AUDIT_TABLE} ORDER BY id")
    ).mappings())


def audit_count(session) -> int:
    return session.execute(text(f"SELECT count(*) FROM {AUDIT_TABLE}")).scalar()


def loads(value):
    return json.loads(value) if isinstance(value, str) else value


# --------------------------------------------------------------------------
# A. image_url NULL -> URL creates an audit row
# --------------------------------------------------------------------------
def test_null_to_url_creates_audit_row(session):
    row_id = make_row(session)
    assert audit_count(session) == 0, "creating a row must not audit anything"

    row = session.get(Scholarship, row_id)
    row.image_url = IMAGE_URL
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["scholarship_id"] == row_id
    assert "image_url" in events[0]["changed_fields"]


# --------------------------------------------------------------------------
# B. URL -> NULL creates an audit row  (the transition that went missing)
# --------------------------------------------------------------------------
def test_url_to_null_creates_audit_row(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_kind="program_image")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    row = session.get(Scholarship, row_id)
    row.image_url = None
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["changed_fields"] == "image_url"
    assert loads(events[0]["before_values"])["image_url"] == IMAGE_URL
    assert loads(events[0]["after_values"])["image_url"] is None


# --------------------------------------------------------------------------
# C. image_kind changes create an audit row
# --------------------------------------------------------------------------
def test_image_kind_change_creates_audit_row(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_kind="program_image")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_kind = "official_banner"
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["changed_fields"] == "image_kind"
    assert loads(events[0]["before_values"])["image_kind"] == "program_image"
    assert loads(events[0]["after_values"])["image_kind"] == "official_banner"


# --------------------------------------------------------------------------
# D. image_verified_at changes create an audit row
# --------------------------------------------------------------------------
def test_image_verified_at_change_creates_audit_row(session):
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_verified_at = VERIFIED_AT
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["changed_fields"] == "image_verified_at"


# --------------------------------------------------------------------------
# E. evaluation status changes create an audit row
# --------------------------------------------------------------------------
def test_image_evaluation_status_change_creates_audit_row(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_evaluation_status="pending")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_evaluation_status = "verified"
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["changed_fields"] == "image_evaluation_status"
    assert loads(events[0]["after_values"])["image_evaluation_status"] == "verified"


def test_image_evaluated_at_change_creates_audit_row(session):
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_evaluated_at = EVALUATED_AT
    session.commit()

    assert audit_rows(session)[0]["changed_fields"] == "image_evaluated_at"


@pytest.mark.parametrize("field,value", [
    ("image_source_url", "https://ethz.ch/"),
    ("image_source_type", "issuer_page"),
    ("image_alt_text", "Students on the ETH campus"),
])
def test_every_tracked_field_is_audited(session, field, value):
    """Every column the image pipeline writes must be under the trigger."""
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    setattr(session.get(Scholarship, row_id), field, value)
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1, f"{field} was not audited"
    assert events[0]["changed_fields"] == field


def test_all_eight_fields_are_tracked():
    """Guards against a field being dropped from the trigger by accident."""
    assert set(TRACKED_IMAGE_FIELDS) == {
        "image_url",
        "image_source_url",
        "image_source_type",
        "image_kind",
        "image_alt_text",
        "image_verified_at",
        "image_evaluation_status",
        "image_evaluated_at",
    }


# --------------------------------------------------------------------------
# F. multiple image fields changed in one transaction -> one coherent event
# --------------------------------------------------------------------------
def test_multiple_fields_in_one_transaction_create_one_event(session):
    row_id = make_row(session)
    row = session.get(Scholarship, row_id)
    row.image_url = IMAGE_URL
    row.image_kind = "program_image"
    row.image_verified_at = VERIFIED_AT
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1, "one transaction must be one event"
    fields = set(events[0]["changed_fields"].split(", "))
    assert fields == {"image_url", "image_kind", "image_verified_at"}
    # Before/after objects must be complete, not partial.
    assert set(loads(events[0]["after_values"])) == fields
    assert set(loads(events[0]["before_values"])) == fields


def test_full_clear_in_one_transaction_is_one_coherent_event(session):
    """The do_purge() shape: every image field cleared together."""
    row_id = make_row(session,
                      image_url=IMAGE_URL,
                      image_source_url="https://ethz.ch/",
                      image_source_type="issuer_page",
                      image_kind="program_image",
                      image_alt_text="campus",
                      image_verified_at=VERIFIED_AT,
                      image_evaluation_status="verified",
                      image_evaluated_at=EVALUATED_AT)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    row = session.get(Scholarship, row_id)
    for field in TRACKED_IMAGE_FIELDS:
        setattr(row, field, None)
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert set(events[0]["changed_fields"].split(", ")) == set(TRACKED_IMAGE_FIELDS)
    assert set(loads(events[0]["before_values"])) == set(TRACKED_IMAGE_FIELDS)
    assert all(v is None for v in loads(events[0]["after_values"]).values())


# --------------------------------------------------------------------------
# G. unrelated Scholarship changes create NO image audit
# --------------------------------------------------------------------------
def test_unrelated_field_change_creates_no_audit(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_kind="program_image")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    row = session.get(Scholarship, row_id)
    row.title = "Renamed programme"
    row.notes = "A note that has nothing to do with images"
    row.last_verified_date = datetime(2026, 3, 5).date()
    session.commit()

    assert audit_count(session) == 0, "an unrelated update was audited"


def test_audit_isolation_flag_change_creates_no_audit(session):
    """Archiving is a visibility change, not an image mutation."""
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).is_archived = True
    session.commit()

    assert audit_count(session) == 0


def test_touching_an_image_field_to_the_same_value_is_not_audited(session):
    """An update that names image columns but changes nothing is not an event."""
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.execute(
        text("UPDATE scholarships SET image_url = :url, image_kind = :kind WHERE id = :id"),
        {"url": IMAGE_URL, "kind": None, "id": row_id},
    )
    session.commit()

    assert audit_count(session) == 0


# --------------------------------------------------------------------------
# H. raw SQL image update is captured
# --------------------------------------------------------------------------
def test_raw_sql_update_is_captured(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_kind="program_image")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    # Exactly the shape a one-off script or psql session would use.
    session.execute(
        text("UPDATE scholarships SET image_url = NULL, image_kind = NULL WHERE id = :id"),
        {"id": row_id},
    )
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1, "a raw SQL image clear escaped the audit"
    assert set(events[0]["changed_fields"].split(", ")) == {"image_url", "image_kind"}


def test_raw_sql_bulk_update_is_captured_for_every_row(session):
    ids = [make_row(session, image_url=IMAGE_URL, image_kind="program_image")
           for _ in range(3)]
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.execute(
        text("UPDATE scholarships SET image_url = NULL WHERE image_kind = 'program_image'")
    )
    session.commit()

    events = audit_rows(session)
    assert len(events) == len(ids)
    assert {e["scholarship_id"] for e in events} == set(ids)


# --------------------------------------------------------------------------
# I. ORM image update is captured
# --------------------------------------------------------------------------
def test_orm_update_is_captured(session):
    row_id = make_row(session)
    row = session.get(Scholarship, row_id)
    row.image_url = IMAGE_URL
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["changed_fields"] == "image_url"


# --------------------------------------------------------------------------
# J. an unattributed mutation is still captured
# --------------------------------------------------------------------------
def test_unattributed_mutation_is_still_captured(session):
    """The whole point: no context must not mean no audit."""
    row_id = make_row(session)
    session.execute(
        text("UPDATE scholarships SET image_url = :url WHERE id = :id"),
        {"url": IMAGE_URL, "id": row_id},
    )
    session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["writer_context"] == UNATTRIBUTED


# --------------------------------------------------------------------------
# K. a supplied writer context is stored
# --------------------------------------------------------------------------
def test_supplied_writer_context_is_stored(session):
    row_id = make_row(session)
    with image_writer("maintenance.images", session):
        session.get(Scholarship, row_id).image_url = IMAGE_URL
        session.commit()

    assert audit_rows(session)[0]["writer_context"] == "maintenance.images"


@pytest.mark.parametrize("label", [
    "maintenance.images",
    "maintenance.logos",
    "maintenance.purge",
    "image_verifier",
    "image_coverage_runner",
    "admin_image_review",
    "audit_images",
    "logo_fallback",
    "resolve_generic_images",
    "verification",
    "backfill_alt_text",
])
def test_every_documented_writer_label_is_recorded(session, label):
    row_id = make_row(session)
    with image_writer(label, session):
        session.get(Scholarship, row_id).image_url = IMAGE_URL
        session.commit()

    assert audit_rows(session)[0]["writer_context"] == label


def test_writer_context_does_not_leak_to_later_transactions(session):
    """A pooled connection must not carry one writer's label forward."""
    first = make_row(session)
    second = make_row(session)

    with image_writer("maintenance.images", session):
        session.get(Scholarship, first).image_url = IMAGE_URL
        session.commit()

    session.get(Scholarship, second).image_url = IMAGE_URL
    session.commit()

    contexts = {e["scholarship_id"]: e["writer_context"] for e in audit_rows(session)}
    assert contexts[first] == "maintenance.images"
    assert contexts[second] == UNATTRIBUTED


def test_writer_context_is_sanitized():
    assert sanitize_writer_context("  maintenance.images  ") == "maintenance.images"
    assert sanitize_writer_context(None) == UNATTRIBUTED
    assert sanitize_writer_context("") == UNATTRIBUTED
    assert sanitize_writer_context("a" * 500).startswith("a")
    assert len(sanitize_writer_context("a" * 500)) == 120


# --------------------------------------------------------------------------
# L. before/after values are correct
# --------------------------------------------------------------------------
def test_before_and_after_values_are_correct(session):
    row_id = make_row(session, image_url="https://old.example/img.png", image_alt_text="old alt")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    row = session.get(Scholarship, row_id)
    row.image_url = IMAGE_URL
    row.image_alt_text = "new alt"
    session.commit()

    event = audit_rows(session)[0]
    before, after = loads(event["before_values"]), loads(event["after_values"])
    assert before["image_url"] == "https://old.example/img.png"
    assert after["image_url"] == IMAGE_URL
    assert before["image_alt_text"] == "old alt"
    assert after["image_alt_text"] == "new alt"


def test_audit_records_only_the_fields_that_changed(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_alt_text="keep me")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_kind = "official_logo"
    session.commit()

    event = audit_rows(session)[0]
    assert set(event["changed_fields"].split(", ")) == {"image_kind"}
    assert "image_alt_text" not in loads(event["before_values"])


def test_no_secret_bearing_columns_exist():
    """The audit must not be able to hold credentials."""
    import inspect

    from app.image_audit import audit_ddl_for

    ddl = " ".join(audit_ddl_for("postgresql"))
    for forbidden in ("password", "token", "secret", "api_key", "authorization"):
        assert forbidden not in ddl.lower(), f"{forbidden} appears in the audit DDL"
    assert inspect.isclass(Scholarship)


# --------------------------------------------------------------------------
# M. the audit record survives commit
# --------------------------------------------------------------------------
def test_audit_record_survives_commit(session):
    row_id = make_row(session)
    session.get(Scholarship, row_id).image_url = IMAGE_URL
    session.commit()

    session.expire_all()
    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["after_values"]
    assert events[0]["changed_at_utc"] is not None


def test_audit_is_readable_from_a_fresh_session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_image_audit_schema(connection)
    factory = sessionmaker(bind=engine)

    with factory() as s:
        row_id = make_row(s)
        s.get(Scholarship, row_id).image_url = IMAGE_URL
        s.commit()

    with factory() as s:
        events = list(s.execute(text(f"SELECT * FROM {AUDIT_TABLE}")).mappings())
        assert len(events) == 1
    engine.dispose()


# --------------------------------------------------------------------------
# N. rollback leaves nothing behind
# --------------------------------------------------------------------------
def test_rollback_leaves_no_audit_row(session):
    row_id = make_row(session)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    session.get(Scholarship, row_id).image_url = IMAGE_URL
    session.flush()
    assert audit_count(session) == 1, "the trigger fires inside the transaction"

    session.rollback()
    assert audit_count(session) == 0, "a rolled-back mutation stayed in the audit"
    session.refresh(session.get(Scholarship, row_id))
    assert session.get(Scholarship, row_id).image_url is None


# --------------------------------------------------------------------------
# O. identical assignment is not a false positive
# --------------------------------------------------------------------------
def test_repeated_identical_assignment_is_not_audited(session):
    row_id = make_row(session, image_url=IMAGE_URL, image_kind="program_image")
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    for _ in range(3):
        row = session.get(Scholarship, row_id)
        row.image_url = IMAGE_URL
        row.image_kind = "program_image"
        session.commit()

    assert audit_count(session) == 0, "an unchanged re-assignment produced audit noise"


def test_changing_back_and_forth_records_each_real_change(session):
    row_id = make_row(session, image_url=IMAGE_URL)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    row = session.get(Scholarship, row_id)
    row.image_url = None
    session.commit()
    row.image_url = IMAGE_URL
    session.commit()

    assert audit_count(session) == 2


# --------------------------------------------------------------------------
# P. the exact ID 14 transition
# --------------------------------------------------------------------------
def test_id14_shaped_program_image_transition_is_captured(session):
    """ID 14 was set to an ETHZ programme photograph with no history row.

    That exact mutation must now leave a record naming the writer.
    """
    row_id = make_row(session, image_kind=None, image_verified_at=None)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    with image_writer("image_verifier", session):
        row = session.get(Scholarship, row_id)
        row.image_url = IMAGE_URL
        row.image_kind = "program_image"
        row.image_verified_at = VERIFIED_AT
        session.commit()

    events = audit_rows(session)
    assert len(events) == 1
    assert events[0]["writer_context"] == "image_verifier"
    assert set(events[0]["changed_fields"].split(", ")) == {
        "image_url", "image_kind", "image_verified_at"
    }
    after = loads(events[0]["after_values"])
    assert after["image_url"] == IMAGE_URL
    assert after["image_kind"] == "program_image"


def test_id14_shaped_clear_is_captured(session):
    """And the reverse: a silent clear of an accepted programme image."""
    row_id = make_row(session,
                      image_url=IMAGE_URL,
                      image_source_url="https://ethz.ch/",
                      image_source_type="issuer_page",
                      image_kind="program_image",
                      image_alt_text="campus",
                      image_verified_at=VERIFIED_AT,
                      image_evaluation_status="verified",
                      image_evaluated_at=EVALUATED_AT)
    session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
    session.commit()

    with image_writer("maintenance.purge", session):
        row = session.get(Scholarship, row_id)
        for field in TRACKED_IMAGE_FIELDS:
            setattr(row, field, None)
        session.commit()

    event = audit_rows(session)[0]
    assert event["writer_context"] == "maintenance.purge"
    assert set(event["changed_fields"].split(", ")) == set(TRACKED_IMAGE_FIELDS)


# --------------------------------------------------------------------------
# Append-only enforcement
# --------------------------------------------------------------------------
def test_audit_row_cannot_be_updated(session):
    row_id = make_row(session)
    session.get(Scholarship, row_id).image_url = IMAGE_URL
    session.commit()

    with pytest.raises(Exception) as excinfo:
        session.execute(text(f"UPDATE {AUDIT_TABLE} SET writer_context = 'forged'"))
        session.commit()
    assert "append-only" in str(excinfo.value).lower()
    session.rollback()


def test_audit_row_cannot_be_deleted(session):
    row_id = make_row(session)
    session.get(Scholarship, row_id).image_url = IMAGE_URL
    session.commit()

    with pytest.raises(Exception) as excinfo:
        session.execute(text(f"DELETE FROM {AUDIT_TABLE}"))
        session.commit()
    assert "append-only" in str(excinfo.value).lower()
    session.rollback()
    assert audit_count(session) == 1


def test_audit_table_has_no_public_endpoint():
    """The audit must not be reachable from the API surface."""
    from pathlib import Path

    routers = Path(__file__).resolve().parents[1] / "app" / "routers"
    offenders = [
        f.name for f in routers.glob("*.py")
        if AUDIT_TABLE in f.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"{AUDIT_TABLE} is referenced in a router: {offenders}"


# --------------------------------------------------------------------------
# Migration safety and idempotency
# --------------------------------------------------------------------------
def test_schema_install_is_idempotent():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    for _ in range(3):
        with engine.begin() as connection:
            create_image_audit_schema(connection)
    assert audit_trigger_is_installed(engine)
    engine.dispose()


def test_existing_image_rows_are_untouched_by_installation():
    """Installing the audit must not alter any stored image state."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as s:
        row_id = make_row(s, image_url=IMAGE_URL, image_kind="program_image",
                          image_verified_at=VERIFIED_AT,
                          image_evaluation_status="verified")
        before = s.execute(
            text("SELECT image_url, image_kind, image_verified_at, image_evaluation_status "
                 "FROM scholarships WHERE id = :id"),
            {"id": row_id},
        ).mappings().one()
        # Drop the audit, reinstall, and confirm the data is identical.
        s.execute(text(f"DROP TRIGGER IF EXISTS trg_scholarships_image_audit"))
        s.execute(text(f"DROP TABLE IF EXISTS {AUDIT_TABLE}"))
        s.commit()

    with engine.begin() as connection:
        create_image_audit_schema(connection)

    with factory() as s:
        after = s.execute(
            text("SELECT image_url, image_kind, image_verified_at, image_evaluation_status "
                 "FROM scholarships WHERE id = :id"),
            {"id": row_id},
        ).mappings().one()
        assert dict(after) == dict(before)
        assert audit_count(s) == 0, "installation backfilled audit rows for existing data"
    engine.dispose()


def test_trigger_is_reinstalled_after_being_dropped():
    """Startup migration must repair a missing trigger, not assume it."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        create_image_audit_schema(connection)
    with engine.begin() as connection:
        connection.execute(text("DROP TRIGGER trg_scholarships_image_audit"))
    assert not audit_trigger_is_installed(engine)
    with engine.begin() as connection:
        create_image_audit_schema(connection)
    assert audit_trigger_is_installed(engine)
    engine.dispose()


# --------------------------------------------------------------------------
# PostgreSQL DDL structure (no server available in this environment)
# --------------------------------------------------------------------------
def test_postgresql_ddl_covers_every_tracked_field():
    ddl = "\n".join(postgresql_audit_ddl())
    for field in TRACKED_IMAGE_FIELDS:
        assert field in ddl, f"{field} is absent from the PostgreSQL trigger"
        assert f"{field} IS DISTINCT FROM NEW.{field}" in ddl


def test_postgresql_ddl_is_idempotent_and_guarded():
    statements = postgresql_audit_ddl()
    joined = "\n".join(statements)
    assert "CREATE TABLE IF NOT EXISTS" in joined
    assert "CREATE OR REPLACE FUNCTION" in joined
    assert "DROP TRIGGER IF EXISTS trg_scholarships_image_audit" in joined
    # The guard must reject both rewrite directions.
    assert "BEFORE UPDATE OR DELETE" in joined
    assert "append-only" in joined
    assert "restrict_violation" in joined


def test_postgresql_ddl_uses_null_safe_comparison():
    """A NULL->URL change is exactly the case a plain <>' misses."""
    ddl = "\n".join(postgresql_audit_ddl())
    assert "IS DISTINCT FROM" in ddl
    assert " IS NOT DISTINCT FROM " not in ddl


def test_postgresql_ddl_defaults_context_to_unknown():
    ddl = "\n".join(postgresql_audit_ddl())
    assert "current_setting('scholarzone.writer_context', true)" in ddl
    assert f"'{UNATTRIBUTED}'" in ddl


def test_postgresql_trigger_records_session_and_transaction_metadata():
    ddl = "\n".join(postgresql_audit_ddl())
    assert "application_name" in ddl
    assert "inet_client_addr()" in ddl
    assert "txid_current()" in ddl
    # Nothing that could carry a credential.
    for forbidden in ("password", "auth_header", "api_key", "secret"):
        assert forbidden not in ddl.lower()


def test_postgresql_ddl_has_no_bind_placeholders():
    """A driver placeholder inside a function body would be a syntax error."""
    for statement in postgresql_audit_ddl():
        assert "%s" not in statement, "bind placeholder found inside DDL"


def test_postgresql_record_function_uses_the_right_dialect():
    """An AFTER row trigger must RETURN NULL, which is PL/pgSQL only.

    A ``LANGUAGE sql`` function cannot contain ``RETURN NULL``, so the trigger
    would fail to create on the first production startup.
    """
    ddl = "\n".join(postgresql_audit_ddl())
    assert "LANGUAGE plpgsql" in ddl
    record = next(s for s in postgresql_audit_ddl()
                  if "scholarzone_record_image_mutation" in s)
    assert "RETURN NULL" in record
    assert "LANGUAGE sql" not in record


def test_postgresql_record_function_is_balanced():
    """Structural sanity: the body must open and close correctly."""
    record = next(s for s in postgresql_audit_ddl()
                  if "scholarzone_record_image_mutation" in s)
    assert record.count("$audit$") == 2, "dollar-quote delimiters are unbalanced"
    assert "DECLARE" in record
    assert record.rstrip().endswith("$audit$")
    assert record.count("IF OLD.") == len(TRACKED_IMAGE_FIELDS)
    assert record.count("END IF;") == len(TRACKED_IMAGE_FIELDS)


def test_postgresql_guard_raises_on_rewrite():
    guard = next(s for s in postgresql_audit_ddl()
                 if "scholarzone_image_mutation_guard" in s)
    assert "RAISE EXCEPTION" in guard
    assert "append-only" in guard


def test_postgresql_ddl_records_writer_context_column():
    """The context must be a first-class, bounded column on the audit table."""
    ddl = "\n".join(postgresql_audit_ddl())
    assert "writer_context VARCHAR(120) NOT NULL" in ddl