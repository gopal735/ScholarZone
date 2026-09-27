"""Tests for the official-source enrichment engine.

Covers source resolution, projection of extractor output into canonical
Scholarship columns, merge/preservation semantics, status derivation,
idempotency, rate limiting, retry, and per-record isolation.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Scholarship
from app.services.discovery_scheduler import DomainRateLimiter
from app.services.scholarship_enrichment import (
    STATUS_CLOSED,
    STATUS_CLOSING_SOON,
    STATUS_OPEN,
    STATUS_UNKNOWN,
    EnrichmentOutcome,
    ScholarshipEnrichmentService,
    as_list,
    derive_status,
    merge_list,
    project_enrichment,
    resolve_official_source,
    _trim_to_clause,
)
from app.services.scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
)


@pytest.fixture
def engine():
    return create_engine("sqlite:///:memory:")


@pytest.fixture
def session_factory(engine):
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_scholarship(session_factory, **overrides) -> int:
    defaults = dict(
        title="Test Scholarship",
        country="Germany",
        degree="Master",
        funding="Fully Funded",
        official_source="DAAD",
        official_source_url="https://www.daad.de/en/studying-in-germany/scholarships/",
        application_link="https://www.daad.de/en/studying-in-germany/scholarships/",
        is_verified=True,
        verification_status="active",
        status="open",
        deadline_precision="unknown",
    )
    defaults.update(overrides)
    session = session_factory()
    try:
        scholarship = Scholarship(**defaults)
        session.add(scholarship)
        session.commit()
        session.refresh(scholarship)
        return scholarship.id
    finally:
        session.close()


# ---------------------------------------------------------------- source resolution


class TestSourceResolution:
    def test_prefers_official_source_url(self, session_factory):
        sid = _make_scholarship(session_factory)
        session = session_factory()
        try:
            resolved = resolve_official_source(session.get(Scholarship, sid))
            assert resolved is not None
            assert resolved.field_name == "official_source_url"
            assert resolved.authoritative is True
        finally:
            session.close()

    def test_falls_back_to_application_link(self, session_factory):
        sid = _make_scholarship(
            session_factory,
            official_source_url=None,
            application_link="https://www.campusfrance.org/en/scholarship",
        )
        session = session_factory()
        try:
            resolved = resolve_official_source(session.get(Scholarship, sid))
            assert resolved.field_name == "application_link"
            assert resolved.authoritative is True
        finally:
            session.close()

    def test_returns_none_when_no_urls(self, session_factory):
        sid = _make_scholarship(
            session_factory,
            official_source_url=None,
            application_link=None,
        )
        session = session_factory()
        try:
            assert resolve_official_source(session.get(Scholarship, sid)) is None
        finally:
            session.close()

    def test_third_party_reported_as_not_authoritative(self, session_factory):
        sid = _make_scholarship(
            session_factory,
            official_source_url="https://www.scholarshipdb.net/some-scholarship",
            application_link="https://www.scholarshipdb.net/some-scholarship",
        )
        session = session_factory()
        try:
            resolved = resolve_official_source(session.get(Scholarship, sid))
            assert resolved is not None
            assert resolved.authoritative is False
        finally:
            session.close()

    def test_official_beats_earlier_third_party_field(self, session_factory):
        """A later official field must win over an earlier aggregator URL."""
        sid = _make_scholarship(
            session_factory,
            official_source_url="https://www.scholarshipdb.net/x",
            application_link="https://www.campusfrance.org/en/scholarship",
        )
        session = session_factory()
        try:
            resolved = resolve_official_source(session.get(Scholarship, sid))
            assert resolved.field_name == "application_link"
            assert resolved.authoritative is True
        finally:
            session.close()

    def test_skips_placeholder_urls(self, session_factory):
        sid = _make_scholarship(
            session_factory,
            official_source_url="   ",
            application_link="https://www.daad.de/en/",
        )
        session = session_factory()
        try:
            resolved = resolve_official_source(session.get(Scholarship, sid))
            assert resolved.field_name == "application_link"
        finally:
            session.close()


# ---------------------------------------------------------------- as_list / merge


class TestListSplitting:
    def test_single_sentence_stays_single_item(self):
        assert as_list("Must hold a Bachelor's degree") == ["Must hold a Bachelor's degree"]

    def test_splits_bullets(self):
        assert as_list("\u2022 First item\n\u2022 Second item") == ["First item", "Second item"]

    def test_drops_placeholders(self):
        assert as_list("N/A") == []
        assert as_list(None) == []

    def test_deduplicates(self):
        assert as_list("Item one\nItem one") == ["Item one"]


class TestMergeList:
    def test_union_adds_new(self):
        merged, added = merge_list(["A"], ["B"])
        assert merged == ["A", "B"]
        assert added == ["B"]

    def test_is_case_and_space_insensitive(self):
        merged, added = merge_list(["Full  Tuition"], ["full tuition"])
        assert merged == ["Full  Tuition"]
        assert added == []

    def test_preserves_existing_order_first(self):
        merged, _ = merge_list(["Existing"], ["New"])
        assert merged[0] == "Existing"

    def test_idempotent(self):
        once, _ = merge_list(["A"], ["B"])
        twice, added = merge_list(once, ["B"])
        assert once == twice
        assert added == []

    def test_handles_none(self):
        merged, added = merge_list(None, ["A"])
        assert merged == ["A"]
        assert added == ["A"]


# ---------------------------------------------------------------- projection


def _extraction(**kwargs) -> ScholarshipExtractionResult:
    confidence = kwargs.pop("confidence", None) or {}
    return ScholarshipExtractionResult(**kwargs, confidence=confidence)


class TestProjection:
    def test_maps_financial_fields_to_coverage(self):
        extracted = _extraction(
            tuition_coverage="Full tuition fees",
            living_stipend="Monthly stipend of 900 EUR",
            confidence={"tuition_coverage": "high", "living_stipend": "high"},
        )
        proposals = project_enrichment(extracted)
        assert "coverage" in proposals
        assert "Full tuition fees" in proposals["coverage"]["value"]
        assert "Monthly stipend of 900 EUR" in proposals["coverage"]["value"]

    def test_benefits_does_not_duplicate_coverage_items(self):
        """benefits and coverage are distinct contracts; no silent collapsing."""
        extracted = _extraction(
            award_amount="15000 EUR per year",
            tuition_coverage="Full tuition",
            confidence={"award_amount": "high", "tuition_coverage": "high"},
        )
        proposals = project_enrichment(extracted)
        assert proposals["benefits"]["value"] == ["15000 EUR per year"]
        assert "Full tuition" not in proposals["benefits"]["value"]
        assert "Full tuition" in proposals["coverage"]["value"]
        assert "15000 EUR" not in proposals["coverage"]["value"]

    def test_eligibility_vs_requirements_are_separate(self):
        extracted = _extraction(
            eligible_nationalities="Citizens of country X",
            academic_requirements="Bachelor's degree",
            confidence={"eligible_nationalities": "high", "academic_requirements": "high"},
        )
        proposals = project_enrichment(extracted)
        assert proposals["eligibility"]["value"] == ["Citizens of country X"]
        assert proposals["requirements"]["value"] == ["Bachelor's degree"]

    def test_english_requirement_joins_language_and_tests(self):
        extracted = _extraction(
            language_requirement="English at B2",
            test_requirements="IELTS 6.5",
            confidence={"language_requirement": "high", "test_requirements": "high"},
        )
        proposals = project_enrichment(extracted)
        value = proposals["english_requirement"]["value"]
        assert "English at B2" in value
        assert "IELTS 6.5" in value

    def test_low_confidence_fields_are_dropped(self):
        extracted = _extraction(
            tuition_coverage="guessed tuition",
            confidence={"tuition_coverage": "low"},
        )
        proposals = project_enrichment(extracted)
        assert "coverage" not in proposals

    def test_deadline_type_maps_to_precision(self):
        extracted = _extraction(deadline_type="exact", confidence={"deadline_type": "high"})
        proposals = project_enrichment(extracted)
        assert proposals["deadline_precision"]["value"] == "exact"

    def test_no_extraction_yields_no_proposals(self):
        assert project_enrichment(_extraction()) == {}


# ---------------------------------------------------------------- status


class TestStatusDerivation:
    def test_past_deadline_is_closed(self):
        status, _ = derive_status(
            today=date(2026, 6, 1),
            deadline_date=date(2026, 1, 1),
            deadline_display="January 1",
            deadline_precision="day",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_CLOSED

    def test_future_deadline_is_open(self):
        status, _ = derive_status(
            today=date(2026, 1, 1),
            deadline_date=date(2026, 12, 1),
            deadline_display="December 1",
            deadline_precision="day",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_OPEN

    def test_near_deadline_is_closing_soon(self):
        status, _ = derive_status(
            today=date(2026, 6, 1),
            deadline_date=date(2026, 6, 15),
            deadline_display="June 15",
            deadline_precision="day",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_CLOSING_SOON

    def test_explicit_closed_text_wins(self):
        status, reason = derive_status(
            today=date(2026, 6, 1),
            deadline_date=date(2026, 12, 1),
            deadline_display="December 1",
            deadline_precision="day",
            source_text="Applications have closed for this cycle.",
            current_status="open",
        )
        assert status == STATUS_CLOSED
        assert "closed" in reason.lower()

    def test_rolling_is_open(self):
        status, _ = derive_status(
            today=date(2026, 6, 1),
            deadline_date=None,
            deadline_display="Rolling admissions",
            deadline_precision="rolling",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_OPEN

    def test_no_signal_is_unknown(self):
        status, _ = derive_status(
            today=date(2026, 6, 1),
            deadline_date=None,
            deadline_display=None,
            deadline_precision="unknown",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_UNKNOWN

    def test_unparseable_deadline_is_unknown_not_guessed(self):
        status, _ = derive_status(
            today=date(2026, 6, 1),
            deadline_date=None,
            deadline_display="Typically mid-March",
            deadline_precision="month",
            source_text=None,
            current_status="open",
        )
        assert status == STATUS_UNKNOWN


# ---------------------------------------------------------------- service


RICH_HTML = """
<html><head><title>Fulbright Programme</title></head><body>
<h1>Fulbright Foreign Student Scholarship</h1>
<p>Offered by: Fulbright Program</p>
<p>Degree: Master's</p>
<p>Tuition: Full tuition fees covered</p>
<p>Living stipend: 1,000 USD per month</p>
<p>Housing: On-campus housing provided</p>
<p>Insurance: Health insurance included</p>
<p>Travel: Round-trip airfare funded</p>
<p>Award amount: 50,000 USD total</p>
<p>Eligibility criteria: Applicants must hold a Bachelor's degree</p>
<p>Academic requirements: Minimum 3.0 GPA</p>
<p>Language: English proficiency required</p>
<p>IELTS 6.5 minimum</p>
<p>Degree level: Master's</p>
<p>Duration: 12 months</p>
<p>Deadline: March 15, 2027</p>
</body></html>
"""


class TestEnrichmentService:
    def test_dry_run_reports_without_writing(self, session_factory):
        sid = _make_scholarship(session_factory, coverage=[], benefits=[], requirements=[])
        service = ScholarshipEnrichmentService(session_factory, dry_run=True)
        with patch(
            "app.services.scholarship_enrichment.fetch_official_source"
        ) as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                status_code=200,
                final_url="https://www.daad.de/en/",
                content=RICH_HTML,
                content_type="text/html",
            )
            result = service.enrich_one(sid)

        assert result.outcome in (EnrichmentOutcome.ENRICHED, EnrichmentOutcome.NO_USABLE_EXTRACTION)
        session = session_factory()
        try:
            scholarship = session.get(Scholarship, sid)
            # Nothing must have been written.
            assert (scholarship.coverage or []) == []
            assert (scholarship.benefits or []) == []
        finally:
            session.close()

    def test_persists_enrichment_when_not_dry_run(self, session_factory):
        sid = _make_scholarship(session_factory, coverage=[], benefits=[], requirements=[])
        service = ScholarshipEnrichmentService(session_factory, dry_run=False)
        with patch(
            "app.services.scholarship_enrichment.fetch_official_source"
        ) as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True,
                status_code=200,
                final_url="https://www.daad.de/en/",
                content=RICH_HTML,
                content_type="text/html",
            )
            result = service.enrich_one(sid)

        session = session_factory()
        try:
            scholarship = session.get(Scholarship, sid)
            coverage = " | ".join(scholarship.coverage or [])
            assert "Full tuition fees covered" in coverage
            assert "1,000 USD per month" in coverage
            assert "On-campus housing provided" in coverage
            # benefits must NOT be a copy of coverage
            benefits = " | ".join(scholarship.benefits or [])
            assert "50,000 USD total" in benefits
            assert "Full tuition fees covered" not in benefits
            assert result.was_enriched
        finally:
            session.close()

    def test_never_overwrites_existing_verified_text(self, session_factory):
        sid = _make_scholarship(session_factory, duration="12 months")
        service = ScholarshipEnrichmentService(session_factory, dry_run=False)
        with patch(
            "app.services.scholarship_enrichment.fetch_official_source"
        ) as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True, status_code=200, final_url="https://www.daad.de/en/",
                content=RICH_HTML, content_type="text/html",
            )
            service.enrich_one(sid)

        session = session_factory()
        try:
            assert session.get(Scholarship, sid).duration == "12 months"
        finally:
            session.close()

    def test_idempotent_second_run_makes_no_changes(self, session_factory):
        sid = _make_scholarship(session_factory, coverage=[], benefits=[], requirements=[])
        service = ScholarshipEnrichmentService(session_factory, dry_run=False)
        with patch(
            "app.services.scholarship_enrichment.fetch_official_source"
        ) as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True, status_code=200, final_url="https://www.daad.de/en/",
                content=RICH_HTML, content_type="text/html",
            )
            first = service.enrich_one(sid)
            session = session_factory()
            try:
                before = list(session.get(Scholarship, sid).coverage)
            finally:
                session.close()

            second = service.enrich_one(sid)

        assert first.was_enriched
        session = session_factory()
        try:
            after = list(session.get(Scholarship, sid).coverage)
            assert before == after
            assert sorted(after) == sorted(set(after))  # no duplicates introduced
            assert not second.was_enriched or not second.changed_fields
        finally:
            session.close()

    def test_no_official_source_reports_cleanly(self, session_factory):
        sid = _make_scholarship(session_factory, official_source_url=None, application_link=None)
        service = ScholarshipEnrichmentService(session_factory, dry_run=True)
        result = service.enrich_one(sid)
        assert result.outcome == EnrichmentOutcome.NO_OFFICIAL_SOURCE

    def test_third_party_source_refused(self, session_factory):
        sid = _make_scholarship(
            session_factory,
            official_source_url="https://www.scholarshipdb.net/x",
            application_link="https://www.scholarshipdb.net/x",
        )
        service = ScholarshipEnrichmentService(session_factory, dry_run=False)
        with patch("app.services.scholarship_enrichment.fetch_official_source") as mock_fetch:
            result = service.enrich_one(sid)
        assert result.outcome == EnrichmentOutcome.NOT_AUTHORITATIVE
        mock_fetch.assert_not_called()

    def test_source_failure_is_reported_not_raised(self, session_factory):
        sid = _make_scholarship(session_factory)
        service = ScholarshipEnrichmentService(session_factory, dry_run=True, max_attempts=2)
        with patch("app.services.scholarship_enrichment.fetch_official_source") as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False, error_type="not_found",
                error_reason="404",
            )
            result = service.enrich_one(sid)
        assert result.outcome == EnrichmentOutcome.SOURCE_UNAVAILABLE
        assert result.fetch_attempts == 1  # not_found is not retryable

    def test_retryable_failure_retries(self, session_factory):
        sid = _make_scholarship(session_factory)
        service = ScholarshipEnrichmentService(session_factory, dry_run=True, max_attempts=3)
        with patch("app.services.scholarship_enrichment.fetch_official_source") as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=False, error_type="timeout", error_reason="timed out",
            )
            with patch("app.services.scholarship_enrichment.time.sleep"):
                result = service.enrich_one(sid)
        assert result.fetch_attempts == 3
        assert result.retryable is True

    def test_missing_record_is_error_not_exception(self, session_factory):
        service = ScholarshipEnrichmentService(session_factory, dry_run=True)
        result = service.enrich_one(999999)
        assert result.outcome == EnrichmentOutcome.ERROR

    def test_freshness_only_stamped_for_verified_records(self, session_factory):
        verified_id = _make_scholarship(session_factory, is_verified=True)
        unverified_id = _make_scholarship(
            session_factory, title="Unverified", official_source_url="https://www.daad.de/other",
            is_verified=False,
        )
        service = ScholarshipEnrichmentService(session_factory, dry_run=False)
        with patch("app.services.scholarship_enrichment.fetch_official_source") as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True, status_code=200, final_url="https://www.daad.de/en/",
                content=RICH_HTML, content_type="text/html",
            )
            verified_result = service.enrich_one(verified_id)
            unverified_result = service.enrich_one(unverified_id)

        skipped = [u for u in unverified_result.updates if u.field_name == "last_verified_at"]
        assert skipped and skipped[0].action == "skipped"
        assert any(u.field_name == "last_verified_at" for u in verified_result.updates)


# ---------------------------------------------------------------- rate limiting


class TestRateLimiting:
    def test_domain_rate_limiter_is_consulted_before_fetch(self, session_factory):
        sid = _make_scholarship(session_factory)
        limiter = DomainRateLimiter(min_interval_seconds=0.0)
        calls: list[str] = []

        original_wait = limiter.wait_if_needed

        def spy(domain: str) -> None:
            calls.append(domain)
            original_wait(domain)

        limiter.wait_if_needed = spy  # type: ignore[method-assign]

        service = ScholarshipEnrichmentService(
            session_factory, dry_run=True, rate_limiter=limiter, max_attempts=1
        )
        with patch("app.services.scholarship_enrichment.fetch_official_source") as mock_fetch:
            from app.services.official_source_fetcher import OfficialSourceFetchResult

            mock_fetch.return_value = OfficialSourceFetchResult(
                success=True, status_code=200, final_url="https://www.daad.de/en/",
                content="<html><body>nothing useful</body></html>", content_type="text/html",
            )
            service.enrich_one(sid)

        assert calls, "rate limiter was never consulted before fetching"
        assert "daad.de" in calls[0]


# ------------------------------------------------- anti-garbage regression
#
# Every assertion below corresponds to real garbage observed during a dry run
# over the live catalogue. They exist to stop that class of defect returning.


class TestExtractionRejectsGarbage:
    def _extract(self, body: str):
        from app.services.scholarship_extractor import extract_scholarship_information

        return extract_scholarship_information(f"<html><body>{body}</body></html>", "https://x.test")

    def test_negated_coverage_is_not_recorded_as_coverage(self):
        r = self._extract("<p>Tuition: fees are not covered by this programme.</p>")
        assert r.tuition_coverage is None

    def test_negated_benefit_is_not_recorded(self):
        r = self._extract("<p>Amount: travel costs are not included.</p>")
        assert r.award_amount is None

    def test_mid_sentence_fragment_rejected(self):
        """'Award of Excellence at KAIST' must not become a benefit value."""
        r = self._extract("<p>Award of Excellence at KAIST</p>")
        assert r.award_amount is None

    def test_unbalanced_parenthesis_fragment_rejected(self):
        r = self._extract("<p>Stipend: fee, etc.) received by the candidate must not exceed 90,000 yen.</p>")
        assert r.living_stipend is None

    def test_bare_label_produces_nothing(self):
        r = self._extract("<p>Housing:</p>")
        assert r.housing is None

    def test_well_formed_labelled_value_is_kept(self):
        r = self_extract = self._extract("<p>Housing: On-campus residence provided</p>")
        assert r.housing == "On-campus residence provided"

    def test_ielts_label_kept(self):
        r = self._extract("<p>IELTS: 6.5 minimum</p>")
        assert r.test_requirements is not None
        assert "6.5" in r.test_requirements

    def test_stipend_of_phrase_yields_amount(self):
        r = self._extract("<p>Living stipend of $15,000</p>")
        assert r.living_stipend == "$15,000"

    def test_prose_mentioning_insurance_is_not_a_benefit(self):
        r = self._extract("<p>Insurance costs for example).</p>")
        assert r.insurance is None

    def test_garbage_never_reaches_coverage_projection(self):
        r = self._extract(
            "<p>Tuition: fees are not covered by the programme.</p>"
            "<p>Stipend: of 2,100 per month to which several services are added</p>"
        )
        proposals = project_enrichment(r)
        assert "coverage" not in proposals

    def test_bare_generic_word_is_not_a_coverage_item(self):
        """'Full tuition coverage' must not yield the bare word 'coverage'."""
        r = self._extract("<p>Full tuition coverage</p>")
        assert r.tuition_coverage is None

    def test_bare_fees_is_not_a_coverage_item(self):
        r = self._extract("<p>Tuition: fees</p>")
        assert r.tuition_coverage is None

    def test_financial_value_needs_amount_or_coverage_outcome(self):
        r = self._extract("<p>Housing: provided</p>")
        # "provided" is a coverage verb, so this one is acceptable.
        assert r.housing is not None
        r2 = self._extract("<p>Housing: some arrangements</p>")
        assert r2.housing is None

    def test_ui_chrome_is_not_a_benefit(self):
        r = self._extract("<p>Select award type</p>")
        assert r.award_amount is None

    def test_award_type_chrome_is_not_a_benefit(self):
        r = self._extract("<p>Award type: <b>Postgraduate</b></p>")
        assert r.award_amount is None

    def test_real_award_label_still_extracted(self):
        r = self._extract("<p>Award: $10,000</p>")
        assert r.award_amount == "$10,000"

    def test_value_amount_still_extracted(self):
        r = self._extract("<p>Value: $25,000 per year</p>")
        assert r.award_amount == "$25,000 per year"

    def test_link_markers_never_survive(self):
        r = self._extract("<p>Eligibility: <a href='/x'>Scholarship type</a></p>")
        value = (r.eligibility or "")
        assert "[LINK]" not in value
        assert "[/LINK]" not in value

    def test_form_label_is_not_a_value(self):
        r = self._extract("<p>Open date: 1 September</p><p>Close date: 30 November</p>")
        proposals = project_enrichment(r)
        for value in (proposals.get("eligibility") or {}).get("value", []):
            assert value.lower() not in ("open date", "close date")

    def test_mid_sentence_eligibility_rejected(self):
        r = self._extract(
            "<p>We select candidates with strong academic performance and research potential, "
            "requirements, attracting candidates that show excellence.</p>"
        )
        assert r.eligibility is None

    def test_heading_then_value_eligibility_is_captured(self):
        r = self._extract(
            "<h2>Eligibility Criteria</h2><p>Must be a citizen of an eligible country</p>"
        )
        assert r.eligibility is not None
        assert "citizen" in r.eligibility

    def test_inline_eligibility_label_still_captured(self):
        r = self._extract("<p>Eligibility: Open to applicants from 183 countries</p>")
        assert r.eligibility is not None
        assert "183" in r.eligibility


class TestValueTrimming:
    def test_long_value_trimmed_at_clause_boundary(self):
        long_value = "The award covers " + ("a very long list of expenses " * 12) + "cut"
        trimmed = _trim_to_clause(long_value)
        assert len(trimmed) <= 200
        # Must not end mid-word.
        assert not trimmed.endswith(("cu", "c", "c "))
        assert trimmed == trimmed.rstrip()

    def test_short_value_untouched(self):
        assert _trim_to_clause("Full tuition covered") == "Full tuition covered"
