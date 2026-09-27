"""Tests for the image audit's clear-vs-repair decision.

The dangerous mistake is destroying a legitimate official image because a
metadata column was empty, or keeping an advertising beacon because it came
from the official domain.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "data"))

from audit_images import JUNK_HOSTS, classify, reasons_for  # noqa: E402


class Row:
    def __init__(self, **kw):
        self.image_url = kw.get("image_url")
        self.official_source_url = kw.get("official_source_url", "https://daad.de/x")
        self.image_source_url = kw.get("image_source_url")
        self.image_source_type = kw.get("image_source_type")
        self.image_alt_text = kw.get("image_alt_text")
        self.image_verified_at = kw.get("image_verified_at")
        self.image_kind = kw.get("image_kind")
        self.title = kw.get("title", "A Scholarship")
        self.id = kw.get("id", 1)


FULL = {
    "image_source_url": "https://daad.de/x",
    "image_source_type": "official_page",
    "image_alt_text": "DAAD scholarship",
    "image_verified_at": "2026-01-01",
    "image_kind": "program_image",
}


class TestCompleteImagePasses:
    def test_fully_provenanced_official_image_has_no_reasons(self):
        row = Row(image_url="https://daad.de/img/scholarship.jpg", **FULL)
        assert reasons_for(row) == []


class TestBeaconsAreCleared:
    @pytest.mark.parametrize(
        "url",
        [
            "https://px.ads.linkedin.com/collect/?pid=7882178",
            "https://dc.ads.linkedin.com/collect",
            "https://secure.gravatar.com/avatar/abc.png",
            "https://www.facebook.com/tr?id=12345",
            "https://site.example.org/collect?pid=1",
        ],
    )
    def test_beacon_is_hard_failure(self, url):
        row = Row(image_url=url, **FULL)
        reasons = reasons_for(row)
        clear, _ = classify(reasons, row)
        assert clear is True, f"{url} must be cleared, not kept"

    def test_official_domain_does_not_excuse_a_beacon(self):
        """A tracker served from the official domain is still not an image."""
        row = Row(
            image_url="https://daad.de/collect?pid=9",
            image_source_url="https://daad.de/x",
            image_source_type="official_page",
            image_alt_text="x",
            image_verified_at="2026-01-01",
            image_kind="program_image",
        )
        assert classify(reasons_for(row), row)[0] is True


class TestLegitimateOfficialImagesAreNotDestroyed:
    @pytest.mark.parametrize(
        "url",
        [
            "https://cdn.ubc.ca/scholarship.jpg",
            "https://state.gov/fulbright.jpg",
            "https://ku.dk/study.jpg",
            "https://www.daad.de/shared/study/scholarship-banner.jpg",
        ],
    )
    def test_other_official_institution_hosts_are_reviewed_not_cleared(self, url):
        row = Row(image_url=url, **FULL)
        clear, _ = classify(reasons_for(row), row)
        assert clear is False, "an institution's own host must survive for review"

    def test_missing_kind_is_repaired_not_removed(self):
        row = Row(
            image_url="https://daad.de/img/x.jpg",
            image_source_url="https://daad.de/x",
            image_source_type="official_page",
            image_alt_text="x",
            image_verified_at="2026-01-01",
        )
        reasons = reasons_for(row)
        assert "image_kind_unset" in reasons
        assert classify(reasons, row)[0] is False

    def test_missing_provenance_is_repaired_not_removed(self):
        row = Row(image_url="https://daad.de/img/x.jpg", image_kind="program_image")
        reasons = reasons_for(row)
        assert "incomplete_provenance" in reasons
        assert classify(reasons, row)[0] is False


class TestJunkList:
    def test_stock_photo_hosts_are_listed(self):
        for host in ("unsplash.com", "shutterstock.com", "gettyimages.com"):
            assert host in JUNK_HOSTS

    def test_no_official_university_is_on_the_junk_list(self):
        for host in ("daad.de", "ku.dk", "aau.dk", "state.gov", "ubc.ca"):
            assert host not in JUNK_HOSTS
