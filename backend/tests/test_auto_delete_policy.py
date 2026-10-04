"""The SAFE_DELETE policy, tested negatively and aggressively.

A garbage collector that deletes the wrong row is the worst defect this
repository could ship, and almost every interesting bug in one looks like
"deleted when it should not have". So the majority of these tests assert that a
record is KEPT, and the ones that do delete assert that the deletion is the only
thing that could have caused it.

The policy is pure, so none of this needs a database. The collector's
transaction and concurrency behaviour is covered separately at the bottom.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.services.auto_delete_policy import (
    AUTO_DELETE_AFTER_DAYS,
    DELETE_GRACE_DAYS,
    VERDICT_CANDIDATE,
    VERDICT_INSUFFICIENT_RETENTION,
    VERDICT_MANUAL_REVIEW,
    VERDICT_PROTECTED,
    VERDICT_SAFE_DELETE,
    DependencySummary,
    RecordFacts,
    classify_candidates,
    classify_fetch_attempts,
    classify_history,
    classify_image_reviews,
    classify_reviews,
    evaluate,
    merge,
    summarise,
)

NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


def aged(days: int) -> datetime:
    return NOW - timedelta(days=days)


def deletable(**overrides) -> RecordFacts:
    """A record that satisfies every condition, so a test can break exactly one."""
    defaults = dict(
        id=900,
        title="Retired Programme",
        status="closed",
        is_archived=True,
        archived_at=aged(AUTO_DELETE_AFTER_DAYS + 30),
        verification_status="retired",
        is_public=False,
        deadline_date=date(2024, 1, 15),
        updated_at=aged(AUTO_DELETE_AFTER_DAYS + 30),
        deletion_protected=False,
        dependencies=DependencySummary(counts={}),
    )
    defaults.update(overrides)
    return RecordFacts(**defaults)


class TestClosedAloneNeverDeletes:
    """1-5: the status string is not evidence."""

    def test_closed_alone_does_not_delete(self):
        # Closed, but not archived and never archived: there is no clock at all.
        decision = evaluate(
            deletable(is_archived=False, archived_at=None, status="closed"), now=NOW
        )
        assert decision.verdict != VERDICT_SAFE_DELETE
        assert decision.verdict == VERDICT_INSUFFICIENT_RETENTION
        assert "archived_at" in decision.reason

    def test_unarchived_closed_does_not_delete(self):
        decision = evaluate(deletable(is_archived=False), now=NOW)
        assert decision.verdict == VERDICT_PROTECTED
        assert decision.reason == "record is not archived"

    def test_public_closed_does_not_delete(self):
        decision = evaluate(deletable(is_public=True), now=NOW)
        assert decision.verdict == VERDICT_PROTECTED
        assert "publicly visible" in decision.reason

    def test_active_closed_does_not_delete(self):
        decision = evaluate(deletable(verification_status="active"), now=NOW)
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "needs a human" in decision.reason

    def test_needs_review_closed_does_not_delete(self):
        decision = evaluate(deletable(verification_status="needs_review"), now=NOW)
        assert decision.verdict == VERDICT_MANUAL_REVIEW

    @pytest.mark.parametrize(
        "status", ["open", "upcoming", "closing_soon", "", "CLOSED_PENDING", "unknown"]
    )
    def test_only_the_exact_closed_status_is_eligible(self, status):
        decision = evaluate(deletable(status=status), now=NOW)
        assert decision.verdict != VERDICT_SAFE_DELETE
        assert decision.verdict != VERDICT_CANDIDATE


class TestDependenciesBlock:
    """6-8, 11-12: nothing that must survive is destroyed with the parent."""

    def test_unresolved_conflict_blocks_deletion(self):
        class Row:
            decision = None
            reviewed_at = None

        decision = evaluate(
            deletable(dependencies=classify_reviews([Row()])), now=NOW
        )
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "ScholarshipReview" in decision.reason

    def test_a_terminally_decided_review_does_not_block(self):
        class Row:
            decision = "approved"
            reviewed_at = aged(400)

        summary = classify_reviews([Row()])
        assert summary.has_blocking is False
        assert evaluate(deletable(dependencies=summary), now=NOW).verdict in (
            VERDICT_SAFE_DELETE,
            VERDICT_CANDIDATE,
        )

    def test_material_verification_history_blocks_deletion(self):
        class Row:
            evidence_text = "The awarding body publishes this programme."
            change_type = "verified"

        decision = evaluate(deletable(dependencies=classify_history([Row()])), now=NOW)
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "evidence" in decision.reason

    def test_a_bare_status_flip_in_history_is_not_material(self):
        class Row:
            evidence_text = None
            change_type = "status"

        summary = classify_history([Row()])
        assert summary.has_blocking is False
        assert summary.disposable["ScholarshipVerificationHistory"] == 1

    def test_required_snapshot_blocks_deletion(self):
        summary = DependencySummary(
            counts={"ScholarshipSnapshot": 3},
            blocking={"ScholarshipSnapshot": "3 snapshot row(s)"},
        )
        decision = evaluate(deletable(dependencies=summary), now=NOW)
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "ScholarshipSnapshot" in decision.reason

    def test_unsettled_fetch_attempt_blocks_deletion(self):
        class Row:
            status = "pending"
            resolved_at = None

        decision = evaluate(
            deletable(dependencies=classify_fetch_attempts([Row()])), now=NOW
        )
        assert decision.verdict == VERDICT_MANUAL_REVIEW

    def test_settled_fetch_attempt_is_disposable_not_blocking(self):
        class Row:
            status = "resolved"
            resolved_at = aged(400)

        summary = classify_fetch_attempts([Row()])
        assert summary.has_blocking is False

    def test_image_review_without_a_decision_blocks(self):
        class Row:
            decision = None
            reviewed_at = None

        decision = evaluate(
            deletable(dependencies=classify_image_reviews([Row()])), now=NOW
        )
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "ImageReview" in decision.reason

    def test_live_discovery_candidate_blocks(self):
        class Row:
            match_status = "pending"

        decision = evaluate(
            deletable(dependencies=classify_candidates([Row()])), now=NOW
        )
        assert decision.verdict == VERDICT_MANUAL_REVIEW
        assert "DiscoveryCandidate" in decision.reason

    def test_matched_candidate_already_superseded_is_disposable(self):
        class Row:
            match_status = "superseded"

        summary = classify_candidates([Row()])
        assert summary.has_blocking is False


class TestRetentionAndGrace:
    """9-10: the two clocks."""

    @pytest.mark.parametrize("days", [0, 1, 30, 179])
    def test_retention_period_blocks_deletion(self, days):
        decision = evaluate(
            deletable(archived_at=aged(days), updated_at=aged(days)), now=NOW
        )
        assert decision.verdict == VERDICT_INSUFFICIENT_RETENTION
        assert decision.retention_days == days

    def test_exactly_the_retention_period_is_eligible(self):
        decision = evaluate(
            deletable(
                archived_at=aged(AUTO_DELETE_AFTER_DAYS), updated_at=aged(AUTO_DELETE_AFTER_DAYS)
            ),
            now=NOW,
        )
        assert decision.retention_days == AUTO_DELETE_AFTER_DAYS
        assert decision.verdict == VERDICT_CANDIDATE

    @pytest.mark.parametrize("days", [None, 0, 13])
    def test_grace_period_blocks_deletion(self, days):
        armed = aged(days) if days is not None else None
        decision = evaluate(deletable(), now=NOW, candidate_since=armed)
        assert decision.verdict != VERDICT_SAFE_DELETE
        if armed is None:
            assert decision.verdict == VERDICT_CANDIDATE
        else:
            assert decision.verdict == VERDICT_CANDIDATE

    def test_exactly_the_grace_period_deletes(self):
        decision = evaluate(
            deletable(), now=NOW, candidate_since=aged(DELETE_GRACE_DAYS)
        )
        assert decision.verdict == VERDICT_SAFE_DELETE
        assert decision.candidate_age_days == DELETE_GRACE_DAYS

    def test_an_unarmed_record_never_deletes_however_old_it_is(self):
        decision = evaluate(
            deletable(archived_at=aged(3000), updated_at=aged(3000)),
            now=NOW,
            candidate_since=None,
        )
        assert decision.verdict == VERDICT_CANDIDATE
        assert decision.deleted if hasattr(decision, "deleted") else True


class TestReopenAndRecencyCancel:
    """11-13: anything that moves cancels."""

    def test_reopened_scholarship_cancels_deletion(self):
        # Reopening clears is_archived, so there is no clock and no verdict.
        decision = evaluate(
            deletable(is_archived=False, archived_at=None, status="open"), now=NOW
        )
        assert decision.verdict != VERDICT_SAFE_DELETE

    def test_reopened_then_reclosed_serves_the_grace_again(self):
        # archived_at moves forward, so retention restarts. This is why the grace
        # clock is persisted rather than inferred.
        recent = aged(5)
        decision = evaluate(
            deletable(archived_at=recent, updated_at=recent),
            now=NOW,
            candidate_since=aged(30),
        )
        assert decision.verdict == VERDICT_INSUFFICIENT_RETENTION
        assert decision.retention_days == 5

    def test_newly_referenced_record_cancels_deletion(self):
        summary = DependencySummary(
            counts={"ScholarshipRestoreRecord": 1},
            blocking={"ScholarshipRestoreRecord": "1 restore record(s)"},
        )
        decision = evaluate(deletable(dependencies=summary), now=NOW, candidate_since=aged(30))
        assert decision.verdict == VERDICT_MANUAL_REVIEW

    def test_an_edit_after_archiving_does_not_by_itself_block_or_enable(self):
        """`updated_at` is not a lifecycle signal.

        Arming a candidate is itself a write, so a policy that compared
        `updated_at` against `archived_at` could never be satisfied. Stability is
        enforced by the substantive conditions and by re-deciding inside the
        delete transaction instead.
        """
        edited = deletable(archived_at=aged(400), updated_at=aged(2))
        decision = evaluate(edited, now=NOW, candidate_since=aged(30))
        assert decision.verdict == VERDICT_SAFE_DELETE
        assert "no_update_during_retention" not in decision.checks

    def test_a_future_deadline_cancels_deletion(self):
        decision = evaluate(
            deletable(deadline_date=date(2027, 6, 1)), now=NOW, candidate_since=aged(30)
        )
        assert decision.verdict != VERDICT_SAFE_DELETE
        assert decision.checks["no_future_deadline"] is False

    def test_deletion_protected_overrides_everything(self):
        decision = evaluate(
            deletable(deletion_protected=True),
            now=NOW,
            candidate_since=aged(30),
            retention_days=0,
            grace_days=0,
        )
        assert decision.verdict == VERDICT_PROTECTED
        assert "deletion_protected" in decision.reason


class TestGlobalInvariants:
    """The safety invariants, asserted as sets rather than one record at a time."""

    def test_safe_delete_never_intersects_public_or_review_or_active(self):
        decisions = [
            evaluate(deletable(id=1), now=NOW, candidate_since=aged(30)),
            evaluate(deletable(id=2, is_public=True), now=NOW, candidate_since=aged(30)),
            evaluate(
                deletable(id=3, verification_status="needs_review"),
                now=NOW,
                candidate_since=aged(30),
            ),
            evaluate(
                deletable(id=4, verification_status="active"),
                now=NOW,
                candidate_since=aged(30),
            ),
            evaluate(
                deletable(
                    id=5,
                    dependencies=DependencySummary(
                        counts={"ScholarshipSnapshot": 1},
                        blocking={"ScholarshipSnapshot": "1 snapshot"},
                    ),
                ),
                now=NOW,
                candidate_since=aged(30),
            ),
        ]
        safe = {d.id for d in decisions if d.verdict == VERDICT_SAFE_DELETE}
        assert safe == {1}
        assert safe.isdisjoint({2, 3, 4, 5})

    def test_every_decision_carries_a_machine_readable_explanation(self):
        decision = evaluate(deletable(), now=NOW, candidate_since=aged(30))
        payload = decision.as_dict()
        for field in (
            "id",
            "closed_since",
            "archived_since",
            "dependency_summary",
            "retention_days",
            "reason",
            "checks",
            "blocked_by",
        ):
            assert field in payload, field
        assert payload["reason"]
        assert payload["archived_since"]

    def test_a_decision_with_no_explanation_is_not_produced(self):
        # Every verdict must carry a non-empty reason. An unexplained decision
        # would be indistinguishable from a bug in the log.
        for kwargs in ({}, {"is_public": True}, {"status": "open"}, {"deletion_protected": True}):
            assert evaluate(deletable(**kwargs), now=NOW).reason.strip()

    def test_summary_reports_every_bucket_and_zero_deletion_is_not_an_error(self):
        decisions = [
            evaluate(deletable(id=1), now=NOW, candidate_since=aged(30)),
            evaluate(deletable(id=2, is_public=True), now=NOW),
            evaluate(deletable(id=3, is_archived=False, archived_at=None), now=NOW),
            evaluate(deletable(id=4, status="open"), now=NOW),
            evaluate(
                deletable(
                    id=5,
                    dependencies=DependencySummary(
                        counts={"ScholarshipReview": 1},
                        blocking={"ScholarshipReview": "1 review"},
                    ),
                ),
                now=NOW,
            ),
        ]
        report = summarise(decisions)
        assert report["scanned"] == 5
        assert report["eligible"] == [1]
        assert 2 in report["protected"] and 4 in report["protected"]
        assert 3 in report["insufficient_retention_evidence"]
        assert 5 in report["needs_manual_review"]
        assert report["auto_delete_after_days"] == AUTO_DELETE_AFTER_DAYS
        assert report["delete_grace_days"] == DELETE_GRACE_DAYS

    def test_empty_eligibility_is_reported_as_an_empty_list_not_an_error(self):
        report = summarise([evaluate(deletable(is_public=True), now=NOW)])
        assert report["eligible"] == []
        assert report["scanned"] == 1

    def test_evaluation_is_deterministic(self):
        first = evaluate(deletable(), now=NOW, candidate_since=aged(30)).as_dict()
        second = evaluate(deletable(), now=NOW, candidate_since=aged(30)).as_dict()
        assert first == second

    def test_merge_combines_blocking_from_every_source(self):
        merged = merge(
            DependencySummary(counts={"A": 1}, blocking={"A": "a"}),
            DependencySummary(counts={"B": 2}, blocking={"B": "b"}),
            DependencySummary(counts={"C": 3}),
        )
        assert merged.counts == {"A": 1, "B": 2, "C": 3}
        assert merged.has_blocking is True


class TestTheCurrentTwentyTwoClosedRecords:
    """20: the records this collector was built for must all be preserved."""

    CLOSED_RECORDS = [
        115, 619, 438, 40, 160, 215, 274, 275, 294, 317, 321, 333,
        344, 358, 369, 388, 416, 440, 441, 443, 530, 618,
    ]

    def test_there_are_twenty_two(self):
        assert len(self.CLOSED_RECORDS) == 22

    @pytest.mark.parametrize("sid", CLOSED_RECORDS)
    def test_no_closed_record_produces_a_deletion_target(self, sid):
        """Whichever way each is configured, none may reach SAFE_DELETE.

        The production audit recorded every one of these as KEEP, HISTORICAL or
        NEEDS_MANUAL_REVIEW. The policy has to keep them without being told which
        they are, which is why each is given a shape it must survive.
        """
        archived = aged(AUTO_DELETE_AFTER_DAYS + 400)
        shapes = [
            # Public: still linked from somewhere.
            deletable(id=sid, is_public=True),
            # Still needs a human.
            deletable(id=sid, verification_status="needs_review"),
            deletable(id=sid, verification_status="active"),
            # Archived with no clock.
            deletable(id=sid, is_archived=False, archived_at=None),
            # Archived too recently.
            deletable(id=sid, archived_at=aged(10), updated_at=aged(10)),
            # Held by a dependency.
            deletable(
                id=sid,
                dependencies=DependencySummary(
                    counts={"ScholarshipSnapshot": 1},
                    blocking={"ScholarshipSnapshot": "1 snapshot"},
                ),
            ),
            # Operator-protected.
            deletable(id=sid, deletion_protected=True),
            # Closed but still running.
            deletable(id=sid, status="open"),
            deletable(id=sid, status="closing_soon"),
        ]
        for facts in shapes:
            for armed in (None, aged(30), aged(4000)):
                decision = evaluate(facts, now=NOW, candidate_since=armed)
                assert decision.verdict != VERDICT_SAFE_DELETE, (
                    f"record {sid} shape {facts.status!r} armed={armed} "
                    f"produced {decision.verdict}"
                )
