"""Dependency-aware verification graph for scholarship field relationships.

Determines which fields must be re-validated when a related field changes,
enabling targeted re-verification instead of full-record reprocessing.

Design principles:
- Deterministic: same inputs always produce same affected-field sets
- Cycle-safe: graph traversal detects and handles cycles
- Depth-limited: prevents unbounded traversal
- Auditable: every dependency rule is versioned and explainable
- Low-latency: in-memory static graph, O(V+E) traversal
- No network calls: pure computation layer
- Batch-friendly: supports batch dependency resolution
- Safety-first: ambiguous dependencies escalate to REVIEW

Dependency types:
- DIRECT: field A change requires re-verification of field B
- TRANSITIVE: field A change requires re-verification of field B,
  which requires re-verification of field C
- NO_RECHECK: field A change does not require re-verification of field B

Criticality levels (from change_impact_staleness):
- CRITICAL: deadline_date, eligibility, funding, application_method, etc.
- HIGH: documents, requirements, duration, application_period, etc.
- MEDIUM: best_fit, program_type, notes, catalogue_url, etc.
- LOW: title, description, country, degree, region, etc.

Version: 1 (initial dependency graph for scholarship field relationships)
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any


class DependencyType(str, Enum):
    """Types of field dependencies."""
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    NO_RECHECK = "no_recheck"


class ReVerificationClass(str, Enum):
    """Classification of re-verification requirements."""
    DIRECT = "direct"
    TRANSITIVE = "transitive"
    NO_RECHECK = "no_recheck"
    REVIEW = "review"


class CriticalityLevel(str, Enum):
    """Field criticality levels (mirrors change_impact_staleness)."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class DependencyEdge:
    """A single dependency relationship between two fields."""
    source_field: str
    target_field: str
    dependency_type: DependencyType
    criticality: CriticalityLevel
    reason: str


@dataclass(frozen=True)
class AffectedField:
    """A field that requires re-verification due to a dependency."""
    field_name: str
    re_verification_class: ReVerificationClass
    criticality: CriticalityLevel
    depth: int
    reason: str
    source_fields: tuple[str, ...]
    requires_escalation: bool = False


@dataclass
class DependencyAnalysis:
    """Complete analysis result for a set of changed fields."""
    changed_fields: tuple[str, ...]
    affected_fields: list[AffectedField]
    direct_fields: list[AffectedField]
    transitive_fields: list[AffectedField]
    review_fields: list[AffectedField]
    no_recheck_fields: list[str]
    max_depth_reached: bool = False
    cycles_detected: list[tuple[str, ...]] = dataclass_field(default_factory=list)
    analysis_version: str = "v1"


    @property
    def requires_full_verification(self) -> bool:
        """Check if full record verification is needed."""
        return len(self.review_fields) > 0


    @property
    def requires_review(self) -> bool:
        """Check if any fields require human review."""
        return len(self.review_fields) > 0


    @property
    def re_verification_set(self) -> frozenset[str]:
        """Get the complete set of fields requiring re-verification."""
        return frozenset(
            af.field_name for af in self.affected_fields
            if af.re_verification_class != ReVerificationClass.NO_RECHECK
        )


    @property
    def prioritized_fields(self) -> list[AffectedField]:
        """Get affected fields prioritized by criticality then depth."""
        criticality_order = {
            CriticalityLevel.CRITICAL: 0,
            CriticalityLevel.HIGH: 1,
            CriticalityLevel.MEDIUM: 2,
            CriticalityLevel.LOW: 3,
        }
        return sorted(
            self.affected_fields,
            key=lambda af: (
                criticality_order.get(af.criticality, 4),
                af.depth,
                af.field_name,
            ),
        )


# Dependency rules version
DEPENDENCY_GRAPH_VERSION = "v1"

# Maximum traversal depth to prevent unbounded analysis
DEFAULT_MAX_DEPTH = 5


# Deterministic dependency rules
# Each rule: (source_field, target_field, criticality, reason)
# Rules are auditable and versioned
_DEPENDENCY_RULES: tuple[tuple[str, str, CriticalityLevel, str], ...] = (
    # deadline_date changes affect deadline_display and application_period
    ("deadline_date", "deadline_display", CriticalityLevel.CRITICAL,
     "Deadline date change requires display value re-verification"),
    ("deadline_date", "application_period", CriticalityLevel.HIGH,
     "Deadline date change may affect application period validity"),
    ("deadline_date", "status", CriticalityLevel.HIGH,
     "Deadline date change may affect scholarship lifecycle status"),
    ("deadline_date", "deadline_precision", CriticalityLevel.MEDIUM,
     "Deadline date change may require precision adjustment"),

    # deadline_display changes may affect deadline interpretation
    ("deadline_display", "application_period", CriticalityLevel.MEDIUM,
     "Deadline display change may affect application period interpretation"),

    # eligibility changes affect requirements and documents
    ("eligibility", "requirements", CriticalityLevel.CRITICAL,
     "Eligibility criteria change requires requirements re-verification"),
    ("eligibility", "documents", CriticalityLevel.HIGH,
     "Eligibility change may affect required documents"),
    ("eligibility", "english_requirement", CriticalityLevel.MEDIUM,
     "Eligibility change may affect language requirements"),

    # eligibility_summary changes may affect interpretation
    ("eligibility_summary", "requirements", CriticalityLevel.MEDIUM,
     "Eligibility summary change may indicate requirements shift"),

    # funding changes affect coverage and requirements
    ("funding", "coverage", CriticalityLevel.CRITICAL,
     "Funding type change requires coverage re-verification"),
    ("funding", "requirements", CriticalityLevel.HIGH,
     "Funding change may affect financial requirements"),

    # coverage changes may affect requirements interpretation
    ("coverage", "requirements", CriticalityLevel.MEDIUM,
     "Coverage change may affect requirement interpretation"),

    # application_method changes affect application_link and period
    ("application_method", "application_link", CriticalityLevel.CRITICAL,
     "Application method change requires link re-verification"),
    ("application_method", "application_period", CriticalityLevel.HIGH,
     "Application method change may affect application period"),
    ("application_method", "documents", CriticalityLevel.MEDIUM,
     "Application method change may affect required documents"),

    # degree changes affect eligibility and requirements
    ("degree", "eligibility", CriticalityLevel.HIGH,
     "Degree level change may affect eligibility criteria"),
    ("degree", "requirements", CriticalityLevel.HIGH,
     "Degree level change may affect requirements"),
    ("degree", "duration", CriticalityLevel.MEDIUM,
     "Degree level change may affect program duration"),

    # country/region changes affect eligibility and context
    ("country", "eligibility", CriticalityLevel.HIGH,
     "Country change may affect eligibility criteria"),
    ("country", "requirements", CriticalityLevel.MEDIUM,
     "Country change may affect requirements"),
    ("country", "official_source", CriticalityLevel.MEDIUM,
     "Country change may affect source attribution"),

    ("region", "eligibility", CriticalityLevel.MEDIUM,
     "Region change may affect eligibility interpretation"),
    ("region", "country", CriticalityLevel.LOW,
     "Region change may affect country classification"),

    # status changes may affect lifecycle interpretation
    ("status", "next_verification_due", CriticalityLevel.MEDIUM,
     "Status change may affect verification schedule"),

    # duration changes may affect application period
    ("duration", "application_period", CriticalityLevel.MEDIUM,
     "Duration change may affect application period"),

    # requirements changes may affect documents
    ("requirements", "documents", CriticalityLevel.HIGH,
     "Requirements change may affect required documents"),

    # official_source changes may affect trust assessment
    ("official_source", "official_source_url", CriticalityLevel.MEDIUM,
     "Source change requires URL re-verification"),

    # title changes may indicate identity shift (handled separately)
    ("title", "official_source", CriticalityLevel.LOW,
     "Title change may indicate source shift"),

    # program_type changes may affect eligibility
    ("program_type", "eligibility", CriticalityLevel.MEDIUM,
     "Program type change may affect eligibility interpretation"),
    ("program_type", "requirements", CriticalityLevel.MEDIUM,
     "Program type change may affect requirements"),

    # official_source_url changes may affect related fields
    ("official_source_url", "catalogue_url", CriticalityLevel.LOW,
     "Source URL change may affect catalogue URL"),
    ("official_source_url", "official_updates_url", CriticalityLevel.LOW,
     "Source URL change may affect updates URL"),
)


def _build_adjacency_map() -> dict[str, list[DependencyEdge]]:
    """Build adjacency map from dependency rules."""
    adjacency: dict[str, list[DependencyEdge]] = {}
    for source, target, criticality, reason in _DEPENDENCY_RULES:
        edge = DependencyEdge(
            source_field=source,
            target_field=target,
            dependency_type=DependencyType.DIRECT,
            criticality=criticality,
            reason=reason,
        )
        if source not in adjacency:
            adjacency[source] = []
        adjacency[source].append(edge)
    return adjacency


# Static in-memory dependency graph
_ADJACENCY_MAP: dict[str, list[DependencyEdge]] = _build_adjacency_map()

# All fields that appear in dependency rules
_ALL_FIELDS: frozenset[str] = frozenset(
    source for source, _, _, _ in _DEPENDENCY_RULES
) | frozenset(
    target for _, target, _, _ in _DEPENDENCY_RULES
)


def get_all_tracked_fields() -> frozenset[str]:
    """Get all fields that participate in dependency tracking."""
    return _ALL_FIELDS


def get_direct_dependencies(field_name: str) -> list[DependencyEdge]:
    """Get direct dependencies for a single field."""
    return _ADJACENCY_MAP.get(field_name, [])


def get_dependency_rules() -> tuple[DependencyEdge, ...]:
    """Get all dependency rules as a flat tuple for auditing."""
    rules: list[DependencyEdge] = []
    for edges in _ADJACENCY_MAP.values():
        rules.extend(edges)
    return tuple(rules)


def get_dependency_graph_version() -> str:
    """Get the current dependency graph version."""
    return DEPENDENCY_GRAPH_VERSION


def analyze_dependencies(
    changed_fields: list[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
    known_fields: frozenset[str] | None = None,
) -> DependencyAnalysis:
    """Analyze which fields require re-verification given changed fields.

    Args:
        changed_fields: List of field names that have changed.
        max_depth: Maximum traversal depth (default 5).
        known_fields: Optional set of all known fields for NO_RECHECK detection.

    Returns:
        DependencyAnalysis with affected fields and classifications.
    """
    if not changed_fields:
        return DependencyAnalysis(
            changed_fields=(),
            affected_fields=[],
            direct_fields=[],
            transitive_fields=[],
            review_fields=[],
            no_recheck_fields=[],
        )

    changed_set = frozenset(changed_fields)
    visited: dict[str, AffectedField] = {}
    cycles_detected: list[tuple[str, ...]] = []
    max_depth_reached = False

    def _traverse(current_field: str, depth: int, path: list[str]) -> None:
        nonlocal max_depth_reached

        if depth >= max_depth:
            max_depth_reached = True
            return

        edges = _ADJACENCY_MAP.get(current_field, [])
        for edge in edges:
            target = edge.target_field
            new_path = path + [target]

            # Cycle detection
            if target in path:
                cycle = tuple(path[path.index(target):] + [target])
                if cycle not in cycles_detected:
                    cycles_detected.append(cycle)
                continue

            # Determine re-verification class
            if depth == 0:
                reclass = ReVerificationClass.DIRECT
            else:
                reclass = ReVerificationClass.TRANSITIVE

            # Check for ambiguous dependencies (same field affected by multiple paths)
            if target in visited:
                existing = visited[target]
                if existing.depth > depth:
                    # This path is shorter, update
                    visited[target] = AffectedField(
                        field_name=target,
                        re_verification_class=reclass,
                        criticality=edge.criticality,
                        depth=depth,
                        reason=edge.reason,
                        source_fields=tuple(new_path[:1]),
                        requires_escalation=edge.criticality == CriticalityLevel.CRITICAL,
                    )
                elif existing.depth == depth and existing.criticality != edge.criticality:
                    # Ambiguous criticality - escalate to review
                    visited[target] = AffectedField(
                        field_name=target,
                        re_verification_class=ReVerificationClass.REVIEW,
                        criticality=max(
                            [existing.criticality, edge.criticality],
                            key=lambda c: _criticality_order(c),
                        ),
                        depth=depth,
                        reason=f"Ambiguous dependency: conflicting criticality from {existing.source_fields} and {new_path[:1]}",
                        source_fields=existing.source_fields + tuple(new_path[:1]),
                        requires_escalation=True,
                    )
                else:
                    # Add source field to existing
                    visited[target] = AffectedField(
                        field_name=target,
                        re_verification_class=existing.re_verification_class,
                        criticality=existing.criticality,
                        depth=existing.depth,
                        reason=existing.reason,
                        source_fields=existing.source_fields + tuple(new_path[:1]),
                        requires_escalation=existing.requires_escalation or edge.criticality == CriticalityLevel.CRITICAL,
                    )
            else:
                visited[target] = AffectedField(
                    field_name=target,
                    re_verification_class=reclass,
                    criticality=edge.criticality,
                    depth=depth,
                    reason=edge.reason,
                    source_fields=tuple(new_path[:1]),
                    requires_escalation=edge.criticality == CriticalityLevel.CRITICAL,
                )

            # Continue traversal for transitive dependencies
            _traverse(target, depth + 1, new_path)

    # Traverse from each changed field
    for changed_field in sorted(changed_fields):
        _traverse(changed_field, 0, [changed_field])

    # Classify affected fields
    direct_fields: list[AffectedField] = []
    transitive_fields: list[AffectedField] = []
    review_fields: list[AffectedField] = []

    for affected in visited.values():
        if affected.re_verification_class == ReVerificationClass.REVIEW:
            review_fields.append(affected)
        elif affected.re_verification_class == ReVerificationClass.DIRECT:
            direct_fields.append(affected)
        else:
            transitive_fields.append(affected)

    # Sort by field name for determinism
    direct_fields.sort(key=lambda af: af.field_name)
    transitive_fields.sort(key=lambda af: af.field_name)
    review_fields.sort(key=lambda af: af.field_name)

    # Determine no_recheck fields
    no_recheck: list[str] = []
    if known_fields:
        affected_set = frozenset(af.field_name for af in visited.values())
        no_recheck = sorted(known_fields - affected_set - changed_set)

    all_affected = direct_fields + transitive_fields + review_fields

    return DependencyAnalysis(
        changed_fields=tuple(sorted(changed_fields)),
        affected_fields=all_affected,
        direct_fields=direct_fields,
        transitive_fields=transitive_fields,
        review_fields=review_fields,
        no_recheck_fields=no_recheck,
        max_depth_reached=max_depth_reached,
        cycles_detected=cycles_detected,
        analysis_version=DEPENDENCY_GRAPH_VERSION,
    )


def batch_analyze_dependencies(
    field_changes_list: list[list[str]],
    max_depth: int = DEFAULT_MAX_DEPTH,
    known_fields: frozenset[str] | None = None,
) -> list[DependencyAnalysis]:
    """Analyze dependencies for multiple sets of changed fields.

    Args:
        field_changes_list: List of changed field sets.
        max_depth: Maximum traversal depth.
        known_fields: Optional set of all known fields.

    Returns:
        List of DependencyAnalysis results.
    """
    return [
        analyze_dependencies(changed_fields, max_depth, known_fields)
        for changed_fields in field_changes_list
    ]


def _criticality_order(criticality: CriticalityLevel) -> int:
    """Get ordering value for criticality (higher = more critical)."""
    order = {
        CriticalityLevel.CRITICAL: 3,
        CriticalityLevel.HIGH: 2,
        CriticalityLevel.MEDIUM: 1,
        CriticalityLevel.LOW: 0,
    }
    return order.get(criticality, -1)


def get_fields_for_reverification(
    changed_fields: list[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> frozenset[str]:
    """Get the minimal set of fields requiring re-verification.

    This is a convenience function for integration with the verification pipeline.

    Args:
        changed_fields: List of field names that have changed.
        max_depth: Maximum traversal depth.

    Returns:
        Set of field names requiring re-verification.
    """
    analysis = analyze_dependencies(changed_fields, max_depth)
    return analysis.re_verification_set


def should_escalate_to_review(
    changed_fields: list[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> tuple[bool, list[str]]:
    """Check if changes should escalate to human review.

    Args:
        changed_fields: List of field names that have changed.
        max_depth: Maximum traversal depth.

    Returns:
        Tuple of (should_escalate, reasons).
    """
    analysis = analyze_dependencies(changed_fields, max_depth)

    if not analysis.requires_review:
        return False, []

    reasons: list[str] = []
    for af in analysis.review_fields:
        reasons.append(f"{af.field_name}: {af.reason}")

    return True, reasons


def get_targeted_verification_set(
    changed_fields: list[str],
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> dict[str, list[str]]:
    """Get fields grouped by verification priority.

    Returns:
        Dict with keys: critical, high, medium, low, review
        Each containing a list of field names.
    """
    analysis = analyze_dependencies(changed_fields, max_depth)

    result: dict[str, list[str]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
        "review": [],
    }

    for af in analysis.affected_fields:
        if af.re_verification_class == ReVerificationClass.REVIEW:
            result["review"].append(af.field_name)
        elif af.criticality == CriticalityLevel.CRITICAL:
            result["critical"].append(af.field_name)
        elif af.criticality == CriticalityLevel.HIGH:
            result["high"].append(af.field_name)
        elif af.criticality == CriticalityLevel.MEDIUM:
            result["medium"].append(af.field_name)
        else:
            result["low"].append(af.field_name)

    # Sort for determinism
    for key in result:
        result[key].sort()

    return result


def detect_dependency_cycles() -> list[tuple[str, ...]]:
    """Detect cycles in the dependency graph for auditing.

    Returns:
        List of detected cycles, each as a tuple of field names.
    """
    cycles: list[tuple[str, ...]] = []

    def _dfs(current: str, path: list[str], visited: set[str]) -> None:
        edges = _ADJACENCY_MAP.get(current, [])
        for edge in edges:
            target = edge.target_field
            if target in path:
                # Found a cycle
                cycle_start = path.index(target)
                cycle = tuple(path[cycle_start:] + [target])
                if cycle not in cycles:
                    cycles.append(cycle)
            elif target not in visited:
                visited.add(target)
                _dfs(target, path + [target], visited)

    for start_field in sorted(_ADJACENCY_MAP.keys()):
        _dfs(start_field, [start_field], {start_field})

    return cycles


def get_dependency_path(
    source_field: str,
    target_field: str,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> list[str] | None:
    """Find the dependency path from source to target.

    Returns:
        List of fields in the path, or None if no path exists.
    """
    if source_field == target_field:
        return [source_field]

    visited: set[str] = {source_field}
    queue: list[tuple[str, list[str]]] = [(source_field, [source_field])]

    while queue:
        current, path = queue.pop(0)
        if len(path) > max_depth:
            continue

        edges = _ADJACENCY_MAP.get(current, [])
        for edge in edges:
            target = edge.target_field
            if target == target_field:
                return path + [target]
            if target not in visited:
                visited.add(target)
                queue.append((target, path + [target]))

    return None
