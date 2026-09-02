"""Unit tests for the confidence and cross-source verification engine."""

from __future__ import annotations

import unittest

from app.services.scholarship_evidence import (
    EvidenceItem,
    SourceType,
)
from app.services.verification_confidence import (
    ConfidenceLevel,
    FieldConfidenceResult,
    VerificationAssessment,
    VerificationState,
    assess_confidence,
    assess_field_confidence,
    can_field_auto_update,
)


def _make_evidence_item(
    field_name: str,
    value: str,
    source_url: str,
    evidence_text: str,
    confidence: str | None = "high",
    source_type: SourceType | None = None,
) -> EvidenceItem:
    """Helper to create evidence items for testing."""
    if source_type is None:
        # Infer source type from URL
        if "gov" in source_url or "bund" in source_url or "admin.ch" in source_url:
            source_type = SourceType.OFFICIAL_GOVERNMENT
        elif ".ac." in source_url or ".edu" in source_url or "uni-" in source_url:
            source_type = SourceType.OFFICIAL_UNIVERSITY
        elif "daad" in source_url or "campusfrance" in source_url:
            source_type = SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM
        elif "apply." in source_url:
            source_type = SourceType.OFFICIAL_APPLICATION_PORTAL
        else:
            source_type = SourceType.THIRD_PARTY

    return EvidenceItem(
        scholarship_id=1,
        field_name=field_name,
        extracted_value=value,
        source_url=source_url,
        evidence_text=evidence_text,
        confidence=confidence,
        source_type=source_type,
        verification_timestamp="2026-08-31T12:00:00+00:00",
    )


class TestSingleHighConfidenceOfficialEvidence(unittest.TestCase):
    """Test 1: Single high-confidence official evidence."""

    def test_single_high_confidence_government(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 15, 2027",
                source_url="https://www.gov.uk/scholarships/chevening",
                evidence_text="Deadline: January 15, 2027",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.verification_state, VerificationState.VERIFIED)
        self.assertEqual(result.source_count, 1)
        self.assertEqual(result.authoritative_source_count, 1)
        self.assertTrue(result.is_update_candidate)

    def test_single_high_confidence_university(self):
        items = [
            _make_evidence_item(
                field_name="duration",
                value="2 years",
                source_url="https://www.ox.ac.uk/masters",
                evidence_text="Duration: 2 years",
                confidence="high",
                source_type=SourceType.OFFICIAL_UNIVERSITY,
            ),
        ]
        result = assess_field_confidence(1, "duration", items)

        self.assertIn(result.confidence, [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM])
        self.assertNotEqual(result.verification_state, VerificationState.UNSUPPORTED)
        self.assertTrue(result.is_update_candidate)

    def test_single_high_confidence_scholarship_program(self):
        items = [
            _make_evidence_item(
                field_name="award_amount",
                value="€850 per month",
                source_url="https://www.daad.de/en/stipendium",
                evidence_text="Award: €850 per month",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
        ]
        result = assess_field_confidence(1, "award_amount", items)

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.verification_state, VerificationState.VERIFIED)
        self.assertTrue(result.is_update_candidate)


class TestMultipleAgreeingOfficialSources(unittest.TestCase):
    """Test 2: Multiple agreeing official sources."""

    def test_two_government_sources_agree(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="January 15, 2027",
                source_url="https://www.gouv.fr/bourses",
                evidence_text="Apply by January 15, 2027",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.source_count, 2)
        self.assertEqual(result.authoritative_source_count, 2)
        # Two agreeing authoritative sources should be at least MEDIUM (or HIGH)
        self.assertIn(result.confidence, [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH])
        self.assertEqual(result.conflicting_source_count, 0)
        self.assertTrue(result.is_update_candidate)
        self.assertEqual(result.conflicting_source_count, 0)

    def test_university_and_portal_agree(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-03-01",
                source_url="https://www.tokyo.ac.jp/en/admissions",
                evidence_text="Deadline: 2027-03-01",
                confidence="high",
                source_type=SourceType.OFFICIAL_UNIVERSITY,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="March 1, 2027",
                source_url="https://apply.jasso.go.jp/portal",
                evidence_text="Applications close on March 1, 2027",
                confidence="high",
                source_type=SourceType.OFFICIAL_APPLICATION_PORTAL,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.source_count, 2)
        self.assertEqual(result.conflicting_source_count, 0)
        self.assertTrue(result.is_update_candidate)


class TestConflictingOfficialSources(unittest.TestCase):
    """Test 3: Conflicting official sources."""

    def test_two_authoritative_sources_different_dates(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-20",
                source_url="https://www.gouv.fr/bourses",
                evidence_text="Deadline: 2027-01-20",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.confidence, ConfidenceLevel.CONFLICT)
        self.assertEqual(result.verification_state, VerificationState.CONFLICT)
        self.assertGreater(result.conflicting_source_count, 0)
        self.assertFalse(result.is_update_candidate)

    def test_different_deadline_values(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="December 1, 2026",
                source_url="https://www.daad.de/en/schedule",
                evidence_text="Deadline: December 1, 2026",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="January 31, 2027",
                source_url="https://apply.daad.de/portal",
                evidence_text="Applications must be received by January 31, 2027",
                confidence="high",
                source_type=SourceType.OFFICIAL_APPLICATION_PORTAL,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.confidence, ConfidenceLevel.CONFLICT)
        self.assertFalse(result.is_update_candidate)


class TestThirdPartySource(unittest.TestCase):
    """Test 4: Third-party source."""

    def test_third_party_source_not_authoritative(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 2027",
                source_url="https://www.scholars4dev.com/scholarship",
                evidence_text="Deadline: January 2027",
                confidence="high",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.authoritative_source_count, 0)
        self.assertEqual(result.confidence, ConfidenceLevel.LOW)
        self.assertEqual(result.verification_state, VerificationState.UNSUPPORTED)
        self.assertFalse(result.is_update_candidate)

    def test_third_party_with_official_prefers_official(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 2027",
                source_url="https://www.scholars4dev.com/scholarship",
                evidence_text="Deadline: January 2027",
                confidence="high",
                source_type=SourceType.THIRD_PARTY,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Should have at least one authoritative source
        self.assertGreater(result.authoritative_source_count, 0)


class TestMissingEvidence(unittest.TestCase):
    """Test 5: Missing evidence."""

    def test_no_evidence_items(self):
        result = assess_field_confidence(1, "deadline", [])

        self.assertEqual(result.source_count, 0)
        self.assertEqual(result.verification_state, VerificationState.UNSUPPORTED)
        self.assertFalse(result.is_update_candidate)

    def test_empty_evidence_text(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 2027",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Empty evidence should reduce quality
        self.assertLess(result.quality_score, 50)


class TestLowExtractorConfidence(unittest.TestCase):
    """Test 6: Low extractor confidence."""

    def test_low_confidence_extractor(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 2027",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: January 2027",
                confidence="low",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertIn(result.confidence, [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM])
        # Low extractor confidence should prevent automatic update
        self.assertFalse(result.is_update_candidate)


class TestMediumConfidence(unittest.TestCase):
    """Test 7: Medium confidence."""

    def test_medium_extractor_confidence_with_good_evidence(self):
        items = [
            _make_evidence_item(
                field_name="duration",
                value="24 months",
                source_url="https://www.ox.ac.uk/programme",
                evidence_text="Duration: 24 months",
                confidence="medium",
                source_type=SourceType.OFFICIAL_UNIVERSITY,
            ),
        ]
        result = assess_field_confidence(1, "duration", items)

        # Medium confidence with good evidence should be at least MEDIUM
        self.assertIn(result.confidence, [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH])


class TestCurrentCycleEvidence(unittest.TestCase):
    """Test 8: Current-cycle evidence."""

    def test_evidence_with_current_cycle_year(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="January 15, 2027",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Academic year 2026-27 deadline: January 15, 2027",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items, current_cycle="2026-27")

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertTrue(result.is_update_candidate)


class TestHistoricalEvidence(unittest.TestCase):
    """Test 9: Historical evidence."""

    def test_evidence_with_old_cycle_year(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="December 1, 2024",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Academic year 2024-25 deadline: December 1, 2024",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items, current_cycle="2026-27")

        # Historical evidence should not validate current cycle
        self.assertIn(result.confidence, [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM])
        self.assertFalse(result.is_update_candidate)


class TestExactDeadlineStrongEvidence(unittest.TestCase):
    """Test 10: Exact deadline with strong evidence."""

    def test_exact_date_with_direct_evidence(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-03-15",
                source_url="https://www.sbfi.admin.ch/scholarships",
                evidence_text="Applications close on 15 March 2027.",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertEqual(result.verification_state, VerificationState.VERIFIED)
        self.assertTrue(result.is_update_candidate)


class TestVagueDeadline(unittest.TestCase):
    """Test 11: Vague deadline."""

    def test_usually_january_not_exact(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="Usually January",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Applications usually close in January.",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Vague date should not be high confidence
        self.assertIn(result.confidence, [ConfidenceLevel.LOW, ConfidenceLevel.MEDIUM])
        self.assertFalse(result.is_update_candidate)

    def test_closes_soon_not_specific(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="Closing soon",
                source_url="https://www.example.com/scholarship",
                evidence_text="Applications close soon.",
                confidence="medium",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertFalse(result.is_update_candidate)


class TestRollingDeadline(unittest.TestCase):
    """Test 12: Rolling deadline."""

    def test_rolling_deadline_exact(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="rolling",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Applications are accepted on a rolling basis.",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Rolling is a valid semantic value when explicitly stated
        self.assertNotEqual(result.verification_state, VerificationState.UNSUPPORTED)
        self.assertIn(result.confidence, [ConfidenceLevel.MEDIUM, ConfidenceLevel.HIGH])

    def test_multiple_sources_agree_rolling(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="rolling",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Rolling admissions.",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="rolling",
                source_url="https://www.daad.de/en/",
                evidence_text="Applications accepted on a rolling basis.",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result.conflicting_source_count, 0)


class TestVariesByCountryDeadline(unittest.TestCase):
    """Test 13: Varies-by-country deadline."""

    def test_varies_by_country(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="varies by country",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline varies by country.",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Varies is valid when explicitly stated
        self.assertNotEqual(result.verification_state, VerificationState.UNSUPPORTED)


class TestMonetaryValueDirectEvidence(unittest.TestCase):
    """Test 14: Monetary value with direct evidence."""

    def test_exact_amount_with_currency(self):
        items = [
            _make_evidence_item(
                field_name="award_amount",
                value="€850 per month",
                source_url="https://www.daad.de/en/stipendium",
                evidence_text="Monthly stipend: €850 per month",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
        ]
        result = assess_field_confidence(1, "award_amount", items)

        self.assertEqual(result.confidence, ConfidenceLevel.HIGH)
        self.assertTrue(result.is_update_candidate)

    def test_amount_with_symbol(self):
        items = [
            _make_evidence_item(
                field_name="living_stipend",
                value="$2,000/month",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Living stipend: $2,000/month",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "living_stipend", items)

        self.assertIn(result.confidence, [ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM])
        self.assertGreater(result.quality_score, 0)


class TestUnsupportedField(unittest.TestCase):
    """Test 15: Unsupported field."""

    def test_no_evidence_for_field(self):
        result = assess_field_confidence(1, "nonexistent_field", [])

        self.assertEqual(result.verification_state, VerificationState.UNSUPPORTED)
        self.assertFalse(result.is_update_candidate)


class TestAuthoritativeSourceConflict(unittest.TestCase):
    """Test 16: Authoritative source conflict."""

    def test_highly_authoritative_sources_disagree(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-03-01",
                source_url="https://www.daad.de/en/",
                evidence_text="Deadline: 2027-03-01",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="2027-03-15",
                source_url="https://apply.daad.de/portal",
                evidence_text="Deadline: 2027-03-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_APPLICATION_PORTAL,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Even if one is more authoritative, disagreement = CONFLICT
        self.assertEqual(result.confidence, ConfidenceLevel.CONFLICT)
        self.assertFalse(result.is_update_candidate)


class TestDeterministicIdenticalInputs(unittest.TestCase):
    """Test 17: Deterministic identical inputs."""

    def test_same_input_same_output(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]

        result1 = assess_field_confidence(1, "deadline", items)
        result2 = assess_field_confidence(1, "deadline", items)

        self.assertEqual(result1.confidence, result2.confidence)
        self.assertEqual(result1.verification_state, result2.verification_state)
        self.assertEqual(result1.authority_score, result2.authority_score)
        self.assertEqual(result1.quality_score, result2.quality_score)

    def test_assessment_deterministic(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="duration",
                value="2 years",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Duration: 2 years",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]

        assessment1 = assess_confidence(1, items)
        assessment2 = assess_confidence(1, items)

        self.assertEqual(len(assessment1.field_results), len(assessment2.field_results))
        for r1, r2 in zip(assessment1.field_results, assessment2.field_results):
            self.assertEqual(r1.confidence, r2.confidence)
            self.assertEqual(r1.verification_state, r2.verification_state)


class TestAutomaticUpdateGate(unittest.TestCase):
    """Test 18: Automatic-update gate."""

    def test_high_confidence_official_passes_gate(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)
        can_update, reason = can_field_auto_update(result)

        self.assertTrue(can_update)
        self.assertIn("meets all criteria", reason)

    def test_low_confidence_fails_gate(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="sometime in 2027",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: sometime in 2027",
                confidence="low",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)
        can_update, reason = can_field_auto_update(result)

        self.assertFalse(can_update)

    def test_conflict_fails_gate(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="deadline",
                value="2027-02-15",
                source_url="https://www.gouv.fr/bourses",
                evidence_text="Deadline: 2027-02-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)
        can_update, reason = can_field_auto_update(result)

        self.assertFalse(can_update)


class TestIdentityConflictBlocksUpdate(unittest.TestCase):
    """Test 19: Identity conflict blocks update."""

    def test_identity_conflict_field_blocked(self):
        items = [
            _make_evidence_item(
                field_name="title",
                value="Different Scholarship Name",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Scholarship: Different Scholarship Name",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(
            1, "title", items, is_identity_conflict=True
        )

        self.assertFalse(result.is_update_candidate)
        self.assertIn("Identity conflict", result.reason)


class TestMultipleFieldsAssessedIndependently(unittest.TestCase):
    """Test 20: Multiple fields assessed independently."""

    def test_different_fields_different_confidence(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="award_amount",
                value="unknown",
                source_url="https://www.example.com/scholarship",
                evidence_text="",
                confidence="low",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]

        assessment = assess_confidence(1, items)

        self.assertEqual(len(assessment.field_results), 2)

        deadline_result = assessment.get_field_result("deadline")
        award_result = assessment.get_field_result("award_amount")

        self.assertIsNotNone(deadline_result)
        self.assertIsNotNone(award_result)

        # Deadline should be verifiable
        self.assertEqual(deadline_result.field_name, "deadline")
        self.assertTrue(deadline_result.is_update_candidate)

        # Award amount should not be verifiable
        self.assertEqual(award_result.field_name, "award_amount")
        self.assertFalse(award_result.is_update_candidate)

    def test_update_candidates_property(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Deadline: 2027-01-15",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="duration",
                value="2 years",
                source_url="https://www.gov.uk/scholarships",
                evidence_text="Duration: 2 years",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
            _make_evidence_item(
                field_name="award_amount",
                value="unknown",
                source_url="https://www.example.com",
                evidence_text="",
                confidence="low",
                source_type=SourceType.THIRD_PARTY,
            ),
        ]

        assessment = assess_confidence(1, items)

        # Only deadline and duration should be update candidates
        update_names = [f.field_name for f in assessment.update_candidates]
        self.assertIn("deadline", update_names)
        self.assertIn("duration", update_names)
        self.assertNotIn("award_amount", update_names)


class TestSourcePriority(unittest.TestCase):
    """Test source priority ordering."""

    def test_scholarship_program_higher_than_government(self):
        from app.services.verification_confidence import (
            _SOURCE_AUTHORITY_SCORES,
            _SOURCE_PRIORITY,
            SourceType,
        )

        # Scholarship program should have higher authority score
        self.assertGreater(
            _SOURCE_AUTHORITY_SCORES[SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM],
            _SOURCE_AUTHORITY_SCORES[SourceType.OFFICIAL_GOVERNMENT],
        )

        # Scholarship program should have higher priority (lower number)
        self.assertLess(
            _SOURCE_PRIORITY[SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM],
            _SOURCE_PRIORITY[SourceType.OFFICIAL_GOVERNMENT],
        )

    def test_third_party_lowest(self):
        from app.services.verification_confidence import (
            _SOURCE_AUTHORITY_SCORES,
            SourceType,
        )

        self.assertEqual(_SOURCE_AUTHORITY_SCORES[SourceType.THIRD_PARTY], 0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_none_value(self):
        items = [
            _make_evidence_item(
                field_name="deadline",
                value=None,
                source_url="https://www.gov.uk/scholarships",
                evidence_text="No deadline specified",
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # None value should still produce a result
        self.assertIsNotNone(result)
        self.assertEqual(result.value, None)

    def test_very_long_evidence_text(self):
        long_text = "Deadline: 2027-01-15. " * 100
        items = [
            _make_evidence_item(
                field_name="deadline",
                value="2027-01-15",
                source_url="https://www.gov.uk/scholarships",
                evidence_text=long_text,
                confidence="high",
                source_type=SourceType.OFFICIAL_GOVERNMENT,
            ),
        ]
        result = assess_field_confidence(1, "deadline", items)

        # Very long text should have reduced quality
        self.assertIsNotNone(result)

    def test_special_characters_in_value(self):
        items = [
            _make_evidence_item(
                field_name="award_amount",
                value="€1,234.56/month",
                source_url="https://www.daad.de/en/",
                evidence_text="Award: €1,234.56/month",
                confidence="high",
                source_type=SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
            ),
        ]
        result = assess_field_confidence(1, "award_amount", items)

        self.assertEqual(result.value, "€1,234.56/month")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
