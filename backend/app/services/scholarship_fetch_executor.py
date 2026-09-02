"""Fetch executor with retry/failure orchestration and persistent state."""

import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import ScholarshipFetchAttempt
from app.services.error_classification import is_retryable
from app.services.official_source_fetcher import OfficialSourceFetchResult, fetch_official_source
from app.services.scholarship_retry import (
    DEFAULT_MAX_ATTEMPTS,
    RetryDecision,
    make_retry_decision,
)
from app.services.telemetry import PipelineStages, record_event


@dataclass(frozen=True)
class FetchExecutionResult:
    fetch_result: OfficialSourceFetchResult
    attempt_id: int
    status: str
    attempts_remaining: int


def get_or_create_attempt(
    session: Session,
    scholarship_id: int,
    source_url: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> ScholarshipFetchAttempt:
    attempt = (
        session.query(ScholarshipFetchAttempt)
        .filter(
            ScholarshipFetchAttempt.scholarship_id == scholarship_id,
            ScholarshipFetchAttempt.source_url == source_url,
        )
        .order_by(ScholarshipFetchAttempt.created_at.desc())
        .first()
    )

    if attempt is None:
        attempt = ScholarshipFetchAttempt(
            scholarship_id=scholarship_id,
            source_url=source_url,
            status="pending",
            attempt_count=0,
            max_attempts=max_attempts,
        )
        session.add(attempt)
        session.flush()

    return attempt


def execute_fetch_with_retry(
    session: Session,
    scholarship_id: int,
    source_url: str,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> FetchExecutionResult:
    attempt = get_or_create_attempt(session, scholarship_id, source_url, max_attempts)

    if attempt.status == "resolved":
        cached = attempt.last_error_detail
        return FetchExecutionResult(
            fetch_result=OfficialSourceFetchResult(
                success=False,
                final_url=source_url,
                error_type="already_resolved",
                error_reason=cached or "attempt already resolved",
            ),
            attempt_id=attempt.id,
            status="resolved",
            attempts_remaining=0,
        )

    if attempt.terminal:
        return FetchExecutionResult(
            fetch_result=OfficialSourceFetchResult(
                success=False,
                final_url=source_url,
                error_type="terminal",
                error_reason=attempt.last_error_detail or "terminal failure",
            ),
            attempt_id=attempt.id,
            status="terminal",
            attempts_remaining=0,
        )

    now = datetime.now(timezone.utc)

    if attempt.next_retry_at is not None:
        next_retry = attempt.next_retry_at
        if next_retry.tzinfo is None:
            next_retry = next_retry.replace(tzinfo=timezone.utc)
        if next_retry > now:
            return FetchExecutionResult(
                fetch_result=OfficialSourceFetchResult(
                    success=False,
                    final_url=source_url,
                    error_type="waiting",
                    error_reason=f"waiting until {attempt.next_retry_at.isoformat()}",
                ),
                attempt_id=attempt.id,
                status="waiting",
                attempts_remaining=max(0, attempt.max_attempts - attempt.attempt_count),
            )

    fetch_start = time.monotonic()
    fetch_result = fetch_official_source(source_url)
    fetch_duration_ms = (time.monotonic() - fetch_start) * 1000.0

    record_event(
        stage=PipelineStages.RETRY,
        metric_type="success" if fetch_result.success else "failure",
        duration_ms=fetch_duration_ms,
        scholarship_id=scholarship_id,
        source=source_url,
        success=fetch_result.success,
        error_type=fetch_result.error_type,
    )

    attempt.attempt_count += 1
    attempt.last_attempt_at = now
    attempt.last_error_type = fetch_result.error_type if not fetch_result.success else None
    attempt.last_error_detail = fetch_result.error_reason if not fetch_result.success else None

    if fetch_result.success:
        attempt.status = "resolved"
        attempt.terminal = False
        attempt.resolved_at = now
        attempt.next_retry_at = None
        session.flush()
        return FetchExecutionResult(
            fetch_result=fetch_result,
            attempt_id=attempt.id,
            status="resolved",
            attempts_remaining=max(0, attempt.max_attempts - attempt.attempt_count),
        )

    decision = make_retry_decision(
        error_type=fetch_result.error_type,
        attempt_count=attempt.attempt_count,
        max_attempts=attempt.max_attempts,
    )

    if decision.should_retry:
        attempt.status = "retrying"
        attempt.next_retry_at = decision.next_retry_at
        session.flush()
        return FetchExecutionResult(
            fetch_result=fetch_result,
            attempt_id=attempt.id,
            status="retrying",
            attempts_remaining=max(0, attempt.max_attempts - attempt.attempt_count),
        )

    attempt.status = "terminal"
    attempt.terminal = True
    attempt.next_retry_at = None
    session.flush()
    return FetchExecutionResult(
        fetch_result=fetch_result,
        attempt_id=attempt.id,
        status="terminal",
        attempts_remaining=0,
    )


def process_due_retries(
    session: Session,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> list[FetchExecutionResult]:
    now = datetime.now(timezone.utc)
    retrying_attempts = (
        session.query(ScholarshipFetchAttempt)
        .filter(ScholarshipFetchAttempt.status == "retrying")
        .all()
    )

    results = []
    for attempt in retrying_attempts:
        next_retry = attempt.next_retry_at
        if next_retry is not None:
            if next_retry.tzinfo is None:
                next_retry = next_retry.replace(tzinfo=timezone.utc)
            if next_retry > now:
                continue

        result = execute_fetch_with_retry(
            session=session,
            scholarship_id=attempt.scholarship_id,
            source_url=attempt.source_url,
            max_attempts=max_attempts,
        )
        results.append(result)

    return results


def get_source_health(session: Session, source_url: str) -> dict:
    attempts = (
        session.query(ScholarshipFetchAttempt)
        .filter(ScholarshipFetchAttempt.source_url == source_url)
        .all()
    )

    total = len(attempts)
    resolved = sum(1 for a in attempts if a.status == "resolved")
    terminal = sum(1 for a in attempts if a.terminal)
    retrying = sum(1 for a in attempts if a.status == "retrying")

    return {
        "source_url": source_url,
        "total_attempts": total,
        "resolved": resolved,
        "terminal": terminal,
        "retrying": retrying,
        "healthy": terminal == 0 or (resolved > 0 and terminal / total < 0.5),
    }
