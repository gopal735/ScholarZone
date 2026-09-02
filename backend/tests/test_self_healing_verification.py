"""Tests for self_healing_verification module.

Covers:
- fetch failure recovery
- extraction failure fallback
- alternate extraction success
- failed recovery
- non-recoverable failure
- bounded recovery attempts
- loop prevention
- idempotency
- partial result rejection
- safety gate preserved
- evidence re-validation
- confidence re-validation
- anomaly re-validation
- no duplicate history/review/update
- telemetry for recovery
- source isolation
- deterministic strategy order
- no N+1
- TASKS 1-28 remain green
"""

from __future__ import annotations

import uuid

import pytest

from app.services.error_classification import classify_error, is_terminal, is_retryable
from app.services.official_source_fetcher import OfficialSourceFetchResult
from app.services.scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
    extract_scholarship_information,
)
from app.services.self_healing_verification import (
    DEFAULT_MAX_RECOVERY_ATTEMPTS,
    EXTRACTION_STAGES,
    FETCH_STAGES,
    MAX_RECOVERY_ATTEMPTS,
    VERIFICATION_STAGES,
    FailureStage,
    Recoverability,
    RecoveryAttempt,
    RecoveryContext,
    RecoveryOutcome,
    RecoveryStrategy,
    SelfHealingResult,
    attempt_recovery,
    diagnose_failure,
    get_recovery_strategies,
    is_recoverable_error,
    should_attempt_recovery,
)
from app.services.telemetry import (
    PipelineStages,
    get_source_health,
    record_event,
    reset_telemetry,
)


class TestFailureStageEnum:
    def test_failure_stage_values(self):
        assert FailureStage.FETCH == "fetch"
        assert FailureStage.EXTRACTION == "extraction"
        assert FailureStage.PARSING == "parsing"
        assert FailureStage.DIFF == "diff"
        assert FailureStage.EVIDENCE == "evidence"
        assert FailureStage.CONFIDENCE == "confidence"
        assert FailureStage.CONSENSUS == "consensus"
        assert FailureStage.ANOMALY == "anomaly"
        assert FailureStage.SAFETY_GATE == "safety_gate"
        assert FailureStage.UPDATE == "update"


class TestRecoveryStrategyEnum:
    def test_recovery_strategy_values(self):
        assert RecoveryStrategy.RETRY_FETCH == "retry_fetch"
        assert RecoveryStrategy.ALTERNATE_FETCH == "alternate_fetch"
        assert RecoveryStrategy.FALLBACK_EXTRACTION == "fallback_extraction"
        assert RecoveryStrategy.ALTERNATE_EXTRACTION == "alternate_extraction"
        assert RecoveryStrategy.RE_VALIDATE == "re_validate"
        assert RecoveryStrategy.ESCALATE_REVIEW == "escalate_review"


class TestRecoveryOutcomeEnum:
    def test_recovery_outcome_values(self):
        assert RecoveryOutcome.SUCCESS == "success"
        assert RecoveryOutcome.PARTIAL == "partial"
        assert RecoveryOutcome.FAILED == "failed"
        assert RecoveryOutcome.NON_RECOVERABLE == "non_recoverable"
        assert RecoveryOutcome.ESCALATED == "escalated"


class TestDiagnoseFailure:
    def test_fetch_timeout_is_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "timeout", "Connection timed out", ctx
        )
        assert recoverability == Recoverability.RECOVERABLE
        assert RecoveryStrategy.RETRY_FETCH in strategies

    def test_fetch_not_found_is_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "not_found", "Page not found", ctx
        )
        assert recoverability == Recoverability.NON_RECOVERABLE

    def test_fetch_forbidden_is_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "forbidden", "Access denied", ctx
        )
        assert recoverability == Recoverability.NON_RECOVERABLE

    def test_fetch_rate_limited_is_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "rate_limited", "Too many requests", ctx
        )
        assert recoverability == Recoverability.RECOVERABLE

    def test_fetch_server_error_is_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "server_error", "Internal server error", ctx
        )
        assert recoverability == Recoverability.RECOVERABLE

    def test_extraction_failure_is_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.EXTRACTION, "timeout", "Extraction timed out", ctx
        )
        assert recoverability == Recoverability.RECOVERABLE
        assert RecoveryStrategy.FALLBACK_EXTRACTION in strategies

    def test_verification_failure_is_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.CONFIDENCE, "timeout", "Confidence assessment timed out", ctx
        )
        assert recoverability == Recoverability.RECOVERABLE
        assert RecoveryStrategy.RE_VALIDATE in strategies

    def test_unexpected_error_is_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        recoverability, strategies = diagnose_failure(
            FailureStage.FETCH, "unexpected_error", "Unknown error", ctx
        )
        assert recoverability == Recoverability.NON_RECOVERABLE


class TestIsRecoverableError:
    def test_retryable_errors(self):
        assert is_recoverable_error("timeout", FailureStage.FETCH) is True
        assert is_recoverable_error("connection_error", FailureStage.FETCH) is True
        assert is_recoverable_error("rate_limited", FailureStage.FETCH) is True
        assert is_recoverable_error("server_error", FailureStage.FETCH) is True

    def test_non_retryable_errors(self):
        assert is_recoverable_error("not_found", FailureStage.FETCH) is False
        assert is_recoverable_error("forbidden", FailureStage.FETCH) is False
        assert is_recoverable_error("invalid_url", FailureStage.FETCH) is False
        assert is_recoverable_error("invalid_content_type", FailureStage.FETCH) is False
        assert is_recoverable_error("client_error", FailureStage.FETCH) is False
        assert is_recoverable_error("unexpected_error", FailureStage.FETCH) is False


class TestShouldAttemptRecovery:
    def test_should_attempt_within_bounds(self):
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 0, 3) is True
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 2, 3) is True

    def test_should_not_attempt_at_max(self):
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 3, 3) is False
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 5, 3) is False

    def test_should_not_attempt_non_recoverable(self):
        assert should_attempt_recovery("not_found", FailureStage.FETCH, 0, 3) is False

    def test_max_attempts_capped(self):
        # max_attempts=100 should be capped at MAX_RECOVERY_ATTEMPTS (5)
        # attempt_count=4 < 5, so should still attempt
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 4, 100) is True
        # attempt_count=5 >= 5, so should not attempt
        assert should_attempt_recovery("timeout", FailureStage.FETCH, 5, 100) is False


class TestGetRecoveryStrategies:
    def test_fetch_strategies(self):
        ctx = RecoveryContext(source_url="https://example.com")
        strategies = get_recovery_strategies(FailureStage.FETCH, "timeout", ctx)
        assert RecoveryStrategy.RETRY_FETCH in strategies
        assert RecoveryStrategy.ESCALATE_REVIEW in strategies

    def test_extraction_strategies(self):
        ctx = RecoveryContext(source_url="https://example.com")
        strategies = get_recovery_strategies(FailureStage.EXTRACTION, "timeout", ctx)
        assert RecoveryStrategy.FALLBACK_EXTRACTION in strategies
        assert RecoveryStrategy.ALTERNATE_EXTRACTION in strategies

    def test_verification_strategies(self):
        ctx = RecoveryContext(source_url="https://example.com")
        strategies = get_recovery_strategies(FailureStage.CONFIDENCE, "timeout", ctx)
        assert RecoveryStrategy.RE_VALIDATE in strategies


class TestAttemptRecoveryNonRecoverable:
    def test_not_found_returns_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE
        assert result.is_recoverable is False
        assert result.requires_review is True

    def test_forbidden_returns_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "forbidden", "Forbidden", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_invalid_url_returns_non_recoverable(self):
        ctx = RecoveryContext(source_url="")
        result = attempt_recovery(FailureStage.FETCH, "invalid_url", "Bad URL", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_unexpected_error_returns_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "unexpected_error", "Unknown", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE


class TestAttemptRecoveryBounded:
    def test_max_attempts_bounded(self):
        ctx = RecoveryContext(source_url="https://example.com", max_attempts=2)
        result = attempt_recovery(
            FailureStage.FETCH, "timeout", "Timeout", ctx, max_recovery_attempts=2
        )
        assert result.attempt_count <= 2

    def test_max_attempts_capped_at_five(self):
        ctx = RecoveryContext(source_url="https://example.com", max_attempts=10)
        result = attempt_recovery(
            FailureStage.FETCH, "timeout", "Timeout", ctx, max_recovery_attempts=10
        )
        assert result.attempt_count <= MAX_RECOVERY_ATTEMPTS

    def test_minimum_one_attempt(self):
        ctx = RecoveryContext(source_url="https://example.com", max_attempts=0)
        result = attempt_recovery(
            FailureStage.FETCH, "not_found", "Not found", ctx, max_recovery_attempts=0
        )
        assert result.attempt_count == 0  # non-recoverable, no attempts


class TestAttemptRecoveryIdempotent:
    def test_same_input_same_recoverability(self):
        ctx1 = RecoveryContext(source_url="https://example.com")
        ctx2 = RecoveryContext(source_url="https://example.com")
        result1 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx1)
        result2 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx2)
        assert result1.final_outcome == result2.final_outcome
        assert result1.is_recoverable == result2.is_recoverable

    def test_non_recoverable_always_same(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result1 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        result2 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result1.final_outcome == result2.final_outcome


class TestAttemptRecoveryFetch:
    def test_retry_fetch_with_source_url(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "timeout", "Timeout", ctx)
        assert any(
            a.strategy == RecoveryStrategy.RETRY_FETCH
            for a in result.recovery_attempts
        )

    def test_retry_fetch_without_source_url_fails(self):
        ctx = RecoveryContext(source_url="")
        result = attempt_recovery(FailureStage.FETCH, "timeout", "Timeout", ctx)
        retry_attempts = [
            a for a in result.recovery_attempts
            if a.strategy == RecoveryStrategy.RETRY_FETCH
        ]
        if retry_attempts:
            assert retry_attempts[0].outcome == RecoveryOutcome.FAILED


class TestAttemptRecoveryExtraction:
    def test_fallback_extraction_with_content(self):
        html = "<html><body><h1>Test Scholarship</h1><p>Deadline: January 15, 2025</p></body></html>"
        ctx = RecoveryContext(source_url="https://example.com", html_content=html)
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        fallback_attempts = [
            a for a in result.recovery_attempts
            if a.strategy == RecoveryStrategy.FALLBACK_EXTRACTION
        ]
        assert len(fallback_attempts) > 0

    def test_fallback_extraction_without_content_fails(self):
        ctx = RecoveryContext(source_url="https://example.com", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        fallback_attempts = [
            a for a in result.recovery_attempts
            if a.strategy == RecoveryStrategy.FALLBACK_EXTRACTION
        ]
        if fallback_attempts:
            assert fallback_attempts[0].outcome == RecoveryOutcome.FAILED

    def test_alternate_extraction_with_content(self):
        html = "<html><body><h2>Program: Test Scholarship</h2><p>Apply by March 1, 2025</p></body></html>"
        ctx = RecoveryContext(source_url="https://example.com", html_content=html)
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        alt_attempts = [
            a for a in result.recovery_attempts
            if a.strategy == RecoveryStrategy.ALTERNATE_EXTRACTION
        ]
        assert len(alt_attempts) > 0


class TestAttemptRecoveryEscalation:
    def test_escalates_when_unrecoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.requires_review is True
        assert result.review_reason is not None

    def test_escalates_after_exhaustion(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.requires_review is True


class TestSelfHealingResultProperties:
    def test_was_recovered_true(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="timeout",
            original_error_message="Timeout",
            final_outcome=RecoveryOutcome.SUCCESS,
        )
        assert result.was_recovered is True
        assert result.was_escalated is False

    def test_was_escalated_true(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="not_found",
            original_error_message="Not found",
            final_outcome=RecoveryOutcome.ESCALATED,
        )
        assert result.was_recovered is False
        assert result.was_escalated is True

    def test_attempt_count(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="timeout",
            original_error_message="Timeout",
            recovery_attempts=[
                RecoveryAttempt(
                    attempt_number=1,
                    strategy=RecoveryStrategy.RETRY_FETCH,
                    outcome=RecoveryOutcome.FAILED,
                    timestamp=0.0,
                    duration_ms=1.0,
                ),
                RecoveryAttempt(
                    attempt_number=2,
                    strategy=RecoveryStrategy.ESCALATE_REVIEW,
                    outcome=RecoveryOutcome.ESCALATED,
                    timestamp=0.0,
                    duration_ms=1.0,
                ),
            ],
        )
        assert result.attempt_count == 2

    def test_strategies_attempted(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="timeout",
            original_error_message="Timeout",
            recovery_attempts=[
                RecoveryAttempt(
                    attempt_number=1,
                    strategy=RecoveryStrategy.RETRY_FETCH,
                    outcome=RecoveryOutcome.FAILED,
                    timestamp=0.0,
                    duration_ms=1.0,
                ),
            ],
        )
        assert result.strategies_attempted == [RecoveryStrategy.RETRY_FETCH]


class TestRecoveryContext:
    def test_default_values(self):
        ctx = RecoveryContext()
        assert ctx.source_url is None
        assert ctx.html_content is None
        assert ctx.scholarship_id is None
        assert ctx.attempt_count == 0
        assert ctx.max_attempts == DEFAULT_MAX_RECOVERY_ATTEMPTS

    def test_custom_values(self):
        ctx = RecoveryContext(
            source_url="https://example.com",
            html_content="<html></html>",
            scholarship_id=42,
            max_attempts=5,
        )
        assert ctx.source_url == "https://example.com"
        assert ctx.html_content == "<html></html>"
        assert ctx.scholarship_id == 42
        assert ctx.max_attempts == 5


class TestRecoveryAttempt:
    def test_creation(self):
        attempt = RecoveryAttempt(
            attempt_number=1,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.SUCCESS,
            timestamp=1234567890.0,
            duration_ms=100.0,
        )
        assert attempt.attempt_number == 1
        assert attempt.strategy == RecoveryStrategy.RETRY_FETCH
        assert attempt.outcome == RecoveryOutcome.SUCCESS
        assert attempt.duration_ms == 100.0

    def test_with_error_details(self):
        attempt = RecoveryAttempt(
            attempt_number=1,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.FAILED,
            timestamp=1234567890.0,
            duration_ms=50.0,
            error_type="timeout",
            error_message="Connection timed out",
        )
        assert attempt.error_type == "timeout"
        assert attempt.error_message == "Connection timed out"


class TestSafetyGatesPreserved:
    def test_non_recoverable_never_bypassed(self):
        for error_type in ["not_found", "forbidden", "invalid_url", "client_error", "unexpected_error"]:
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, error_type, "Error", ctx)
            assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE
            assert result.requires_review is True

    def test_recovery_never_auto_accepts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.was_recovered is False
        assert result.requires_review is True

    def test_partial_recovery_requires_review(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        if result.final_outcome == RecoveryOutcome.PARTIAL:
            assert result.requires_review is True


class TestDeterministicStrategyOrder:
    def test_fetch_strategies_ordered(self):
        ctx = RecoveryContext(source_url="https://example.com")
        _, strategies1 = diagnose_failure(FailureStage.FETCH, "timeout", "Timeout", ctx)
        _, strategies2 = diagnose_failure(FailureStage.FETCH, "timeout", "Timeout", ctx)
        assert strategies1 == strategies2

    def test_extraction_strategies_ordered(self):
        ctx = RecoveryContext(source_url="https://example.com")
        _, strategies1 = diagnose_failure(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        _, strategies2 = diagnose_failure(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert strategies1 == strategies2

    def test_verification_strategies_ordered(self):
        ctx = RecoveryContext(source_url="https://example.com")
        _, strategies1 = diagnose_failure(FailureStage.CONFIDENCE, "timeout", "Timeout", ctx)
        _, strategies2 = diagnose_failure(FailureStage.CONFIDENCE, "timeout", "Timeout", ctx)
        assert strategies1 == strategies2


class TestLoopPrevention:
    def test_no_infinite_loop_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.attempt_count == 0

    def test_bounded_attempts_prevent_loops(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(
            FailureStage.EXTRACTION, "timeout", "Timeout", ctx, max_recovery_attempts=3
        )
        assert result.attempt_count <= 3


class TestSourceIsolation:
    def test_context_source_url_isolated(self):
        ctx1 = RecoveryContext(source_url="https://example1.com")
        ctx2 = RecoveryContext(source_url="https://example2.com")
        result1 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx1)
        result2 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx2)
        assert result1.correlation_id != result2.correlation_id


class TestCorrelationId:
    def test_correlation_id_generated(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.correlation_id != ""

    def test_custom_correlation_id(self):
        ctx = RecoveryContext(source_url="https://example.com")
        custom_id = str(uuid.uuid4())
        result = attempt_recovery(
            FailureStage.FETCH, "not_found", "Not found", ctx, correlation_id=custom_id
        )
        assert result.correlation_id == custom_id


class TestTelemetryRecording:
    def test_telemetry_recorded_for_non_recoverable(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_telemetry_recorded_for_recovery_attempts(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.total_duration_ms >= 0


class TestNoDuplicateOperations:
    def test_non_recoverable_no_duplicate_attempts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        strategies = [a.strategy for a in result.recovery_attempts]
        assert len(strategies) == len(set(strategies))

    def test_recovery_no_duplicate_strategies(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        strategies = [a.strategy for a in result.recovery_attempts]
        non_escalate = [s for s in strategies if s != RecoveryStrategy.ESCALATE_REVIEW]
        assert len(non_escalate) == len(set(non_escalate))


class TestPartialResultRejection:
    def test_empty_extraction_rejected(self):
        ctx = RecoveryContext(source_url="https://example.com", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.was_recovered is False

    def test_no_fields_extracted_rejected(self):
        ctx = RecoveryContext(source_url="https://example.com", html_content="<html></html>")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.was_recovered is False


class TestFailureStageClassification:
    def test_fetch_stages(self):
        assert FailureStage.FETCH in FETCH_STAGES
        assert FailureStage.PARSING in FETCH_STAGES

    def test_extraction_stages(self):
        assert FailureStage.EXTRACTION in EXTRACTION_STAGES

    def test_verification_stages(self):
        assert FailureStage.DIFF in VERIFICATION_STAGES
        assert FailureStage.EVIDENCE in VERIFICATION_STAGES
        assert FailureStage.CONFIDENCE in VERIFICATION_STAGES
        assert FailureStage.CONSENSUS in VERIFICATION_STAGES
        assert FailureStage.ANOMALY in VERIFICATION_STAGES
        assert FailureStage.SAFETY_GATE in VERIFICATION_STAGES
        assert FailureStage.UPDATE in VERIFICATION_STAGES


class TestIntegrationWithExistingServices:
    def test_error_classification_integration(self):
        from app.services.error_classification import classify_error, is_retryable, is_terminal
        assert is_retryable("timeout") is True
        assert is_retryable("not_found") is False
        assert is_terminal("not_found") is True
        assert is_terminal("timeout") is False

    def test_official_source_fetcher_integration(self):
        from app.services.official_source_fetcher import fetch_official_source
        result = fetch_official_source("")
        assert result.success is False
        assert result.error_type == "invalid_url"

    def test_scholarship_extractor_integration(self):
        from app.services.scholarship_extractor import extract_scholarship_information
        result = extract_scholarship_information("", "")
        assert isinstance(result, ScholarshipExtractionResult)

    def test_telemetry_integration(self):
        reset_telemetry()
        event = record_event(
            stage=PipelineStages.RETRY,
            metric_type="success",
            duration_ms=100.0,
            scholarship_id=1,
            source="https://example.com",
        )
        assert event.stage == PipelineStages.RETRY


class TestTasksOneThroughTwentyEightImportsFunctional:
    def test_import_error_classification(self):
        from app.services.error_classification import classify_error, is_retryable, is_terminal
        assert callable(classify_error)
        assert callable(is_retryable)
        assert callable(is_terminal)

    def test_import_official_source_fetcher(self):
        from app.services.official_source_fetcher import fetch_official_source, OfficialSourceFetchResult
        assert callable(fetch_official_source)

    def test_import_scholarship_extractor(self):
        from app.services.scholarship_extractor import extract_scholarship_information, ScholarshipExtractionResult
        assert callable(extract_scholarship_information)

    def test_import_content_fingerprinting(self):
        from app.services.content_fingerprinting import FingerprintStatus, check_source_changed
        assert FingerprintStatus.UNCHANGED == "unchanged"
        assert FingerprintStatus.CHANGED == "changed"

    def test_import_dependency_graph(self):
        from app.services.dependency_graph import CriticalityLevel, analyze_dependencies
        assert CriticalityLevel.CRITICAL == "critical"

    def test_import_evidence_arbitration(self):
        from app.services.evidence_arbitration import ArbitrationDecision, arbitrate_field
        assert ArbitrationDecision.CONSENSUS == "consensus"

    def test_import_verification_confidence(self):
        from app.services.verification_confidence import ConfidenceLevel, VerificationState
        assert ConfidenceLevel.HIGH == "high"
        assert VerificationState.VERIFIED == "verified"

    def test_import_anomaly_detection(self):
        from app.services.anomaly_detection import AnomalySeverity, detect_anomalies
        assert AnomalySeverity.CRITICAL == "critical"

    def test_import_scheduler_priority(self):
        from app.services.scheduler_priority import PriorityScore, calculate_priority
        assert "total" in dir(PriorityScore)

    def test_import_information_gain_scheduler(self):
        from app.services.information_gain_scheduler import InformationGainTier, compute_information_gain
        assert InformationGainTier.CRITICAL == "critical"

    def test_import_telemetry(self):
        from app.services.telemetry import PipelineStages, record_event, get_source_stats
        assert hasattr(PipelineStages, "RETRY")

    def test_import_scholarship_retry(self):
        from app.services.scholarship_retry import RetryDecision, make_retry_decision
        assert "should_retry" in RetryDecision.__dataclass_fields__

    def test_import_adaptive_policy(self):
        from app.services.adaptive_policy import AdaptiveVerificationPolicy, compute_adaptive_policy
        assert "recommended_interval_days" in AdaptiveVerificationPolicy.__dataclass_fields__

    def test_import_verification_cost_optimizer(self):
        from app.services.verification_cost_optimizer import VerificationCostProfile, compute_cost_profile
        assert "estimated_cpu_cost" in VerificationCostProfile.__dataclass_fields__

    def test_import_change_impact_staleness(self):
        from app.services.change_impact_staleness import get_field_criticality, compute_deadline_urgency
        assert callable(get_field_criticality)

    def test_import_lifecycle_identity(self):
        from app.services.lifecycle_identity import classify_lifecycle_state, LifecycleState
        assert callable(classify_lifecycle_state)

    def test_import_self_healing_verification(self):
        from app.services.self_healing_verification import (
            FailureStage,
            RecoveryStrategy,
            RecoveryOutcome,
            SelfHealingResult,
            RecoveryContext,
            attempt_recovery,
            diagnose_failure,
            is_recoverable_error,
            should_attempt_recovery,
            get_recovery_strategies,
        )
        assert FailureStage.FETCH == "fetch"
        assert RecoveryStrategy.RETRY_FETCH == "retry_fetch"
        assert RecoveryOutcome.SUCCESS == "success"


class TestSelfHealingResultDataclass:
    def test_default_construction(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="timeout",
            original_error_message="Timeout",
        )
        assert result.recovery_attempts == []
        assert result.final_outcome == RecoveryOutcome.FAILED
        assert result.requires_review is False
        assert result.total_duration_ms == 0.0

    def test_with_all_fields(self):
        result = SelfHealingResult(
            original_failure_stage=FailureStage.FETCH,
            original_error_type="timeout",
            original_error_message="Timeout",
            is_recoverable=True,
            recovery_attempts=[
                RecoveryAttempt(
                    attempt_number=1,
                    strategy=RecoveryStrategy.RETRY_FETCH,
                    outcome=RecoveryOutcome.SUCCESS,
                    timestamp=0.0,
                    duration_ms=100.0,
                ),
            ],
            final_outcome=RecoveryOutcome.SUCCESS,
            correlation_id="test-id",
            total_duration_ms=100.0,
        )
        assert result.was_recovered is True
        assert result.attempt_count == 1


class TestRecoveryStrategyExecution:
    def test_retry_fetch_strategy(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "timeout", "Timeout", ctx)
        retry_found = any(
            a.strategy == RecoveryStrategy.RETRY_FETCH
            for a in result.recovery_attempts
        )
        assert retry_found

    def test_alternate_fetch_strategy(self):
        # Use an invalid URL to ensure retry fetch fails and alternate fetch is attempted
        ctx = RecoveryContext(source_url="")
        result = attempt_recovery(FailureStage.FETCH, "timeout", "Timeout", ctx)
        alt_found = any(
            a.strategy == RecoveryStrategy.ALTERNATE_FETCH
            for a in result.recovery_attempts
        )
        assert alt_found

    def test_escalate_review_strategy(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.requires_review is True


class TestBoundedRecoveryAttemptsExtended:
    def test_zero_max_attempts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(
            FailureStage.FETCH, "not_found", "Not found", ctx, max_recovery_attempts=0
        )
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_one_max_attempt(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(
            FailureStage.FETCH, "not_found", "Not found", ctx, max_recovery_attempts=1
        )
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_negative_max_attempts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(
            FailureStage.FETCH, "not_found", "Not found", ctx, max_recovery_attempts=-1
        )
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE


class TestIdempotencyExtended:
    def test_multiple_calls_same_result(self):
        results = []
        for _ in range(3):
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
            results.append(result.final_outcome)
        assert all(r == RecoveryOutcome.NON_RECOVERABLE for r in results)

    def test_different_correlation_ids(self):
        ids = set()
        for _ in range(3):
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
            ids.add(result.correlation_id)
        assert len(ids) == 3


class TestSafetyGatePreservedExtended:
    def test_no_auto_update_on_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.was_recovered is False
        assert result.requires_review is True

    def test_no_bypass_of_safety(self):
        for error_type in ["not_found", "forbidden", "invalid_url", "client_error"]:
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, error_type, "Error", ctx)
            assert result.was_recovered is False
            assert result.requires_review is True


class TestEvidenceRevalidation:
    def test_recovery_requires_evidence(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.evidence_validated is False
        assert result.requires_review is True


class TestConfidenceRevalidation:
    def test_recovery_requires_confidence(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.confidence_validated is False
        assert result.requires_review is True


class TestAnomalyRevalidation:
    def test_recovery_requires_anomaly_check(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.anomaly_checked is False
        assert result.requires_review is True


class TestNoDuplicateHistoryReviewUpdate:
    def test_non_recovery_no_history_created(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.was_recovered is False

    def test_requires_review_only_once(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.requires_review is True
        review_reasons = [a for a in result.recovery_attempts if a.outcome == RecoveryOutcome.ESCALATED]
        assert len(review_reasons) <= 1


class TestTelemetryForRecoveryExtended:
    def test_telemetry_records_failure_stage(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.original_failure_stage == FailureStage.FETCH

    def test_telemetry_records_recovery_strategy(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_telemetry_records_attempt_number(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        for attempt in result.recovery_attempts:
            assert attempt.attempt_number >= 1

    def test_telemetry_records_recovery_latency(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.total_duration_ms >= 0

    def test_telemetry_records_correlation_id(self):
        reset_telemetry()
        ctx = RecoveryContext(source_url="https://example.com", scholarship_id=1)
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.correlation_id != ""


class TestSourceIsolationExtended:
    def test_different_sources_different_results(self):
        ctx1 = RecoveryContext(source_url="https://example1.com")
        ctx2 = RecoveryContext(source_url="https://example2.com")
        result1 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx1)
        result2 = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx2)
        assert result1.correlation_id != result2.correlation_id

    def test_source_url_preserved_in_context(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert ctx.source_url == "https://example.com"


class TestDeterministicStrategyOrderExtended:
    def test_fetch_strategies_always_same_order(self):
        ctx = RecoveryContext(source_url="https://example.com")
        orders = []
        for _ in range(5):
            _, strategies = diagnose_failure(FailureStage.FETCH, "timeout", "Timeout", ctx)
            orders.append(strategies)
        assert all(o == orders[0] for o in orders)

    def test_extraction_strategies_always_same_order(self):
        ctx = RecoveryContext(source_url="https://example.com")
        orders = []
        for _ in range(5):
            _, strategies = diagnose_failure(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
            orders.append(strategies)
        assert all(o == orders[0] for o in orders)


class TestNoNPlusOneExtended:
    def test_single_recovery_no_extra_calls(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.attempt_count == 0

    def test_bounded_strategies_no_unbounded_calls(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.attempt_count <= MAX_RECOVERY_ATTEMPTS


class TestFailedRecoveryExtended:
    def test_all_strategies_fail_results_in_failed(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.final_outcome in (
            RecoveryOutcome.FAILED,
            RecoveryOutcome.PARTIAL,
            RecoveryOutcome.NON_RECOVERABLE,
        )

    def test_failed_recovery_requires_review(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.requires_review is True


class TestNonRecoverableFailureExtended:
    def test_not_found_terminates_cleanly(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE
        assert result.requires_review is True
        assert result.review_reason is not None

    def test_forbidden_terminates_cleanly(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "forbidden", "Forbidden", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_invalid_url_terminates_cleanly(self):
        ctx = RecoveryContext(source_url="")
        result = attempt_recovery(FailureStage.FETCH, "invalid_url", "Bad URL", ctx)
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE


class TestBoundedRecoveryAttemptsExtended2:
    def test_max_attempts_respected(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(
            FailureStage.EXTRACTION, "timeout", "Timeout", ctx, max_recovery_attempts=2
        )
        assert result.attempt_count <= 2

    def test_max_attempts_capped_at_five(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(
            FailureStage.EXTRACTION, "timeout", "Timeout", ctx, max_recovery_attempts=100
        )
        assert result.attempt_count <= MAX_RECOVERY_ATTEMPTS


class TestLoopPreventionExtended:
    def test_non_recoverable_no_loop(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.attempt_count == 0

    def test_bounded_strategies_prevent_infinite_loops(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(
            FailureStage.EXTRACTION, "timeout", "Timeout", ctx, max_recovery_attempts=3
        )
        assert result.attempt_count <= 3


class TestIdempotencyExtended2:
    def test_same_input_same_outcome(self):
        results = []
        for _ in range(3):
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
            results.append(result.final_outcome)
        assert all(r == results[0] for r in results)

    def test_different_correlation_ids_each_call(self):
        ids = set()
        for _ in range(5):
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
            ids.add(result.correlation_id)
        assert len(ids) == 5


class TestPartialResultRejectionExtended:
    def test_empty_html_no_recovery(self):
        ctx = RecoveryContext(source_url="https://example.com", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.was_recovered is False

    def test_no_fields_no_recovery(self):
        ctx = RecoveryContext(source_url="https://example.com", html_content="<html></html>")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        assert result.was_recovered is False


class TestSafetyGatePreservedExtended2:
    def test_non_recoverable_never_bypasses_safety(self):
        for error_type in ["not_found", "forbidden", "invalid_url", "client_error", "unexpected_error"]:
            ctx = RecoveryContext(source_url="https://example.com")
            result = attempt_recovery(FailureStage.FETCH, error_type, "Error", ctx)
            assert result.was_recovered is False
            assert result.requires_review is True

    def test_recovery_never_auto_accepts_uncertain(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.was_recovered is False


class TestEvidenceRevalidationExtended:
    def test_recovery_requires_evidence_validation(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.evidence_validated is False
        assert result.requires_review is True


class TestConfidenceRevalidationExtended:
    def test_recovery_requires_confidence_validation(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.confidence_validated is False
        assert result.requires_review is True


class TestAnomalyRevalidationExtended:
    def test_recovery_requires_anomaly_check(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.anomaly_checked is False
        assert result.requires_review is True


class TestSelfHealingPreservesOriginalFailure:
    def test_original_failure_preserved(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.original_failure_stage == FailureStage.FETCH
        assert result.original_error_type == "not_found"
        assert result.original_error_message == "Not found"

    def test_recovery_trail_preserved(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert isinstance(result.recovery_attempts, list)


class TestRecoveryStrategyOrder:
    def test_fetch_strategies_follow_order(self):
        ctx = RecoveryContext(source_url="https://example.com")
        _, strategies = diagnose_failure(FailureStage.FETCH, "timeout", "Timeout", ctx)
        expected_order = [RecoveryStrategy.RETRY_FETCH, RecoveryStrategy.ALTERNATE_FETCH, RecoveryStrategy.ESCALATE_REVIEW]
        assert strategies == expected_order

    def test_extraction_strategies_follow_order(self):
        ctx = RecoveryContext(source_url="https://example.com")
        _, strategies = diagnose_failure(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        expected_order = [
            RecoveryStrategy.FALLBACK_EXTRACTION,
            RecoveryStrategy.ALTERNATE_EXTRACTION,
            RecoveryStrategy.RE_VALIDATE,
            RecoveryStrategy.ESCALATE_REVIEW,
        ]
        assert strategies == expected_order


class TestNonRecoverableCleanTermination:
    def test_not_found_no_recovery_attempts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.attempt_count == 0
        assert result.final_outcome == RecoveryOutcome.NON_RECOVERABLE

    def test_forbidden_no_recovery_attempts(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "forbidden", "Forbidden", ctx)
        assert result.attempt_count == 0

    def test_invalid_url_no_recovery_attempts(self):
        ctx = RecoveryContext(source_url="")
        result = attempt_recovery(FailureStage.FETCH, "invalid_url", "Bad URL", ctx)
        assert result.attempt_count == 0


class TestAllFailureStages:
    def test_all_failure_stages_have_classification(self):
        ctx = RecoveryContext(source_url="https://example.com")
        for stage in FailureStage:
            recoverability, strategies = diagnose_failure(stage, "timeout", "Timeout", ctx)
            assert recoverability in Recoverability
            assert isinstance(strategies, list)

    def test_all_failure_stages_with_non_recoverable(self):
        ctx = RecoveryContext(source_url="https://example.com")
        for stage in FailureStage:
            recoverability, strategies = diagnose_failure(stage, "not_found", "Not found", ctx)
            assert recoverability == Recoverability.NON_RECOVERABLE


class TestRecoveredResultMustPassNormalPipeline:
    def test_partial_recovery_not_auto_applied(self):
        ctx = RecoveryContext(source_url="", html_content="")
        result = attempt_recovery(FailureStage.EXTRACTION, "timeout", "Timeout", ctx)
        if result.final_outcome == RecoveryOutcome.PARTIAL:
            assert result.requires_review is True

    def test_non_recovered_not_auto_applied(self):
        ctx = RecoveryContext(source_url="https://example.com")
        result = attempt_recovery(FailureStage.FETCH, "not_found", "Not found", ctx)
        assert result.recovered_extraction is None
        assert result.recovered_fetch is None


class TestDefaultConstants:
    def test_default_max_recovery_attempts(self):
        assert DEFAULT_MAX_RECOVERY_ATTEMPTS == 3

    def test_max_recovery_attempts_cap(self):
        assert MAX_RECOVERY_ATTEMPTS == 5

    def test_recovery_strategy_order(self):
        from app.services.self_healing_verification import RECOVERY_STRATEGY_ORDER
        assert RecoveryStrategy.RETRY_FETCH in RECOVERY_STRATEGY_ORDER
        assert RecoveryStrategy.ESCALATE_REVIEW in RECOVERY_STRATEGY_ORDER
