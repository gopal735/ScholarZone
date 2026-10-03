"""Facets, filter semantics and self-exclusion.

A facet is a question asked of a candidate set: "how many of these are German?".
Three things make those numbers trustworthy, and all three live here.

**One universe per question.** Every facet in a response is built from the same
candidate set, so a count is never stale relative to the list it filters. A reader
who sees "Germany (5)" and then sees five cards has not been misled.

**Self-exclusion, stated plainly.** When the reader has Germany selected, the
country facet still has to be able to say "France (3)" - otherwise the alternative
countries become invisible the moment you commit to one, which is exactly when you
need them. So each facet is computed with its own dimension's predicate removed
and every other active predicate retained. That is the standard behaviour, and it
is declared in :data:`SELF_EXCLUSION_SEMANTICS` rather than left as an
implementation detail a reader has to guess at.

**No truncation and no invented values.** A country in the catalogue is always
offerable. A region is offered only where a curated region mapping places the
country, never inferred from prose. A field is offered only where the taxonomy
resolved one, never guessed from a title.

Labels are never derived from keys by title-casing. A country and a degree are
already written for a reader, and restyling text ScholarZone did not author is how
"PhD" becomes "Phd".
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Iterable, Mapping, Sequence

from .contract import PARTITIONS_BY_NAME
from .core import _predicates_for
from .types import CountBucket, CountFilter, CountUniverse


#: Published verbatim with every facet response, because the semantics are part of
#: the contract rather than an implementation detail.
SELF_EXCLUSION_SEMANTICS = (
    "Each facet counts records matching every active filter except its own "
    "dimension. A facet therefore still offers alternative values while one of its "
    "own values is selected. count_basis names the set each count describes."
)


#: Dimension key -> the ``FilterState`` field that holds it.
#:
#: The dimension keys are the published vocabulary (``COUNTRY``); the fields are
#: Python names (``countries``). Conflating the two is not a style preference - it
#: silently produces a filter state that reports no active predicates at all,
#: which would make every facet count describe the unfiltered catalogue.
DIMENSION_FIELDS: dict[str, str] = {
    CountFilter.COUNTRY.value: "countries",
    CountFilter.REGION.value: "region",
    CountFilter.DEGREE.value: "degree",
    CountFilter.FIELD.value: "field",
    CountFilter.FUNDING.value: "funding",
    CountFilter.ELIGIBILITY.value: "eligibility",
    CountFilter.FIT.value: "fit",
    CountFilter.CONFIDENCE.value: "confidence",
    CountFilter.COVERAGE.value: "coverage",
    CountFilter.READINESS.value: "readiness",
    CountFilter.DEADLINE.value: "deadline",
}


@dataclass(frozen=True)
class FilterState:
    """The active predicates.

    A dimension accepts several values as an OR; dimensions are combined as an AND.
    ``None`` and an empty tuple both mean "not constrained". Nothing here is
    presentation state: this object *is* the filter, and two equal states produce
    equal counts.
    """

    countries: tuple[str, ...] = ()
    region: str | None = None
    degree: tuple[str, ...] = ()
    field: tuple[str, ...] = ()
    funding: tuple[str, ...] = ()
    eligibility: tuple[str, ...] = ()
    fit: tuple[str, ...] = ()
    confidence: tuple[str, ...] = ()
    coverage: tuple[str, ...] = ()
    readiness: tuple[str, ...] = ()
    deadline: tuple[str, ...] = ()

    # -- predicates ---------------------------------------------------------

    def _region_predicate(self) -> Callable[[object], bool] | None:
        if not self.region:
            return None
        members = region_members(self.region)
        return lambda item: item.country in members

    def predicate_for(self, dimension: str) -> Callable[[object], bool] | None:
        """The predicate for one dimension, or ``None`` when unconstrained."""
        match dimension:
            case CountFilter.COUNTRY:
                values = self.countries
                if not values:
                    return None
                return lambda item: item.country in values
            case CountFilter.REGION:
                return self._region_predicate()
            case CountFilter.DEGREE:
                values = self.degree
                if not values:
                    return None
                return lambda item: item.degree_levels in values
            case CountFilter.FIELD:
                values = self.field
                if not values:
                    return None
                return lambda item: item.field in values
            case CountFilter.FUNDING:
                return _partition_predicate("funding", self.funding)
            case CountFilter.ELIGIBILITY:
                return _partition_predicate("eligibility", self.eligibility)
            case CountFilter.FIT:
                return _partition_predicate("fit_tier", self.fit)
            case CountFilter.CONFIDENCE:
                return _partition_predicate("confidence", self.confidence)
            case CountFilter.COVERAGE:
                return _partition_predicate("coverage", self.coverage)
            case CountFilter.READINESS:
                return _partition_predicate("readiness", self.readiness)
            case CountFilter.DEADLINE:
                return _partition_predicate("deadline", self.deadline)
        return None

    # -- composition --------------------------------------------------------

    def predicates(self) -> tuple[Callable[[object], bool], ...]:
        """Every active dimension, in the published dimension order."""
        resolved = []
        for dimension in DIMENSION_ORDER:
            predicate = self.predicate_for(dimension)
            if predicate is not None:
                resolved.append(predicate)
        return tuple(resolved)

    def matches(self, record: object) -> bool:
        return all(predicate(record) for predicate in self.predicates())

    def filter(self, records: Sequence[object]) -> list[object]:
        """Apply every predicate. Order-preserving, so ranking survives."""
        predicates = self.predicates()
        if not predicates:
            return list(records)
        return [record for record in records if all(p(record) for p in predicates)]

    # -- self-exclusion -----------------------------------------------------

    def without(self, dimension: str) -> "FilterState":
        """This filter with one dimension removed.

        Used to build the facet for ``dimension``: the alternatives a reader needs
        to see are exactly the ones this dimension's own predicate was hiding.
        """
        return replace(self, **{DIMENSION_FIELDS[dimension]: _EMPTY[dimension]})

    # -- provenance ---------------------------------------------------------

    def active(self) -> dict[str, list[str]]:
        """The active predicates, for provenance and for a reproducible count."""
        state: dict[str, list[str]] = {}
        for dimension in DIMENSION_ORDER:
            predicate = self.predicate_for(dimension)
            if predicate is None:
                continue
            values = active_values(self, dimension)
            if values:
                state[dimension] = values
        return state

    def is_empty(self) -> bool:
        return not any(self.predicate_for(dimension) for dimension in DIMENSION_ORDER)

    def fingerprint(self) -> str:
        """A stable identity for this filter state.

        Used by reset integrity: the same fingerprint must produce the same counts,
        and two different filter states must not share one.

        Values are sorted as well as dimensions. Two states that selected Germany
        and France in different orders constrain exactly the same records, so they
        must share a fingerprint - otherwise a reset could be judged a different
        request from the one it restored.
        """
        parts = [
            f"{dimension}={'|'.join(sorted(values))}"
            for dimension, values in sorted(self.active().items())
        ]
        return ";".join(parts) if parts else "NONE"


DIMENSION_ORDER: tuple[str, ...] = tuple(dimension.value for dimension in CountFilter)

_EMPTY: dict[str, object] = {
    CountFilter.COUNTRY.value: (),
    CountFilter.REGION.value: None,
    CountFilter.DEGREE.value: (),
    CountFilter.FIELD.value: (),
    CountFilter.FUNDING.value: (),
    CountFilter.ELIGIBILITY.value: (),
    CountFilter.FIT.value: (),
    CountFilter.CONFIDENCE.value: (),
    CountFilter.COVERAGE.value: (),
    CountFilter.READINESS.value: (),
    CountFilter.DEADLINE.value: (),
}


def active_values(state: FilterState, dimension: str) -> list[str]:
    """The values currently selected on one dimension.

    Public because provenance and counterfactual explanations both need to name what
    was selected, and re-deriving it from the field mapping in two places is how
    they drift.
    """
    value = getattr(state, DIMENSION_FIELDS[dimension], None)
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _partition_predicate(
    partition: str, values: tuple[str, ...]
) -> Callable[[object], bool] | None:
    """Build a predicate from a contract partition's published buckets."""
    if not values:
        return None
    from .core import partition_of

    spec = PARTITIONS_BY_NAME[partition]
    selected = set(values)

    def predicate(item: object) -> bool:
        key = partition_of(item, spec)
        return key is not None and key in selected

    return predicate


# ---------------------------------------------------------------------------
# Canonical region mapping
# ---------------------------------------------------------------------------


def region_members(region: str) -> frozenset[str]:
    """The curated member countries of a named region.

    Delegates to the parser's canonical region table, which is the only region
    mapping this product has. A region is never inferred from prose: if a country
    is not in a curated region, that country has no region facet value.
    """
    from ..matching.nlp import REGION_MEMBERS

    return frozenset(REGION_MEMBERS.get(region.casefold().strip(), ()))


def known_regions() -> tuple[str, ...]:
    from ..matching.nlp import REGION_MEMBERS

    return tuple(sorted(REGION_MEMBERS))


def region_for_country(country: str) -> str | None:
    """The one curated region a country belongs to, or ``None``.

    ``None`` when the country appears in no curated region, and also when the
    curated regions disagree about it. A country in two regions has no single
    region facet value, and picking either one would be an invention.
    """
    matches = [
        region
        for region in known_regions()
        if country in region_members(region)
    ]
    return matches[0] if len(matches) == 1 else None


# ---------------------------------------------------------------------------
# Facet families
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FacetFamily:
    """One facet dimension.

    ``resolver`` returns the bucket key for a record, or ``None`` when the record
    has no value on this dimension. ``None`` means absent, and absent records are
    counted and reported rather than filed under an invented bucket.
    """

    name: str
    label: str
    dimension: str
    resolver: Callable[[object], str | None]
    #: How a bucket key becomes a display label.
    labeller: Callable[[str, Sequence[object]], str]
    #: False where the facet is a partial partition of the candidate set.
    complete: bool = True
    note: str = ""


def _verbatim(key: str, _records: Sequence[object]) -> str:
    """The published string, unchanged.

    Countries and degree levels arrive already written for a reader. Echoing them
    exactly is both more correct and more honest about where the wording came from.
    """
    return key


def _field_label(key: str, records: Sequence[object]) -> str:
    for record in records:
        if getattr(record, "field", None) == key and getattr(record, "field_label", None):
            return record.field_label
    # No record in this set carries the canonical label. The key is still the
    # taxonomy's own term, so it is shown rather than dropped.
    return key.replace("_", " ").title()


def _partition_labeller(partition: str) -> Callable[[str, Sequence[object]], str]:
    """Labels for a contract partition, matching the family labeller signature."""
    spec = PARTITIONS_BY_NAME[partition]
    labels = dict(spec.buckets)

    def labeller(key: str, _records: Sequence[object]) -> str:
        return labels.get(key, key)

    return labeller


def _countries(resolver_name: str) -> Callable[[object], str | None]:
    def resolve(record: object) -> str | None:
        value = getattr(record, resolver_name, None)
        return value if value else None

    return resolve


def _partition_resolver(partition: str) -> Callable[[object], str | None]:
    from .core import partition_of

    spec = PARTITIONS_BY_NAME[partition]

    def resolve(record: object) -> str | None:
        return partition_of(record, spec)

    return resolve


def _region_resolver(record: object) -> str | None:
    return region_for_country(record.country)


FACET_FAMILIES: tuple[FacetFamily, ...] = (
    FacetFamily(
        name="countries",
        label="Country",
        dimension=CountFilter.COUNTRY.value,
        resolver=_countries("country"),
        labeller=_verbatim,
        complete=True,
        note="Every record publishes exactly one country, so this is a complete partition.",
    ),
    FacetFamily(
        name="regions",
        label="Region",
        dimension=CountFilter.REGION.value,
        resolver=_region_resolver,
        labeller=_verbatim,
        complete=False,
        note=(
            "A record appears here only where the curated region mapping places its "
            "country in exactly one region. Countries in no curated region, or in "
            "more than one, are absent from this facet rather than assigned to a "
            "region by inference."
        ),
    ),
    FacetFamily(
        name="degree_levels",
        label="Degree",
        dimension=CountFilter.DEGREE.value,
        resolver=_countries("degree_levels"),
        labeller=_verbatim,
        complete=True,
        note="The published degree string, verbatim. Never title-cased, never split.",
    ),
    FacetFamily(
        name="fields",
        label="Field",
        dimension=CountFilter.FIELD.value,
        resolver=lambda record: getattr(record, "field", None),
        labeller=_field_label,
        complete=False,
        note=(
            "The canonical programme field from the Match taxonomy. A record whose "
            "programme the taxonomy cannot resolve is absent rather than filed under "
            "an invented subject, so this facet is deliberately a partial partition."
        ),
    ),
    FacetFamily(
        name="funding_states",
        label="Funding",
        dimension=CountFilter.FUNDING.value,
        resolver=_partition_resolver("funding"),
        labeller=_partition_labeller("funding"),
        complete=True,
        note="Normalised funding state. UNKNOWN is published as its own value.",
    ),
    FacetFamily(
        name="eligibility_states",
        label="Eligibility",
        dimension=CountFilter.ELIGIBILITY.value,
        resolver=_partition_resolver("eligibility"),
        labeller=_partition_labeller("eligibility"),
        complete=True,
        note="The hard gate's verdict. Every analysed record has exactly one.",
    ),
    FacetFamily(
        name="fit_bands",
        label="Fit",
        dimension=CountFilter.FIT.value,
        resolver=_partition_resolver("fit_tier"),
        labeller=_partition_labeller("fit_tier"),
        complete=False,
        note=(
            "Records with no published fit score are absent, because the gate "
            "refused them or nothing could be evaluated. They are never filed under "
            "the lowest band."
        ),
    ),
    FacetFamily(
        name="confidence_bands",
        label="Confidence",
        dimension=CountFilter.CONFIDENCE.value,
        resolver=_partition_resolver("confidence"),
        labeller=_partition_labeller("confidence"),
        complete=True,
        note="Data trust in the record. Not an accuracy or success rate.",
    ),
    FacetFamily(
        name="coverage_bands",
        label="Coverage",
        dimension=CountFilter.COVERAGE.value,
        resolver=_partition_resolver("coverage"),
        labeller=_partition_labeller("coverage"),
        complete=True,
        note="How much of the scoring model was evaluated per record.",
    ),
    FacetFamily(
        name="readiness_bands",
        label="Readiness",
        dimension=CountFilter.READINESS.value,
        resolver=_partition_resolver("readiness"),
        labeller=_partition_labeller("readiness"),
        complete=True,
        note="Application readiness. A third dimension, distinct from fit and confidence.",
    ),
    FacetFamily(
        name="deadline_buckets",
        label="Deadline",
        dimension=CountFilter.DEADLINE.value,
        resolver=_partition_resolver("deadline"),
        labeller=_partition_labeller("deadline"),
        complete=True,
        note="Timing resolved against the injected as_of date.",
    ),
)

FACET_FAMILIES_BY_NAME: dict[str, FacetFamily] = {
    family.name: family for family in FACET_FAMILIES
}


def build_facets(
    records: Sequence[object],
    filter_state: FilterState | None = None,
    *,
    self_exclusion: bool = True,
    families: Iterable[str] | None = None,
) -> dict[str, list[CountBucket]]:
    """Build every facet from one candidate set, with self-exclusion.

    For each family, the candidate set is ``filter_state`` with that family's own
    dimension removed. Every other active predicate is retained, so the numbers
    describe what one more click would produce rather than what the catalogue holds
    in isolation.

    Order is deterministic: keys sort by count descending, then by key ascending, so
    the most common value is first and two runs never differ on a tie.
    """
    state = filter_state or FilterState()
    selected = set(families) if families is not None else None

    facets: dict[str, list[CountBucket]] = {}
    for family in FACET_FAMILIES:
        if selected is not None and family.name not in selected:
            continue

        scoped = state.without(family.dimension) if self_exclusion else state
        candidates = scoped.filter(records)

        counts: dict[str, int] = {}
        labels: dict[str, str] = {}
        absent = 0
        for record in candidates:
            key = family.resolver(record)
            if key is None:
                absent += 1
                continue
            counts[key] = counts.get(key, 0) + 1
            if key not in labels:
                labels[key] = family.labeller(key, candidates)

        buckets = [
            CountBucket(key=key, label=labels[key], count=count)
            for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
        facets[family.name] = buckets

    return facets


def assert_facets_reconciled(
    facets: Mapping[str, list[CountBucket]],
    facet_sets: Mapping[str, Sequence[object]],
) -> None:
    """Each complete facet must count its own candidate set exactly once.

    Under self-exclusion each family describes a *different* set - the candidate set
    with that family's own dimension relaxed - so the invariant is checked against
    the set that family actually used, not against one shared set. Checking them all
    against the same population would fail every facet whose dimension was selected,
    which is the normal case.

    A COMPLETE family's buckets must sum to the records it counted. A PARTIAL one may
    be smaller by exactly the records with no value on that dimension, and must never
    be larger.
    """
    for family in FACET_FAMILIES:
        buckets = facets.get(family.name)
        counted = facet_sets.get(family.name)
        if buckets is None or counted is None:
            continue
        total = sum(bucket.count for bucket in buckets)
        resolvable = sum(1 for record in counted if family.resolver(record) is not None)

        if family.complete:
            if total != resolvable:
                raise AssertionError(
                    f"{family.name} facet counts ({total}) must equal the records it "
                    f"describes ({resolvable})"
                )
        elif total > resolvable:
            raise AssertionError(
                f"{family.name} facet counts ({total}) exceed the records it describes "
                f"({resolvable})"
            )

        for bucket in buckets:
            if not bucket.label:
                raise AssertionError(
                    f"{family.name} facet {bucket.value} has no label; a bucket without a "
                    "readable label cannot be offered to anyone"
                )


def facet_candidate_sets(
    records: Sequence[object],
    filter_state: FilterState | None = None,
) -> dict[str, list[object]]:
    """The candidate set each facet family counted.

    Published alongside the facets so a reconciliation failure is diagnosable, and
    used by :func:`assert_facets_reconciled` rather than re-deriving it.
    """
    state = filter_state or FilterState()
    return {
        family.name: state.without(family.dimension).filter(records)
        for family in FACET_FAMILIES
    }


__all__ = [
    "DIMENSION_ORDER",
    "FACET_FAMILIES",
    "FACET_FAMILIES_BY_NAME",
    "FacetFamily",
    "FilterState",
    "SELF_EXCLUSION_SEMANTICS",
    "active_values",
    "assert_facets_reconciled",
    "facet_candidate_sets",
    "build_facets",
    "known_regions",
    "region_for_country",
    "region_members",
]