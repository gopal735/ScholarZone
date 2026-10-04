"""Regression: the evidence fingerprint lost record identity.

`collect()` deduplicated chips on a global ``(label, value)`` pair, so an
equivalent chip belonging to a DIFFERENT record was silently dropped. Measured
on the shipped code: two records sharing verification/funding/deadline values
gave ``{28: 6, 61: 1}`` - the second record kept only its name.

The contract these tests pin:

* an equivalent chip for a DIFFERENT record must survive;
* a genuinely duplicated chip for the SAME record (two canonical systems
  reporting one fact) must still collapse.

`chip.key` already carries record identity, so the key-based `seen` set was
always correct. Only the value fingerprint needed scoping.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.mentor.context import (  # noqa: E402
    ApplicationFacts,
    DeadlineFacts,
    MentorContext,
    ScholarshipFacts,
    StudentFacts,
)
from app.services.mentor.evidence import collect  # noqa: E402

TODAY = date(2026, 10, 4)


def _deadline(days: int, precision: str = "exact") -> DeadlineFacts:
    return DeadlineFacts(days_remaining=days, precision=precision, kind="date", closed=False)


def _scholarship(sid: int, name: str, deadline: DeadlineFacts | None) -> ScholarshipFacts:
    return ScholarshipFacts(
        scholarship_id=sid,
        name=name,
        country="UK",
        degree="masters",
        funding="Fully funded",
        official_source_url=f"https://example.org/{sid}",
        verification_status="active",
        verified=True,
        verification_label="Verified",
        is_listed=True,
        deadline=deadline,
        deadline_text=None,
        eligibility=None,
        fit_score=80.0,
        fit_label="Strong",
        confidence_score=0.9,
        data_coverage=0.9,
        readiness_label="Ready",
        saved=False,
        why=None,
        gaps=(),
        unverified_requirements=(),
    )


def _application(aid: int, sid: int, name: str, deadline: DeadlineFacts | None) -> ApplicationFacts:
    return ApplicationFacts(
        application_id=aid,
        scholarship_id=sid,
        name=name,
        state="Saved",
        state_label="Saved",
        outcome="Pending",
        progress_percent=40.0,
        next_open_task="Write a personal statement",
        deadline=deadline,
        saved=True,
        has_notes=False,
        is_listed=True,
        verification_label="Verified",
    )


def _student() -> StudentFacts:
    return StudentFacts(
        has_profile=True,
        profile_is_empty=False,
        strength_score=70.0,
        strength_band="good",
        strength_label="Good",
        supplied_field_count=16,
        total_field_count=16,
        gaps=(),
        missing_field_labels=(),
    )


def _ctx(scholarships=(), applications=(), focused_scholarship=None, focused_application=None):
    return MentorContext(
        as_of=TODAY,
        student=_student(),
        scholarships=list(scholarships),
        applications=list(applications),
        next_actions=(),
        catalogue_note=None,
        caveats=(),
        focused_scholarship_id=focused_scholarship,
        focused_application_id=focused_application,
    )


def _chips_by_record(chips):
    counts: dict[int, int] = {}
    for chip in chips:
        if chip.scholarship_id:
            counts[chip.scholarship_id] = counts.get(chip.scholarship_id, 0) + 1
    return counts


class TestEquivalentChipsAcrossDifferentRecordsSurvive:
    def test_two_records_with_identical_values_keep_their_own_chips(self):
        """THE REGRESSION. 60 of 63 catalogue records share (verification,
        funding), so this fires routinely rather than in a contrived case.

        The limit is raised deliberately: at the default budget the second record
        would be truncated by the *count* cap, which is correct behaviour and would
        mask whether its chips were suppressed. Truncation is asserted separately.
        """
        chips = collect(_ctx(scholarships=[
            _scholarship(28, "Chevening Scholarship", _deadline(2)),
            _scholarship(61, "Knight-Hennessy Scholars", _deadline(2)),
        ]), limit=20)

        counts = _chips_by_record(chips)
        assert counts.get(28, 0) >= 5, f"first record lost chips: {counts}"
        assert counts.get(61, 0) >= 5, (
            f"second record was reduced to {counts.get(61)} chip(s); an equivalent "
            "chip belonging to a DIFFERENT record must not be suppressed")

    def test_the_budget_may_truncate_but_must_never_suppress(self):
        """Truncation is by count and is reported; suppression is silent. A record
        cut off by the budget keeps a *prefix* of its chips, whereas a suppressed
        record keeps only its name."""
        chips = collect(_ctx(scholarships=[
            _scholarship(28, "Chevening Scholarship", _deadline(2)),
            _scholarship(61, "Knight-Hennessy Scholars", _deadline(2)),
        ]), limit=8)
        assert len(chips) <= 8
        second = [c for c in chips if c.scholarship_id == 61]
        assert len(second) >= 2, (
            "a budget-truncated record still shows more than its name; "
            f"got {[(c.label) for c in second]}")

    def test_a_record_is_never_reduced_to_its_name_alone(self):
        chips = collect(_ctx(scholarships=[
            _scholarship(28, "Chevening Scholarship", _deadline(2)),
            _scholarship(61, "Knight-Hennessy Scholars", _deadline(2)),
            _scholarship(62, "Third Programme", _deadline(2)),
        ]), limit=20)
        for chip in chips:
            if chip.scholarship_id and chip.field == "scholarship.title":
                continue
            assert chip.scholarship_id in (28, 61, 62) or chip.scholarship_id is None
        counts = _chips_by_record(chips)
        assert all(v > 1 for v in counts.values()), (
            f"a record was left with only a name chip: {counts}")

    def test_identical_funding_and_verification_do_not_cross_suppress(self):
        chips = collect(_ctx(scholarships=[
            _scholarship(1, "Alpha", _deadline(4)),
            _scholarship(2, "Beta", _deadline(9)),
        ]), limit=20)
        funding = {c.scholarship_id for c in chips if c.label == "Funding"}
        verification = {c.scholarship_id for c in chips if c.label == "Verification"}
        assert funding == {1, 2}, f"funding chip suppressed across records: {funding}"
        assert verification == {1, 2}, f"verification chip suppressed: {verification}"

    def test_a_focused_record_keeps_priority_and_others_keep_their_chips(self):
        chips = collect(_ctx(scholarships=[
            _scholarship(28, "Chevening Scholarship", _deadline(2)),
            _scholarship(61, "Knight-Hennessy Scholars", _deadline(2)),
        ], focused_scholarship=61), limit=20)
        assert chips[0].scholarship_id == 61, "the focused record must lead"
        counts = _chips_by_record(chips)
        assert counts.get(28, 0) >= 5 and counts.get(61, 0) >= 5, (
            f"focused priority must not be paid for by suppressing others: {counts}")


class TestGenuineDuplicatesWithinOneRecordStillCollapse:
    def test_the_same_record_reported_by_two_systems_collapses_to_one_deadline(self):
        """The dedup's original purpose: the catalogue and the workspace both
        evaluate one deadline for one scholarship."""
        chips = collect(_ctx(
            scholarships=[_scholarship(7, "Shared Programme", _deadline(20))],
            applications=[_application(3, 7, "Shared Programme", _deadline(20))],
        ), limit=20)
        deadlines = [c for c in chips if c.scholarship_id == 7 and "deadline" in (c.field or "")]
        assert len(deadlines) == 1, (
            f"one record's deadline should appear once, got {len(deadlines)}: "
            f"{[(c.field, c.value) for c in deadlines]}")

    def test_two_applications_on_one_scholarship_do_not_duplicate_a_deadline(self):
        chips = collect(_ctx(
            scholarships=[_scholarship(8, "Shared", _deadline(15))],
            applications=[
                _application(1, 8, "Shared", _deadline(15)),
                _application(2, 8, "Shared", _deadline(15)),
            ],
        ), limit=20)
        deadlines = [c for c in chips if c.scholarship_id == 8 and "deadline" in (c.field or "")]
        assert len(deadlines) == 1, f"duplicate deadline for one record: {len(deadlines)}"


class TestOtherGuaranteesAreUnchanged:
    def test_student_evidence_is_still_appended(self):
        chips = collect(_ctx(scholarships=[_scholarship(1, "Alpha", _deadline(3))]), limit=20)
        assert any(c.field and c.field.startswith("profile") for c in chips), (
            "student evidence must still appear")

    def test_deadline_precision_wording_is_untouched(self):
        exact = [c for c in collect(_ctx(scholarships=[_scholarship(1, "A", _deadline(11, "exact"))]), limit=20)
                 if "deadline" in (c.field or "")]
        month = [c for c in collect(_ctx(scholarships=[_scholarship(1, "A", _deadline(11, "month"))]), limit=20)
                 if "deadline" in (c.field or "")]
        assert exact and exact[0].value == "11 days left."
        assert month and month[0].value.startswith("About 11 days left")

    def test_funding_unknown_remains_unmeasured(self):
        chips = collect(_ctx(scholarships=[
            _scholarship(1, "A", _deadline(3)),
        ]), limit=20)
        assert not [c for c in chips if c.value in (None, "", "UNKNOWN")]