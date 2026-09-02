"""Focused unit tests for the scholarship diff engine."""

from __future__ import annotations

import os
import sys
import types
import unittest
from uuid import uuid4

from pathlib import Path
import tempfile


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / f"scholarzone-diff-test-{uuid4().hex}.db"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{TEST_DATABASE_PATH.as_posix()}"
os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"


fake_scheduler = types.ModuleType("app.scheduler")
fake_scheduler.start_scheduler = lambda: None
fake_scheduler.mark_due_for_review = lambda: None
sys.modules["app.scheduler"] = fake_scheduler


from app.models import Scholarship  # noqa: E402
from app.services.scholarship_diff import (  # noqa: E402
    ChangeSet,
    FieldChange,
    FieldChangeType,
    diff_scholarship,
)
from app.services.scholarship_extractor import (  # noqa: E402
    ExtractionConfidence,
    ScholarshipExtractionResult,
)


def _make_scholarship(**overrides) -> Scholarship:
    base = dict(
        title="Test Scholarship",
        country="Test Country",
        degree="Master",
        funding="Fully Funded",
    )
    base.update(overrides)
    return Scholarship(**base)


def _make_extraction(**overrides) -> ScholarshipExtractionResult:
    return ScholarshipExtractionResult(**overrides)


class DiffEngineTests(unittest.TestCase):
    def test_identical_records_unchanged(self):
        scholarship = _make_scholarship(
            title="Test Scholarship",
            degree="Master",
            official_source="Test Provider",
            eligibility=["Must be enrolled"],
            duration="2 years",
            application_method=["Online"],
            deadline_display="October 15, 2026",
            status="open",
            application_link="https://example.com/apply",
        )
        extracted = _make_extraction(
            scholarship_name="Test Scholarship",
            degree_level="Master",
            provider="Test Provider",
            eligibility="Must be enrolled",
            duration="2 years",
            application_method="Online",
            deadline="October 15, 2026",
            status="open",
            application_url="https://example.com/apply",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.HIGH,
                "eligibility": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
                "application_method": ExtractionConfidence.HIGH,
                "deadline": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.HIGH,
                "application_url": ExtractionConfidence.HIGH,
            },
        )

        result = diff_scholarship(scholarship, extracted)

        self.assertIsInstance(result, ChangeSet)
        self.assertFalse(result.has_changes)
        self.assertFalse(result.identity_conflict)
        self.assertFalse(result.cycle_changed)
        self.assertFalse(result.is_new_scholarship)
        for change in result.changes:
            self.assertEqual(change.change_type, FieldChangeType.UNCHANGED)
        self.assertEqual(result.update_candidates, [])

    def test_whitespace_only_difference_unchanged(self):
        scholarship = _make_scholarship(title="Test Scholarship")
        extracted = _make_extraction(
            scholarship_name="  Test   Scholarship  ",
            confidence={"scholarship_name": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        title_change = next(c for c in result.changes if c.field == "title")
        self.assertEqual(title_change.change_type, FieldChangeType.UNCHANGED)

    def test_url_normalization_unchanged(self):
        scholarship = _make_scholarship(application_link="https://example.com/apply")
        extracted = _make_extraction(
            application_url="HTTPS://EXAMPLE.COM/APPLY",
            confidence={"application_url": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        link_change = next(c for c in result.changes if c.field == "application_link")
        self.assertEqual(link_change.change_type, FieldChangeType.UNCHANGED)

    def test_equivalent_date_representations_unchanged(self):
        scholarship = _make_scholarship(deadline_display="October 15, 2026")
        extracted = _make_extraction(
            deadline="  october   15,   2026  ",
            confidence={"deadline": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        deadline_change = next(c for c in result.changes if c.field == "deadline_display")
        self.assertEqual(deadline_change.change_type, FieldChangeType.UNCHANGED)

    def test_newly_available_field_added(self):
        scholarship = _make_scholarship()
        extracted = _make_extraction(
            duration="2 years",
            confidence={"duration": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        duration_change = next(c for c in result.changes if c.field == "duration")
        self.assertEqual(duration_change.change_type, FieldChangeType.ADDED)
        self.assertIsNone(duration_change.old_value)
        self.assertEqual(duration_change.new_value, "2 years")
        self.assertTrue(duration_change.is_update_candidate)

    def test_changed_field_modified(self):
        scholarship = _make_scholarship(duration="2 years")
        extracted = _make_extraction(
            duration="3 years",
            confidence={"duration": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        duration_change = next(c for c in result.changes if c.field == "duration")
        self.assertEqual(duration_change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(duration_change.old_value, "2 years")
        self.assertEqual(duration_change.new_value, "3 years")
        self.assertTrue(duration_change.is_update_candidate)

    def test_extractor_none_not_removed(self):
        scholarship = _make_scholarship(duration="2 years")
        extracted = _make_extraction(
            duration=None,
            confidence={"duration": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        duration_change = next(c for c in result.changes if c.field == "duration")
        self.assertEqual(duration_change.change_type, FieldChangeType.REMOVED)
        self.assertFalse(duration_change.is_update_candidate)

    def test_low_confidence_not_automatic_update(self):
        scholarship = _make_scholarship()
        extracted = _make_extraction(
            duration="2 years",
            confidence={"duration": ExtractionConfidence.LOW},
        )

        result = diff_scholarship(scholarship, extracted)

        duration_change = next(c for c in result.changes if c.field == "duration")
        self.assertEqual(duration_change.change_type, FieldChangeType.ADDED)
        self.assertFalse(duration_change.is_update_candidate)

    def test_changed_deadline_detected(self):
        scholarship = _make_scholarship(deadline_display="October 15, 2026")
        extracted = _make_extraction(
            deadline="December 1, 2026",
            confidence={"deadline": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        deadline_change = next(c for c in result.changes if c.field == "deadline_display")
        self.assertEqual(deadline_change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(deadline_change.old_value, "October 15, 2026")
        self.assertEqual(deadline_change.new_value, "December 1, 2026")
        self.assertTrue(deadline_change.is_update_candidate)

    def test_changed_eligibility_detected(self):
        scholarship = _make_scholarship(eligibility=["Must be enrolled"])
        extracted = _make_extraction(
            eligibility="Must have a bachelor's degree",
            confidence={"eligibility": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        eligibility_change = next(c for c in result.changes if c.field == "eligibility")
        self.assertEqual(eligibility_change.change_type, FieldChangeType.MODIFIED)
        self.assertTrue(eligibility_change.is_update_candidate)

    def test_scholarship_name_identity_conflict(self):
        scholarship = _make_scholarship(title="Old Scholarship Name")
        extracted = _make_extraction(
            scholarship_name="Completely Different Scholarship",
            confidence={"scholarship_name": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        self.assertTrue(result.identity_conflict)
        title_change = next(c for c in result.changes if c.field == "title")
        self.assertEqual(title_change.change_type, FieldChangeType.IDENTITY_CONFLICT)
        self.assertFalse(title_change.is_update_candidate)

    def test_provider_identity_conflict(self):
        scholarship = _make_scholarship(official_source="Old Provider")
        extracted = _make_extraction(
            provider="New Provider",
            confidence={"provider": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        self.assertTrue(result.identity_conflict)
        provider_change = next(c for c in result.changes if c.field == "official_source")
        self.assertEqual(provider_change.change_type, FieldChangeType.IDENTITY_CONFLICT)
        self.assertFalse(provider_change.is_update_candidate)

    def test_exact_deadline_to_rolling(self):
        scholarship = _make_scholarship(deadline_display="October 15, 2026")
        extracted = _make_extraction(
            deadline="rolling",
            confidence={"deadline": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        deadline_change = next(c for c in result.changes if c.field == "deadline_display")
        self.assertEqual(deadline_change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(deadline_change.old_value, "October 15, 2026")
        self.assertEqual(deadline_change.new_value, "rolling")

    def test_exact_deadline_to_not_announced(self):
        scholarship = _make_scholarship(deadline_display="October 15, 2026")
        extracted = _make_extraction(
            deadline="not announced",
            confidence={"deadline": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        deadline_change = next(c for c in result.changes if c.field == "deadline_display")
        self.assertEqual(deadline_change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(deadline_change.new_value, "not announced")

    def test_not_announced_to_exact_deadline(self):
        scholarship = _make_scholarship(deadline_display="not announced")
        extracted = _make_extraction(
            deadline="October 15, 2026",
            confidence={"deadline": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        deadline_change = next(c for c in result.changes if c.field == "deadline_display")
        self.assertEqual(deadline_change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(deadline_change.old_value, "not announced")
        self.assertEqual(deadline_change.new_value, "October 15, 2026")

    def test_meaningful_long_text_change_modified(self):
        scholarship = _make_scholarship(
            eligibility=["Must be a citizen of an eligible country", "Minimum GPA 3.0"]
        )
        extracted = _make_extraction(
            eligibility="Must be a citizen of an eligible country with minimum GPA 3.5 and demonstrated leadership",
            confidence={"eligibility": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        eligibility_change = next(c for c in result.changes if c.field == "eligibility")
        self.assertEqual(eligibility_change.change_type, FieldChangeType.MODIFIED)
        self.assertTrue(eligibility_change.is_update_candidate)

    def test_deterministic_identical_inputs_produce_identical_changeset(self):
        scholarship = _make_scholarship(
            title="Test Scholarship",
            degree="Master",
            duration="2 years",
        )
        extracted = _make_extraction(
            scholarship_name="Test Scholarship",
            degree_level="Master",
            duration="3 years",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
            },
        )

        result1 = diff_scholarship(scholarship, extracted)
        result2 = diff_scholarship(scholarship, extracted)

        self.assertEqual(
            [(c.field, c.change_type, c.old_value, c.new_value) for c in result1.changes],
            [(c.field, c.change_type, c.old_value, c.new_value) for c in result2.changes],
        )
        self.assertEqual(result1.identity_conflict, result2.identity_conflict)
        self.assertEqual(result1.cycle_changed, result2.cycle_changed)
        self.assertEqual(result1.is_new_scholarship, result2.is_new_scholarship)

    def test_unmapped_extractor_field_ignored(self):
        scholarship = _make_scholarship(
            title="Test Scholarship",
            degree="Master",
            official_source="Test Provider",
            eligibility=["Must be enrolled"],
            duration="2 years",
            application_method=["Online"],
            deadline_display="October 15, 2026",
            status="open",
            application_link="https://example.com/apply",
        )
        extracted = _make_extraction(
            scholarship_name="Test Scholarship",
            degree_level="Master",
            provider="Test Provider",
            eligibility="Must be enrolled",
            duration="2 years",
            application_method="Online",
            deadline="October 15, 2026",
            status="open",
            application_url="https://example.com/apply",
            award_amount="$10,000",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.HIGH,
                "eligibility": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
                "application_method": ExtractionConfidence.HIGH,
                "deadline": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.HIGH,
                "application_url": ExtractionConfidence.HIGH,
                "award_amount": ExtractionConfidence.HIGH,
            },
        )

        result = diff_scholarship(scholarship, extracted)

        fields = {c.field for c in result.changes}
        self.assertNotIn("award_amount", fields)
        self.assertFalse(result.has_changes)

    def test_unmapped_scholarship_cycle_ignored(self):
        scholarship = _make_scholarship(
            title="Test Scholarship",
            degree="Master",
            official_source="Test Provider",
            eligibility=["Must be enrolled"],
            duration="2 years",
            application_method=["Online"],
            deadline_display="October 15, 2026",
            status="open",
            application_link="https://example.com/apply",
        )
        extracted = _make_extraction(
            scholarship_name="Test Scholarship",
            degree_level="Master",
            provider="Test Provider",
            eligibility="Must be enrolled",
            duration="2 years",
            application_method="Online",
            deadline="October 15, 2026",
            status="open",
            application_url="https://example.com/apply",
            scholarship_cycle="2027-28",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.HIGH,
                "eligibility": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
                "application_method": ExtractionConfidence.HIGH,
                "deadline": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.HIGH,
                "application_url": ExtractionConfidence.HIGH,
                "scholarship_cycle": ExtractionConfidence.HIGH,
            },
        )

        result = diff_scholarship(scholarship, extracted)

        fields = {c.field for c in result.changes}
        self.assertNotIn("scholarship_cycle", fields)
        self.assertFalse(result.cycle_changed)
        self.assertFalse(result.has_changes)

    def test_field_change_model_fields(self):
        change = FieldChange(
            field="duration",
            change_type=FieldChangeType.MODIFIED,
            old_value="2 years",
            new_value="3 years",
            source="extractor -> database",
            confidence=ExtractionConfidence.HIGH,
            is_update_candidate=True,
        )

        self.assertEqual(change.field, "duration")
        self.assertEqual(change.change_type, FieldChangeType.MODIFIED)
        self.assertEqual(change.old_value, "2 years")
        self.assertEqual(change.new_value, "3 years")
        self.assertEqual(change.source, "extractor -> database")
        self.assertEqual(change.confidence, ExtractionConfidence.HIGH)
        self.assertTrue(change.is_update_candidate)

    def test_changeset_update_candidates_property(self):
        scholarship = _make_scholarship()
        extracted = _make_extraction(
            duration="2 years",
            status="closed",
            confidence={
                "duration": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.LOW,
            },
        )

        result = diff_scholarship(scholarship, extracted)

        candidates = result.update_candidates
        candidate_fields = {c.field for c in candidates}
        self.assertIn("duration", candidate_fields)
        self.assertNotIn("status", candidate_fields)

    def test_changeset_has_changes_property(self):
        scholarship = _make_scholarship(
            title="Test Scholarship",
            degree="Master",
            official_source="Test Provider",
            eligibility=["Must be enrolled"],
            duration="2 years",
            application_method=["Online"],
            deadline_display="October 15, 2026",
            status="open",
            application_link="https://example.com/apply",
        )
        extracted = _make_extraction(
            scholarship_name="Test Scholarship",
            degree_level="Master",
            provider="Test Provider",
            eligibility="Must be enrolled",
            duration="2 years",
            application_method="Online",
            deadline="October 15, 2026",
            status="open",
            application_url="https://example.com/apply",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.HIGH,
                "eligibility": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
                "application_method": ExtractionConfidence.HIGH,
                "deadline": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.HIGH,
                "application_url": ExtractionConfidence.HIGH,
            },
        )

        result = diff_scholarship(scholarship, extracted)
        self.assertFalse(result.has_changes)

        extracted2 = _make_extraction(
            scholarship_name="Different Name",
            degree_level="Master",
            provider="Test Provider",
            eligibility="Must be enrolled",
            duration="2 years",
            application_method="Online",
            deadline="October 15, 2026",
            status="open",
            application_url="https://example.com/apply",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "degree_level": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.HIGH,
                "eligibility": ExtractionConfidence.HIGH,
                "duration": ExtractionConfidence.HIGH,
                "application_method": ExtractionConfidence.HIGH,
                "deadline": ExtractionConfidence.HIGH,
                "status": ExtractionConfidence.HIGH,
                "application_url": ExtractionConfidence.HIGH,
            },
        )
        result2 = diff_scholarship(scholarship, extracted2)
        self.assertTrue(result2.has_changes)

    def test_json_list_order_insensitive(self):
        scholarship = _make_scholarship(
            eligibility=["Must be enrolled", "Minimum GPA 3.0"]
        )
        extracted = _make_extraction(
            eligibility="Minimum GPA 3.0",
            confidence={"eligibility": ExtractionConfidence.HIGH},
        )

        result = diff_scholarship(scholarship, extracted)

        eligibility_change = next(c for c in result.changes if c.field == "eligibility")
        self.assertEqual(eligibility_change.change_type, FieldChangeType.MODIFIED)

    def test_semantic_deadline_values_preserved(self):
        for semantic in ("rolling", "not announced", "varies"):
            scholarship = _make_scholarship(deadline_display="October 15, 2026")
            extracted = _make_extraction(
                deadline=semantic,
                confidence={"deadline": ExtractionConfidence.HIGH},
            )

            result = diff_scholarship(scholarship, extracted)
            deadline_change = next(c for c in result.changes if c.field == "deadline_display")
            self.assertEqual(deadline_change.change_type, FieldChangeType.MODIFIED)
            self.assertEqual(deadline_change.new_value, semantic)


if __name__ == "__main__":
    unittest.main()
