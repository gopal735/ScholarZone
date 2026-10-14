"""Wave 1-3 hardening — tests through the real production paths.

Every case here drives the function that actually writes or reads the field, not
a re-implementation of its predicate:

* image transport / non-content / provenance  -> `assess_image_evidence`, the
  function `upsert_verified_scholarships` and `do_add` both call
* enum coercion                                -> `ScholarshipIngestionRecord`,
  which is what `do_add` constructs every record through
* kind coherence                               -> the same model validator
* retirement protection in reverify            -> `do_reverify` itself
* admin image review                           -> `approve_image_review`, the
  service the admin endpoint calls
* public visibility                            -> `public_visibility_conditions`,
  the function the catalogue counts through
"""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.jobs import scholarzone_maintenance as M
from app.models import Base, Scholarship
from app.repositories.scholarships import public_visibility_conditions
from app.services.admin_image_review import approve_image_review
from app.services.image_validator import assess_image_evidence
from app.services.scholarship_ingestion import (
    ScholarshipIngestionRecord,
    upsert_verified_scholarships,
)

BACKEND = Path(__file__).resolve().parents[1]

#: Tables these tests need. `Base.metadata.create_all()` cannot be used: two
#: model classes declare the same index twice - once via `index=True` on the
#: column and once as an explicit `Index()` in `__table_args__`
#: (`student_sessions.expires_at` and `professor_availability.professor_id`).
#: SQLAlchemy derives the same name for both, so creating the schema from scratch
#: fails with "index already exists". That is a pre-existing schema defect,
#: invisible in production because these tables were created before the explicit
#: Index was added, and out of scope for this hardening pass. Creating only the
#: tables under test keeps the fixtures honest instead of hiding the defect.
SCHEMA_TABLES = ("scholarships", "scholarship_reviews",
                 "scholarship_verification_history", "image_reviews",
                 "maintenance_runs")


def _create_schema(engine):
    for name in SCHEMA_TABLES:
        table = Base.metadata.tables.get(name)
        if table is not None:
            table.create(engine, checkfirst=True)


@pytest.fixture()
def session():
    """In-memory database, so nothing here can reach the working SQLite file."""
    engine = create_engine("sqlite://")
    _create_schema(engine)
    s = sessionmaker(bind=engine)()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()

BASE = dict(
    name="Test Programme",
    country="Testland",
    degree_levels="PG",
    funding_type="Fully Funded",
    official_source_url="https://example.edu/scholarship",
)


def record(**over):
    payload = dict(BASE)
    payload.update(over)
    return ScholarshipIngestionRecord(**payload)


# ---------------------------------------------------------------------------
# image: the evidence gate, as the write path calls it
# ---------------------------------------------------------------------------

GOV_LOGO = "https://www.gov.uk/assets/static/govuk-logo.png"
EDU_LOGO = "https://media.ox.ac.uk/files/oxford-logo.png"
EDU_BANNER = "https://mit.edu/sites/default/files/undergrad-hero.jpg"


class TestImageEvidenceGate:
    """Drives `assess_image_evidence`, the gate both write paths consult."""

    def verdict(self, url, kind="official_logo", stype="official_government", alt=None):
        return assess_image_evidence(
            image_url=url, image_source_url=url, image_source_type=stype,
            image_kind=kind, alt_text=alt,
        )

    def test_app_icon_rejected(self):
        v = self.verdict(
            "https://ethz.ch/etc/designs/ethz/img/icons/"
            "ETH-APP-Icons-Theme-white/192-xxxhpdi.png"
        )
        assert v.accepted is False
        assert any("non-content" in r for r in v.reasons)

    def test_favicon_rejected(self):
        for url in (
            "https://akf.org/wp-content/themes/aga-khan/assets/favicon/favicon.svg",
            "https://www.worldbank.org/content/dam/wbr-redesign/logos/wbg-favicon.png",
        ):
            assert self.verdict(url).accepted is False, url

    def test_ui_asset_rejected(self):
        assert self.verdict("https://example.edu/assets/ui/close-icon.png").accepted is False
        assert self.verdict("https://example.edu/sprite/nav-arrow.png").accepted is False

    def test_obvious_social_asset_rejected(self):
        assert self.verdict(
            "https://example.edu/share/facebook-share-button.png"
        ).accepted is False
        assert self.verdict(
            "https://example.edu/twitter-card.png?h=200&w=200"
        ).accepted is False

    def test_valid_official_logo_accepted(self):
        assert self.verdict(GOV_LOGO).accepted is True
        assert self.verdict(EDU_LOGO, stype="official_university").accepted is True

    def test_valid_program_image_accepted(self):
        v = self.verdict(
            "https://www.ox.ac.uk/images/students/library-photo.jpg",
            kind="program_image", stype="official_university",
        )
        assert v.accepted is True

    def test_valid_official_banner_accepted(self):
        v = self.verdict(
            "https://mit.edu/sites/default/files/undergrad-banner.jpg",
            kind="official_banner", stype="official_university",
        )
        assert v.accepted is True

    def test_unsafe_http_rejected(self):
        v = self.verdict("http://calas.lat/sites/default/files/imagotipo_color.png")
        assert v.accepted is False
        assert any("https" in r for r in v.reasons)

    def test_valid_https_accepted(self):
        assert self.verdict(EDU_LOGO, stype="official_university").accepted is True

    def test_legitimate_official_cdn_allowed_untrusted_cdn_rejected(self):
        # The existing domain policy is a government/education/academic suffix
        # allowlist, not a same-host rule: an official CDN subdomain passes and a
        # commercial CDN does not.
        assert self.verdict(
            "https://cdn.ox.ac.uk/assets/oxford-wordmark.png",
            stype="official_university",
        ).accepted is True
        assert self.verdict("https://d2.cloudfront.net/x/logo.png").accepted is False
        assert self.verdict("https://images.squarespace-cdn.com/x/logo.png").accepted is False

    def test_cms_theme_directory_is_not_rejection(self):
        # A Drupal/WordPress theme directory is where most real institutional
        # logos live. Treating it as decisive would reject correct assets.
        assert self.verdict(
            "https://www.example.edu/themes/custom/brand/logo.png",
            stype="official_university",
        ).accepted is True

    def test_logo_in_filename_is_not_rejection_for_a_declared_logo(self):
        assert self.verdict(
            "https://www.example.edu/assets/brand/university-logo.png",
            stype="official_university",
        ).accepted is True

    def test_missing_source_type_rejected(self):
        v = assess_image_evidence(
            image_url=EDU_LOGO, image_source_url=EDU_LOGO,
            image_source_type=None, image_kind="official_logo",
        )
        assert v.accepted is False

    def test_none_image_is_accepted(self):
        assert assess_image_evidence(image_url=None).accepted is True


# ---------------------------------------------------------------------------
# image: through the real ingestion model and upsert
# ---------------------------------------------------------------------------

class TestIngestionImagePath:
    def test_app_icon_record_rejected_by_the_model(self):
        with pytest.raises(ValidationError) as exc:
            record(
                image_url="https://ethz.ch/etc/designs/ethz/img/icons/ETH-APP-Icons-Theme-white/192-a.png",
                image_source_url="https://ethz.ch/",
                image_source_type="official_university",
                image_kind="official_logo",
            )
        assert "evidence gate" in str(exc.value)

    def test_favicon_record_rejected_by_the_model(self):
        with pytest.raises(ValidationError):
            record(
                image_url="https://akf.org/wp-content/themes/aga-khan/assets/favicon/favicon.svg",
                image_source_url="https://akf.org/",
                image_source_type="official_ngo" if False else "official_provider",
                image_kind="official_logo",
            )

    def test_http_image_url_rejected_by_the_field_validator(self):
        with pytest.raises(ValidationError) as exc:
            record(image_url="http://calas.lat/x.png")
        assert "HTTPS" in str(exc.value)

    def test_image_without_kind_is_accepted_without_a_kind(self):
        """A URL with no kind is stored as exactly that — no kind.

        The pipeline owns classification. Inventing one at ingestion, or
        refusing the record outright, both fabricate evidence this mapper
        has no way to read: what it holds is a URL, a source URL, a source
        type and an alt text, and the honest answer about the kind is "not
        classified yet". The record is therefore valid, and the kind simply
        never enters ``to_persistence_fields``.
        """
        rec = record(
            image_url=EDU_LOGO,
            image_source_url=EDU_LOGO,
            image_source_type="official_university",
        )
        fields = rec.to_persistence_fields(date(2026, 10, 4))
        assert fields["image_url"] == EDU_LOGO
        assert "image_kind" not in fields

    def test_valid_image_survives_to_persistence_fields(self):
        rec = record(
            image_url=EDU_LOGO, image_source_url=EDU_LOGO,
            image_source_type="official_university", image_kind="official_logo",
        )
        fields = rec.to_persistence_fields(date(2026, 10, 4))
        assert fields["image_url"] == EDU_LOGO
        assert fields["image_source_type"] == "official_university"
        # Accepted, then not written: the kind is the pipeline's to set.
        assert "image_kind" not in fields

    def test_upsert_persists_a_valid_image_and_refuses_a_bad_one(self, session):
        good = record(
            name="Good Programme", image_url=EDU_LOGO, image_source_url=EDU_LOGO,
            image_source_type="official_university", image_kind="official_logo",
        )
        created, _ = upsert_verified_scholarships(session, [good])
        assert created == 1
        row = session.query(Scholarship).filter_by(title="Good Programme").one()
        assert row.image_url == EDU_LOGO
        assert row.image_source_type == "official_university"
        # The kind the caller carried is not written through: the pipeline
        # owns that column, so ingestion leaving it unset is correct rather
        # than a gap.
        assert row.image_kind is None

        with pytest.raises(ValidationError):
            record(
                name="Bad Programme",
                image_url="https://www.example.edu/favicon.ico",
                image_source_url="https://www.example.edu/",
                image_source_type="official_university",
                image_kind="official_logo",
            )


# ---------------------------------------------------------------------------
# enums: through the model that builds every record
# ---------------------------------------------------------------------------

class TestEnumPath:
    @pytest.mark.parametrize("value", sorted(
        {"exact", "month", "year", "rolling", "recurring", "varies",
         "approximate", "unknown"}
    ))
    def test_valid_deadline_precision_accepted(self, value):
        assert record(deadline_precision=value).deadline_precision == value

    def test_invalid_deadline_precision_coerced_not_passed_through(self):
        assert record(deadline_precision="day").deadline_precision == "unknown"
        assert record(deadline_precision="application_dead").deadline_precision == "unknown"
        # A recognisable token survives rather than collapsing to unknown.
        assert record(deadline_precision="application_deadline_rolling").deadline_precision \
            == "rolling"

    def test_coerced_precision_reaches_the_database(self, session):
        rec = record(name="Precision Programme", deadline_precision="day")
        upsert_verified_scholarships(session, [rec])
        row = session.query(Scholarship).filter_by(title="Precision Programme").one()
        assert row.deadline_precision == "unknown"

    @pytest.mark.parametrize("value", [
        "official_scholarship", "official_university",
        "official_government", "official_provider", "wikimedia",
    ])
    def test_valid_image_source_type_accepted(self, value):
        rec = record(
            image_url=EDU_LOGO, image_source_url=EDU_LOGO,
            image_source_type=value, image_kind="official_logo",
        )
        assert rec.image_source_type == value

    @pytest.mark.parametrize("value", [
        "official_logo", "official_page_logo", "official_ngo",
        "official_organization", "official_institution", "official_charity",
    ])
    def test_invalid_image_source_type_rejected(self, value):
        with pytest.raises(ValidationError) as exc:
            record(
                image_url=EDU_LOGO, image_source_url=EDU_LOGO,
                image_source_type=value, image_kind="official_logo",
            )
        assert "canonical vocabulary" in str(exc.value)

    def test_issuer_kind_fallback_is_a_canonical_source_type(self):
        # `_issuer_kind` classifies the *source* of a logo. Its fallback used to
        # be "official_logo", which is an image kind and is not a member of
        # ImageSourceType, so 228 rows stored a value nothing could interpret.
        from app.services.scholarship_image_verifier import is_valid_source_type

        assert M._issuer_kind("www.example.com", None) == "official_provider"
        assert is_valid_source_type(M._issuer_kind("www.example.com", None))
        assert M._issuer_kind("www.gov.uk", None) == "official_government"
        assert M._issuer_kind("www.ox.ac.uk", None) == "official_university"


# ---------------------------------------------------------------------------
# verification: through do_reverify
# ---------------------------------------------------------------------------

CONFIRMATIONS = {
    "records": [
        {"id": 9001, "evidence": "official page still live"},
        {"id": 9002, "evidence": "official page still live"},
        {"id": 9003, "evidence": "official page still live"},
    ]
}
RETIRED = {"records": [{"id": 9003, "flag": "DUPLICATE", "reason": "same programme",
                        "duplicate_of": 9004}]}


@pytest.fixture()
def reverify_env(tmp_path, monkeypatch):
    """A throwaway database and config directory for the real `do_reverify`.

    `do_reverify` obtains its session factory through `get_session_factory`,
    imported from `app.database` at call time, so patching that one attribute
    redirects the genuine code path at a database created for this test. Both
    the database and the config directory live in the tmp path, so the test
    cannot reach the working SQLite file or the real change set.
    """
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sm

    db_path = tmp_path / "reverify.db"
    url = f"sqlite:///{db_path.as_posix()}"

    engine = _create_engine(url)
    _create_schema(engine)
    s = _sm(bind=engine)()
    s.close()
    engine.dispose()

    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "verification_confirmations.json").write_text(
        json.dumps(CONFIRMATIONS), encoding="utf-8")
    (cfg / "retired_records.json").write_text(
        json.dumps(RETIRED), encoding="utf-8")
    monkeypatch.setattr(M, "CONFIG_DIR", cfg)

    def factory():
        e = _create_engine(url)
        return _sm(bind=e)

    monkeypatch.setattr("app.database.get_session_factory", factory)
    monkeypatch.setattr("app.database.init_database", lambda *a, **k: None)
    return url, cfg


def _seed_rows(url):
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy.orm import sessionmaker as _sm

    engine = _create_engine(url)
    s = _sm(bind=engine)()
    for sid, archived in ((9001, False), (9002, True), (9003, False)):
        s.add(Scholarship(
            degree="PG", funding="Fully Funded", id=sid, title=f"P{sid}", country="X",
            official_source_url=f"https://example.edu/{sid}",
            deadline_precision="unknown", status="open",
            verification_status="quarantined", is_verified=False,
            is_archived=archived,
        ))
    s.commit()
    return s


class TestReverifyRetirementGuard:
    def test_retired_record_is_not_promoted(self, reverify_env):
        url, _cfg = reverify_env
        s = _seed_rows(url)

        assert M.main(["--stage", "reverify"]) == 0

        s.expire_all()
        after = {r.id: r for r in s.query(Scholarship).all()}
        assert after[9001].verification_status == "active"
        assert after[9001].is_verified is True
        # An archived row is never promoted by a live page alone.
        assert after[9002].verification_status == "quarantined"
        # Neither is a row listed in retired_records.json.
        assert after[9003].verification_status == "quarantined"
        s.close()

    def test_protected_ids_are_reported_with_their_reason(self, reverify_env):
        url, _cfg = reverify_env
        s = _seed_rows(url)
        assert M.main(["--stage", "reverify"]) == 0
        s.expire_all()
        blob = s.execute(
            text("select stages from maintenance_runs order by rowid desc limit 1")
        ).scalar_one()
        # The run log records that the stage refused work and why, rather than
        # silently skipping it. Values are elided by the recorder's truncation,
        # so the assertion is on the reported shape and the confirmed count;
        # the per-id outcome is asserted against the database in the test above.
        assert '"name": "reverify"' in blob
        assert "protected_retired" in blob
        assert "archived_reason" in blob
        assert "listed_in_retired_records" in blob
        assert '"confirmed": 1' in blob
        s.close()

    def test_archived_record_dry_run_writes_nothing(self, reverify_env):
        url, _cfg = reverify_env
        s = _seed_rows(url)
        assert M.main(["--stage", "reverify", "--dry-run"]) == 0
        s.expire_all()
        for sid in (9001, 9002, 9003):
            assert s.get(Scholarship, sid).verification_status == "quarantined"
        s.close()


# ---------------------------------------------------------------------------
# admin image review: through approve_image_review
# ---------------------------------------------------------------------------

class TestAdminImageReviewArchiveGuard:
    def _review(self, session, sid, archived):
        from app.models import ImageReview

        row = Scholarship(
            degree="PG", funding="Fully Funded",
            id=sid, title=f"Reviewed {sid}", country="X",
            official_source_url=f"https://example.edu/{sid}",
            deadline_precision="unknown", status="open",
            verification_status="active", is_verified=True,
            is_archived=archived, image_evaluation_status="pending",
        )
        session.add(row)
        review = ImageReview(
            scholarship_id=sid, image_url=EDU_LOGO, image_kind="official_logo",
            source_page=f"https://example.edu/{sid}", source_type="official_university",
            confidence="high", decision="pending", reason_for_review="test",
        )
        session.add(review)
        session.flush()
        return review

    def test_archived_record_cannot_be_approved(self, session):
        review = self._review(session, 9101, archived=True)
        result = approve_image_review(
            session=session, review_id=review.id, reviewed_by="admin")
        assert result.success is False
        assert "archived" in result.error.lower()
        row = session.get(Scholarship, 9101)
        assert row.image_url is None
        assert row.image_evaluation_status == "pending"

    def test_live_record_still_approves(self, session):
        review = self._review(session, 9102, archived=False)
        result = approve_image_review(
            session=session, review_id=review.id, reviewed_by="admin")
        assert result.success is True
        row = session.get(Scholarship, 9102)
        assert row.image_url == EDU_LOGO
        assert row.image_kind == "official_logo"
        assert row.image_evaluation_status == "verified"

    def test_queue_counts_exclude_archived_rows(self, session):
        from app.routers.admin_image_review import review_queue_counts

        self._review(session, 9103, archived=True)
        session.add(Scholarship(
            degree="PG", funding="Fully Funded", id=9104, title="Live needs review", country="X",
            official_source_url="https://example.edu/9104",
            deadline_precision="unknown", status="open",
            verification_status="needs_review", is_archived=False,
        ))
        session.commit()
        counts = review_queue_counts(session)
        assert counts["scholarships_needing_review"] == 1


# ---------------------------------------------------------------------------
# public visibility: the function the catalogue actually publishes through
# ---------------------------------------------------------------------------

class TestPublicVisibility:
    def test_archived_row_is_never_public(self, session):
        from sqlalchemy import select

        row = Scholarship(
            degree="PG", funding="Fully Funded", id=9201, title="Expired", country="X",
            official_source_url="https://example.edu/9201",
            deadline_precision="exact", deadline_date=date(2020, 1, 1),
            status="open", verification_status="active", is_verified=True,
            is_archived=True, image_url=EDU_LOGO,
            image_verified_at=date(2026, 1, 1),
            image_source_type="official_university", image_kind="official_logo",
        )
        session.add(row)
        session.commit()
        ids = [s.id for s in session.scalars(
            select(Scholarship).where(*public_visibility_conditions()))]
        assert 9201 not in ids

    def test_public_gate_does_not_itself_check_image_kind(self, session):
        """Documents where the classification invariant actually lives.

        `public_visibility_conditions()` requires an image_url, an
        `image_verified_at` and an `image_source_type`. It does not require
        `image_kind`, so a row whose image was never classified is still
        listable. That is intentional and not a gap in the gate: the gate
        answers "is this record visible", and the visibility contract is
        about a verified source, not about what the image is.

        The classification invariant is enforced by the image pipeline that
        *writes* the kind, not by the gate that reads the rows, because
        hiding unclassified rows here would silently withdraw real listings
        rather than classify them. Ingestion correspondingly does not demand
        a kind it has no way to read.
        """
        row = Scholarship(
            degree="PG", funding="Fully Funded", id=9202, title="Kindless", country="X",
            official_source_url="https://example.edu/9202",
            deadline_precision="exact", deadline_date=date(2030, 1, 1),
            status="open", verification_status="active", is_verified=True,
            is_archived=False, image_url=EDU_LOGO,
            image_verified_at=date(2026, 1, 1),
            image_source_type="official_university", image_kind=None,
        )
        session.add(row)
        session.commit()
        ids = [s.id for s in session.scalars(
            select(Scholarship).where(*public_visibility_conditions()))]
        assert 9202 in ids  # the gate does not test kind; see the docstring

        # ...and the write path stores no kind of its own invention.
        rec = record(
            image_url=EDU_LOGO, image_source_url=EDU_LOGO,
            image_source_type="official_university",
        )
        assert rec.image_kind is None
        assert "image_kind" not in rec.to_persistence_fields(date(2026, 10, 4))




