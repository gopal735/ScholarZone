"""Tests for the image coverage runner: timeouts, isolation, resumability."""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.image_coverage_runner import ImageCoverageRunner
from app.services.image_discovery import ImageDiscoveryService
from app.services.official_page_discovery import (
    DEFAULT_TOTAL_BUDGET_SECONDS,
    OfficialPageDiscoveryService,
)


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _seed(session_factory, n: int, *, verified: bool = False, prefix: str = "p") -> list[int]:
    """Seed records. official_source_url is UNIQUE, so each call needs a prefix."""
    ids = []
    s = session_factory()
    try:
        for i in range(n):
            row = Scholarship(
                title=f"Scholarship {prefix}{i}",
                country="Germany",
                degree="Master",
                funding="Full",
                official_source="Org",
                official_source_url=f"https://www.daad.de/{prefix}-{i}",
                image_verified_at=datetime(2026, 1, 1) if verified else None,
            )
            s.add(row)
            s.commit()
            s.refresh(row)
            ids.append(row.id)
    finally:
        s.close()
    return ids


class TestDeadlineEnforcement:
    def test_total_budget_default_is_bounded(self):
        assert 0 < DEFAULT_TOTAL_BUDGET_SECONDS <= 120

    def test_discover_sets_deadline_on_shared_service(self):
        svc = OfficialPageDiscoveryService(total_budget_seconds=30.0)
        shared = ImageDiscoveryService(timeout=5.0)
        svc._discovery = shared
        got = svc._get_discovery()
        assert got is shared
        assert shared.deadline is not None
        assert shared.deadline > time.monotonic()

    def test_fetch_returns_immediately_when_deadline_passed(self):
        svc = ImageDiscoveryService(timeout=30.0, deadline=time.monotonic() - 1.0)
        started = time.monotonic()
        result = svc._fetch_page("https://www.example.org/")
        elapsed = time.monotonic() - started
        assert elapsed < 1.0, "expired deadline must not issue a request"
        assert result.error == "deadline_exceeded"
        assert result.content is None

    def test_retry_loop_also_respects_deadline(self):
        """A single URL must not consume (retries+1)*timeout past the budget."""
        svc = ImageDiscoveryService(timeout=0.2, max_retries=5, deadline=time.monotonic() + 0.05)
        started = time.monotonic()
        for _ in range(3):
            svc._fetch_page("https://www.example.org/")
        assert time.monotonic() - started < 1.0


class TestCoverageScope:
    def test_only_missing_scope_excludes_verified(self, session_factory):
        _seed(session_factory, 3, prefix="miss")
        _seed(session_factory, 2, verified=True, prefix="ver")
        runner = ImageCoverageRunner(session_factory, dry_run=True, only_missing=True)
        rows, total = runner._in_scope_ids(ids=None, start_after=None, limit=None)
        assert total == 3
        assert all(r[4] is None for r in rows)

    def test_all_scope_includes_everything(self, session_factory):
        _seed(session_factory, 2, prefix="a")
        _seed(session_factory, 1, verified=True, prefix="b")
        runner = ImageCoverageRunner(session_factory, dry_run=True, only_missing=False)
        _rows, total = runner._in_scope_ids(ids=None, start_after=None, limit=None)
        assert total == 3

    def test_resume_window_is_deterministic(self, session_factory):
        ids = _seed(session_factory, 5)
        ids.sort()
        runner = ImageCoverageRunner(session_factory, dry_run=True)
        first, total_a = runner._in_scope_ids(ids=None, start_after=None, limit=None)
        second, total_b = runner._in_scope_ids(ids=None, start_after=ids[1], limit=None)
        assert total_a == 5
        assert [r[0] for r in first] == ids
        assert [r[0] for r in second] == ids[2:]
        # Repeating the same resume point yields the same window.
        third, _ = runner._in_scope_ids(ids=None, start_after=ids[1], limit=None)
        assert [r[0] for r in third] == [r[0] for r in second]

    def test_explicit_empty_ids_yields_nothing(self, session_factory):
        _seed(session_factory, 3)
        runner = ImageCoverageRunner(session_factory, dry_run=True)
        rows, total = runner._in_scope_ids(ids=[], start_after=None, limit=None)
        assert rows == [] and total == 0

    def test_limit_caps_rows_but_reports_full_scope(self, session_factory):
        _seed(session_factory, 6)
        runner = ImageCoverageRunner(session_factory, dry_run=True)
        rows, total = runner._in_scope_ids(ids=None, start_after=None, limit=2)
        assert total == 6
        assert len(rows) == 2


class TestFailureIsolation:
    def test_one_crashing_record_does_not_abort_the_run(self, session_factory):
        _seed(session_factory, 4)

        class Boom(Exception):
            pass

        calls = {"n": 0}

        def fake_run(self, scholarship_id, scholarship_title, official_source_url,
                     official_source_name=None, session=None):
            calls["n"] += 1
            if scholarship_id == calls.get("bad"):
                raise Boom("kaboom")
            from app.services.image_discovery_orchestrator import (
                OrchestratorRunResult,
                TrustworthyImageStatus,
            )

            return OrchestratorRunResult(
                scholarship_id=scholarship_id,
                scholarship_title=scholarship_title or "",
                status=TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE,
            )

        ids = _seed  # placeholder to keep names clear
        runner = ImageCoverageRunner(session_factory, dry_run=True, max_workers=2)
        s = session_factory()
        try:
            all_ids = [r.id for r in s.query(Scholarship).all()]
            calls["bad"] = sorted(all_ids)[1]
        finally:
            s.close()

        with patch(
            "app.services.image_discovery_orchestrator.ImageDiscoveryOrchestrator.run",
            new=fake_run,
        ):
            metrics = runner.run()

        assert calls["n"] == 4, "every record must be attempted"
        assert metrics.failed == 1
        assert metrics.records_in_scope == 4

    def test_verified_records_are_excluded_from_scope(self, session_factory):
        """A record with a verified image is never re-discovered automatically."""
        _seed(session_factory, 1, verified=True, prefix="ver")
        runner = ImageCoverageRunner(session_factory, dry_run=True, only_missing=True)

        def never(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("verified record must not be re-discovered")

        with patch(
            "app.services.image_discovery_orchestrator.ImageDiscoveryOrchestrator.run",
            new=never,
        ):
            metrics = runner.run()

        assert metrics.records_in_scope == 0
        assert metrics.skipped_existing == 0
        assert metrics.outcomes == []

    def test_verified_record_is_counted_as_skipped_when_in_scope(self, session_factory):
        """With only_missing=False, verified records are counted, not refetched."""
        _seed(session_factory, 1, verified=True, prefix="ver")
        runner = ImageCoverageRunner(session_factory, dry_run=True, only_missing=False)

        def never(*a, **k):  # pragma: no cover - must not be called
            raise AssertionError("verified record must not be re-discovered")

        with patch(
            "app.services.image_discovery_orchestrator.ImageDiscoveryOrchestrator.run",
            new=never,
        ):
            metrics = runner.run()

        assert metrics.records_in_scope == 1
        assert metrics.skipped_existing == 1


class TestMetrics:
    def test_blocked_and_unreachable_are_separate_from_no_image(self, session_factory):
        _seed(session_factory, 3)
        from app.services.image_discovery_orchestrator import (
            OrchestratorRunResult,
            TrustworthyImageStatus,
        )

        # One outcome per record, in the order the runner will process them.
        plans = [
            (TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE, "no_official_source_url", False, 3),
            (TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE, None, True, 0),
            (TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE, None, False, 5),
        ]
        counter = {"i": 0}

        def fake(self, scholarship_id, scholarship_title, official_source_url,
                 official_source_name=None, session=None):
            status, page_error, timed_out, requests = plans[counter["i"] % len(plans)]
            counter["i"] += 1
            pd = type("PD", (), {"error": page_error, "timed_out": timed_out})()
            return OrchestratorRunResult(
                scholarship_id=scholarship_id,
                scholarship_title=scholarship_title or "",
                status=status,
                page_discovery=pd,
                requests_made=requests,
            )

        runner = ImageCoverageRunner(session_factory, dry_run=True, max_workers=1)
        with patch(
            "app.services.image_discovery_orchestrator.ImageDiscoveryOrchestrator.run",
            new=fake,
        ):
            metrics = runner.run()

        assert metrics.source_unreachable == 1
        assert metrics.source_blocked == 1
        assert metrics.no_official_image == 1

    def test_worker_count_is_capped(self, session_factory):
        runner = ImageCoverageRunner(session_factory, dry_run=True, max_workers=999)
        assert runner.max_workers <= 12
        runner2 = ImageCoverageRunner(session_factory, dry_run=True, max_workers=0)
        assert runner2.max_workers >= 1
