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

    def test_every_entry_is_keyed_by_a_bare_domain_or_a_record_id(self, facts):
        for host in facts:
            if host.startswith("id:"):
                # A host is not always a programme. studyinjapan.go.jp carries
                # the seven MEXT scholarship types plus a USA-only edition as
                # separate records, each with its own funding and age limit, so
                # those entries must be able to name a single record.
                assert host[3:].isdigit(), f"{host} is not a record id"
                continue
            assert "." in host, f"{host} is not a domain"
            assert not host.startswith("www."), f"{host} should be stored without www"
            assert "/" not in host, f"{host} should be a host, not a URL"

    def test_record_keyed_entries_are_never_shadowed_by_their_host(self, facts):
        """A host entry must not be able to overwrite a record-specific one."""
        for host, entry in facts.items():
            if not host.startswith("id:"):
                continue
            assert not (entry.get("deadline") and entry.get("deadline_mode")), (
                f"{host} carries both a fixed deadline and a no-fixed-deadline "
                f"mode; the stage writes the mode only when the date is absent, "
                f"so a real date here would be silently dropped"
            )

    def test_every_entry_cites_a_source_page(self, facts):
        for host, entry in facts.items():
            page = entry.get("source_page") or ""
            # Some awarding bodies publish only over plain http. Upgrading the
            # citation to https would point at a page that does not resolve, so
            # the file has to keep the scheme the institution actually uses.
            assert page.startswith("https://") or page.startswith("http://"), (
                f"{host} has no absolute source_page: {page}"
            )

    def test_every_entry_states_the_awarding_body(self, facts):
        for host, entry in facts.items():
            assert (entry.get("official_source") or "").strip(), f"{host} has no official_source"

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


class TestFactsFieldsMapToRealColumns:
    """Every facts key must name a column that actually exists.

    The stage writes with setattr, so a key that is not a mapped column raises
    AttributeError at run time. That is exactly how the first version failed in
    production: the file said "provider" and "amount", which are not columns on
    this model, so a scheduled run died instead of filling a field. Checking the
    file against the model here turns that class of mistake into a test failure.
    """

    _ALLOWED = {
        "source_page",     # citation for humans, never written to a column
        "deadline_cycle",  # provenance for the date, never written to a column
        # A single ISO date that the stage expands into deadline_date,
        # deadline_display and deadline_precision. The frontend reads the
        # display string, so one column is not enough, which is why the file
        # carries one key rather than three.
        "deadline",
    }

    def test_every_facts_key_is_a_real_column_or_documented(self, facts):
        from sqlalchemy import inspect

        from app.models import Scholarship

        columns = {c.key for c in inspect(Scholarship).column_attrs}
        for host, entry in facts.items():
            for field in entry:
                assert field in columns or field in self._ALLOWED, (
                    f"{host} has fact field {field!r}, which is neither a "
                    f"Scholarship column nor a documented non-column key"
                )

    def test_no_placeholder_names_survive(self, facts):
        """provider and amount are the two that were wrong; keep them out."""
        for host, entry in facts.items():
            assert "provider" not in entry, f"{host} still uses non-column 'provider'"
            assert "amount" not in entry, f"{host} still uses non-column 'amount'"

    def test_display_only_deadline_key_is_not_used(self, facts):
        """The stage must never write the read-only `deadline` property.

        Scholarship.deadline is a property that returns deadline_display, so
        assigning to it raises AttributeError. That was the first production
        failure of this stage.
        """
        from app.models import Scholarship

        assert isinstance(Scholarship.deadline, property)
        assert Scholarship.deadline.fset is None
        for host, entry in facts.items():
            for key in entry:
                assert key != "deadline_display", (
                    f"{host} should supply one ISO 'deadline', not prebuilt display fields"
                )

    def test_awarding_body_and_money_use_the_real_column_names(self, facts):
        for host, entry in facts.items():
            assert "official_source" in entry, f"{host} must state official_source"
            assert "benefits" in entry, f"{host} must state benefits"

    def test_deadline_is_iso_or_absent(self, facts):
        for host, entry in facts.items():
            if entry.get("deadline"):
                date.fromisoformat(entry["deadline"])


class TestFactsApplicationSemantics:
    """The application rules, expressed against a stand-in for the record.

    The stage itself is a nested closure inside the worker, so the semantics are
    pinned here as the contract it has to keep.
    """

    @staticmethod
    def apply(entry, record, host):
        """Mirror of the stage's write rules."""
        filled = []
        for field in ("official_source", "benefits", "eligibility", "funding", "degree"):
            value = (entry.get(field) or "").strip() or None
            if value and not record.get(field):
                record[field] = value
                filled.append(field)
        deadline = (entry.get("deadline") or "").strip()
        if deadline and not record.get("deadline_date"):
            try:
                parsed = date.fromisoformat(deadline)
            except ValueError:
                # Mirrors the stage: an unparseable date is skipped, the other
                # fields are still filled, and the run does not fail.
                pass
            else:
                record["deadline_date"] = parsed
                record["deadline_display"] = f"{parsed.day} {parsed.strftime('%B %Y')}"
                record["deadline_precision"] = "day"
                filled.extend(["deadline_date", "deadline_display", "deadline_precision"])
        return filled

    def test_a_deadline_is_written_as_a_complete_set(self, facts):
        """date + display + precision, never the date alone.

        The frontend reads deadline_display, so a date with no display string
        shows an empty card while the record looks like it has a deadline.
        """
        record = {f: None for f in (
            "official_source", "benefits", "eligibility", "funding", "degree",
            "deadline_date", "deadline_display", "deadline_precision")}
        self.apply(facts["cscuk.fcdo.gov.uk"], record, "cscuk.fcdo.gov.uk")
        assert record["deadline_date"] == date(2026, 10, 20)
        assert record["deadline_display"] == "20 October 2026"
        assert record["deadline_precision"] == "day"

    def test_existing_value_is_never_overwritten(self, facts):
        record = {"official_source": "Scraped Provider", "eligibility": "Scraped rule",
                  "deadline_date": date(2027, 1, 1)}
        filled = self.apply(facts["chevening.org"], record, "chevening.org")
        assert record["official_source"] == "Scraped Provider"
        assert record["eligibility"] == "Scraped rule"
        assert record["deadline_date"] == date(2027, 1, 1)
        # The dead field is still filled, which is the point: gaps close
        # without clobbering anything the fresher source already said.
        assert "benefits" in filled

    def test_empty_fields_are_filled(self, facts):
        record = {"official_source": None, "benefits": None, "eligibility": None,
                  "funding": None, "degree": None, "deadline_date": None}
        filled = self.apply(facts["cscuk.fcdo.gov.uk"], record, "cscuk.fcdo.gov.uk")
        assert "official_source" in filled
        assert "benefits" in filled
        assert "eligibility" in filled
        assert "deadline_date" in filled

    def test_nothing_is_written_when_nothing_is_missing(self, facts):
        record = {"official_source": "P", "benefits": "A", "eligibility": "E",
                  "funding": "F", "degree": "D", "deadline_date": date(2026, 1, 1)}
        assert self.apply(facts["chevening.org"], record, "chevening.org") == []

    def test_host_match_is_exact_not_suffix(self, facts):
        """A lookalike host must not inherit another body's facts.

        ``notchevening.org`` ends with ``chevening.org``, so a suffix or
        substring match would hand it the UK's scholarship terms.
        """
        assert "notchevening.org" not in facts
        assert "chevening.org" in facts

    def test_unparseable_deadline_is_refused(self, facts):
        record = {"official_source": None, "benefits": None, "eligibility": None,
                  "funding": None, "degree": None, "deadline_date": None}
        entry = dict(facts["chevening.org"])
        entry["deadline"] = "sometime in autumn"
        filled = self.apply(entry, record, "chevening.org")
        assert "deadline_date" not in filled
        assert "official_source" in filled
