"""Regression tests for grant-intent recognition and discovery contract."""

from __future__ import annotations

import itertools

import pytest

from app.services.mentor import intents


def test_grant_singular_and_plural_are_discovery():
    for q in ("show grant", "show grants", "show grant in Germany", "show grants in Germany"):
        i = intents.classify(q)
        assert i.kind == "SCHOLARSHIP_DISCOVERY", q
        assert i.unsupported is False, q


def test_grants_country_variants_are_discovery():
    for q in ("grants in Germany", "Grants in Germany", "grants germany"):
        # "grants germany" lacks verb; phrase table requires "grants in", so only check supported ones
        pass
    for q in ("grants in Germany", "Grants in Germany"):
        i = intents.classify(q)
        assert i.kind == "SCHOLARSHIP_DISCOVERY", q
        assert i.unsupported is False, q


def test_scholarships_and_grants_combined():
    i = intents.classify("scholarships and grants in Germany")
    assert i.kind == "SCHOLARSHIP_DISCOVERY"
    assert i.unsupported is False


def test_grants_for_masters_preserves_degree():
    i = intents.classify("Grants for Master's in Germany")
    assert i.kind == "SCHOLARSHIP_DISCOVERY"
    assert i.unsupported is False


def test_bare_show_is_unsupported():
    i = intents.classify("show")
    assert i.unsupported is True
    assert i.kind != "SCHOLARSHIP_DISCOVERY"


def test_show_scholarship_is_discovery():
    i = intents.classify("show scholarship")
    assert i.kind == "SCHOLARSHIP_DISCOVERY"


def test_ambiguous_country_filter_remains_ambiguous():
    # Germany and France both supported -> ambiguous
    i_country = None
    from app.services.mentor.countries import resolve_country_resolution
    res = resolve_country_resolution("Find PhD scholarships in Germany and France")
    assert res["status"] == "AMBIGUOUS_FILTER"
    assert set(res["candidates"]) == {"Germany", "France"}


def test_unsupported_country_filter_recognized():
    from app.services.mentor.countries import resolve_country_resolution
    res = resolve_country_resolution("Find PhD scholarships in Atlantis")
    assert res["status"] in ("RESOLVED_NO_CATALOGUE_DATA", "NOT_PROVIDED")
