"""Pydantic schemas for the student dashboard.

Separate from ``app/schemas.py``, which is scoped to the *public* scholarship
API. A dashboard response is private, user-scoped and assembled from Match 2.0
rather than from the catalogue tables, so folding it into the public contract
would blur exactly the boundary this module depends on.

Three rules hold throughout:

* **No invented numbers.** Every score, count and band is copied from an
  existing authoritative structure - ``MatchResponse.summary``,
  ``MatchResponse.results``, ``ProfileStrengthResult`` - and named with the
  field it came from. Nothing here computes a fit, a confidence, a readiness or
  a profile score.
* **No invented trust.** ``verification_status`` is the only authority for a
  verification claim, and the public label is derived from it through the same
  contract the public API uses. The legacy ``is_verified`` column is never read.
* **Every absence is ``None``.** An unknown deadline is ``None``, not ``0``. A
  dashboard that turns "we do not know" into "zero" is worse than one that
  admits ignorance, because zero looks like a measurement.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from .verification_contract import (
    normalize_public_verification_status,
    public_verified_from_status,
)


class ApplicationState(str, Enum):
    """The lightweight application vocabulary.

    A closed set of five plain states. This records where a student is; it is
    not a workflow engine, and no transition is validated as a state machine
    beyond requiring the value be one of these.
    """

    SAVED = "saved"
    PLANNING = "planning"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    WITHDRAWN = "withdrawn"


#: Used by the service layer to validate a value before it reaches the database.
APPLICATION_STATES: frozenset[str] = frozenset(member.value for member in ApplicationState)

#: The label shown for an application in progress, for the Continue affordance.
APPLICATION_STATE_LABELS: dict[str, str] = {
    ApplicationState.SAVED.value: "Saved",
    ApplicationState.PLANNING.value: "Planning",
    ApplicationState.IN_PROGRESS.value: "In progress",
    ApplicationState.SUBMITTED.value: "Submitted",
    ApplicationState.WITHDRAWN.value: "Withdrawn",
}


def verification_display(verification_status: object) -> str:
    """The only place a dashboard verification label is produced.

    ``active`` is the single status the public contract allows us to present as
    verified (``verification_contract.AUTHORITATIVE_VERIFIED_STATUS``). Everything
    else - including ``needs_review`` - is shown as an outstanding confirmation
    rather than as a verdict, because an unverified record is not a refuted one.
    """
    return "Verified" if public_verified_from_status(normalize_public_verification_status(verification_status)) else "Confirm with provider"


# --------------------------------------------------------------------------- auth


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class PublicUser(BaseModel):
    """The account fields the browser is allowed to see about itself.

    Deliberately excludes the password digest. A session response is fetched on
    every page load, so anything added here is disclosed on every page load.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    created_at: datetime


class SessionResponse(BaseModel):
    """``{ user: null }`` means signed out. The frontend contract in
    ``AuthContext.jsx`` reads exactly that shape."""

    user: PublicUser | None = None


# ---------------------------------------------------------------------- profile


class ProfileSnapshotField(BaseModel):
    """One row of the profile snapshot: a known field and what it currently holds."""

    key: str
    label: str
    value: str | None = None
    #: ``None`` when the student has not supplied it. Drives the "missing" list.
    is_supplied: bool = False


class DashboardProfile(BaseModel):
    is_empty: bool = True
    updated_at: datetime | None = None
    fields: list[ProfileSnapshotField] = Field(default_factory=list)


class StrengthComponent(BaseModel):
    """One measured dimension of profile completeness, with its own weight.

    ``score`` is 0-100 *completeness* for that group, never a judgement about
    the student, and ``contribution`` is how much of the overall score it
    actually produced.
    """

    model_config = ConfigDict(from_attributes=True)

    name: str
    label: str
    weight: float
    status: str
    score: float | None = None
    detail: str
    effective_weight: float | None = None
    contribution: float | None = None


class ProfileStrength(BaseModel):
    """The deterministic completeness measure, from ``compute_profile_strength``.

    ``score is None`` when nothing at all was supplied: with no input there is
    no completeness to measure, and reporting ``0%`` would read as a failing
    grade rather than an absent measurement.
    """

    score: float | None = None
    band: str | None = None
    label: str | None = None
    detail: str = ""
    components: list[StrengthComponent] = Field(default_factory=list)
    complete: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    """A concrete, actionable gap with the reason it could not be resolved.

    ``category`` comes from Match's own ``GapCategory``, so a student's missing
    data stays distinguishable from a missing record without the dashboard
    inventing a third distinction.
    """

    code: str
    message: str
    category: str
    component: str | None = None
    #: Where the gap can actually be closed. ``None`` when the fix is not a page.
    href: str | None = None
    action_label: str | None = None


# ---------------------------------------------------------------------- summary


class DashboardSummary(BaseModel):
    """Authoritative counts, copied from the engines that computed them.

    ``universe`` is carried on the object rather than left to a reader to
    infer, because a count without its universe is the exact failure PHASE 14
    of the brief warns about: two numbers from different populations presented
    as if they were the same population.
    """

    universe: str
    total_candidates: int
    visible_candidate_count: int
    eligible_count: int
    needs_verification_count: int
    ineligible_count: int
    strong_match_count: int
    scored_count: int
    not_scored_count: int
    #: ``READY`` + ``READY_WITH_CHECKS`` from the Count Intelligence readiness
    #: partition. Sourced, never recomputed.
    ready_to_apply_count: int = 0
    #: ``COMFORTABLE`` + ``APPROACHING`` + ``CLOSING_SOON``: an open round with a
    #: published deadline inside the horizon the engine recognises.
    open_with_deadline_count: int = 0
    closing_soon_count: int = 0
    truncated: bool = False


class CountConsistency(BaseModel):
    """Proof that the two authoritative sources agree.

    Match and Count Intelligence are separate analyses over the same catalogue.
    If their totals disagree, a dashboard showing both would contradict itself,
    so the check is performed server-side and reported rather than left to a
    reader to notice.
    """

    match_total_candidates: int
    count_total_candidates: int
    counts_agree: bool
    #: The Count Intelligence integrity verdict, verbatim. ``WARNING`` is not a
    #: failure: an unavailable baseline is a limitation, not a contradiction.
    integrity_status: str = "PASS"
    integrity_issues: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------- matches


class MatchEvidenceLine(BaseModel):
    """One structured reason, copied from Match's own ``Reason``.

    ``component`` is present because a reason is only actionable once the
    student can see which part of their profile produced it.
    """

    code: str
    message: str
    component: str | None = None


class MatchRequirementLine(BaseModel):
    """A published requirement and how it was treated.

    ``raw_quote`` and ``provenance_url`` travel together on purpose. Match's own
    rule is that a reader unable to produce both may not state a requirement at
    all, so the dashboard never renders a requirement without the provider's
    wording and where it came from.
    """

    kind: str
    status: str
    summary: str
    raw_quote: str | None = None
    provenance_url: str | None = None


class MatchRecommendation(BaseModel):
    """One scholarship on the dashboard.

    ``fit_score``, ``confidence_score`` and the readiness block are copied from
    ``MatchResult`` unchanged, including the distinction that matters: a fit
    score of ``None`` means "not evaluated or not eligible", never "scored zero".
    """

    scholarship_id: int
    name: str
    country: str
    degree: str
    funding: str | None = None
    detail_url: str
    official_source_url: str | None = None

    deadline: str | None = None
    deadline_date: date | None = None
    deadline_precision: str | None = None
    days_to_deadline: int | None = None
    timing_bucket: str | None = None

    eligibility: str
    fit_score: float | None = None
    fit_label: str
    fit_label_display: str
    confidence_score: float
    confidence_label: str
    data_coverage: float

    readiness_score: float | None = None
    readiness_band: str | None = None
    readiness_label: str | None = None

    #: Public trust surface. ``verified`` is derived from
    #: ``verification_status`` by the shared contract, never read from the
    #: legacy column, and ``verification_display`` is the only label rendered.
    verification_status: str
    verified: bool
    verification_display: str

    #: Why it matches, from Match's structured ``reasons``.
    why: list[MatchEvidenceLine] = Field(default_factory=list)
    #: What to check before applying, from Match's ``gaps`` and unverified
    #: requirements. Never a generated sentence.
    needs_attention: list[GapItem] = Field(default_factory=list)
    actions: list[MatchEvidenceLine] = Field(default_factory=list)
    #: Requirements Match could only report as unverified, kept apart from gaps
    #: so the card can say which are unevaluated rather than failing.
    unverified_requirements: list[MatchRequirementLine] = Field(default_factory=list)


# ------------------------------------------------------- saved and applications


class ScholarshipReference(BaseModel):
    """A scholarship the student has acted on, joined to live catalogue fields.

    Built from a single bounded query. A storage-only record is never joined in,
    so a shortlist can never surface something the public directory hides.
    """

    scholarship_id: int
    name: str
    country: str
    degree: str
    funding: str | None = None
    detail_url: str
    official_source_url: str | None = None
    verification_status: str
    verified: bool
    verification_display: str
    #: False when the scholarship has left the public universe - archived, or no
    #: longer publicly verified. The name and context are then served from the
    #: immutable snapshot the student took when they acted on it, because dropping
    #: the row outright would silently erase the student's own history the moment
    #: a round closed. Trust is never claimed for an unlisted record.
    is_listed: bool = True


class DeadlineItem(BaseModel):
    """One row of Deadline Watch.

    ``days_remaining`` is whatever the matching engine computed for this
    record. It is ``None`` for a rolling, recurring or unpublished deadline,
    which is an open round rather than a missing date, and the UI shows the
    published wording instead of a countdown.
    """

    scholarship_id: int
    name: str
    detail_url: str
    deadline: str | None = None
    deadline_date: date | None = None
    deadline_precision: str | None = None
    days_remaining: int | None = None
    timing_bucket: str | None = None
    is_actionable: bool = False
    readiness_label: str | None = None
    fit_score: float | None = None
    application_state: str | None = None
    is_saved: bool = False
    verification_status: str
    verified: bool
    verification_display: str


class SavedItem(BaseModel):
    scholarship: ScholarshipReference
    saved_at: datetime
    is_in_matches: bool = False
    days_remaining: int | None = None
    readiness_label: str | None = None
    application_state: str | None = None


class ApplicationItem(BaseModel):
    scholarship: ScholarshipReference
    state: str
    state_label: str
    created_at: datetime
    updated_at: datetime
    days_remaining: int | None = None
    deadline: str | None = None
    readiness_label: str | None = None
    fit_score: float | None = None


class NextAction(BaseModel):
    """One deterministic suggestion.

    ``priority`` is a fixed integer band, not a computed urgency: these are
    ordered by what unblocks the most work, never by a fake deadline pressure
    and never by a model. Two identical states always produce an identical list
    in an identical order.
    """

    code: str
    title: str
    detail: str
    priority: int
    href: str
    action_label: str


# ------------------------------------------------------------------- aggregate


class DashboardResponse(BaseModel):
    """``GET /api/dashboard``.

    Assembled on the server for one authenticated user. ``as_of`` is echoed so a
    reader can tell which day "days remaining" was measured against, and so the
    whole response is reproducible in a test by pinning it.
    """

    as_of: date
    has_profile: bool
    #: The application-state vocabulary, published with the response so the
    #: interface never hard-codes a list the server defines. Adding a state is a
    #: server change, and a client that guessed the list could offer a value the
    #: API would reject.
    application_states: list[str] = Field(default_factory=lambda: sorted(APPLICATION_STATES))
    profile: DashboardProfile
    profile_strength: ProfileStrength
    summary: DashboardSummary
    consistency: CountConsistency
    matches: list[MatchRecommendation] = Field(default_factory=list)
    matches_truncated: bool = False
    saved: list[SavedItem] = Field(default_factory=list)
    deadlines: list[DeadlineItem] = Field(default_factory=list)
    applications: list[ApplicationItem] = Field(default_factory=list)
    gaps: list[GapItem] = Field(default_factory=list)
    next_actions: list[NextAction] = Field(default_factory=list)


class SavedMutationResponse(BaseModel):
    scholarship_id: int
    saved: bool
    #: The authoritative count after the mutation, so the header cannot drift
    #: from the list it is describing.
    saved_count: int


class ApplicationUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ApplicationState


class ProfileUpdateRequest(BaseModel):
    """The dashboard stores the Match engine's own profile schema.

    Accepting it verbatim is what keeps one definition of a profile in the
    system. An unknown key is rejected rather than dropped, so a client typo
    fails loudly instead of silently losing a field the student entered.
    """

    model_config = ConfigDict(extra="forbid")

    profile: dict = Field(default_factory=dict)