"""Terminal outcome vocabulary for official-image evaluation.

``image_verified_at`` only records success. Without a terminal state for the
records that were evaluated and produced nothing, "we looked and found no
trustworthy official image" is stored identically to "we never looked", and a
catalogue-wide sweep cannot prove that every record was actually examined.

This module defines that terminal state and the single mapping used to derive
it from a discovery run, so the runner, the acceptance report and the API all
agree on what a given result means.
"""

from __future__ import annotations

from enum import StrEnum


class ImageEvaluationStatus(StrEnum):
    """Exactly one terminal outcome per evaluated record."""

    PENDING = "pending"
    # An image was accepted and stored, with full provenance. ``image_kind``
    # carries which of the accepted categories it is.
    VERIFIED = "verified"
    # The official source refused automated access. This is an access failure,
    # NOT evidence that the scholarship has no image.
    SOURCE_BLOCKED = "source_blocked"
    # The official source could not be reached at all (DNS, TLS, 5xx, reset).
    SOURCE_UNREACHABLE = "source_unreachable"
    # Candidates existed but every one was rejected as generic, third-party,
    # tracking or otherwise untrustworthy. The rejection is auditable.
    INVALID_CANDIDATES = "invalid_candidates"
    # The page was read successfully and genuinely publishes no trustworthy
    # official image. This is a true absence, not a failure.
    NO_OFFICIAL_IMAGE = "no_official_image"
    # The discovery run itself errored. Retryable, and distinguished from a
    # real negative result so it is never mistaken for one.
    ERROR = "error"


TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        ImageEvaluationStatus.VERIFIED,
        ImageEvaluationStatus.SOURCE_BLOCKED,
        ImageEvaluationStatus.SOURCE_UNREACHABLE,
        ImageEvaluationStatus.INVALID_CANDIDATES,
        ImageEvaluationStatus.NO_OFFICIAL_IMAGE,
        ImageEvaluationStatus.ERROR,
    }
)

#: Statuses that mean "we could not read the official source". These must never
#: be reported as "no image exists".
ACCESS_FAILURES: frozenset[str] = frozenset(
    {ImageEvaluationStatus.SOURCE_BLOCKED, ImageEvaluationStatus.SOURCE_UNREACHABLE}
)

#: Statuses that represent a completed, non-retryable negative result.
NEGATIVE_RESULTS: frozenset[str] = frozenset(
    {ImageEvaluationStatus.NO_OFFICIAL_IMAGE, ImageEvaluationStatus.INVALID_CANDIDATES}
)


def is_terminal(status: str | None) -> bool:
    return status in TERMINAL_STATUSES


def is_access_failure(status: str | None) -> bool:
    return status in ACCESS_FAILURES


def evaluation_status_for(
    *,
    trusted_status: str,
    candidate_count: int,
    page_error: str | None,
    timed_out: bool,
    requests_made: int,
) -> str:
    """Derive the single terminal outcome for one record's discovery result.

    Ordering matters: an access failure outranks everything, because a page we
    could not read tells us nothing about whether an image exists. Only when the
    page was genuinely read may a negative result be recorded.
    """
    trusted = str(trusted_status)
    if trusted in ("high", "medium") and candidate_count > 0:
        return ImageEvaluationStatus.VERIFIED

    if page_error:
        return ImageEvaluationStatus.SOURCE_UNREACHABLE
    if timed_out or requests_made == 0:
        return ImageEvaluationStatus.SOURCE_BLOCKED
    if trusted in ("error", "skipped"):
        return ImageEvaluationStatus.ERROR
    if candidate_count > 0:
        # We saw candidates and rejected all of them: an audited negative, not
        # an absence.
        return ImageEvaluationStatus.INVALID_CANDIDATES
    return ImageEvaluationStatus.NO_OFFICIAL_IMAGE


def preflight_status_for(reason: str) -> str:
    """Map a preflight probe reason to a terminal outcome."""
    if reason in ("blocked",):
        return ImageEvaluationStatus.SOURCE_BLOCKED
    if reason in ("timeout", "connection_error", "unexpected"):
        return ImageEvaluationStatus.SOURCE_BLOCKED
    if reason in ("no_source_url", "page_missing_root_may_exist"):
        # No page to read at all. Not an image verdict, but terminal for
        # image purposes: there is nothing official to inspect.
        return ImageEvaluationStatus.NO_OFFICIAL_IMAGE
    return ImageEvaluationStatus.SOURCE_UNREACHABLE
