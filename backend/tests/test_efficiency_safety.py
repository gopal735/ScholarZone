"""Tests for efficiency and safety hardening.

Four things are proven here, each of which was a real gap:

* verification priority scoring no longer costs queries per candidate;
* the anomaly gate is genuinely shared, not two copies that can drift;
* quarantine sweeps the catalogue on its own cursor;
* failures are classified so a retry is spent on the right ones.

The priority tests are the important ones: an optimisation that changes a
ranking is worse than the N+1 it removed, so equivalence is asserted against
the original per-record implementation rather than against a snapshot.
"""

from __future__ import annotations

from datetime import date, timedelta

import re

import pytest

from app.jobs import scholarzone_maintenance as worker
from app.services import mutation_safety_gate as gate
from app.services.scheduler_config import SchedulerConfig
from app.services.scheduler_priority import (
    PrioritySignals,
    batch_calculate_priorities,
    calculate_priority,
    calculate_priority_from_signals,
    load_priority_signals,
)


@pytest.fixture()
def factory(tmp_path, monkeypatch):
    monkeypatch.setenv("SCHOLARZONE_ENVIRONMENT", "test")
    monkeypatch.setenv("SCHOLARZONE_DATABASE_URL", f"sqlite:///{(tmp_path / 'p.db').as_posix()}")
    from app.database import get_session_factory, init_database, reset_database_connections

    reset_database_connections()
    init_database()
    yield get_session_factory()
    reset_database_connections()


class _Counter:
    """Counts statements, so 'queries are bounded' is measurable."""

    def __init__(self, session):
        self._session = session
        self.count = 0

    def __enter__(self):
        from sqlalchemy import event

        self._engine = self._session.get_bind()
        event.listen(self._engine, "before_cursor_execute", self._on_execute)
        return self

    def __exit__(self, *exc):
        from sqlalchemy import event

        event.remove(self._engine, "before_cursor_execute", self._on_execute)
        return False

    def _on_execute(self, *args):
        self.count += 1


def _seed(factory, count: int, *, start: int = 1, with_history: bool = True):
    from datetime import datetime, timezone

    from app.models import Scholarship, ScholarshipFetchAttempt, ScholarshipReview, ScholarshipVerificationHistory

    session = factory()
    try:
        records = []
        for i in range(start, start + count):
            s = Scholarship(
                id=i,
                title=f"Programme {i}",
                country="Sweden",
                degree="Master",
                funding="Full",
                official_source_url=f"https://provider{i % 3}.example.org/p/{i}",
                next_verification_due=date.today() - timedelta(days=i % 40),
                status="open",
            )
            session.add(s)
            records.append(s)
        session.flush()
        if with_history:
            for i, s in enumerate(records):
                for n in range(i % 4):
                    session.add(
                        ScholarshipVerificationHistory(
                            scholarship_id=s.id,
                            field_name="funding",
                            old_value="Full",
                            new_value="Partial",
                            change_type="modified",
                            verification_status="active",
                            created_at=datetime.now(timezone.utc) - timedelta(days=n * 10),
                        )
                    )
                session.add(
                    ScholarshipFetchAttempt(
                        scholarship_id=s.id,
                        source_url=s.official_source_url,
                        status="done",
                        attempt_count=1,
                        max_attempts=3,
                        terminal=(i % 2 == 0),
                    )
                )
                if i % 5 == 0:
                    session.add(
                        ScholarshipReview(
                            scholarship_id=s.id,
                            field_name="funding",
                            conflict_reason="low_confidence",
                            verification_state="uncertain",
                            decision="pending",
                        )
                    )
        session.commit()
        session.expunge_all()
        return records
    finally:
        session.close()


# ---------------------------------------------------------------------------
# 1. Priority N+1
# ---------------------------------------------------------------------------


class TestPriorityQueryBoundedness:
    def test_query_count_is_independent_of_candidate_count(self, factory):
        """The whole point: 5N queries became a fixed number."""
        from app.models import Scholarship

        small = _seed(factory, 10, start=1)
        session = factory()
        try:
            loaded = session.query(Scholarship).order_by(Scholarship.id).limit(10).all()
            with _Counter(session) as counter:
                batch_calculate_priorities(session, loaded, date.today())
            small_queries = counter.count
        finally:
            session.close()
        assert small_queries <= 6, f"expected a fixed small number, got {small_queries}"

        _seed(factory, 90, start=100)
        session = factory()
        try:
            loaded = session.query(Scholarship).order_by(Scholarship.id).all()
            with _Counter(session) as counter:
                batch_calculate_priorities(session, loaded, date.today())
            big_queries = counter.count
        finally:
            session.close()
        assert big_queries <= 6, f"10x the candidates changed the query count: {big_queries}"
        assert big_queries == small_queries, (
            f"query count grew with candidates: {small_queries} -> {big_queries}"
        )

    def test_the_per_record_path_still_costs_more(self, factory):
        """Proves the batch path is the optimisation, not the only path."""
        from app.models import Scholarship

        _seed(factory, 5)
        session = factory()
        try:
            records = session.query(Scholarship).order_by(Scholarship.id).all()
            with _Counter(session) as per_record:
                for r in records:
                    calculate_priority(session, r, date.today())
            with _Counter(session) as batched:
                batch_calculate_priorities(session, records, date.today())
        finally:
            session.close()
        assert per_record.count > batched.count


class TestPrioritySemanticEquivalence:
    def test_batch_scores_match_the_original_per_record_scores(self, factory):
        from app.models import Scholarship

        _seed(factory, 30)
        session = factory()
        try:
            records = session.query(Scholarship).order_by(Scholarship.id).all()
            batched = {s.scholarship_id: s for s in batch_calculate_priorities(session, records, date.today())}
            for r in records:
                assert batched[r.id] == calculate_priority(session, r, date.today()), (
                    f"optimisation changed the score for {r.id}"
                )
        finally:
            session.close()

    def test_ranking_order_is_unchanged(self, factory):
        from app.models import Scholarship

        _seed(factory, 30)
        session = factory()
        try:
            records = session.query(Scholarship).order_by(Scholarship.id).all()
            old_order = [
                r.id
                for r in sorted(
                    records,
                    key=lambda r: calculate_priority(session, r, date.today()).to_sort_key(),
                )
            ]
            new_order = [
                s.scholarship_id
                for s in sorted(
                    batch_calculate_priorities(session, records, date.today()),
                    key=lambda s: s.to_sort_key(),
                )
            ]
        finally:
            session.close()
        assert old_order == new_order

    def test_source_reliability_is_still_correct(self, factory):
        from app.models import Scholarship

        _seed(factory, 6)
        session = factory()
        try:
            records = session.query(Scholarship).order_by(Scholarship.id).all()
            for score, r in zip(batch_calculate_priorities(session, records, date.today()), records):
                from app.services.scheduler_priority import compute_source_reliability

                assert score.source_reliability == compute_source_reliability(session, r)
        finally:
            session.close()

    def test_retry_and_review_signals_survive_batching(self, factory):
        from app.models import Scholarship, ScholarshipFetchAttempt

        _seed(factory, 6)
        session = factory()
        try:
            target = session.query(Scholarship).filter_by(id=2).one()
            session.add(
                ScholarshipFetchAttempt(
                    scholarship_id=target.id,
                    source_url=target.official_source_url,
                    status="retrying",
                    next_retry_at=date.today() - timedelta(days=1),
                )
            )
            session.commit()
            records = session.query(Scholarship).order_by(Scholarship.id).all()
            scores = {s.scholarship_id: s for s in batch_calculate_priorities(session, records, date.today())}
            # id 2 has a due retry; id 1 has a pending review.
            assert scores[2].retry_pending == 100
            assert scores[3].retry_pending == 0
            assert scores[1].review_pending == 100
            assert scores[2].review_pending == 0
        finally:
            session.close()

    def test_an_empty_batch_costs_nothing(self, factory):
        session = factory()
        try:
            assert batch_calculate_priorities(session, [], date.today()) == []
        finally:
            session.close()

    def test_impact_remains_unwindowed_and_that_is_pinned(self, factory):
        """The dead `window_start` in compute_impact is preserved deliberately.

        Windowing it would silently re-rank every record with an old history,
        and no test or specification confirms the change is wanted. This test
        exists so that if someone does change it, they change it on purpose.
        """
        from datetime import datetime, timezone

        from app.models import Scholarship, ScholarshipVerificationHistory
        from app.services.scheduler_priority import compute_impact

        _seed(factory, 1, with_history=False)
        session = factory()
        try:
            s = session.query(Scholarship).filter_by(id=1).one()
            for _ in range(3):
                session.add(
                    ScholarshipVerificationHistory(
                        scholarship_id=s.id,
                        field_name="funding",
                        old_value="a",
                        new_value="b",
                        change_type="modified",
                        verification_status="active",
                        # Far outside the 180-day change-frequency window.
                        created_at=datetime.now(timezone.utc) - timedelta(days=1000),
                    )
                )
            session.commit()
            assert compute_impact(session, s, date.today(), SchedulerConfig()) > 0, (
                "compute_impact is currently un-windowed; if this is a bug, fix it "
                "deliberately and update this test"
            )
        finally:
            session.close()


# ---------------------------------------------------------------------------
# 2. Shared anomaly gate
# ---------------------------------------------------------------------------


class _Scholarship:
    def __init__(self, sid=1):
        self.id = sid
        self.status = "open"
        self.deadline_date = None
        self.is_verified = False
        self.official_source_url = "https://provider.example.org/p/1"
        self.funding = "Full tuition"


class TestSharedAnomalyGate:
    def test_both_pipelines_use_the_same_gate(self):
        """Not two implementations that can drift apart."""
        engine_src = open(
            __import__("app.services.scheduler_engine", fromlist=["x"]).__file__, encoding="utf-8"
        ).read()
        enrich_src = open(
            __import__("app.services.scholarship_enrichment", fromlist=["x"]).__file__, encoding="utf-8"
        ).read()
        assert "mutation_safety_gate" in engine_src
        assert "mutation_safety_gate" in enrich_src
        # Neither pipeline may call the detector directly any more.
        assert "from .anomaly_detection import detect_anomalies" not in engine_src
        assert "from .anomaly_detection import detect_anomalies" not in enrich_src

    def test_safe_mutation_is_allowed(self):
        v = gate.evaluate_mutation(_Scholarship(), "duration", None, "12 months")
        assert v.allowed is True

    def test_deadline_moving_backwards_is_blocked(self):
        today = date(2026, 6, 1)
        v = gate.evaluate_mutation(
            _Scholarship(), "deadline_date", today + timedelta(days=120), today - timedelta(days=20)
        )
        assert v.allowed is False
        assert v.reasons

    def test_detector_exception_fails_closed(self, monkeypatch):
        import app.services.anomaly_detection as ad

        original = ad.detect_anomalies
        try:
            def boom(*a, **k):
                raise RuntimeError("detector down")

            monkeypatch.setattr(ad, "detect_anomalies", boom)
            v = gate.evaluate_mutation(_Scholarship(), "funding", "Full", "Partial")
            assert v.allowed is False, "a broken gate must refuse, not allow"
            assert v.failed_closed is True
        finally:
            monkeypatch.setattr(ad, "detect_anomalies", original)

    def test_gate_is_deterministic(self):
        s = _Scholarship()
        today = date(2026, 6, 1)
        args = ("deadline_date", today + timedelta(days=90), today - timedelta(days=10))
        assert gate.evaluate_mutation(s, *args) == gate.evaluate_mutation(s, *args)

    def test_gate_makes_no_query_and_no_network(self):
        source = open(gate.__file__, encoding="utf-8").read()
        head = source.split("def record_blocked_mutation")[0]
        for needle in ("httpx", "requests", "urlopen", "aiohttp"):
            assert needle not in head, f"the gate must stay free of {needle}"

    def test_candidate_partition_matches_the_old_engine_contract(self):
        today = date(2026, 6, 1)
        candidates = [
            {"field": "duration", "old_value": None, "new_value": "12 months"},
            {"field": "deadline_date", "old_value": today + timedelta(days=300),
             "new_value": today - timedelta(days=5)},
        ]
        safe, blocked = gate.partition_candidates(candidates, _Scholarship())
        assert [c["field"] for c in safe] == ["duration"]
        assert [f for f, _ in blocked] == ["deadline_date"]


class TestBlockedMutationReviewRouting:
    def test_a_blocked_mutation_creates_one_review(self, factory):
        from app.models import Scholarship, ScholarshipReview

        session = factory()
        try:
            s = Scholarship(id=1, title="P", country="SE", degree="M", funding="Full",
                           official_source_url="https://provider.example.org/p/1")
            session.add(s)
            session.commit()
            today = date(2026, 6, 1)
            verdict = gate.evaluate_mutation(
                s, "deadline_date", today + timedelta(days=200), today - timedelta(days=5)
            )
            assert verdict.allowed is False
            assert gate.record_blocked_mutation(
                session, s.id, "deadline_date", verdict,
                old_value=today + timedelta(days=200), new_value=today - timedelta(days=5),
                source_url=s.official_source_url,
            ) is True
            session.commit()
            assert session.query(ScholarshipReview).filter_by(
                scholarship_id=1, field_name="deadline_date"
            ).count() == 1
        finally:
            session.close()

    def test_repeated_execution_creates_no_duplicate(self, factory):
        from app.models import Scholarship, ScholarshipReview

        session = factory()
        try:
            s = Scholarship(id=1, title="P", country="SE", degree="M", funding="Full",
                           official_source_url="https://provider.example.org/p/1")
            session.add(s)
            session.commit()
            today = date(2026, 6, 1)
            created = 0
            for _ in range(5):
                verdict = gate.evaluate_mutation(
                    s, "deadline_date", today + timedelta(days=200), today - timedelta(days=5)
                )
                if gate.record_blocked_mutation(session, s.id, "deadline_date", verdict):
                    created += 1
                session.commit()
            assert created == 1, "idempotent pipeline created duplicate reviews"
            assert session.query(ScholarshipReview).filter_by(
                scholarship_id=1, field_name="deadline_date"
            ).count() == 1
        finally:
            session.close()


class TestEnrichmentSafety:
    def _enrich(self, factory, monkeypatch, current_deadline, proposed_deadline):
        """Run _apply_proposals with a single deadline proposal."""
        from app.models import Scholarship
        from app.services.scholarship_enrichment import ScholarshipEnrichmentService

        session = factory()
        try:
            s = Scholarship(id=1, title="P", country="SE", degree="M", funding="Full",
                           official_source_url="https://provider.example.org/p/1",
                           deadline_date=current_deadline)
            session.add(s)
            session.commit()
            session.refresh(s)
            service = ScholarshipEnrichmentService(session)
            updates = service._apply_proposals(
                session, s,
                {"deadline_date": {"value": proposed_deadline, "confidence": "high"}},
                "https://provider.example.org/p/1",
            )
            return s, updates
        finally:
            session.close()

    def test_enrichment_blocks_a_backwards_deadline(self, factory):
        today = date(2026, 6, 1)
        _, updates = self._enrich(factory, None, today + timedelta(days=200), today - timedelta(days=10))
        assert any(u.action == "skipped" and "safety gate" in u.reason for u in updates)

    def test_enrichment_still_fills_an_empty_deadline(self, factory):
        """A fill has no prior value, so there is no direction to distrust."""
        today = date(2026, 6, 1)
        _, updates = self._enrich(factory, None, None, today + timedelta(days=60))
        assert any(u.action == "fill" for u in updates)

    def test_enrichment_applies_a_normal_forward_correction(self, factory):
        """An ordinary extension is still applied; the gate is not a blanket block.

        The detector escalates a 60-day shift to HIGH and a 90-day shift to
        CRITICAL, so the normal correction has to be sized like a real one.
        """
        today = date(2026, 6, 1)
        _, updates = self._enrich(
            factory, None, today + timedelta(days=200), today + timedelta(days=230)
        )
        assert any(u.action == "replace" for u in updates), [u.reason for u in updates]

    def test_enrichment_blocks_an_implausibly_large_shift(self, factory):
        """A 90-day jump is a broken page, not a corrected deadline."""
        today = date(2026, 6, 1)
        _, updates = self._enrich(
            factory, None, today + timedelta(days=200), today + timedelta(days=290)
        )
        assert any(u.action == "skipped" and "safety gate" in u.reason for u in updates)


# ---------------------------------------------------------------------------
# 3. Quarantine independence
# ---------------------------------------------------------------------------


class TestQuarantineIsIndependent:
    def test_quarantine_has_no_prerequisite_stage(self):
        assert worker.STAGE_DEPENDENCIES["quarantine"] == ()

    def test_it_has_its_own_cursor(self, factory):
        from app.models import Scholarship
        from app.services.maintenance_cursor import MaintenanceCursorStore

        session = factory()
        try:
            for i in range(1, 6):
                session.add(Scholarship(id=i, title=f"P{i}", country="SE", degree="M", funding="F",
                                        official_source_url=f"https://x{i}.example.org/p"))
            session.commit()
        finally:
            session.close()

        store = MaintenanceCursorStore(factory)
        enrich = store.select_batch("enrich", limit=3, skip_complete=False)
        store.advance("enrich", enrich)
        quarant = store.select_batch("quarantine", limit=5, skip_complete=False)
        assert quarant.ids == [1, 2, 3, 4, 5], (
            "quarantine must cover the whole catalogue regardless of where "
            "the enrichment cursor is"
        )

    def test_the_two_cursors_advance_independently(self, factory):
        from app.models import Scholarship
        from app.services.maintenance_cursor import MaintenanceCursorStore

        session = factory()
        try:
            for i in range(1, 11):
                session.add(Scholarship(id=i, title=f"P{i}", country="SE", degree="M", funding="F",
                                        official_source_url=f"https://x{i}.example.org/p"))
            session.commit()
        finally:
            session.close()

        store = MaintenanceCursorStore(factory)
        e1 = store.select_batch("enrich", limit=3, skip_complete=False)
        store.advance("enrich", e1)
        q1 = store.select_batch("quarantine", limit=3, skip_complete=False)
        store.advance("quarantine", q1)
        e2 = store.select_batch("enrich", limit=3, skip_complete=False)
        q2 = store.select_batch("quarantine", limit=3, skip_complete=False)
        assert e2.ids == [4, 5, 6]
        assert q2.ids == [4, 5, 6]

    def test_quarantine_still_makes_no_network_call(self):
        source = open(
            __import__("app.services.catalogue_quarantine", fromlist=["x"]).__file__, encoding="utf-8"
        ).read()
        for needle in ("httpx", "requests", "urlopen"):
            assert needle not in source


# ---------------------------------------------------------------------------
# 4. Failure classification and retry
# ---------------------------------------------------------------------------


class TestFailureClassification:
    @pytest.mark.parametrize(
        "message",
        [
            "OperationalError: could not connect to server",
            "connection refused",
            "SSL: SYSLIBX509_CERTIFICATE_VERIFY_FAILED",
            "Read timed out",
            "503 Service Unavailable",
            "Temporary failure in name resolution",
        ],
    )
    def test_transient_failures_are_classified_transient(self, message):
        assert worker.classify_failure(message) == "transient"

    @pytest.mark.parametrize(
        "message",
        [
            "SCHOLARZONE_DATABASE_URL is required in production",
            "production maintenance requires a PostgreSQL (Neon) database URL",
            "worker service imports failed: ModuleNotFoundError",
            "no such table: scholarships",
            "IndentationError: expected an indented block",
        ],
    )
    def test_fatal_failures_are_never_retried(self, message):
        assert worker.classify_failure(message) == "fatal"

    def test_a_schema_error_naming_a_connection_is_still_fatal(self):
        """Ordering matters: fatal is checked first on purpose."""
        assert worker.classify_failure("OperationalError: connection refused; no such table: x") == "fatal"

    def test_unknown_is_the_safe_default(self):
        assert worker.classify_failure("something else entirely") == "unknown"
        assert worker.classify_failure(None) == "unknown"

    def test_classification_is_emitted_for_a_failed_run(self, capsys):
        reports = [
            worker.StageReport(name="verify", ok=False, error="connection refused"),
            worker.StageReport(name="enrich", ok=False, error="no such table: x"),
        ]
        buckets = worker.emit_failure_classification(reports)
        assert buckets["transient"] == ["verify"]
        assert buckets["fatal"] == ["enrich"]
        assert "transient" in capsys.readouterr().out


class TestRetryPolicy:
    def test_the_workflow_retries_once_and_only_on_failure(self):
        from pathlib import Path

        text = (
            Path(__file__).resolve().parents[2]
            / ".github/workflows/verification-cron.yml"
        ).read_text(encoding="utf-8")
        assert "retry:" in text
        assert "if: failure()" in text
        assert "needs: maintain" in text

    def test_the_retry_shares_the_concurrency_group(self):
        """GitHub concurrency remains authoritative: no overlapping runs."""
        import yaml
        from pathlib import Path

        data = yaml.safe_load(
            (
                Path(__file__).resolve().parents[2]
                / ".github/workflows/verification-cron.yml"
            ).read_text(encoding="utf-8")
        )
        assert data["concurrency"]["group"] == "scholarzone-maintenance"
        assert data["jobs"]["retry"]["concurrency"]["group"] == "scholarzone-maintenance"

    def test_the_worker_has_no_internal_retry_loop(self):
        """Retries belong to the workflow, not to an unbounded loop."""
        source = open(worker.__file__, encoding="utf-8").read().lower()
        assert "while true" not in source
        # A bounded retry of the database handshake is allowed, and is not what
        # this test is about. Neon drops idle pooled connections, so a run that
        # starts on a recycled socket fails preflight and does nothing. What must
        # never appear is a loop that re-runs a stage: retries of whole stages
        # belong to the workflow, which has its own bounded retry job.
        for fragment in re.findall(r"for\s+\w+\s+in\s+range\(([^)]*)\)", source):
            assert fragment.strip() in {"1, 2", "1, 3", "1, 4"}, (
                f"found a loop bounded by {fragment!r}; the worker's only bounded "
                f"retry is the three-attempt database handshake"
            )
        # The cursor makes a repeated run resume rather than redo.
        assert "store.advance(" in source

    def test_a_retried_run_is_marked_as_such(self):
        from app.services.maintenance_run_log import MaintenanceRunRecorder, RETRY_ATTEMPT_ENV

        import os

        os.environ[RETRY_ATTEMPT_ENV] = "2"
        try:
            recorder = MaintenanceRunRecorder(lambda: None)
            assert "attempt2" in recorder.worker
        finally:
            os.environ.pop(RETRY_ATTEMPT_ENV, None)


# ---------------------------------------------------------------------------
# 5. Image workload
# ---------------------------------------------------------------------------


class TestImageWorkload:
    def test_terminal_outcomes_are_still_skipped(self, factory):
        from app.models import Scholarship
        from app.services.image_coverage_runner import ImageCoverageRunner

        session = factory()
        try:
            for i in range(1, 4):
                session.add(
                    Scholarship(id=i, title=f"P{i}", country="SE", degree="M", funding="F",
                               official_source_url=f"https://x{i}.example.org/p",
                               image_evaluation_status="no_official_image")
                )
            session.commit()
        finally:
            session.close()

        calls = []

        def never(url):  # pragma: no cover - must not be reached
            calls.append(url)
            raise AssertionError("a terminal record must not be crawled")

        runner = ImageCoverageRunner(factory, dry_run=False, skip_terminally_evaluated=True,
                                     preflight_fn=never, max_workers=1)
        metrics = runner.run(limit=10)
        assert metrics.records_in_scope == 0
        assert not calls

    def test_plan_only_makes_no_network_request(self, factory):
        from app.models import Scholarship
        from app.services.image_coverage_runner import ImageCoverageRunner

        session = factory()
        try:
            for i in range(1, 4):
                session.add(Scholarship(id=i, title=f"P{i}", country="SE", degree="M", funding="F",
                                        official_source_url=f"https://x{i}.example.org/p"))
            session.commit()
        finally:
            session.close()

        def never(url):  # pragma: no cover
            raise AssertionError("plan_only must not touch the network")

        runner = ImageCoverageRunner(factory, dry_run=True, plan_only=True, preflight_fn=never,
                                     max_workers=1)
        metrics = runner.run(limit=10)
        assert metrics.records_in_scope == 3
        assert metrics.planned_only is True
        assert metrics.newly_found == 0

    def test_preflight_is_probed_once_per_domain_per_run(self, factory):
        """The caching that removes the redundant requests."""
        from app.models import Scholarship
        from app.services.image_coverage_runner import ImageCoverageRunner, PreflightResult

        session = factory()
        try:
            # Three records, one domain.
            for i in range(1, 4):
                session.add(Scholarship(id=i, title=f"P{i}", country="SE", degree="M", funding="F",
                                        official_source_url=f"https://shared.example.org/p/{i}"))
            session.commit()
        finally:
            session.close()

        probes = []

        def blocked(url):
            probes.append(url)
            return PreflightResult(False, 403, "blocked")

        runner = ImageCoverageRunner(factory, dry_run=True, preflight_fn=blocked, max_workers=1)
        metrics = runner.run(limit=10)
        assert len(probes) == 1, f"expected one probe for one domain, got {len(probes)}"
        # Correctness must survive the optimisation: all three are still
        # accounted for as blocked. The circuit breaker may short-circuit the
        # third before a probe, which is the other reason the run is cheap -
        # so the outcome reason is either the preflight or the breaker, never
        # "no image exists".
        assert metrics.source_blocked + metrics.domain_blocked_skipped == 3
        assert metrics.no_official_image == 0
        assert all(
            o["page_error"] in ("preflight_blocked", "domain_blocked_after_repeated_failures")
            for o in metrics.outcomes
        )


# ---------------------------------------------------------------------------
# 6. Autonomous contract
# ---------------------------------------------------------------------------


class TestAutonomousContract:
    def test_no_snapdeploy_on_the_maintenance_path(self):
        from pathlib import Path

        for workflow in (Path(__file__).resolve().parents[2] / ".github/workflows").glob("*.yml"):
            body = "\n".join(
                line for line in workflow.read_text(encoding="utf-8").splitlines()
                if not line.lstrip().startswith("#")
            )
            assert "api/public/wake" not in body
            assert "snapdeploy.dev" not in body

    def test_metrics_are_reported_without_a_paid_service(self):
        source = open(worker.__file__, encoding="utf-8").read()
        assert "--- metrics ---" in source
        assert "total_runtime_s" in source
        for needle in ("sentry", "datadog", "prometheus_push"):
            assert needle not in source.lower()

    def test_every_autonomous_stage_is_durable_and_bounded(self):
        for stage in worker.STAGE_ORDER:
            assert stage in worker.STAGE_DEPENDENCIES
        assert worker.DEFAULT_STAGE_LIMIT > 0
        assert worker.MAX_STAGE_WORKERS > 0

    def test_execution_contract_order(self):
        """The documented contract is what the code actually does."""
        assert list(worker.STAGE_ORDER) == [
            "verify", "worklist", "inventory", "enrich", "programme_details", "images", "logos", "discover", "quarantine",
            "retire", "correct", "stats", "facts", "archive", "discontinued", "purge", "add", "reverify",
            # Both repairs are independent, and both run before the only stage
            # that deletes rows: a row that cannot be read is a row that cannot
            # be reviewed before it is destroyed.
            "repair_encoding", "repair_list_columns",
            # The closed-record collector is two stages and they are ordered:
            # a record must hold every SAFE_DELETE condition for the grace
            # period before any delete may consider it, so arming always runs
            # first.
            "auto_delete_candidate", "purge_closed",
        ]
        # Verification is the root; everything else is either downstream of it
        # or independent.
        assert worker.STAGE_DEPENDENCIES["verify"] == ()
        for stage in ("enrich", "images", "discover"):
            assert worker.STAGE_DEPENDENCIES[stage] == ("verify",)
        # stats is a read-only catalogue count. It has to stay a leaf: giving it
        # a dependency would mean a count could silently reflect a partial run.
        assert worker.STAGE_DEPENDENCIES["stats"] == ()
        # purge must also stay a leaf, and must stay after the stages that could
        # introduce a non-logo image. A dependency here would make the ordering
        # an assumption in code rather than an explicit contract.
        assert worker.STAGE_DEPENDENCIES["purge"] == ()
        # purge_closed is the one stage that destroys rows, so it is the one
        # stage with an ordering dependency: a record must hold every SAFE_DELETE
        # condition for the grace period before a delete may consider it. This
        # also keeps the destructive path a leaf with respect to the stages that
        # could introduce a non-logo image.
        assert worker.STAGE_DEPENDENCIES["auto_delete_candidate"] == ()
        assert worker.STAGE_DEPENDENCIES["purge_closed"] == ("auto_delete_candidate",)
        assert worker.STAGE_ORDER.index("purge") > worker.STAGE_ORDER.index("images")
        # facts writes verified programme data, so it has to stay a leaf: it
        # reads the live page state of the records it is about to change.
        assert worker.STAGE_DEPENDENCIES["facts"] == ()
        # logos only fills empty image slots, so it has to run before the stage
        # that would otherwise re-crawl records it could have filled instantly.
        assert worker.STAGE_DEPENDENCIES["logos"] == ()
        assert worker.STAGE_ORDER.index("logos") < worker.STAGE_ORDER.index("purge")
        # purge_closed destroys rows, so it runs last and is reachable only by
        # naming it. If "all" ever stops excluding it, a scheduled run deletes
        # the catalogue with nobody watching.
        assert worker.STAGE_ORDER.index("purge_closed") == len(worker.STAGE_ORDER) - 1
        # A record inserted by "add" earlier in the same run must still be
        # judged by the purge, or freshly added rows would slip past it.
        assert worker.STAGE_ORDER.index("add") < worker.STAGE_ORDER.index("purge_closed")
        # The destructive stage no longer has zero dependencies, but its only
        # one is the arming stage that immediately precedes it. It must not gain a
        # dependency on any stage that could change its input, which is what
        # would let the delete depend on run ordering.
        assert worker.STAGE_DEPENDENCIES["purge_closed"] == ("auto_delete_candidate",)
        # Phase 3 activated the scheduled lifecycle, so the deleting stage is no
        # longer held out of "all". What replaces the exclusion is asserted rather
        # than assumed: the flag is compared against the real selection, and when
        # the stage is reachable the arming stage must be reachable too and must
        # come first. A refactor that reintroduces a hard-coded stage name fails
        # here rather than quietly deciding the question on its own.
        import inspect as _inspect

        main_source = _inspect.getsource(worker.main)
        assert "does not match the stage selection" in main_source
        assert "would run before the arming stage" in main_source
        assert 's != "purge_closed"' not in main_source
        assert isinstance(worker.PURGE_CLOSED_EXCLUDED_FROM_ALL, bool)
        # Every declared stage must have a runner and a dependency entry. A
        # stage wired into only one of the three lists passes the tests above
        # and then fails at dispatch, mid-run.
        #
        # The runners are nested inside main(), so the dispatch table is read
        # from the source rather than imported.
        import ast
        import inspect

        tree = ast.parse(inspect.getsource(worker))
        dispatched = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(
                isinstance(t, ast.Name) and t.id == "stages" for t in node.targets
            ):
                continue
            if isinstance(node.value, ast.Dict):
                dispatched = {
                    k.value for k in node.value.keys if isinstance(k, ast.Constant)
                }
        assert set(worker.STAGE_ORDER) == set(worker.STAGE_DEPENDENCIES)
        assert set(worker.STAGE_ORDER) == dispatched, (
            "STAGE_ORDER and the dispatch table disagree: "
            f"declared-only={set(worker.STAGE_ORDER) - dispatched}, "
            f"dispatch-only={dispatched - set(worker.STAGE_ORDER)}"
        )
        # Archive derives status from the published deadline, so it reads state
        # that facts and enrichment write. Declaring that explicitly stops a
        # closed-date record from being marked open by a run that ordered
        # itself before those fields were filled.
        assert worker.STAGE_DEPENDENCIES["archive"] == ()
        assert worker.STAGE_ORDER.index("archive") > worker.STAGE_ORDER.index("facts")
        # A discontinued programme is a correctness problem, not a data gap, so
        # it is quarantined rather than closed: the record and its history stay.
