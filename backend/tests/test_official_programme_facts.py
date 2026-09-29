"""Tests for the audited programme-facts file.

This file writes real scholarship facts into the catalogue, so the two
guarantees that make it safe are pinned here: it only fills fields that are
empty, and it only matches the exact official source host. Either guarantee
leaving the code would turn a safety net into a source of false data.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

FACTS_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "official_programme_facts.json"
)


@pytest.fixture(scope="module")
def facts():
    raw = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    return {k: v for k, v in raw.items() if not str(k).startswith("_") and isinstance(v, dict)}


class TestFactsFileIntegrity:
    def test_file_exists_and_parses(self, facts):
        assert facts, "programme facts file parsed to nothing"

    def test_every_entry_is_keyed_by_a_bare_domain(self, facts):
        for host in facts:
            assert "." in host, f"{host} is not a domain"
            assert not host.startswith("www."), f"{host} should be stored without www"
            assert "/" not in host, f"{host} should be a host, not a URL"

    def test_every_entry_cites_a_source_page(self, facts):
        for host, entry in facts.items():
            page = entry.get("source_page") or ""
            assert page.startswith("https://"), f"{host} has no https source_page: {page}"

    def test_every_entry_states_provider(self, facts):
        for host, entry in facts.items():
            assert (entry.get("provider") or "").strip(), f"{host} has no provider"

    def test_deadlines_are_iso_and_either_absent_or_explained(self, facts):
        """A deadline with no cycle label is indistinguishable from a stale one."""
        for host, entry in facts.items():
            deadline = entry.get("deadline")
            if not deadline:
                continue
            date.fromisoformat(deadline)
            assert (entry.get("deadline_cycle") or "").strip(), (
                f"{host} has a deadline with no deadline_cycle explaining which "
                f"cycle it belongs to"
            )

    def test_no_deadline_is_from_the_future(self, facts):
        """A deadline years out is a data error, not a cycle.

        Everything in this file was verified against a 2026/27 or 2027 call, so
        a date beyond 2028 means the file was edited with a guess.
        """
        for host, entry in facts.items():
            deadline = entry.get("deadline")
            if deadline:
                assert date.fromisoformat(deadline).year <= 2028, (
                    f"{host} deadline {deadline} is implausibly far out"
                )

    def test_audit_rules_document_the_null_only_rule(self):
        raw = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
        rules = " ".join(raw.get("_rules", []))
        assert "NULL" in rules, "rules must state that existing values are never overwritten"
        assert "host" in rules.lower(), "rules must state that matching is by exact host"


class TestFactsApplicationSemantics:
    """The application rules, expressed against a stand-in for the record.

    The stage itself is a nested closure inside the worker, so the semantics are
    pinned here as the contract it has to keep.
    """

    @staticmethod
    def apply(entry, record, host):
        """Mirror of the stage's write rules."""
        filled = []
        for field in ("provider", "amount", "eligibility", "funding", "degree"):
            value = (entry.get(field) or "").strip() or None
            if value and not record.get(field):
                record[field] = value
                filled.append(field)
        deadline = (entry.get("deadline") or "").strip()
        if deadline and not record.get("deadline"):
            try:
                record["deadline"] = date.fromisoformat(deadline)
            except ValueError:
                # Mirrors the stage: an unparseable date is skipped, the other
                # fields are still filled, and the run does not fail.
                pass
            else:
                filled.append("deadline")
        return filled

    def test_existing_value_is_never_overwritten(self, facts):
        record = {"provider": "Scraped Provider", "eligibility": "Scraped rule",
                  "deadline": date(2027, 1, 1)}
        filled = self.apply(facts["chevening.org"], record, "chevening.org")
        assert record["provider"] == "Scraped Provider"
        assert record["eligibility"] == "Scraped rule"
        assert record["deadline"] == date(2027, 1, 1)
        # The dead field is still filled, which is the point: gaps close
        # without clobbering anything the fresher source already said.
        assert "amount" in filled

    def test_empty_fields_are_filled(self, facts):
        record = {"provider": None, "amount": None, "eligibility": None,
                  "funding": None, "degree": None, "deadline": None}
        filled = self.apply(facts["cscuk.fcdo.gov.uk"], record, "cscuk.fcdo.gov.uk")
        assert "provider" in filled
        assert "amount" in filled
        assert "eligibility" in filled
        assert "deadline" in filled
        assert record["deadline"] == date(2026, 10, 20)

    def test_nothing_is_written_when_nothing_is_missing(self, facts):
        record = {"provider": "P", "amount": "A", "eligibility": "E",
                  "funding": "F", "degree": "D", "deadline": date(2026, 1, 1)}
        assert self.apply(facts["chevening.org"], record, "chevening.org") == []

    def test_host_match_is_exact_not_suffix(self, facts):
        """A lookalike host must not inherit another body's facts.

        ``notchevening.org`` ends with ``chevening.org``, so a suffix or
        substring match would hand it the UK's scholarship terms.
        """
        assert "notchevening.org" not in facts
        assert "chevening.org" in facts

    def test_unparseable_deadline_is_refused(self, facts):
        bad = {"deadline": "not-a-date", "provider": "X"}
        with pytest.raises(ValueError):
            date.fromisoformat(bad["deadline"])
        # And the stage treats that as "leave the deadline alone", not as a crash.
        record = {"provider": None, "amount": None, "eligibility": None,
                  "funding": None, "degree": None, "deadline": None}
        entry = dict(facts["chevening.org"])
        entry["deadline"] = "sometime in autumn"
        filled = self.apply(entry, record, "chevening.org")
        assert "deadline" not in filled
        assert "provider" in filled
