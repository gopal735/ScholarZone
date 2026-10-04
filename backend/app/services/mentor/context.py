"""Assemble the grounded context for one mentor question.

Every value that leaves this module came out of a canonical service. Nothing is
recomputed, re-bucketed or re-derived here, for three reasons that are each a
correctness concern rather than a style preference:

- A second deadline calculation would eventually disagree with the first, and a
  mentor that contradicts the rest of the product is worse than no mentor.
- A second visibility rule would eventually leak a record the catalogue hides.
- A second readiness or fit number would be a claim nobody measured.

**The single most important behaviour in this file is refusing to invent.** A
missing measurement is carried as ``None`` all the way to the response, where it
becomes "ScholarZone has not measured this" rather than a zero, a low score, or a
silent omission. ``_match_index`` in the application workspace swallows engine
failures and returns ``{}``, so an absent fit reading cannot be distinguished from
a broken engine; :func:`_measurement_caveat` records that honestly instead of
asserting a confident "no fit data".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import (
    ApplicationChecklistItem,
    ApplicationRecord,
    Scholarship,
    SavedScholarship,
    User,
)
from ...repositories.scholarships import public_visibility_conditions
from ...schemas_dashboard import APPLICATION_STATE_LABELS, verification_display
from ...verification_contract import (
    normalize_public_verification_status,
    public_verified_from_status,
)
from ..dashboard import build_dashboard
from ..deadline_semantics import coerce_deadline_precision

#: Bounds on what the mentor will read for a single answer. A mentor question is
#: about one student's one decision, so it never needs the whole catalogue and
#: never needs every application.
MAX_EVIDENCE_SCHOLARSHIPS = 6
MAX_EVIDENCE_APPLICATIONS = 6
MAX_EVIDENCE_LINES = 8

#: Precision values that mean "there is a real date, but not to the day". Used to
#: qualify a day count rather than presenting it as exact.
_APPROXIMATE_PRECISIONS = frozenset({"month", "year", "approximate", "varies"})


@dataclass(frozen=True)
class DeadlineFacts:
    """Deadline facts, already resolved by the canonical evaluator.

    ``days_remaining`` is ``None`` for four genuinely different situations -
    closed by lifecycle, no published date, unparseable stored value, and a
    rolling or annual window - so ``kind`` is what makes the difference and the
    wording is built from it rather than from the number.
    """

    days_remaining: int | None
    precision: str
    kind: str
    closed: bool

    @property
    def has_fixed_date(self) -> bool:
        return self.days_remaining is not None

    @property
    def is_approximate(self) -> bool:
        return self.precision in _APPROXIMATE_PRECISIONS

    @property
    def is_overdue(self) -> bool:
        """Only a real past date with a closed round is ever overdue.

        A missing deadline is not overdue. Saying so would invent urgency against
        a record that never published one.
        """
        return self.closed and self.days_remaining is not None and self.days_remaining < 0

    def describe(self) -> str:
        """Honest, canonical-only wording. Never returns "0 days"."""
        if self.closed and self.days_remaining is not None:
            return f"Closed - the published date passed {abs(self.days_remaining)} days ago."
        if self.closed:
            return "Closed - this round is not accepting applications."
        if self.kind in {"rolling", "annual", "recurring"}:
            return "Rolling or annual deadline - no single fixed closing date is published."
        if self.days_remaining is None and self.kind == "unparseable":
            return "A deadline is published but ScholarZone could not read it as a date."
        if self.days_remaining is None:
            return "No published deadline to count down to."
        if self.is_approximate:
            return f"About {self.days_remaining} days left, based on a month-precision date."
        return f"{self.days_remaining} days left."


UNKNOWN_DEADLINE = DeadlineFacts(
    days_remaining=None, precision="unknown", kind="unknown", closed=False
)


@dataclass(frozen=True)
class ScholarshipFacts:
    """One scholarship, reduced to what a mentor answer may assert about it."""

    scholarship_id: int
    name: str
    country: str = ""
    degree: str = ""
    funding: str | None = None
    official_source_url: str | None = None
    verification_status: str = "needs_review"
    verified: bool = False
    verification_label: str = "Confirm with provider"
    is_listed: bool = True
    deadline: DeadlineFacts = UNKNOWN_DEADLINE
    deadline_text: str | None = None
    eligibility: str | None = None
    fit_score: float | None = None
    fit_label: str | None = None
    confidence_score: float | None = None
    data_coverage: float | None = None
    readiness_label: str | None = None
    saved: bool = False
    why: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    unverified_requirements: tuple[str, ...] = ()

    @property
    def fit_is_measured(self) -> bool:
        return self.fit_score is not None

    @property
    def deadline_is_known(self) -> bool:
        return self.deadline.has_fixed_date or self.deadline.closed


@dataclass(frozen=True)
class ApplicationFacts:
    """One application, read through the Application Workspace only."""

    application_id: int
    scholarship_id: int
    name: str
    state: str
    state_label: str
    outcome: str | None = None
    progress_percent: float | None = None
    next_open_task: str | None = None
    deadline: DeadlineFacts = UNKNOWN_DEADLINE
    saved: bool = False
    #: Existence only. The text of a student's private notes is never read into a
    #: mentor context: no grounding benefit, and it is the most sensitive field in
    #: the product.
    has_notes: bool = False
    is_listed: bool = True
    verification_label: str = "Confirm with provider"

    @property
    def is_terminal(self) -> bool:
        return self.state == "submitted" or self.state == "withdrawn"

    @property
    def progress_is_measured(self) -> bool:
        return self.progress_percent is not None


@dataclass(frozen=True)
class StudentFacts:
    """Profile-derived context. Only what a question can legitimately use."""

    has_profile: bool
    profile_is_empty: bool
    strength_score: float | None = None
    strength_band: str | None = None
    strength_label: str | None = None
    supplied_field_count: int = 0
    total_field_count: int = 0
    gaps: tuple[str, ...] = ()
    missing_field_labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class NextActionFacts:
    """A deterministic action, carried through with its band intact.

    ``priority`` is the dashboard's fixed band, not a score this module invented,
    and it is not re-sorted here: the mentor presents the engine's own order so a
    student never sees the mentor disagree with their dashboard.
    """

    code: str
    title: str
    detail: str
    priority: int
    href: str
    action_label: str


@dataclass(frozen=True)
class MentorContext:
    """Everything one answer is allowed to be built from."""

    as_of: date
    student: StudentFacts
    scholarships: tuple[ScholarshipFacts, ...] = ()
    applications: tuple[ApplicationFacts, ...] = ()
    next_actions: tuple[NextActionFacts, ...] = ()
    catalogue_note: str | None = None
    #: Non-fatal degradations, surfaced to the reader instead of hidden.
    caveats: tuple[str, ...] = ()
    focused_scholarship_id: int | None = None
    focused_application_id: int | None = None

    @property
    def has_grounded_data(self) -> bool:
        return bool(self.scholarships or self.applications or self.next_actions)

    def scholarship(self, scholarship_id: int) -> ScholarshipFacts | None:
        for item in self.scholarships:
            if item.scholarship_id == scholarship_id:
                return item
        return None

    def application(self, application_id: int) -> ApplicationFacts | None:
        for item in self.applications:
            if item.application_id == application_id:
                return item
        return None


def _facts_from_days(days: int | None, precision: object) -> DeadlineFacts:
    """Wrap an already-resolved day count without touching the arithmetic.

    A published day count plus its precision is all the mentor needs; the only
    judgement added here is that a negative count means the round is closed,
    which is what the canonical evaluator concluded too.
    """
    coerced = coerce_deadline_precision(precision)
    closed = bool(days is not None and days < 0)
    if closed:
        kind = "closed"
    elif days is None:
        kind = "none"
    else:
        kind = "exact"
    return DeadlineFacts(days_remaining=days, precision=coerced, kind=kind, closed=closed)


def _deadline_for_row(row: Scholarship, as_of: date) -> DeadlineFacts:
    """Canonical deadline evaluation for a raw row, for ids the dashboard omits."""
    from ..matching.eligibility import evaluate_deadline
    from ..matching.repository import CandidateRow, to_facts

    columns = _match_columns_for(row)
    facts = to_facts(CandidateRow(*columns))
    evaluation = evaluate_deadline(facts, as_of)
    return DeadlineFacts(
        days_remaining=evaluation.days_remaining,
        precision=coerce_deadline_precision(evaluation.precision),
        kind=evaluation.kind,
        closed=evaluation.closed,
    )


def _match_columns_for(row: Scholarship) -> tuple:
    """Project a loaded row onto ``CandidateRow`` field order.

    Uses the canonical column list rather than naming 30 attributes by hand,
    which is the failure mode this indirection exists to prevent.
    """
    from ..matching.repository import MATCH_COLUMNS

    values = []
    for column in MATCH_COLUMNS:
        field_name = getattr(column, "key", None) or getattr(column, "name", None)
        values.append(getattr(row, field_name, None))
    return tuple(values)


def _visible_row(db: Session, scholarship_id: int) -> Scholarship | None:
    """Load one scholarship through the canonical visibility predicate.

    Never ``session.get``. The direct-id loader used by the public detail route
    does not filter, and reusing it here would let the mentor describe a record
    the catalogue has archived.
    """
    return db.execute(
        select(Scholarship).where(Scholarship.id == scholarship_id).where(
            *public_visibility_conditions()
        )
    ).scalar_one_or_none()


def _visible_rows(db: Session, ids: Iterable[int]) -> dict[int, Scholarship]:
    wanted = sorted({value for value in ids if value})
    if not wanted:
        return {}
    rows = db.execute(
        select(Scholarship).where(Scholarship.id.in_(wanted)).where(
            *public_visibility_conditions()
        )
    ).scalars()
    return {row.id: row for row in rows}


def _saved_ids(db: Session, user_id: int) -> set[int]:
    """Saved membership in one query.

    A per-card existence query is the N+1 this whole module exists to avoid.
    """
    rows = db.execute(
        select(SavedScholarship.scholarship_id).where(
            SavedScholarship.user_id == user_id
        )
    ).scalars()
    return set(rows)


def _application_ids_by_scholarship(db: Session, user_id: int) -> dict[int, int]:
    rows = db.execute(
        select(ApplicationRecord.scholarship_id, ApplicationRecord.id).where(
            ApplicationRecord.user_id == user_id
        )
    ).all()
    return {scholarship: application for scholarship, application in rows}


def _measurement_caveat(has_any_fit: bool) -> str | None:
    """Say when a missing measurement might be a failure rather than a fact.

    The application workspace's match index catches every exception and returns
    an empty mapping, so "no fit reading" and "the Match engine threw" look
    identical from outside. Rather than assert either, the mentor reports that
    the measurement is unavailable.
    """
    if has_any_fit:
        return None
    return (
        "ScholarZone has not published a match measurement for these records, so no "
        "fit or readiness figure is claimed here."
    )


def build_context(
    db: Session,
    user: User,
    *,
    as_of: date | None = None,
    scholarship_id: int | None = None,
    application_id: int | None = None,
) -> MentorContext:
    """Assemble the bounded context for one question.

    ``build_dashboard`` is called once and reused wholesale. It is the existing
    single bounded assembly for exactly this user, and reusing it means the mentor
    cannot contradict the dashboard the student is already looking at. Everything
    else here is either a bounded extra read for a named record, or arithmetic on
    values that service already published.
    """
    resolved_as_of = as_of or date.today()
    dashboard = build_dashboard(db, user, resolved_as_of)

    saved = _saved_ids(db, user.id)
    application_by_scholarship = _application_ids_by_scholarship(db, user.id)

    caveats: list[str] = []

    # ---- scholarships, most relevant first -----------------------------------
    recommendation_by_id = {match.scholarship_id: match for match in dashboard.matches}

    ordered_ids: list[int] = []
    if scholarship_id:
        ordered_ids.append(scholarship_id)
    ordered_ids.extend(match.scholarship_id for match in dashboard.matches)
    for item in dashboard.saved:
        if item.scholarship.scholarship_id not in ordered_ids:
            ordered_ids.append(item.scholarship.scholarship_id)

    # Anything the dashboard did not already describe as a ranked match is loaded
    # once, through the visibility predicate. A saved scholarship the profile
    # never matched is still a real, publicly visible record the mentor may
    # describe; dropping it because it is absent from the match list would make
    # the mentor unable to answer a question about something the student saved.
    extra_ids = [
        value for value in ordered_ids if value not in recommendation_by_id
    ]
    extra_rows = _visible_rows(db, extra_ids)

    scholarships: list[ScholarshipFacts] = []
    deadline_by_id = {
        entry.scholarship_id: entry for entry in dashboard.deadlines
    }
    for identifier in ordered_ids:
        if len(scholarships) >= MAX_EVIDENCE_SCHOLARSHIPS:
            break
        match = recommendation_by_id.get(identifier)
        row = extra_rows.get(identifier)
        if match is not None:
            scholarships.append(_from_recommendation(match, saved, deadline_by_id))
            continue
        if row is None:
            if identifier == scholarship_id:
                caveats.append(
                    "That scholarship is not in the public catalogue, so no verified "
                    "facts about it are available."
                )
            continue
        scholarships.append(_from_row(row, saved, resolved_as_of))

    # ---- applications --------------------------------------------------------
    applications: list[ApplicationFacts] = []
    if application_id:
        applications = _applications_for(db, user, [application_id], saved, as_of=resolved_as_of)
    else:
        applications = _applications_from_dashboard(
            dashboard, saved, deadline_by_id, application_by_scholarship
        )

    # ---- student -------------------------------------------------------------
    supplied = sum(1 for field in dashboard.profile.fields if field.is_supplied)
    total = len(dashboard.profile.fields)
    student = StudentFacts(
        has_profile=dashboard.has_profile,
        profile_is_empty=dashboard.profile.is_empty,
        strength_score=dashboard.profile_strength.score,
        strength_band=dashboard.profile_strength.band,
        strength_label=dashboard.profile_strength.label,
        supplied_field_count=supplied,
        total_field_count=total,
        gaps=tuple(gap.message for gap in dashboard.gaps[:MAX_EVIDENCE_LINES]),
        missing_field_labels=tuple(
            field.label
            for field in dashboard.profile.fields
            if not field.is_supplied
        ),
    )

    actions = tuple(
        NextActionFacts(
            code=action.code,
            title=action.title,
            detail=action.detail,
            priority=action.priority,
            href=action.href,
            action_label=action.action_label,
        )
        for action in dashboard.next_actions
    )

    caveat = _measurement_caveat(any(item.fit_is_measured for item in scholarships))
    if caveat:
        caveats.append(caveat)

    return MentorContext(
        as_of=resolved_as_of,
        student=student,
        scholarships=tuple(scholarships),
        applications=tuple(applications),
        next_actions=actions,
        caveats=tuple(caveats),
        focused_scholarship_id=scholarship_id,
        focused_application_id=application_id,
    )


def _from_recommendation(match, saved: set[int], deadline_by_id: dict) -> ScholarshipFacts:
    """Convert a published ``MatchRecommendation`` into mentor facts.

    The recommendation already carries a deadline resolved by the canonical
    evaluator, so it is read rather than recalculated. Where the deadline watch
    has a richer record for the same id - which happens for saved and tracked
    records that never entered the ranked match list - that one is preferred,
    because it came from the same evaluator with the same ``as_of``.
    """
    deadline = deadline_by_id.get(match.scholarship_id)
    if deadline is not None:
        days = deadline.days_remaining
        precision = coerce_deadline_precision(deadline.deadline_precision)
    else:
        days = match.days_to_deadline
        precision = coerce_deadline_precision(match.deadline_precision)

    return ScholarshipFacts(
        scholarship_id=match.scholarship_id,
        name=match.name,
        country=match.country,
        degree=match.degree,
        funding=match.funding,
        official_source_url=match.official_source_url,
        verification_status=match.verification_status,
        verified=match.verified,
        verification_label=match.verification_display,
        is_listed=True,
        deadline=DeadlineFacts(
            days_remaining=days,
            precision=precision,
            kind="closed" if days is not None and days < 0 else "exact",
            closed=bool(days is not None and days < 0),
        ),
        deadline_text=match.deadline,
        eligibility=match.eligibility,
        fit_score=match.fit_score,
        fit_label=match.fit_label_display,
        confidence_score=match.confidence_score,
        data_coverage=match.data_coverage,
        readiness_label=match.readiness_label,
        saved=match.scholarship_id in saved,
        why=tuple(line.message for line in match.why[:MAX_EVIDENCE_LINES]),
        gaps=tuple(gap.message for gap in match.needs_attention[:MAX_EVIDENCE_LINES]),
        unverified_requirements=tuple(
            f"{line.summary} ({line.status})"
            for line in match.unverified_requirements[:MAX_EVIDENCE_LINES]
        ),
    )


def _from_row(row: Scholarship, saved: set[int], as_of: date) -> ScholarshipFacts:
    """Facts for a visible scholarship that is not in the ranked match list.

    A student may ask about a scholarship their profile never matched - including
    one they are not yet eligible for - and answering "no deadline" about a record
    that published one would be the mentor being wrong in the direction of
    withholding. So the deadline is resolved through the canonical evaluator
    exactly as it would be for a ranked match.

    Fit, readiness and eligibility stay ``None``: they were genuinely not
    measured for this record, and the answer says so rather than estimating.
    """
    status = normalize_public_verification_status(row.verification_status)
    return ScholarshipFacts(
        scholarship_id=row.id,
        name=row.title,
        country=row.country or "",
        degree=row.degree or "",
        funding=row.funding,
        official_source_url=row.official_source_url,
        verification_status=status,
        verified=public_verified_from_status(status),
        verification_label=verification_display(status),
        is_listed=True,
        deadline=_deadline_for_row(row, as_of),
        deadline_text=row.deadline_display,
        saved=row.id in saved,
    )


def _applications_from_dashboard(
    dashboard, saved: set[int], deadline_by_id: dict, application_by_scholarship: dict
) -> list[ApplicationFacts]:
    """Applications from the dashboard's published list.

    Progress is not on ``ApplicationItem``, so it is deliberately left ``None``
    here rather than recomputed from a checklist this module did not read. The
    mentor says "progress not measured here" instead of implying zero.
    """
    items: list[ApplicationFacts] = []
    for entry in dashboard.applications[:MAX_EVIDENCE_APPLICATIONS]:
        reference = entry.scholarship
        watch = deadline_by_id.get(reference.scholarship_id)
        if watch is not None:
            deadline = _facts_from_days(
                watch.days_remaining, watch.deadline_precision
            )
        else:
            deadline = _facts_from_days(entry.days_remaining, None)
        items.append(
            ApplicationFacts(
                application_id=application_by_scholarship.get(
                    reference.scholarship_id, 0
                ),
                scholarship_id=reference.scholarship_id,
                name=reference.name,
                state=entry.state,
                state_label=entry.state_label,
                deadline=deadline,
                saved=reference.scholarship_id in saved,
                is_listed=getattr(reference, "is_listed", True),
                verification_label=reference.verification_display,
            )
        )
    return items


def _applications_for(
    db: Session, user: User, ids: list[int], saved: set[int], *, as_of: date
) -> list[ApplicationFacts]:
    """Load specific applications through the workspace's ownership rule.

    The query is scoped by ``user_id`` in the same statement, which is what makes
    another student's application simply absent rather than forbidden. This is
    the same 404-not-403 posture as the workspace's own route, so the mentor
    cannot be used to probe for the existence of an id.
    """
    from ..application_workspace import compute_progress, open_task_label

    results: list[ApplicationFacts] = []
    for identifier in ids:
        record = db.execute(
            select(ApplicationRecord).where(
                ApplicationRecord.id == identifier,
                ApplicationRecord.user_id == user.id,
            )
        ).scalar_one_or_none()
        if record is None:
            continue
        row = _visible_row(db, record.scholarship_id)

        # Progress and the next open task are the workspace's own definitions,
        # called rather than reimplemented. Both return ``None`` when there is no
        # counted checklist, which is a fact about the record and not a zero.
        items = list(
            db.execute(
                select(ApplicationChecklistItem)
                .where(ApplicationChecklistItem.application_id == record.id)
                .order_by(ApplicationChecklistItem.position, ApplicationChecklistItem.id)
            ).scalars()
        )
        progress = compute_progress(items)
        next_open = open_task_label(items)

        results.append(
            ApplicationFacts(
                application_id=record.id,
                scholarship_id=record.scholarship_id,
                name=(
                    (row.title if row is not None else None)
                    or record.scholarship_name_snapshot
                    or f"Scholarship {record.scholarship_id}"
                ),
                state=record.state,
                state_label=APPLICATION_STATE_LABELS.get(
                    record.state, record.state
                ),
                outcome=record.outcome,
                progress_percent=progress,
                next_open_task=next_open,
                has_notes=bool(record.notes),
                saved=record.scholarship_id in saved,
                is_listed=row is not None,
                verification_label=(
                    verification_display(
                        normalize_public_verification_status(row.verification_status)
                    )
                    if row is not None
                    else "No longer listed"
                ),
                deadline=_deadline_for_row(row, as_of) if row is not None else UNKNOWN_DEADLINE,
            )
        )
    return results