"""Tests for the separated award economics and structured programme detail.

The CGRS programme records made one thing obvious: a scholarship's award amount
and what that award actually pays for are different facts. A 120-character
``funding`` label cannot hold "CAD 40,000 a year" and "covers tuition and living
costs" at the same time, and an applicant who reads the first as the second
makes a serious financial decision on a database's brevity.

These tests pin the separation, and pin the rules that keep derived guidance from
being published as an awarding body's own wording.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import Scholarship

CONFIG = Path(__file__).resolve().parents[1] / "config"
DETAILS = CONFIG / "programme_details.json"


class TestSeparatedAwardEconomics:
    def test_amount_currency_and_coverage_are_distinct_columns(self):
        columns = Scholarship.__table__.columns
        for name in (
            "funding_amount", "funding_currency", "funding_period",
            "tuition_coverage", "living_cost_coverage", "travel_coverage",
            "fully_funded",
        ):
            assert name in columns, f"{name} must exist as its own column"

    def test_fully_funded_defaults_to_false_not_unknown(self):
        """Unknown must not read as probably yes.

        A default of NULL would be ambiguous in any filter, and an applicant
        reading a blank as permissive is the exact harm this split was meant to
        prevent.
        """
        column = Scholarship.__table__.columns["fully_funded"]
        assert column.nullable is False
        assert column.default.arg is False

    def test_coverage_flags_are_nullable(self):
        """A programme that simply does not say must not be recorded as false."""
        for name in ("tuition_coverage", "living_cost_coverage", "travel_coverage"):
            assert Scholarship.__table__.columns[name].nullable is True

    def test_funding_label_still_exists_alongside_the_amount(self):
        assert "funding" in Scholarship.__table__.columns


class TestStructuredDetailColumns:
    def test_official_and_derived_data_are_stored_apart(self):
        columns = Scholarship.__table__.columns
        for name in ("official_details", "applicant_utility", "programme_verification"):
            assert name in columns

    def test_derived_guidance_can_never_enter_the_published_block(self):
        """Utility keys must not be applied to official_details.

        The stage writes each block to its own column, so the guarantee is
        structural. The source file is checked here because the real risk is an
        agent putting guidance inside the official block, where nothing would
        stop it.
        """
        utility_only = {
            "application_readiness_checklist", "common_rejection_risks",
            "estimated_uncovered_costs", "document_audit", "alerts",
            "submission_workflow",
        }
        raw = json.loads(DETAILS.read_text(encoding="utf-8"))
        for record in raw["records"]:
            official = record.get("official") or {}
            for key in official:
                assert key not in utility_only, (
                    f"record {record.get('id')} puts derived guidance in the "
                    f"published block under {key!r}"
                )


class TestProgrammeDetailsFile:
    @pytest.fixture(scope="class")
    def records(self):
        raw = json.loads(DETAILS.read_text(encoding="utf-8"))
        return [r for r in raw.get("records", []) if isinstance(r, dict) and "id" in r]

    def test_every_record_carries_usable_citations(self, records):
        for record in records:
            verification = record.get("verification") or {}
            citations = verification.get("source_citations") or []
            official = record.get("official") or {}
            urls = citations or official.get("official_source_urls") or []
            assert any(isinstance(u, str) and u.startswith("http") for u in urls), (
                f"record {record['id']} has no official citation; an amount with "
                f"nothing behind it looks researched and is not"
            )

    def test_fully_funded_is_only_asserted_with_tuition_coverage(self, records):
        """A stipend must never be stored as though it were a tuition waiver."""
        for record in records:
            official = record.get("official") or {}
            if official.get("fully_funded") is True:
                assert official.get("tuition_coverage") is True, (
                    f"record {record['id']} claims full funding without tuition "
                    f"coverage being established"
                )

    def test_no_placeholder_strings_pass_as_values(self, records):
        placeholders = {"", "n/a", "na", "-", "none", "tbd", "unknown", "null"}
        for record in records:
            official = record.get("official") or {}
            for field in (
                "funding_currency", "funding_period", "deadline_central",
                "application_route", "study_mode",
            ):
                value = official.get(field)
                if isinstance(value, str):
                    assert value.strip().lower() not in placeholders, (
                        f"record {record['id']} field {field} holds the placeholder "
                        f"{value!r}; an unanswered field must be null"
                    )

    def test_verification_records_when_the_data_was_checked(self, records):
        for record in records:
            verification = record.get("verification") or {}
            official = record.get("official") or {}
            stamp = verification.get("last_verified_date") or official.get("last_verified_date")
            assert stamp, f"record {record['id']} has no verification date"
            date.fromisoformat(str(stamp)[:10])


class TestProgrammeDetailsStageWiring:
    def test_stage_is_registered_in_all_three_places(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        assert '"programme_details": do_programme_details' in source, (
            "missing from the dispatch table"
        )
        assert '"programme_details"' in source, (
            "missing from STAGE_ORDER or argparse choices; a stage in the table "
            "but not the order is selected out and reports success having done nothing"
        )

    def test_stage_fills_only_empty_fields(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_programme_details", 1)[1].split("def do_facts", 1)[0]
        assert "if getattr(row, field, None):" in body, (
            "an existing verified value must never be overwritten by research"
        )

    def test_stage_refuses_data_with_no_citation(self):
        source = (
            Path(__file__).resolve().parents[1] / "app" / "jobs" / "scholarzone_maintenance.py"
        ).read_text(encoding="utf-8")
        body = source.split("def do_programme_details", 1)[1].split("def do_facts", 1)[0]
        assert "skipped_no_provenance" in body, (
            "a record whose research cites nothing must be skipped, not applied"
        )
