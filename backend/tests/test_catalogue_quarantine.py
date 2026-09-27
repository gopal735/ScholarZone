"""Tests for catalogue quarantine of non-scholarship records."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship, ScholarshipReview
from app.services.catalogue_quarantine import (
    QUARANTINE_STATUS,
    assess_record,
    quarantine_non_scholarships,
    quarantine_record,
)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _real(session_factory, **overrides) -> int:
    defaults = dict(
        title="ETH Zurich Excellence Scholarship",
        country="Switzerland",
        degree="Master's",
        funding="Fully Funded",
        official_source="ETH Zurich",
        official_source_url="https://ethz.ch/en/scholarships/excellence.html",
        description="A doctoral programme for outstanding students.",
        deadline_display="30 November annually",
        duration="12 months",
        eligibility=["Bachelor's degree"],
        benefits=["Full tuition"],
    )
    defaults.update(overrides)
    s = session_factory()
    try:
        row = Scholarship(**defaults)
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id
    finally:
        s.close()


def _not_a_scholarship(session_factory) -> int:
    s = session_factory()
    try:
        row = Scholarship(
            title="Welcome to GOV.UK",
            country="United Kingdom",
            degree="Unknown",
            funding="Unknown",
            official_source_url="https://gov.uk/",
            is_verified=True,
            verification_status="active",
            status="open",
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row.id
    finally:
        s.close()


class TestAssessment:
    def test_flags_landing_page_record(self, session_factory):
        sid = _not_a_scholarship(session_factory)
        s = session_factory()
        try:
            verdict = assess_record(s.get(Scholarship, sid))
            assert verdict.is_non_scholarship is True
            assert len(verdict.reasons) >= 3
        finally:
            s.close()

    def test_real_record_is_never_flagged(self, session_factory):
        sid = _real(session_factory)
        s = session_factory()
        try:
            assert assess_record(s.get(Scholarship, sid)).is_non_scholarship is False
        finally:
            s.close()

    def test_bare_root_alone_is_not_enough(self, session_factory):
        """One signal must never quarantine: sparse real records exist."""
        sid = _real(session_factory, official_source_url="https://www.daad.de")
        s = session_factory()
        try:
            verdict = assess_record(s.get(Scholarship, sid))
            assert verdict.is_non_scholarship is False
        finally:
            s.close()


class TestQuarantine:
    def test_dry_run_changes_nothing(self, session_factory):
        sid = _not_a_scholarship(session_factory)
        s = session_factory()
        try:
            quarantine_record(s, sid, dry_run=True)
            row = s.get(Scholarship, sid)
            assert row.verification_status == "active"
            assert row.status == "open"
            assert s.scalars(select(ScholarshipReview)).all() == []
        finally:
            s.close()

    def test_persist_quarantines_and_keeps_row(self, session_factory):
        sid = _not_a_scholarship(session_factory)
        s = session_factory()
        try:
            verdict = quarantine_record(s, sid, dry_run=False)
            assert verdict.is_non_scholarship
            row = s.get(Scholarship, sid)
            assert row is not None, "row must not be deleted"
            assert row.verification_status == QUARANTINE_STATUS
            assert row.status == "closed"
            assert row.is_verified is False
            assert "not a scholarship" in (row.verification_notes or "")
        finally:
            s.close()

    def test_writes_review_with_evidence(self, session_factory):
        sid = _not_a_scholarship(session_factory)
        s = session_factory()
        try:
            quarantine_record(s, sid, dry_run=False)
            reviews = s.scalars(
                select(ScholarshipReview).where(ScholarshipReview.scholarship_id == sid)
            ).all()
            assert len(reviews) == 1
            assert reviews[0].field_name == "__record__"
            assert reviews[0].decision == "quarantined"
            assert "gov.uk" in reviews[0].conflict_reason
        finally:
            s.close()

    def test_is_idempotent(self, session_factory):
        sid = _not_a_scholarship(session_factory)
        for _ in range(3):
            s = session_factory()
            try:
                quarantine_record(s, sid, dry_run=False)
            finally:
                s.close()
        s = session_factory()
        try:
            reviews = s.scalars(
                select(ScholarshipReview).where(ScholarshipReview.scholarship_id == sid)
            ).all()
            assert len(reviews) == 1, "repeated runs must not duplicate review rows"
        finally:
            s.close()

    def test_catalogue_scan_flags_only_the_bad_record(self, session_factory):
        _real(session_factory, title="Real One", official_source_url="https://a.example.org/p1")
        _real(session_factory, title="Real Two", official_source_url="https://b.example.org/p2")
        bad = _not_a_scholarship(session_factory)

        verdicts = quarantine_non_scholarships(session_factory, dry_run=False)
        assert [v.scholarship_id for v in verdicts] == [bad]

        s = session_factory()
        try:
            assert s.get(Scholarship, bad).verification_status == QUARANTINE_STATUS
            assert s.get(Scholarship, 1).verification_status != QUARANTINE_STATUS
        finally:
            s.close()

    def test_missing_record_is_handled(self, session_factory):
        s = session_factory()
        try:
            verdict = quarantine_record(s, 99999, dry_run=False)
            assert verdict.is_non_scholarship is False
        finally:
            s.close()
