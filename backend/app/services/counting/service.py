"""Count intelligence orchestration.

This is the impure boundary: it holds the session, resolves ``as_of``, and assembles
the single response that carries results, summary, facets, integrity and provenance
together.

The assembly order is fixed and matters:

1. Resolve the candidate universe once. For Match counts that means running the
   engine exactly once and keeping *every* scored result - never just the page that
   was returned, which is what previously made summary counts silently change
   identity the moment a request was truncated.
2. Count every partition over that one set.
3. Reconcile, and refuse to publish a contradicting set.
4. Build facets with self-exclusion over the filtered set.
5. Attach provenance, explanation and integrity.

One response, one pass, one candidate set. Every partition, facet, distribution and
relationship in the response is derived from the list held in memory, so there is
no per-facet query explosion and no way for two sections to disagree about which
records they are describing.

This module never scores. Eligibility, fit, confidence, coverage and readiness are
the Match engine's responsibility and arrive here as finished facts.
"""

from __future__ import annotations

from datetime import date
from typing import Sequence

from sqlalchemy.orm import Session

from ..matching.config import FIT_WEIGHTS
from ..matching.engine import rank_results, score_record
from ..matching.normalize import normalise_profile
from ..matching.repository import load_candidates, to_facts
from ..matching.types import MatchProfileRequest, MatchResult
from .anomalies import (
    ANOMALY_DETECTION_VERSION,
    detect_count_anomalies,
    detect_facet_imbalance,
    detect_impossible_buckets,
    integrity_report,
    worst_severity,
)
from .catalogue import build_catalogue_partitions, catalogue_counts
from .contract import COUNT_CONTRACT_VERSION, contract_snapshot
from .core import assert_integrity, count_all_partitions, distribution, integrity
from .counterfactual import (
    counterfactual as filter_counterfactual,
    related_field_alternatives,
    zero_result_alternatives,
)
from .facets import (
    DIMENSION_ORDER,
    SELF_EXCLUSION_SEMANTICS,
    FACET_FAMILIES,
    FACET_FAMILIES_BY_NAME,
    FilterState,
    active_values,
    assert_facets_reconciled,
    build_facets,
    facet_candidate_sets,
    known_regions,
)
from .incremental import apply_plan, plan_increments
from .provenance import explain_count, filter_conditions, provenance, provenance_summary
from .relationships import relationship_counts, related_fields, verified_graph_counts
from .temporal import count_trend, current_snapshot, snapshot_coverage
from .types import CountBasis, CountUniverse, ProvenanceKind


#: Every optional section the report can carry. Named so a caller asks for what it
#: needs rather than receiving everything and paying for all of it.
CAPABILITIES: tuple[str, ...] = (
    "summary",
    "facets",
    "explain",
    "zero_result",
    "counterfactual",
    "catalogue",
    "snapshot",
    "trends",
    "relationships",
    "incremental",
    "distributions",
    "integrity",
)


def analysed_candidates(
    session: Session,
    request: MatchProfileRequest,
    *,
    as_of: date,
    hard_limit: int | None = None,
) -> list[MatchResult]:
    """Run the engine once and keep everything it scored.

    The engine is scored exactly once per request; nothing downstream re-scores.
    ``include_ineligible=False`` removes records from the analysed universe rather
    than scoring and hiding them, so the eligibility states still sum to the total.
    """
    from ..matching.config import MATCH_CANDIDATE_HARD_LIMIT

    profile = normalise_profile(request)
    rows = load_candidates(
        session,
        country_filter=profile.country_filter,
        hard_limit=hard_limit or MATCH_CANDIDATE_HARD_LIMIT,
    )
    results = [score_record(profile, to_facts(row), as_of) for row in rows]

    if not profile.include_ineligible:
        results = [item for item in results if item.eligibility.value != "INELIGIBLE"]

    return rank_results(results)


def count_intelligence(
    session: Session,
    request: MatchProfileRequest,
    *,
    as_of: date,
    filters: FilterState | None = None,
    capabilities: Sequence[str] = ("summary", "facets", "integrity"),
    history: Sequence[tuple[str, object, int]] = (),
) -> dict:
    """The count intelligence report.

    ``history`` is a sequence of ``(metric, moment, value)`` observations. They are
    only ever supplied from real stored evidence; a caller with none passes an empty
    sequence and the report says so rather than inferring a baseline.
    """
    requested = set(capabilities) or {"summary", "facets", "integrity"}

    results = analysed_candidates(session, request, as_of=as_of)
    total = len(results)
    scored = sum(1 for item in results if item.fit_score is not None)

    partitions = count_all_partitions(results, scored=scored)

    # A missing baseline is a limitation of the evidence, never a defect in the
    # counts, so it is a WARNING rather than a FAIL: the numbers are sound and
    # incomplete, and the interface says which.
    warnings: list[str] = []
    if len(history) < 3:
        warnings.append(
            "No historical baseline is available, so spike and drop detection could "
            "not be evaluated. The counts themselves are unaffected."
        )

    verdict = integrity(partitions, total=total, scored=scored, warnings=warnings)
    assert_integrity(verdict)

    state = filters or FilterState()
    filtered = state.filter(results)
    facets = build_facets(results, state) if "facets" in requested else {}
    facet_sets = facet_candidate_sets(results, state) if facets else {}
    if facets:
        assert_facets_reconciled(facets, facet_sets)

    anomalies = detect_impossible_buckets(partitions)
    for metric, observations in _history_by_metric(history):
        anomalies.extend(
            detect_count_anomalies(
                _metric_value(partitions, metric),
                [value for _, value in observations],
                metric=metric,
            )
        )
    for name, buckets in facets.items():
        anomalies.extend(
            detect_facet_imbalance(
                buckets,
                name=name,
                universe_size=len(filtered) or total or 1,
            )
        )

    block = provenance(
        universe=CountUniverse.MATCH_ANALYSED,
        basis=CountBasis.COMPLETE,
        filter_state=state.active(),
        as_of=as_of.isoformat(),
        as_of_dependency=True,
        engine_dependency=("confidence", "eligibility", "metrics", "readiness"),
        version_dependency=("scoring_config_version", "deadline_semantics_version"),
        value_kinds={
            "summary": ProvenanceKind.OBSERVED,
            "facets": ProvenanceKind.OBSERVED,
            "distributions": ProvenanceKind.DERIVED,
        },
    )

    report: dict = {
        "count_contract_version": COUNT_CONTRACT_VERSION,
        "anomaly_detection_version": ANOMALY_DETECTION_VERSION,
        "universe": CountUniverse.MATCH_ANALYSED.value,
        "as_of": as_of.isoformat(),
        "capabilities": sorted(requested),
        "total_candidates": total,
        "scored_count": scored,
        "results": {
            "matched": len(filtered),
            "filter_state": state.active(),
            "fingerprint": state.fingerprint(),
        },
        "summary": _partition_map(partitions),
        "partitions": [partition.model_dump() for partition in partitions],
        "integrity": integrity_report(verdict),
        "provenance": provenance_summary(block),
        "weights": dict(FIT_WEIGHTS),
        "versions": contract_snapshot(),
        "anomalies": [anomaly.model_dump() for anomaly in anomalies],
    }

    if "facets" in requested:
        report["facets"] = {
            "count_basis": CountUniverse.MATCH_RETURNED_PAGE.value,
            "self_exclusion": SELF_EXCLUSION_SEMANTICS,
            "facet_sets": {name: len(records) for name, records in facet_sets.items()},
            "families": {
                name: [bucket.model_dump() for bucket in buckets]
                for name, buckets in facets.items()
            },
            "known_regions": list(known_regions()),
        }

    if "distributions" in requested:
        report["distributions"] = _distributions(results)

    if "explain" in requested:
        report["explanations"] = _explanations(total, filtered, state)

    if "zero_result" in requested or not filtered:
        report["zero_result"] = {
            "status": "EMPTY" if not filtered else "NON_EMPTY",
            "alternatives": [
                alternative.model_dump()
                for alternative in _alternatives(results, state)
            ],
        }

    if "counterfactual" in requested:
        report["counterfactuals"] = _counterfactuals(results, state)

    if "catalogue" in requested:
        counts = catalogue_counts(session)
        report["catalogue"] = {
            "universe": CountUniverse.CATALOGUE.value,
            "counts": counts,
            "partitions": [
                partition.model_dump() for partition in build_catalogue_partitions(counts)
            ],
        }

    if "snapshot" in requested:
        report["snapshot"] = current_snapshot(
            as_of, summary=_partition_map(partitions)
        ).model_dump()
        report["snapshot_coverage"] = snapshot_coverage(session)

    if "trends" in requested:
        report["trends"] = {
            metric: count_trend(
                [(moment, value) for _, moment, value in observations], metric=metric
            ).model_dump()
            for metric, observations in _history_by_metric(history)
        }

    if "relationships" in requested:
        graph_counts, density = verified_graph_counts(session)
        report["relationships"] = {
            "published_field_matches": [
                item.model_dump() for item in relationship_counts(results)
            ],
            "verified_graph_edges": [item.model_dump() for item in graph_counts],
            "graph_density": density,
        }

    if "incremental" in requested:
        report["incremental"] = _incremental_preview()

    return report


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


def _partition_map(partitions) -> dict[str, int]:
    """Flat bucket counts, for readers that want numbers without the structure."""
    return {
        f"{partition.name}.{bucket.key}": bucket.count
        for partition in partitions
        for bucket in partition.buckets
    }


def _metric_value(partitions, metric: str) -> int:
    partition_name, _, bucket = metric.partition(".")
    for partition in partitions:
        if partition.name != partition_name:
            continue
        for candidate in partition.buckets:
            if candidate.key == bucket:
                return candidate.count
    return 0


def _history_by_metric(history: Sequence[tuple[str, object, int]]):
    grouped: dict[str, list] = {}
    for metric, moment, value in history:
        grouped.setdefault(metric, []).append((moment, value))
    return sorted(grouped.items())


def _distributions(results: Sequence[MatchResult]) -> list[dict]:
    """Safe aggregates, each with its sample size and exclusion count.

    Never combined into one figure and never labelled as a probability. "Average
    fit" is a statement about the scores in this candidate set, and the sample size
    is what makes it interpretable.
    """
    published: list[dict] = []

    def add(dimension: str, values) -> None:
        published.append(
            distribution(
                list(values),
                dimension=dimension,
                universe=CountUniverse.MATCH_ANALYSED,
            ).model_dump()
        )

    add("fit_score", [item.fit_score for item in results])
    add("confidence", [item.confidence_score for item in results])
    add("coverage", [item.data_coverage for item in results])
    add(
        "readiness",
        [
            item.readiness.score if item.readiness is not None else None
            for item in results
        ],
    )
    return published


def _explanations(total: int, filtered: Sequence[MatchResult], state: FilterState) -> dict:
    conditions = filter_conditions(state.active())
    eligible = sum(
        1 for item in filtered if item.eligibility.value == "ELIGIBLE"
    )
    return {
        "total_candidates": explain_count(
            total,
            universe=CountUniverse.MATCH_ANALYSED,
            metric_label="scholarships analysed",
        ).model_dump(),
        "matched": explain_count(
            len(filtered),
            universe=CountUniverse.MATCH_ANALYSED,
            conditions=conditions,
            metric_label="scholarships matching your filters",
        ).model_dump(),
        "eligible": explain_count(
            eligible,
            universe=CountUniverse.MATCH_ANALYSED,
            conditions=[*conditions, ("eligibility", "=", '"ELIGIBLE"')],
            metric_label="eligible scholarships",
        ).model_dump(),
    }


def _alternatives(results, state: FilterState):
    """Zero-result help: dimension removals first, then curated related fields.

    Only changes that actually produce results are offered. A reader is never shown
    "Remove Degree → 0".
    """
    alternatives = zero_result_alternatives(results, state)
    if alternatives:
        return alternatives
    return related_field_alternatives(results, state, related_fields)


def _counterfactuals(results, state: FilterState) -> dict:
    """One controlled change per active dimension, each reported separately.

    Only dimensions the reader actually constrained produce a counterfactual: there
    is nothing to change about a filter that was never applied.
    """
    interventions = []
    for dimension in DIMENSION_ORDER:
        if state.predicate_for(dimension) is None:
            continue
        values = active_values(state, dimension)
        if not values:
            continue
        interventions.append(
            filter_counterfactual(
                results, state, dimension, None, metric="results"
            ).model_dump()
        )
    return {
        "interventions": interventions,
        "disclaimer": (
            "Each entry changes exactly one dimension and recomputes over the same "
            "candidate universe. A delta is a difference between two counts, not a "
            "causal effect and not a probability."
        ),
    }


def _incremental_preview() -> dict:
    """Show the strategy a change *would* take, without persisting anything.

    A single-record change to a simple dimension is the only case that stays
    incremental. Everything else recomputes, and says which partitions and why.
    """
    plan = plan_increments(
        [("CHANGED_SCHOLARSHIP", 0, "illustrative single-record change")],
        partitions=["eligibility", "scored", "fit_tier"],
    )
    return apply_plan(
        plan,
        recomputed_summary={"note": "Preview only. No counters are persisted."},
    ).model_dump()


__all__ = [
    "CAPABILITIES",
    "analysed_candidates",
    "count_intelligence",
]