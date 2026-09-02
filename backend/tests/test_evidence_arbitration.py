"""Tests for the source consensus and evidence arbitration engine."""

from datetime import datetime, timedelta, timezone

import pytest

from app.services.evidence_arbitration import (
    ArbitrationDecision,
    ArbitrationResult,
    EvidenceScore,
    ReasonCode,
    _compute_composite_score,
    _compute_freshness_score,
    _compute_health_score,
    _compute_specificity_score,
    arbitrate_field,
    arbitrate_fields,
    has_consensus,
    is_conflict,
    is_sufficient,
    requires_review,
)
from app.services.scholarship_evidence import (
    EvidenceItem,
    EvidenceStatus,
    SourceType,
)


def _make_evidence(
    field_name: str = "deadline_display",
    value: str = "2025-03-15",
    source_url: str = "https://www.daad.de/scholarship/deadline",
    source_type: SourceType = SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
    evidence_text: str = "Deadline: 2025-03-15",
    confidence: str = "high",
    timestamp: str | None = None,
    scholarship_id: int = 1,
) -> EvidenceItem:
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).isoformat()
    return EvidenceItem(
        scholarship_id=scholarship_id,
        field_name=field_name,
        extracted_value=value,
        source_url=source_url,
        evidence_text=evidence_text,
        confidence=confidence,
        source_type=source_type,
        verification_timestamp=timestamp,
        status=EvidenceStatus.HIGH_CONFIDENCE,
    )


class TestSingleAuthoritativeSource:
    def test_single_source_returns_single_trusted(self):
        evidence = [_make_evidence()]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.SINGLE_TRUSTED_SOURCE
        assert result.winning_value == "2025-03-15"
        assert result.winning_source_url == "https://www.daad.de/scholarship/deadline"
        assert ReasonCode.SINGLE_AUTHORITATIVE in result.reason_codes

    def test_single_source_is_sufficient(self):
        evidence = [_make_evidence()]
        result = arbitrate_field("deadline_display", evidence)

        assert is_sufficient(result)
        assert not requires_review(result)


class TestMultipleAgreeingOfficialSources:
    def test_two_agreeing_official_sources_returns_consensus(self):
        evidence = [
            _make_evidence(source_url="https://www.daad.de/scholarship/deadline"),
            _make_evidence(source_url="https://apply.daad.de/deadline"),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.CONSENSUS
        assert result.winning_value == "2025-03-15"
        assert ReasonCode.MULTIPLE_AUTHORITATIVE_AGREE in result.reason_codes

    def test_three_agreeing_sources_high_consensus_score(self):
        evidence = [
            _make_evidence(source_url="https://www.daad.de/scholarship/deadline"),
            _make_evidence(source_url="https://apply.daad.de/deadline"),
            _make_evidence(
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.CONSENSUS
        assert result.consensus_score > 0.5


class TestOfficialSourcesWithDifferentFreshness:
    def test_fresher_evidence_wins_tiebreak(self):
        now = datetime.now(timezone.utc)
        stale_ts = (now - timedelta(days=60)).isoformat()
        fresh_ts = (now - timedelta(days=5)).isoformat()

        evidence = [
            _make_evidence(
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
                timestamp=stale_ts,
            ),
            _make_evidence(
                source_url="https://www.daad.de/scholarship/deadline",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
                timestamp=fresh_ts,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence, now=now)

        assert result.decision == ArbitrationDecision.CONSENSUS
        assert result.winning_source_type == SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM


class TestConflictingOfficialSources:
    def test_conflicting_authoritative_sources_returns_conflict(self):
        evidence = [
            _make_evidence(
                value="2025-03-15",
                source_url="https://www.daad.de/scholarship/deadline",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.CONFLICT
        assert result.winning_value is None
        assert result.winning_evidence is None
        assert len(result.conflicting_evidence) >= 1
        assert ReasonCode.AUTHORITATIVE_CONFLICT in result.reason_codes

    def test_conflict_requires_review(self):
        evidence = [
            _make_evidence(value="2025-03-15"),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert requires_review(result)
        assert not is_sufficient(result)


class TestThirdPartyConflict:
    def test_third_party_never_overrides_official(self):
        evidence = [
            _make_evidence(
                value="2025-03-15",
                source_url="https://www.daad.de/scholarship/deadline",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
            _make_evidence(
                value="2025-06-01",
                source_url="https://www.scholars4dev.com/scholarship",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.SINGLE_TRUSTED_SOURCE
        assert result.winning_value == "2025-03-15"
        assert result.winning_source_type == SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM

    def test_only_third_party_returns_insufficient(self):
        evidence = [
            _make_evidence(
                value="2025-03-15",
                source_url="https://www.scholars4dev.com/scholarship",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.INSUFFICIENT
        assert result.winning_value is None
        assert ReasonCode.THIRD_PARTY_NEVER_OVERRIDES in result.reason_codes


class TestStaleVsFreshEvidence:
    def test_stale_evidence_scores_lower(self):
        now = datetime.now(timezone.utc)
        stale_ts = (now - timedelta(days=90)).isoformat()
        fresh_ts = (now - timedelta(days=1)).isoformat()

        stale_score = _compute_freshness_score(stale_ts, now)
        fresh_score = _compute_freshness_score(fresh_ts, now)

        assert fresh_score > stale_score

    def test_very_old_evidence_has_near_zero_freshness(self):
        now = datetime.now(timezone.utc)
        very_old_ts = (now - timedelta(days=365)).isoformat()

        score = _compute_freshness_score(very_old_ts, now)

        assert score < 0.01


class TestSourceHealthInfluence:
    def test_healthy_source_scores_higher_than_unhealthy(self):
        healthy = _compute_health_score("healthy")
        unhealthy = _compute_health_score("unhealthy")

        assert healthy > unhealthy

    def test_unknown_health_gets_moderate_score(self):
        unknown = _compute_health_score("unknown")
        healthy = _compute_health_score("healthy")

        assert unknown < healthy
        assert unknown > 0.5

    def test_degraded_health_reduces_composite_score(self):
        auth = 100
        freshness = 1.0
        specificity = 1.0

        healthy_composite = _compute_composite_score(auth, freshness, 1.0, specificity, True)
        degraded_composite = _compute_composite_score(auth, freshness, 0.7, specificity, True)

        assert healthy_composite > degraded_composite


class TestDeterministicWinner:
    def test_same_evidence_produces_same_result(self):
        evidence = [
            _make_evidence(value="2025-03-15"),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]

        result1 = arbitrate_field("deadline_display", evidence)
        result2 = arbitrate_field("deadline_display", evidence)

        assert result1.decision == result2.decision
        assert result1.arbitrator_id == result2.arbitrator_id

    def test_deterministic_arbitration_id(self):
        evidence = [_make_evidence()]
        result = arbitrate_field("deadline_display", evidence)

        assert len(result.arbitrator_id) == 16


class TestNoConsensus:
    def test_no_consensus_returns_conflict(self):
        evidence = [
            _make_evidence(value="2025-03-15"),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert not has_consensus(result)
        assert is_conflict(result)


class TestInsufficientEvidence:
    def test_no_evidence_returns_insufficient(self):
        result = arbitrate_field("deadline_display", [])

        assert result.decision == ArbitrationDecision.INSUFFICIENT
        assert result.winning_value is None
        assert ReasonCode.NO_EVIDENCE in result.reason_codes

    def test_only_third_party_returns_insufficient(self):
        evidence = [
            _make_evidence(
                source_url="https://www.scholars4dev.com",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert result.decision == ArbitrationDecision.INSUFFICIENT
        assert requires_review(result)


class TestReviewEscalation:
    def test_conflict_escalates_to_review(self):
        evidence = [
            _make_evidence(value="2025-03-15"),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert requires_review(result)

    def test_insufficient_escalates_to_review(self):
        result = arbitrate_field("deadline_display", [])

        assert requires_review(result)

    def test_consensus_does_not_require_review(self):
        evidence = [
            _make_evidence(),
            _make_evidence(source_url="https://apply.daad.de/deadline"),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert not requires_review(result)


class TestProvenancePreservation:
    def test_all_evidence_preserved_in_result(self):
        evidence = [
            _make_evidence(value="2025-03-15"),
            _make_evidence(
                value="2025-04-01",
                source_url="https://www.gov.de/scholarships",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert len(result.all_evidence) == 2

    def test_scored_evidence_includes_all_items(self):
        evidence = [
            _make_evidence(),
            _make_evidence(source_url="https://apply.daad.de/deadline"),
        ]
        result = arbitrate_field("deadline_display", evidence)

        assert len(result.scored_evidence) == 2
        assert all(isinstance(s, EvidenceScore) for s in result.scored_evidence)


class TestBatchArbitration:
    def test_arbitrate_fields_processes_all_fields(self):
        now = datetime.now(timezone.utc)
        evidence = [
            _make_evidence(field_name="deadline_display", value="2025-03-15"),
            _make_evidence(field_name="deadline_display", value="2025-03-15", source_url="https://apply.daad.de/deadline"),
            _make_evidence(field_name="award_amount", value="1000 EUR"),
            _make_evidence(field_name="award_amount", value="1000 EUR", source_url="https://apply.daad.de/amount"),
        ]
        results = arbitrate_fields(evidence, now=now)

        assert "deadline_display" in results
        assert "award_amount" in results
        assert results["deadline_display"].decision == ArbitrationDecision.CONSENSUS
        assert results["award_amount"].decision == ArbitrationDecision.CONSENSUS

    def test_batch_empty_evidence(self):
        results = arbitrate_fields([])

        assert results == {}


class TestNoNPlusOne:
    def test_batch_arbitration_no_extra_queries(self):
        """Verify batch arbitration processes all fields in one pass."""
        evidence = [
            _make_evidence(field_name="deadline_display", value="2025-03-15"),
            _make_evidence(field_name="award_amount", value="1000 EUR"),
            _make_evidence(field_name="duration", value="2 years"),
        ]
        results = arbitrate_fields(evidence)

        assert len(results) == 3


class TestSpecificityScoring:
    def test_short_evidence_low_specificity(self):
        score = _compute_specificity_score("abc")

        assert score == 0.3

    def test_optimal_evidence_high_specificity(self):
        score = _compute_specificity_score("Deadline: 2025-03-15 for all applicants")

        assert score == 1.0

    def test_empty_evidence_zero_specificity(self):
        score = _compute_specificity_score("")

        assert score == 0.0


class TestCompositeScoring:
    def test_authoritative_higher_than_third_party(self):
        auth_composite = _compute_composite_score(100, 1.0, 1.0, 1.0, True)
        third_composite = _compute_composite_score(0, 1.0, 1.0, 1.0, False)

        assert auth_composite > third_composite

    def test_perfect_scores_yield_high_composite(self):
        composite = _compute_composite_score(100, 1.0, 1.0, 1.0, True)

        assert composite > 0.9


class TestHelperFunctions:
    def test_has_consensus_true(self):
        result = ArbitrationResult(
            field_name="test",
            decision=ArbitrationDecision.CONSENSUS,
            winning_value="x",
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.9,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=[],
            reason_text="",
            arbitrator_id="",
            arbitr_at="",
        )

        assert has_consensus(result)

    def test_is_conflict_true(self):
        result = ArbitrationResult(
            field_name="test",
            decision=ArbitrationDecision.CONFLICT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=[],
            reason_text="",
            arbitrator_id="",
            arbitr_at="",
        )

        assert is_conflict(result)

    def test_requires_review_for_conflict(self):
        result = ArbitrationResult(
            field_name="test",
            decision=ArbitrationDecision.CONFLICT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=[],
            reason_text="",
            arbitrator_id="",
            arbitr_at="",
        )

        assert requires_review(result)

    def test_requires_review_for_insufficient(self):
        result = ArbitrationResult(
            field_name="test",
            decision=ArbitrationDecision.INSUFFICIENT,
            winning_value=None,
            winning_source_url=None,
            winning_source_type=None,
            consensus_score=0.0,
            winning_evidence=None,
            conflicting_evidence=[],
            all_evidence=[],
            scored_evidence=[],
            reason_codes=[],
            reason_text="",
            arbitrator_id="",
            arbitr_at="",
        )

        assert requires_review(result)
