"""Phase 10 - admin-review protection, proven as a regression suite.

The rule under test is short: a record under admin review is retained, whatever
else is true about it. The value of the suite is entirely in the ``parametrize``
markers - every combination below is a way the retention rule could plausibly
resolve doubt in favour of deletion, and each one has to be shown not to.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.retention_contract import (
    BUCKET_ADMIN_REVIEW,
    BUCKET_AMBIGUOUS,
    BUCKET_CONFLICTING,
    BUCKET_DELETE,
    BUCKET_LIVE,
    BUCKET_PROTECTED,
    DECISION_DELETE,
    DECISION_KEEP,
    REASON_ADMIN_REVIEW,
    REASON_LIVE,
    RETENTION_CONTRACT_VERSION,
    RetentionDecision,
    RetentionFacts,
    RetentionPolicy,
    assert_invariants,
    classify,
    default_policy,
)

AS_OF = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
LONG_AGO = datetime(2020, 1, 1, tzinfo=timezone.utc)


def facts(**overrides) -> RetentionFacts:
    """A record that satisfies every deletion condition.

    Starting from a deletable record and overriding one fact at a time is what
    makes these tests meaningful: a test that starts from a protected record and
    expects it to stay protected would also pass if the classifier simply returned
    KEEP for everything.
    """
    base = dict(
        scholarship_id=1,
        is_live=False,
        verification_status="inactive",
        lifecycle_status="closed",
        deletion_protected=False,
        is_archived=True,
        archived_at=LONG_AGO,
        archived_reason="deadline passed on 2020-01-01",
        candidate_since=LONG_AGO,
        is_verified=False,
        deadline_date=date(2019, 1, 1),
        blocking_dependencies=frozenset(),
        evidence_complete=True,
    )
    base.update(overrides)
    return RetentionFacts(**base)


def decide(**overrides) -> RetentionDecision:
    return classify(facts(**overrides), policy=default_policy(), as_of=AS_OF)


class TestTheCanonicalRule:
    def test_live_is_kept_for_the_live_reason(self):
        decision = decide(is_live=True, verification_status="active", is_verified=True)
        assert decision.decision == DECISION_KEEP
        assert decision.reason == REASON_LIVE
        assert decision.bucket == BUCKET_LIVE

    def test_admin_review_is_kept_for_the_admin_review_reason(self):
        decision = decide(verification_status="needs_review")
        assert decision.decision == DECISION_KEEP
        assert decision.reason == REASON_ADMIN_REVIEW
        assert decision.bucket == BUCKET_ADMIN_REVIEW

    def test_live_and_admin_review_is_retained_once(self):
        """Both states hold, so the record is kept - and named by the review.

        The two gates cannot both fire as separate decisions, and the order
        between them is a reporting choice rather than a safety one: either order
        produces KEEP. Review is checked first so the reason names the more urgent
        state, because "a human must look at this" is the actionable fact.
        """
        decision = decide(
            is_live=True, verification_status="needs_review", is_verified=False
        )
        assert decision.decision == DECISION_KEEP
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert decision.reason == REASON_ADMIN_REVIEW

    def test_provably_neither_live_nor_review_is_a_delete_candidate(self):
        decision = decide()
        assert decision.decision == DECISION_DELETE
        assert decision.reason == "NOT_LIVE_NOT_REVIEW"
        assert decision.bucket == BUCKET_DELETE

    def test_keep_is_exactly_live_union_admin_review_over_the_deletable_base(self):
        """KEEP = LIVE ∪ ADMIN_REVIEW, asserted over a set rather than a row."""
        decisions = [
            decide(scholarship_id=1, is_live=True, verification_status="active", is_verified=True),
            decide(scholarship_id=2, verification_status="needs_review"),
            decide(scholarship_id=3),
        ]
        keep = {d.scholarship_id for d in decisions if d.is_keep}
        delete = {d.scholarship_id for d in decisions if d.is_delete}
        assert keep == {1, 2}
        assert delete == {3}
        assert keep & delete == set()
        assert keep | delete == {1, 2, 3}

    def test_contract_version_is_published(self):
        """Version 2 added the explicit state machine and split UNKNOWN from
        AMBIGUOUS. A pinned value, so a version bump has to be a deliberate edit
        rather than something that happens because a field was added."""
        assert RETENTION_CONTRACT_VERSION == "live-admin-review-retention/2"


class TestAdminReviewSurvivesEveryGate:
    """Phase 2 precedence: review wins, even when everything else has failed."""

    @pytest.mark.parametrize(
        "failing_gates",
        [
            pytest.param({"deadline_date": date(2019, 1, 1)}, id="deadline-expired"),
            pytest.param({"is_verified": False}, id="not-verified"),
            pytest.param({"is_archived": True, "archived_at": None}, id="archived-no-clock"),
            pytest.param({"is_archived": False, "archived_at": None}, id="not-archived"),
            pytest.param({"candidate_since": None}, id="not-armed"),
            pytest.param({"archived_at": AS_OF - timedelta(days=1)}, id="closed-yesterday"),
            pytest.param({"lifecycle_status": "closed"}, id="lifecycle-closed"),
            pytest.param({"blocking_dependencies": frozenset({"ScholarshipReview"})}, id="has-dependency"),
        ],
    )
    @pytest.mark.parametrize(
        "review_status",
        ["needs_review", "conflict", "disputed", "uncertain", "pending", "partially_verified", "unsupported"],
    )
    def test_review_status_keeps_the_record_whatever_else_fails(
        self, review_status, failing_gates
    ):
        decision = decide(verification_status=review_status, **failing_gates)
        assert decision.decision == DECISION_KEEP, decision.detail
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert decision.reason == REASON_ADMIN_REVIEW

    @pytest.mark.parametrize(
        "status", ["needs_review", "conflict", "disputed", "uncertain", "unsupported"]
    )
    def test_review_status_with_no_clock_at_all_is_still_admin_review(self, status):
        """The review gate is first, so it does not depend on any other evidence."""
        decision = decide(
            verification_status=status,
            is_archived=False,
            archived_at=None,
            candidate_since=None,
        )
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert decision.decision == DECISION_KEEP

    def test_pending_scholarship_review_keeps_the_record(self):
        decision = decide(pending_scholarship_reviews=1)
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert decision.decision == DECISION_KEEP

    def test_pending_image_review_keeps_the_record(self):
        decision = decide(pending_image_reviews=2)
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert "2 image review" in decision.detail

    def test_quarantined_record_is_protected_not_deleted(self):
        """A judged non-scholarship is evidence of where it came from."""
        decision = decide(verification_status="quarantined")
        assert decision.decision == DECISION_KEEP
        assert decision.bucket == BUCKET_PROTECTED
        assert decision.reason == "PROTECTED_STATUS"

    def test_admin_review_decision_never_names_protection(self):
        """Review must win over protection, or the reason misreports why it lives."""
        decision = decide(verification_status="needs_review", deletion_protected=True)
        assert decision.bucket == BUCKET_ADMIN_REVIEW
        assert decision.reason == REASON_ADMIN_REVIEW


class TestUncertaintyIsNeverDeletion:
    """Phase 4: UNKNOWN, AMBIGUOUS and CONFLICTING are all retained."""

    @pytest.mark.parametrize(
        "overrides, expected_bucket",
        [
            pytest.param({"verification_status": "brand-new-state"}, BUCKET_AMBIGUOUS, id="unknown-verification"),
            pytest.param({"verification_status": None}, BUCKET_AMBIGUOUS, id="null-verification"),
            pytest.param({"verification_status": "   "}, BUCKET_AMBIGUOUS, id="blank-verification"),
            pytest.param({"lifecycle_status": "rolling"}, BUCKET_AMBIGUOUS, id="unknown-lifecycle"),
            pytest.param({"lifecycle_status": None}, BUCKET_AMBIGUOUS, id="null-lifecycle"),
            pytest.param({"evidence_complete": False, "evidence_error": "query failed"}, BUCKET_AMBIGUOUS, id="incomplete-evidence"),
            pytest.param({"is_archived": True, "archived_at": None}, BUCKET_CONFLICTING, id="archived-without-clock"),
            pytest.param({"is_archived": True, "archived_reason": "  "}, BUCKET_CONFLICTING, id="archived-without-reason"),
            pytest.param({"verification_status": "active", "is_verified": False}, BUCKET_CONFLICTING, id="legacy-flag-contradicts"),
            pytest.param(
                {"lifecycle_status": "open", "is_archived": True, "deadline_date": date(2099, 1, 1)},
                BUCKET_CONFLICTING,
                id="open-but-archived-with-future-deadline",
            ),
        ],
    )
    def test_unresolvable_records_are_retained(self, overrides, expected_bucket):
        decision = decide(**overrides)
        assert decision.decision == DECISION_KEEP
        assert decision.bucket == expected_bucket

    def test_unknown_status_does_not_become_live(self):
        decision = decide(verification_status="mystery")
        assert decision.bucket != BUCKET_LIVE
        assert decision.is_keep

    def test_missing_status_does_not_become_live(self):
        assert decide(verification_status=None).bucket != BUCKET_LIVE
        assert decide(lifecycle_status=None).bucket != BUCKET_LIVE

    def test_a_contradictory_record_is_never_deleted_even_though_aged_out(self):
        """Conflict detection must precede the retention clock, not follow it."""
        decision = decide(archived_at=None, is_archived=True)
        assert decision.bucket == BUCKET_CONFLICTING
        assert decision.is_keep


class TestPreservePrecedence:
    def test_operator_protection_beats_the_deletion_test(self):
        decision = decide(deletion_protected=True)
        assert decision.bucket == BUCKET_PROTECTED
        assert decision.reason == "OPERATOR_PROTECTED"

    def test_a_dependency_that_must_survive_blocks_deletion(self):
        decision = decide(blocking_dependencies=frozenset({"ScholarshipSnapshot"}))
        assert decision.bucket == BUCKET_PROTECTED
        assert decision.reason == "DEPENDENCY_MUST_SURVIVE"

    def test_a_verified_record_hidden_by_the_image_gate_is_never_deletable(self):
        """The real reason this engine exists.

        A record absent from the public catalogue because its awarding body
        publishes no findable logo is a real programme with a real deadline. It
        is hidden by a product quality gate, not stale, and deleting it would
        destroy a scholarship an applicant can still apply to.

        Two independent protections hold it, and both are asserted, because
        relying on either one alone is how a future edit to the status list
        silently removes the guarantee.
        """
        by_status = decide(
            verification_status="active", is_verified=True, is_archived=False, archived_at=None
        )
        assert by_status.decision == DECISION_KEEP
        assert by_status.reason == "PROTECTED_STATUS"

        # And with the verified status removed from the protected set, the
        # "hidden rather than closed" reasons are still there to catch it. Two
        # are asserted because a record that is not archived may present either:
        # one that was never archived at all, and one whose round closed, was
        # archived, and was then reopened without its clock being cleared.
        relaxed = RetentionPolicy(protected_statuses=frozenset({"quarantined"}))
        never_archived = classify(
            facts(verification_status="inactive", is_archived=False, archived_at=None),
            policy=relaxed,
            as_of=AS_OF,
        )
        assert never_archived.decision == DECISION_KEEP
        assert never_archived.reason == "NO_RETENTION_CLOCK"
        assert "unknown date is not evidence of a long one" in never_archived.detail

        reopened = classify(
            facts(verification_status="inactive", is_archived=False, archived_at=LONG_AGO),
            policy=relaxed,
            as_of=AS_OF,
        )
        assert reopened.decision == DECISION_KEEP
        assert reopened.reason == "NOT_ARCHIVED"
        assert "quality gate" in reopened.detail

    def test_retention_not_elapsed_keeps_the_record(self):
        decision = decide(archived_at=AS_OF - timedelta(days=179))
        assert decision.bucket == BUCKET_PROTECTED
        assert decision.reason == "RETENTION_NOT_ELAPSED"

    def test_retention_elapsed_on_the_boundary_is_deletable(self):
        decision = decide(archived_at=AS_OF - timedelta(days=180))
        assert decision.decision == DECISION_DELETE

    def test_grace_not_elapsed_keeps_the_record(self):
        decision = decide(candidate_since=AS_OF - timedelta(days=13))
        assert decision.reason == "GRACE_NOT_ELAPSED"

    def test_not_armed_keeps_the_record(self):
        decision = decide(candidate_since=None)
        assert decision.reason == "NOT_ARMED"

    def test_no_retention_clock_keeps_the_record(self):
        decision = decide(is_archived=False, archived_at=None)
        assert decision.reason == "NO_RETENTION_CLOCK"


class TestPurity:
    def test_same_inputs_give_the_same_decision(self):
        first = decide()
        second = decide()
        assert first.as_dict() == second.as_dict()

    def test_a_different_as_of_changes_only_the_clock_arithmetic(self):
        late = classify(facts(), policy=default_policy(), as_of=AS_OF + timedelta(days=365))
        assert late.scholarship_id == 1
        assert late.decision == DECISION_DELETE

    def test_every_decision_records_every_check(self):
        decision = decide()
        assert "retention_satisfied" in decision.checks
        assert "not_under_admin_review" in decision.checks
        assert "no_blocking_dependency" in decision.checks

    def test_a_delete_has_no_failing_check(self):
        decision = decide()
        assert all(decision.checks.values())


class TestInvariantAssertion:
    def test_invariants_accept_a_valid_population(self):
        decisions = [
            decide(scholarship_id=1, is_live=True, verification_status="active", is_verified=True),
            decide(scholarship_id=2, verification_status="needs_review"),
            decide(scholarship_id=3, verification_status="mystery"),
            decide(scholarship_id=4),
        ]
        assert_invariants(decisions)

    def test_invariants_reject_a_forged_live_deletion(self):
        """The assertion is the engine's last line, so it must actually fire."""
        forged = decide().as_dict()
        forged["bucket"] = BUCKET_LIVE
        bad = type(decide())(
            scholarship_id=forged["scholarship_id"],
            decision=DECISION_DELETE,
            bucket=BUCKET_LIVE,
            reason=forged["reason"],
            checks=forged["checks"],
        )
        with pytest.raises(AssertionError, match="LIVE records decided to delete"):
            assert_invariants([bad])

    def test_invariants_reject_a_delete_with_a_failing_check(self):
        decision = decide()
        tampered = type(decision)(
            scholarship_id=decision.scholarship_id,
            decision=DECISION_DELETE,
            bucket=BUCKET_DELETE,
            reason=decision.reason,
            checks={**decision.checks, "retention_satisfied": False},
        )
        with pytest.raises(AssertionError, match="failing check"):
            assert_invariants([tampered])
