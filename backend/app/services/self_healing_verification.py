"""Self-healing verification layer.

When fetching, parsing, extraction, or verification encounters a recoverable failure,
automatically diagnose and recover using bounded fallback strategies without
bypassing any existing safety controls.

A recovered result must pass the NORMAL verification pipeline again:
Recovery -> Extracted candidate -> Diff -> Evidence -> Confidence -> Consensus -> Anomaly -> Safety -> Update / Review

Never send a recovered value directly to the database.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from html import unescape
from typing import Any

from .error_classification import classify_error, is_terminal
from .official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from .scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
    extract_scholarship_information,
)
from .scholarship_fetch_executor import execute_fetch_with_retry
from .telemetry import (
    MetricType,
    PipelineStages,
    record_event,
)


class FailureStage(str, Enum):
    FETCH = "fetch"
    EXTRACTION = "extraction"
    PARSING = "parsing"
    DIFF = "diff"
    EVIDENCE = "evidence"
    CONFIDENCE = "confidence"
    CONSENSUS = "consensus"
    ANOMALY = "anomaly"
    SAFETY_GATE = "safety_gate"
    UPDATE = "update"


class RecoveryStrategy(str, Enum):
    RETRY_FETCH = "retry_fetch"
    ALTERNATE_FETCH = "alternate_fetch"
    FALLBACK_EXTRACTION = "fallback_extraction"
    ALTERNATE_EXTRACTION = "alternate_extraction"
    RE_VALIDATE = "re_validate"
    ESCALATE_REVIEW = "escalate_review"


class RecoveryOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NON_RECOVERABLE = "non_recoverable"
    ESCALATED = "escalated"


class Recoverability(str, Enum):
    RECOVERABLE = "recoverable"
    NON_RECOVERABLE = "non_recoverable"
    UNCERTAIN = "uncertain"


FETCH_STAGES = frozenset({FailureStage.FETCH, FailureStage.PARSING})
EXTRACTION_STAGES = frozenset({FailureStage.EXTRACTION})
VERIFICATION_STAGES = frozenset({
    FailureStage.DIFF,
    FailureStage.EVIDENCE,
    FailureStage.CONFIDENCE,
    FailureStage.CONSENSUS,
    FailureStage.ANOMALY,
    FailureStage.SAFETY_GATE,
    FailureStage.UPDATE,
})

DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
MAX_RECOVERY_ATTEMPTS = 5

RECOVERY_STRATEGY_ORDER = [
    RecoveryStrategy.RETRY_FETCH,
    RecoveryStrategy.ALTERNATE_FETCH,
    RecoveryStrategy.FALLBACK_EXTRACTION,
    RecoveryStrategy.ALTERNATE_EXTRACTION,
    RecoveryStrategy.RE_VALIDATE,
    RecoveryStrategy.ESCALATE_REVIEW,
]


@dataclass
class RecoveryAttempt:
    attempt_number: int
    strategy: RecoveryStrategy
    outcome: RecoveryOutcome
    timestamp: float
    duration_ms: float = 0.0
    error_type: str | None = None
    error_message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SelfHealingResult:
    original_failure_stage: FailureStage
    original_error_type: str
    original_error_message: str
    is_recoverable: bool = False
    recovery_attempts: list[RecoveryAttempt] = field(default_factory=list)
    final_outcome: RecoveryOutcome = RecoveryOutcome.FAILED
    recovered_extraction: ScholarshipExtractionResult | None = None
    recovered_fetch: OfficialSourceFetchResult | None = None
    requires_review: bool = False
    review_reason: str | None = None
    correlation_id: str = ""
    total_duration_ms: float = 0.0
    safety_gates_passed: bool = False
    evidence_validated: bool = False
    confidence_validated: bool = False
    anomaly_checked: bool = False

    @property
    def was_recovered(self) -> bool:
        return self.final_outcome == RecoveryOutcome.SUCCESS

    @property
    def was_escalated(self) -> bool:
        return self.final_outcome == RecoveryOutcome.ESCALATED

    @property
    def attempt_count(self) -> int:
        return len(self.recovery_attempts)

    @property
    def strategies_attempted(self) -> list[RecoveryStrategy]:
        return [a.strategy for a in self.recovery_attempts]


@dataclass
class RecoveryContext:
    source_url: str | None = None
    html_content: str | None = None
    scholarship_id: int | None = None
    field_name: str | None = None
    job_id: str | None = None
    verification_id: str | None = None
    existing_fetch_result: OfficialSourceFetchResult | None = None
    existing_extraction_result: ScholarshipExtractionResult | None = None
    attempt_count: int = 0
    max_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS
    session: object | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def diagnose_failure(
    failure_stage: FailureStage,
    error_type: str,
    error_message: str,
    context: RecoveryContext,
) -> tuple[Recoverability, list[RecoveryStrategy]]:
    """Diagnose a failure and determine recovery strategies.

    Returns a tuple of (recoverability, ordered_strategies).
    """
    if is_terminal(error_type):
        return Recoverability.NON_RECOVERABLE, [RecoveryStrategy.ESCALATE_REVIEW]

    category = classify_error(error_type)
    if not category.retryable:
        return Recoverability.NON_RECOVERABLE, [RecoveryStrategy.ESCALATE_REVIEW]

    if failure_stage in FETCH_STAGES:
        strategies = [
            RecoveryStrategy.RETRY_FETCH,
            RecoveryStrategy.ALTERNATE_FETCH,
            RecoveryStrategy.ESCALATE_REVIEW,
        ]
    elif failure_stage in EXTRACTION_STAGES:
        strategies = [
            RecoveryStrategy.FALLBACK_EXTRACTION,
            RecoveryStrategy.ALTERNATE_EXTRACTION,
            RecoveryStrategy.RE_VALIDATE,
            RecoveryStrategy.ESCALATE_REVIEW,
        ]
    elif failure_stage in VERIFICATION_STAGES:
        strategies = [
            RecoveryStrategy.RE_VALIDATE,
            RecoveryStrategy.ESCALATE_REVIEW,
        ]
    else:
        strategies = [
            RecoveryStrategy.RETRY_FETCH,
            RecoveryStrategy.FALLBACK_EXTRACTION,
            RecoveryStrategy.RE_VALIDATE,
            RecoveryStrategy.ESCALATE_REVIEW,
        ]

    return Recoverability.RECOVERABLE, strategies


def attempt_recovery(
    failure_stage: FailureStage,
    error_type: str,
    error_message: str,
    context: RecoveryContext,
    max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    correlation_id: str | None = None,
) -> SelfHealingResult:
    """Attempt to recover from a verification failure.

    Tries recovery strategies in order until one succeeds or all fail.
    Never bypasses safety controls.
    """
    start_time = time.monotonic()
    cid = correlation_id or str(uuid.uuid4())

    bounded_attempts = min(max(max_recovery_attempts, 1), MAX_RECOVERY_ATTEMPTS)

    recoverability, strategies = diagnose_failure(
        failure_stage, error_type, error_message, context
    )

    result = SelfHealingResult(
        original_failure_stage=failure_stage,
        original_error_type=error_type,
        original_error_message=error_message,
        is_recoverable=recoverability == Recoverability.RECOVERABLE,
        correlation_id=cid,
    )

    if recoverability == Recoverability.NON_RECOVERABLE:
        result.final_outcome = RecoveryOutcome.NON_RECOVERABLE
        result.requires_review = True
        result.review_reason = f"Non-recoverable failure at {failure_stage.value}: {error_type}"
        _record_recovery_telemetry(result, context)
        result.total_duration_ms = (time.monotonic() - start_time) * 1000.0
        return result

    strategies_seen: set[RecoveryStrategy] = set()
    for attempt_idx, strategy in enumerate(strategies):
        if result.was_recovered or result.was_escalated:
            break
        if attempt_idx >= bounded_attempts:
            break
        if strategy in strategies_seen and strategy != RecoveryStrategy.ESCALATE_REVIEW:
            continue
        strategies_seen.add(strategy)

        attempt_start = time.monotonic()
        attempt = _try_recovery_strategy(
            strategy=strategy,
            context=context,
            attempt_number=attempt_idx + 1,
            result=result,
            correlation_id=cid,
        )
        attempt_duration = (time.monotonic() - attempt_start) * 1000.0
        attempt.duration_ms = attempt_duration
        result.recovery_attempts.append(attempt)

        if attempt.outcome == RecoveryOutcome.SUCCESS:
            result.final_outcome = RecoveryOutcome.SUCCESS
        elif attempt.outcome == RecoveryOutcome.ESCALATED:
            result.final_outcome = RecoveryOutcome.ESCALATED
            result.requires_review = True
            result.review_reason = f"Escalated after {strategy.value}"

    if not result.was_recovered and not result.was_escalated:
        if any(a.outcome == RecoveryOutcome.PARTIAL for a in result.recovery_attempts):
            result.final_outcome = RecoveryOutcome.PARTIAL
            result.requires_review = True
            result.review_reason = "Partial recovery; requires manual review"
        else:
            result.final_outcome = RecoveryOutcome.FAILED
            result.requires_review = True
            result.review_reason = f"All recovery strategies exhausted for {failure_stage.value}"

    result.total_duration_ms = (time.monotonic() - start_time) * 1000.0
    _record_recovery_telemetry(result, context)
    return result


def _try_recovery_strategy(
    strategy: RecoveryStrategy,
    context: RecoveryContext,
    attempt_number: int,
    result: SelfHealingResult,
    correlation_id: str,
) -> RecoveryAttempt:
    """Try a single recovery strategy."""
    timestamp = time.time()

    if strategy == RecoveryStrategy.RETRY_FETCH:
        return _retry_fetch(context, attempt_number, timestamp, correlation_id)
    elif strategy == RecoveryStrategy.ALTERNATE_FETCH:
        return _alternate_fetch(context, attempt_number, timestamp, correlation_id)
    elif strategy == RecoveryStrategy.FALLBACK_EXTRACTION:
        return _fallback_extraction(context, attempt_number, timestamp, correlation_id)
    elif strategy == RecoveryStrategy.ALTERNATE_EXTRACTION:
        return _alternate_extraction(context, attempt_number, timestamp, correlation_id)
    elif strategy == RecoveryStrategy.RE_VALIDATE:
        return _re_validate(context, attempt_number, timestamp, correlation_id)
    elif strategy == RecoveryStrategy.ESCALATE_REVIEW:
        return _escalate_to_review(
            context, attempt_number, timestamp, correlation_id,
            reason=f"Recovery strategy {strategy.value} triggered"
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=strategy,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_message=f"Unknown recovery strategy: {strategy.value}",
    )


def _retry_fetch(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Retry the existing fetch path.

    CRITICAL: Delegates to the authoritative execute_fetch_with_retry()
    when a session is available. No second retry loop is implemented here.
    """
    if not context.source_url:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=0.0,
            error_message="No source URL available for retry",
        )

    if context.session is not None:
        return _delegate_retry_to_executor(context, attempt_number, timestamp, correlation_id)

    fetch_result = fetch_official_source(context.source_url)

    if fetch_result.success:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.SUCCESS,
            timestamp=timestamp,
            duration_ms=0.0,
            details={"status_code": fetch_result.status_code, "content_length": len(fetch_result.content or "")},
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.RETRY_FETCH,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_type=fetch_result.error_type,
        error_message=fetch_result.error_reason,
    )


def _delegate_retry_to_executor(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Delegate retry to the authoritative execute_fetch_with_retry().

    Self-healing RETRY_FETCH does NOT implement its own retry loop.
    The existing retry executor remains the single retry owner.
    """
    import time

    retry_start = time.monotonic()

    execution_result = execute_fetch_with_retry(
        session=context.session,
        scholarship_id=context.scholarship_id or 0,
        source_url=context.source_url,
        max_attempts=context.max_attempts,
    )

    retry_duration_ms = (time.monotonic() - retry_start) * 1000.0

    if execution_result.fetch_result.success:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.SUCCESS,
            timestamp=timestamp,
            duration_ms=retry_duration_ms,
            details={
                "status_code": execution_result.fetch_result.status_code,
                "content_length": len(execution_result.fetch_result.content or ""),
                "delegated_to_executor": True,
                "executor_status": execution_result.status,
                "attempt_id": execution_result.attempt_id,
            },
        )

    if execution_result.status == "waiting":
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=retry_duration_ms,
            error_type="waiting",
            error_message=execution_result.fetch_result.error_reason,
            details={
                "delegated_to_executor": True,
                "executor_status": execution_result.status,
                "attempt_id": execution_result.attempt_id,
            },
        )

    if execution_result.status in ("resolved", "terminal"):
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.RETRY_FETCH,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=retry_duration_ms,
            error_type=execution_result.fetch_result.error_type or execution_result.status,
            error_message=execution_result.fetch_result.error_reason,
            details={
                "delegated_to_executor": True,
                "executor_status": execution_result.status,
                "attempt_id": execution_result.attempt_id,
            },
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.RETRY_FETCH,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=retry_duration_ms,
        error_type=execution_result.fetch_result.error_type,
        error_message=execution_result.fetch_result.error_reason,
        details={
            "delegated_to_executor": True,
            "executor_status": execution_result.status,
            "attempt_id": execution_result.attempt_id,
        },
    )


def _alternate_fetch(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Try alternate fetch/response handling where supported."""
    if not context.source_url:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.ALTERNATE_FETCH,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=0.0,
            error_message="No source URL available for alternate fetch",
        )

    if context.existing_fetch_result and context.existing_fetch_result.success:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.ALTERNATE_FETCH,
            outcome=RecoveryOutcome.SUCCESS,
            timestamp=timestamp,
            duration_ms=0.0,
            details={"reused_existing": True},
        )

    if context.html_content:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.ALTERNATE_FETCH,
            outcome=RecoveryOutcome.PARTIAL,
            timestamp=timestamp,
            duration_ms=0.0,
            details={"has_content": True, "content_length": len(context.html_content)},
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.ALTERNATE_FETCH,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_message="No alternate fetch path available",
    )


_FALLBACK_FIELD_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "scholarship_name": [
        re.compile(r"<h1[^>]*>(.+?)</h1>", re.IGNORECASE | re.DOTALL),
        re.compile(r"<title>(.+?)</title>", re.IGNORECASE | re.DOTALL),
    ],
    "deadline": [
        re.compile(r"deadline[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"due[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"close[:\s]+([^\n<]{2,100})", re.IGNORECASE),
    ],
    "award_amount": [
        re.compile(r"(\$[\d,]+(?:\.\d{2})?)", re.IGNORECASE),
        re.compile(r"award[:\s]+([^\n<]{2,100})", re.IGNORECASE),
    ],
    "provider": [
        re.compile(r"provided\s+by[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"offered\s+by[:\s]+([^\n<]{2,100})", re.IGNORECASE),
    ],
    "eligibility": [
        re.compile(r"eligib[^\n<]{2,200}", re.IGNORECASE),
    ],
    "duration": [
        re.compile(r"(\d+\s*(?:year|month|week|semester)[^\n<]{0,50})", re.IGNORECASE),
    ],
}


def _fallback_extraction(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Try fallback extraction strategy with simpler patterns."""
    html_content = context.html_content
    if not html_content:
        if context.existing_fetch_result and context.existing_fetch_result.content:
            html_content = context.existing_fetch_result.content

    if not html_content:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.FALLBACK_EXTRACTION,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=0.0,
            error_message="No HTML content available for fallback extraction",
        )

    extracted_fields: dict[str, str | None] = {}
    confidence: dict[str, str] = {}
    notes: list[str] = []

    for field_name, patterns in _FALLBACK_FIELD_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(html_content)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                value = unescape(value)
                value = re.sub(r"\s+", " ", value)
                if value and len(value) > 1:
                    extracted_fields[field_name] = value
                    confidence[field_name] = ExtractionConfidence.LOW
                    break

    if extracted_fields:
        extraction_result = ScholarshipExtractionResult(
            **extracted_fields,
            confidence=confidence,
            extraction_notes=notes + ["Fallback extraction used"],
        )
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.FALLBACK_EXTRACTION,
            outcome=RecoveryOutcome.PARTIAL,
            timestamp=timestamp,
            duration_ms=0.0,
            details={"fields_extracted": list(extracted_fields.keys())},
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.FALLBACK_EXTRACTION,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_message="Fallback extraction produced no fields",
    )


_ALTERNATE_FIELD_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "scholarship_name": [
        re.compile(r"(?:scholarship|program|award)[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"<h[1-3][^>]*>([^<]{2,100})</h[1-3]>", re.IGNORECASE | re.DOTALL),
    ],
    "deadline": [
        re.compile(r"(?:by|before|until)[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"),
        re.compile(r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2},?\s*\d{4})", re.IGNORECASE),
    ],
    "award_amount": [
        re.compile(r"(?:amount|value|prize)[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*(?:USD|EUR|GBP|\$|€|£)?)"),
    ],
    "provider": [
        re.compile(r"(?:university|institute|foundation|organization|company)[:\s]+([^\n<]{2,100})", re.IGNORECASE),
    ],
    "eligibility": [
        re.compile(r"(?:open\s+to|for|available\s+to)[:\s]+([^\n<]{2,200})", re.IGNORECASE),
    ],
    "duration": [
        re.compile(r"(?:lasts?|period|term|span)[:\s]+([^\n<]{2,100})", re.IGNORECASE),
        re.compile(r"(\d+\s*(?:year|month|week|semester|term)[^\n<]{0,50})", re.IGNORECASE),
    ],
    "application_url": [
        re.compile(r'href="(https?://[^"]{5,200}(?:apply|application|submit)[^"]{0,100})"', re.IGNORECASE),
    ],
}


def _alternate_extraction(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Try alternate structured extraction path."""
    html_content = context.html_content
    if not html_content:
        if context.existing_fetch_result and context.existing_fetch_result.content:
            html_content = context.existing_fetch_result.content

    if not html_content:
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.ALTERNATE_EXTRACTION,
            outcome=RecoveryOutcome.FAILED,
            timestamp=timestamp,
            duration_ms=0.0,
            error_message="No HTML content available for alternate extraction",
        )

    extracted_fields: dict[str, str | None] = {}
    confidence: dict[str, str] = {}
    notes: list[str] = []

    for field_name, patterns in _ALTERNATE_FIELD_PATTERNS.items():
        for pattern in patterns:
            match = pattern.search(html_content)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                value = unescape(value)
                value = re.sub(r"\s+", " ", value)
                if value and len(value) > 1:
                    extracted_fields[field_name] = value
                    confidence[field_name] = ExtractionConfidence.LOW
                    break

    if extracted_fields:
        extraction_result = ScholarshipExtractionResult(
            **extracted_fields,
            confidence=confidence,
            extraction_notes=notes + ["Alternate extraction used"],
        )
        return RecoveryAttempt(
            attempt_number=attempt_number,
            strategy=RecoveryStrategy.ALTERNATE_EXTRACTION,
            outcome=RecoveryOutcome.PARTIAL,
            timestamp=timestamp,
            duration_ms=0.0,
            details={"fields_extracted": list(extracted_fields.keys())},
        )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.ALTERNATE_EXTRACTION,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_message="Alternate extraction produced no fields",
    )


def _re_validate(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
) -> RecoveryAttempt:
    """Re-validate extracted result through normal pipeline."""
    if context.existing_extraction_result is not None:
        extraction = context.existing_extraction_result
        has_fields = any(
            getattr(extraction, f, None) is not None
            for f in [
                "scholarship_name", "provider", "deadline", "award_amount",
                "eligibility", "duration", "application_url",
            ]
        )
        if has_fields:
            return RecoveryAttempt(
                attempt_number=attempt_number,
                strategy=RecoveryStrategy.RE_VALIDATE,
                outcome=RecoveryOutcome.PARTIAL,
                timestamp=timestamp,
                duration_ms=0.0,
                details={"has_extractable_fields": True},
            )

    if context.html_content:
        re_extraction = extract_scholarship_information(context.html_content, context.source_url or "")
        has_fields = any(
            getattr(re_extraction, f, None) is not None
            for f in [
                "scholarship_name", "provider", "deadline", "award_amount",
                "eligibility", "duration", "application_url",
            ]
        )
        if has_fields:
            return RecoveryAttempt(
                attempt_number=attempt_number,
                strategy=RecoveryStrategy.RE_VALIDATE,
                outcome=RecoveryOutcome.PARTIAL,
                timestamp=timestamp,
                duration_ms=0.0,
                details={"re_extraction_fields": [f for f in [
                    "scholarship_name", "provider", "deadline", "award_amount",
                    "eligibility", "duration", "application_url",
                ] if getattr(re_extraction, f, None) is not None]},
            )

    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.RE_VALIDATE,
        outcome=RecoveryOutcome.FAILED,
        timestamp=timestamp,
        duration_ms=0.0,
        error_message="Re-validation produced no usable fields",
    )


def _escalate_to_review(
    context: RecoveryContext,
    attempt_number: int,
    timestamp: float,
    correlation_id: str,
    reason: str = "Recovery uncertain",
) -> RecoveryAttempt:
    """Escalate to REVIEW if recovery remains uncertain."""
    return RecoveryAttempt(
        attempt_number=attempt_number,
        strategy=RecoveryStrategy.ESCALATE_REVIEW,
        outcome=RecoveryOutcome.ESCALATED,
        timestamp=timestamp,
        duration_ms=0.0,
        details={"reason": reason, "source_url": context.source_url},
    )


def _record_recovery_telemetry(
    result: SelfHealingResult,
    context: RecoveryContext,
) -> None:
    """Record telemetry for recovery attempt."""
    for attempt in result.recovery_attempts:
        metric_type = (
            MetricType.SUCCESS
            if attempt.outcome == RecoveryOutcome.SUCCESS
            else MetricType.FAILURE
        )
        record_event(
            stage=PipelineStages.RETRY,
            metric_type=metric_type,
            duration_ms=attempt.duration_ms,
            scholarship_id=context.scholarship_id,
            source=context.source_url,
            job_id=context.job_id,
            verification_id=context.verification_id,
            success=attempt.outcome == RecoveryOutcome.SUCCESS,
            error_type=attempt.error_type or result.original_error_type,
            metadata={
                "recovery_strategy": attempt.strategy.value,
                "attempt_number": attempt.attempt_number,
                "failure_stage": result.original_failure_stage.value,
                "recovery_outcome": attempt.outcome.value,
                "correlation_id": result.correlation_id,
            },
        )

    record_event(
        stage=PipelineStages.RETRY,
        metric_type=MetricType.SUCCESS if result.was_recovered else MetricType.FAILURE,
        duration_ms=result.total_duration_ms,
        scholarship_id=context.scholarship_id,
        source=context.source_url,
        job_id=context.job_id,
        verification_id=context.verification_id,
        success=result.was_recovered,
        error_type=result.original_error_type if not result.was_recovered else None,
        metadata={
            "final_outcome": result.final_outcome.value,
            "total_attempts": result.attempt_count,
            "failure_stage": result.original_failure_stage.value,
            "requires_review": result.requires_review,
            "correlation_id": result.correlation_id,
            "strategies_attempted": [s.value for s in result.strategies_attempted],
        },
    )


def is_recoverable_error(error_type: str, failure_stage: FailureStage) -> bool:
    """Determine if an error is recoverable."""
    if is_terminal(error_type):
        return False
    category = classify_error(error_type)
    return category.retryable


def get_recovery_strategies(
    failure_stage: FailureStage,
    error_type: str,
    context: RecoveryContext,
) -> list[RecoveryStrategy]:
    """Get ordered list of recovery strategies for a failure."""
    _, strategies = diagnose_failure(failure_stage, error_type, "", context)
    return strategies


def should_attempt_recovery(
    error_type: str,
    failure_stage: FailureStage,
    attempt_count: int = 0,
    max_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
) -> bool:
    """Determine if recovery should be attempted."""
    if attempt_count >= min(max(max_attempts, 1), MAX_RECOVERY_ATTEMPTS):
        return False
    return is_recoverable_error(error_type, failure_stage)
