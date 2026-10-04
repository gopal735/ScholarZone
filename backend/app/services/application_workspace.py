"""Application Workspace 1.0: the private, trackable side of an application.

This module turns a saved scholarship into a structured workspace without
duplicating any business truth. The rules it follows, and why:

**The catalogue stays canonical.** Title, provider, country, funding, deadline
and trust all come from the live scholarship row. An application keeps an
immutable snapshot only so that history stays readable when a record later leaves
the public universe - archived, or no longer publicly verified. Live values
always win; the snapshot is a fallback, never an override.

**Deadlines are asked of the engine, never computed.** Every day count comes from
the matching engine's own ``evaluate_deadline``, which owns the month-end rule,
the rolling and recurring handling, and the closed-status precedence. This module
contains no date arithmetic at all.

**Progress is not fit.** Progress answers "how far have I got" and is a plain
weighted count of completed tasks. Fit, confidence and readiness answer "how well
do I match" and are copied from Match 2.0 for the same profile. They are separate
numbers that are never combined, and a student can be a poor fit with a finished
application, or a strong fit with nothing done.

**Nothing is invented.** A checklist task either comes from a generic
preparation template, from a Match gap, or from a requirement the provider
actually published - and it says which. The module will never assert that a
specific document is required on its own authority.

**Ownership is the session.** Nothing here accepts a user id. Every query is
scoped by the ``User`` the session resolved to.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import ApplicationChecklistItem, ApplicationRecord, Scholarship, User
from ..repositories.scholarships import public_visibility_conditions
from ..schemas_application import (
    APPLICATION_OUTCOMES,
    MAX_CHECKLIST_ITEMS,
    MAX_NOTES_LENGTH,
    OUTCOME_LABELS,
    TERMINAL_OUTCOMES,
    ApplicationDetail,
    ApplicationListResponse,
    ApplicationOutcome,
    ApplicationSummary,
    ChecklistItemResponse,
    ChecklistSource,
    ScholarshipAvailability,
)
from ..verification_contract import (
    normalize_public_verification_status,
    public_verified_from_status,
)
from ..schemas_dashboard import APPLICATION_STATE_LABELS, verification_display
from .deadline_semantics import coerce_deadline_precision
from .matching.eligibility import evaluate_deadline
from .matching.repository import MATCH_COLUMNS, CandidateRow, to_facts
from .matching.types import GapCategory

#: The canonical lifecycle vocabulary, unchanged from Dashboard 1.0. This module
#: validates transitions within it; it never extends it.
APPLICATION_STATES: frozenset[str] = frozenset(APPLICATION_STATE_LABELS)

#: Legal transitions. Anything absent here is refused with a 409.
#:
#: ``submitted`` deliberately cannot go back to ``in_progress``, ``planning`` or
#: ``saved``. A submitted application has been seen by the provider; quietly
#: reopening it would let a student believe an application is live when the
#: provider already holds it. Withdrawing is the honest exit, and ``withdrawn``
#: can be reopened explicitly.
#:
#: ``withdrawn`` can return to ``saved``/``planning`` because withdrawing is a
#: decision a student may reverse while the round is still open - unlike
#: submission, which is not reversible once made.
STATE_TRANSITIONS: dict[str, frozenset[str]] = {
    "saved": frozenset({"planning", "in_progress", "withdrawn"}),
    "planning": frozenset({"saved", "in_progress", "withdrawn"}),
    "in_progress": frozenset({"planning", "submitted", "withdrawn"}),
    "submitted": frozenset({"withdrawn"}),
    "withdrawn": frozenset({"saved", "planning"}),
}

#: States a student cannot act on further. A terminal state is one the provider
#: or the student has finished with; only ``withdrawn`` can be reopened.
TERMINAL_STATES: frozenset[str] = frozenset({"submitted"})

OUTCOME_TRANSITIONS: dict[str, frozenset[str]] = {
    ApplicationOutcome.PENDING.value: frozenset(
        {
            ApplicationOutcome.ACCEPTED.value,
            ApplicationOutcome.REJECTED.value,
            ApplicationOutcome.WAITLISTED.value,
            ApplicationOutcome.WITHDRAWN.value,
        }
    ),
    ApplicationOutcome.ACCEPTED.value: frozenset(),
    ApplicationOutcome.REJECTED.value: frozenset(),
    ApplicationOutcome.WAITLISTED.value: frozenset(),
    ApplicationOutcome.WITHDRAWN.value: frozenset(),
}

#: Only a submitted application can have an outcome. Accepting something that was
#: never sent would be a claim ScholarZone has no basis for.
OUTCOME_ALLOWED_STATES: frozenset[str] = frozenset({"submitted"})

#: Bounded so a student's workspace cannot become an unbounded filing system.
MAX_APPLICATIONS = 200


class WorkspaceError(Exception):
    """Base class carrying the HTTP status the router should surface."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(WorkspaceError):
    """A resource the caller may not see. Also used for another user's rows."""

    status_code = 404


class Conflict(WorkspaceError):
    """A stale write, or an illegal transition."""

    status_code = 409


class ValidationProblem(WorkspaceError):
    status_code = 422


# --------------------------------------------------------------- deadline facts


class ScholarshipContext:
    """What the workspace needs to know about one scholarship.

    ``facts`` is built by the matching engine's own ``to_facts``, and
    ``deadline`` by its own ``evaluate_deadline``, so a deadline shown here is
    produced by exactly the code that produced it on a match card. The fields
    below are the only ones the workspace is allowed to publish.
    """

    __slots__ = (
        "scholarship_id",
        "is_visible",
        "name",
        "country",
        "degree",
        "funding",
        "provider",
        "official_source_url",
        "verification_status",
        "deadline_date",
        "deadline_display",
        "deadline_precision",
        "deadline_evaluation",
        "status",
        "published_requirements",
    )

    def __init__(self, row: CandidateRow, is_visible: bool):
        facts = to_facts(row)
        self.scholarship_id = row.id
        self.is_visible = is_visible
        self.name = row.title
        self.country = row.country
        self.degree = row.degree
        self.funding = row.funding
        self.provider = row.official_source
        self.official_source_url = row.official_source_url
        self.verification_status = row.verification_status
        self.deadline_date = row.deadline_date
        self.deadline_display = row.deadline_display
        self.deadline_precision = coerce_deadline_precision(row.deadline_precision)
        self.status = row.status
        self.published_requirements = tuple(row.documents or ())
        self.deadline_evaluation = None  # set by load_contexts, needs as_of


def load_contexts(db: Session, ids: list[int], as_of: date) -> dict[int, ScholarshipContext]:
    """Load engine-shaped scholarship context for a bounded id set.

    Two queries, both bounded by the ids the caller already owns - never a scan
    of the catalogue. The first resolves visibility through the canonical
    predicate; the second loads the engine's own column list so the deadline can
    be evaluated by ``evaluate_deadline`` rather than approximated.

    Rows are loaded whether or not they are publicly visible. The owner is
    entitled to the history of a scholarship they applied to, and the visibility
    result is returned alongside so the interface can be honest about the
    difference. What is *published* is still bounded to the display fields above:
    loading a row internally is not the same as exposing it.
    """
    if not ids:
        return {}

    rows = db.execute(select(*MATCH_COLUMNS).where(Scholarship.id.in_(ids))).all()
    if not rows:
        return {}

    row_ids = {row.id for row in rows}
    visible_ids = set(
        db.execute(
            select(Scholarship.id)
            .where(Scholarship.id.in_(row_ids))
            .where(*public_visibility_conditions())
        ).scalars()
    )

    contexts: dict[int, ScholarshipContext] = {}
    for row in rows:
        context = ScholarshipContext(CandidateRow(*row), row.id in visible_ids)
        context.deadline_evaluation = evaluate_deadline(to_facts(CandidateRow(*row)), as_of)
        contexts[context.scholarship_id] = context

    return contexts


# ------------------------------------------------------------------- checklist


def _generic_template(state: str) -> list[dict]:
    """Preparation steps offered for every application.

    Every one is labelled ``generic``: none of them asserts that this particular
    provider requires anything. They exist because preparing an application
    involves these steps in general, and a student can dismiss any of them.
    """
    template = [
        {
            "key": "review_eligibility",
            "label": "Review the eligibility criteria",
            "description": "Read every published requirement and check it against your profile.",
        },
        {
            "key": "review_official_requirements",
            "label": "Review the official requirements",
            "description": "Open the provider's own page and confirm what they ask for.",
        },
        {
            "key": "verify_language_requirement",
            "label": "Confirm the language requirement",
            "description": "Check any language or test score the provider publishes.",
        },
        {
            "key": "prepare_application_materials",
            "label": "Prepare your application materials",
            "description": "Draft whatever the provider asks you to submit.",
        },
        {
            "key": "submit_application",
            "label": "Submit the application",
            "description": "Submit on the provider's own site, then mark this application submitted.",
            "action_target": "official_source",
        },
    ]

    items = [
        {
            **step,
            "source": ChecklistSource.GENERIC.value,
            "position": index,
            # Submission is tracked by the application *state*, not by a
            # checkbox. Counting it here would mean an application submitted by
            # changing state still showed as incomplete forever.
            "weight": 0 if step["key"] == "submit_application" else 1,
        }
        for index, step in enumerate(template)
    ]

    if state == "submitted":
        # Once submitted, the generic "submit" task is behind the student and
        # marking it complete would be theatre.
        items = [item for item in items if item["key"] != "submit_application"]

    return items


def derive_checklist(
    state: str,
    context: ScholarshipContext | None,
    match_result=None,
) -> list[dict]:
    """Build the initial task set from canonical data.

    Three sources, each declaring itself: generic preparation steps, gaps the
    matching engine reported for this student, and requirements the provider
    actually published. The last is the only source permitted to name a specific
    document, and it names what the record says rather than what a typical
    application needs.

    Derivation happens once, when the application is created, and the result is
    then the student's own working list. Re-deriving on every read would let
    tasks appear and vanish as the catalogue or the profile changed, which makes
    progress jump for reasons the student did not cause.
    """
    items = _generic_template(state)
    seen = {item["key"] for item in items}

    # Published requirements, straight from the catalogue row.
    if context is not None:
        for index, document in enumerate(context.published_requirements[:8]):
            label = str(document).strip()
            if not label:
                continue
            key = f"published_requirement_{index}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "key": key,
                    "label": f"Prepare: {label}",
                    "description": "The provider lists this among its required materials.",
                    "source": ChecklistSource.PUBLISHED_REQUIREMENT.value,
                    "source_detail": "documents",
                    "position": len(items),
                    "weight": 1,
                    "action_target": "scholarship",
                }
            )

    # Match gaps, which are evidence about this student rather than claims
    # about the provider.
    if match_result is not None:
        for gap in match_result.gaps:
            if gap.category is not GapCategory.MISSING_USER_INFORMATION:
                continue
            key = f"match_gap_{gap.code.lower()}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "key": key,
                    "label": gap.message,
                    "description": (
                        "ScholarZone could not check this against your profile, so the rule remains "
                        "unevaluated."
                    ),
                    "source": ChecklistSource.MATCH_EVIDENCE.value,
                    "source_detail": gap.code,
                    "position": len(items),
                    "weight": 1,
                    "action_target": "profile",
                }
            )

        for index, requirement in enumerate(
            getattr(match_result.eligibility_detail, "unverified", None) or []
        ):
            key = f"unverified_{requirement.kind.value.lower()}_{index}"
            if key in seen:
                continue
            seen.add(key)
            items.append(
                {
                    "key": key,
                    "label": requirement.summary,
                    "description": (
                        "Published but not yet evaluated against your profile. Confirm it yourself "
                        "before assuming it applies."
                    ),
                    "source": ChecklistSource.MATCH_EVIDENCE.value,
                    "source_detail": requirement.kind.value,
                    "position": len(items),
                    "weight": 1,
                    "action_target": requirement.provenance_url or "scholarship",
                }
            )

    return items[:MAX_CHECKLIST_ITEMS]


def open_task_label(items: list[ApplicationChecklistItem]) -> str | None:
    """The first incomplete task, in checklist order, or ``None``.

    Extracted so that "what should I finish next" has exactly one definition. The
    mentor needs this answer as much as the workspace does, and two
    implementations of "first incomplete by position" would eventually disagree
    about which task a student is actually on.
    """
    return next(
        (
            item.label
            for item in sorted(items, key=lambda entry: (entry.position, entry.id))
            if not item.completed
        ),
        None,
    )


def compute_progress(items: list[ApplicationChecklistItem]) -> float | None:
    """Completed weight as a percentage of counted weight.

    ``progress = 100 * completed_weight / total_counted_weight``

    Returns ``None`` when there is nothing to measure - no tasks at all, or every
    task weighted zero. It never returns ``0.0`` for an unmeasured application and
    never returns ``100.0`` for an empty checklist, because both would be a
    measurement nobody made. Zero-weight tasks are excluded from the denominator
    so a non-applicable step cannot drag the number down, and are equally excluded
    from the numerator so it cannot count as done either.
    """
    total = sum(item.weight for item in items if item.weight > 0)
    if total <= 0:
        return None

    completed = sum(item.weight for item in items if item.weight > 0 and item.completed)
    # Bounded rather than trusted: the arithmetic cannot exceed these bounds, but
    # a future weighting change should not be able to publish 140% or -10%.
    return max(0.0, min(100.0, round(100.0 * completed / total, 1)))


# ------------------------------------------------------------ record assembly


def _availability(context: ScholarshipContext | None, record: ApplicationRecord) -> ScholarshipAvailability:
    if context is not None and context.is_visible:
        return ScholarshipAvailability(is_available=True)

    if record.state in ("submitted", "withdrawn"):
        reason = "This scholarship is no longer listed, but your application record is unchanged."
    else:
        reason = (
            "This scholarship is no longer listed in the directory. Your record is kept exactly "
            "as you left it."
        )
    return ScholarshipAvailability(is_available=False, reason=reason)


def _resolve_action_target(target: str | None, context: ScholarshipContext | None) -> str | None:
    """Turn a symbolic action target into a URL the interface can follow."""
    if target is None:
        return None
    if target == "scholarship":
        return f"/scholarships/{context.scholarship_id}" if context else None
    if target == "official_source":
        return context.official_source_url if context else None
    if target == "profile":
        return "/match"
    return target


def _checklist_responses(
    items: list[ApplicationChecklistItem], context: ScholarshipContext | None
) -> list[ChecklistItemResponse]:
    responses = []
    for item in sorted(items, key=lambda entry: (entry.position, entry.id)):
        responses.append(
            ChecklistItemResponse(
                key=item.key,
                label=item.label,
                description=item.description,
                action_target=_resolve_action_target(item.action_target, context),
                source=item.source,
                source_detail=item.source_detail,
                position=item.position,
                weight=item.weight,
                completed=item.completed,
                completed_at=item.completed_at,
                is_counted=item.weight > 0,
            )
        )
    return responses


def _summary(
    record: ApplicationRecord,
    items: list[ApplicationChecklistItem],
    context: ScholarshipContext | None,
    match_item=None,
) -> ApplicationSummary:
    """Assemble one list row or detail body.

    Where the scholarship is still public, every displayed value is the live one.
    Where it is not, the immutable snapshot taken when the student started is used
    so the history stays readable - and the availability block says so plainly,
    because a stale-looking row that is not labelled as such is the confusing
    outcome.
    """
    use_snapshot = context is None or not context.is_visible
    name = record.scholarship_name_snapshot if use_snapshot else context.name
    country = record.scholarship_country_snapshot if use_snapshot else context.country
    degree = record.scholarship_degree_snapshot if use_snapshot else context.degree
    provider = record.scholarship_provider_snapshot if use_snapshot else context.provider
    funding = record.scholarship_funding_snapshot if use_snapshot else context.funding
    source_url = record.scholarship_source_url_snapshot if use_snapshot else context.official_source_url
    deadline_text = record.scholarship_deadline_text_snapshot if use_snapshot else context.deadline_display
    deadline_date = record.scholarship_deadline_date_snapshot if use_snapshot else context.deadline_date

    evaluation = context.deadline_evaluation if context is not None else None
    days_remaining = evaluation.days_remaining if evaluation is not None else None
    precision = evaluation.precision if evaluation is not None else None
    is_overdue = bool(evaluation is not None and evaluation.closed)
    is_actionable = bool(days_remaining is not None and days_remaining >= 0 and not is_overdue)

    status_value = (
        normalize_public_verification_status(context.verification_status)
        if (context is not None and context.is_visible)
        else None
    )
    verified = public_verified_from_status(status_value) if status_value else False

    next_open = open_task_label(items)

    return ApplicationSummary(
        id=record.id,
        scholarship_id=record.scholarship_id,
        name=name or f"Scholarship {record.scholarship_id}",
        country=country,
        degree=degree,
        provider=provider,
        funding=funding,
        detail_url=f"/scholarships/{record.scholarship_id}",
        official_source_url=source_url,
        state=record.state,
        state_label=APPLICATION_STATE_LABELS.get(record.state, record.state),
        outcome=record.outcome,
        outcome_label=_outcome_label(record.outcome),
        availability=_availability(context, record),
        deadline_text=deadline_text,
        deadline_date=deadline_date,
        deadline_precision=precision,
        days_remaining=days_remaining,
        is_overdue=is_overdue,
        is_actionable=is_actionable,
        progress_percent=compute_progress(items),
        checklist_total=len([item for item in items if item.weight > 0]),
        checklist_completed=len([item for item in items if item.weight > 0 and item.completed]),
        next_open_task=next_open,
        # Trust travels on the list row as well as the detail, derived from the
        # authoritative status. A scholarship that is no longer listed reports no
        # status at all and is never presented as verified.
        verification_status=status_value or "not_listed",
        verified=verified,
        verification_display=verification_display(status_value) if status_value else "No longer listed",
        updated_at=record.updated_at,
        version=record.version,
    )


def _outcome_label(outcome: str) -> str:
        return OUTCOME_LABELS.get(outcome, outcome)


# ------------------------------------------------------------------ retrieval


def list_for_user(
    db: Session,
    user: User,
    as_of: date | None = None,
    limit: int = MAX_APPLICATIONS,
) -> ApplicationListResponse:
    """Every application this student owns, in deterministic decision order.

    One bounded query for the records, one for their checklist, one for the
    scholarship contexts, and at most one Match run for the profile. There is no
    per-application detail fetch.
    """
    effective_date = as_of or date.today()

    records = list(
        db.execute(
            select(ApplicationRecord)
            .where(ApplicationRecord.user_id == user.id)
            .order_by(ApplicationRecord.scholarship_id.asc())
            .limit(limit)
        ).scalars()
    )

    if not records:
        return ApplicationListResponse(
            applications=[],
            count=0,
            states=sorted(APPLICATION_STATES),
            outcomes=sorted(APPLICATION_OUTCOMES),
        )

    items_by_application = _load_checklists(db, [record.id for record in records])
    contexts = load_contexts(db, sorted({record.scholarship_id for record in records}), effective_date)
    match_by_id = _match_index(db, user, effective_date)

    summaries = [
        _summary(
            record,
            items_by_application.get(record.id, []),
            contexts.get(record.scholarship_id),
            match_by_id.get(record.scholarship_id),
        )
        for record in records
    ]

    summaries.sort(key=lambda item: _decision_order(item))

    return ApplicationListResponse(
        applications=summaries,
        count=len(summaries),
        states=sorted(APPLICATION_STATES),
        outcomes=sorted(APPLICATION_OUTCOMES),
    )


def _decision_order(item: ApplicationSummary):
    """Ordering the workspace uses, and why this sequence.

    Actionable deadlines first, nearest first, because that is what a student
    opening the page is deciding about. Then closed and overdue records, so a
    finished round is visible without competing with live work. Then unmeasurable
    deadlines - an open round with no fixed date is genuinely open, and sorting
    it above a real deadline would be the more harmful error. Readiness then
    breaks ties, and the id makes the order total and stable.
    """
    return (
        0 if item.is_actionable else (1 if item.is_overdue else 2),
        item.days_remaining if item.days_remaining is not None else 0,
        0 if item.progress_percent is not None else 1,
        -1 * (item.progress_percent or 0.0),
        item.state,
        item.scholarship_id,
    )


def _load_checklists(
    db: Session, application_ids: list[int]
) -> dict[int, list[ApplicationChecklistItem]]:
    if not application_ids:
        return {}
    rows = db.execute(
        select(ApplicationChecklistItem).where(
            ApplicationChecklistItem.application_id.in_(application_ids)
        )
    ).scalars()
    grouped: dict[int, list[ApplicationChecklistItem]] = {}
    for row in rows:
        grouped.setdefault(row.application_id, []).append(row)
    return grouped


def _match_index(db: Session, user: User, as_of: date) -> dict:
    """Match 2.0 results for this student's profile, keyed by scholarship id.

    The engine is run once for the whole workspace and shared, rather than once
    per application. A display layer may copy fit and readiness from these
    results but must never recompute them, and it must not call the engine
    repeatedly to get the same answers.
    """
    from .dashboard import load_stored_profile, profile_is_empty
    from .matching.service import match_scholarships

    profile = load_stored_profile(db, user.id)
    if profile is None or profile_is_empty(profile):
        return {}

    try:
        response = match_scholarships(db, profile, as_of)
    except Exception:
        # Match is enrichment here, not the workspace. If it cannot run, the
        # workspace still shows the student's own state, deadlines and tasks
        # rather than failing wholesale.
        return {}

    return {result.scholarship_id: result for result in response.results}


def get_owned(db: Session, user: User, application_id: int, as_of: date | None = None) -> ApplicationRecord:
    """Resolve one application, or 404.

    Scoped to the owner in the query rather than fetched and checked afterwards,
    so there is no path where another student's row is loaded and then judged.
    """
    record = db.execute(
        select(ApplicationRecord).where(
            ApplicationRecord.id == application_id,
            ApplicationRecord.user_id == user.id,
        )
    ).scalar_one_or_none()

    if record is None:
        # The same answer for "no such id" and "someone else's id". A 403 would
        # confirm the row exists.
        raise NotFound("That application was not found.")

    return record


def build_detail(
    db: Session,
    user: User,
    record: ApplicationRecord,
    as_of: date | None = None,
) -> ApplicationDetail:
    effective_date = as_of or date.today()
    items = _load_checklists(db, [record.id]).get(record.id, [])
    contexts = load_contexts(db, [record.scholarship_id], effective_date)
    match_by_id = _match_index(db, user, effective_date)

    summary = _summary(record, items, contexts.get(record.scholarship_id), match_by_id.get(record.scholarship_id))
    context = contexts.get(record.scholarship_id)
    match_item = match_by_id.get(record.scholarship_id)

    status_value = (
        normalize_public_verification_status(context.verification_status)
        if (context is not None and context.is_visible)
        else None
    )

    gaps = []
    if match_item is not None:
        for gap in match_item.gaps:
            gaps.append(
                {
                    "code": gap.code,
                    "message": gap.message,
                    "category": gap.category.value,
                    "component": gap.component,
                }
            )

    # The trust fields are not restated here: they come from the summary, which
    # is the single place they are derived. Passing them again would be a second
    # derivation of the same value.
    return ApplicationDetail(
        **summary.model_dump(),
        notes=record.notes,
        checklist=_checklist_responses(items, context),
        fit_score=match_item.fit_score if match_item else None,
        fit_label_display=match_item.fit_label_display if match_item else None,
        confidence_score=match_item.confidence_score if match_item else None,
        readiness_label=match_item.readiness.label if (match_item and match_item.readiness) else None,
        open_gaps=gaps,
        created_at=record.created_at,
    )

# ------------------------------------------------------------------ mutations


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_state(current: str, requested: str) -> None:
    """Refuse an illegal transition, naming both states.

    Same-state is allowed and is a no-op: a retried PATCH after network
    uncertainty must not fail, and idempotency is a requirement rather than a
    convenience here.
    """
    if requested == current:
        return

    allowed = STATE_TRANSITIONS.get(current, frozenset())
    if requested not in allowed:
        reachable = ", ".join(sorted(allowed)) or "nothing"
        raise Conflict(
            f"An application that is {current} cannot move to {requested}. "
            f"From {current} it can move to: {reachable}."
        )


def _validate_outcome(current_outcome: str, requested: str, new_state: str) -> None:
    if requested not in APPLICATION_OUTCOMES:
        raise ValidationProblem(f"{requested} is not a recorded outcome.")

    if new_state not in OUTCOME_ALLOWED_STATES and requested != current_outcome:
        # Refusing here rather than silently coercing: an acceptance the provider
        # never sent is not something ScholarZone may record.
        raise Conflict(
            "An outcome can only be recorded once the application has been submitted."
        )

    if requested == current_outcome:
        return

    if current_outcome in TERMINAL_OUTCOMES:
        raise Conflict(
            f"This application already has a final outcome ({current_outcome}), which cannot change."
        )

    if requested not in OUTCOME_TRANSITIONS.get(current_outcome, frozenset()):
        raise Conflict(f"An outcome of {current_outcome} cannot change to {requested}.")


def _validate_notes(notes: str | None) -> str | None:
    if notes is None:
        return None
    # Length is bounded by the schema too; this is the layer that would run if a
    # future caller bypassed it. Control characters are stripped rather than
    # stored so a note cannot carry an invisible payload through exports.
    cleaned = "".join(character for character in notes if character == "\n" or ord(character) >= 32)
    if len(cleaned) > MAX_NOTES_LENGTH:
        raise ValidationProblem("That note is too long to save.")
    return cleaned


def create_application(
    db: Session,
    user: User,
    scholarship_id: int,
    as_of: date | None = None,
) -> ApplicationRecord:
    """Start an application for one scholarship.

    Idempotent: the unique pair on (user_id, scholarship_id) means a second
    request returns the existing application rather than creating a rival one. A
    student gets exactly one workspace per scholarship, which is what keeps a
    shortlist from turning into several half-maintained copies of the same work.

    The saved shortlist is deliberately left alone. Starting an application is a
    new fact about the student's intent, not a reason to discard an earlier one.
    """
    effective_date = as_of or date.today()

    existing = db.execute(
        select(ApplicationRecord).where(
            ApplicationRecord.user_id == user.id,
            ApplicationRecord.scholarship_id == scholarship_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    contexts = load_contexts(db, [scholarship_id], effective_date)
    context = contexts.get(scholarship_id)

    if context is None or not context.is_visible:
        # 404 for both "no such scholarship" and "not publicly listed", so this
        # endpoint cannot be used to discover which ids exist behind the
        # visibility contract.
        raise NotFound("That scholarship is not available.")

    record = ApplicationRecord(
        user_id=user.id,
        scholarship_id=scholarship_id,
        state="saved",
        outcome=ApplicationOutcome.PENDING.value,
        version=1,
        notes=None,
        scholarship_name_snapshot=context.name,
        scholarship_country_snapshot=context.country,
        scholarship_degree_snapshot=context.degree,
        scholarship_provider_snapshot=context.provider,
        scholarship_funding_snapshot=context.funding,
        scholarship_deadline_text_snapshot=context.deadline_display,
        scholarship_deadline_date_snapshot=(
            # The catalogue column is a real date, so it is stored as one. It is
            # not parsed from text here: to_facts does that conversion for the
            # engine, and doing it twice is how a snapshot ends up holding a
            # string where a date column is declared.
            context.deadline_date
            if isinstance(context.deadline_date, date)
            else (date.fromisoformat(context.deadline_date) if context.deadline_date else None)
        ),
        scholarship_source_url_snapshot=context.official_source_url,
    )
    db.add(record)

    try:
        db.flush()
    except IntegrityError:
        # Lost a race with a concurrent create for the same scholarship. The
        # unique constraint decided, which is the behaviour we want.
        db.rollback()
        found = db.execute(
            select(ApplicationRecord).where(
                ApplicationRecord.user_id == user.id,
                ApplicationRecord.scholarship_id == scholarship_id,
            )
        ).scalar_one_or_none()
        if found is None:
            raise
        return found

    match_by_id = _match_index(db, user, effective_date)
    for spec in derive_checklist("saved", context, match_by_id.get(scholarship_id)):
        db.add(
            ApplicationChecklistItem(
                application_id=record.id,
                key=spec["key"],
                label=spec["label"],
                description=spec.get("description"),
                action_target=spec.get("action_target"),
                source=spec["source"],
                source_detail=spec.get("source_detail"),
                position=spec["position"],
                weight=spec.get("weight", 1),
                completed=False,
            )
        )

    db.commit()
    db.refresh(record)
    return record


def patch_application(
    db: Session,
    user: User,
    application_id: int,
    payload,
) -> ApplicationRecord:
    """Apply a partial update, refusing a stale write.

    The staleness check is a conditional UPDATE rather than a read-then-write
    compare in Python. That matters because two tabs can interleave between the
    read and the write, and only the database can make the comparison and the
    write a single atomic step. If the row moved on, the update matches no rows
    and the newer data is left exactly as it is.
    """
    record = get_owned(db, user, application_id)

    new_state = payload.state or record.state
    new_outcome = payload.outcome or record.outcome
    new_notes = record.notes if payload.notes is None and "notes" not in payload.model_fields_set else _validate_notes(payload.notes)

    _validate_state(record.state, new_state)
    _validate_outcome(record.outcome, new_outcome, new_state)

    values: dict = {
        "state": new_state,
        "outcome": new_outcome,
        "notes": new_notes,
        "updated_at": _now(),
        # The version is incremented in the same statement that matches the old
        # one, so it can never be read as two separate steps.
        "version": ApplicationRecord.version + 1,
    }

    result = db.execute(
        update(ApplicationRecord)
        .where(
            ApplicationRecord.id == record.id,
            ApplicationRecord.user_id == user.id,
            ApplicationRecord.version == payload.expected_version,
        )
        .values(**values)
    )

    if result.rowcount == 0:
        db.rollback()
        raise Conflict(
            "This application was changed somewhere else while you were editing it. "
            "Reload to see the newer version."
        )

    db.commit()
    db.refresh(record)
    return record


def set_checklist_item(
    db: Session,
    user: User,
    application_id: int,
    item_key: str,
    completed: bool,
    expected_version: int,
) -> ApplicationRecord:
    """Complete or un-complete one task. Idempotent.

    Setting a task to the value it already holds is accepted and does nothing.
    A retried request, or a double-clicked checkbox, must not fail - and the
    completion timestamp is written only on an actual transition to complete, so
    the timestamp continues to mean "when this was finished" rather than "when
    this was last clicked".
    """
    record = get_owned(db, user, application_id)

    item = db.execute(
        select(ApplicationChecklistItem).where(
            ApplicationChecklistItem.application_id == record.id,
            ApplicationChecklistItem.key == item_key,
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFound("That task is not part of this application.")

    changed = item.completed != completed
    stamp = _now() if completed else None

    if changed:
        db.execute(
            update(ApplicationChecklistItem)
            .where(
                ApplicationChecklistItem.id == item.id,
                ApplicationChecklistItem.application_id == record.id,
            )
            .values(completed=completed, completed_at=stamp, updated_at=_now())
        )

    # The parent version advances only when something actually changed, so an
    # idempotent retry does not invalidate another tab's view for no reason.
    if changed:
        result = db.execute(
            update(ApplicationRecord)
            .where(
                ApplicationRecord.id == record.id,
                ApplicationRecord.user_id == user.id,
                ApplicationRecord.version == expected_version,
            )
            .values(updated_at=_now(), version=ApplicationRecord.version + 1)
        )
        if result.rowcount == 0:
            db.rollback()
            raise Conflict(
                "This application was changed somewhere else while you were editing it. "
                "Reload to see the newer version."
            )

    db.commit()
    db.refresh(record)
    return record


def withdraw_or_delete(db: Session, user: User, application_id: int) -> None:
    """Remove an application from the workspace.

    Withdrawal as a *state* is the normal path and keeps the history. This
    endpoint is the explicit discard, and it exists because a student may have
    started one by accident. It is refused for a submitted application: the
    provider holds that submission, so silently deleting the student's record of
    it would misrepresent what happened.
    """
    record = get_owned(db, user, application_id)

    if record.state == "submitted":
        raise Conflict(
            "A submitted application cannot be deleted. Withdraw it instead, so the record "
            "shows what happened."
        )

    items = db.execute(
        select(ApplicationChecklistItem).where(ApplicationChecklistItem.application_id == record.id)
    ).scalars()
    for item in items:
        db.delete(item)

    db.delete(record)
    db.commit()


__all__ = [
    "APPLICATION_OUTCOMES",
    "APPLICATION_STATES",
    "MAX_APPLICATIONS",
    "Conflict",
    "NotFound",
    "OUTCOME_TRANSITIONS",
    "STATE_TRANSITIONS",
    "TERMINAL_OUTCOMES",
    "ValidationProblem",
    "WorkspaceError",
    "build_detail",
    "compute_progress",
    "open_task_label",
    "create_application",
    "derive_checklist",
    "get_owned",
    "list_for_user",
    "load_contexts",
    "patch_application",
    "set_checklist_item",
    "withdraw_or_delete",
]
