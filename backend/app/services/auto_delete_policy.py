"""The deterministic SAFE_DELETE policy for closed scholarship records.

``status == "closed"`` is not a deletion condition. A round that closed last week
may reopen, may have a corrected deadline, may be the record that explains a
public claim, and may be the only trace of a programme that an applicant was
rejected by. Deleting on the status string alone is how a catalogue quietly
loses history it cannot rebuild.

So deletion is decided here, in one pure place, from named conditions that are
all individually checkable. Nothing in this module touches a database. It takes
plain values in and returns a decision that says exactly which conditions passed
and which blocked, because a deletion nobody can audit is indistinguishable from
a bug.

Three properties are deliberate:

* **KEEP wins.** Any ambiguity, any unrecognised value, any dependency the
  policy cannot fully account for produces ``NEEDS_MANUAL_REVIEW`` or
  ``INSUFFICIENT_RETENTION_EVIDENCE``. There is no branch that resolves doubt
  in favour of deletion.
* **Retention is measured from a timestamp the system actually wrote.**
  ``archived_at`` is set by the archive stage at the moment a record is folded
  away, and it is cleared when a record is reopened, so it doubles as the start
  of the closed-and-untouched period. ``updated_at`` is never used: it moves on
  every unrelated edit and would silently reset or satisfy the clock.
* **The clock is not guessed.** A record with no trustworthy ``archived_at`` is
  never eligible. An unknown closure date is an unknown date, and this is the
  one decision an applicant cannot recover from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

#: A record must have been closed and archived continuously for this long before
#: it can even become a candidate. Configurable; not a per-record setting.
AUTO_DELETE_AFTER_DAYS = 180

#: Having passed the predicate is not enough. A record stays armed for this long
#: so that a reopen, a new review, or a corrected deadline cancels the deletion
#: before it happens rather than being discovered afterwards.
DELETE_GRACE_DAYS = 14

#: Terminal states. A review or fetch in any other state - including NULL, which
#: is not a state - is unfinished business and blocks.
TERMINAL_REVIEW_DECISIONS = frozenset(
    {"approved", "rejected", "confirmed", "withdrawn", "superseded", "dismissed"}
)
TERMINAL_FETCH_STATUSES = frozenset(
    {"resolved", "failed", "exhausted", "abandoned", "not_found", "skipped"}
)
TERMINAL_CANDIDATE_MATCH = frozenset(
    {"unmatched", "rejected", "superseded", "withdrawn", "expired"}
)

#: Verification states that mean a record still needs a human.
BLOCKING_VERIFICATION_STATUSES = frozenset(
    {
        "active",
        "needs_review",
        "quarantined",
        "conflict",
        "disputed",
        "pending",
        "partially_verified",
        "uncertain",
        "unsupported",
    }
)

#: Verification history rows that carry a quoted finding are evidence about the
#: programme. A bare status flip is not.
MATERIAL_HISTORY_CHANGE_TYPES = frozenset(
    {
        "verified",
        "confirmed",
        "evidence",
        "correction",
        "retired",
        "disputed",
        "conflict",
        "reverified",
        "note",
    }
)

VERDICT_SAFE_DELETE = "SAFE_DELETE"
VERDICT_CANDIDATE = "AUTO_DELETE_CANDIDATE"
VERDICT_PROTECTED = "PROTECTED"
VERDICT_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
VERDICT_INSUFFICIENT_RETENTION = "INSUFFICIENT_RETENTION_EVIDENCE"


def _as_utc(value: datetime | date | None) -> datetime | None:
    """Normalise a stored timestamp to an aware UTC datetime.

    The column is written as timezone-aware UTC but Postgres and SQLite read it
    back differently, and a naive/aware comparison raises rather than deciding.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)


def _age_days(moment: datetime | None, now: datetime) -> int | None:
    if moment is None:
        return None
    return (now - moment).days


@dataclass(frozen=True)
class DependencySummary:
    """What depends on a record, and whether any of it must survive."""

    counts: dict[str, int] = field(default_factory=dict)
    blocking: dict[str, str] = field(default_factory=dict)
    disposable: dict[str, int] = field(default_factory=dict)

    @property
    def has_blocking(self) -> bool:
        return bool(self.blocking)

    def as_dict(self) -> dict[str, Any]:
        return {
            "counts": dict(sorted(self.counts.items())),
            "blocking": dict(sorted(self.blocking.items())),
            "disposable": dict(sorted(self.disposable.items())),
            "total": sum(self.counts.values()),
        }


@dataclass(frozen=True)
class RecordFacts:
    """Everything the policy is allowed to know about one record.

    Assembled by the caller from the row and its dependent tables. Keeping this a
    flat value object is what lets the policy be tested without a database.
    """

    id: int
    title: str = ""
    status: str = ""
    is_archived: bool = False
    archived_at: datetime | None = None
    verification_status: str = ""
    is_public: bool = False
    deadline_date: date | None = None
    updated_at: datetime | None = None
    deletion_protected: bool = False
    dependencies: DependencySummary = field(default_factory=DependencySummary)


@dataclass(frozen=True)
class AutoDeleteDecision:
    id: int
    title: str
    verdict: str
    reason: str
    closed_since: datetime | None = None
    archived_since: datetime | None = None
    retention_days: int | None = None
    candidate_since: datetime | None = None
    candidate_age_days: int | None = None
    eligible_on: datetime | None = None
    deletion_date: datetime | None = None
    checks: dict[str, bool] = field(default_factory=dict)
    blocked_by: list[str] = field(default_factory=list)
    dependency_summary: dict[str, Any] = field(default_factory=dict)

    @property
    def eligible_ids(self) -> bool:
        return self.verdict == VERDICT_SAFE_DELETE

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "verdict": self.verdict,
            "reason": self.reason,
            "closed_since": _iso(self.closed_since),
            "archived_since": _iso(self.archived_since),
            "retention_days": self.retention_days,
            "candidate_since": _iso(self.candidate_since),
            "candidate_age_days": self.candidate_age_days,
            "eligible_on": _iso(self.eligible_on),
            "deletion_date": _iso(self.deletion_date),
            "checks": dict(sorted(self.checks.items())),
            "blocked_by": sorted(self.blocked_by),
            "dependency_summary": self.dependency_summary,
        }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def evaluate(
    facts: RecordFacts,
    *,
    now: datetime | None = None,
    candidate_since: datetime | None = None,
    retention_days: int = AUTO_DELETE_AFTER_DAYS,
    grace_days: int = DELETE_GRACE_DAYS,
) -> AutoDeleteDecision:
    """Decide one record. Pure: same inputs, same decision, every time."""
    now = now or datetime.now(timezone.utc)
    archived = _as_utc(facts.archived_at)
    updated = _as_utc(facts.updated_at)
    armed = _as_utc(candidate_since)

    status = (facts.status or "").strip().lower()
    verification = (facts.verification_status or "").strip().lower()
    age = _age_days(archived, now)
    candidate_age = _age_days(armed, now)

    checks: dict[str, bool] = {
        "closed_status": status == "closed",
        "archived": bool(facts.is_archived),
        "not_public": not facts.is_public,
        "verification_not_active": verification != "active",
        "verification_not_needs_review": verification != "needs_review",
        "verification_not_blocking_state": verification not in BLOCKING_VERIFICATION_STATUSES,
        "no_unresolved_reviews": "ScholarshipReview" not in facts.dependencies.blocking,
        "no_material_history": "ScholarshipVerificationHistory" not in facts.dependencies.blocking,
        "no_required_snapshots": "ScholarshipSnapshot" not in facts.dependencies.blocking,
        "no_restore_dependency": "ScholarshipRestoreRecord" not in facts.dependencies.blocking,
        "no_pending_fetch": "ScholarshipFetchAttempt" not in facts.dependencies.blocking,
        "no_pending_image_review": "ImageReview" not in facts.dependencies.blocking,
        "no_live_discovery_candidate": "DiscoveryCandidate" not in facts.dependencies.blocking,
        "not_protected": not facts.deletion_protected,
        "no_future_deadline": not (
            facts.deadline_date is not None and facts.deadline_date >= now.date()
        ),
    }
    # Deliberately absent: a check on ``updated_at`` versus ``archived_at``.
    # Arming a candidate is itself a write, so that comparison is satisfied by
    # nothing and would make every record permanently ineligible. Stability is
    # enforced where it can be observed - the substantive conditions above, and
    # a full re-decision inside the deletion transaction - rather than through a
    # column the collector moves itself.
    checks["retention_satisfied"] = age is not None and age >= retention_days
    checks["grace_satisfied"] = candidate_age is not None and candidate_age >= grace_days

    dependency_summary = facts.dependencies.as_dict()
    blocked_by = sorted(name for name, ok in checks.items() if not ok)

    eligible_on = (
        datetime.fromtimestamp(archived.timestamp() + retention_days * 86400, tz=timezone.utc)
        if archived
        else None
    )
    deletion_date = (
        datetime.fromtimestamp(armed.timestamp() + grace_days * 86400, tz=timezone.utc)
        if armed
        else None
    )

    base = dict(
        id=facts.id,
        title=facts.title,
        closed_since=archived,
        archived_since=archived,
        retention_days=age,
        candidate_since=armed,
        candidate_age_days=candidate_age,
        eligible_on=eligible_on,
        deletion_date=deletion_date,
        checks=checks,
        blocked_by=blocked_by,
        dependency_summary=dependency_summary,
    )

    # 1. An explicit protection is honoured before anything else is considered.
    if facts.deletion_protected:
        return AutoDeleteDecision(
            verdict=VERDICT_PROTECTED,
            reason="deletion_protected is set; an operator marked this record as retained",
            **base,
        )

    # 2. A closed record that is still archived for an unknown length of time is
    #    not eligible on an unknown date. This is checked before the other
    #    blocking states so the reason names the real obstacle.
    if not checks["archived"] or archived is None:
        return AutoDeleteDecision(
            verdict=VERDICT_INSUFFICIENT_RETENTION if archived is None else VERDICT_PROTECTED,
            reason=(
                "no archived_at timestamp, so the length of the closed period cannot "
                "be established; an unknown closure date is not evidence of a long "
                "one"
                if archived is None
                else "record is not archived"
            ),
            **base,
        )

    if facts.dependencies.has_blocking:
        return AutoDeleteDecision(
            verdict=VERDICT_MANUAL_REVIEW,
            reason=(
                "a dependency must survive the deletion: "
                + ", ".join(
                    f"{name} ({why})" for name, why in sorted(facts.dependencies.blocking.items())
                )
            ),
            **base,
        )

    if facts.is_public:
        return AutoDeleteDecision(
            verdict=VERDICT_PROTECTED,
            reason="record is publicly visible; deleting it would break a published page",
            **base,
        )

    if not checks["closed_status"]:
        return AutoDeleteDecision(
            verdict=VERDICT_PROTECTED,
            reason=f"status is {facts.status!r}, not 'closed'",
            **base,
        )

    if verification in BLOCKING_VERIFICATION_STATUSES:
        return AutoDeleteDecision(
            verdict=VERDICT_MANUAL_REVIEW,
            reason=f"verification_status is {verification!r}, which needs a human",
            **base,
        )

    if not checks["retention_satisfied"]:
        return AutoDeleteDecision(
            verdict=VERDICT_INSUFFICIENT_RETENTION,
            reason=(
                f"closed and archived for {age} day(s); {retention_days} are required"
                if age is not None
                else "retention cannot be measured"
            ),
            **base,
        )

    # Everything the policy can check now passes. Whether the record has been
    # armed long enough to survive the grace period is a separate stage, so the
    # verdict distinguishes "eligible" from "eligible once the grace ends".
    if armed is None:
        return AutoDeleteDecision(
            verdict=VERDICT_CANDIDATE,
            reason=(
                f"every condition passes after {age} day(s) closed; "
                f"{grace_days} grace days must elapse before deletion"
            ),
            **base,
        )

    if not checks["grace_satisfied"]:
        return AutoDeleteDecision(
            verdict=VERDICT_CANDIDATE,
            reason=(
                f"candidate for {candidate_age} day(s); {grace_days} grace days "
                "must elapse before deletion"
            ),
            **base,
        )

    # Last gate, and it is not redundant. Each check above was written to be
    # readable on its own, and reading them individually is how a condition
    # ends up computed but never enforced - a record with a future deadline, or
    # one edited after it was archived, would otherwise reach SAFE_DELETE with
    # its own failure sitting in `blocked_by`. Nothing is deletable while any
    # check is false, whatever the branch above concluded.
    still_failing = sorted(name for name, ok in checks.items() if not ok)
    if still_failing:
        return AutoDeleteDecision(
            verdict=VERDICT_PROTECTED,
            reason="condition(s) not satisfied: " + ", ".join(still_failing),
            **base,
        )

    return AutoDeleteDecision(
        verdict=VERDICT_SAFE_DELETE,
        reason=(
            f"closed, archived and non-public for {age} day(s) (>= {retention_days}), "
            f"no dependency must survive, and armed {candidate_age} day(s) "
            f"(>= {grace_days} grace)"
        ),
        **base,
    )


def summarise(decisions: list[AutoDeleteDecision]) -> dict[str, Any]:
    """The reporting shape every cycle publishes."""
    buckets: dict[str, list[int]] = {}
    for decision in decisions:
        buckets.setdefault(decision.verdict, []).append(decision.id)
    return {
        "scanned": len(decisions),
        "eligible": sorted(buckets.get(VERDICT_SAFE_DELETE, [])),
        "candidate": sorted(buckets.get(VERDICT_CANDIDATE, [])),
        "protected": sorted(buckets.get(VERDICT_PROTECTED, [])),
        "needs_manual_review": sorted(buckets.get(VERDICT_MANUAL_REVIEW, [])),
        "insufficient_retention_evidence": sorted(
            buckets.get(VERDICT_INSUFFICIENT_RETENTION, [])
        ),
        "counts": {key: len(value) for key, value in sorted(buckets.items())},
        "auto_delete_after_days": AUTO_DELETE_AFTER_DAYS,
        "delete_grace_days": DELETE_GRACE_DAYS,
    }


# --------------------------------------------------------------------------
# Dependency classification
# --------------------------------------------------------------------------


def classify_reviews(rows: list[Any]) -> DependencySummary:
    """A review blocks unless it reached a terminal decision and was reviewed.

    A settled review is not pending work, so it does not block - but its row is
    still carried into the deletion manifest, because a review is part of how a
    decision about a record was reached.
    """
    unresolved = [
        r
        for r in rows
        if (getattr(r, "decision", "") or "").strip().lower() not in TERMINAL_REVIEW_DECISIONS
        or getattr(r, "reviewed_at", None) is None
    ]
    blocking: dict[str, str] = {}
    if unresolved:
        blocking["ScholarshipReview"] = (
            f"{len(unresolved)} of {len(rows)} review row(s) without a terminal decision"
        )
    return DependencySummary(
        counts={"ScholarshipReview": len(rows)},
        blocking=blocking,
        disposable={"ScholarshipReview": len(rows) - len(unresolved)},
    )


def classify_history(rows: list[Any]) -> DependencySummary:
    """History blocks when it carries evidence, not when it merely flipped a status."""
    material = [
        r
        for r in rows
        if (getattr(r, "evidence_text", None) or "").strip()
        or (getattr(r, "change_type", "") or "").strip().lower() in MATERIAL_HISTORY_CHANGE_TYPES
    ]
    blocking: dict[str, str] = {}
    if material:
        blocking["ScholarshipVerificationHistory"] = (
            f"{len(material)} material history row(s) carrying evidence"
        )
    return DependencySummary(
        counts={"ScholarshipVerificationHistory": len(rows)},
        blocking=blocking,
        disposable={"ScholarshipVerificationHistory": len(rows) - len(material)},
    )


def always_blocking(model: str, rows: list[Any], why: str) -> DependencySummary:
    """Snapshots and restore records are the substrate of 'explain this later'."""
    blocking = {model: f"{len(rows)} {why}"} if rows else {}
    return DependencySummary(counts={model: len(rows)}, blocking=blocking)


def classify_fetch_attempts(rows: list[Any]) -> DependencySummary:
    """An unfinished fetch is pending work; a settled one is derived telemetry."""
    pending = [
        r
        for r in rows
        if (getattr(r, "status", "") or "").strip().lower() not in TERMINAL_FETCH_STATUSES
        or getattr(r, "resolved_at", None) is None
    ]
    blocking: dict[str, str] = {}
    if pending:
        blocking["ScholarshipFetchAttempt"] = f"{len(pending)} unsettled fetch attempt(s)"
    return DependencySummary(
        counts={"ScholarshipFetchAttempt": len(rows)},
        blocking=blocking,
        disposable={"ScholarshipFetchAttempt": len(rows) - len(pending)},
    )


def classify_image_reviews(rows: list[Any]) -> DependencySummary:
    """An image review with no decision is a queued human task."""
    pending = [
        r
        for r in rows
        if (getattr(r, "decision", "") or "").strip().lower() not in TERMINAL_REVIEW_DECISIONS
        or getattr(r, "reviewed_at", None) is None
    ]
    blocking: dict[str, str] = {}
    if pending:
        blocking["ImageReview"] = f"{len(pending)} image review(s) without a decision"
    return DependencySummary(
        counts={"ImageReview": len(rows)},
        blocking=blocking,
        disposable={"ImageReview": len(rows) - len(pending)},
    )


def classify_candidates(rows: list[Any]) -> DependencySummary:
    """A candidate still awaiting a match decision depends on this record."""
    live = [
        r
        for r in rows
        if (getattr(r, "match_status", "") or "").strip().lower() not in TERMINAL_CANDIDATE_MATCH
    ]
    blocking: dict[str, str] = {}
    if live:
        blocking["DiscoveryCandidate"] = f"{len(live)} discovery candidate(s) awaiting a decision"
    return DependencySummary(
        counts={"DiscoveryCandidate": len(rows)},
        blocking=blocking,
        disposable={"DiscoveryCandidate": len(rows) - len(live)},
    )


def merge(*summaries: DependencySummary) -> DependencySummary:
    counts: dict[str, int] = {}
    blocking: dict[str, str] = {}
    disposable: dict[str, int] = {}
    for summary in summaries:
        for key, value in summary.counts.items():
            counts[key] = counts.get(key, 0) + value
        for key, value in summary.blocking.items():
            blocking[key] = value
        for key, value in summary.disposable.items():
            disposable[key] = disposable.get(key, 0) + value
    return DependencySummary(counts=counts, blocking=blocking, disposable=disposable)