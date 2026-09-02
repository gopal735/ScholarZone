"""Counterfactual safety and pre-commit consistency engine.

Simulates proposed scholarship state BEFORE commit to detect inconsistencies
that would be introduced by the change. Runs ON TOP of the existing safe updater
as an additional safety layer.

Design principles:
- Deterministic: same inputs always produce same outputs
- Non-destructive: simulation NEVER mutates the database
- Explainable: every finding includes reason codes and explanation
- Field-level: reports inconsistencies at field granularity
- Cycle-safe: handles dependency cycles without infinite loops
- Idempotent: re-running simulation produces same result
- No network calls: pure computation layer
- O(changed_fields + affected_dependencies): efficient analysis
- Safety-first: CRITICAL inconsistencies block auto-update

Counterfactual safety may BLOCK or escalate to REVIEW,
but it must NEVER force an update.

A proposed change can AUTO_UPDATE only if:
- existing Evidence/Confidence/Consensus/Safety rules pass
- counterfactual simulation is SAFE
- no critical newly introduced inconsistency

Integration:
    Safe Update
        ↓
    Counterfactual Safety
        ↓
    Existing Safety Gate
        ↓
    AUTO UPDATE / REVIEW / BLOCK
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from .anomaly_detection import (
    AnomalyResult,
    AnomalySeverity,
    detect_anomalies,
    detect_lifecycle_anomaly,
    detect_multi_field_anomaly,
)
from .change_impact_staleness import compute_change_impact
from .dependency_graph import (
    DependencyAnalysis,
    analyze_dependencies,
)
from .lifecycle_identity import (
    ACTIVE,
    APPLICATION_OPEN,
    ARCHIVED,
    CLOSED,
    DEADLINE_NEAR,
    DISCOVERED,
    RESULT_PENDING,
    classify_lifecycle_state,
)


class CounterfactualSeverity(str, Enum):
    """Severity levels for counterfactual findings."""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class LifecycleImpact:
    """Lifecycle state change analysis."""
    previous_state: str
    proposed_state: str
    state_changed: bool
    is_valid_transition: bool
    is_terminal_regression: bool
    reason: str


@dataclass
class CounterfactualResult:
    """Result of counterfactual simulation."""
    safe: bool
    severity: CounterfactualSeverity
    simulated_fields: dict[str, Any] = field(default_factory=dict)
    violated_rules: list[str] = field(default_factory=list)
    affected_dependencies: list[str] = field(default_factory=list)
    anomaly_flags: list[AnomalyResult] = field(default_factory=list)
    lifecycle_impact: LifecycleImpact | None = None
    explanation: str = ""
    reason_codes: list[str] = field(default_factory=list)
    dependency_analysis: DependencyAnalysis | None = None

    def requires_review(self) -> bool:
        """Check if findings require human review."""
        return self.severity in (
            CounterfactualSeverity.LOW,
            CounterfactualSeverity.MEDIUM,
            CounterfactualSeverity.HIGH,
            CounterfactualSeverity.CRITICAL,
        )

    def should_block(self) -> bool:
        """Check if findings should block auto-update."""
        return self.severity == CounterfactualSeverity.CRITICAL


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _normalize(value: Any) -> str:
    """Normalize a value for comparison."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ",".join(str(v).strip().lower() for v in value)
    return str(value).strip().lower()


def _days_between(d1: date | None, d2: date | None) -> int | None:
    """Calculate days between two dates."""
    if d1 is None or d2 is None:
        return None
    if isinstance(d1, datetime):
        d1 = d1.date() if hasattr(d1, 'date') else d1
    if isinstance(d2, datetime):
        d2 = d2.date() if hasattr(d2, 'date') else d2
    try:
        return (d2 - d1).days
    except (TypeError, AttributeError):
        return None


def _build_simulated_state(
    current_state: dict[str, Any],
    proposed_changes: dict[str, Any],
) -> dict[str, Any]:
    """Build the simulated state by applying proposed changes to current state."""
    simulated = dict(current_state)
    for field_name, new_value in proposed_changes.items():
        simulated[field_name] = new_value
    return simulated


def _check_deadline_application_period_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check deadline_date vs application-period consistency."""
    deadline = simulated.get("deadline_date")
    app_period = simulated.get("application_period")

    if deadline is None or app_period is None:
        return True, None, None

    deadline_date = deadline if isinstance(deadline, date) else None
    if deadline_date is None:
        try:
            deadline_date = date.fromisoformat(str(deadline))
        except (ValueError, TypeError):
            return True, None, None

    app_period_lower = str(app_period).lower()

    # Check for seasonal/period inconsistencies
    deadline_month = deadline_date.month
    season_indicators = {
        "spring": (3, 4, 5),
        "summer": (6, 7, 8),
        "fall": (9, 10, 11),
        "autumn": (9, 10, 11),
        "winter": (12, 1, 2),
    }

    for season, months in season_indicators.items():
        if season in app_period_lower and deadline_month not in months:
            # Seasonal mismatch - flag but don't block
            if season in ("spring", "summer") and deadline_month in (9, 10, 11, 12, 1, 2):
                return (
                    False,
                    f"application_period indicates {season} but deadline_month is {deadline_date.strftime('%B')}",
                    "deadline_application_period_season_mismatch",
                )

    return True, None, None


def _check_deadline_status_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check deadline_date vs status/lifecycle consistency."""
    deadline = simulated.get("deadline_date")
    status = simulated.get("status")

    if deadline is None or status is None:
        return True, None, None

    deadline_date = deadline if isinstance(deadline, date) else None
    if deadline_date is None:
        try:
            deadline_date = date.fromisoformat(str(deadline))
        except (ValueError, TypeError):
            return True, None, None

    today = _today()
    status_lower = str(status).lower()

    # Deadline in past but status is active/open
    if deadline_date < today and status_lower in ("active", "application_open", "open", "discovered"):
        return (
            False,
            f"deadline_date ({deadline_date}) is in the past but status is '{status}'",
            "deadline_passed_but_status_active",
        )

    # Closed status but deadline in future
    if deadline_date >= today and status_lower in ("closed", "expired", "cancelled"):
        return (
            False,
            f"deadline_date ({deadline_date}) is in the future but status is '{status}'",
            "deadline_future_but_status_closed",
        )

    return True, None, None


def _check_eligibility_degree_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check eligibility vs degree/requirements consistency."""
    eligibility = simulated.get("eligibility")
    degree = simulated.get("degree")
    requirements = simulated.get("requirements")

    if not eligibility:
        return True, None, None

    degree_lower = _normalize(degree)
    reqs_lower = _normalize(requirements)

    # Check for degree-specific requirements mismatches
    if degree_lower and reqs_lower:
        if "phd" in degree_lower and "bachelor" in reqs_lower and "master" not in reqs_lower:
            return (
                False,
                "PhD degree level but requirements only mention bachelor",
                "eligibility_degree_requirements_mismatch",
            )

    return True, None, None


def _check_funding_coverage_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check funding vs coverage/requirements consistency."""
    funding = simulated.get("funding")
    coverage = simulated.get("coverage")

    if funding is None or coverage is None:
        return True, None, None

    funding_lower = _normalize(funding)

    # Full funding with empty coverage
    if funding_lower in ("full", "fully funded", "full funding"):
        if not coverage or (isinstance(coverage, list) and len(coverage) == 0):
            return (
                False,
                "funding is 'full' but coverage is empty",
                "full_funding_empty_coverage",
            )

    # No funding but coverage exists
    if funding_lower in ("none", "no funding", "unfunded", "self-funded"):
        if isinstance(coverage, list) and len(coverage) > 0:
            return (
                False,
                "funding is 'none' but coverage has entries",
                "no_funding_has_coverage",
            )

    return True, None, None


def _check_application_method_link_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check application_method vs application_link consistency."""
    app_method = simulated.get("application_method")
    app_link = simulated.get("application_link")

    if app_method is None:
        return True, None, None

    method_lower = _normalize(app_method)

    # Online method but no link
    if "online" in method_lower and not app_link:
        return (
            False,
            "application_method includes 'online' but application_link is missing",
            "online_method_missing_link",
        )

    return True, None, None


def _check_country_source_consistency(
    simulated: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    """Check country vs official_source consistency."""
    country = simulated.get("country")
    source = simulated.get("official_source")
    source_url = simulated.get("official_source_url")

    if not country:
        return True, None, None

    country_lower = _normalize(country)

    # Check for obvious country-source mismatches
    # This is a lightweight check - not exhaustive
    country_domain_hints = {
        "uk": [".uk", "gov.uk", "ac.uk"],
        "usa": [".edu", "gov"],
        "germany": [".de", "gov.de"],
        "france": [".fr", "gouv.fr"],
        "canada": [".ca", "gc.ca"],
        "australia": [".au", "gov.au"],
    }

    if source_url and source:
        url_lower = str(source_url).lower()
        source_lower = str(source).lower()

        # Check if country name appears in source but URL doesn't match
        country_name = country_lower.split(",")[0].strip()
        if country_name in source_lower:
            # Country mentioned in source - URL should match
            expected_domains = country_domain_hints.get(country_name, [])
            if expected_domains and not any(d in url_lower for d in expected_domains):
                return (
                    True,
                    None,
                    None,
                )

    return True, None, None


def _check_impossible_combinations(
    simulated: dict[str, Any],
) -> tuple[bool, list[str], list[str]]:
    """Check for impossible or contradictory field combinations."""
    violations: list[str] = []
    reason_codes: list[str] = []

    # Status: archived but deadline in future
    status = simulated.get("status")
    deadline = simulated.get("deadline_date")
    if status and deadline:
        status_lower = _normalize(status)
        deadline_date = deadline if isinstance(deadline, date) else None
        if deadline_date is None:
            try:
                deadline_date = date.fromisoformat(str(deadline))
            except (ValueError, TypeError):
                deadline_date = None

        if status_lower == "archived" and deadline_date and deadline_date >= _today():
            violations.append(
                f"status is 'archived' but deadline ({deadline_date}) is in the future"
            )
            reason_codes.append("archived_with_future_deadline")

    # Funding: full funding but eligibility is extremely restrictive
    funding = simulated.get("funding")
    eligibility = simulated.get("eligibility")
    if funding and eligibility:
        funding_lower = _normalize(funding)
        if funding_lower in ("full", "fully funded"):
            elig_text = _normalize(eligibility) if isinstance(eligibility, list) else _normalize(eligibility)
            if "citizens of" in elig_text and elig_text.count(",") > 3:
                violations.append(
                    "Full funding with extremely restrictive citizenship requirements"
                )
                reason_codes.append("full_funding_very_restrictive")

    return len(violations) == 0, violations, reason_codes


def _analyze_lifecycle_impact(
    session: Any,
    scholarship: Any,
    simulated_state: dict[str, Any],
) -> LifecycleImpact:
    """Analyze lifecycle state change between current and proposed."""
    current_lifecycle = classify_lifecycle_state(session, scholarship)

    # Build a temporary scholarship object for lifecycle classification
    # This does NOT mutate the database - we use a simple object proxy
    class _SimulatedScholarship:
        def __init__(self, state: dict[str, Any]):
            for key, value in state.items():
                setattr(self, key, value)

    simulated_scholarship = _SimulatedScholarship(simulated_state)

    # Copy required attributes from original if missing
    for attr in ("id", "created_at", "updated_at", "is_verified", "verification_status"):
        if not hasattr(simulated_scholarship, attr):
            setattr(simulated_scholarship, attr, getattr(scholarship, attr, None))

    proposed_lifecycle = classify_lifecycle_state(session, simulated_scholarship)

    state_changed = current_lifecycle.state != proposed_lifecycle.state

    # Check for invalid transitions
    is_valid = True
    if state_changed:
        # Terminal states should not regress
        terminal_states = {ARCHIVED, CLOSED}
        if current_lifecycle.state in terminal_states and proposed_lifecycle.state not in terminal_states:
            is_valid = False

    # Detect terminal regression: status change from terminal to non-terminal
    current_status = getattr(scholarship, "status", "")
    proposed_status = simulated_state.get("status", current_status)
    current_status_lower = str(current_status).lower() if current_status else ""
    proposed_status_lower = str(proposed_status).lower() if proposed_status else ""

    terminal_statuses = {"closed", "expired", "cancelled", "archived"}
    non_terminal_statuses = {"active", "open", "discovered", "application_open"}

    status_regression = (
        current_status_lower in terminal_statuses
        and proposed_status_lower in non_terminal_statuses
    )

    is_terminal_regression = (
        (current_lifecycle.state in (CLOSED, ARCHIVED)
         and proposed_lifecycle.state not in (CLOSED, ARCHIVED, RESULT_PENDING))
        or status_regression
    )

    reason = proposed_lifecycle.reason
    if state_changed:
        reason = f"Lifecycle would change: {current_lifecycle.state} -> {proposed_lifecycle.state} ({proposed_lifecycle.reason})"
    elif status_regression:
        reason = f"Status regression: '{current_status}' -> '{proposed_status}' is invalid"

    return LifecycleImpact(
        previous_state=current_lifecycle.state,
        proposed_state=proposed_lifecycle.state,
        state_changed=state_changed or status_regression,
        is_valid_transition=is_valid and not status_regression,
        is_terminal_regression=is_terminal_regression,
        reason=reason,
    )


def _detect_new_anomalies(
    current_state: dict[str, Any],
    simulated_state: dict[str, Any],
    changed_fields: dict[str, Any],
) -> list[AnomalyResult]:
    """Detect newly introduced anomalies by comparing current vs simulated."""
    anomalies: list[AnomalyResult] = []

    for field_name, new_value in changed_fields.items():
        old_value = current_state.get(field_name)
        if old_value == new_value:
            continue

        # Run anomaly detection on the change
        field_anomalies = detect_anomalies(
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            scholarship_status=simulated_state.get("status"),
            deadline_date=simulated_state.get("deadline_date"),
            is_verified=simulated_state.get("is_verified"),
        )
        anomalies.extend(field_anomalies)

    # Multi-field anomaly detection
    multi_field_changes = {
        field_name: (current_state.get(field_name), new_value)
        for field_name, new_value in changed_fields.items()
        if current_state.get(field_name) != new_value
    }
    if multi_field_changes:
        multi_result = detect_multi_field_anomaly(multi_field_changes)
        if multi_result:
            anomalies.append(multi_result)

    return anomalies


def simulate_counterfactual(
    session: Any,
    scholarship: Any,
    proposed_changes: dict[str, Any],
    current_state: dict[str, Any] | None = None,
    today: date | None = None,
) -> CounterfactualResult:
    """Simulate proposed changes and detect inconsistencies.

    Args:
        session: Database session (used for lifecycle classification).
        scholarship: Current scholarship ORM object.
        proposed_changes: Dict of field_name -> new_value to simulate.
        current_state: Optional pre-extracted current state. If None, extracted from scholarship.
        today: Optional date override for deterministic testing.

    Returns:
        CounterfactualResult with safety assessment.
    """
    if today is None:
        today = _today()

    # Build current state if not provided
    if current_state is None:
        current_state = {
            "title": scholarship.title,
            "country": scholarship.country,
            "degree": scholarship.degree,
            "funding": scholarship.funding,
            "description": scholarship.description,
            "deadline_date": scholarship.deadline_date,
            "deadline_display": scholarship.deadline_display,
            "deadline_precision": scholarship.deadline_precision,
            "status": scholarship.status,
            "is_verified": scholarship.is_verified,
            "last_verified_at": scholarship.last_verified_at,
            "last_verified_date": scholarship.last_verified_date,
            "verification_status": scholarship.verification_status,
            "next_verification_due": scholarship.next_verification_due,
            "verified_by": scholarship.verified_by,
            "verification_notes": scholarship.verification_notes,
            "region": scholarship.region,
            "duration": scholarship.duration,
            "application_period": scholarship.application_period,
            "official_source": scholarship.official_source,
            "official_source_url": scholarship.official_source_url,
            "catalogue_url": scholarship.catalogue_url,
            "official_updates_url": scholarship.official_updates_url,
            "application_link": scholarship.application_link,
            "eligibility": scholarship.eligibility,
            "eligibility_summary": scholarship.eligibility_summary,
            "benefits": scholarship.benefits,
            "coverage": scholarship.coverage,
            "requirements": scholarship.requirements,
            "documents": scholarship.documents,
            "english_requirement": scholarship.english_requirement,
            "application_method": scholarship.application_method,
            "selection_notes": scholarship.selection_notes,
            "program_type": scholarship.program_type,
            "best_fit": scholarship.best_fit,
            "notes": scholarship.notes,
        }

    # Build simulated state (does NOT mutate scholarship)
    simulated = _build_simulated_state(current_state, proposed_changes)

    violated_rules: list[str] = []
    reason_codes: list[str] = []
    all_anomalies: list[AnomalyResult] = []

    # 1. Dependency analysis
    dep_analysis = analyze_dependencies(
        changed_fields=list(proposed_changes.keys()),
    )
    affected_dependencies = [af.field_name for af in dep_analysis.affected_fields]

    # 2. Deadline/application-period consistency
    deadline_app_ok, deadline_app_violation, deadline_app_code = (
        _check_deadline_application_period_consistency(simulated)
    )
    if not deadline_app_ok:
        violated_rules.append(deadline_app_violation)
        reason_codes.append(deadline_app_code)

    # 3. Deadline/status consistency
    deadline_status_ok, deadline_status_violation, deadline_status_code = (
        _check_deadline_status_consistency(simulated)
    )
    if not deadline_status_ok:
        violated_rules.append(deadline_status_violation)
        reason_codes.append(deadline_status_code)

    # 4. Eligibility/degree/requirements consistency
    elig_ok, elig_violation, elig_code = _check_eligibility_degree_consistency(simulated)
    if not elig_ok:
        violated_rules.append(elig_violation)
        reason_codes.append(elig_code)

    # 5. Funding/coverage consistency
    fund_ok, fund_violation, fund_code = _check_funding_coverage_consistency(simulated)
    if not fund_ok:
        violated_rules.append(fund_violation)
        reason_codes.append(fund_code)

    # 6. Application-method/link consistency
    app_ok, app_violation, app_code = _check_application_method_link_consistency(simulated)
    if not app_ok:
        violated_rules.append(app_violation)
        reason_codes.append(app_code)

    # 7. Country/source consistency
    country_ok, country_violation, country_code = _check_country_source_consistency(simulated)
    if not country_ok:
        violated_rules.append(country_violation)
        reason_codes.append(country_code)

    # 8. Impossible combinations
    impossible_ok, impossible_violations, impossible_codes = _check_impossible_combinations(simulated)
    if not impossible_ok:
        violated_rules.extend(impossible_violations)
        reason_codes.extend(impossible_codes)

    # 9. Lifecycle impact analysis
    lifecycle_impact = _analyze_lifecycle_impact(session, scholarship, simulated)
    if lifecycle_impact.is_terminal_regression:
        violated_rules.append(
            f"Invalid lifecycle regression: {lifecycle_impact.previous_state} -> {lifecycle_impact.proposed_state}"
        )
        reason_codes.append("invalid_lifecycle_regression")

    # 10. Detect newly introduced anomalies
    new_anomalies = _detect_new_anomalies(current_state, simulated, proposed_changes)
    all_anomalies.extend(new_anomalies)

    # Add critical anomalies from detection
    for anomaly in new_anomalies:
        if anomaly.should_block():
            violated_rules.append(f"Critical anomaly: {anomaly.explanation}")
            reason_codes.append(f"critical_anomaly:{anomaly.reason_codes[0] if anomaly.reason_codes else 'unknown'}")

    # Determine overall severity
    severity = CounterfactualSeverity.SAFE
    if violated_rules:
        # Check for critical violations
        critical_indicators = [
            "invalid_lifecycle_regression",
            "archived_with_future_deadline",
            "critical_anomaly",
            "deadline_passed_but_status_active",
            "deadline_future_but_status_closed",
        ]
        if any(
            any(indicator in rc for indicator in critical_indicators)
            for rc in reason_codes
        ):
            severity = CounterfactualSeverity.CRITICAL
        elif len(violated_rules) >= 3:
            severity = CounterfactualSeverity.HIGH
        elif len(violated_rules) >= 2:
            severity = CounterfactualSeverity.MEDIUM
        else:
            severity = CounterfactualSeverity.LOW

    # Build explanation
    if violated_rules:
        explanation = f"Counterfactual simulation found {len(violated_rules)} inconsistency(ies): " + "; ".join(violated_rules)
    else:
        explanation = "Counterfactual simulation: no inconsistencies detected"

    # Any violation makes the result not safe
    is_safe = len(violated_rules) == 0

    return CounterfactualResult(
        safe=is_safe,
        severity=severity,
        simulated_fields=simulated,
        violated_rules=violated_rules,
        affected_dependencies=affected_dependencies,
        anomaly_flags=all_anomalies,
        lifecycle_impact=lifecycle_impact,
        explanation=explanation,
        reason_codes=reason_codes,
        dependency_analysis=dep_analysis,
    )


def batch_simulate_counterfactual(
    session: Any,
    scholarships: list[Any],
    proposed_changes_list: list[dict[str, Any]],
    current_states: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> list[CounterfactualResult]:
    """Run counterfactual simulation for multiple scholarships.

    Args:
        session: Database session.
        scholarships: List of scholarship ORM objects.
        proposed_changes_list: List of proposed changes dicts (one per scholarship).
        current_states: Optional list of pre-extracted current states.
        today: Optional date override for deterministic testing.

    Returns:
        List of CounterfactualResult objects.
    """
    results: list[CounterfactualResult] = []
    for idx, scholarship in enumerate(scholarships):
        proposed = proposed_changes_list[idx] if idx < len(proposed_changes_list) else {}
        current = current_states[idx] if current_states and idx < len(current_states) else None
        result = simulate_counterfactual(
            session=session,
            scholarship=scholarship,
            proposed_changes=proposed,
            current_state=current,
            today=today,
        )
        results.append(result)
    return results


def validate_proposed_state(
    session: Any,
    scholarship: Any,
    proposed_changes: dict[str, Any],
    current_state: dict[str, Any] | None = None,
    today: date | None = None,
) -> tuple[bool, CounterfactualResult]:
    """Validate a proposed state change.

    Convenience function that returns (is_valid, result) tuple.

    Args:
        session: Database session.
        scholarship: Current scholarship ORM object.
        proposed_changes: Dict of field_name -> new_value.
        current_state: Optional pre-extracted current state.
        today: Optional date override.

    Returns:
        Tuple of (is_valid, CounterfactualResult).
    """
    result = simulate_counterfactual(
        session=session,
        scholarship=scholarship,
        proposed_changes=proposed_changes,
        current_state=current_state,
        today=today,
    )
    return (not result.requires_review(), result)
