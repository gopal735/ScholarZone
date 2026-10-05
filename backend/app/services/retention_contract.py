"""The authoritative retention rule for scholarship storage, and nothing else.

``KEEP = LIVE UNION ADMIN_REVIEW``. Everything else is a deletion *candidate*.
That sentence is the whole product rule, and this module is where it is decided,
once, purely, so that no caller can re-derive it and reach a different answer.

Three design decisions are load-bearing, and each of them exists because the
opposite one has already caused a failure in this repository.

**1. LIVE is never computed here.**

This module does not know what makes a record publicly visible. It receives
``is_live`` as an already-resolved fact, produced in SQL from
``app.repositories.scholarships.public_visibility_conditions()`` - the same
function the public directory, the homepage statistics, the counting layer and the
closed-record collector all call. A second Python copy of the visibility rule is
how a homepage advertises a total the directory contradicts; the same failure
would appear here as a retention engine deleting the live catalogue.

**2. There is no branch that resolves doubt in favour of deletion.**

``UNKNOWN``, ``AMBIGUOUS``, ``CONFLICTING`` and every ``PROTECTED`` state produce
``KEEP``. The rule "delete everything we do not currently understand" is exactly
the failure this engine exists to prevent, so a record the classifier cannot
safely classify is retained rather than swept. The categorical claim is
enforced structurally, in :func:`classify`, and re-asserted after the fact by the
final block that no decision other than the fully-proved one may be ``DELETE``.

**3. The clock is injected, never read.**

``classify`` takes ``as_of``. A classifier that calls ``now()`` cannot be tested
against a fixed dataset, cannot be replayed, and cannot answer "what would this
have decided last Tuesday" - which is the question every audit of a deletion
eventually asks.

The recognised vocabularies are imported from the modules that declare them
rather than restated, so a state the repository learns about cannot be
unrecognised here by accident. The consequence is the important one: a value
that is genuinely new to the codebase classifies as ``AMBIGUOUS`` and is kept,
which is the correct direction for a value nobody has classified yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from typing import Any

from .auto_delete_policy import (
    AUTO_DELETE_AFTER_DAYS,
    BLOCKING_VERIFICATION_STATUSES,
    DELETE_GRACE_DAYS,
)
from .catalogue_quarantine import QUARANTINE_STATUS

#: The count contract already publishes this vocabulary as the residual bucket of
#: the catalogue's lifecycle partition, so it is imported from there rather than
#: restated. Restating it here is how a lifecycle state ends up meaning two
#: different things in two places.
from .counting.contract import _LIFECYCLE_STATUS_KEYS
from ..verification_contract import (
    AUTHORITATIVE_VERIFIED_STATUS,
    UNCERTAIN_VERIFICATION_STATUS,
)

#: Bumped when the meaning of a decision changes, so an audit record says which
#: contract produced a verdict rather than only that one was produced.
RETENTION_CONTRACT_VERSION = "live-admin-review-retention/2"

# ---------------------------------------------------------------------------
# The retention state machine
# ---------------------------------------------------------------------------
#
# A *bucket* says why a decision was reached; a *state* says where the record
# stands in the lifecycle. Both are needed, and conflating them is how a
# lifecycle becomes unreadable: "AMBIGUOUS" is a reason for retaining, but it is
# not a place a record can be in and wait, whereas GRACE_ELIGIBLE is both - it is
# a fully-qualified candidate whose only outstanding condition is the reversible
# clock.
#
# The eight states below are the whole machine. There is no ninth, and the legal
# transitions between them are enumerated in ``RETENTION_TRANSITIONS`` rather
# than left to prose, so a transition the machine does not permit fails a test
# instead of being discovered in a log.

STATE_KEEP = "KEEP"
STATE_UNKNOWN = "UNKNOWN"
STATE_AMBIGUOUS = "AMBIGUOUS"
STATE_CONFLICTING = "CONFLICTING"
STATE_PROTECTED = "PROTECTED"
STATE_DELETE_CANDIDATE = "DELETE_CANDIDATE"
STATE_GRACE_ELIGIBLE = "GRACE_ELIGIBLE"
STATE_DELETED = "DELETED"

RETENTION_STATES: frozenset[str] = frozenset(
    {
        STATE_KEEP,
        STATE_UNKNOWN,
        STATE_AMBIGUOUS,
        STATE_CONFLICTING,
        STATE_PROTECTED,
        STATE_DELETE_CANDIDATE,
        STATE_GRACE_ELIGIBLE,
        STATE_DELETED,
    }
)

#: States from which no deletion can ever be produced, at any ``as_of``, under any
#: policy. Enumerated rather than inferred from ``NON_DELETABLE_BUCKETS`` so that
#: adding a bucket cannot silently add a path to a deletion.
NON_DELETABLE_STATES: frozenset[str] = frozenset(
    {STATE_KEEP, STATE_UNKNOWN, STATE_AMBIGUOUS, STATE_CONFLICTING, STATE_PROTECTED}
)

#: The legal transitions, as ``from -> {to}``.
#:
#: Two properties are encoded here and both are load-bearing. First, nothing
#: reaches ``DELETED`` except from ``DELETE_CANDIDATE`` - so a record cannot
#: appear deleted without having been classified as a candidate first. Second,
#: ``DELETE_CANDIDATE`` is not terminal: it may fall back to ``GRACE_ELIGIBLE``
#: or straight to ``KEEP`` when a concurrent writer re-verifies, reviews or
#: reopens it, which is the ordinary outcome of a lost race.
RETENTION_TRANSITIONS: dict[str, frozenset[str]] = {
    STATE_KEEP: frozenset({STATE_KEEP, STATE_PROTECTED, STATE_UNKNOWN, STATE_AMBIGUOUS,
                           STATE_CONFLICTING, STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE}),
    STATE_UNKNOWN: frozenset({STATE_UNKNOWN, STATE_AMBIGUOUS, STATE_KEEP, STATE_PROTECTED,
                              STATE_CONFLICTING, STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE}),
    STATE_AMBIGUOUS: frozenset({STATE_AMBIGUOUS, STATE_UNKNOWN, STATE_KEEP, STATE_PROTECTED,
                                STATE_CONFLICTING, STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE}),
    STATE_CONFLICTING: frozenset({STATE_CONFLICTING, STATE_KEEP, STATE_PROTECTED, STATE_UNKNOWN,
                                  STATE_AMBIGUOUS, STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE}),
    STATE_PROTECTED: frozenset({STATE_PROTECTED, STATE_KEEP, STATE_UNKNOWN, STATE_AMBIGUOUS,
                                STATE_CONFLICTING, STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE}),
    STATE_GRACE_ELIGIBLE: frozenset({STATE_GRACE_ELIGIBLE, STATE_DELETE_CANDIDATE, STATE_PROTECTED,
                                     STATE_KEEP, STATE_UNKNOWN, STATE_AMBIGUOUS, STATE_CONFLICTING}),
    STATE_DELETE_CANDIDATE: frozenset({STATE_DELETE_CANDIDATE, STATE_DELETED, STATE_GRACE_ELIGIBLE,
                                       STATE_PROTECTED, STATE_KEEP, STATE_UNKNOWN,
                                       STATE_AMBIGUOUS, STATE_CONFLICTING}),
    # Terminal. A deleted row has no state to be re-classified into; recovering it
    # is a restore, which is a different operation with a different authorisation.
    STATE_DELETED: frozenset(),
}

# ---------------------------------------------------------------------------
# Decisions and reasons
# ---------------------------------------------------------------------------

DECISION_KEEP = "KEEP"
DECISION_DELETE = "DELETE"

#: The two authoritative KEEP reasons, named by the state that produced them.
REASON_LIVE = "LIVE"
REASON_ADMIN_REVIEW = "ADMIN_REVIEW"
REASON_NOT_LIVE_NOT_REVIEW = "NOT_LIVE_NOT_REVIEW"

#: Classification buckets. A bucket is *why* a decision was reached; a decision is
#: *what* was done about it. The three protected buckets are not decoration: they
#: are the records this engine exists not to destroy, and they are reported
#: separately from LIVE and ADMIN_REVIEW so an operator can see the size of the
#: population the retention rule declined to classify.
BUCKET_LIVE = "LIVE"
BUCKET_ADMIN_REVIEW = "ADMIN_REVIEW"
BUCKET_PROTECTED = "PROTECTED"
BUCKET_AMBIGUOUS = "AMBIGUOUS"
BUCKET_CONFLICTING = "CONFLICTING"
BUCKET_DELETE = "NOT_LIVE_NOT_REVIEW"

ALL_BUCKETS = frozenset(
    {
        BUCKET_LIVE,
        BUCKET_ADMIN_REVIEW,
        BUCKET_PROTECTED,
        BUCKET_AMBIGUOUS,
        BUCKET_CONFLICTING,
        BUCKET_DELETE,
    }
)

#: Buckets that can never produce a deletion, whatever the policy says.
NON_DELETABLE_BUCKETS = frozenset(
    {BUCKET_LIVE, BUCKET_ADMIN_REVIEW, BUCKET_PROTECTED, BUCKET_AMBIGUOUS, BUCKET_CONFLICTING}
)


# ---------------------------------------------------------------------------
# Vocabularies, derived from the modules that declare them
# ---------------------------------------------------------------------------

#: Verification states where a human is the next actor.
#:
#: ``active`` is excluded: it is the *verified* state, not a review state, and a
#: record can carry it while being archived - which is precisely the case that
#: must be protected rather than deleted, and that protection is carried by
#: ``protected_statuses`` instead. ``quarantined`` is excluded because it is a
#: decision that was already taken and recorded, not a review that is waiting.
ADMIN_REVIEW_STATUSES: frozenset[str] = frozenset(
    BLOCKING_VERIFICATION_STATUSES - {AUTHORITATIVE_VERIFIED_STATUS, QUARANTINE_STATUS}
)

#: Every verification state the repository has a name for.
#:
#: Built by union rather than by picking one module because the vocabulary is
#: genuinely spread: the verification contract names two, the public schema
#: admits three, the quarantine service writes a fourth, and the closed-record
#: policy already reasons about nine. A state outside this set has never been
#: classified by anybody, so this engine classifies it as unknown and keeps it.
RECOGNISED_VERIFICATION_STATUSES: frozenset[str] = frozenset(
    BLOCKING_VERIFICATION_STATUSES
    | {
        AUTHORITATIVE_VERIFIED_STATUS,
        UNCERTAIN_VERIFICATION_STATUS,
        QUARANTINE_STATUS,
        "inactive",  # app.schemas.ScholarshipVerificationUpdate
    }
)

#: Lifecycle states the catalogue declares. Anything else is the contract's own
#: published residual bucket, which is a reporting position rather than a
#: classification, so a record in it is unresolved here.
RECOGNISED_LIFECYCLE_STATUSES: frozenset[str] = frozenset(_LIFECYCLE_STATUS_KEYS)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionPolicy:
    """The safety policy. Every cap is a named, explicit field, never a constant.

    Two defaults are non-negotiable and are asserted in
    :meth:`assert_deletion_permitted`: cleanup is off, and every run is a dry run.
    A caller must opt in twice, deliberately, to remove a row.
    """

    #: The master switch. Off means the engine classifies and reports, and the
    #: deletion path is unreachable regardless of what a candidate list contains.
    cleanup_enabled: bool = False

    #: The second switch. A dry run performs every classification the deleting
    #: path would perform, through the same code, and then returns without
    #: writing.
    dry_run: bool = True

    #: Minimum time a record must have been continuously out of the public
    #: catalogue, measured from the timestamp the archive stage wrote. Defaults
    #: to the closed-record policy's own retention period so the two engines can
    #: never disagree about how long a record has been gone.
    minimum_age_before_delete: int = AUTO_DELETE_AFTER_DAYS

    #: The persisted grace clock: a record must have held every deletion
    #: condition continuously across at least this many days. Reused rather than
    #: reinvented; it is the same clock, and the same column, the closed-record
    #: collector arms.
    grace_days: int = DELETE_GRACE_DAYS

    #: Hard ceiling on rows removed by one run. Unbounded deletion is not a
    #: policy choice, it is an outage.
    max_delete_per_run: int = 50

    #: Ceiling on the share of storage one run may remove. A candidate count that
    #: jumps is a symptom - a settings change, a bad migration, a query bug - and
    #: the percentage guard is what catches a mis-scoped predicate that the
    #: per-run ceiling alone would not.
    max_delete_percentage: float = 0.05

    #: Verification and lifecycle states that are preserved whatever else is true.
    #: Includes ``quarantined``: a record the quality audit judged not to be a
    #: scholarship is kept precisely because it is documented evidence of where it
    #: came from, not because it is a live opportunity.
    protected_statuses: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {QUARANTINE_STATUS, AUTHORITATIVE_VERIFIED_STATUS} | ADMIN_REVIEW_STATUSES
        )
    )

    #: Rows classified and reconsidered per transaction.
    batch_size: int = 25

    #: Share of the catalogue that may be unclassifiable before the run aborts.
    #: A non-zero unknown population is a data problem; the engine refuses to
    #: sweep a dataset it only partly understands.
    max_ambiguous_ratio: float = 0.0

    #: Relative tolerance for a drop in the protected populations between the
    #: pre-run and post-run classification. Guards against a batch that
    #: succeeded by removing more than it was told to.
    count_reconciliation_tolerance: int = 0

    def assert_deletion_permitted(self) -> None:
        """Raise unless this policy has been enabled for real deletion.

        Called at the single point where rows are about to disappear, so the two
        switches are checked where they matter rather than trusted from a caller.
        """
        if not self.cleanup_enabled:
            raise PermissionError(
                "cleanup_enabled is False: the retention engine may classify and "
                "report, but it is not authorised to delete"
            )
        if self.dry_run:
            raise PermissionError(
                "dry_run is True: this run cannot delete by construction. A "
                "deleting run must set dry_run=False explicitly."
            )

    def with_overrides(self, **kwargs: Any) -> "RetentionPolicy":
        return replace(self, **kwargs)


def default_policy() -> RetentionPolicy:
    """The shipped policy: classification only, no deletion, no exceptions."""
    return RetentionPolicy()


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------


def _as_utc(value: datetime | date | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


@dataclass(frozen=True)
class RetentionFacts:
    """Everything the classifier is allowed to know about one record.

    Deliberately a flat value object with no database types in it. That is what
    lets the entire classification surface be tested without a database, and it
    makes the dependency on the rest of the engine visible: a new column of
    evidence has to be added here, on purpose, before it can affect a deletion.

    ``is_live`` and the ``admin_review_*`` facts are *resolved elsewhere*, by the
    canonical predicates, and arrive here as booleans and counts. They are
    deliberately not raw column values, so that the classifier cannot be tricked
    into deriving visibility from something narrower than the public rule.
    """

    scholarship_id: int

    #: Resolved from ``public_visibility_conditions()``. Not computed here.
    is_live: bool

    #: Whether a human review is outstanding on this record: a pending
    #: scholarship review, or a pending image review. Counts, not booleans, so a
    #: record under review by three reviewers is visibly different from one under
    #: review by one.
    pending_scholarship_reviews: int = 0
    pending_image_reviews: int = 0

    #: Raw stored state, used only to detect states nobody has classified.
    verification_status: str | None = None
    lifecycle_status: str | None = None

    #: Operator override, checked before anything else can be considered.
    deletion_protected: bool = False

    #: Retention clock: written by the archive stage, cleared on reopen.
    archived_at: datetime | None = None
    archived_reason: str | None = None
    is_archived: bool = False

    #: The persisted grace clock.
    candidate_since: datetime | None = None

    #: Legacy boolean. Carried only to detect it contradicting the authoritative
    #: status; it is never used to decide anything on its own.
    is_verified: bool = False

    deadline_date: date | None = None

    #: Dependent rows that must survive the record, by table name. The engine's
    #: reference-integrity audit supplies them; the classifier only asks whether
    #: the set is empty.
    blocking_dependencies: frozenset[str] = frozenset()

    #: Set by the engine when a required column came back NULL or the query
    #: failed. A record whose evidence is incomplete cannot be classified, and an
    #: incomplete record is not a record that may be deleted.
    evidence_complete: bool = True
    evidence_error: str | None = None


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


#: Which states each classification bucket may legitimately carry.
#:
#: ``bucket`` and ``state`` answer different questions - why a verdict was
#: reached, and where the record stands - so they are stored separately, which
#: means they can disagree. Without this table nothing would notice: a record
#: bucketed CONFLICTING and labelled KEEP still returns KEEP, still deletes
#: nothing, and still satisfies every other invariant. The verdict happens to be
#: right while the record's self-description is wrong, and a mislabelled state is
#: precisely what an auditor reads. This is the check that catches it.
LEGAL_STATES_FOR_BUCKET: dict[str, frozenset[str]] = {
    BUCKET_LIVE: frozenset({STATE_KEEP}),
    BUCKET_ADMIN_REVIEW: frozenset({STATE_KEEP}),
    # PROTECTED carries two states because "why is this retained" and "where is
    # it waiting" are genuinely different answers: a permanent protection versus a
    # clock that will run out.
    BUCKET_PROTECTED: frozenset({STATE_PROTECTED, STATE_GRACE_ELIGIBLE}),
    BUCKET_AMBIGUOUS: frozenset({STATE_UNKNOWN, STATE_AMBIGUOUS}),
    BUCKET_CONFLICTING: frozenset({STATE_CONFLICTING}),
    BUCKET_DELETE: frozenset({STATE_DELETE_CANDIDATE}),
}


@dataclass(frozen=True)
class RetentionDecision:
    """One record's verdict, with the evidence that produced it."""

    scholarship_id: int
    decision: str
    bucket: str
    reason: str
    detail: str = ""
    blocking: tuple[str, ...] = ()
    checks: dict[str, bool] = field(default_factory=dict)

    #: Where the record stands in the retention lifecycle, from
    #: :data:`RETENTION_STATES`. Distinct from ``bucket``: ``bucket`` is the reason
    #: a verdict was reached, ``state`` is the place the record stands.
    state: str = STATE_KEEP

    #: True only when every deletion condition holds *except* the reversible grace
    #: clock. This is the population an operator should expect to become
    #: candidates, and naming it explicitly is what makes the grace period
    #: observable instead of something a reader has to infer from a reason string.
    grace_eligible: bool = False

    @property
    def is_delete(self) -> bool:
        return self.decision == DECISION_DELETE

    @property
    def is_keep(self) -> bool:
        return self.decision == DECISION_KEEP

    @property
    def state_is_deletable(self) -> bool:
        """Whether this state may ever lead to a deletion."""
        return self.state not in NON_DELETABLE_STATES

    def as_dict(self) -> dict[str, Any]:
        return {
            "scholarship_id": self.scholarship_id,
            "decision": self.decision,
            "reason": self.reason,
            "bucket": self.bucket,
            "state": self.state,
            "grace_eligible": self.grace_eligible,
            "detail": self.detail,
            "blocking": list(self.blocking),
            "checks": dict(sorted(self.checks.items())),
        }


def _conflicts(facts: RetentionFacts) -> list[str]:
    """States that are internally contradictory.

    A contradiction is not an unknown and not a protection: it is a record that
    says two incompatible things about itself, and no rule applied to it can be
    trusted to mean what it appears to mean. Every case here is a case where
    reading either side as authoritative would be a guess.
    """
    found: list[str] = []

    # Archived with no clock. The archive stage writes ``archived_at`` in the
    # same statement that sets the flag, so their disagreement means one of them
    # was written by something else - and the length of the closed period, which
    # is the entire basis for age-based retention, cannot be established.
    if facts.is_archived and facts.archived_at is None:
        found.append("is_archived is set but archived_at is missing, so the closed period is unknown")

    # Archived for no stated reason. The archive and discontinued stages both
    # write a reason; its absence means the row was hidden by a path that did not
    # have to justify itself.
    if facts.is_archived and not (facts.archived_reason or "").strip():
        found.append("is_archived is set but archived_reason is empty")

    # The authoritative status and the legacy boolean disagree. The verification
    # contract is explicit that ``is_verified`` is legacy bookkeeping and never
    # the semantic authority, so this is not resolved in favour of either: the
    # record contradicts the contract that says which one to believe.
    if facts.verification_status == AUTHORITATIVE_VERIFIED_STATUS and facts.is_verified is False:
        found.append(
            "verification_status is 'active' while the legacy is_verified flag is false; "
            "the two disagree about whether this record is verified"
        )

    # A live-status record that is archived while its deadline is still ahead.
    # Archived means the round is over; an open status with a future date says it
    # is not. One of the two is stale, and neither can be preferred.
    if (
        facts.lifecycle_status in {"open", "upcoming", "closing-soon"}
        and facts.is_archived
        and facts.deadline_date is not None
    ):
        found.append(
            f"status is {facts.lifecycle_status!r} with a deadline of "
            f"{facts.deadline_date.isoformat()} yet the record is archived"
        )

    return found


def _incomplete_evidence(facts: RetentionFacts) -> list[str]:
    """States where the evidence itself failed, rather than the record being odd.

    Distinct from :func:`_unknown_states` because the two mean different things to
    an operator. "UNKNOWN" is a question about the record: a value nobody has
    classified, waiting to be adjudicated. "AMBIGUOUS" is a question about the
    run: a query came back NULL or short, so the engine did not manage to look
    properly. The first needs a data decision; the second needs a fixed query. They
    are retained identically, and reported separately because their remedies are
    not interchangeable.
    """
    if not facts.evidence_complete:
        return [f"classification evidence is incomplete: {facts.evidence_error or 'no detail'}"]
    return []


def _unknown_states(facts: RetentionFacts) -> list[str]:
    """Values this codebase has no classification for."""
    found: list[str] = []

    verification = facts.verification_status
    if verification is None:
        found.append("verification_status is NULL, which is not a state")
    elif verification.strip() not in RECOGNISED_VERIFICATION_STATUSES:
        found.append(
            f"verification_status is {verification!r}, which no repository module classifies"
        )

    lifecycle = facts.lifecycle_status
    if lifecycle is None:
        found.append("status is NULL, which is not a state")
    elif lifecycle.strip() not in RECOGNISED_LIFECYCLE_STATUSES:
        found.append(f"status is {lifecycle!r}, which is not a declared lifecycle state")

    if facts.is_archived is None:  # pragma: no cover - defensive
        found.append("is_archived could not be resolved to a boolean")

    return found


def classify(
    facts: RetentionFacts,
    *,
    policy: RetentionPolicy | None = None,
    as_of: datetime,
) -> RetentionDecision:
    """Decide one record. Pure: same facts and ``as_of``, same decision, always.

    Precedence is deliberate and total. ADMIN_REVIEW and LIVE are checked before
    every protection, so review always wins over deletion; a record under review
    is kept even when its deadline has passed, its image is missing, its source is
    gone and every public visibility gate fails. The protections are checked
    before the deletion test, so nothing ambiguous can reach ``DELETE``.

    There is exactly one return site that produces ``DELETE``, and it is reached
    only by falling through every check above. A future edit that adds a branch
    cannot make a record deletable without adding a delete, and a check that
    fails can never be ignored.
    """
    policy = policy or default_policy()
    blocking: list[str] = []

    def keep(
        bucket: str,
        reason: str,
        detail: str,
        state: str = STATE_KEEP,
        grace_eligible: bool = False,
    ) -> RetentionDecision:
        return RetentionDecision(
            scholarship_id=facts.scholarship_id,
            decision=DECISION_KEEP,
            bucket=bucket,
            reason=reason,
            detail=detail,
            blocking=tuple(sorted(set(blocking))),
            checks=_checks(facts, policy, as_of, blocking),
            state=state,
            grace_eligible=grace_eligible,
        )

    # ---- 1. Review precedence. The most protective gate, checked first. ----
    if facts.verification_status in ADMIN_REVIEW_STATUSES:
        blocking.append(f"verification_status={facts.verification_status}")
        return keep(
            BUCKET_ADMIN_REVIEW,
            REASON_ADMIN_REVIEW,
            f"verification_status is {facts.verification_status!r}, which means a human is "
            "the next actor; admin review is retained regardless of every other condition",
        )

    if facts.pending_scholarship_reviews > 0:
        blocking.append(f"pending_scholarship_reviews={facts.pending_scholarship_reviews}")
        return keep(
            BUCKET_ADMIN_REVIEW,
            REASON_ADMIN_REVIEW,
            f"{facts.pending_scholarship_reviews} scholarship review(s) awaiting a decision",
        )

    if facts.pending_image_reviews > 0:
        blocking.append(f"pending_image_reviews={facts.pending_image_reviews}")
        return keep(
            BUCKET_ADMIN_REVIEW,
            REASON_ADMIN_REVIEW,
            f"{facts.pending_image_reviews} image review(s) awaiting a decision",
        )

    # ---- 2. Live precedence. ----
    if facts.is_live:
        return keep(
            BUCKET_LIVE,
            REASON_LIVE,
            "satisfies the catalogue's public visibility conditions and is therefore live",
        )

    # ---- 3. Contradiction. ----
    conflicts = _conflicts(facts)
    if conflicts:
        blocking.extend(conflicts)
        return keep(
            BUCKET_CONFLICTING,
            "CONFLICTING_STATE",
            "; ".join(conflicts),
            state=STATE_CONFLICTING,
        )

    # ---- 4. Incomplete evidence: the run did not manage to look properly. ----
    incomplete = _incomplete_evidence(facts)
    if incomplete:
        blocking.extend(incomplete)
        return keep(BUCKET_AMBIGUOUS, "INCOMPLETE_EVIDENCE", "; ".join(incomplete),
                    state=STATE_AMBIGUOUS)

    # ---- 5. Unrecognised state: a value nobody has classified. ----
    unknown = _unknown_states(facts)
    if unknown:
        blocking.extend(unknown)
        return keep(BUCKET_AMBIGUOUS, "UNKNOWN_STATE", "; ".join(unknown),
                    state=STATE_UNKNOWN)

    # ---- 6. Explicit operator protection. ----
    if facts.deletion_protected:
        blocking.append("deletion_protected")
        return keep(
            BUCKET_PROTECTED,
            "OPERATOR_PROTECTED",
            "deletion_protected is set, so an operator marked this record as retained",
            state=STATE_PROTECTED,
        )

    # ---- 7. Configured status protection. ----
    if facts.verification_status in policy.protected_statuses:
        blocking.append(f"verification_status={facts.verification_status} is protected")
        return keep(
            BUCKET_PROTECTED,
            "PROTECTED_STATUS",
            f"verification_status {facts.verification_status!r} is in protected_statuses",
            state=STATE_PROTECTED,
        )

    # ---- 8. Reference integrity. ----
    if facts.blocking_dependencies:
        blocking.extend(f"dependency:{name}" for name in sorted(facts.blocking_dependencies))
        return keep(
            BUCKET_PROTECTED,
            "DEPENDENCY_MUST_SURVIVE",
            "rows that must survive the record exist in: "
            + ", ".join(sorted(facts.blocking_dependencies)),
            state=STATE_PROTECTED,
        )

    # ---- 9. Retention clock. ``archived_at`` is the only column that measures
    #         the closed period; ``updated_at`` moves on every unrelated edit and
    #         would silently satisfy the clock. ----
    archived = _as_utc(facts.archived_at)
    if archived is None:
        blocking.append("no archived_at")
        return keep(
            BUCKET_PROTECTED,
            "NO_RETENTION_CLOCK",
            "archived_at is not set, so how long the record has been out of the catalogue "
            "cannot be established; an unknown date is not evidence of a long one",
            state=STATE_PROTECTED,
        )

    if not facts.is_archived:
        blocking.append("not archived")
        return keep(
            BUCKET_PROTECTED,
            "NOT_ARCHIVED",
            "the record is not archived, so it was hidden by a quality gate rather than "
            "by its round closing",
            state=STATE_PROTECTED,
        )

    age_days = (as_of - archived).days
    if age_days < policy.minimum_age_before_delete:
        blocking.append(f"retention_age={age_days}d < {policy.minimum_age_before_delete}d")
        return keep(
            BUCKET_PROTECTED,
            "RETENTION_NOT_ELAPSED",
            f"archived {age_days} day(s) ago; {policy.minimum_age_before_delete} are required",
            state=STATE_PROTECTED,
        )

    # ---- 10. Grace clock, which is persisted rather than derived. Both branches
    #          below are GRACE_ELIGIBLE: every other deletion condition holds, and
    #          the reversible clock is the only thing outstanding. ----
    armed = _as_utc(facts.candidate_since)
    if armed is None:
        blocking.append("no candidate_since")
        return keep(
            BUCKET_PROTECTED,
            "NOT_ARMED",
            f"every condition passes after {age_days} day(s); the record has not yet served "
            f"the {policy.grace_days}-day grace period",
            state=STATE_GRACE_ELIGIBLE,
            grace_eligible=True,
        )

    grace_age = (as_of - armed).days
    if grace_age < policy.grace_days:
        blocking.append(f"grace_age={grace_age}d < {policy.grace_days}d")
        return keep(
            BUCKET_PROTECTED,
            "GRACE_NOT_ELAPSED",
            f"armed {grace_age} day(s) ago; {policy.grace_days} grace days must elapse",
            state=STATE_GRACE_ELIGIBLE,
            grace_eligible=True,
        )

    # ---- 11. The only path to DELETE, reached by satisfying every check. ----
    return RetentionDecision(
        scholarship_id=facts.scholarship_id,
        decision=DECISION_DELETE,
        bucket=BUCKET_DELETE,
        reason=REASON_NOT_LIVE_NOT_REVIEW,
        detail=(
            f"not live, not under review, not protected, archived {age_days} day(s) "
            f"(>= {policy.minimum_age_before_delete}), armed {grace_age} day(s) "
            f"(>= {policy.grace_days} grace), no dependency that must survive"
        ),
        blocking=(),
        checks=_checks(facts, policy, as_of, blocking),
        state=STATE_DELETE_CANDIDATE,
        grace_eligible=False,
    )


def _checks(
    facts: RetentionFacts,
    policy: RetentionPolicy,
    as_of: datetime,
    blocking: list[str],
) -> dict[str, bool]:
    """The named conditions, for the audit record.

    Every condition that can stop a deletion appears here, whether or not the
    branch that reads it was reached. A deletion whose own failure sits in this
    dict is a bug, and the dict is what makes it visible instead of latent.
    """
    archived = _as_utc(facts.archived_at)
    armed = _as_utc(facts.candidate_since)
    age = (as_of - archived).days if archived else None
    grace = (as_of - armed).days if armed else None
    return {
        "evidence_complete": facts.evidence_complete,
        "no_conflict": not _conflicts(facts),
        "no_unknown_state": not _unknown_states(facts),
        "not_under_admin_review": facts.verification_status not in ADMIN_REVIEW_STATUSES
        and facts.pending_scholarship_reviews == 0
        and facts.pending_image_reviews == 0,
        "not_live": not facts.is_live,
        "not_operator_protected": not facts.deletion_protected,
        "status_not_protected": facts.verification_status not in policy.protected_statuses,
        "no_blocking_dependency": not facts.blocking_dependencies,
        "has_retention_clock": archived is not None,
        "archived": bool(facts.is_archived),
        "retention_satisfied": age is not None and age >= policy.minimum_age_before_delete,
        "armed": armed is not None,
        "grace_satisfied": grace is not None and grace >= policy.grace_days,
    }


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionSummary:
    scanned: int = 0
    live_kept: int = 0
    admin_review_kept: int = 0
    protected: int = 0
    ambiguous: int = 0
    conflicting: int = 0
    delete_candidates: int = 0
    errors: int = 0
    buckets: dict[str, int] = field(default_factory=dict)
    keep_reasons: dict[str, int] = field(default_factory=dict)
    #: Population histogram over :data:`RETENTION_STATES`.
    states: dict[str, int] = field(default_factory=dict)
    #: Fully-qualified candidates whose only outstanding condition is the
    #: reversible clock. The number an operator should expect to become
    #: candidates, and the population a grace-clock regression would show up in.
    grace_eligible: int = 0

    @property
    def unclassifiable(self) -> int:
        """Records the engine declined to classify in either direction."""
        return self.ambiguous + self.conflicting

    def reconciles(self) -> bool:
        """Whether every scanned record is accounted for exactly once.

        The arithmetic is the point. A run that reports 500 scanned, 480 kept and
        30 candidates has not described a dataset; it has described a wish, and
        the difference is whatever it was too unsure to mention.
        """
        return self.scanned == (
            self.live_kept
            + self.admin_review_kept
            + self.protected
            + self.ambiguous
            + self.conflicting
            + self.delete_candidates
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "scanned": self.scanned,
            "live_kept": self.live_kept,
            "admin_review_kept": self.admin_review_kept,
            "protected": self.protected,
            "ambiguous": self.ambiguous,
            "conflicting": self.conflicting,
            "unclassifiable": self.unclassifiable,
            "delete_candidates": self.delete_candidates,
            "grace_eligible": self.grace_eligible,
            "errors": self.errors,
            "buckets": dict(sorted(self.buckets.items())),
            "keep_reasons": dict(sorted(self.keep_reasons.items())),
            "states": dict(sorted(self.states.items())),
            "reconciles": self.reconciles(),
        }


def summarise(decisions: list[RetentionDecision], *, errors: int = 0) -> RetentionSummary:
    buckets: dict[str, int] = {}
    reasons: dict[str, int] = {}
    states: dict[str, int] = {}
    grace_eligible = 0
    for decision in decisions:
        buckets[decision.bucket] = buckets.get(decision.bucket, 0) + 1
        reasons[decision.reason] = reasons.get(decision.reason, 0) + 1
        states[decision.state] = states.get(decision.state, 0) + 1
        if decision.grace_eligible:
            grace_eligible += 1
    return RetentionSummary(
        scanned=len(decisions),
        live_kept=buckets.get(BUCKET_LIVE, 0),
        admin_review_kept=buckets.get(BUCKET_ADMIN_REVIEW, 0),
        protected=buckets.get(BUCKET_PROTECTED, 0),
        ambiguous=buckets.get(BUCKET_AMBIGUOUS, 0),
        conflicting=buckets.get(BUCKET_CONFLICTING, 0),
        delete_candidates=buckets.get(BUCKET_DELETE, 0),
        errors=errors,
        buckets=buckets,
        keep_reasons=reasons,
        states=states,
        grace_eligible=grace_eligible,
    )


def retained_ids(decisions: list[RetentionDecision]) -> list[int]:
    return sorted(d.scholarship_id for d in decisions if d.is_keep)


def delete_candidate_ids(decisions: list[RetentionDecision]) -> list[int]:
    return sorted(d.scholarship_id for d in decisions if d.is_delete)


# ---------------------------------------------------------------------------
# Invariants, asserted rather than documented
# ---------------------------------------------------------------------------


def assert_invariants(decisions: list[RetentionDecision]) -> None:
    """Fail loudly if any safety invariant has been violated.

    Cheap enough to run on every classification pass, including the dry run, and
    the failure it reports is the single most important thing this engine can
    assert: that no LIVE record, no record under admin review, and no record it
    could not classify was ever decided to delete.
    """
    live = {d.scholarship_id for d in decisions if d.bucket == BUCKET_LIVE}
    review = {d.scholarship_id for d in decisions if d.bucket == BUCKET_ADMIN_REVIEW}
    unclassified = {
        d.scholarship_id for d in decisions if d.bucket in {BUCKET_AMBIGUOUS, BUCKET_CONFLICTING}
    }
    deleted = {d.scholarship_id for d in decisions if d.is_delete}

    if live & deleted:
        raise AssertionError(
            f"invariant broken: LIVE records decided to delete: {sorted(live & deleted)}"
        )
    if review & deleted:
        raise AssertionError(
            f"invariant broken: ADMIN_REVIEW records decided to delete: {sorted(review & deleted)}"
        )
    if unclassified & deleted:
        raise AssertionError(
            f"invariant broken: unclassifiable records decided to delete: "
            f"{sorted(unclassified & deleted)}"
        )
    non_deletable = {d.scholarship_id for d in decisions if d.bucket in NON_DELETABLE_BUCKETS}
    if non_deletable & deleted:
        raise AssertionError(
            f"invariant broken: a non-deletable bucket reached DELETE: "
            f"{sorted(non_deletable & deleted)}"
        )
    # A deletion whose own condition list still contains a failure is the
    # specific bug this repository has already shipped once: a condition computed
    # and never enforced.
    for decision in decisions:
        if decision.is_delete and not all(decision.checks.values()):
            failing = sorted(name for name, ok in decision.checks.items() if not ok)
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} was decided DELETE with "
                f"failing check(s) {failing}"
            )

    # ---- State-machine legality. ----
    for decision in decisions:
        if decision.state not in RETENTION_STATES:
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} carries state "
                f"{decision.state!r}, which is not a state of this machine"
            )
        legal = LEGAL_STATES_FOR_BUCKET.get(decision.bucket)
        if legal is not None and decision.state not in legal:
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} is bucketed "
                f"{decision.bucket} but labelled {decision.state}; that bucket may only "
                f"carry {sorted(legal)}"
            )
        # A DELETE decision and the DELETE_CANDIDATE state are the same thing
        # stated twice, so they must agree in both directions. Asserting the
        # biconditional rather than one implication is what catches a forged
        # deletion in a retained state *and* a retained verdict wearing the
        # candidate state - either of which would otherwise pass a one-sided check.
        if decision.is_delete != (decision.state == STATE_DELETE_CANDIDATE):
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} is in state "
                f"{decision.state} with decision {decision.decision}; a deletion may only "
                "come from DELETE_CANDIDATE, and only from DELETE_CANDIDATE"
            )
        if decision.grace_eligible and decision.state != STATE_GRACE_ELIGIBLE:
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} is grace-eligible but "
                f"in state {decision.state}"
            )
        if decision.is_delete and decision.grace_eligible:
            raise AssertionError(
                f"invariant broken: record {decision.scholarship_id} is both a deletion "
                "candidate and awaiting its grace period"
            )


def assert_transition(source: str, target: str) -> None:
    """Fail unless ``source -> target`` is a transition this machine permits.

    The transition table is data, and this is the only thing that reads it, so a
    transition the table does not list cannot be reached through an assertion
    path. Used by the state-machine tests and by the release gate when it checks
    that a candidate may legitimately fall back to a retained state.
    """
    if source not in RETENTION_TRANSITIONS:
        raise AssertionError(f"{source!r} is not a state of this machine")
    if target not in RETENTION_TRANSITIONS[source]:
        raise AssertionError(
            f"illegal retention transition {source} -> {target}; permitted targets are "
            f"{sorted(RETENTION_TRANSITIONS[source])}"
        )


__all__ = [
    "ADMIN_REVIEW_STATUSES",
    "ALL_BUCKETS",
    "BUCKET_ADMIN_REVIEW",
    "BUCKET_AMBIGUOUS",
    "BUCKET_CONFLICTING",
    "BUCKET_DELETE",
    "BUCKET_LIVE",
    "BUCKET_PROTECTED",
    "DECISION_DELETE",
    "DECISION_KEEP",
    "LEGAL_STATES_FOR_BUCKET",
    "NON_DELETABLE_BUCKETS",
    "NON_DELETABLE_STATES",
    "REASON_ADMIN_REVIEW",
    "REASON_LIVE",
    "REASON_NOT_LIVE_NOT_REVIEW",
    "RECOGNISED_LIFECYCLE_STATUSES",
    "RECOGNISED_VERIFICATION_STATUSES",
    "RETENTION_CONTRACT_VERSION",
    "RETENTION_STATES",
    "RETENTION_TRANSITIONS",
    "STATE_AMBIGUOUS",
    "STATE_CONFLICTING",
    "STATE_DELETE_CANDIDATE",
    "STATE_DELETED",
    "STATE_GRACE_ELIGIBLE",
    "STATE_KEEP",
    "STATE_PROTECTED",
    "STATE_UNKNOWN",
    "RetentionDecision",
    "RetentionFacts",
    "RetentionPolicy",
    "RetentionSummary",
    "assert_invariants",
    "assert_transition",
    "classify",
    "default_policy",
    "delete_candidate_ids",
    "retained_ids",
    "summarise",
]
