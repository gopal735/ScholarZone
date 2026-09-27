"""The runner must persist a terminal image outcome for every record it
examines, including the records where it found nothing.

Before this, `image_verified_at` was the only signal, so a rejected record was
indistinguishable from an unprocessed one and catalogue-wide image coverage
could not be proven.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_coverage_runner import (
    ImageCoverageRunner,
    PreflightResult,
)
from app.services.image_evaluation_status import ImageEvaluationStatus


@pytest.fixture()
def factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _make(factory, **kwargs) -> int:
    session = factory()
    try:
        row = Scholarship(
            title=kwargs.pop("title", "Test Scholarship"),
            country=kwargs.pop("country", "Germany"),
            degree=kwargs.pop("degree", "Master"),
            funding=kwargs.pop("funding", "Full"),
            official_source=kwargs.pop("official_source", "Org"),
            eligibility=[],
            benefits=[],
            coverage=[],
            requirements=[],
            documents=[],
            application_method=[],
            **kwargs,
        )
        session.add(row)
        session.commit()
        return row.id
    finally:
        session.close()


def _read(factory, sid):
    session = factory()
    try:
        return session.get(Scholarship, sid)
    finally:
        session.close()


class TestOutcomePersistence:
    def test_blocked_record_is_recorded_as_blocked_not_absent(self, factory):
        sid = _make(
            factory,
            official_source_url="https://blocked.example.org/scholarship",
            verification_status="active",
        )
        runner = ImageCoverageRunner(
            factory,
            dry_run=False,
            preflight_fn=lambda url: PreflightResult(False, 403, "blocked"),
        )
        runner.run()

        row = _read(factory, sid)
        assert row.image_evaluation_status == ImageEvaluationStatus.SOURCE_BLOCKED
        assert row.image_evaluated_at is not None
        assert row.image_verified_at is None

    def test_connection_failure_is_recorded(self, factory):
        sid = _make(
            factory,
            official_source_url="https://dead.example.org/x",
            verification_status="active",
        )
        runner = ImageCoverageRunner(
            factory,
            dry_run=False,
            preflight_fn=lambda url: PreflightResult(False, None, "connection_error"),
        )
        runner.run()

        assert _read(factory, sid).image_evaluation_status == (
            ImageEvaluationStatus.SOURCE_BLOCKED
        )

    def test_dry_run_never_writes(self, factory):
        sid = _make(
            factory,
            official_source_url="https://blocked.example.org/scholarship",
            verification_status="active",
        )
        runner = ImageCoverageRunner(
            factory,
            dry_run=True,
            preflight_fn=lambda url: PreflightResult(False, 403, "blocked"),
        )
        runner.run()

        row = _read(factory, sid)
        assert row.image_evaluation_status is None
        assert row.image_evaluated_at is None

    def test_existing_verified_image_is_never_downgraded(self, factory):
        """A later negative outcome must not erase a good, verified image."""
        from datetime import datetime, timezone

        verified = datetime.now(timezone.utc)
        sid = _make(
            factory,
            official_source_url="https://ok.example.org/x",
            verification_status="active",
            image_url="https://ok.example.org/logo.png",
            image_kind="official_logo",
            image_verified_at=verified,
            image_evaluation_status=ImageEvaluationStatus.VERIFIED,
        )
        runner = ImageCoverageRunner(factory, dry_run=False)
        # The guard is what protects a verified image from a later negative
        # result, so exercise it directly with the image still present.
        runner._record_evaluation(sid, ImageEvaluationStatus.SOURCE_BLOCKED)

        row = _read(factory, sid)
        assert row.image_evaluation_status == ImageEvaluationStatus.VERIFIED
        assert row.image_url == "https://ok.example.org/logo.png"
        assert row.image_verified_at is not None

    def test_negative_outcome_is_recorded_when_no_image_exists(self, factory):
        sid = _make(
            factory,
            official_source_url="https://ok.example.org/y",
            verification_status="active",
        )
        runner = ImageCoverageRunner(factory, dry_run=False)
        runner._record_evaluation(sid, ImageEvaluationStatus.NO_OFFICIAL_IMAGE)
        assert _read(factory, sid).image_evaluation_status == (
            ImageEvaluationStatus.NO_OFFICIAL_IMAGE
        )


class TestScopeSelection:
    def test_terminally_evaluated_records_are_skipped(self, factory):
        done = _make(
            factory,
            official_source_url="https://done.example.org/x",
            verification_status="active",
            image_evaluation_status=ImageEvaluationStatus.NO_OFFICIAL_IMAGE,
        )
        todo = _make(
            factory,
            official_source_url="https://todo.example.org/x",
            verification_status="active",
        )
        probed: list[str] = []

        def preflight(url):
            probed.append(url)
            return PreflightResult(False, 403, "blocked")

        runner = ImageCoverageRunner(
            factory,
            dry_run=False,
            preflight_fn=preflight,
            skip_terminally_evaluated=True,
        )
        runner.run()

        assert any("todo.example.org" in u for u in probed)
        assert not any("done.example.org" in u for u in probed)

    def test_quarantined_records_are_out_of_scope(self, factory):
        _make(
            factory,
            official_source_url="https://q.example.org/x",
            verification_status="quarantined",
        )
        probed: list[str] = []
        runner = ImageCoverageRunner(
            factory,
            dry_run=False,
            preflight_fn=lambda url: (probed.append(url), PreflightResult(False, 403, "blocked"))[1],
            exclude_quarantined=True,
        )
        runner.run()
        assert probed == []
