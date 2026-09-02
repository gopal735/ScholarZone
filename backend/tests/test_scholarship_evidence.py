"""Unit tests for the scholarship evidence layer."""

from __future__ import annotations

import unittest

from app.services.scholarship_diff import ChangeSet, FieldChange, FieldChangeType
from app.services.scholarship_evidence import (
    EvidenceCollection,
    EvidenceItem,
    EvidenceStatus,
    SourceType,
    can_automatically_update,
    classify_source,
    collect_evidence,
    is_authoritative_source,
)
from app.services.scholarship_extractor import ExtractionConfidence, ScholarshipExtractionResult


SAMPLE_SOURCE_HTML = """<html>
<head><title>Test Government Scholarship</title></head>
<body>
<h1>Test Government Scholarship</h1>
<p>Degree: Master's, Doctoral</p>
<p>Offered by: Ministry of Education</p>
<p>Eligibility: Open to all international students</p>
<p>Duration: 2 years</p>
<p>Deadline: March 31, 2026</p>
<p>Award: $50,000 per year</p>
<p>Tuition: Full tuition coverage</p>
<p>Stipend: $2,000/month</p>
<p>GPA: 3.5 minimum</p>
<p>Language: IELTS 6.5 or equivalent</p>
<a href="https://apply.example.gov/now">Apply now</a>
</body>
</html>"""


class TestEvidenceCreation(unittest.TestCase):
    """Test 1: Evidence creation."""

    def test_evidence_item_creation(self):
        item = EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Test Scholarship",
            source_url="https://www.sbfi.admin.ch/en/test",
            evidence_text="<title>Test Scholarship</title>",
            confidence=ExtractionConfidence.HIGH,
            source_type=SourceType.OFFICIAL_GOVERNMENT,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.HIGH_CONFIDENCE,
        )
        self.assertEqual(item.scholarship_id, 1)
        self.assertEqual(item.field_name, "title")
        self.assertEqual(item.extracted_value, "Test Scholarship")
        self.assertEqual(item.source_url, "https://www.sbfi.admin.ch/en/test")
        self.assertEqual(item.confidence, "high")
        self.assertEqual(item.source_type, SourceType.OFFICIAL_GOVERNMENT)
        self.assertEqual(item.status, EvidenceStatus.HIGH_CONFIDENCE)

    def test_evidence_collection_creation(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        self.assertEqual(collection.scholarship_id, 1)
        self.assertEqual(len(collection.items), 0)
        self.assertFalse(collection.has_any_evidence)

    def test_evidence_collection_with_items(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        collection.items.append(EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Test",
            source_url="https://www.sbfi.admin.ch/en/test",
            evidence_text="Test",
            confidence="high",
            source_type=SourceType.OFFICIAL_GOVERNMENT,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.HIGH_CONFIDENCE,
        ))
        self.assertTrue(collection.has_any_evidence)
        self.assertEqual(len(collection.high_confidence_items), 1)


class TestFieldEvidenceAssociation(unittest.TestCase):
    """Test 2: Field/evidence association."""

    def test_get_evidence_for_field(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                provider="Ministry of Education",
                degree_level="Master's, Doctoral",
                eligibility="Open to all international students",
                duration="2 years",
                deadline="March 31, 2026",
                award_amount="$50,000 per year",
                tuition_coverage="Full tuition coverage",
                living_stipend="$2,000/month",
                gpa_requirement="3.5 minimum",
                language_requirement="IELTS 6.5 or equivalent",
                application_url="https://apply.example.gov/now",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.MEDIUM,
                    "degree_level": ExtractionConfidence.MEDIUM,
                    "eligibility": ExtractionConfidence.MEDIUM,
                    "duration": ExtractionConfidence.MEDIUM,
                    "deadline": ExtractionConfidence.HIGH,
                    "award_amount": ExtractionConfidence.MEDIUM,
                    "tuition_coverage": ExtractionConfidence.MEDIUM,
                    "living_stipend": ExtractionConfidence.MEDIUM,
                    "gpa_requirement": ExtractionConfidence.MEDIUM,
                    "language_requirement": ExtractionConfidence.MEDIUM,
                    "application_url": ExtractionConfidence.HIGH,
                },
            ),
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertEqual(title_evidence.field_name, "title")
        self.assertEqual(title_evidence.extracted_value, "Test Government Scholarship")

        provider_evidence = collection.get_evidence_for_field("official_source")
        self.assertIsNotNone(provider_evidence)
        self.assertEqual(provider_evidence.extracted_value, "Ministry of Education")

    def test_evidence_for_nonexistent_field_returns_none(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test",
                confidence={"scholarship_name": ExtractionConfidence.HIGH},
            ),
        )
        result = collection.get_evidence_for_field("nonexistent_field")
        self.assertIsNone(result)


class TestHighConfidenceEvidence(unittest.TestCase):
    """Test 3: High-confidence evidence."""

    def test_high_confidence_evidence_status(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                deadline="March 31, 2026",
                application_url="https://apply.example.gov/now",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "deadline": ExtractionConfidence.HIGH,
                    "application_url": ExtractionConfidence.HIGH,
                },
            ),
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertEqual(title_evidence.status, EvidenceStatus.HIGH_CONFIDENCE)
        self.assertEqual(title_evidence.confidence, "high")

        deadline_evidence = collection.get_evidence_for_field("deadline_display")
        self.assertIsNotNone(deadline_evidence)
        self.assertEqual(deadline_evidence.status, EvidenceStatus.HIGH_CONFIDENCE)

    def test_high_confidence_items_property(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                deadline="March 31, 2026",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "deadline": ExtractionConfidence.HIGH,
                },
            ),
        )
        self.assertGreater(len(collection.high_confidence_items), 0)
        for item in collection.high_confidence_items:
            self.assertEqual(item.status, EvidenceStatus.HIGH_CONFIDENCE)


class TestLowConfidenceEvidence(unittest.TestCase):
    """Test 4: Low-confidence evidence."""

    def test_low_confidence_evidence_status(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                provider="Ministry of Education",
                confidence={
                    "scholarship_name": ExtractionConfidence.LOW,
                    "provider": ExtractionConfidence.LOW,
                },
            ),
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertEqual(title_evidence.status, EvidenceStatus.LOW_CONFIDENCE)

    def test_low_confidence_items_property(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                confidence={
                    "scholarship_name": ExtractionConfidence.LOW,
                },
            ),
        )
        self.assertGreater(len(collection.low_confidence_items), 0)
        for item in collection.low_confidence_items:
            self.assertEqual(item.status, EvidenceStatus.LOW_CONFIDENCE)


class TestMissingEvidence(unittest.TestCase):
    """Test 5: Missing evidence."""

    def test_missing_evidence_text(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content="",  # Empty source
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                },
            ),
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertEqual(title_evidence.evidence_text, "")

    def test_missing_items_property(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content="",  # Empty source
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                provider="Ministry of Education",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.MEDIUM,
                },
            ),
        )
        # With empty source content, evidence_text will be empty for all fields
        missing = collection.missing_items
        self.assertGreater(len(missing), 0)


class TestMultipleFieldsSeparateEvidence(unittest.TestCase):
    """Test 6: Multiple fields with separate evidence."""

    def test_multiple_fields_each_have_evidence(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                provider="Ministry of Education",
                degree_level="Master's, Doctoral",
                eligibility="Open to all international students",
                duration="2 years",
                deadline="March 31, 2026",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.MEDIUM,
                    "degree_level": ExtractionConfidence.MEDIUM,
                    "eligibility": ExtractionConfidence.MEDIUM,
                    "duration": ExtractionConfidence.MEDIUM,
                    "deadline": ExtractionConfidence.HIGH,
                },
            ),
        )

        expected_fields = {"title", "official_source", "degree", "eligibility", "duration", "deadline_display"}
        actual_fields = {item.field_name for item in collection.items}
        self.assertTrue(expected_fields.issubset(actual_fields))

        # Each field should have its own evidence item
        for field_name in expected_fields:
            evidence = collection.get_evidence_for_field(field_name)
            self.assertIsNotNone(evidence, f"Missing evidence for field: {field_name}")
            self.assertEqual(evidence.field_name, field_name)

    def test_evidence_items_are_distinct(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                provider="Ministry of Education",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "provider": ExtractionConfidence.MEDIUM,
                },
            ),
        )

        field_names = [item.field_name for item in collection.items]
        self.assertEqual(len(field_names), len(set(field_names)))


class TestDeterministicEvidenceOutput(unittest.TestCase):
    """Test 7: Deterministic evidence output."""

    def test_same_input_produces_same_output(self):
        extraction_result = ScholarshipExtractionResult(
            scholarship_name="Test Government Scholarship",
            provider="Ministry of Education",
            degree_level="Master's",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.MEDIUM,
                "degree_level": ExtractionConfidence.MEDIUM,
            },
        )

        collection1 = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=extraction_result,
        )

        collection2 = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=extraction_result,
        )

        self.assertEqual(len(collection1.items), len(collection2.items))
        for item1, item2 in zip(collection1.items, collection2.items):
            self.assertEqual(item1.field_name, item2.field_name)
            self.assertEqual(item1.extracted_value, item2.extracted_value)
            self.assertEqual(item1.evidence_text, item2.evidence_text)
            self.assertEqual(item1.status, item2.status)
            self.assertEqual(item1.source_type, item2.source_type)

    def test_evidence_ordering_is_deterministic(self):
        extraction_result = ScholarshipExtractionResult(
            scholarship_name="Test",
            provider="Provider",
            degree_level="Master",
            eligibility="All students",
            duration="2 years",
            deadline="March 31",
            confidence={
                "scholarship_name": ExtractionConfidence.HIGH,
                "provider": ExtractionConfidence.MEDIUM,
                "degree_level": ExtractionConfidence.MEDIUM,
                "eligibility": ExtractionConfidence.MEDIUM,
                "duration": ExtractionConfidence.MEDIUM,
                "deadline": ExtractionConfidence.HIGH,
            },
        )

        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=extraction_result,
        )

        field_names = [item.field_name for item in collection.items]
        # Run again and verify same order
        collection2 = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=extraction_result,
        )
        field_names2 = [item.field_name for item in collection2.items]
        self.assertEqual(field_names, field_names2)


class TestOfficialSourceClassification(unittest.TestCase):
    """Test 8: Official-source classification."""

    def test_government_source_classification(self):
        self.assertEqual(
            classify_source("https://www.gov.uk/scholarships"),
            SourceType.OFFICIAL_GOVERNMENT,
        )
        self.assertEqual(
            classify_source("https://www.gouv.fr/bourses"),
            SourceType.OFFICIAL_GOVERNMENT,
        )
        self.assertEqual(
            classify_source("https://www.bund.de/en/scholarships"),
            SourceType.OFFICIAL_GOVERNMENT,
        )

    def test_university_source_classification(self):
        self.assertEqual(
            classify_source("https://www.ox.ac.uk/admissions"),
            SourceType.OFFICIAL_UNIVERSITY,
        )
        self.assertEqual(
            classify_source("https://www.tokyo.ac.jp/en/admissions"),
            SourceType.OFFICIAL_UNIVERSITY,
        )

    def test_scholarship_program_classification(self):
        self.assertEqual(
            classify_source("https://www.daad.de/en/"),
            SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
        )
        self.assertEqual(
            classify_source("https://www.campusfrance.org/en/scholarships"),
            SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
        )

    def test_application_portal_classification(self):
        self.assertEqual(
            classify_source("https://apply.daad.de/portal"),
            SourceType.OFFICIAL_APPLICATION_PORTAL,
        )

    def test_third_party_classification(self):
        self.assertEqual(
            classify_source("https://www.example.com/scholarship"),
            SourceType.THIRD_PARTY,
        )
        self.assertEqual(
            classify_source("https://www.randomblog.net/scholarship"),
            SourceType.THIRD_PARTY,
        )

    def test_is_authoritative_source(self):
        self.assertTrue(is_authoritative_source(SourceType.OFFICIAL_GOVERNMENT))
        self.assertTrue(is_authoritative_source(SourceType.OFFICIAL_UNIVERSITY))
        self.assertTrue(is_authoritative_source(SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM))
        self.assertTrue(is_authoritative_source(SourceType.OFFICIAL_APPLICATION_PORTAL))
        self.assertFalse(is_authoritative_source(SourceType.THIRD_PARTY))


class TestEvidenceSafetyRules(unittest.TestCase):
    """Test safety rules for evidence-based updates."""

    def test_no_evidence_no_automatic_update(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        can_update, reasons = can_automatically_update(collection)
        self.assertFalse(can_update)
        self.assertIn("No evidence available for any field", reasons)

    def test_low_confidence_no_automatic_update(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        collection.items.append(EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Test",
            source_url="https://www.sbfi.admin.ch/en/test",
            evidence_text="Test",
            confidence="low",
            source_type=SourceType.OFFICIAL_GOVERNMENT,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.LOW_CONFIDENCE,
        ))
        can_update, reasons = can_automatically_update(collection)
        self.assertFalse(can_update)

    def test_identity_conflict_no_automatic_update(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        collection.items.append(EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Different Name",
            source_url="https://www.sbfi.admin.ch/en/test",
            evidence_text="Different Name",
            confidence="high",
            source_type=SourceType.OFFICIAL_GOVERNMENT,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.IDENTITY_CONFLICT,
        ))
        can_update, reasons = can_automatically_update(collection)
        self.assertFalse(can_update)
        self.assertIn("Identity conflict detected on fields:", reasons[0])

    def test_third_party_source_no_automatic_update(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.example.com/scholarship",
        )
        collection.items.append(EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Test",
            source_url="https://www.example.com/scholarship",
            evidence_text="Test",
            confidence="high",
            source_type=SourceType.THIRD_PARTY,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.HIGH_CONFIDENCE,
        ))
        can_update, reasons = can_automatically_update(collection)
        self.assertFalse(can_update)
        self.assertIn("Source is not authoritative: third_party", reasons)

    def test_high_confidence_official_source_can_update(self):
        collection = EvidenceCollection(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
        )
        collection.items.append(EvidenceItem(
            scholarship_id=1,
            field_name="title",
            extracted_value="Test",
            source_url="https://www.sbfi.admin.ch/en/test",
            evidence_text="Test",
            confidence="high",
            source_type=SourceType.OFFICIAL_GOVERNMENT,
            verification_timestamp="2026-08-31T12:00:00+00:00",
            status=EvidenceStatus.HIGH_CONFIDENCE,
        ))
        can_update, reasons = can_automatically_update(collection)
        self.assertTrue(can_update)


class TestEvidenceWithChangeSet(unittest.TestCase):
    """Test evidence integration with ChangeSet."""

    def test_identity_conflict_from_changeset(self):
        changeset = ChangeSet(
            changes=[
                FieldChange(
                    field="title",
                    change_type=FieldChangeType.IDENTITY_CONFLICT,
                    old_value="Original Name",
                    new_value="Different Name",
                    confidence="high",
                    is_update_candidate=False,
                ),
            ],
            identity_conflict=True,
        )

        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Different Name",
                confidence={"scholarship_name": ExtractionConfidence.HIGH},
            ),
            changeset=changeset,
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertEqual(title_evidence.status, EvidenceStatus.IDENTITY_CONFLICT)

    def test_evidence_text_extraction_from_source(self):
        collection = collect_evidence(
            scholarship_id=1,
            source_url="https://www.sbfi.admin.ch/en/test",
            source_content=SAMPLE_SOURCE_HTML,
            extraction_result=ScholarshipExtractionResult(
                scholarship_name="Test Government Scholarship",
                duration="2 years",
                confidence={
                    "scholarship_name": ExtractionConfidence.HIGH,
                    "duration": ExtractionConfidence.MEDIUM,
                },
            ),
        )

        title_evidence = collection.get_evidence_for_field("title")
        self.assertIsNotNone(title_evidence)
        self.assertIn("Test Government Scholarship", title_evidence.evidence_text)

        duration_evidence = collection.get_evidence_for_field("duration")
        self.assertIsNotNone(duration_evidence)
        self.assertIn("2 years", duration_evidence.evidence_text)


if __name__ == "__main__":
    unittest.main()
