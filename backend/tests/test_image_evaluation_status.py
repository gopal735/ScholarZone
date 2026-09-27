"""Tests for the terminal image-evaluation outcome.

The defect these guard against: a record that was crawled and produced no
trustworthy image was stored identically to a record that was never crawled, so
catalogue-wide image coverage could never be proven.
"""

from __future__ import annotations

import pytest

from app.services.image_evaluation_status import (
    ACCESS_FAILURES,
    NEGATIVE_RESULTS,
    TERMINAL_STATUSES,
    ImageEvaluationStatus,
    evaluation_status_for,
    is_terminal,
    preflight_status_for,
)


class TestVocabulary:
    def test_pending_is_not_terminal(self):
        assert not is_terminal(ImageEvaluationStatus.PENDING)
        assert not is_terminal(None)

    def test_every_outcome_is_terminal(self):
        for status in TERMINAL_STATUSES:
            assert is_terminal(status)

    def test_access_failures_and_negatives_are_disjoint(self):
        assert not (ACCESS_FAILURES & NEGATIVE_RESULTS)


class TestEvaluationStatusFor:
    def test_trusted_candidate_is_verified(self):
        assert (
            evaluation_status_for(
                trusted_status="high",
                candidate_count=1,
                page_error=None,
                timed_out=False,
                requests_made=5,
            )
            == ImageEvaluationStatus.VERIFIED
        )

    def test_page_error_outranks_a_trusted_status(self):
        """We cannot claim an image result from a page we failed to read."""
        assert (
            evaluation_status_for(
                trusted_status="no_trustworthy_image",
                candidate_count=0,
                page_error="404 Not Found",
                timed_out=False,
                requests_made=1,
            )
            == ImageEvaluationStatus.SOURCE_UNREACHABLE
        )

    def test_timeout_is_blocked_not_absence(self):
        assert (
            evaluation_status_for(
                trusted_status="no_trustworthy_image",
                candidate_count=0,
                page_error=None,
                timed_out=True,
                requests_made=1,
            )
            == ImageEvaluationStatus.SOURCE_BLOCKED
        )

    def test_no_requests_means_blocked(self):
        assert (
            evaluation_status_for(
                trusted_status="no_trustworthy_image",
                candidate_count=0,
                page_error=None,
                timed_out=False,
                requests_made=0,
            )
            == ImageEvaluationStatus.SOURCE_BLOCKED
        )

    def test_rejected_candidates_are_an_audited_negative(self):
        assert (
            evaluation_status_for(
                trusted_status="no_trustworthy_image",
                candidate_count=7,
                page_error=None,
                timed_out=False,
                requests_made=3,
            )
            == ImageEvaluationStatus.INVALID_CANDIDATES
        )

    def test_genuine_absence_is_no_official_image(self):
        assert (
            evaluation_status_for(
                trusted_status="no_trustworthy_image",
                candidate_count=0,
                page_error=None,
                timed_out=False,
                requests_made=4,
            )
            == ImageEvaluationStatus.NO_OFFICIAL_IMAGE
        )

    def test_error_status_is_retryable_and_distinct(self):
        status = evaluation_status_for(
            trusted_status="error",
            candidate_count=0,
            page_error=None,
            timed_out=False,
            requests_made=2,
        )
        assert status == ImageEvaluationStatus.ERROR
        assert status not in NEGATIVE_RESULTS

    def test_blocked_is_never_reported_as_no_image(self):
        for trusted in ("no_trustworthy_image", "low", "error"):
            status = evaluation_status_for(
                trusted_status=trusted,
                candidate_count=0,
                page_error=None,
                timed_out=True,
                requests_made=0,
            )
            assert status != ImageEvaluationStatus.NO_OFFICIAL_IMAGE

    def test_trusted_status_with_no_candidate_is_not_verified(self):
        """An empty candidate list must not be recorded as a verified image."""
        assert (
            evaluation_status_for(
                trusted_status="high",
                candidate_count=0,
                page_error=None,
                timed_out=False,
                requests_made=3,
            )
            != ImageEvaluationStatus.VERIFIED
        )


class TestPreflightStatusFor:
    @pytest.mark.parametrize("reason", ["blocked", "timeout", "connection_error", "unexpected"])
    def test_refusals_are_blocked(self, reason):
        assert preflight_status_for(reason) == ImageEvaluationStatus.SOURCE_BLOCKED

    def test_missing_source_url_is_a_real_absence(self):
        assert preflight_status_for("no_source_url") == ImageEvaluationStatus.NO_OFFICIAL_IMAGE

    def test_missing_root_is_not_blocked(self):
        assert preflight_status_for("page_missing_root_may_exist") == (
            ImageEvaluationStatus.NO_OFFICIAL_IMAGE
        )

    def test_every_preflight_outcome_is_terminal(self):
        for reason in (
            "blocked",
            "timeout",
            "connection_error",
            "unexpected",
            "no_source_url",
            "page_missing_root_may_exist",
        ):
            assert is_terminal(preflight_status_for(reason))
