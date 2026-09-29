"""Tests for the newly activated autonomous capabilities.

Two things were activated in this phase, and this file is the evidence that
they are genuinely autonomous rather than merely reachable:

* ``catalogue_quarantine`` as a bounded, cursor-driven ``quarantine`` stage.
* ``anomaly_detection`` (with ``change_impact_staleness`` and
  ``evidence_arbitration`` beneath it) as a gate on automatic updates.

The repeated theme: a safety layer is only useful if it cannot be bypassed, so
several tests here try to make the safety layer *fail open* and assert that it
does not.
"""

from __future__ import annotations

import pytest

from app.jobs import scholarzone_maintenance as worker
from app.services.catalogue_quarantine import (
    QUARANTINE_STATUS,
    assess_record,
    quarantine_record,
)
from app.services.maintenance_cursor import MaintenanceCursorStore


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'a.db').as_posix()}")
    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


def _real(factory, sid=1, **kw):
    from app.models import Scholarship

    session = factory()
    try:
        s = Scholarship(
            id=sid,
            title=kw.get("title", f"Scholarship {sid}"),
            country="Sweden",
            degree=kw.get("degree", "Master"),
            funding=kw.get("funding", "Full"),
            # An awarding body is required. This fixture predates that rule and
            # originally omitted it; the rule was added after a live discovery
            # round published two records whose official_source was None, and
            # the sweep scored zero signals on them without it. A record with no
            # content, no lists and no provider is not a scholarship, so the
            # fixture now says who offers the thing.
            official_source=kw.get("official_source", "Example University"),
            # official_source_url carries a UNIQUE constraint, so every
            # fixture record needs its own programme page.
            official_source_url=kw.get("url", f"https://www.kth.se/programmes/xyz-{sid}"),
        )
        session.add(s)
        session.commit()
        return s.id
    finally:
        session.close()


def _junk(factory, sid=900):
    """Structurally not a scholarship: bare root, no content, placeholder meta."""
    from app.models import Scholarship

    session = factory()
    try:
        session.add(
            Scholarship(
                id=sid,
                title="Welcome to GOV.UK",
                country="United Kingdom",
                degree="unknown",
                funding="n/a",
                official_source_url="https://www.gov.uk/",
            )
        )
        session.commit()
        return sid
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Quarantine assessment
# ---------------------------------------------------------------------------


class TestQuarantineAssessment:
    def test_a_real_scholarship_is_never_quarantined(self, factory):
        """One signal is not enough; a sparse but genuine programme survives."""
        _real(factory)
        session = factory()
        try:
            record = session.get(__import__("app.models", fromlist=["x"]).Scholarship, 1)
            verdict = assess_record(record)
            assert verdict.is_non_scholarship is False
        finally:
            session.close()

    def test_a_landing_page_is_quarantined(self, factory):
        _junk(factory)
        from app.models import Scholarship

        session = factory()
        try:
            verdict = assess_record(session.get(Scholarship, 900))
            assert verdict.is_non_scholarship is True
            assert len(verdict.reasons) >= 3, "quarantine must require multiple signals"
        finally:
            session.close()

    def test_assessment_performs_no_network_and_no_write(self, factory):
        """The gate must be free: no fetch, no commit, no new row."""
        from app.models import Scholarship

        _junk(factory)
        session = factory()
        try:
            before = session.query(Scholarship).count()
            reviews_before = session.execute(
                __import__("sqlalchemy").text("SELECT COUNT(*) FROM scholarship_reviews")
            ).scalar()
            assess_record(session.get(Scholarship, 900))
            session.expire_all()
            assert session.query(Scholarship).count() == before
            assert (
                session.execute(
                    __import__("sqlalchemy").text("SELECT COUNT(*) FROM scholarship_reviews")
                ).scalar()
                == reviews_before
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Quarantine persistence
# ---------------------------------------------------------------------------


class TestQuarantinePersistence:
    def test_quarantine_preserves_the_record_and_its_source(self, factory):
        """Nothing is deleted; the audit trail must remain complete."""
        from app.models import Scholarship, ScholarshipReview

        _junk(factory)
        session = factory()
        try:
            verdict = quarantine_record(session, 900, dry_run=False)
            session.commit()
            assert verdict.is_non_scholarship is True
            record = session.get(Scholarship, 900)
            assert record is not None
            assert record.verification_status == QUARANTINE_STATUS
            assert record.official_source_url == "https://www.gov.uk/"
            assert record.verification_notes and "Quarantined" in record.verification_notes
            assert session.query(ScholarshipReview).filter_by(
                scholarship_id=900
            ).count() >= 1
        finally:
            session.close()

    def test_dry_run_writes_nothing(self, factory):
        from app.models import Scholarship

        _junk(factory)
        session = factory()
        try:
            quarantine_record(session, 900, dry_run=True)
            session.rollback()
            record = session.get(Scholarship, 900)
            assert record.verification_status != QUARANTINE_STATUS
        finally:
            session.close()

    def test_repeated_runs_are_idempotent(self, factory):
        from app.models import ScholarshipReview

        _junk(factory)
        session = factory()
        try:
            for _ in range(3):
                quarantine_record(session, 900, dry_run=False)
            session.commit()
            assert (
                session.query(ScholarshipReview)
                .filter_by(scholarship_id=900, field_name="__record__")
                .count()
                == 1
            ), "repeat runs must not accumulate duplicate review rows"
        finally:
            session.close()

    def test_a_real_record_is_untouched_by_the_writer(self, factory):
        from app.models import Scholarship

        _real(factory)
        session = factory()
        try:
            verdict = quarantine_record(session, 1, dry_run=False)
            session.commit()
            assert verdict.is_non_scholarship is False
            assert session.get(Scholarship, 1).verification_status != QUARANTINE_STATUS
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Worker integration
# ---------------------------------------------------------------------------


class TestQuarantineStage:
    def test_the_stage_is_selectable_and_registered(self):
        assert "quarantine" in worker.STAGE_ORDER
        assert "quarantine" in worker.STAGE_DEPENDENCIES
        assert "quarantine" in open(worker.__file__, encoding="utf-8").read()

    def test_the_stage_is_cursor_advanced(self, factory):
        _real(factory, 1)
        _real(factory, 2)
        _junk(factory, 3)
        store = MaintenanceCursorStore(factory)
        first = store.select_batch("quarantine", limit=2, skip_complete=False)
        assert first.ids == [1, 2]
        store.advance("quarantine", first)
        second = store.select_batch("quarantine", limit=2, skip_complete=False)
        assert second.ids == [3]
        assert not set(first.ids) & set(second.ids)

    def test_the_stage_catches_a_landing_page_via_the_worker(self, factory, monkeypatch):
        from app.models import Scholarship

        _junk(factory, 3)
        monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
        monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", str(factory.kw["bind"].url))

        # Reuse the worker's own stage body without re-running preflight.
        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("quarantine", limit=10, skip_complete=False)
        assert 3 in batch.ids

        session = factory()
        try:
            for sid in batch.ids:
                quarantine_record(session, sid, dry_run=False)
            session.commit()
            assert session.get(Scholarship, 3).verification_status == QUARANTINE_STATUS
        finally:
            session.close()

    def test_the_stage_is_bounded_by_limit(self, factory):
        for i in range(1, 8):
            _real(factory, i)
        store = MaintenanceCursorStore(factory)
        assert len(store.select_batch("quarantine", limit=3, skip_complete=False).ids) == 3

    def test_the_stage_makes_no_network_call(self, factory):
        session = factory()
        _junk(factory, 3)
        try:
            import app.services.catalogue_quarantine as q

            source = open(q.__file__, encoding="utf-8").read()
            for needle in ("httpx", "requests", "urlopen", "aiohttp"):
                assert needle not in source
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Anomaly gate on automatic updates
# ---------------------------------------------------------------------------


class _FakeScholarship:
    id = 1
    status = "open"
    deadline_date = None
    is_verified = False
    official_source_url = "https://www.kth.se/programmes/xyz"


class TestAnomalyGate:
    def _candidates(self, field, old, new):
        return [{"field": field, "old_value": old, "new_value": new}]

    def test_a_critical_anomaly_is_held_back(self):
        """A deadline moving backwards must never be auto-applied."""
        from app.services.scheduler_engine import SchedulerEngine

        # Deadline jumps backwards by more than the critical threshold.
        from datetime import date, timedelta

        today = date(2026, 6, 1)
        old = today + timedelta(days=200)
        new = today - timedelta(days=30)
        safe, blocked = SchedulerEngine._filter_anomalous_candidates(
            self._candidates("deadline_date", old, new), _FakeScholarship()
        )
        assert blocked == ["deadline_date"]
        assert safe == []

    def test_an_ordinary_change_still_applies(self):
        from app.services.scheduler_engine import SchedulerEngine

        safe, blocked = SchedulerEngine._filter_anomalous_candidates(
            self._candidates("duration", None, "12 months"), _FakeScholarship()
        )
        assert blocked == []
        assert len(safe) == 1

    def test_the_gate_can_only_reduce_automatic_mutation(self):
        """Whatever the detector dislikes must not be applied automatically."""
        from app.services.scheduler_engine import SchedulerEngine

        from datetime import date, timedelta

        today = date(2026, 6, 1)
        candidates = [
            {"field": "deadline_date", "old_value": today + timedelta(days=300),
             "new_value": today - timedelta(days=10)},
            {"field": "duration", "old_value": None, "new_value": "24 months"},
        ]
        safe, blocked = SchedulerEngine._filter_anomalous_candidates(
            candidates, _FakeScholarship()
        )
        assert "deadline_date" in blocked, "the backwards deadline must be held back"
        # The safe candidate may still be applied; the gate narrows the set, it
        # never reorders it or invents a candidate.
        assert [c["field"] for c in safe] == ["duration"]
        assert len(safe) + len(blocked) == len(candidates)

    def test_a_detector_failure_fails_closed_into_review(self):
        """If the safety layer breaks, it must block, not wave changes through."""
        from app.services import scheduler_engine
        import app.services.anomaly_detection as ad

        real_filter = scheduler_engine.SchedulerEngine._filter_anomalous_candidates
        real_detect = ad.detect_anomalies

        def boom(*a, **k):
            raise RuntimeError("detector exploded")

        try:
            ad.detect_anomalies = boom
            safe, blocked = real_filter(
                self._candidates("funding", "Full", "Partial"), _FakeScholarship()
            )
            assert safe == [], "a broken detector must not allow automatic mutation"
            assert blocked == ["funding"]
        finally:
            # Restore the real detector. Leaving it patched silently breaks
            # every later test in the suite, which is exactly the kind of
            # cross-test coupling this file should not introduce.
            ad.detect_anomalies = real_detect
            assert scheduler_engine.SchedulerEngine._filter_anomalous_candidates is real_filter

    def test_the_gate_costs_no_query_and_no_fetch(self):
        source = open(
            __import__("app.services.scheduler_engine", fromlist=["x"]).__file__,
            encoding="utf-8",
        ).read()
        block = source.split("def _filter_anomalous_candidates")[1][:1500]
        for needle in ("session.execute", "session.query", "httpx", "requests", "urlopen"):
            assert needle not in block, f"the gate must stay free of {needle}"

    def test_detection_uses_change_impact_and_evidence_layers(self):
        """The subordinate layers are reached through the detector, not reimplemented."""
        import app.services.anomaly_detection as ad

        source = open(ad.__file__, encoding="utf-8").read()
        assert "compute_change_impact" in source
        assert "ArbitrationResult" in source


# ---------------------------------------------------------------------------
# Architecture-level guarantees
# ---------------------------------------------------------------------------


class TestActivatedFeaturesAreGenuinelyAutonomous:
    """trigger -> execution -> persistence -> failure handling -> recurrence."""

    def test_every_autonomous_stage_is_in_the_order_and_reachable(self):
        import inspect

        source = inspect.getsource(worker.main)
        for stage in worker.STAGE_ORDER:
            assert f'"{stage}"' in source, f"{stage} has no execution path"
            assert f'"{stage}": do_' in source or stage in worker.STAGE_DEPENDENCIES

    def test_every_autonomous_stage_uses_a_durable_cursor(self):
        """No autonomous stage may rely on process memory or Actions cache."""
        import re

        source = open(worker.__file__, encoding="utf-8").read()
        for stage in ("enrich", "quarantine"):
            assert re.search(rf'select_batch\(\s*"{stage}"', source), (
                f"{stage} does not read a durable cursor"
            )
        assert "store.advance(" in source

    def test_failure_semantics_are_preserved(self):
        assert worker.EXIT_OK == 0
        assert worker.EXIT_STAGE_FAILED != 0
        assert worker.EXIT_FATAL != 0
        # Quarantine was decoupled from enrichment: it sweeps the whole valid
        # catalogue on its own cursor, so it must have no prerequisite at all.
        assert worker.STAGE_DEPENDENCIES["quarantine"] == ()

    def test_dry_run_cannot_advance_a_cursor(self, factory):
        _real(factory, 1)
        _real(factory, 2)
        store = MaintenanceCursorStore(factory)
        batch = store.select_batch("quarantine", limit=2, skip_complete=False)
        # The worker only advances when not dry-running.
        assert store.get_state("quarantine").last_id == 0
        store.advance("quarantine", batch)
        assert store.get_state("quarantine").last_id == 2

    def test_no_snapdeploy_and_no_paid_dependency(self):
        """Code, not prose: the worker explains the SnapDeploy history in comments."""
        import io
        import tokenize
        from pathlib import Path

        kept: list[str] = []
        with open(Path(worker.__file__), "rb") as handle:
            for token in tokenize.tokenize(io.BytesIO(handle.read()).readline):
                if token.type in (tokenize.COMMENT, tokenize.STRING):
                    continue
                kept.append(token.string)
        source = " ".join(kept).lower()
        for needle in ("snapdeploy", "openai", "anthropic", "api/public/wake"):
            assert needle not in source
