"""Counterfactual counting and zero-result intelligence.

"What happens if I relax this?" is a real question with a real answer, and the
answer here is arithmetic: apply one stated change to the same candidate universe,
re-run the same filter logic, and report the number that comes out. Nothing is
predicted, estimated or implied.

Three rules are absolute.

**Exactly one dimension changes per question.** A "what if I moved to Germany and
also looked at part-time and dropped the funding requirement" answer is not a
counterfactual, it is a different search, and reporting it as one hides which
change did the work. Every result here names the single dimension it altered.

**The user's state is never mutated.** Every counterfactual is computed on a copy.
A reader who opens a counterfactual and closes it must find their filters exactly
as they left them, and the test suite asserts it.

**Nothing is offered unless it was measured.** A zero-result alternative is only
published when applying the change actually produces results, and the count beside
it is the count that was produced - not a projection of what might happen.

On terminology: this is deterministic recomputation, not causal inference. The
delta is the difference between two counts of one universe under two stated
conditions. It is never a causal effect, a treatment effect, or a probability of
getting in, and :class:`CounterfactualCounting` carries that statement in its own
payload so it cannot be lost in transit.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Sequence

from .facets import DIMENSION_FIELDS, FilterState
from .types import (
    CountAlternative,
    CounterfactualCounting,
    CountFilter,
    CountUniverse,
    ProvenanceKind,
)


#: The dimensions a reader may change one at a time. Each maps to a filter
#: dimension the product already evaluates, so no counterfactual can be based on a
#: predicate the catalogue cannot apply.
SUPPORTED_INTERVENTIONS: tuple[str, ...] = (
    CountFilter.COUNTRY.value,
    CountFilter.REGION.value,
    CountFilter.DEGREE.value,
    CountFilter.FIELD.value,
    CountFilter.FUNDING.value,
    CountFilter.ELIGIBILITY.value,
    CountFilter.FIT.value,
    CountFilter.CONFIDENCE.value,
    CountFilter.COVERAGE.value,
    CountFilter.READINESS.value,
    CountFilter.DEADLINE.value,
)

#: Human wording per dimension, so the reader sees "Remove \"Country\"" rather than
#: a field name.
DIMENSION_LABELS: dict[str, str] = {
    CountFilter.COUNTRY.value: "Country",
    CountFilter.REGION.value: "Region",
    CountFilter.DEGREE.value: "Degree",
    CountFilter.FIELD.value: "Field",
    CountFilter.FUNDING.value: "Funding",
    CountFilter.ELIGIBILITY.value: "Eligibility",
    CountFilter.FIT.value: "Fit",
    CountFilter.CONFIDENCE.value: "Confidence",
    CountFilter.COVERAGE.value: "Coverage",
    CountFilter.READINESS.value: "Readiness",
    CountFilter.DEADLINE.value: "Deadline",
}


# ---------------------------------------------------------------------------
# Filter counterfactuals
# ---------------------------------------------------------------------------


def _eligible_count(records: Sequence[object]) -> int:
    return sum(
        1
        for record in records
        if getattr(record, "eligibility", None) is not None
        and getattr(record.eligibility, "value", record.eligibility) == "ELIGIBLE"
    )


def counterfactual(
    records: Sequence[object],
    filter_state: FilterState,
    dimension: str,
    proposed_value: str | None,
    *,
    metric: str = "results",
) -> CounterfactualCounting:
    """Recompute one count under one changed filter dimension.

    ``proposed_value`` of ``None`` removes the dimension's constraint entirely.
    Exactly one dimension differs between the two states; every other active
    predicate is retained, so the delta is attributable to the stated change alone.
    """
    if dimension not in SUPPORTED_INTERVENTIONS:
        raise ValueError(
            f"{dimension!r} is not a supported counterfactual dimension; "
            f"supported: {list(SUPPORTED_INTERVENTIONS)}"
        )

    baseline_state = filter_state
    baseline_records = filter_state.filter(records)
    baseline_count = (
        len(baseline_records) if metric == "results" else _eligible_count(baseline_records)
    )

    # A new state, never a mutation of the caller's.
    counterfactual_state = _with_dimension(filter_state, dimension, proposed_value)
    counterfactual_records = counterfactual_state.filter(records)
    counterfactual_count = (
        len(counterfactual_records) if metric == "results" else _eligible_count(counterfactual_records)
    )

    return CounterfactualCounting(
        metric=metric,
        baseline_count=baseline_count,
        counterfactual_count=counterfactual_count,
        delta=counterfactual_count - baseline_count,
        changed_dimension=dimension,
        baseline_state=baseline_state.active(),
        counterfactual_state=counterfactual_state.active(),
        value_kind=ProvenanceKind.SIMULATED,
    )


def _with_dimension(
    state: FilterState, dimension: str, proposed_value: str | None
) -> FilterState:
    """A copy of ``state`` with one dimension replaced.

    ``None`` clears a single-valued dimension; for a multi-valued one it clears the
    whole dimension, because "remove the country filter" means remove all of them.
    """
    if dimension == CountFilter.REGION.value:
        return replace(state, region=proposed_value)

    field_name = DIMENSION_FIELDS[dimension]
    if proposed_value is None:
        return replace(state, **{field_name: ()})
    return replace(state, **{field_name: (proposed_value,)})


# ---------------------------------------------------------------------------
# Zero-result intelligence
# ---------------------------------------------------------------------------

#: How many alternatives to publish. Enough to show a way out, few enough that the
#: list is a decision aid rather than a menu of every combination.
MAX_ALTERNATIVES = 6


def zero_result_alternatives(
    records: Sequence[object],
    filter_state: FilterState,
    *,
    candidate_dimensions: Sequence[str] | None = None,
    limit: int = MAX_ALTERNATIVES,
) -> list[CountAlternative]:
    """Deterministic one-change ways out of an empty result set.

    Each alternative removes one active dimension entirely, keeping every other
    predicate. Alternatives that produce no results are discarded rather than
    offered: showing a reader "Remove Degree -> 0" is noise dressed as a
    suggestion.

    Ordered by resulting count descending, then by dimension name, so the widest
    way out is first and two runs never differ on a tie.
    """
    dimensions = (
        tuple(candidate_dimensions)
        if candidate_dimensions is not None
        else tuple(
            dimension for dimension in DIMENSION_FIELDS if filter_state.predicate_for(dimension)
        )
    )

    alternatives: list[CountAlternative] = []
    for dimension in dimensions:
        removed = _active_label(filter_state, dimension)
        relaxed = _with_dimension(filter_state, dimension, None)
        produced = relaxed.filter(records)
        if not produced:
            continue

        alternatives.append(
            CountAlternative(
                changed_dimension=dimension,
                change_label=f"Remove \"{DIMENSION_LABELS.get(dimension, dimension)}\"",
                proposed_value=None,
                removed_value=removed,
                result_count=len(produced),
                is_removal=True,
            )
        )

    return sorted(
        alternatives, key=lambda item: (-item.result_count, item.changed_dimension)
    )[:limit]


def _active_label(state: FilterState, dimension: str) -> str | None:
    from .facets import active_values

    values = active_values(state, dimension)
    if not values:
        return None
    return ", ".join(values)


# ---------------------------------------------------------------------------
# Profile counterfactuals
# ---------------------------------------------------------------------------


def profile_counterfactual(
    *,
    metric_name: str,
    baseline_count: int,
    counterfactual_count: int,
    changed_dimension: str,
    baseline_state: dict[str, list[str]],
    counterfactual_state: dict[str, list[str]],
) -> CounterfactualCounting:
    """Wrap a profile-level recomputation in the counterfactual contract.

    The caller supplies both counts because recomputing a profile means re-running
    the Match engine, which this module must not do: it has no session, no facts
    loader and no business touching the scoring path. The separation is deliberate -
    the counting layer measures, the engine decides.
    """
    return CounterfactualCounting(
        metric=metric_name,
        baseline_count=baseline_count,
        counterfactual_count=counterfactual_count,
        delta=counterfactual_count - baseline_count,
        changed_dimension=changed_dimension,
        baseline_state=baseline_state,
        counterfactual_state=counterfactual_state,
        value_kind=ProvenanceKind.SIMULATED,
    )


def related_field_alternatives(
    records: Sequence[object],
    filter_state: FilterState,
    resolver: Callable[[str], tuple[str, ...]],
    *,
    limit: int = MAX_ALTERNATIVES,
) -> list[CountAlternative]:
    """Zero-result help for "include a related field".

    Only offered where the curated taxonomy declares the fields related. The
    relationship comes from the taxonomy's own resolver, never from string
    similarity, so a proposed field is one the product has a documented opinion
    about rather than one that merely looks similar.
    """
    active = filter_state.active().get(CountFilter.FIELD.value, [])
    if not active:
        return []

    alternatives: list[CountAlternative] = []
    for current in active:
        for related in resolver(current):
            proposed = tuple(dict.fromkeys(tuple(active) + (related,)))
            state = replace(filter_state, field=proposed)
            produced = state.filter(records)
            if not produced:
                continue
            alternatives.append(
                CountAlternative(
                    changed_dimension=CountFilter.FIELD.value,
                    change_label=f"Include related field \"{related.replace('_', ' ').title()}\"",
                    proposed_value=related,
                    removed_value=current,
                    result_count=len(produced),
                    is_removal=False,
                )
            )

    return sorted(
        alternatives, key=lambda item: (-item.result_count, item.proposed_value or "")
    )[:limit]


__all__ = [
    "DIMENSION_LABELS",
    "MAX_ALTERNATIVES",
    "SUPPORTED_INTERVENTIONS",
    "counterfactual",
    "profile_counterfactual",
    "related_field_alternatives",
    "zero_result_alternatives",
]