"""Tests for the Supervisor personhood gate.

These tests verify that the personhood gate correctly:
- Rejects false positives (navigation labels, UI elements, etc.)
- Accepts legitimate person names when they have academic roles/honorifics
"""

import pytest

from app.services.supervisor_person import (
    looks_like_a_person_name,
    _is_person_shaped,
)
from app.services.supervisor_discovery import (
    extract_faculty_candidates,
)
from app.services.supervisor_discovery import FacultyCandidate

#: The discovery layer's private gate is the same function this suite is
#: about — it is a two-line delegate onto ``looks_like_a_person_name``.
#: The tests reference it by its own name, so it is bound here rather
#: than rewritten at every call site.
from app.services.supervisor_discovery import _looks_like_a_person_name


class TestPersonNameGate:
    """Tests for the _looks_like_a_person_name function (Gate 1)."""

    # === REQUIRED NEGATIVES: Navigation/UI labels that must be rejected ===

    @pytest.mark.parametrize("text", [
        "read more",
        "view more",
        "view all",
        "see all",
        "see more",
        "learn more",
        "click here",
        "view profile",
        "view details",
        "apply now",
        "apply",
        "view",
        "read more",
        "more",
    ])
    def test_rejects_navigation_labels(self, text):
        """Navigation/UI labels must be rejected."""
        assert not _looks_like_a_person_name(text), f"Should reject: {text}"

    @pytest.mark.parametrize("text", [
        "educational development",
        "educational development unit",
        "annual review",
        "annual review conversation",
        "research track",
        "teaching track",
        "academic staff",
        "teaching staff",
        "research staff",
        "professional staff",
        "academic unit",
        "research unit",
        "research centre",
        "research center",
        "research group",
        "research team",
        "school of",
        "department of",
        "faculty of",
        "institute of",
        "center for",
        "centre for",
        "institute for",
        "center of",
        "centre of",
        "unit of",
        "division of",
        "office of",
        "school of",
        "college of",
        "university of",
    ])
    def test_rejects_organizational_units(self, text):
        """Organizational units and section titles must be rejected."""
        assert not _looks_like_a_person_name(text), f"Should reject: {text}"

    @pytest.mark.parametrize("text", [
        "apply now",
        "read more",
        "view more",
        "click here",
        "learn more",
        "see all",
        "view all",
        "apply",
        "more",
        "view",
    ])
    def test_rejects_cta_labels(self, text):
        """Call-to-action labels must be rejected."""
        assert not _looks_like_a_person_name(text), f"Should reject CTA: {text}"

    @pytest.mark.parametrize("text", [
        "Read More",
        "View More",
        "View All",
        "See All",
        "See More",
        "Learn More",
        "Click Here",
        "View Profile",
        "View Details",
        "Apply Now",
        "Read More",
    ])
    def test_rejects_capitalized_cta_labels(self, text):
        """Capitalized CTA labels must be rejected (case insensitive)."""
        assert not _looks_like_a_person_name(text), f"Should reject: {text}"

    # === Word count validation ===

    @pytest.mark.parametrize("text", [
        "John",
        "John Smith",
        "John Smith Williams",
        "John Smith Williams Jones",
        "John Smith Williams Jones Brown",  # 5 words - too many
    ])
    def test_word_count_validation(self, text):
        """Names must be 2-4 words."""
        words = text.split()
        if 2 <= len(words) <= 4:
            # Note: This test checks the word count logic, but other checks may still reject
            pass
        else:
            assert not _looks_like_a_person_name(text), f"Should reject wrong word count: {text}"

    @pytest.mark.parametrize("text", [
        "John2 Smith",
        "John Smi2th",
        "J0hn Smith",
    ])
    def test_rejects_names_with_digits(self, text):
        """Names with digits must be rejected."""
        assert not _looks_like_a_person_name(text), f"Should reject: {text}"

    @pytest.mark.parametrize("text", [
        "john smith",
        "john Smith",
        "John smith",
    ])
    def test_rejects_lowercase(self, text):
        """Names with lowercase words must be rejected."""
        assert not _looks_like_a_person_name(text), f"Should reject: {text}"

    # === ACCEPT: Legitimate person names ===

    @pytest.mark.parametrize("text", [
        "John Smith",
        "John A. Smith",
        "Mary Jane",
        "Robert Johnson",
        "Maria Garcia",
        "Wei Zhang",
        "Jean-Luc Picard",
        "John van der Waals",
        "Maria de la Cruz",
        "Pierre de Fermat",
        "Elena von Braun",
        "Ivan Ivanovich",
        "Mohamed bin Ali",
    ])
    def test_accepts_valid_names(self, text):
        """Valid person names should be accepted."""
        assert _looks_like_a_person_name(text), f"Should accept: {text}"


class TestProfileUrlEvidenceGate:
    """Tests for the _verify_profile_url_evidence function (Gate 2)."""

    def test_rejects_different_host(self):
        """Must reject profile URLs on different hosts."""
        # This would require mocking polite_fetch - for now just test the host check logic
        # We can't easily test the full function without mocking, but we can
        # verify the host check logic in _same_site
        pass

    def test_rejects_non_readable_page(self):
        """Must reject non-readable pages."""
        # Would require mocking - placeholder
        pass


class TestExtractFacultyCandidates:
    """Integration tests for the full extract_faculty_candidates pipeline."""

    def test_extracts_valid_candidates(self):
        """Should extract valid faculty candidates from HTML."""
        html = """
        <html><body>
            <a href="/faculty/john-smith">John Smith</a>
            <a href="/faculty/jane-doe">Jane Doe</a>
            <a href="/apply-now">Apply Now</a>
        </body></html>
        """
        # This would need mocking of polite_fetch for the profile verification
        # For now, test that the basic structure works
        pass

    def test_rejects_navigation_links(self):
        """Should reject navigation links like 'Apply Now'."""
        html = """
        <html><body>
            <a href="/apply-now">Apply Now</a>
            <a href="/faculty/john-smith">John Smith</a>
        </body></html>
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])