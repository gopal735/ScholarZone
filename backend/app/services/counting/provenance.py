"""Provenance and count explanation.

Every published number carries enough metadata to be recomputed rather than
trusted, and every count can be explained in a sentence a person can check against
the response itself.

This is the part of the layer that makes it auditable rather than merely correct.
A number that is right but unexplainable is indistinguishable from a number that is
wrong by coincidence, and a reader who cannot ask "why is this 213?" has no way to
tell which one they are looking at.

Provenance names four things:

* which **universe** the count describes,
* which **predicates** were active,
* which **versions** produced it, including the count contract's own,
* how each number was obtained - ``OBSERVED``, ``DERIVED``, ``SIMULATED``,
  ``HISTORICAL`` or ``UNAVAILABLE``.

The value kinds are the important part. A catalogue count read from stored rows and
a counterfactual recomputed under a hypothetical change are both integers, and
adding them together would produce a number meaning nothing. They are therefore
never published in the same total without being labelled.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from ..deadline_semantics import DEADLINE_PRECISION_VALUES
from ..matching.config import (
    DEADLINE_SEMANTICS_VERSION,
    FIELD_TAXONOMY_VERSION,
    FIT_ENGINE_VERSION,
    SCORING_CONFIG_VERSION,
)
from .contract import COUNT_CONTRACT_VERSION
from .types import (
    CountBasis,
    CountExplanation,
    CountExplanationLine,
    CountProvenance,
    CountUniverse,
    ProvenanceKind,
)


#: The version identifiers every provenance block carries. Declared once so the
#: block cannot accidentally omit the dependency that actually matters.
VERSION_KEYS: tuple[str, ...] = (
    "count_contract_version",
    "engine_version",
    "scoring_config_version",
    "field_taxonomy_version",
    "deadline_semantics_version",
)


def match_versions() -> dict[str, str]:
    return {
        "engine_version": FIT_ENGINE_VERSION,
        "scoring_config_version": SCORING_CONFIG_VERSION,
        "field_taxonomy_version": FIELD_TAXONOMY_VERSION,
        "deadline_semantics_version": DEADLINE_SEMANTICS_VERSION,
    }


def provenance(
    *,
    universe: CountUniverse,
    basis: CountBasis,
    filter_state: Mapping[str, Sequence[str]] | None = None,
    as_of: str | None = None,
    as_of_dependency: bool = False,
    engine_dependency: Sequence[str] = (),
    version_dependency: Sequence[str] = (),
    value_kinds: Mapping[str, ProvenanceKind] | None = None,
) -> CountProvenance:
    """Build the provenance block for one set of counts.

    ``as_of`` is only populated where the count genuinely depends on the date. A
    catalogue count is not a function of today, and stamping today's date on it
    would imply a history it does not have.
    """
    return CountProvenance(
        count_basis=basis,
        universe=universe,
        filter_state={key: list(values) for key, values in (filter_state or {}).items()},
        as_of=as_of if as_of_dependency else None,
        as_of_dependency=as_of_dependency,
        count_contract_version=COUNT_CONTRACT_VERSION,
        depends_on=tuple(sorted({*engine_dependency, *version_dependency})),
        value_kinds=dict(value_kinds or {}),
        **match_versions(),
    )


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------

_UNIVERSE_PHRASES: dict[str, str] = {
    CountUniverse.CATALOGUE.value: "the public scholarship catalogue",
    CountUniverse.SEARCH_FILTER.value: "catalogue scholarships matching the active search",
    CountUniverse.MATCH_ANALYSED.value: "analysed scholarships",
    CountUniverse.MATCH_RETURNED_PAGE.value: "the returned results page",
}


def explain_count(
    count: int,
    *,
    universe: CountUniverse,
    conditions: Sequence[tuple[str, str, str]] = (),
    metric_label: str = "",
) -> CountExplanation:
    """Explain one count in both readable and reproducible form.

    ``conditions`` are ``(dimension, operator, value)`` triples and are rendered as
    ordered clauses, so the sentence and the predicate list are the same statement
    in two languages. The human-readable form is assembled from the same list, so
    the two can never disagree.
    """
    clauses = [
        CountExplanationLine(dimension=dimension, operator=operator, value=value)
        for dimension, operator, value in conditions
    ]

    noun = metric_label or "scholarships"
    if count == 1:
        noun = noun.rstrip("s") if noun.endswith("s") and not noun.endswith("ss") else noun

    phrase = _UNIVERSE_PHRASES.get(universe.value, universe.value)
    clauses_text = "".join(f" AND {clause.value}" for clause in clauses)
    readable = f"{count} {noun} in {phrase}{clauses_text}."

    return CountExplanation(count=count, human_readable=readable, clauses=clauses)


def filter_conditions(
    filter_state: Mapping[str, Sequence[str]]
) -> list[tuple[str, str, str]]:
    """Turn a filter state into explanation clauses, in published dimension order."""
    from .facets import DIMENSION_ORDER

    conditions: list[tuple[str, str, str]] = []
    for dimension in DIMENSION_ORDER:
        values = filter_state.get(dimension)
        if not values:
            continue
        rendered = " or ".join(f'"{value}"' for value in values)
        conditions.append((dimension, "=", rendered))
    return conditions


def provenance_summary(block: CountProvenance) -> dict:
    """A compact, publishable view of the provenance block."""
    return {
        "count_basis": block.count_basis.value,
        "universe": block.universe.value,
        "filter_state": dict(block.filter_state),
        "as_of": block.as_of,
        "as_of_dependency": block.as_of_dependency,
        "count_contract_version": block.count_contract_version,
        "engine_version": block.engine_version,
        "scoring_config_version": block.scoring_config_version,
        "field_taxonomy_version": block.field_taxonomy_version,
        "deadline_semantics_version": block.deadline_semantics_version,
        "depends_on": list(block.depends_on),
        "value_kinds": {key: kind.value for key, kind in block.value_kinds.items()},
        "deadline_precision_vocabulary": sorted(DEADLINE_PRECISION_VALUES),
    }


__all__ = [
    "VERSION_KEYS",
    "explain_count",
    "filter_conditions",
    "match_versions",
    "provenance",
    "provenance_summary",
]