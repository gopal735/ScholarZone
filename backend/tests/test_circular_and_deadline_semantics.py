"""Tests for the PDF circular reader, deadline semantics and prose isolation.

These three exist because the pipeline was reporting real published
information as absent: circulars were never opened, a stated "rolling basis"
deadline was indistinguishable from no deadline, and documents named inside an
eligibility sentence were discarded.
"""

from __future__ import annotations

import io

import pytest

from app.services.deadline_semantics import (
    DeadlineKind,
    classify_deadline_text,
    is_rolling_or_recurring,
    normalise_deadline_precision,
)
from app.services.official_pdf_extractor import (
    OfficialPdfExtractor,
    find_official_pdf_links,
    same_official_site,
)
from app.services.prose_fact_isolation import (
    extract_documents_from_prose,
    extract_selection_from_prose,
)


class TestOfficialSiteScope:
    def test_same_host_is_official(self):
        assert same_official_site(
            "https://www.otago.ac.nz/a.pdf", "https://www.otago.ac.nz/scholarship"
        )

    def test_a_subdomain_of_the_same_publisher_is_official(self):
        assert same_official_site(
            "https://apply.example.org/x.pdf", "https://www.example.org/y"
        )

    def test_a_country_code_domain_does_not_collapse_to_its_government(self):
        """embassy.gov.uk is one embassy; gov.uk is the whole government."""
        assert not same_official_site(
            "https://embassy.gov.uk/x.pdf", "https://www.gov.uk/y"
        )

    def test_two_countries_never_share_a_publisher(self):
        assert not same_official_site(
            "https://bs.china-embassy.gov.cn/x.pdf", "https://www.gov.cn/y"
        )

    def test_a_foreign_host_is_never_official(self):
        assert not same_official_site(
            "https://random-aggregator.com/x.pdf", "https://www.otago.ac.nz/y"
        )


class TestPdfLinkDiscovery:
    HTML = """
    <a href="/circulars/2026-call.pdf">Call for applications</a>
    <a href="https://thirdparty.example/other.pdf">Other</a>
    <a href="/guidelines">HTML page</a>
    <a href="javascript:void(0)">Nothing</a>
    """

    def test_finds_only_same_publisher_pdfs(self):
        links = find_official_pdf_links(
            self.HTML, "https://example.org/page", "https://example.org/x"
        )
        assert links == ["https://example.org/circulars/2026-call.pdf"]

    def test_link_order_is_document_order(self):
        html = '<a href="/b.pdf">B</a><a href="/a.pdf">A</a>'
        assert find_official_pdf_links(html, "https://e.org/", "https://e.org/") == [
            "https://e.org/b.pdf",
            "https://e.org/a.pdf",
        ]

    def test_duplicates_are_collapsed(self):
        html = '<a href="/a.pdf">1</a><a href="/a.pdf">2</a>'
        assert len(find_official_pdf_links(html, "https://e.org/", "https://e.org/")) == 1

    def test_limit_is_respected(self):
        html = "".join(f'<a href="/{i}.pdf">x</a>' for i in range(10))
        assert len(find_official_pdf_links(html, "https://e.org/", "https://e.org/", limit=3)) == 3

    def test_no_links_is_not_an_error(self):
        assert find_official_pdf_links("", "https://e.org/", "https://e.org/") == []


class TestPdfExtractionFailure:
    def _extractor(self, handler):
        import httpx

        client = httpx.Client(transport=httpx.MockTransport(handler))
        return OfficialPdfExtractor(client=client)

    def test_http_error_is_reported_not_raised(self):
        ext = self._extractor(lambda request: __import__("httpx").Response(404))
        result = ext.fetch("https://e.org/a.pdf", "https://e.org/")
        assert result.ok is False
        assert result.error == "http_404"
        assert result.usable is False

    def test_an_html_page_is_not_mistaken_for_a_pdf(self):
        import httpx

        def handler(request):
            return httpx.Response(200, content=b"<html>not a pdf</html>")

        result = self._extractor(handler).fetch("https://e.org/a.pdf", "https://e.org/")
        assert result.error == "not_a_pdf"

    def test_oversized_document_is_refused(self):
        import httpx

        def handler(request):
            return httpx.Response(200, content=b"%PDF-1.4" + b"x" * 5_000)

        import httpx as hx

        client = hx.Client(transport=hx.MockTransport(handler))
        result = OfficialPdfExtractor(client=client, max_pdf_bytes=1_000).fetch(
            "https://e.org/a.pdf", "https://e.org/"
        )
        assert result.error == "too_large"

    def test_transport_failure_is_captured(self):
        def handler(request):
            raise RuntimeError("connection reset")

        result = self._extractor(handler).fetch("https://e.org/a.pdf", "https://e.org/")
        assert result.ok is False
        assert result.error == "RuntimeError"


class TestDeadlineSemantics:
    @pytest.mark.parametrize(
        "text",
        [
            "Applications are accepted on a rolling basis",
            "Open year-round",
            "There is no fixed deadline",
            "First come, first served",
            "Open until places are filled",
        ],
    )
    def test_rolling_policies_are_recognised(self, text):
        assert classify_deadline_text(text) is DeadlineKind.ROLLING
        assert is_rolling_or_recurring(text) is True

    @pytest.mark.parametrize(
        "text",
        ["Deadline: 30 November annually", "Applications close every year", "Annual application"],
    )
    def test_repeating_deadlines_are_recognised(self, text):
        assert classify_deadline_text(text) is DeadlineKind.ANNUAL

    def test_rolling_outranks_annual(self):
        """'reviewed on a rolling basis throughout the year' is a rolling policy."""
        assert classify_deadline_text("reviewed on a rolling basis throughout the year") is (
            DeadlineKind.ROLLING
        )

    def test_exact_date_is_left_to_the_date_parser(self):
        """Classification must not claim a date it cannot see."""
        assert classify_deadline_text("15 March 2027") is not DeadlineKind.ROLLING

    def test_absent_text_is_unknown(self):
        assert classify_deadline_text(None) is DeadlineKind.UNKNOWN
        assert classify_deadline_text("") is DeadlineKind.UNKNOWN

    def test_precision_resolution(self):
        assert normalise_deadline_precision(True, "15 March 2027") == "exact"
        assert normalise_deadline_precision(False, "rolling basis") == "rolling"
        assert normalise_deadline_precision(False, "30 November annually") == "recurring"
        assert normalise_deadline_precision(False, "sometime") == "unknown"


class TestDocumentIsolation:
    def test_documents_inside_an_eligibility_sentence_are_recovered(self):
        found = extract_documents_from_prose(
            "Applicants must submit a certified transcript of records together "
            "with two reference letters and a copy of their passport."
        )
        assert any("transcript" in f.lower() for f in found)
        assert any("passport" in f.lower() for f in found)

    def test_a_negated_document_is_never_recorded_as_required(self):
        assert extract_documents_from_prose("A language certificate is not required.") == []

    def test_optional_material_is_not_a_requirement(self):
        assert extract_documents_from_prose("A CV is recommended but not required.") == []

    def test_output_is_a_verbatim_substring(self):
        """Nothing is paraphrased into existence."""
        source = "Please upload your research proposal and personal statement."
        for clause in extract_documents_from_prose(source):
            assert clause.strip(" ,;.") in source

    def test_one_sentence_does_not_produce_duplicate_clauses(self):
        found = extract_documents_from_prose(
            "You must submit a transcript of records and a degree certificate."
        )
        assert len(found) == len(set(found))

    def test_language_tests_are_recognised(self):
        found = extract_documents_from_prose("Candidates must provide an IELTS score.")
        assert any("IELTS" in f for f in found)

    def test_a_sentence_with_no_requirement_context_yields_nothing(self):
        assert extract_documents_from_prose("The programme is taught in English.") == []


class TestSelectionIsolation:
    def test_selection_process_is_recovered_from_prose(self):
        found = extract_selection_from_prose(
            "Shortlisted candidates are interviewed by a selection committee."
        )
        assert any("interviewed" in f for f in found)

    def test_no_selection_language_yields_nothing(self):
        assert extract_selection_from_prose("The award covers full tuition fees.") == []
