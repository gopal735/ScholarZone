"""Retry orchestration with exponential backoff, jitter, and bounded attempts."""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.services.error_classification import classify_error, is_retryable

DEFAULT_MAX_ATTEMPTS = 5
BASE_BACKOFF_SECONDS = 2.0
MAX_BACKOFF_SECONDS = 300.0
JITTER_FRACTION = 0.25
RATE_LIMIT_BACKOFF_SECONDS = 60.0


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    next_retry_at: datetime | None
    reason: str


def compute_backoff(attempt_count: int, error_type: str) -> float:
    if error_type == "rate_limited":
        return RATE_LIMIT_BACKOFF_SECONDS

    backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt_count - 1))
    backoff = min(backoff, MAX_BACKOFF_SECONDS)

    jitter_range = backoff * JITTER_FRACTION
    jitter = random.uniform(-jitter_range, jitter_range)
    backoff = max(0.0, backoff + jitter)

    return backoff


def compute_next_retry_at(attempt_count: int, error_type: str, now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    backoff = compute_backoff(attempt_count, error_type)
    return now + timedelta(seconds=backoff)


def make_retry_decision(
    error_type: str,
    attempt_count: int,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> RetryDecision:
    category = classify_error(error_type)

    if not category.retryable:
        return RetryDecision(
            should_retry=False,
            next_retry_at=None,
            reason=f"non-retryable: {category.reason}",
        )

    if attempt_count >= max_attempts:
        return RetryDecision(
            should_retry=False,
            next_retry_at=None,
            reason=f"max attempts ({max_attempts}) exhausted",
        )

    next_at = compute_next_retry_at(attempt_count, error_type)
    return RetryDecision(
        should_retry=True,
        next_retry_at=next_at,
        reason=f"attempt {attempt_count + 1}/{max_attempts}",
    )
