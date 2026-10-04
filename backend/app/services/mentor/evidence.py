"""Evidence: the traceable provenance of every factual claim in an answer.

A mentor sentence like "the deadline is 12 March" is only trustworthy if the
reader can see where it came from. Each :class:`EvidenceItem` therefore carries
three things beyond the sentence itself:

* ``field`` - the canonical field the value was read from, so a reader (or a
  later audit) can tell a measurement from a label.
* ``basis`` - which ScholarZone system produced it. This is the honest answer to
  "why should I believe this", and it is why a Match-derived fit score can never
  be presented as though the catalogue had published it.
* ``verification`` - the authoritative verification state of the record the fact
  came from, so an unverified requirement is visibly unverified.

Internal implementation detail never appears here: no column names, no table
names, no internal status enums beyond what the product already shows a student.
"""

from __future__ import annotations

from dataclasses import dataclass

from .context import (
    MAX_EVIDENCE_LINES,
    ApplicationFacts,
    MentorContext,
    ScholarshipFacts,
    StudentFacts,
)
from .guards import bound_text, evidence_is_usable

#: The canonical systems a fact can come from, in the words the product uses.
BASIS_CATALOGUE = "ScholarZone catalogue"
BASIS_MATCH = "Match 2.0"
BASIS_WORKSPACE = "Application Workspace"
BASIS_PROFILE = "Your profile"
BASIS_COUNT = "Count Intelligence"


@dataclass(frozen=True)
class EvidenceItem:
    """One claim, with the provenance that makes it checkable."""

    key: str
    label: str
    value: str
    field: str
    basis: str
    verification: str | None = None
    source_url: str | None = None
    scholarship_id: int | None = None


#: Scope used when deduplicating the student's own profile chips, which belong to
#: no scholarship. Distinct from every ``scholarship_id`` by construction.
_STUDENT_SCOPE = "__student__"

#: The Match engine's normalised funding vocabulary, in words.
#:
#: ``dashboard.py`` publishes ``MatchRecommendation.funding`` as
#: ``funding_state.value`` - a controlled enum, not the catalogue's prose funding
#: text - so a raw ``UNKNOWN`` would reach the interface as a bare token and read
#: as a fault rather than as an answer. These labels say the same thing in the
#: language the rest of the product uses, exactly as ``verification_display`` does
#: for verification. The vocabulary is not invented here; only the wording is.
_FUNDING_WORDS = {
    "FULL": "Full funding.",
    "TUITION_PLUS_LIVING": "Tuition and living costs.",
    "TUITION_ONLY": "Tuition only.",
    "PARTIAL": "Partial funding.",
    "NONE": "No funding is offered.",
}

#: The one value that is an absence rather than a measurement. A funding state of
#: UNKNOWN means the engine could not establish coverage from the catalogue, which
#: is a different statement from "no funding is offered".
FUNDING_UNKNOWN = "UNKNOWN"


def funding_is_unmeasured(value: str | None) -> bool:
    return value is None or value.strip().upper() == FUNDING_UNKNOWN


def funding_word(value: str | None) -> str | None:
    """Readable wording for a canonical funding value, or ``None`` if absent.

    Catalogue prose passes through untouched; only the enum tokens are relabelled.
    """
    if funding_is_unmeasured(value):
        return None
    assert value is not None
    return _FUNDING_WORDS.get(value.strip().upper(), value.strip())


def _verification_for(item: ScholarshipFacts) -> str:
    if not item.is_listed:
        return "No longer listed"
    return item.verification_label


def scholarship_evidence(item: ScholarshipFacts) -> list[EvidenceItem]:
    """Evidence for one scholarship, skipping anything unmeasured.

    A fact nobody measured is not evidence, so it is omitted here and surfaces in
    the answer's *unknown* list instead. That distinction is the difference
    between "the funding is not published" and "ScholarZone never looked".
    """
    evidence: list[EvidenceItem] = []
    verification = _verification_for(item)

    evidence.append(
        EvidenceItem(
            key=f"scholarship-{item.scholarship_id}-identity",
            label="Scholarship",
            value=bound_text(f"{item.name} (record {item.scholarship_id})"),
            field="scholarship.title",
            basis=BASIS_CATALOGUE,
            verification=verification,
            source_url=item.official_source_url,
            scholarship_id=item.scholarship_id,
        )
    )

    if item.is_listed:
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-trust",
                label="Verification",
                value=item.verification_label,
                field="scholarship.verification_status",
                basis=BASIS_CATALOGUE,
                verification=item.verification_label,
                source_url=item.official_source_url,
                scholarship_id=item.scholarship_id,
            )
        )

    # A deadline claim states the precision it was measured at. Without that, a
    # month-precision date reads as an exact one.
    evidence.append(
        EvidenceItem(
            key=f"scholarship-{item.scholarship_id}-deadline",
            label="Deadline",
            value=item.deadline.describe(),
            field="deadline (evaluate_deadline)",
            basis=BASIS_CATALOGUE,
            verification=verification if item.is_listed else None,
            source_url=item.official_source_url,
            scholarship_id=item.scholarship_id,
        )
    )

    funding = funding_word(item.funding)
    if funding:
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-funding",
                label="Funding",
                value=bound_text(funding),
                field="scholarship.funding",
                basis=BASIS_CATALOGUE,
                verification=verification,
                source_url=item.official_source_url,
                scholarship_id=item.scholarship_id,
            )
        )

    if item.eligibility:
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-eligibility",
                label="Eligibility",
                value=_eligibility_word(item.eligibility),
                field="match.eligibility",
                basis=BASIS_MATCH,
                verification=verification,
                scholarship_id=item.scholarship_id,
            )
        )

    if item.fit_score is not None:
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-fit",
                label="Fit",
                value=f"{round(item.fit_score, 1)}"
                + (f" ({item.fit_label})" if item.fit_label else ""),
                field="match.fit_score",
                basis=BASIS_MATCH,
                verification=verification,
                scholarship_id=item.scholarship_id,
            )
        )

    if item.readiness_label:
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-readiness",
                label="Readiness",
                value=item.readiness_label,
                field="match.readiness.band",
                basis=BASIS_MATCH,
                verification=verification,
                scholarship_id=item.scholarship_id,
            )
        )

    # Unverified requirements are the highest-value evidence in the whole
    # system: a published rule ScholarZone could not evaluate against the
    # student. They are quoted from the catalogue, bounded, and labelled as
    # unconfirmed.
    for index, requirement in enumerate(item.unverified_requirements[:MAX_EVIDENCE_LINES]):
        if not evidence_is_usable(requirement):
            continue
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{item.scholarship_id}-requirement-{index}",
                label="Unconfirmed requirement",
                value=bound_text(requirement),
                field="match.eligibility_detail.unverified",
                basis=BASIS_MATCH,
                verification="Confirm with provider",
                source_url=item.official_source_url,
                scholarship_id=item.scholarship_id,
            )
        )

    return evidence


def _eligibility_word(value: str) -> str:
    """The product's own eligibility vocabulary, in words.

    ``NEEDS_VERIFICATION`` is deliberately not softened into "possible" or
    "likely". It means a published rule could not be evaluated, which is a
    different statement from eligible and from ineligible.
    """
    return {
        "ELIGIBLE": "No blocking published rule was found against your profile.",
        "INELIGIBLE": "A published rule currently rules this out for your profile.",
        "NEEDS_VERIFICATION": (
            "A published rule could not be evaluated against your profile, so this "
            "is neither a match nor a refusal."
        ),
    }.get(value, value.replace("_", " ").capitalize())


def application_evidence(item: ApplicationFacts) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = [
        EvidenceItem(
            key=f"application-{item.application_id}-state",
            label="Application state",
            value=item.state_label,
            field="application.state",
            basis=BASIS_WORKSPACE,
            verification=None,
            scholarship_id=item.scholarship_id,
        )
    ]

    if item.outcome:
        evidence.append(
            EvidenceItem(
                key=f"application-{item.application_id}-outcome",
                label="Outcome",
                value=item.outcome.replace("_", " ").capitalize(),
                field="application.outcome",
                basis=BASIS_WORKSPACE,
                scholarship_id=item.scholarship_id,
            )
        )

    evidence.append(
        EvidenceItem(
            key=f"application-{item.application_id}-deadline",
            label="Deadline",
            value=item.deadline.describe(),
            field="deadline (evaluate_deadline)",
            basis=BASIS_WORKSPACE,
            verification=item.verification_label if item.is_listed else None,
            scholarship_id=item.scholarship_id,
        )
    )

    # Progress is only ever stated when the workspace measured it. A `None` here
    # means there is no counted checklist - not zero progress.
    if item.progress_is_measured:
        evidence.append(
            EvidenceItem(
                key=f"application-{item.application_id}-progress",
                label="Tasks completed",
                value=f"{round(item.progress_percent, 1)}%",
                field="application.progress_percent",
                basis=BASIS_WORKSPACE,
                scholarship_id=item.scholarship_id,
            )
        )

    if item.next_open_task:
        evidence.append(
            EvidenceItem(
                key=f"application-{item.application_id}-next-task",
                label="Next open task",
                value=bound_text(item.next_open_task),
                field="application.next_open_task",
                basis=BASIS_WORKSPACE,
                scholarship_id=item.scholarship_id,
            )
        )

    return evidence


def student_evidence(item: StudentFacts) -> list[EvidenceItem]:
    evidence: list[EvidenceItem] = []
    if item.strength_score is not None:
        evidence.append(
            EvidenceItem(
                key="student-strength",
                label="Profile strength",
                value=f"{round(item.strength_score, 1)}"
                + (f" ({item.strength_label})" if item.strength_label else ""),
                field="profile_strength.score",
                basis=BASIS_PROFILE,
            )
        )
    if item.total_field_count:
        evidence.append(
            EvidenceItem(
                key="student-coverage",
                label="Profile fields supplied",
                value=f"{item.supplied_field_count} of {item.total_field_count}",
                field="profile.fields",
                basis=BASIS_PROFILE,
            )
        )
    return evidence


def collect(context: MentorContext, *, limit: int = 10) -> list[EvidenceItem]:
    """Build the evidence set for an answer, de-duplicated and bounded.

    Ordered so the record a question was about leads, then that record's
    applications, then the student's own profile. Truncation is by count and the
    response says so, because a silently shortened evidence list reads as a
    complete one.
    """
    items: list[EvidenceItem] = []
    seen: set[str] = set()
    #: Two canonical systems can independently resolve the same fact about the
    #: same record - the catalogue and the workspace both evaluate one deadline.
    #: Showing the identical sentence twice reads as two findings rather than one
    #: confirmed one, so a repeated (label, value) pair is collapsed onto the
    #: first, highest-priority basis that reported it.
    #:
    #: The pair is scoped to the record the chip is ABOUT, because an identical
    #: sentence about a different scholarship is a different fact, not a repeat.
    #: Keying on the bare pair made every record after the first lose its chips
    #: wherever they shared a verification state, funding wording or day count -
    #: which is most of the catalogue, since 60 of 63 records share one
    #: (verification, funding) combination. ``scholarship_id`` is the right scope
    #: for both a scholarship and an application, because an application's chips
    #: are about that scholarship; the same fact reported by either system is
    #: therefore still recognised as one.
    seen_values: set[tuple[object, str, str]] = set()

    focused = context.focused_scholarship_id
    focused_application = context.focused_application_id

    ordered_applications = sorted(
        context.applications,
        key=lambda entry: (entry.application_id != focused_application, entry.application_id),
    )
    ordered_scholarships = sorted(
        context.scholarships,
        key=lambda entry: (entry.scholarship_id != focused, entry.scholarship_id),
    )

    #: The record the student actually asked about comes first, and an application
    #: the student named is placed ahead of the general scholarship list entirely.
    #: A student asking "what should I finish in application 4" must not be shown
    #: ten scholarship chips and no application, which is what a flat budget
    #: spends first when a profile has eight matches.
    groups = [ordered_applications] if focused_application is not None else []
    groups.append(ordered_scholarships)
    if focused_application is None:
        groups.append(ordered_applications)

    for group in groups:
        for entry in group:
            for chip in (
                application_evidence(entry)
                if isinstance(entry, ApplicationFacts)
                else scholarship_evidence(entry)
            ):
                if len(items) >= limit:
                    return items
                fingerprint = (entry.scholarship_id, chip.label, chip.value)
                if chip.key in seen or fingerprint in seen_values:
                    continue
                seen.add(chip.key)
                seen_values.add(fingerprint)
                items.append(chip)

    for entry in student_evidence(context.student):
        if len(items) >= limit:
            return items
        fingerprint = (_STUDENT_SCOPE, entry.label, entry.value)
        if entry.key in seen or fingerprint in seen_values:
            continue
        seen.add(entry.key)
        seen_values.add(fingerprint)
        items.append(entry)

    return items