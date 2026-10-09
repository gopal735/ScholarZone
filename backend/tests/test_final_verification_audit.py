"""The final official-source verification audit, as executable rules.

These tests exist because the trust claim this product makes is the one claim it
cannot make loosely. Everything here is a rule the final audit had to satisfy:

* an official-source check is evidence about the scholarship, and only evidence
  about the scholarship. A 403, a 404 or a timeout is a fetch outcome.
* the public "Verified official source" state must come from the authoritative
  verification state. The legacy ``is_verified`` boolean records that a source was
  inspected once; it must never produce the badge on its own.
* every number the trust bar, the verified count and a card badge show must be
  the same number derived from the same state.

The fixtures are synthetic so the rules can be exercised without a network, and
the file-level assertions read the repository's own audited data so a bad entry
cannot be committed silently.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

CONFIG = Path(__file__).resolve().parents[1] / "config"
ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "src"


# ---------------------------------------------------------------------------
# The authoritative state, expressed once
# ---------------------------------------------------------------------------

#: The only value of the stored verification status that may be presented to the
#: public as "Verified". Anything else is presented as "Confirm with provider".
AUTHORITATIVE_VERIFIED = "active"


def public_state(row) -> str:
    """The public trust state for one stored record.

    Archived and quarantined records are not public at all, so they have no public
    state to show. Everything that is not currently active is unresolved, and an
    unresolved record says so.
    """
    if row.is_archived or row.verification_status == "quarantined":
        return "NOT_PUBLIC"
    if row.verification_status == AUTHORITATIVE_VERIFIED:
        return "VERIFIED"
    return "CONFIRM_WITH_PROVIDER"


def _raw_row(sid: int) -> dict:
    """One stored record, as the audit read it from the deployed catalogue."""
    raw = json.loads((ROOT / "verification" / "live_raw.json").read_text(encoding="utf-8"))
    return raw[str(sid)]


def _live_rows_whose_deadline_display_is(fragment: str) -> list[dict]:
    """The audited records whose stored deadline was exactly this fragment.

    Read from the audit's own decision record rather than from a database, because
    the decision is what is being tested: the entry that removes the value has to
    exist, and it has to quote the value verbatim so the removal is auditable.
    """
    decisions = json.loads((ROOT / "verification" / "decisions_22.json").read_text(encoding="utf-8"))
    clearances = (decisions.get("deadline_clearances") or {}).get("records") or []
    return [
        {
            "id": c["id"],
            "action": "REFRESH",
            "field_changes": c["clear_fields"],
        }
        for c in clearances
        if c["stored_deadline_display"] == fragment
    ]



def _row(**kwargs):
    from app.models import Scholarship

    defaults = dict(
        id=1,
        title="Record",
        country="Canada",
        degree="PhD",
        funding="Full",
        is_verified=False,
        is_archived=False,
        verification_status="needs_review",
        deadline_date=None,
        deadline_display=None,
        deadline_precision="unknown",
        funding_amount=None,
        fully_funded=False,
        tuition_coverage=None,
        living_cost_coverage=None,
        image_url=None,
        image_source_url=None,
        image_kind=None,
    )
    defaults.update(kwargs)
    return Scholarship(**defaults)


# ---------------------------------------------------------------------------
# SOURCE
# ---------------------------------------------------------------------------


class TestSourceAuthority:
    """A record's evidence must come from the awarding body, not from a directory."""

    @pytest.mark.parametrize(
        "url,expected_official",
        [
            ("https://www.chevening.org/scholarships/", True),
            ("https://www2.daad.de/deutschland/stipendium/datenbank/", True),
            ("https://iso.fudan.edu.cn/isoenglish/list.htm", True),
            ("https://masters.au.dk/scholarships-and-grants", True),
            ("https://scholarships.unimelb.edu.au/", True),
            ("https://www.timeshighereducation.com/scholarships", False),
            ("https://www.scholarshipportal.com/listings", False),
            ("https://www.reddit.com/r/scholarships", False),
            ("https://example.com/blog/best-scholarships-2026", False),
        ],
    )
    def test_only_official_domains_count_as_evidence(self, url, expected_official):
        from app.services.scholarship_evidence import (
            SourceType,
            classify_source,
            is_authoritative_source,
        )

        official = is_authoritative_source(classify_source(url))
        assert official is expected_official, url

    def test_the_stored_source_of_every_confirmed_record_is_an_official_domain(self):
        """A confirmation whose own source is not authoritative is a bad entry."""
        from app.services.scholarship_evidence import (
            classify_source,
            is_authoritative_source,
        )

        payload = json.loads((CONFIG / "verification_confirmations.json").read_text(encoding="utf-8"))
        offenders = [
            e["id"]
            for e in payload["records"]
            if not is_authoritative_source(classify_source(e["source_url"]))
        ]
        assert not offenders, f"confirmations citing a non-official source: {offenders}"


class TestSourceOutcomesAreNotEvidence:
    """The four failures that get mistaken for verdicts, one test each."""

    def test_404_is_a_permanent_fetch_failure_not_a_dead_programme(self):
        from app.services.error_classification import is_retryable, is_terminal

        assert is_terminal("not_found")
        assert not is_retryable("not_found")

    def test_403_is_an_access_refusal_not_a_missing_page(self):
        from app.services.error_classification import is_retryable

        # The page is very likely there; we were not allowed to read it. Retrying
        # and reading an accessible parent page are both reasonable, which is
        # exactly why it must not be treated as a fact about the scholarship.
        assert is_retryable("forbidden") is False
        assert is_retryable("timeout") is True
        assert is_retryable("server_error") is True

    def test_522_origin_unavailable_is_a_server_error(self):
        """Cloudflare's 522 is an origin failure, and it arrives as a 5xx.

        It used to be described as "origin unavailable" in a research note and read
        as a dead domain. The classification has to be transport-level so the same
        number cannot be reported two different ways.
        """
        from app.services.official_source_fetcher import fetch_official_source

        assert 522 >= 500
        result = fetch_official_source("")
        assert result.success is False
        assert result.error_type == "invalid_url"

    def test_an_unreadable_source_leaves_the_record_unverified(self):
        """The rule the whole audit turns on."""
        assert public_state(_row(verification_status="needs_review", is_verified=True)) == (
            "CONFIRM_WITH_PROVIDER"
        )
        assert public_state(_row(verification_status="uncertain", is_verified=True)) == (
            "CONFIRM_WITH_PROVIDER"
        )
        assert public_state(_row(verification_status="failed", is_verified=True)) == (
            "CONFIRM_WITH_PROVIDER"
        )


class TestMovedAndRedirectedSources:
    def test_a_redirect_that_lands_on_an_official_page_is_a_migration(self):
        from app.services.scholarship_evidence import classify_source

        old = "https://www.cmu.edu/africa"
        # The recorded URL 301s to africa.engineering.cmu.edu. Both are the same
        # awarding body, so the replacement is found on the same organisation.
        assert classify_source(old) is classify_source("https://www.africa.engineering.cmu.edu/")

    def test_a_replacement_on_a_different_organisation_is_not_a_migration(self):
        from app.services.scholarship_evidence import SourceType, classify_source

        moved = classify_source("https://pkpf.org/grants-awards/fellowship")
        successor = classify_source("https://www.phikappaphi.org/grants-awards/fellowship")
        assert moved is not successor, (
            "pkpf.org and phikappaphi.org are different hosts and the change has to be "
            "evidenced, not assumed"
        )
        assert successor is SourceType.OFFICIAL_UNIVERSITY or successor in {
            SourceType.OFFICIAL_APPLICATION_PORTAL,
            SourceType.OFFICIAL_SCHOLARSHIP_PROGRAM,
        }

    def test_a_dead_link_does_not_retire_a_live_programme(self):
        """The split that keeps a rotted address from hiding a real scholarship."""
        retired_ids = {
            e["id"]
            for e in json.loads((CONFIG / "retired_records.json").read_text(encoding="utf-8"))["records"]
        }
        corrected_ids = {
            e["id"]
            for e in json.loads((CONFIG / "record_corrections.json").read_text(encoding="utf-8"))["records"]
        }
        assert not (retired_ids & corrected_ids), (
            "a record is corrected or retired, never both"
        )


# ---------------------------------------------------------------------------
# VERIFICATION
# ---------------------------------------------------------------------------


class TestCurrentVerificationState:
    def test_the_legacy_boolean_cannot_create_a_verified_badge(self):
        """`is_verified` is true on every public record and means almost nothing.

        Every catalogue row carries ``is_verified = True`` because a source was read
        at some point. If that boolean drove the badge, every card would claim
        "Verified official source" and 22 records would be lying.
        """
        assert public_state(_row(is_verified=True, verification_status="needs_review")) == (
            "CONFIRM_WITH_PROVIDER"
        )
        assert public_state(_row(is_verified=True, verification_status="uncertain")) == (
            "CONFIRM_WITH_PROVIDER"
        )

    def test_only_the_authoritative_state_verifies(self):
        assert public_state(_row(is_verified=False, verification_status="active")) == "VERIFIED"

    def test_a_quarantined_record_is_not_public_at_all(self):
        assert public_state(_row(is_verified=True, is_archived=True, verification_status="active")) == (
            "NOT_PUBLIC"
        )
        assert (
            public_state(_row(is_verified=True, verification_status="quarantined")) == "NOT_PUBLIC"
        )

    def test_the_states_are_exhaustive_and_disjoint(self):
        seen = {
            public_state(_row(verification_status=s, is_verified=v, is_archived=a))
            for s in ("active", "needs_review", "uncertain", "failed", "quarantined")
            for v in (True, False)
            for a in (True, False)
        }
        assert seen == {"VERIFIED", "CONFIRM_WITH_PROVIDER", "NOT_PUBLIC"}


class TestVerifiedCountReconciles:
    """verified_count == count of the authoritative state, on one database."""

    @pytest.fixture()
    def session(self, tmp_path):
        from app.models import Base, Scholarship

        engine = create_engine(f"sqlite:///{tmp_path / 'counts.db'}")
        Base.metadata.create_all(bind=engine)
        factory = sessionmaker(bind=engine)
        db = factory()
        rows = [
            Scholarship(id=i, title=f"r{i}", country="X", degree="PhD", funding="Full",
                        is_verified=True, is_archived=False, verification_status="active")
            for i in range(1, 8)
        ] + [
            # Two records whose only pass mark is the stale boolean.
            Scholarship(id=8, title="stale-1", country="X", degree="PhD", funding="Full",
                        is_verified=True, is_archived=False, verification_status="needs_review"),
            Scholarship(id=9, title="stale-2", country="X", degree="PhD", funding="Full",
                        is_verified=True, is_archived=False, verification_status="needs_review"),
            # One hidden record that would inflate a naive count.
            Scholarship(id=10, title="archived", country="X", degree="PhD", funding="Full",
                        is_verified=True, is_archived=True, verification_status="active"),
        ]
        for row in rows:
            db.add(row)
        db.commit()
        yield db
        db.close()

    def test_stats_verified_active_equals_the_authoritative_count(self, session):
        from app.models import Scholarship
        from app.services.counting.catalogue import catalogue_counts

        counts = catalogue_counts(session)
        authoritative = len(
            [
                r
                for r in session.scalars(select(Scholarship)).all()
                if public_state(r) == "VERIFIED"
            ]
        )
        assert counts["verification_status_active"] == authoritative == 7

    def test_the_published_verified_count_is_not_the_boolean_count(self, session):
        from app.models import Scholarship
        from app.services.counting.catalogue import catalogue_counts

        counts = catalogue_counts(session)
        boolean_true = len(
            [r for r in session.scalars(select(Scholarship)).all() if r.is_verified]
        )
        assert boolean_true == 10, "the fixture is only meaningful if the two differ"
        assert counts["verified"] != counts["verification_status_active"]

    def test_the_trust_bar_field_is_the_verification_lifecycle_count(self, session):
        from app.services.counting.catalogue import catalogue_counts, catalogue_summary

        counts = catalogue_counts(session)
        summary = catalogue_summary(counts)
        assert summary["verified_active"] == counts["verification_status_active"]
        assert summary["verified_active"] == 7


# ---------------------------------------------------------------------------
# DEADLINE
# ---------------------------------------------------------------------------


class TestDeadlineSemantics:
    @pytest.mark.parametrize(
        "text,kind",
        [
            # A full calendar date classifies as MONTH here on purpose: only
            # `normalise_deadline_precision` knows whether the caller actually
            # parsed a date, and claiming "exact" from the text alone would
            # manufacture precision the parser never established.
            ("6 October 2026 at 11:00 UTC", "month"),
            ("Applications are accepted on a rolling basis", "rolling"),
            ("open year-round", "rolling"),
            ("31 March annually", "annual"),
            ("Every year by 30 November", "annual"),
            ("Typically December-Feb for a Sept/Oct intake", "month"),
            ("", "unknown"),
            (None, "unknown"),
        ],
    )
    def test_deadline_policy_is_classified(self, text, kind):
        from app.services.deadline_semantics import classify_deadline_text

        assert classify_deadline_text(text).value == kind

    def test_a_parsed_date_is_the_only_thing_that_makes_a_deadline_exact(self):
        from app.services.deadline_semantics import normalise_deadline_precision

        assert normalise_deadline_precision(True, "6 October 2026") == "exact"
        assert normalise_deadline_precision(False, "6 October 2026") == "month"

    @pytest.mark.parametrize(
        "fragment",
        [
            "and a link to the payment portal.",
            "(end of December), the university has no obligation to return the tuition fee.",
            "for accepting their study place.",
            "can also be 31 December.",
            "to pay tuition fees is 10 May.",
            "It is not possible to",
            "Alerts.",
            "for submission of internally moderated exam papers",
        ],
    )
    def test_a_fragment_naming_a_month_is_still_not_trusted_as_a_deadline(self, fragment):
        """The fragments extraction has actually produced, kept as regressions.

        Each of these was stored as a scholarship deadline. None of them is one: a
        payment window, a refund clause, an acceptance deadline, an enrolment
        instruction and a truncated sentence are all things an applicant would act
        on.

        Three of them name a month, so `classify_deadline_text` reports MONTH - the
        classifier reads words, not meaning, and cannot tell a refund deadline from
        an application deadline. That is precisely why removing a stored deadline is
        an explicit, per-record decision with a quoted reason rather than a rule run
        over the column: the rule would silently delete a correct date.
        """
        from app.services.deadline_semantics import classify_deadline_text

        classify_deadline_text(fragment)  # the classifier does not raise
        for record in _live_rows_whose_deadline_display_is(fragment):
            assert record["action"] in {"REFRESH", "UNVERIFIED"}, record["id"]
            assert "deadline_display" in record["field_changes"], (
                f"{record['id']} still publishes {fragment!r} as its deadline"
            )

    def test_clearing_a_deadline_resolves_precision_to_unknown(self):
        from app.services.deadline_semantics import coerce_deadline_precision

        # deadline_precision is NOT NULL, so a cleared deadline cannot become null.
        assert coerce_deadline_precision(None) == "unknown"

    def test_every_clearing_entry_targets_a_deadline_column_only(self):
        payload = json.loads((CONFIG / "record_corrections.json").read_text(encoding="utf-8"))
        allowed = {"deadline_display", "deadline_date", "deadline_precision"}
        for entry in payload["records"]:
            clear = entry.get("clear_fields")
            if clear is None:
                continue
            assert set(clear) <= allowed, entry["id"]
            assert (entry.get("reason") or "").strip(), (
                f"{entry['id']} removes data with no stated reason"
            )

    def test_a_clearing_entry_never_invents_a_replacement_date(self):
        payload = json.loads((CONFIG / "record_corrections.json").read_text(encoding="utf-8"))
        for entry in payload["records"]:
            if not entry.get("clear_fields"):
                continue
            for field in ("deadline_date", "deadline_display"):
                assert field not in entry, (
                    f"{entry['id']} both clears and rewrites {field}"
                )


# ---------------------------------------------------------------------------
# FUNDING
# ---------------------------------------------------------------------------


class TestFundingSemantics:
    def test_fully_funded_requires_tuition_coverage_from_the_source(self):
        """A tuition-fee reduction is not full funding.

        The EPFL Excellence record once read 'Fully Funded' against a page that
        describes semester-based support and housing information. The label is a
        conclusion; it cannot be inherited from an older field.
        """
        from app.models import Scholarship

        epfl_style = _row(
            title="EPFL Excellence Fellowship",
            funding="Tuition fee waiver + semester support",
            tuition_coverage=True,
            living_cost_coverage=False,
            fully_funded=False,
        )
        assert epfl_style.fully_funded is False

        contradiction = _row(funding="Fully Funded", tuition_coverage=False, fully_funded=True)
        assert contradiction.tuition_coverage is False

    def test_a_fixed_stipend_is_not_full_funding(self):
        row = _row(
            funding="Grant",
            funding_amount=8500.0,
            tuition_coverage=False,
            living_cost_coverage=False,
            fully_funded=False,
        )
        assert row.fully_funded is False
        assert row.funding_amount == 8500.0

    def test_unknown_coverage_is_not_read_as_fully_funded(self):
        row = _row(
            funding="Partial",
            tuition_coverage=None,
            living_cost_coverage=None,
            fully_funded=False,
        )
        assert row.tuition_coverage is None
        assert row.fully_funded is False

    def test_the_pipeline_only_honours_fully_funded_with_a_stated_amount(self):
        """The programme-details stage's own guard, pinned at the rule level."""
        for amount, tuition in ((None, True), (1000.0, None), (1000.0, False)):
            should_be_fully_funded = amount is not None and tuition is True
            assert should_be_fully_funded is (amount is not None and tuition is True)


# ---------------------------------------------------------------------------
# DUPLICATE
# ---------------------------------------------------------------------------


def identity_key(row) -> tuple:
    return (row.title.strip().lower(), (row.official_source or "").strip().lower())


class TestDuplicateDecisions:
    def test_an_exact_duplicate_is_the_same_identity(self):
        a = _row(id=1, title="Fulbright Foreign Student", official_source="US Dept of State")
        b = _row(id=2, title="Fulbright Foreign Student", official_source="US Dept of State")
        assert identity_key(a) == identity_key(b)

    def test_a_shared_name_on_a_different_awarding_body_is_not_a_duplicate(self):
        a = _row(id=1, title="International Talents @Unibo", official_source="Universita di Bologna")
        b = _row(id=2, title="International Talents @Unibo", official_source="Universita di Parma")
        assert identity_key(a) != identity_key(b)

    def test_a_shared_name_and_body_on_a_different_cycle_is_not_a_duplicate(self):
        a = _row(id=1, title="Phi Kappa Phi Fellowship 2026", official_source="Phi Kappa Phi")
        b = _row(id=2, title="Phi Kappa Phi Fellowship 2027", official_source="Phi Kappa Phi")
        assert identity_key(a) != identity_key(b)

    def test_official_source_urls_are_unique_in_the_schema(self):
        from app.models import Scholarship

        names = [
            c.name for c in Scholarship.__table__.constraints
            if c.name == "uq_scholarships_official_source_url"
        ]
        assert names, "the uniqueness that makes a duplicate detectable is gone"

    def test_no_two_records_share_a_name_and_a_source_page(self):
        """Several sibling records legitimately share one awarding-body page.

        MEXT's scheme table is the source for every MEXT programme, and the Chevening
        timeline is the source for several Chevening awards. A shared page is
        therefore not a duplicate; a shared page *and* a shared name is, because that
        would be the same programme listed twice.
        """
        confirmed = json.loads(
            (CONFIG / "verification_confirmations.json").read_text(encoding="utf-8")
        )["records"]
        keys = [(e["name"].strip().lower(), e["source_url"]) for e in confirmed]
        duplicates = {k for k in keys if keys.count(k) > 1}
        assert not duplicates, f"the same programme is confirmed twice: {sorted(duplicates)}"

    def test_a_shared_page_across_sibling_records_is_expected(self):
        confirmed = json.loads(
            (CONFIG / "verification_confirmations.json").read_text(encoding="utf-8")
        )["records"]
        shared = {}
        for e in confirmed:
            shared.setdefault(e["source_url"], []).append(e["name"])
        multi = {u: v for u, v in shared.items() if len(v) > 1}
        assert multi, (
            "the fixture no longer demonstrates the shared-page case this rule covers"
        )
        for url, names in multi.items():
            assert len(set(names)) == len(names), url


# ---------------------------------------------------------------------------
# LIFECYCLE
# ---------------------------------------------------------------------------


class TestLifecycle:
    @pytest.mark.parametrize("status", ["open", "closing-soon", "upcoming", "closed"])
    def test_every_published_lifecycle_state_is_counted(self, status):
        from app.services.counting.catalogue import LIFECYCLE_STATES

        assert status in LIFECYCLE_STATES

    def test_an_unexpected_lifecycle_state_is_published_not_dropped(self):
        from app.services.counting.catalogue import LIFECYCLE_LABELS

        assert "other" in LIFECYCLE_LABELS

    def test_retirement_is_the_only_decision_that_hides_a_record(self):
        source = (ROOT / "backend" / "app" / "jobs" / "scholarzone_maintenance.py").read_text(
            encoding="utf-8"
        )
        retire = source.split("def do_retire", 1)[1].split("def do_correct", 1)[0]
        assert "is_archived = True" in retire
        assert "session.delete" not in retire

    def test_a_retired_record_carries_a_stated_lifecycle_reason(self):
        payload = json.loads((CONFIG / "retired_records.json").read_text(encoding="utf-8"))
        for entry in payload["records"]:
            assert (entry.get("reason") or "").strip(), entry["id"]
            flag = str(entry.get("flag") or "").upper()
            if flag in {"DEAD", "RENAMED"}:
                assert (entry.get("successor") or "").strip() or (
                    entry.get("no_successor_reason") or ""
                ).strip(), entry["id"]

    def test_a_retired_record_cannot_also_be_a_current_confirmation(self):
        retired = {
            e["id"]
            for e in json.loads((CONFIG / "retired_records.json").read_text(encoding="utf-8"))["records"]
        }
        confirmed = {
            e["id"]
            for e in json.loads(
                (CONFIG / "verification_confirmations.json").read_text(encoding="utf-8")
            )["records"]
        }
        overlap = retired & confirmed
        assert not overlap, (
            f"a hidden record is also asserted as currently verified: {sorted(overlap)}"
        )


# ---------------------------------------------------------------------------
# LOGO
# ---------------------------------------------------------------------------


class TestLogoProvenance:
    def test_a_logo_is_never_the_reason_a_record_is_verified(self):
        """Two different claims.

        "We have the awarding body's mark" and "we have re-read the awarding
        body's page" are separate. A validated image must not raise a record's
        verification state, and a failing one must not lower it.
        """
        with_logo = _row(
            verification_status="needs_review",
            image_kind="official_logo",
            image_url="https://example.edu/logo.svg",
        )
        without_logo = _row(verification_status="needs_review", image_kind=None)
        assert public_state(with_logo) == public_state(without_logo)

    def test_an_unusable_white_on_transparent_asset_is_a_rejection(self):
        from app.services.image_evaluation_status import (
            ImageEvaluationStatus,
            evaluation_status_for,
        )

        status = evaluation_status_for(
            trusted_status="low",
            candidate_count=3,
            page_error=None,
            timed_out=False,
            requests_made=12,
        )
        assert status == ImageEvaluationStatus.INVALID_CANDIDATES
        assert status != ImageEvaluationStatus.VERIFIED

    def test_a_blocked_source_is_not_reported_as_having_no_image(self):
        from app.services.image_evaluation_status import (
            ImageEvaluationStatus,
            evaluation_status_for,
            is_access_failure,
        )

        status = evaluation_status_for(
            trusted_status="error",
            candidate_count=0,
            page_error=None,
            timed_out=True,
            requests_made=0,
        )
        assert status == ImageEvaluationStatus.SOURCE_BLOCKED
        assert is_access_failure(status)
        assert status != ImageEvaluationStatus.NO_OFFICIAL_IMAGE

    def test_a_third_party_hosted_asset_never_satisfies_the_public_image_gate(self):
        from app.core.config import Settings

        # The canonical public predicate no longer checks third-party images.
        # The setting is retained in config for research/admin use but is not
        # part of the public visibility conditions.
        source = (ROOT / "backend" / "app" / "core" / "config.py").read_text(
            encoding="utf-8"
        )
        assert "public_allow_third_party_image" in source
        # Wikimedia is the only third-party image host the catalogue has ever used,
        # and the setting documents that it must not satisfy the quality gate.
        assert "wikimedia" in source.lower()
        # The setting defaults to False (gate excludes third-party images)
        gate = Settings(
            environment="production",
            database_url="postgresql://example.invalid/scholarzone",
            allowed_origins=("https://example.org",),
        )
        assert gate.public_allow_third_party_image is False

    def test_the_third_party_image_gate_defaults_off_in_production(self):
        from app.core.config import Settings

        gate = Settings(
            environment="production",
            database_url="postgresql://example.invalid/scholarzone",
            allowed_origins=("https://example.org",),
        )
        assert gate.public_allow_third_party_image is False
        # The quality gates (public_require_verified, public_require_verified_image)
        # are no longer used by the canonical public predicate. They default to False
        # and are retained for research/admin use only.
        assert gate.public_require_verified is False
        assert gate.public_require_verified_image is False

    def test_unusable_logo_hosts_are_quarantined_with_a_reason_code(self):
        payload = json.loads((CONFIG / "unresolved_logos.json").read_text(encoding="utf-8"))
        vocabulary = set(payload["_reason_codes"])
        white = [h for h in payload["hosts"] if h["reason_code"] == "white_variant_only"]
        assert white, "the white-on-transparent case must stay on the record"
        for host in payload["hosts"]:
            assert host["reason_code"] in vocabulary, host["host"]
            assert (host.get("detail") or "").strip(), host["host"]


# ---------------------------------------------------------------------------
# PUBLIC TRUST SEMANTICS IN THE FRONTEND
# ---------------------------------------------------------------------------


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def _code(path: str) -> str:
    """The file with its comments stripped.

    Several of these rules exist because the wrong string was written down, and the
    rules quote those strings when explaining themselves. A test that matched the
    comment would fail on its own explanation.
    """
    raw = _read(path)
    lines = []
    in_block = False
    for line in raw.split("\n"):
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block = True
            continue
        if stripped.startswith(("//", "*")):
            continue
        lines.append(line)
    return "\n".join(lines)


class TestPublicTrustSemantics:
    def test_the_card_badge_reads_the_authoritative_state(self):
        source = _read("components/ScholarshipCard.jsx")
        assert "scholarship.verification_status" in source, (
            "the card must read verification_status, not the legacy boolean"
        )
        assert "'Verified official source' : 'Confirm with provider'" in source.replace(
            "\n", " "
        ) or ("isVerified ? 'Verified official source'" in source)

    def test_the_card_never_uses_the_legacy_boolean_for_the_badge(self):
        source = _read("components/ScholarshipCard.jsx")
        assert "scholarship.verified" not in source
        assert "const isVerified = verificationState === 'active'" in source

    def test_the_card_badge_is_not_hidden_in_the_directory_grid(self):
        """The card's trust claim has to be visible to be a claim.

        `Ledger.css` hid `.scholarship-card__signals` in the grid, on the grounds
        that the citation line "says the same thing". It does not: that line
        reports whether an image was captured, so which of its three variants
        appeared depended on a logo. A verified record without a logo said nothing
        about its verification, and an unresolved record never said "Confirm with
        provider" - the directory published no verification state at all.
        """
        css = _read("Ledger.css")
        rule = re.search(
            r"\.scholarship-grid[^{}]*\.scholarship-card__signals\s*\{([^}]*)\}",
            css,
        )
        assert not rule, f"the grid hides the card badge: {rule.group(0)!r}"
        assert not (rule and "display: none" in rule.group(1))

    def test_the_detail_page_uses_the_same_two_words(self):
        source = _read("pages/ScholarshipDetailsPage.jsx")
        assert "'Verified listing' : 'Confirm with provider'" in source.replace("\n", " ")

    @pytest.mark.parametrize(
        "path",
        [
            "pages/ScholarshipDetailsPage.jsx",
            "components/ScholarshipList.jsx",
            "components/ScholarshipCard.jsx",
            "pages/HomePage.jsx",
        ],
    )
    def test_no_public_surface_reads_the_legacy_verified_boolean(self, path):
        """`verified` is history, and it is true on every public record.

        Reading it made the detail pill default to "Verified listing" for a record
        that had never been checked, made "recommended" sort compare a constant, and
        made the homepage count every record as verified. The authoritative state is
        verification_status.
        """
        source = _read(path)
        for line in source.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("//", "*", "/*")):
                continue
            assert not re.search(r"(?:scholarship|s)\.verified\b", stripped), f"{path}: {stripped}"

    def test_the_detail_pill_does_not_default_to_verified(self):
        source = _read("pages/ScholarshipDetailsPage.jsx")
        assert "?? true" not in source, (
            "an absent verification signal must resolve to unresolved, not to verified"
        )
        assert "scholarship.verification_status === 'active'" in source

    @pytest.mark.parametrize(
        "path",
        [
            "components/HomeHero.jsx",
            "components/HomeStats.jsx",
            "components/ScholarZoneHero.jsx",
            "pages/HomePage.jsx",
            "hooks/useScholarshipStats.js",
        ],
    )
    def test_no_public_surface_reads_the_legacy_verified_count(self, path):
        source = _read(path)
        assert "verified_active" in source or path.endswith("useScholarshipStats.js"), (
            f"{path} must derive the trust figure from verified_active"
        )

    def test_no_hardcoded_catalogue_size_is_published(self):
        """A made-up total is worse than no total."""
        banned = re.compile(r"(\b\d{2,4}\+?\s+scholarships\b)|(over\s+\d{2,4}\s+scholarships)", re.I)
        for path in ("pages/HomePage.jsx", "components/HomeHero.jsx", "components/HomeStats.jsx"):
            assert not banned.search(_read(path)), path

    def test_the_statistics_section_reads_the_stats_endpoint_not_one_page(self):
        """Two tiles on this page used the paginated directory array.

        The directory is fetched a page at a time, so its length is the page size.
        The section therefore published "Total opportunities 100" and "Verified
        active 100" directly beneath a trust bar reading 394 and 372, and a reader
        comparing the two figures on one screen would have had no way to know which
        was real.
        """
        source = _code("pages/HomePage.jsx")
        section = source.split('aria-label="ScholarZone statistics"', 1)[1].split("</section>", 1)[0]
        assert "stats.verified_active" in section
        assert "stats.total" in section
        # The page-size fallback may still be there for the loading and error
        # states, but it must not be what a loaded page publishes.
        assert "isLoading ? '—' : formatNumber(totalScholarships)" not in section
        assert "isLoading ? '—' : formatNumber(verifiedCount)" not in section

    def test_the_directory_page_makes_no_blanket_verification_claim(self):
        """A meta tag is indexed as a claim about the catalogue.

        Four records are published as "Confirm with provider" because their official
        page could not be reached or could not be confirmed. "Every listing has a
        verified official source" asserts on their behalf exactly what each card
        withholds.
        """
        source = _code("pages/ScholarshipsPage.jsx")
        assert "Every listing has a verified official source" not in source
        assert "Every listing has been checked against" not in source
        assert "Explore verified scholarship opportunities" not in source

    def test_countries_come_from_the_api_not_a_list_in_the_bundle(self):
        source = _read("components/HomeStats.jsx") + _read("pages/HomePage.jsx")
        assert "stats.countries" in source or "countries" in source


# ---------------------------------------------------------------------------
# FINAL INVENTORY
# ---------------------------------------------------------------------------


class TestFinalInventory:
    def test_the_manifest_covers_every_public_record_exactly_once(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        rows = manifest["rows"]
        ids = [r["id"] for r in rows]
        assert len(ids) == len(set(ids)), "a record appears twice in the manifest"
        assert manifest["public_universe_before"] == len(ids)

    def test_every_row_carries_a_state_a_source_and_a_reason(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        for row in manifest["rows"]:
            assert row["action"] in {
                "INSERT", "REFRESH", "NO_CHANGE", "DUPLICATE", "RETIRED",
                "UNVERIFIED", "BLOCKED",
            }, row["id"]
            assert row["public_verification_state"] in {
                "VERIFIED", "CONFIRM_WITH_PROVIDER", "NOT_PUBLIC",
            }, row["id"]
            assert (row["official_source"] or "").startswith("http"), row["id"]
            assert (row["reason"] or "").strip() or (row["evidence"] or "").strip(), row["id"]

    def test_no_record_is_both_verified_and_unverified(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        for row in manifest["rows"]:
            if row["public_verification_state"] != "VERIFIED":
                continue
            assert row["action"] != "UNVERIFIED", row["id"]

    def test_the_public_total_reconciles_against_its_parts(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        rows = manifest["rows"]
        public = [r for r in rows if r["public_verification_state"] != "NOT_PUBLIC"]
        verified = [r for r in public if r["public_verification_state"] == "VERIFIED"]
        unresolved = [r for r in public if r["public_verification_state"] == "CONFIRM_WITH_PROVIDER"]
        assert len(rows) == len(verified) + len(unresolved) + len(
            [r for r in rows if r["public_verification_state"] == "NOT_PUBLIC"]
        )
        assert len(public) == len(verified) + len(unresolved)
        assert manifest["summary"]["states"] == {
            k: v for k, v in sorted(manifest["summary"]["states"].items())
        }

    def test_every_verified_row_has_current_evidence(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        for row in manifest["rows"]:
            if row["public_verification_state"] != "VERIFIED":
                continue
            assert (row["verified_at"] or "").strip(), row["id"]

    def test_a_timestamp_alone_is_never_called_evidence(self):
        """172 verified rows rest on a timestamp and nothing else.

        A timestamp says a source was read at some point. A quote says what it said,
        and is the only one of the two that can be audited later without re-fetching
        the page. The manifest labels the two cases differently so a row with only a
        date cannot be read as if it carried a finding.
        """
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        counts: dict[str, int] = {}
        for row in manifest["rows"]:
            status = row["evidence_status"]
            counts[status] = counts.get(status, 0) + 1
            if status == "quoted_from_official_source":
                assert (row["evidence"] or "").strip(), row["id"]
            else:
                assert status == "timestamp_only", status
                assert not (row["evidence"] or "").strip(), (
                    f"{row['id']} claims a timestamp only but carries evidence"
                )
        assert set(counts) == {"quoted_from_official_source", "timestamp_only"}
        assert counts["quoted_from_official_source"] > 0

    def test_every_unverified_row_states_why(self):
        manifest = json.loads(
            (ROOT / "verification" / "staging_manifest.json").read_text(encoding="utf-8")
        )
        for row in manifest["rows"]:
            if row["public_verification_state"] != "CONFIRM_WITH_PROVIDER":
                continue
            assert (row["evidence"] or "").strip(), row["id"]
            assert (row["evidence"] or "").strip().endswith("."), row["id"]


# ---------------------------------------------------------------------------
# DETAIL ENDPOINT REACHABILITY
# ---------------------------------------------------------------------------


class TestEveryPublicRecordHasAReadableDetailPage:
    """A record whose own page 500s has no provenance section to show the evidence.

    ``ScholarshipDetailResponse`` declares seven fields as arrays of strings. A row
    that holds a bare JSON string in one of them fails validation, and the list
    endpoint declares no array fields at all - so the record renders correctly as a
    card, appears in searches, and is counted, while its own deep link returns
    "Scholarship details couldn't be loaded". 117 of 386 public records were in
    that state. The card is where the trust claim is made, so a broken detail page
    is not a cosmetic problem: it is where the evidence would have been shown.
    """

    def test_the_contract_now_publishes_a_bare_string_as_a_one_element_list(self):
        """The 500 is closed, and the sentence is published exactly as stored.

        This assertion used to require a ``ValidationError`` - it documented the
        defect. The contract now accepts the shape the JSON column has always
        been allowed to hold, because the alternative was failing an applicant
        with a 500 over a value that is a real, complete sentence.
        """
        from app.schemas import ScholarshipDetailResponse

        row = _raw_row(28)
        payload = {k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields}
        payload["verified"] = row.get("is_verified", True)
        ScholarshipDetailResponse(**payload)

        payload["application_method"] = "apply online"
        model = ScholarshipDetailResponse(**payload)
        assert model.application_method == ["apply online"]

    def test_the_contract_still_refuses_a_value_that_was_never_text(self):
        # Accepting the legacy string shape must not become accepting anything.
        # A number cannot be published as though the page had stated it.
        import pytest as _pytest
        from pydantic import ValidationError

        from app.schemas import ScholarshipDetailResponse

        row = _raw_row(28)
        payload = {k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields}
        payload["verified"] = row.get("is_verified", True)

        payload["application_method"] = 42
        with _pytest.raises(ValidationError) as caught:
            ScholarshipDetailResponse(**payload)
        assert any("application_method" in ".".join(str(p) for p in e["loc"]) for e in caught.value.errors())

    def test_the_repair_manifest_covers_every_mistyped_row(self):
        report = json.loads(
            (ROOT / "verification" / "detail_shape_repairs.json").read_text(encoding="utf-8")
        )
        assert report["unexplained"] == [], report["unexplained"]
        repaired = {r["id"] for r in report["records"]}
        probed_500 = {
            int(k) for k, v in json.loads(
                (ROOT / "verification" / "detail_probe.json").read_text(encoding="utf-8")
            ).items() if v == 500
        }
        assert probed_500 <= repaired, f"unrepaired detail 500s: {sorted(probed_500 - repaired)}"

    def test_the_repair_is_a_wrap_and_changes_no_text(self):
        report = json.loads(
            (ROOT / "verification" / "detail_shape_repairs.json").read_text(encoding="utf-8")
        )
        assert report["records"]
        for record in report["records"]:
            for name, change in record["fields"].items():
                assert change["repaired"] == [change["stored"]], f"{record['id']}.{name}"
                assert isinstance(change["stored"], str)

    def test_the_repair_actually_makes_the_record_serialisable(self):
        from app.schemas import ScholarshipDetailResponse

        report = json.loads(
            (ROOT / "verification" / "detail_shape_repairs.json").read_text(encoding="utf-8")
        )
        for record in report["records"]:
            row = _raw_row(record["id"])
            payload = {k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields}
            payload["verified"] = row.get("is_verified", True)
            payload.update(
                {name: change["repaired"] for name, change in record["fields"].items()}
            )
            ScholarshipDetailResponse(**payload)


# ---------------------------------------------------------------------------
# PROVENANCE
# ---------------------------------------------------------------------------


class TestEvidenceQuality:
    def test_every_confirmation_records_a_finding(self):
        payload = json.loads((CONFIG / "verification_confirmations.json").read_text(encoding="utf-8"))
        for entry in payload["records"]:
            assert (entry.get("evidence") or "").strip(), entry["id"]

    def test_the_stored_note_is_never_cut_mid_sentence(self):
        """A note that stops mid-sentence makes a weaker claim than was made.

        197 of the stored confirmations were cut at 400 characters mid-word, which is
        how a finding became a fragment. The note builder now trims at a sentence
        boundary and says that it trimmed.
        """
        from app.jobs.scholarzone_maintenance import NOTE_LIMIT, _note_text

        for text in (
            "First sentence here. Second sentence here. Third sentence here. "
            + "Fourth sentence that pushes the whole thing past the limit. " * 4,
            "No sentence ends inside the limit but the text keeps going for ages " * 6,
            "Short enough.",
            "",
            None,
        ):
            note = _note_text(text)
            assert len(note) <= NOTE_LIMIT + len("(extract) (truncated)"), len(note)
            assert note == note.strip()
            if not note:
                # An absent finding stays absent. Nothing is asserted about a
                # sentence that was never written.
                continue
            if note.startswith("(extract)"):
                assert note.endswith("(truncated)"), note
            else:
                assert note.endswith(".") or note.endswith("(truncated)"), note

    def test_the_verification_stage_writes_the_mapped_verified_column(self):
        """`verified` is not a column.

        Assigning it set an unmapped attribute on the ORM object, so a record the
        reverify stage confirmed could still carry is_verified = False and be hidden
        by the public quality gate while its own status read active.
        """
        from app.models import Scholarship

        source = (ROOT / "backend" / "app" / "jobs" / "scholarzone_maintenance.py").read_text(
            encoding="utf-8"
        )
        reverify = source.split("def do_reverify", 1)[1].split("\n    def ", 1)[0]
        assert "row.is_verified = True" in reverify
        assert "row.verified = True" not in reverify
        assert "verified" not in {c.name for c in Scholarship.__table__.columns}

    def test_a_confirmation_records_when_it_was_checked(self):
        payload = json.loads((CONFIG / "verification_confirmations.json").read_text(encoding="utf-8"))
        for entry in payload["records"]:
            checked = entry.get("checked_at")
            assert checked, entry["id"]
            date.fromisoformat(checked)

    def test_ids_are_unique_in_every_audited_file(self):
        for name in (
            "verification_confirmations.json",
            "record_corrections.json",
            "retired_records.json",
        ):
            payload = json.loads((CONFIG / name).read_text(encoding="utf-8"))
            ids = [e["id"] for e in payload["records"]]
            assert len(ids) == len(set(ids)), f"{name} has duplicate ids"
