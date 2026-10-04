"""Regression tests: ingestion must not silently delete a stored image.

Proven production defect
------------------------
``scholarship_image_audit`` recorded a single transaction (txn 281792,
2026-10-04 08:39:23.519402, ``writer_context='maintenance.add'``) blanking the
image fields of four scholarships: 130, 557, 564 and 569. The audit
``changed_fields`` were exactly::

    image_url, image_source_url, image_source_type, image_alt_text, image_verified_at

which is exactly - five fields, five of five - the set of image fields mapped by
``ScholarshipIngestionRecord.to_persistence_fields``. ``image_kind`` was absent
because the mapper does not map it, which is how ID 130 was left holding
``image_kind='official_logo'`` with a null ``image_url``.

The mechanism is not speculative. ``do_add`` copies every key of each
worklist entry into the ingestion model::

    flat = {k: v for k, v in entry.items() if k != "detail"}
    record = ScholarshipIngestionRecord(**flat)

``backend/config/new_scholarships.json`` contains entries whose five image keys
are present and explicitly ``null``. Pydantic records explicitly supplied keys
in ``model_fields_set`` even when the value is ``None``, the mapper therefore
emits those keys, and the upsert's dynamic ``setattr`` loop writes ``None`` over
a stored image.

Why "preserve" is the correct semantic
--------------------------------------
Ingestion is a create/enrich path. Every caller was audited and **none** uses it
to retract an image: the static catalogues omit the image keys or supply real
URLs, and canonical clearing lives in ``do_purge`` and ``do_logos``, neither of
which goes through ``upsert_verified_scholarships``. An explicit ``null``
therefore means "this record carries no image", not "retract the stored one".

These tests drive the real ``upsert_verified_scholarships`` against a real
database. Nothing here re-derives the rule.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Scholarship
from app.services.scholarship_ingestion import (
    ScholarshipIngestionRecord,
    upsert_verified_scholarships,
)
from app.services.image_discovery_orchestrator import (
    ACCEPTED_IMAGE_KINDS,
    LOGO_IDENTITY_KINDS,
)

IMAGE_FIELDS = (
    "image_url",
    "image_source_url",
    "image_source_type",
    "image_alt_text",
    "image_verified_at",
)

STORED_URL = "https://official.example.edu/assets/stored-logo.png"
STORED_SOURCE = "https://official.example.edu/about"
NEW_URL = "https://official.example.edu/assets/replacement-logo.png"
NEW_SOURCE = "https://official.example.edu/about"


@pytest.fixture()
def session(tmp_path, monkeypatch) -> Session:
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'ing.db').as_posix()}")

    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def _stored_image(session: Session, *, url: str = STORED_URL, kind: str | None) -> Scholarship:
    """A row that already carries a trusted image, as the pipeline would leave it."""
    row = Scholarship(
        title="Stored Image Scholarship",
        country="Testland",
        degree="masters",
        funding="full",
        official_source_url="https://official.example.edu/scholarships/stored",
        is_archived=False,
        verification_status="active",
        image_url=url,
        image_source_url=STORED_SOURCE,
        image_source_type="official_page_logo",
        image_alt_text="Official logo",
        image_kind=kind,
        image_verified_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )
    session.add(row)
    session.commit()
    return row


def _ingestion_record(**overrides) -> ScholarshipIngestionRecord:
    """The identity fields do_add always supplies, plus whatever the caller adds."""
    base = {
        "name": "Stored Image Scholarship",
        "country": "Testland",
        "degree_levels": "masters",
        "funding_type": "full",
        "official_source_url": "https://official.example.edu/scholarships/stored",
    }
    base.update(overrides)
    return ScholarshipIngestionRecord(**base)


def _reload(session: Session, row_id: int) -> Scholarship:
    session.expire_all()
    return session.scalar(select(Scholarship).where(Scholarship.id == row_id))


class TestExplicitNullMustNotEraseStoredImage:
    """The exact production failure shape: all five image keys explicitly null."""

    @pytest.mark.parametrize("kind", sorted(LOGO_IDENTITY_KINDS | {"program_image", "official_banner"}))
    def test_all_five_image_fields_explicit_null_preserves_the_image(self, session, kind):
        row = _stored_image(session, kind=kind)
        row_id = row.id

        # Exactly what backend/config/new_scholarships.json carries today.
        record = _ingestion_record(
            image_url=None,
            image_source_url=None,
            image_source_type=None,
            image_alt_text=None,
            image_verified_at=None,
        )
        assert set(record.model_fields_set) >= set(IMAGE_FIELDS), (
            "the record must really carry explicit nulls, or this test proves nothing"
        )

        created, updated = upsert_verified_scholarships(session, (record,))
        assert (created, updated) == (0, 1)

        after = _reload(session, row_id)
        assert after.image_url == STORED_URL
        assert after.image_source_url == STORED_SOURCE
        assert after.image_source_type == "official_page_logo"
        assert after.image_alt_text == "Official logo"
        assert after.image_verified_at is not None
        assert after.image_kind == kind

    def test_only_image_url_null_preserves_the_rest_of_the_pairing(self, session):
        row = _stored_image(session, kind="official_logo")
        row_id = row.id

        record = _ingestion_record(image_url=None)
        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.image_url == STORED_URL
        assert after.image_kind == "official_logo"


class TestAbsentImageFieldsChangeNothing:
    def test_ingestion_without_image_keys_leaves_the_image_alone(self, session):
        row = _stored_image(session, kind="official_logo")
        row_id = row.id

        record = _ingestion_record()
        assert not set(record.model_fields_set) & set(IMAGE_FIELDS)

        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.image_url == STORED_URL
        assert after.image_kind == "official_logo"


class TestAcceptedImagesSurviveOrdinaryIngestion:
    """87ad84c protection must not be undone from the ingestion side either."""

    @pytest.mark.parametrize("kind", ["program_image", "official_banner"])
    def test_accepted_non_identity_kind_is_not_erased(self, session, kind):
        assert kind in ACCEPTED_IMAGE_KINDS and kind not in LOGO_IDENTITY_KINDS
        row = _stored_image(session, kind=kind)
        row_id = row.id

        record = _ingestion_record(
            image_url=None, image_source_url=None, image_source_type=None,
            image_alt_text=None, image_verified_at=None,
        )
        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.image_url == STORED_URL
        assert after.image_kind == kind


class TestLegitimateReplacementStillWorks:
    def test_authoritative_replacement_is_applied(self, session):
        row = _stored_image(session, kind="official_logo")
        row_id = row.id

        record = _ingestion_record(
            image_url=NEW_URL,
            image_source_url=NEW_SOURCE,
            image_source_type="official_page_logo",
            image_alt_text="Replacement logo",
            image_verified_at=date(2026, 10, 1),
        )
        created, updated = upsert_verified_scholarships(session, (record,))
        assert (created, updated) == (0, 1)

        after = _reload(session, row_id)
        assert after.image_url == NEW_URL
        assert after.image_source_url == NEW_SOURCE
        assert after.image_alt_text == "Replacement logo"

    def test_replacement_on_a_row_with_no_image_still_works(self, session):
        row = Scholarship(
            title="Stored Image Scholarship",
            country="Testland",
            degree="masters",
            funding="full",
            official_source_url="https://official.example.edu/scholarships/stored",
        )
        session.add(row)
        session.commit()
        row_id = row.id

        record = _ingestion_record(
            image_url=NEW_URL,
            image_source_url=NEW_SOURCE,
            image_source_type="official_page_logo",
            image_alt_text="First logo",
            image_verified_at=date(2026, 10, 1),
        )
        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.image_url == NEW_URL
        assert after.image_verified_at is not None

    def test_non_image_fields_still_update_normally(self, session):
        row = _stored_image(session, kind="official_logo")
        row_id = row.id

        record = _ingestion_record(region="Europe", duration="12 months")
        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.region == "Europe"
        assert after.duration == "12 months"
        assert after.image_url == STORED_URL


class TestImageKindIsNeverInventedByIngestion:
    """The mapper must not guess a kind it has no producer semantics for."""

    def test_ingestion_does_not_write_image_kind(self, session):
        row = _stored_image(session, kind=None)
        row_id = row.id

        record = _ingestion_record(
            image_url=NEW_URL,
            image_source_url=NEW_SOURCE,
            image_source_type="official_page_logo",
            image_alt_text="New",
            image_verified_at=date(2026, 10, 1),
        )
        upsert_verified_scholarships(session, (record,))

        after = _reload(session, row_id)
        assert after.image_url == NEW_URL
        assert after.image_kind is None, (
            "ingestion must not fabricate a kind; that is the image pipeline's job"
        )

    def test_preserved_image_never_ends_up_url_without_kind(self, session):
        """The I6 shape must not be produced by an ingestion refresh."""
        row = _stored_image(session, kind="official_logo")
        row_id = row.id

        upsert_verified_scholarships(
            session, (_ingestion_record(image_url=None),)
        )

        after = _reload(session, row_id)
        assert not (after.image_url is not None and after.image_kind is None)


class TestCanonicalClearingIsUnaffected:
    """Ingestion cannot clear, so clearing stays with the policy that owns it."""

    def test_the_real_purge_stage_still_clears_a_non_accepted_image(self, session):
        """do_purge is untouched and must remain the clearing authority."""
        row = _stored_image(session, kind=None)
        row_id = row.id

        from app.jobs import scholarzone_maintenance as worker

        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK

        after = _reload(session, row_id)
        assert after.image_url is None, "the canonical purge stage must still clear"

    def test_the_real_purge_stage_still_preserves_an_accepted_image(self, session):
        row = _stored_image(session, kind="program_image")
        row_id = row.id

        from app.jobs import scholarzone_maintenance as worker

        assert worker.main(["--stage", "purge"]) == worker.EXIT_OK

        after = _reload(session, row_id)
        assert after.image_url == STORED_URL
        assert after.image_kind == "program_image"


class TestMapperContractDirectly:
    """Pin the mapper rule itself, through the real function."""

    def test_mapper_drops_explicit_null_image_fields(self):
        fields = _ingestion_record(
            image_url=None, image_source_url=None, image_source_type=None,
            image_alt_text=None, image_verified_at=None,
        ).to_persistence_fields(date(2026, 10, 1))
        assert not set(fields) & set(IMAGE_FIELDS)

    def test_mapper_keeps_real_image_values(self):
        fields = _ingestion_record(
            image_url=NEW_URL,
            image_source_url=NEW_SOURCE,
            image_source_type="official_page_logo",
            image_alt_text="New",
            image_verified_at=date(2026, 10, 1),
        ).to_persistence_fields(date(2026, 10, 1))
        assert fields["image_url"] == NEW_URL
        assert fields["image_alt_text"] == "New"

    def test_mapper_never_emits_image_kind(self):
        fields = _ingestion_record(
            image_url=NEW_URL,
            image_source_url=NEW_SOURCE,
            image_source_type="official_page_logo",
            image_alt_text="New",
            image_verified_at=date(2026, 10, 1),
        ).to_persistence_fields(date(2026, 10, 1))
        assert "image_kind" not in fields

    def test_explicit_null_non_image_field_is_still_honoured(self):
        """The guard is scoped to images; other fields keep their semantics."""
        fields = _ingestion_record(region=None).to_persistence_fields(date(2026, 10, 1))
        assert "region" in fields
        assert fields["region"] is None
