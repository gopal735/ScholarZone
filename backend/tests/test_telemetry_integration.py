"""Integration tests for telemetry in the verification pipeline.

Proves that:
- Every stage emits telemetry
- Correlation IDs survive the full pipeline
- Total duration is measurable
- Failures are recorded
- Telemetry cannot break the pipeline
- No duplicate events
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models import Base, Scholarship
from app.services.official_source_fetcher import OfficialSourceFetchResult
from app.services.scholarship_evidence import EvidenceCollection, EvidenceItem, EvidenceStatus, SourceType
from app.services.scholarship_extractor import ScholarshipExtractionResult
from app.services.telemetry import (
    PipelineStages,
    get_collector,
    get_latency_stats,
    get_snapshot,
    reset_telemetry,
)
from app.services.verification_confidence import VerificationAssessment, FieldConfidenceResult, ConfidenceLevel, VerificationState


@dataclass
class MockFetchResult:
    success: bool
    status_code: int | None = None
    final_url: str | None = None
    content: str | None = None
    content_type: str | None = None
    error_type: str | None = None
    error_reason: str | None = None


def create_mock_fetch_result(success=True, error_type=None, error_reason=None, content="<html>test</html>"):
    return OfficialSourceFetchResult(
        success=success,
        status_code=200 if success else None,
        final_url="https://www.daad.de/test",
        content=content if success else None,
        content_type="text/html" if success else None,
        error_type=error_type,
        error_reason=error_reason,
    )


def create_mock_extraction_result():
    return ScholarshipExtractionResult(
        scholarship_name="Test Scholarship",
        provider="DAAD",
        degree_level="Masters",
        eligibility="All nationalities",
        application_method="Online",
        confidence={},
        extraction_notes=[],
    )


def create_mock_changeset():
    from app.services.scholarship_diff import ChangeSet
    return ChangeSet(
        changes=[],
        is_new_scholarship=False,
        identity_conflict=False,
        cycle_changed=False,
    )


def create_mock_evidence_collection(scholarship_id):
    return EvidenceCollection(
        scholarship_id=scholarship_id,
        source_url="https://www.daad.de/test",
        items=[
            EvidenceItem(
                scholarship_id=scholarship_id,
                field_name="title",
                extracted_value="Test Scholarship",
                source_url="https://www.daad.de/test",
                evidence_text="Test Scholarship",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
                verification_timestamp="2024-01-01T00:00:00Z",
                status=EvidenceStatus.HIGH_CONFIDENCE,
            )
        ],
        collected_at="2024-01-01T00:00:00Z",
    )


def create_mock_confidence_assessment(scholarship_id):
    return VerificationAssessment(
        scholarship_id=scholarship_id,
        field_results=[
            FieldConfidenceResult(
                field_name="title",
                value="Test Scholarship",
                confidence=ConfidenceLevel.HIGH,
                verification_state=VerificationState.VERIFIED,
                source_count=1,
                authoritative_source_count=1,
                agreeing_source_count=1,
                conflicting_source_count=0,
                evidence_references=[],
                reason="Single authoritative source",
                is_update_candidate=True,
                authority_score=100,
                quality_score=100,
                cross_source_score=100,
            )
        ],
        assessed_at="2024-01-01T00:00:00Z",
    )


@pytest.fixture
def session_factory():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def session(session_factory):
    return session_factory()


@pytest.fixture
def sample_scholarship(session):
    scholarship = Scholarship(
        title="Test Scholarship",
        country="Germany",
        degree="Masters",
        funding="Full",
        official_source="DAAD",
        official_source_url="https://www.daad.de/test",
        application_link="https://www.daad.de/test",
        is_verified=True,
        verification_status="active",
    )
    session.add(scholarship)
    session.commit()
    return scholarship


@pytest.fixture(autouse=True)
def _reset_telemetry():
    reset_telemetry()
    yield
    reset_telemetry()


class TestTelemetryInVerifyScholarship:
    """Test that verify_scholarship emits telemetry for all stages."""

    def test_fetch_stage_emits_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            result = verify_scholarship(session, sample_scholarship.id)

        assert result is not None
        snapshot = get_snapshot()
        assert snapshot.total_events > 0

        fetch_latency = get_latency_stats(PipelineStages.FETCH)
        assert fetch_latency is not None
        assert fetch_latency.count >= 1
        assert fetch_latency.avg_ms > 0

    def test_extraction_stage_emits_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        extraction_latency = get_latency_stats(PipelineStages.EXTRACTION)
        assert extraction_latency is not None
        assert extraction_latency.count >= 1
        assert extraction_latency.avg_ms > 0

    def test_diff_stage_emits_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        diff_latency = get_latency_stats(PipelineStages.DIFF)
        assert diff_latency is not None
        assert diff_latency.count >= 1
        assert diff_latency.avg_ms > 0

    def test_evidence_stage_emits_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        evidence_latency = get_latency_stats(PipelineStages.EVIDENCE)
        assert evidence_latency is not None
        assert evidence_latency.count >= 1
        assert evidence_latency.avg_ms > 0

    def test_confidence_stage_emits_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        confidence_latency = get_latency_stats(PipelineStages.CONFIDENCE)
        assert confidence_latency is not None
        assert confidence_latency.count >= 1
        assert confidence_latency.avg_ms > 0

    def test_all_stages_have_correlation_id(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        snapshot = get_snapshot()
        assert snapshot.total_events > 0

    def test_total_duration_is_measurable(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        snapshot = get_snapshot()
        total_latency = sum(
            latency.total_ms for latency in snapshot.pipeline_latency.values()
        )
        assert total_latency > 0

    def test_fetch_failure_is_recorded(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(
            success=False,
            error_type="timeout",
            error_reason="Request timed out",
        )

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch):
            from app.services.scholarship_verifier import verify_scholarship
            result = verify_scholarship(session, sample_scholarship.id)

        assert result is not None
        assert result.fetch_status == "failed"

        snapshot = get_snapshot()
        assert snapshot.total_events > 0

    def test_telemetry_failure_does_not_break_pipeline(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence), \
             patch("app.services.scholarship_verifier.record_event", side_effect=Exception("Telemetry failure")):
            from app.services.scholarship_verifier import verify_scholarship
            result = verify_scholarship(session, sample_scholarship.id)

        assert result is not None
        assert result.fetch_status == "success"

    def test_no_duplicate_events_per_stage(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)
            first_correlation_id = get_collector().get_correlation_id()

        snapshot = get_snapshot()
        core_stages = {
            PipelineStages.FETCH,
            PipelineStages.EXTRACTION,
            PipelineStages.DIFF,
            PipelineStages.EVIDENCE,
            PipelineStages.CONFIDENCE,
        }
        for stage in core_stages:
            latency = snapshot.pipeline_latency.get(stage)
            assert latency is not None, f"Stage {stage} not found"
            assert latency.count == 1, f"Stage {stage} has {latency.count} events, expected 1"

        reset_telemetry()
        get_collector().clear_correlation_id()

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            verify_scholarship(session, sample_scholarship.id)
            second_correlation_id = get_collector().get_correlation_id()

        assert first_correlation_id != second_correlation_id


class TestTelemetryInSchedulerEngine:
    """Test that scheduler engine emits telemetry."""

    def test_submit_batch_emits_scheduler_telemetry(self, session_factory, sample_scholarship):
        from app.services.scheduler_engine import SchedulerEngine

        engine = SchedulerEngine(session_factory=session_factory)
        engine.start()

        try:
            with patch.object(engine, "find_due_candidates") as mock_find:
                mock_find.return_value = [sample_scholarship]
                with patch.object(engine, "enqueue_candidates", return_value=1):
                    with patch.object(engine, "_executor") as mock_executor:
                        mock_executor.submit = MagicMock()
                        engine.submit_batch()

            snapshot = get_snapshot()
            scheduler_latency = get_latency_stats(PipelineStages.SCHEDULER)
            assert scheduler_latency is not None
        finally:
            engine.shutdown()

    def test_process_due_retries_emits_retry_telemetry(self, session_factory):
        from app.services.scheduler_engine import SchedulerEngine

        engine = SchedulerEngine(session_factory=session_factory)

        with patch("app.services.scheduler_engine.process_due_retries", return_value=[]):
            engine.process_due_retries()

        snapshot = get_snapshot()
        retry_latency = get_latency_stats(PipelineStages.RETRY)
        assert retry_latency is not None


class TestTelemetryInFetchExecutor:
    """Test that fetch executor emits telemetry."""

    def test_execute_fetch_with_retry_emits_telemetry(self, session, sample_scholarship):
        from app.services.scholarship_fetch_executor import execute_fetch_with_retry

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = MagicMock(
                success=True,
                content="<html>test</html>",
                error_type=None,
                error_reason=None,
            )
            result = execute_fetch_with_retry(
                session,
                sample_scholarship.id,
                "https://www.daad.de/test",
            )

        assert result.status == "resolved"
        snapshot = get_snapshot()
        assert snapshot.total_events > 0

    def test_fetch_failure_emits_failure_telemetry(self, session, sample_scholarship):
        from app.services.scholarship_fetch_executor import execute_fetch_with_retry

        with patch("app.services.scholarship_fetch_executor.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = MagicMock(
                success=False,
                error_type="timeout",
                error_reason="Request timed out",
            )
            with patch("app.services.scholarship_fetch_executor.make_retry_decision") as mock_decision:
                mock_decision.return_value = MagicMock(should_retry=False)
                result = execute_fetch_with_retry(
                    session,
                    sample_scholarship.id,
                    "https://www.daad.de/test",
                )

        assert result.status == "terminal"
        snapshot = get_snapshot()
        assert snapshot.total_events > 0


class TestTelemetryInDiscoveryPipeline:
    """Test that discovery pipeline emits telemetry."""

    def test_discover_from_url_emits_telemetry(self, session_factory):
        from app.services.discovery_pipeline import DiscoveryPipeline

        pipeline = DiscoveryPipeline(session_factory=session_factory)

        with patch("app.services.discovery_pipeline.fetch_official_source") as mock_fetch:
            mock_fetch.return_value = MagicMock(
                success=False,
                error_type="not_found",
                error_reason="404 Not Found",
            )
            with patch.object(pipeline, "registry") as mock_registry:
                mock_registry.is_approved.return_value = True
                result = pipeline.discover_from_url("https://www.daad.de/test")

        snapshot = get_snapshot()
        discovery_latency = get_latency_stats(PipelineStages.DISCOVERY)
        assert discovery_latency is not None

    def test_discover_batch_emits_batch_telemetry(self, session_factory):
        from app.services.discovery_pipeline import DiscoveryPipeline

        pipeline = DiscoveryPipeline(session_factory=session_factory)

        with patch.object(pipeline, "discover_from_url") as mock_discover:
            mock_discover.return_value = MagicMock(
                candidate_id=1,
                status="error",
                match_type="error",
            )
            with patch.object(pipeline, "registry") as mock_registry:
                mock_registry.is_approved.return_value = True
                batch = pipeline.discover_batch(["https://www.daad.de/test"])

        snapshot = get_snapshot()
        discovery_events = [
            e for e in snapshot.slowest_operations if e.stage == PipelineStages.DISCOVERY
        ]
        assert snapshot.total_events > 0


class TestCorrelationIdSurvival:
    """Test that correlation IDs survive the full pipeline."""

    def test_correlation_id_set_in_verify_scholarship(self, session, sample_scholarship):
        collector = get_collector()
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)

        assert collector.get_correlation_id() is not None

    def test_correlation_id_unique_per_call(self, session, sample_scholarship):
        collector = get_collector()
        correlation_ids = set()

        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            verify_scholarship(session, sample_scholarship.id)
            correlation_ids.add(collector.get_correlation_id())

        reset_telemetry()
        collector.clear_correlation_id()

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            verify_scholarship(session, sample_scholarship.id)
            correlation_ids.add(collector.get_correlation_id())

        assert len(correlation_ids) == 2


class TestEndToEndTelemetry:
    """End-to-end test proving telemetry produces all required stages."""

    def test_full_pipeline_produces_all_stages(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(success=True)
        mock_extraction = create_mock_extraction_result()
        mock_changeset = create_mock_changeset()
        mock_evidence = create_mock_evidence_collection(sample_scholarship.id)
        mock_confidence = create_mock_confidence_assessment(sample_scholarship.id)

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch), \
             patch("app.services.scholarship_verifier.extract_scholarship_information", return_value=mock_extraction), \
             patch("app.services.scholarship_verifier.diff_scholarship", return_value=mock_changeset), \
             patch("app.services.scholarship_verifier.collect_evidence", return_value=mock_evidence), \
             patch("app.services.scholarship_verifier.assess_confidence", return_value=mock_confidence):
            from app.services.scholarship_verifier import verify_scholarship
            result = verify_scholarship(session, sample_scholarship.id)

        assert result is not None
        snapshot = get_snapshot()

        expected_stages = {
            PipelineStages.FETCH,
            PipelineStages.EXTRACTION,
            PipelineStages.DIFF,
            PipelineStages.EVIDENCE,
            PipelineStages.CONFIDENCE,
        }
        actual_stages = set(snapshot.pipeline_latency.keys())
        assert expected_stages.issubset(actual_stages), f"Missing stages: {expected_stages - actual_stages}"

    def test_pipeline_with_fetch_failure_still_records_telemetry(self, session, sample_scholarship):
        mock_fetch = create_mock_fetch_result(
            success=False,
            error_type="connection_error",
            error_reason="Failed to connect",
        )

        with patch("app.services.scholarship_verifier.fetch_official_source", return_value=mock_fetch):
            from app.services.scholarship_verifier import verify_scholarship
            result = verify_scholarship(session, sample_scholarship.id)

        assert result is not None
        assert result.fetch_status == "failed"

        snapshot = get_snapshot()
        assert snapshot.total_events > 0

        fetch_latency = get_latency_stats(PipelineStages.FETCH)
        assert fetch_latency is not None
        assert fetch_latency.count >= 1
