"""Tests for the quarantine latency fix and the public quality gate.

Two behaviours are being locked in here.

First, a record inserted by discovery is assessed for quarantine *in the same
run*. Before this, a freshly created record had the highest id in the
catalogue while the quarantine cursor sat somewhere in the middle, so junk sat
in the public directory for roughly 49 runs. That is how "Home - Erasmus+" and
"Ministry of Education (MOE)" reached production.

Second, the public directory gate. A record is listed only if it is verified and
carries an image that passed validation. The gate is a real product trade-off,
so these tests assert both what it hides and that it can be switched off - a
gate nobody can reverse is a bad gate.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'q.db').as_posix()}")
    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


def _add(factory, sid, *, url, title="Programme", junk=False, **kw):
    """Seed one record. `junk=True` builds a structurally invalid landing page."""
    from app.models import Scholarship

    session = factory()
    try:
        s = Scholarship(
            id=sid,
            title="Home - Erasmus+" if junk else title,
            country=kw.get("country", "Testland"),
            degree="unknown" if junk else kw.get("degree", "Master"),
            funding="n/a" if junk else kw.get("funding", "Fully Funded"),
            # A non-junk record names an awarding body. "No provider" is a
            # quarantine signal now, added after a live discovery round
            # published two records with official_source=None, and without it
            # this fixture is indistinguishable from those two.
            official_source=None if junk else kw.get("official_source", "Example University"),
            official_source_url=url,
            is_verified=kw.get("is_verified", False),
            image_url=kw.get("image_url"),
            image_verified_at=kw.get("image_verified_at"),
            verification_status=kw.get("verification_status", "active"),
        )
        session.add(s)
        session.commit()
        return sid
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 1. Quarantine latency
# ---------------------------------------------------------------------------


class TestImmediateQuarantine:
    def test_a_freshly_inserted_landing_page_is_caught_immediately(self, factory):
        """The whole point: no waiting for a cursor to wrap around."""
        from datetime import date, timedelta

        from app.jobs.scholarzone_maintenance import _quarantine_ids

        sid = _add(factory, 1, url="https://erasmus-plus.ec.europa.eu/", junk=True)
        assert _quarantine_ids(factory, [sid], dry_run=False) == 1

        from app.models import Scholarship

        session = factory()
        try:
            record = session.get(Scholarship, sid)
            assert record.verification_status == "quarantined"
            assert record.status == "closed"
        finally:
            session.close()

    def test_a_genuine_record_is_not_caught(self, factory):
        from app.jobs.scholarzone_maintenance import _quarantine_ids

        sid = _add(
            factory, 1, url="https://www.kth.se/programmes/xyz", title="KTH Scholarship"
        )
        assert _quarantine_ids(factory, [sid], dry_run=False) == 0

    def test_dry_run_changes_nothing(self, factory):
        from app.jobs.scholarzone_maintenance import _quarantine_ids
        from app.models import Scholarship

        sid = _add(factory, 1, url="https://erasmus-plus.ec.europa.eu/", junk=True)
        assert _quarantine_ids(factory, [sid], dry_run=True) == 1
        session = factory()
        try:
            assert session.get(Scholarship, sid).verification_status != "quarantined"
        finally:
            session.close()

    def test_a_whole_batch_is_assessed_in_one_call(self, factory):
        from app.jobs.scholarzone_maintenance import _quarantine_ids
        from app.models import Scholarship

        ids = [
            _add(factory, 1, url="https://a.example.org/", junk=True),
            _add(factory, 2, url="https://b.example.org/p/2", title="Real Programme"),
            _add(factory, 3, url="https://c.example.org/", junk=True),
        ]
        assert _quarantine_ids(factory, ids, dry_run=False) == 2
        session = factory()
        try:
            assert session.get(Scholarship, 1).verification_status == "quarantined"
            assert session.get(Scholarship, 2).verification_status != "quarantined"
            assert session.get(Scholarship, 3).verification_status == "quarantined"
        finally:
            session.close()

    def test_repeated_assessment_is_idempotent(self, factory):
        from app.jobs.scholarzone_maintenance import _quarantine_ids
        from app.models import ScholarshipReview

        sid = _add(factory, 1, url="https://erasmus-plus.ec.europa.eu/", junk=True)
        for _ in range(3):
            _quarantine_ids(factory, [sid], dry_run=False)

        session = factory()
        try:
            assert (
                session.query(ScholarshipReview)
                .filter_by(scholarship_id=sid, field_name="__record__")
                .count()
                == 1
            )
        finally:
            session.close()


class TestDiscoverySurfacesInsertedIds:
    def test_the_scheduler_reports_inserted_ids(self):
        """Without the ids the immediate check cannot exist."""
        from app.scheduler_v2 import DiscoveryRoundResult

        result = DiscoveryRoundResult(
            countries_scanned=1, inserted_scholarships=1, duplicates=0,
            rejected_candidates=0, errors=0, image_discoveries_triggered=1,
            runtime_ms=1.0, inserted_ids=[42],
        )
        assert result.as_dict()["inserted_ids"] == [42]
        assert result.as_dict()["inserted_scholarships"] == 1

    def test_discovery_metrics_carry_ids(self):
        from app.services.discovery_scheduler import DiscoverySchedulerMetrics

        assert DiscoverySchedulerMetrics().inserted_ids == []

    def test_the_worker_assesses_discovery_output(self):
        from pathlib import Path

        from app.jobs import scholarzone_maintenance as worker

        source = Path(worker.__file__).read_text(encoding="utf-8")
        assert "inserted_ids" in source
        assert "_quarantine_ids" in source
        # The immediate check must run inside discovery, not only in the sweep.
        discover = source.split("def do_discover")[1].split("def do_quarantine")[0]
        assert "_quarantine_ids" in discover

    def test_no_cursor_advance_for_the_immediate_check(self):
        """Immediate assessment must not disturb the durable sweep position."""
        from pathlib import Path

        from app.jobs import scholarzone_maintenance as worker

        source = Path(worker.__file__).read_text(encoding="utf-8")
        helper = source.split("def _quarantine_ids")[1].split("class FatalError")[0]
        assert "store.advance" not in helper
        assert "select_batch" not in helper


# ---------------------------------------------------------------------------
# 2. Public quality gate
# ---------------------------------------------------------------------------


class TestPublicQualityGate:
    def _list_ids(self, factory, monkeypatch, **env):
        from app.core.config import get_settings
        from app.repositories.scholarships import list_scholarships
        from app.schemas import ScholarshipQuery

        for key, value in env.items():
            monkeypatch.setenv(key, value)
        get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
        session = factory()
        try:
            items, total = list_scholarships(session, ScholarshipQuery())
            return [s.id for s in items], total
        finally:
            session.close()

    def test_a_verified_record_with_a_validated_image_is_listed(
        self, factory, monkeypatch
    ):
        from datetime import datetime, timezone

        _add(
            factory, 1, url="https://a.example.org/p/1", is_verified=True,
            image_url="https://a.example.org/logo.png",
            image_verified_at=datetime.now(timezone.utc),
        )
        ids, total = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="true",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="true",
        )
        assert ids == [1]
        assert total == 1

    def test_a_record_without_an_image_is_hidden(self, factory, monkeypatch):
        _add(factory, 1, url="https://a.example.org/p/1", is_verified=True)
        ids, total = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="true",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="true",
        )
        assert ids == []
        assert total == 0

    def test_a_non_validated_image_does_not_satisfy_the_gate(
        self, factory, monkeypatch
    ):
        """An image_url alone is not enough; it must have passed validation."""
        _add(
            factory, 1, url="https://a.example.org/p/1", is_verified=True,
            image_url="https://a.example.org/rejected.png",
        )
        ids, _ = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="true",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="true",
        )
        assert ids == []

    def test_an_unverified_record_is_hidden(self, factory, monkeypatch):
        from datetime import datetime, timezone

        _add(
            factory, 1, url="https://a.example.org/p/1", is_verified=False,
            verification_status="needs_review",
            image_url="https://a.example.org/logo.png",
            image_verified_at=datetime.now(timezone.utc),
        )
        ids, _ = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="true",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="true",
        )
        assert ids == []

    def test_the_gate_can_be_switched_off(self, factory, monkeypatch):
        """A gate nobody can reverse is not a gate, it is a data loss bug."""
        from datetime import datetime, timezone

        _add(factory, 1, url="https://a.example.org/p/1", is_verified=True)
        ids, _ = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="true",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="false",
        )
        assert ids == [1]

    def test_quarantined_records_stay_hidden_even_with_the_gate_off(
        self, factory, monkeypatch
    ):
        _add(factory, 1, url="https://a.example.org/", junk=True,
             verification_status="quarantined")
        ids, _ = self._list_ids(
            factory, monkeypatch,
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED="false",
            SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE="false",
        )
        assert ids == []

    def test_stats_agree_with_the_listing(self, factory, monkeypatch):
        """The homepage must not advertise a total the directory contradicts."""
        from datetime import datetime, timezone

        from app.repositories.scholarships import list_scholarships
        from app.schemas import ScholarshipQuery

        _add(
            factory, 1, url="https://a.example.org/p/1", is_verified=True,
            image_url="https://a.example.org/logo.png",
            image_verified_at=datetime.now(timezone.utc),
        )
        _add(factory, 2, url="https://b.example.org/p/2", is_verified=True)

        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED", "true")
        monkeypatch.setenv("SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE", "true")

        from app.models import Scholarship as Model
        from sqlalchemy import func, select
        from app.core.config import get_settings

        settings = get_settings()
        session = factory()
        try:
            _, total = list_scholarships(session, ScholarshipQuery())
            counted = session.scalar(
                select(func.count(Model.id)).where(
                    Model.verification_status != "quarantined",
                    Model.is_verified.is_(True),
                    Model.image_url.isnot(None),
                    Model.image_verified_at.isnot(None),
                )
            ) or 0
        finally:
            session.close()
        assert total == counted == 1

    def test_the_settings_expose_both_switches(self):
        from app.core.config import get_settings

        settings = get_settings()
        assert hasattr(settings, "public_require_verified")
        assert hasattr(settings, "public_require_verified_image")
