"""Assemble one student's dashboard from existing engines.

This module owns no business truth. It reads what Match 2.0, Count
Intelligence 2.0 and the verification contract already decided and shapes it
into one response, so that:

* no count is recomputed here,
* no fit, confidence or readiness value is recomputed here,
* no deadline is re-derived here,
* no verification claim is formed here.

Where a value does not exist, this module reports ``None`` and says why rather
than substituting a zero, a guess or a plausible-looking default.

Two rules govern data loading. There is no N+1 walk over the catalogue: the
public directory is read by Match's own single candidate query, and everything
the student has actually acted on is joined in one additional bounded query.
And no storage-only record is ever joined in, so a shortlist cannot surface
something the public visibility contract hides.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import ApplicationRecord, Scholarship, SavedScholarship, User
from ..repositories.scholarships import public_visibility_conditions
from ..schemas_dashboard import (
    APPLICATION_STATE_LABELS,
    APPLICATION_STATES,
    ApplicationItem,
    CountConsistency,
    DashboardProfile,
    DashboardResponse,
    DashboardSummary,
    DeadlineItem,
    GapItem,
    MatchEvidenceLine,
    MatchRecommendation,
    MatchRequirementLine,
    NextAction,
    ProfileSnapshotField,
    ProfileStrength,
    SavedItem,
    ScholarshipReference,
    StrengthComponent,
    verification_display,
)
from ..verification_contract import (
    normalize_public_verification_status,
    public_verified_from_status,
)
from .counting.service import count_intelligence
from .deadline_semantics import coerce_deadline_precision
from .matching.eligibility import evaluate_deadline
from .matching.profile_strength import compute_profile_strength
from .matching.repository import MATCH_COLUMNS, CandidateRow, to_facts
from .matching.service import match_scholarships
from .matching.types import EligibilityStatus, GapCategory, MatchProfileRequest, MatchSummary

#: How many matches the "Your matches" section carries. The Match engine still
#: analysed the whole universe - every summary count describes all of it - so
#: this bounds the response without narrowing a single count.
DASHBOARD_MATCH_LIMIT = 24

#: Bound on how many shortlist / application rows one response joins to live
#: catalogue fields. Mirrors the client-side shortlist cap so the two cannot
#: disagree about what a shortlist is.
MAX_SAVED_ITEMS = 100
MAX_APPLICATION_ITEMS = 100

#: Readiness bands Count Intelligence publishes that mean "this can be acted on
#: now", read from the contract rather than redefined.
READY_READINESS_BUCKETS = ("READY", "READY_WITH_CHECKS")
#: Deadline buckets that mean "open, with a published date worth watching".
OPEN_DEADLINE_BUCKETS = ("COMFORTABLE", "APPROACHING", "CLOSING_SOON")
#: The same buckets, as Deadline Watch uses them for rows that are not in the
#: returned matches and so have no engine-assigned ``timing_bucket``.
DEADLINE_HORIZONS = ("COMFORTABLE", "APPROACHING", "CLOSING_SOON")

#: The one page that collects missing student input. Every student-actionable
#: gap resolves here, because there is no per-gap editor.
_PROFILE_EDITOR_HREF = "/match"
_PROFILE_EDITOR_LABEL = "Complete your profile"

_EMPTY_SUMMARY = MatchSummary(
    total_candidates=0,
    visible_candidate_count=0,
    eligible_count=0,
    needs_verification_count=0,
    ineligible_count=0,
    scored_count=0,
    not_scored_count=0,
    strong_or_better_count=0,
)


# --------------------------------------------------------------------- profile

_PROFILE_SNAPSHOT_FIELDS: tuple[tuple[str, str], ...] = (
    ("highest_qualification", "Education level"),
    ("intended_degree_level", "Target degree"),
    ("intended_field", "Field of study"),
    ("study_mode", "Study mode"),
    ("citizenship", "Nationality"),
    ("country_of_residence", "Country of residence"),
    ("age", "Age"),
    ("graduation_year", "Graduation year"),
    ("overall_result", "Academic result"),
    ("subject_results", "Subject results"),
    ("language_credentials", "Language tests"),
    ("funding_requirement", "Funding preference"),
    ("max_self_contribution", "Maximum own contribution"),
    ("living_cost_support_required", "Living-cost support needed"),
    ("preferred_countries", "Preferred study countries"),
    ("intended_intake_year", "Intended intake year"),
)


def load_stored_profile(db: Session, user_id: int) -> MatchProfileRequest | None:
    """Return the user's saved profile, or ``None`` when they have none.

    The stored JSON is validated back through ``MatchProfileRequest`` rather
    than trusted. That makes a row written against a different profile schema a
    *rejected* row instead of a silently differently-shaped one, and it means
    the dashboard reads the engine's own definition of a profile rather than a
    parallel copy of it.
    """
    record = get_profile_record(db, user_id)
    if record is None:
        return None

    payload = record.payload if isinstance(record.payload, dict) else {}
    try:
        return MatchProfileRequest.model_validate(payload)
    except Exception:
        # A payload this version cannot validate is treated as no profile: the
        # dashboard shows its empty state and the student can rebuild it, which
        # is recoverable. Scoring a half-understood profile is not.
        return None


def get_profile_record(db: Session, user_id: int) -> StudentProfile | None:
    from ..models import StudentProfile

    return db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    ).scalar_one_or_none()


def profile_is_empty(profile: MatchProfileRequest | None) -> bool:
    """Whether a profile carries nothing a match could be based on.

    Tested against the fields the engine consumes rather than "is the payload
    empty", because ``country_filter`` and ``limit`` are request options rather
    than facts about the student, and a profile holding only those is still
    empty.
    """
    if profile is None:
        return True

    return not any(
        (
            profile.age is not None,
            bool(profile.citizenship),
            bool(profile.country_of_residence),
            bool(profile.highest_qualification),
            profile.graduation_year is not None,
            profile.overall_result is not None,
            bool(profile.subject_results),
            profile.intended_degree_level is not None,
            bool(profile.intended_field),
            profile.study_mode is not None,
            bool(profile.preferred_countries),
            bool(profile.language_credentials),
            profile.max_self_contribution is not None,
            profile.funding_requirement is not None,
            profile.living_cost_support_required is not None,
            profile.intended_intake_year is not None,
        )
    )


def _format_academic_result(value: object) -> str | None:
    if value is None:
        return None
    scale = getattr(value, "scale", None)
    raw = getattr(value, "value", None)
    letter = getattr(value, "letter", None)
    parts: list[str] = []
    if raw is not None:
        parts.append(f"{raw:g}" if isinstance(raw, float) else str(raw))
    if letter:
        parts.append(str(letter))
    scale_value = getattr(scale, "value", None)
    if scale_value not in (None, "unknown"):
        parts.append(str(scale_value))
    return " ".join(parts) if parts else None


def _format_language_credentials(credentials: list) -> str | None:
    parts: list[str] = []
    for credential in credentials or []:
        test = getattr(credential, "test", None)
        if not test:
            continue
        score = getattr(credential, "score", None)
        level = getattr(credential, "level", None)
        if score is not None:
            parts.append(f"{test} {score:g}" if isinstance(score, float) else f"{test} {score}")
        elif level:
            parts.append(f"{test} {level}")
        else:
            parts.append(str(test))
    return ", ".join(parts) if parts else None


def _snapshot_value(key: str, profile: MatchProfileRequest) -> str | None:
    """Render one profile field for display, or ``None`` when absent."""
    if key == "overall_result":
        return _format_academic_result(profile.overall_result)
    if key == "subject_results":
        rendered = [item for item in (_format_academic_result(subject) for subject in profile.subject_results) if item]
        return ", ".join(rendered) if rendered else None
    if key == "language_credentials":
        return _format_language_credentials(profile.language_credentials)

    value = getattr(profile, key, None)
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return str(enum_value).replace("_", " ").title()
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else None
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return f"{value:,.2f}".rstrip("0").rstrip(".")
    return str(value)


def build_profile_snapshot(profile, updated_at) -> DashboardProfile:
    """The profile as the student currently has it, field by field.

    An absent field is reported with ``is_supplied=False`` and a ``None`` value
    rather than omitted, so the profile card and the "missing" list read the
    same source and cannot describe different sets of fields.
    """
    fields: list[ProfileSnapshotField] = []
    for key, label in _PROFILE_SNAPSHOT_FIELDS:
        value = None if profile is None else _snapshot_value(key, profile)
        fields.append(
            ProfileSnapshotField(key=key, label=label, value=value, is_supplied=value is not None)
        )

    return DashboardProfile(
        is_empty=profile_is_empty(profile),
        updated_at=updated_at,
        fields=fields,
    )


def build_profile_strength(strength) -> ProfileStrength:
    """Re-express ``ProfileStrengthResult`` without altering a value."""
    return ProfileStrength(
        score=strength.score,
        band=strength.band,
        label=strength.label,
        detail=strength.detail,
        complete=list(strength.complete),
        components=[
            StrengthComponent(
                name=component.name,
                label=component.label,
                weight=component.weight,
                status=str(component.status),
                score=component.score,
                detail=component.detail,
                effective_weight=component.effective_weight,
                contribution=component.contribution,
            )
            for component in strength.components
        ],
    )


# ------------------------------------------------------------------- catalogue


def load_facts_for_ids(db: Session, ids: list[int]) -> dict[int, CandidateRow]:
    """Load engine-shaped candidate rows for a small, explicit id set.

    Reuses Match's ``MATCH_COLUMNS`` and ``to_facts`` so a shortlist row is
    interpreted by the same machinery that scored it, and filters through
    ``public_visibility_conditions`` so a shortlist can never surface a record
    the public directory hides. One indexed query, independent of catalogue size.
    """
    if not ids:
        return {}

    statement = select(*MATCH_COLUMNS).where(Scholarship.id.in_(ids)).where(
        *public_visibility_conditions()
    )
    return {row.id: CandidateRow(*row) for row in db.execute(statement).all()}


def deadline_facts(row: CandidateRow, as_of: date):
    """Deadline facts via the matching engine's own evaluator.

    Called rather than reimplemented so the month-end rule, the rolling and
    recurring handling, and the closed-status precedence are identical to what a
    match result reports for the same record.
    """
    return evaluate_deadline(to_facts(row), as_of)


# --------------------------------------------------------------------- matches


def _recommendation(result) -> MatchRecommendation:
    """Shape one ``MatchResult``, copying every score unchanged.

    ``verified`` is derived from ``verification_status`` through the shared
    public contract. The legacy ``is_verified`` column is not read here even
    though Match exposes it on ``evidence_status``: it is internal bookkeeping,
    and a public claim built from it would contradict the status beside it.
    """
    status = normalize_public_verification_status(result.evidence_status.verification_status)
    verified = public_verified_from_status(status)
    readiness = result.readiness

    return MatchRecommendation(
        scholarship_id=result.scholarship_id,
        name=result.scholarship_name,
        country=result.country,
        degree=result.degree_levels,
        funding=result.funding_state.value if result.funding_state is not None else None,
        detail_url=result.detail_url,
        official_source_url=result.official_source_url,
        deadline=None,
        deadline_date=None,
        deadline_precision=coerce_deadline_precision(result.deadline_precision),
        days_to_deadline=result.days_to_deadline,
        timing_bucket=result.timing_bucket,
        eligibility=result.eligibility.value,
        fit_score=result.fit_score,
        fit_label=result.fit_label,
        fit_label_display=result.fit_label_display,
        confidence_score=result.confidence_score,
        confidence_label=result.confidence_label,
        data_coverage=result.data_coverage,
        readiness_score=readiness.score if readiness else None,
        readiness_band=readiness.band if readiness else None,
        readiness_label=readiness.label if readiness else None,
        verification_status=status,
        verified=verified,
        verification_display=verification_display(status),
        why=[
            MatchEvidenceLine(code=reason.code, message=reason.message, component=reason.component)
            for reason in result.reasons
        ],
        needs_attention=[
            GapItem(
                code=gap.code,
                message=gap.message,
                category=gap.category.value,
                component=gap.component,
                href=_PROFILE_EDITOR_HREF
                if gap.category is GapCategory.MISSING_USER_INFORMATION
                else None,
                action_label=_PROFILE_EDITOR_LABEL
                if gap.category is GapCategory.MISSING_USER_INFORMATION
                else None,
            )
            for gap in result.gaps
        ],
        actions=[MatchEvidenceLine(code=action.code, message=action.message) for action in result.actions],
        unverified_requirements=[
            MatchRequirementLine(
                kind=requirement.kind.value,
                status=requirement.status.value,
                summary=requirement.summary,
                raw_quote=requirement.raw_quote,
                provenance_url=requirement.provenance_url,
            )
            for requirement in (getattr(result.eligibility_detail, "unverified", None) or [])
        ],
    )


def select_matches(results: list) -> list:
    """Pick the recommendations worth a card, keeping the engine's own ranking.

    Eligibility leads: a record the gate already refused must not be presented
    as a recommendation however well it scored. When nothing survives the gate the
    section is empty, because opening a command centre with what the student
    cannot have is the one thing it must not do.
    """
    surviving = [result for result in results if result.eligibility is not EligibilityStatus.INELIGIBLE]
    return surviving[:DASHBOARD_MATCH_LIMIT]


# ------------------------------------------------------------------------ gaps


def build_gaps(match_response, strength) -> list[GapItem]:
    """Profile gaps, from the two places Match already reports them.

    Profile-level incompleteness first, because that is input the student can
    actually change, then the student-actionable gaps surfaced across results.
    Deduplicated on ``(code, component)`` in first-seen order so two identical
    requests produce an identical list.
    """
    gaps: list[GapItem] = []
    seen: set[tuple[str, str | None]] = set()

    for improvement in strength.improvements:
        key = (improvement.code, improvement.component)
        if key in seen:
            continue
        seen.add(key)
        gaps.append(
            GapItem(
                code=improvement.code,
                message=improvement.message,
                category=GapCategory.MISSING_USER_INFORMATION.value,
                component=improvement.component,
                href=_PROFILE_EDITOR_HREF,
                action_label=_PROFILE_EDITOR_LABEL,
            )
        )

    for result in (match_response.results if match_response else []):
        for gap in result.gaps:
            if gap.category is not GapCategory.MISSING_USER_INFORMATION:
                continue
            key = (gap.code, gap.component)
            if key in seen:
                continue
            seen.add(key)
            gaps.append(
                GapItem(
                    code=gap.code,
                    message=gap.message,
                    category=gap.category.value,
                    component=gap.component,
                    href=_PROFILE_EDITOR_HREF,
                    action_label=_PROFILE_EDITOR_LABEL,
                )
            )

    return gaps


# ---------------------------------------------------------------- next actions

#: Fixed priority bands. Ordering is a property of this table, not a score, a
#: model or a clock reading: two identical states produce an identical list in
#: an identical order. No fake urgency.
_PRIORITY_PROFILE = 10
_PRIORITY_IN_PROGRESS = 20
_PRIORITY_SAVED_NOT_STARTED = 30
_PRIORITY_UNVERIFIED_REQUIREMENT = 40
_PRIORITY_CLOSING_SOON = 50
_PRIORITY_COMPARE = 60
_PRIORITY_EXPLORE = 90


def build_next_actions(
    has_profile: bool,
    strength,
    recommendations: list[MatchRecommendation],
    saved_items: list[SavedItem],
    application_items: list[ApplicationItem],
) -> list[NextAction]:
    actions: list[NextAction] = []

    if not has_profile:
        return [
            NextAction(
                code="complete_profile",
                title="Build your scholarship profile",
                detail=(
                    "ScholarZone checks every published eligibility rule against the details you "
                    "supply. Without a profile it cannot rank anything for you."
                ),
                priority=_PRIORITY_PROFILE,
                href=_PROFILE_EDITOR_HREF,
                action_label=_PROFILE_EDITOR_LABEL,
            )
        ]

    incomplete = strength.score is None or any(
        component.score != 100.0 for component in strength.components
    )
    if incomplete:
        actions.append(
            NextAction(
                code="improve_profile",
                title="Complete your profile",
                detail=(
                    "Each field you are missing is a published rule ScholarZone currently cannot "
                    "check against you, which is why some matches read as unevaluated."
                ),
                priority=_PRIORITY_PROFILE,
                href=_PROFILE_EDITOR_HREF,
                action_label=_PROFILE_EDITOR_LABEL,
            )
        )

    # An application already in motion outranks anything new: it is the one thing
    # the student has already decided to do.
    for item in sorted(
        (entry for entry in application_items if entry.state in ("in_progress", "planning")),
        key=lambda entry: (entry.updated_at, entry.scholarship.scholarship_id),
        reverse=True,
    ):
        actions.append(
            NextAction(
                code=f"continue_application_{item.scholarship.scholarship_id}",
                title=f"Continue {item.scholarship.name}",
                detail=f"You marked this one {item.state_label.lower()}.",
                priority=_PRIORITY_IN_PROGRESS,
                href=item.scholarship.detail_url,
                action_label="Continue",
            )
        )

    tracked = {item.scholarship.scholarship_id for item in application_items}
    for item in sorted(
        (entry for entry in saved_items if entry.scholarship.scholarship_id not in tracked),
        key=lambda entry: (entry.saved_at, entry.scholarship.scholarship_id),
    ):
        actions.append(
            NextAction(
                code=f"start_tracking_{item.scholarship.scholarship_id}",
                title=f"Start tracking {item.scholarship.name}",
                detail="You saved this one but have not marked it as planning or in progress.",
                priority=_PRIORITY_SAVED_NOT_STARTED,
                href=item.scholarship.detail_url,
                action_label="Open",
            )
        )
        break

    for recommendation in recommendations:
        if not recommendation.unverified_requirements:
            continue
        actions.append(
            NextAction(
                code=f"confirm_requirement_{recommendation.scholarship_id}",
                title=f"Confirm a requirement for {recommendation.name}",
                detail=(
                    "ScholarZone found a published rule it could not evaluate against your profile, "
                    "so it is reported as unconfirmed rather than as a match or a refusal."
                ),
                priority=_PRIORITY_UNVERIFIED_REQUIREMENT,
                href=recommendation.detail_url,
                action_label="Review",
            )
        )
        break

    for recommendation in recommendations:
        days = recommendation.days_to_deadline
        if days is None or days > 30:
            continue
        if recommendation.scholarship_id in tracked:
            continue
        actions.append(
            NextAction(
                code=f"review_deadline_{recommendation.scholarship_id}",
                title=f"Decide on {recommendation.name}",
                detail=f"{days} days remain on a published deadline.",
                priority=_PRIORITY_CLOSING_SOON,
                href=recommendation.detail_url,
                action_label="Review",
            )
        )
        break

    if len(saved_items) >= 2:
        actions.append(
            NextAction(
                code="compare_saved",
                title=f"Compare your {len(saved_items)} saved scholarships",
                detail="Side-by-side funding, deadline and verification state.",
                priority=_PRIORITY_COMPARE,
                href="/compare",
                action_label="Compare",
            )
        )

    if not actions:
        actions.append(
            NextAction(
                code="explore",
                title="Explore the scholarship directory",
                detail=(
                    "Your profile is complete and nothing is waiting on you. Opportunities are added "
                    "as awarding bodies publish and ScholarZone verifies them."
                ),
                priority=_PRIORITY_EXPLORE,
                href="/scholarships",
                action_label="Browse scholarships",
            )
        )

    return sorted(actions, key=lambda action: (action.priority, action.code))


# ------------------------------------------------------------------- aggregate


def _build_summary(summary: MatchSummary, count_report: dict | None) -> DashboardSummary:
    """Copy authoritative counts; read readiness from Count Intelligence.

    ``MatchSummary`` carries no readiness partition, so the ready-to-apply figure
    is read from the Count Intelligence report rather than tallied here. Reading
    it from the second authoritative engine - instead of counting readiness bands
    in this module - is what stops a dashboard number from becoming a private
    reimplementation of a published contract.
    """
    ready_to_apply = 0
    open_with_deadline = 0
    count_total = summary.total_candidates
    integrity_status = "UNAVAILABLE"
    integrity_issues: list[str] = []

    if count_report is not None:
        counts = count_report.get("summary", {}) or {}
        ready_to_apply = sum(int(counts.get(f"readiness.{key}", 0)) for key in READY_READINESS_BUCKETS)
        open_with_deadline = sum(int(counts.get(f"deadline.{key}", 0)) for key in OPEN_DEADLINE_BUCKETS)
        count_total = int(count_report.get("total_candidates", summary.total_candidates))
        integrity = count_report.get("integrity", {}) or {}
        integrity_status = str(integrity.get("status", "PASS"))
        integrity_issues = list(integrity.get("issues", []) or [])

    return DashboardSummary(
        universe="match_analysed",
        total_candidates=summary.total_candidates,
        visible_candidate_count=summary.visible_candidate_count,
        eligible_count=summary.eligible_count,
        needs_verification_count=summary.needs_verification_count,
        ineligible_count=summary.ineligible_count,
        strong_match_count=summary.strong_or_better_count,
        scored_count=summary.scored_count,
        not_scored_count=summary.not_scored_count,
        ready_to_apply_count=ready_to_apply,
        open_with_deadline_count=open_with_deadline,
        closing_soon_count=summary.closing_soon_count,
        truncated=summary.truncated,
    )


def _build_consistency(summary: MatchSummary, count_report: dict | None) -> CountConsistency:
    """Compare the two engines' universes and report the verdict.

    Match and Count Intelligence are separate analyses over one catalogue. If
    their totals disagreed, a dashboard showing both would contradict itself, so
    the comparison is performed server-side and published rather than left for a
    reader to notice.
    """
    if count_report is None:
        return CountConsistency(
            match_total_candidates=summary.total_candidates,
            count_total_candidates=summary.total_candidates,
            counts_agree=True,
            integrity_status="UNAVAILABLE",
        )

    count_total = int(count_report.get("total_candidates", summary.total_candidates))
    integrity = count_report.get("integrity", {}) or {}
    return CountConsistency(
        match_total_candidates=summary.total_candidates,
        count_total_candidates=count_total,
        counts_agree=count_total == summary.total_candidates,
        integrity_status=str(integrity.get("status", "PASS")),
        integrity_issues=list(integrity.get("issues", []) or []),
    )


def build_dashboard(db: Session, user: User, as_of: date | None = None) -> DashboardResponse:
    """Assemble the whole dashboard for one authenticated user.

    Every query here is scoped to ``user.id`` - the account the session resolved
    to, never a value from the request - so one student can only ever read their
    own rows.
    """
    effective_date = as_of or date.today()

    record = get_profile_record(db, user.id)
    profile = load_stored_profile(db, user.id)
    has_profile = not profile_is_empty(profile)

    saved_rows = list(
        db.execute(
            select(SavedScholarship)
            .where(SavedScholarship.user_id == user.id)
            .order_by(SavedScholarship.scholarship_id.asc())
            .limit(MAX_SAVED_ITEMS)
        ).scalars()
    )
    application_rows = list(
        db.execute(
            select(ApplicationRecord)
            .where(ApplicationRecord.user_id == user.id)
            .order_by(ApplicationRecord.scholarship_id.asc())
            .limit(MAX_APPLICATION_ITEMS)
        ).scalars()
    )

    match_response = None
    count_report: dict | None = None

    if has_profile:
        # A dashboard-sized page of results over an unchanged universe: every
        # summary count below still describes all analysed candidates.
        request = profile.model_copy(update={"limit": DASHBOARD_MATCH_LIMIT})
        match_response = match_scholarships(db, request, effective_date)
        count_report = count_intelligence(
            db,
            request,
            as_of=effective_date,
            capabilities=("summary", "integrity"),
        )

    if match_response is not None:
        strength = match_response.profile_strength
        summary = match_response.summary
        results = list(match_response.results)
    else:
        # No profile, so nothing was scored. Strength is still reported, because
        # "you have not told us anything yet" is itself the measurement, and the
        # engine returns ``score=None`` for exactly that case.
        from .matching.normalize import normalise_profile

        strength = compute_profile_strength(normalise_profile(MatchProfileRequest()))
        summary = _EMPTY_SUMMARY
        results = []

    selected = select_matches(results)

    # One bounded query for every id this response will describe: the shortlist,
    # the applications, and the recommended cards that need their published
    # deadline wording. Never one query per card.
    acted_ids = sorted({row.scholarship_id for row in saved_rows} | {row.scholarship_id for row in application_rows})
    needed_ids = sorted(set(acted_ids) | {result.scholarship_id for result in selected})
    rows_by_id = load_facts_for_ids(db, needed_ids)

    recommendations: list[MatchRecommendation] = []
    for result in selected:
        recommendation = _recommendation(result)
        # The published wording and the machine-readable date live on the
        # catalogue row, not on the match result, so they are joined for exactly
        # the ids the response is about.
        row = rows_by_id.get(result.scholarship_id)
        if row is not None:
            recommendation.deadline = row.deadline_display
            recommendation.deadline_date = row.deadline_date
            recommendation.deadline_precision = coerce_deadline_precision(row.deadline_precision)
        recommendations.append(recommendation)

    match_by_id = {item.scholarship_id: item for item in recommendations}
    saved_by_id = {row.scholarship_id: row for row in saved_rows}
    application_by_id = {row.scholarship_id: row for row in application_rows}

    def _reference(scholarship_id: int) -> ScholarshipReference | None:
        row = rows_by_id.get(scholarship_id)
        if row is None:
            # The student acted on a record the public directory no longer shows
            # - archived, or failing the visibility gate. It is omitted rather
            # than surfaced, because the catalogue's own visibility rules decide
            # what this student is allowed to see.
            return None
        status = normalize_public_verification_status(row.verification_status)
        return ScholarshipReference(
            scholarship_id=row.id,
            name=row.title,
            country=row.country,
            degree=row.degree,
            funding=row.funding,
            detail_url=f"/scholarships/{row.id}",
            official_source_url=row.official_source_url,
            verification_status=status,
            verified=public_verified_from_status(status),
            verification_display=verification_display(status),
        )

    saved_items: list[SavedItem] = []
    for row in saved_rows:
        reference = _reference(row.scholarship_id)
        if reference is None:
            continue
        match_item = match_by_id.get(row.scholarship_id)
        application = application_by_id.get(row.scholarship_id)
        saved_items.append(
            SavedItem(
                scholarship=reference,
                saved_at=row.created_at,
                is_in_matches=match_item is not None,
                days_remaining=match_item.days_to_deadline if match_item else None,
                readiness_label=match_item.readiness_label if match_item else None,
                application_state=application.state if application else None,
            )
        )

    application_items: list[ApplicationItem] = []
    for row in application_rows:
        reference = _reference(row.scholarship_id)
        if reference is None:
            continue
        match_item = match_by_id.get(row.scholarship_id)
        application_items.append(
            ApplicationItem(
                scholarship=reference,
                state=row.state,
                state_label=APPLICATION_STATE_LABELS.get(row.state, row.state),
                created_at=row.created_at,
                updated_at=row.updated_at,
                days_remaining=match_item.days_to_deadline if match_item else None,
                deadline=match_item.deadline if match_item else None,
                readiness_label=match_item.readiness_label if match_item else None,
                fit_score=match_item.fit_score if match_item else None,
            )
        )

    deadlines = _build_deadlines(
        recommendations, saved_items, application_items, saved_by_id, rows_by_id, effective_date
    )

    return DashboardResponse(
        as_of=effective_date,
        has_profile=has_profile,
        application_states=sorted(APPLICATION_STATES),
        profile=build_profile_snapshot(profile, record.updated_at if record is not None else None),
        profile_strength=build_profile_strength(strength),
        summary=_build_summary(summary, count_report),
        consistency=_build_consistency(summary, count_report),
        matches=recommendations,
        matches_truncated=bool(summary.truncated),
        saved=saved_items,
        deadlines=deadlines,
        applications=application_items,
        gaps=build_gaps(match_response, strength),
        next_actions=build_next_actions(
            has_profile, strength, recommendations, saved_items, application_items
        ),
    )


def _build_deadlines(
    recommendations: list[MatchRecommendation],
    saved_items: list[SavedItem],
    application_items: list[ApplicationItem],
    saved_by_id: dict,
    rows_by_id: dict[int, CandidateRow],
    as_of: date,
) -> list[DeadlineItem]:
    """Deadline Watch over everything the student has acted on.

    Ordering is exactly the product rule: nearest actionable deadline, then
    readiness, then scholarship id as a stable tiebreaker, so two identical
    states always render an identical order.

    ``days_remaining`` is always the engine's own figure. A record with no
    trustworthy fixed date - rolling, recurring or unpublished - reports ``None``
    and is ordered last, because it is an open round rather than an urgent one,
    and showing it above a real deadline would be the more harmful error.
    """
    entries: dict[int, DeadlineItem] = {}

    for item in application_items:
        reference = item.scholarship
        entries[reference.scholarship_id] = DeadlineItem(
            scholarship_id=reference.scholarship_id,
            name=reference.name,
            detail_url=reference.detail_url,
            deadline=item.deadline,
            days_remaining=item.days_remaining,
            timing_bucket=None,
            is_actionable=item.days_remaining is not None and item.days_remaining >= 0,
            readiness_label=item.readiness_label,
            fit_score=item.fit_score,
            application_state=item.state,
            is_saved=reference.scholarship_id in saved_by_id,
            verification_status=reference.verification_status,
            verified=reference.verified,
            verification_display=reference.verification_display,
        )

    for item in saved_items:
        reference = item.scholarship
        existing = entries.get(reference.scholarship_id)
        if existing is None:
            entries[reference.scholarship_id] = DeadlineItem(
                scholarship_id=reference.scholarship_id,
                name=reference.name,
                detail_url=reference.detail_url,
                deadline=None,
                days_remaining=item.days_remaining,
                timing_bucket=None,
                is_actionable=item.days_remaining is not None and item.days_remaining >= 0,
                readiness_label=item.readiness_label,
                fit_score=None,
                application_state=None,
                is_saved=True,
                verification_status=reference.verification_status,
                verified=reference.verified,
                verification_display=reference.verification_display,
            )
        else:
            existing.is_saved = True

    match_by_id = {item.scholarship_id: item for item in recommendations}

    for scholarship_id, entry in entries.items():
        recommendation = match_by_id.get(scholarship_id)
        if recommendation is not None:
            entry.deadline = entry.deadline or recommendation.deadline
            entry.timing_bucket = recommendation.timing_bucket
            if entry.days_remaining is None:
                entry.days_remaining = recommendation.days_to_deadline
            if entry.readiness_label is None:
                entry.readiness_label = recommendation.readiness_label
            if entry.fit_score is None:
                entry.fit_score = recommendation.fit_score
            entry.is_actionable = entry.days_remaining is not None and entry.days_remaining >= 0
        else:
            # Not in the returned matches. The engine still owns the deadline
            # question, so it is asked directly for these ids rather than being
            # approximated in this module.
            row = rows_by_id.get(scholarship_id)
            if row is not None:
                facts = deadline_facts(row, as_of)
                entry.deadline = row.deadline_display
                entry.days_remaining = facts.days_remaining
                entry.timing_bucket = facts.kind if facts.kind in DEADLINE_HORIZONS else None
                entry.is_actionable = facts.days_remaining is not None and facts.days_remaining >= 0

    return sorted(
        entries.values(),
        key=lambda entry: (
            entry.days_remaining is None,
            entry.days_remaining if entry.days_remaining is not None else 0,
            0 if entry.readiness_label else 1,
            entry.scholarship_id,
        ),
    )


def count_saved(db: Session, user_id: int) -> int:
    """The authoritative shortlist size, for the count beside the list."""
    return int(
        db.execute(
            select(func.count()).select_from(SavedScholarship).where(SavedScholarship.user_id == user_id)
        ).scalar_one()
    )


__all__ = [
    "DASHBOARD_MATCH_LIMIT",
    "build_dashboard",
    "build_gaps",
    "build_next_actions",
    "build_profile_snapshot",
    "build_profile_strength",
    "count_saved",
    "deadline_facts",
    "get_profile_record",
    "load_facts_for_ids",
    "load_stored_profile",
    "profile_is_empty",
    "select_matches",
]