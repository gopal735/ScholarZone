"""Private schemas for Application Workspace 1.0.

Separate from ``app/schemas.py`` and from ``app/schemas_dashboard.py`` on
purpose. ``schemas.py`` is the *public* scholarship contract: it is what a
visitor, a crawler and a search index may see, and nothing about one student may
ever appear in it. ``schemas_dashboard.py`` is the dashboard's read model.

This module is the third contract, and it is write-capable: it accepts state
transitions, outcome changes, notes edits and checklist completion. Nothing here
inherits from a public or admin schema, so a field added to a public response can
never leak a private one by accident.

Four rules hold across the module.

**Ownership is not a field.** No schema here accepts or returns ``user_id``.
Ownership is resolved from the session on the server before a handler runs, so a
value the browser sent could not widen access even if it were accepted.

**Authority is not a field either.** A request may carry ``expected_version``,
because that is how a client *proves* what it read rather than asserting a fact.
It may not carry ``progress``, ``days_remaining``, ``fit_score`` or ``updated_at``
- those are computed by engines the client does not control.

**Absences stay null.** ``progress`` is ``None`` when there is nothing to
measure. ``days_remaining`` is ``None`` when the provider published no fixed
date. Neither is ever zero, because zero is a measurement and both of these are
an absence.

**Plain text only.** ``notes`` is a string, length-bounded at the schema, and
rendered as text everywhere. There is no HTML field and no trusted rich-text
system to inherit from.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from .verification_contract import (
    normalize_public_verification_status,
    public_verified_from_status,
)


def _as_utc(value: datetime | None) -> datetime | None:
    """Return ``value`` as a UTC-aware datetime, without moving the instant.

    Every timestamp in this file is written by the application as
    ``datetime.now(timezone.utc)``. Reading it back does not always preserve that:
    SQLite's ``DateTime`` has no timezone type, so a value that has made a
    round trip through the database comes back naive, while the same value still
    held in memory arrives aware. Both describe the same instant, so the API was
    publishing one field in two different formats depending on whether the row
    had been refreshed - ``...618155Z`` on one response and ``...618155`` on the
    next, for a value that never changed.

    A client cannot parse that pair the same way twice, and it made an idempotent
    retry look like a changed timestamp. Normalising here, at the serialization
    boundary, fixes the published representation for every consumer at once and
    is a no-op on PostgreSQL, which returns aware values already.

    A naive value is *assumed* UTC rather than localised, and that assumption is
    safe here because nothing in this module writes local time: it is the same
    reasoning ``app.routers.admin_verification._as_utc`` already applies to
    verification timestamps. The instant is never shifted, and the microseconds
    are never truncated - only the tzinfo label is made explicit.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


#: A timestamp that reaches the wire as UTC-aware whatever the storage dialect
#: did to it. Named so a field using it says so at the point of declaration.
UtcTimestamp = Annotated[datetime, BeforeValidator(_as_utc)]


class ApplicationOutcome(str, Enum):
    """How the provider responded, once an application has been submitted.

    A separate vocabulary from :class:`ApplicationState` rather than an
    extension of it. "Submitted" is what the student did; "accepted" is what the
    provider did, and it may never arrive. Folding them together would make
    ``submitted`` mean two different things depending on whether a reply had been
    received yet.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WAITLISTED = "waitlisted"
    WITHDRAWN = "withdrawn"


APPLICATION_OUTCOMES: frozenset[str] = frozenset(member.value for member in ApplicationOutcome)

OUTCOME_LABELS: dict[str, str] = {
    ApplicationOutcome.PENDING.value: "No response yet",
    ApplicationOutcome.ACCEPTED.value: "Accepted",
    ApplicationOutcome.REJECTED.value: "Not successful",
    ApplicationOutcome.WAITLISTED.value: "Waitlisted",
    ApplicationOutcome.WITHDRAWN.value: "Withdrawn",
}

#: Outcomes that end the process. No transition leaves these.
TERMINAL_OUTCOMES: frozenset[str] = frozenset(
    {
        ApplicationOutcome.ACCEPTED.value,
        ApplicationOutcome.REJECTED.value,
        ApplicationOutcome.WAITLISTED.value,
        ApplicationOutcome.WITHDRAWN.value,
    }
)


class ChecklistSource(str, Enum):
    """Where a checklist item came from.

    Not decoration. A generic preparation step and a step derived from a
    published requirement are different claims, and a reader deciding how much to
    trust a task needs to see which one they are looking at. In particular nothing
    may assert a *specific* document is required unless ``PUBLISHED_REQUIREMENT``
    is the source.
    """

    #: A preparation step ScholarZone offers for every application. Carries no
    #: claim about what this particular provider requires.
    GENERIC = "generic"
    #: Derived from a Match 2.0 gap or an unevaluated published requirement.
    MATCH_EVIDENCE = "match_evidence"
    #: Derived from a requirement the provider actually published.
    PUBLISHED_REQUIREMENT = "published_requirement"
    #: Derived from the application lifecycle, e.g. submitting.
    LIFECYCLE = "lifecycle"


CHECKLIST_SOURCES: frozenset[str] = frozenset(member.value for member in ChecklistSource)

#: Hard ceiling on tasks per application. A checklist is a bounded preparation
#: aid, not a document vault; an unbounded list becomes a filing system and stops
#: being useful.
MAX_CHECKLIST_ITEMS = 24

#: A single note is long enough for a considered paragraph and short enough that
#: the column cannot be used as free storage.
MAX_NOTES_LENGTH = 5_000


# --------------------------------------------------------------- write requests


class ApplicationCreateRequest(BaseModel):
    """Start an application.

    ``scholarship_id`` only. No state, because a new application always starts
    at the beginning of the lifecycle, and no outcome, because nothing has been
    submitted.
    """

    model_config = ConfigDict(extra="forbid")

    scholarship_id: int = Field(gt=0)


class ApplicationPatchRequest(BaseModel):
    """A partial update to one application.

    Every field is optional and at least one must be present. ``expected_version``
    is required: a write that does not say which version it read cannot be checked
    for staleness, and silently overwriting a newer edit is the failure this
    whole mechanism exists to prevent.
    """

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    state: str | None = Field(default=None, min_length=1, max_length=16)
    outcome: str | None = Field(default=None, min_length=1, max_length=16)
    #: ``None`` clears the note; a string replaces it. Length-bounded here so an
    #: oversized note is a 422 rather than a silent truncation.
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)


class ChecklistItemPatchRequest(BaseModel):
    """Complete or un-complete one task.

    Idempotent by construction: setting ``completed`` to the value it already has
    is accepted and changes nothing, because a retried request must not fail.
    """

    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    completed: bool


# --------------------------------------------------------------- read responses


class ChecklistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    description: str | None = None
    action_target: str | None = None
    source: str
    source_detail: str | None = None
    position: int
    weight: int
    completed: bool
    completed_at: UtcTimestamp | None = None
    #: True when this item is excluded from the progress denominator because its
    #: weight is zero. Surfaced so the interface can say why a task does not move
    #: the number, rather than leaving a student wondering.
    is_counted: bool = True


class ScholarshipAvailability(BaseModel):
    """Whether the scholarship is still in the public universe.

    ``is_available`` is computed by running the canonical visibility predicate,
    never inferred from a deadline or from the stored verification status.

    When it is false the rest of the response is served from the immutable
    snapshot taken when the student started, so the history stays intelligible
    without exposing anything the visibility contract would hide.
    """

    is_available: bool
    #: Human-readable, non-technical reason. Shown so a student understands that
    #: their record is intact and the *opportunity* closed.
    reason: str | None = None


class ApplicationSummary(BaseModel):
    """List row: identity, deadline, state and progress, in decision order."""

    id: int
    scholarship_id: int
    name: str
    country: str | None = None
    degree: str | None = None
    provider: str | None = None
    funding: str | None = None
    detail_url: str
    official_source_url: str | None = None

    state: str
    state_label: str
    outcome: str
    outcome_label: str

    availability: ScholarshipAvailability

    #: Canonical deadline presentation, from the matching engine's own
    #: evaluator. ``days_remaining`` is null when the provider published no fixed
    #: date - which is an open round, not a countdown of zero.
    deadline_text: str | None = None
    deadline_date: date | None = None
    deadline_precision: str | None = None
    days_remaining: int | None = None
    is_overdue: bool = False
    is_actionable: bool = False

    progress_percent: float | None = None
    checklist_total: int = 0
    checklist_completed: int = 0
    next_open_task: str | None = None

    #: Trust state, on the list row as well as the detail. Derived from the
    #: authoritative ``verification_status`` by the shared public contract, never
    #: from the legacy ``is_verified`` column. For a scholarship that has left the
    #: public universe this is deliberately unverified and says so, because a
    #: record nobody can see must not carry a public trust claim.
    verification_status: str
    verified: bool
    verification_display: str

    updated_at: UtcTimestamp
    version: int


class ApplicationDetail(ApplicationSummary):
    """The full workspace for one application.

    Adds the checklist, the private note, and the values borrowed from Match 2.0.
    Those are copied from the canonical result for the same profile - never
    recomputed here, and never presented as the student's progress.
    """

    notes: str | None = None
    checklist: list[ChecklistItemResponse] = Field(default_factory=list)

    #: Progress is a count of tasks done, not a fit. Kept visibly distinct from
    #: ``fit_score`` so neither can be mistaken for the other.
    progress_label: str = "Tasks completed"

    fit_score: float | None = None
    fit_label_display: str | None = None
    confidence_score: float | None = None
    readiness_label: str | None = None

    #: What the engine says is outstanding for this student and this
    #: scholarship, as structured evidence with a reason for each.
    open_gaps: list[dict] = Field(default_factory=list)

    created_at: UtcTimestamp


class ApplicationListResponse(BaseModel):
    applications: list[ApplicationSummary] = Field(default_factory=list)
    count: int
    #: Named so a caller cannot confuse this with a catalogue total.
    universe: str = "user_applications"
    #: The complete state vocabulary, so the interface never hard-codes a list
    #: the server defines and cannot drift from it.
    states: list[str] = Field(default_factory=list)
    outcomes: list[str] = Field(default_factory=list)