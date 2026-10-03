"""The count contract: one authoritative definition for every business-facing number.

A number on a screen is a claim. This module is where each claim is defined, so
that "36 eligible" is not a value typed into three components but one definition
consulted by all of them. It is the counting system's answer to the question the
Match engine already answered for scoring: what is the single source of truth, and
what happens when it is malformed.

Every metric declares nine things:

``name``
    The stable identifier, and the key it is published under.
``universe``
    Which population it counts. Never inferred from context.
``predicate``
    A deterministic function of one record. No predicate reads a clock, a random
    source, a network or mutable global state.
``partition_type``
    Whether the metric's family partitions the universe exactly, partially, or not
    at all. This is what makes reconciliation assertable rather than hopeful.
``null_policy``
    What happens when the record has no value for the dimension.
``unknown_policy``
    How a known-unknown is handled, which is a different question from ``null``.
``as_of_dependency``
    Whether the value can change purely because the date moved.
``engine_dependency`` / ``version_dependency``
    Which versions, if any, a stored copy of this number would have to be
    invalidated by.

Three rules are structural rather than documented:

1. **A predicate is pure.** It is a function of its argument. There is no
   ``count()`` call anywhere in this module, so the number of records that match
   is decided entirely by the caller, never by the definition.

2. **A metric is declared once.** ``MatchSummary`` in the Match engine is built
   by :mod:`app.services.matching.summaries` from these definitions rather than
   from its own hardcoded field map, so the two layers cannot drift.

3. **The vocabulary is closed and validated at import.** A metric naming a band
   the engine does not define, or a partition declared COMPLETE whose buckets do
   not cover the universe, raises here rather than producing a number nobody can
   reconcile.

There is deliberately no import from :mod:`app.services.matching` in this module.
The predicates are duck-typed over the record shape, which keeps the contract
loadable by the Match engine itself without a circular import, and which means the
contract cannot accidentally depend on the scoring implementation it describes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Sequence

from .types import CountBasis, CountUniverse, NullPolicy, UnknownPolicy


#: Bumped whenever any metric definition, predicate or partition changes. A count
#: that moves under an unchanged contract version is the failure this exists to
#: prevent.
COUNT_CONTRACT_VERSION = "2.0.0"

#: Catalogue visibility is the directory's definition, not this layer's. Named so a
#: reader can see that this module does not own the rule.
CATALOGUE_PREDICATE_SOURCE = "app.repositories.scholarships.public_visibility_conditions"


# ---------------------------------------------------------------------------
# The metric record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CountMetric:
    """One formally defined count."""

    name: str
    universe: CountUniverse
    #: A deterministic predicate over one record, or ``None`` for the universe
    #: size itself.
    predicate: Callable[[object], bool] | None
    partition: str
    partition_type: CountBasis
    null_policy: NullPolicy
    unknown_policy: UnknownPolicy
    as_of_dependency: bool
    engine_dependency: tuple[str, ...] = ()
    version_dependency: tuple[str, ...] = ()
    #: For partition members, the bucket key this metric fills. Absent for
    #: standalone measures.
    bucket: str | None = None
    label: str = ""
    note: str = ""

    def evaluate(self, record: object) -> bool:
        """Apply the predicate. A metric with no predicate is never evaluated."""
        if self.predicate is None:
            raise ValueError(f"metric {self.name!r} defines no predicate")
        return bool(self.predicate(record))


@dataclass(frozen=True)
class CountPartitionSpec:
    """A family of metrics that together describe one dimension."""

    name: str
    label: str
    universe: CountUniverse
    partition_type: CountBasis
    #: Bucket key -> label, in published order.
    buckets: tuple[tuple[str, str], ...]
    #: Records that produce no bucket. A COMPLETE partition must name a bucket for
    #: every possible outcome; a PARTIAL one declares how absences are counted.
    unclassified_bucket: str | None = None
    note: str = ""
    as_of_dependency: bool = False
    engine_dependency: tuple[str, ...] = ()
    version_dependency: tuple[str, ...] = ()
    #: Which population this partition's buckets must sum to.
    #:
    #: ``UNIVERSE`` for a partition of every record in the universe.
    #: ``SCORED`` for the fit tiers, which partition the scored set rather than the
    #: analysed universe - an unscored record has no tier by definition, so
    #: reconciling them against ``total_candidates`` would require inventing a
    #: "no tier" bucket for every unscored record and would misdescribe what a tier
    #: is.
    reconciles_against: str = "UNIVERSE"


# ---------------------------------------------------------------------------
# Predicates
#
# Duck-typed over the record shape on purpose. A predicate reads named attributes
# and nothing else; it does not import the type that happens to provide them.
# ---------------------------------------------------------------------------


def _eligibility_is(value: str) -> Callable[[object], bool]:
    return lambda item: getattr(item.eligibility, "value", item.eligibility) == value


def _has_fit(item: object) -> bool:
    return item.fit_score is not None


def _has_fit_band(item: object) -> bool:
    return _has_fit(item) and item.fit_label in _FIT_BAND_KEY_SET


def _confidence_is(key: str) -> Callable[[object], bool]:
    return lambda item: item.confidence_label == key


def _coverage_is(key: str) -> Callable[[object], bool]:
    from ..matching.config import classify_coverage

    return lambda item: classify_coverage(item.data_coverage) == key


def _readiness_bucket(item: object) -> str:
    """Map a result onto its readiness publication bucket.

    A result with no readiness at all is ``NOT_EVALUATED``. That is distinct from
    the ``NOT_READY`` band: "nothing could be evaluated" and "evaluated, and the
    evidence shows preparation is missing" are different statements, and folding
    them together would let missing data read as a finding about the student.
    """
    readiness = getattr(item, "readiness", None)
    if readiness is None or readiness.band is None:
        return "NOT_EVALUATED"
    return readiness.band


def _readiness_is(key: str) -> Callable[[object], bool]:
    return lambda item: _readiness_bucket(item) == key


def _funding_is(key: str) -> Callable[[object], bool]:
    return lambda item: item.funding_state.value == key


def _deadline_bucket(item: object) -> str:
    return item.timing_bucket or "UNKNOWN"


def _deadline_is(key: str) -> Callable[[object], bool]:
    return lambda item: _deadline_bucket(item) == key


def _deadline_precision_is(key: str) -> Callable[[object], bool]:
    return lambda item: (item.deadline_precision or "unknown") == key


def _field_is(key: str) -> Callable[[object], bool]:
    return lambda item: item.field == key


def _country_is(key: str) -> Callable[[object], bool]:
    return lambda item: item.country == key


def _degree_is(key: str) -> Callable[[object], bool]:
    return lambda item: item.degree_levels == key


#: Populated below from the engine configuration, so the contract cannot declare a
#: band the engine does not define. Declared before the predicates that close over
#: it, and assigned by :func:`_bind`.
_FIT_BAND_KEY_SET: frozenset[str] = frozenset()


# ---------------------------------------------------------------------------
# Partition specifications
# ---------------------------------------------------------------------------

ELIGIBILITY_PARTITION = CountPartitionSpec(
    name="eligibility",
    label="Eligibility",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("ELIGIBLE", "Eligible"),
        ("NEEDS_VERIFICATION", "Needs verification"),
        ("INELIGIBLE", "Not eligible"),
    ),
    note=(
        "Every analysed candidate reaches the hard gate exactly once. This "
        "partition is complete by construction: the gate returns a verdict for "
        "every record it is given."
    ),
    engine_dependency=("eligibility",),
)

SCORED_PARTITION = CountPartitionSpec(
    name="scored",
    label="Scored",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("SCORED", "Scored"),
        ("NOT_SCORED", "Not scored"),
    ),
    note=(
        "Scored means at least one scoring dimension was evaluated and the public "
        "fit contract therefore carries a score. An INELIGIBLE record is not "
        "scored: the gate refuses it before fit is published, so publishing a tier "
        "for it would read as a recommendation the gate already declined."
    ),
    engine_dependency=("metrics", "eligibility"),
)

FIT_TIER_PARTITION = CountPartitionSpec(
    name="fit_tier",
    label="Fit tier",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(),  # filled from the engine band table
    unclassified_bucket="UNCLASSIFIED",
    note=(
        "Fit tiers reconcile against scored_count, not against total_candidates. A "
        "record with no published score has no tier by definition, so the tiers "
        "are a complete partition of the scored set and a partial view of the "
        "analysed universe. INELIGIBLE records publish no tier at all."
    ),
    engine_dependency=("metrics", "config"),
    version_dependency=("scoring_config_version",),
    reconciles_against="SCORED",
)

CONFIDENCE_PARTITION = CountPartitionSpec(
    name="confidence",
    label="Record confidence",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")),
    note=(
        "Confidence describes the record, not the student, and every analysed "
        "candidate receives one, so this partition is complete. It means data "
        "trust. It is not an accuracy rate, a success rate or an admission "
        "confidence, and it is never rendered as one."
    ),
    engine_dependency=("confidence",),
    version_dependency=("scoring_config_version",),
)

COVERAGE_PARTITION = CountPartitionSpec(
    name="coverage",
    label="Data coverage",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")),
    note=(
        "How much of the configured scoring model was evaluated for each record. "
        "Coverage is never folded into LOW for lack of data: an unevaluated "
        "dimension lowers coverage, it does not become an unknown band."
    ),
    engine_dependency=("metrics",),
    version_dependency=("scoring_config_version",),
)

READINESS_PARTITION = CountPartitionSpec(
    name="readiness",
    label="Application readiness",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("READY", "Ready to apply"),
        ("READY_WITH_CHECKS", "Ready with a few checks"),
        ("CHECKS_NEEDED", "Some checks needed"),
        ("NOT_READY", "Not ready yet"),
        ("NOT_EVALUATED", "Readiness not evaluated"),
    ),
    note=(
        "Readiness is a third dimension, distinct from fit and from confidence. "
        "NOT_EVALUATED is published as its own bucket so that a record nothing "
        "could be evaluated for is never read as a record that failed preparation."
    ),
    engine_dependency=("readiness",),
    version_dependency=("scoring_config_version",),
)

FUNDING_PARTITION = CountPartitionSpec(
    name="funding",
    label="Funding",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("FULL", "Full funding"),
        ("TUITION_PLUS_LIVING", "Tuition and living costs"),
        ("TUITION_ONLY", "Tuition only"),
        ("PARTIAL", "Partial funding"),
        ("NONE", "No funding"),
        ("UNKNOWN", "Funding not verified"),
    ),
    note=(
        "Normalised, evidence-backed funding state. UNKNOWN is not NONE: an "
        "unestablished funding state is an absence of evidence, and a published "
        "\"no funding\" is a statement by the provider. Collapsing them would "
        "report a finding ScholarZone never made."
    ),
    engine_dependency=("components", "config"),
    version_dependency=("scoring_config_version",),
)

DEADLINE_PARTITION = CountPartitionSpec(
    name="deadline",
    label="Deadline timing",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("COMFORTABLE", "Comfortable, 60+ days"),
        ("APPROACHING", "Approaching, 14-59 days"),
        ("CLOSING_SOON", "Closing soon, under 14 days"),
        ("CLOSED", "Closed"),
        ("UNKNOWN", "No fixed date published"),
    ),
    note=(
        "Timing buckets over the published deadline, resolved against the "
        "injected as_of date. A rolling or annual deadline lands in UNKNOWN, "
        "because \"no fixed date\" is not \"too late\"."
    ),
    as_of_dependency=True,
    engine_dependency=("components",),
    version_dependency=("deadline_semantics_version",),
)

DEADLINE_PRECISION_PARTITION = CountPartitionSpec(
    name="deadline_precision",
    label="Deadline precision",
    universe=CountUniverse.MATCH_ANALYSED,
    partition_type=CountBasis.COMPLETE,
    buckets=(
        ("exact", "Exact date"),
        ("month", "Month precision"),
        ("rolling", "Rolling"),
        # Two vocabularies exist for one concept, and the counting layer publishes
        # both rather than picking one.
        #
        # `deadline_semantics.DEADLINE_PRECISION_VALUES` spells the recurring state
        # "recurring"; the Match result publishes "annual". Both are real: the first
        # is the stored/extractor vocabulary, the second is what the engine's result
        # object carries. Declaring only one left records uncounted, which
        # reconciliation correctly refused to publish.
        #
        # Choosing one would mean changing the other module. The engine's published
        # value is a non-scoring attribute, so the fix belongs here - the contract
        # covers the union, and the mismatch is recorded rather than erased.
        ("recurring", "Recurring"),
        ("annual", "Annual"),
        ("year", "Year precision"),
        ("varies", "Varies"),
        ("approximate", "Approximate"),
        ("unknown", "Precision unknown"),
    ),
    note=(
        "The precision the provider published, from the existing deadline "
        "semantics vocabulary. This is a statement about the record's own "
        "wording and never contributes to a score."
    ),
    engine_dependency=("components",),
    version_dependency=("deadline_semantics_version",),
)


#: Which module produces each universe, and over what.
#:
#: Declared here so a universe cannot be an enum member that nothing implements.
#: An unreferenced universe is a naming convention; this is a binding. ``MATCH_RETURNED_PAGE``
#: in particular is not a partition - it is the basis *facet counts* describe, and it
#: is produced by the facet builder rather than by :mod:`core`, which is exactly the
#: kind of fact that is otherwise only discoverable by reading two modules.
UNIVERSE_PRODUCERS: dict[str, str] = {
    CountUniverse.CATALOGUE.value: (
        "app.services.counting.catalogue.catalogue_counts, over the directory's "
        "public_visibility_conditions"
    ),
    CountUniverse.SEARCH_FILTER.value: (
        "app.repositories.scholarships.list_scholarships, after the directory's search "
        "and filter predicates"
    ),
    CountUniverse.MATCH_ANALYSED.value: (
        "app.services.counting.core.count_all_partitions, over every result the Match "
        "engine scored for this profile"
    ),
    CountUniverse.MATCH_RETURNED_PAGE.value: (
        "app.services.counting.facets.build_facets, over the candidate set with each "
        "facet's own dimension relaxed"
    ),
}


CATALOGUE_PARTITIONS: tuple[CountPartitionSpec, ...] = (
    CountPartitionSpec(
        name="lifecycle_status",
        label="Lifecycle status",
        universe=CountUniverse.CATALOGUE,
        partition_type=CountBasis.COMPLETE,
        buckets=(
            ("open", "Open"),
            ("closing-soon", "Closing soon"),
            ("upcoming", "Upcoming"),
            ("closed", "Closed"),
            ("other", "Other status"),
        ),
        note=(
            "The lifecycle states the catalogue actually stores. \"other\" is a "
            "published bucket rather than a silent drop, so the partition stays "
            "complete and an unexpected status is visible instead of lost."
        ),
        as_of_dependency=False,
        version_dependency=("lifecycle_manager",),
    ),
    CountPartitionSpec(
        name="catalogue_evidence",
        label="Evidence",
        universe=CountUniverse.CATALOGUE,
        partition_type=CountBasis.NOT_A_PARTITION,
        buckets=(
            ("verified", "Verified"),
            ("unverified", "Not verified"),
            ("quarantined", "Quarantined"),
            ("archived", "Archived"),
            ("with_image", "With image"),
            ("without_image", "Without image"),
            ("with_official_source", "With official source"),
            ("without_official_source", "Without official source"),
        ),
        note=(
            "Independent measures over the catalogue, not a partition: a record "
            "can be verified and have no image, and both claims are true. Their "
            "sum is therefore not asserted anywhere."
        ),
        version_dependency=("verification",),
    ),
)


# ---------------------------------------------------------------------------
# Binding the contract to the engine's own vocabulary
# ---------------------------------------------------------------------------


def _fit_buckets() -> tuple[tuple[str, str], ...]:
    from ..matching.config import FIT_BANDS

    return tuple((key, label) for _, key, label in FIT_BANDS)


def _bind() -> None:
    """Fill the parts of the contract that must agree with the engine.

    Run at import. If the engine's band table and the contract's partition ever
    disagree, this raises rather than letting a bucket exist that nothing can ever
    be counted into.
    """
    global _FIT_BAND_KEY_SET, FIT_TIER_PARTITION

    from ..deadline_semantics import DEADLINE_PRECISION_VALUES
    from ..matching.config import (
        CONFIDENCE_BAND_KEYS,
        COVERAGE_BAND_KEYS,
        FUNDING_STATES,
        READINESS_BAND_KEYS,
        TIMING_BUCKET_KEYS,
    )

    buckets = _fit_buckets()
    _FIT_BAND_KEY_SET = frozenset(key for key, _ in buckets)
    FIT_TIER_PARTITION = replace_partition_buckets(FIT_TIER_PARTITION, buckets)

    _require_subset("CONFIDENCE_PARTITION", CONFIDENCE_PARTITION, CONFIDENCE_BAND_KEYS)
    _require_subset("COVERAGE_PARTITION", COVERAGE_PARTITION, COVERAGE_BAND_KEYS)
    # NOT_EVALUATED is published as a bucket but is produced by the counting
    # layer: it means no readiness dimension could be evaluated at all, which is
    # an absence the engine reports rather than a band it assigns.
    _require_subset(
        "READINESS_PARTITION",
        READINESS_PARTITION,
        READINESS_BAND_KEYS,
        allow_extra=frozenset({"NOT_EVALUATED"}),
    )
    _require_subset("DEADLINE_PARTITION", DEADLINE_PARTITION, TIMING_BUCKET_KEYS)
    _require_subset("FUNDING_PARTITION", FUNDING_PARTITION, FUNDING_STATES)
    _require_subset(
        "DEADLINE_PRECISION_PARTITION",
        DEADLINE_PRECISION_PARTITION,
        DEADLINE_PRECISION_VALUES,
        # "annual" is what the Match result publishes for the recurring state; the
        # deadline-semantics vocabulary spells it "recurring". Both are declared above.
        allow_extra=frozenset({"annual"}),
    )


def replace_partition_buckets(
    spec: CountPartitionSpec, buckets: Sequence[tuple[str, str]]
) -> CountPartitionSpec:
    return CountPartitionSpec(
        name=spec.name,
        label=spec.label,
        universe=spec.universe,
        partition_type=spec.partition_type,
        buckets=tuple(buckets),
        unclassified_bucket=spec.unclassified_bucket,
        note=spec.note,
        as_of_dependency=spec.as_of_dependency,
        engine_dependency=spec.engine_dependency,
        version_dependency=spec.version_dependency,
        reconciles_against=spec.reconciles_against,
    )


def _require_subset(
    name: str,
    spec: CountPartitionSpec,
    allowed: Iterable[str],
    *,
    allow_extra: frozenset[str] = frozenset(),
) -> None:
    """Every bucket must be a state the engine can actually produce.

    ``allow_extra`` names the counting layer's *own* states, which are published
    as buckets but are produced by this layer rather than by the scoring engine.
    They are listed explicitly at each call site rather than waved through,
    because "the contract may declare any state it likes" is how a partition
    quietly grows a bucket that can never be counted into.
    """
    allowed_set = set(allowed) | set(allow_extra)
    unknown = [key for key, _ in spec.buckets if key not in allowed_set]
    if unknown:
        raise RuntimeError(
            f"{name} declares buckets the engine does not define: {unknown}"
        )


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

# Bound here, before the registry is assembled. The fit partition is the one whose
# buckets come from the engine rather than from this module, so binding after
# ``PARTITIONS`` was built would leave a five-bucket partition permanently empty
# and every fit tier count silently zero.
_bind()

PARTITIONS: tuple[CountPartitionSpec, ...] = (
    ELIGIBILITY_PARTITION,
    SCORED_PARTITION,
    FIT_TIER_PARTITION,
    CONFIDENCE_PARTITION,
    COVERAGE_PARTITION,
    READINESS_PARTITION,
    FUNDING_PARTITION,
    DEADLINE_PARTITION,
    DEADLINE_PRECISION_PARTITION,
    *CATALOGUE_PARTITIONS,
)

PARTITIONS_BY_NAME: dict[str, CountPartitionSpec] = {
    spec.name: spec for spec in PARTITIONS
}


def _build_metrics() -> tuple[CountMetric, ...]:
    """Expand every partition into its individual metrics."""
    metrics: list[CountMetric] = []

    for spec in PARTITIONS:
        for key, label in spec.buckets:
            metrics.append(
                CountMetric(
                    name=f"{spec.name}.{key}",
                    universe=spec.universe,
                    predicate=_predicate_for(spec.name, key),
                    partition=spec.name,
                    partition_type=spec.partition_type,
                    null_policy=NullPolicy.EXCLUDED_AND_REPORTED,
                    unknown_policy=(
                        UnknownPolicy.OWN_BUCKET
                        if key in {"UNKNOWN", "NOT_EVALUATED", "unclassified"}
                        else UnknownPolicy.OWN_BUCKET
                    ),
                    as_of_dependency=spec.as_of_dependency,
                    engine_dependency=spec.engine_dependency,
                    version_dependency=spec.version_dependency,
                    bucket=key,
                    label=label,
                    note=spec.note,
                )
            )
        if spec.unclassified_bucket:
            metrics.append(
                CountMetric(
                    name=f"{spec.name}.{spec.unclassified_bucket}",
                    universe=spec.universe,
                    predicate=None,  # supplied by the counting engine
                    partition=spec.name,
                    partition_type=spec.partition_type,
                    null_policy=NullPolicy.EXCLUDED_AND_REPORTED,
                    unknown_policy=UnknownPolicy.OWN_BUCKET,
                    as_of_dependency=spec.as_of_dependency,
                    engine_dependency=spec.engine_dependency,
                    version_dependency=spec.version_dependency,
                    bucket=spec.unclassified_bucket,
                    label="Not classified",
                    note=spec.note,
                )
            )

    return tuple(metrics)


_PREDICATE_FACTORIES: dict[str, Callable[[str], Callable[[object], bool]]] = {
    "eligibility": _eligibility_is,
    # A complement, not an independent predicate: the two buckets must partition
    # the universe, so NOT_SCORED is "no published fit score", never "anything
    # that failed to match SCORED". Writing it as a failed match made the
    # partition sum to the scored count instead of the universe.
    "scored": lambda key: (
        (lambda item: _has_fit(item))
        if key == "SCORED"
        else (lambda item: not _has_fit(item))
    ),
    "fit_tier": lambda key: (lambda item: _has_fit_band(item) and item.fit_label == key),
    "confidence": _confidence_is,
    "coverage": _coverage_is,
    "readiness": _readiness_is,
    "funding": _funding_is,
    "deadline": _deadline_is,
    "deadline_precision": _deadline_precision_is,
    # "other" is the residual lifecycle state, so it means "not one of the states
    # the catalogue declares". Anything else would make the residual bucket match
    # every record.
    "lifecycle_status": lambda key: (
        (lambda item: getattr(item, "status", None) not in _LIFECYCLE_STATUS_KEYS)
        if key == "other"
        else (lambda item: getattr(item, "status", None) == key)
    ),
    # The catalogue evidence family is computed in SQL against stored rows, not by
    # a per-record predicate over scored results. Counting it here would silently
    # report "every record has a source" for each row, so it refuses instead.
    "catalogue_evidence": lambda key: _unsupported_in_memory(key),
}

#: The lifecycle states the catalogue declares. Anything else is the residual.
_LIFECYCLE_STATUS_KEYS: frozenset[str] = frozenset(
    {"open", "closing-soon", "upcoming", "closed"}
)


def _unsupported_in_memory(key: str) -> Callable[[object], bool]:
    """Declare the metric, but refuse to evaluate it in memory.

    The factory is called once at import to populate the registry, so this returns
    a callable rather than raising immediately. Raising on *evaluation* keeps the
    metric visible in the contract snapshot and in provenance while making it
    impossible to accidentally count it over scored results.
    """

    def predicate(_record: object) -> bool:
        raise NotImplementedError(
            f"catalogue_evidence.{key} is computed in SQL against stored catalogue "
            "rows, not by a predicate over scored results"
        )

    return predicate


def _predicate_for(partition: str, key: str) -> Callable[[object], bool]:
    factory = _PREDICATE_FACTORIES.get(partition)
    if factory is None:
        raise RuntimeError(f"no predicate defined for partition {partition!r}")
    return factory(key)


METRICS: tuple[CountMetric, ...] = ()


def metrics_for(partition: str) -> tuple[CountMetric, ...]:
    return tuple(metric for metric in METRICS if metric.partition == partition)


def metric(name: str) -> CountMetric:
    for candidate in METRICS:
        if candidate.name == name:
            return candidate
    raise KeyError(f"no count metric named {name!r}")


def contract_snapshot() -> dict:
    """The complete contract, serialisable.

    Published with the intelligence response so a stored count can be checked
    against the definitions it claims to satisfy.
    """
    return {
        "count_contract_version": COUNT_CONTRACT_VERSION,
        "catalogue_predicate_source": CATALOGUE_PREDICATE_SOURCE,
        "universes": [universe.value for universe in CountUniverse],
        "universe_producers": dict(UNIVERSE_PRODUCERS),
        "partition_types": [basis.value for basis in CountBasis],
        "partitions": [
            {
                "name": spec.name,
                "label": spec.label,
                "universe": spec.universe.value,
                "partition_type": spec.partition_type.value,
                "as_of_dependency": spec.as_of_dependency,
                "buckets": [
                    {"key": key, "label": label} for key, label in spec.buckets
                ],
                "unclassified_bucket": spec.unclassified_bucket,
                "engine_dependency": list(spec.engine_dependency),
                "version_dependency": list(spec.version_dependency),
                "note": spec.note,
            }
            for spec in PARTITIONS
        ],
    }


METRICS: tuple[CountMetric, ...] = _build_metrics()


def validate_contract() -> None:
    """Fail at import time if the contract is internally inconsistent.

    A duplicate metric name, a repeated bucket key, a COMPLETE partition with no
    buckets, or a bucket that has no metric are all states where a published count
    could disagree with itself. They are caught here, once, rather than being
    rediscovered as a wrong number on a dashboard.
    """
    names = [m.name for m in METRICS]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise RuntimeError(f"count contract declares duplicate metrics: {sorted(duplicates)}")

    for spec in PARTITIONS:
        keys = [key for key, _ in spec.buckets]
        if len(set(keys)) != len(keys):
            raise RuntimeError(f"partition {spec.name!r} repeats a bucket key")
        if spec.partition_type is CountBasis.COMPLETE and not spec.buckets:
            raise RuntimeError(f"partition {spec.name!r} is COMPLETE but declares no buckets")
        if spec.unclassified_bucket and spec.unclassified_bucket in keys:
            raise RuntimeError(
                f"partition {spec.name!r} uses {spec.unclassified_bucket!r} as both a bucket and the unclassified state"
            )

    # Every partition's metrics must exist, which is what makes the Match engine's
    # summary a projection of this contract rather than a parallel definition.
    for spec in PARTITIONS:
        for key, _ in spec.buckets:
            if f"{spec.name}.{key}" not in set(names):
                raise RuntimeError(f"partition {spec.name!r} bucket {key!r} has no metric")


validate_contract()


__all__ = [
    "CATALOGUE_PARTITIONS",
    "COUNT_CONTRACT_VERSION",
    "CountMetric",
    "CountPartitionSpec",
    "DEADLINE_PARTITION",
    "DEADLINE_PRECISION_PARTITION",
    "ELIGIBILITY_PARTITION",
    "FIT_TIER_PARTITION",
    "FUNDING_PARTITION",
    "METRICS",
    "PARTITIONS",
    "PARTITIONS_BY_NAME",
    "UNIVERSE_PRODUCERS",
    "CONFIDENCE_PARTITION",
    "COVERAGE_PARTITION",
    "READINESS_PARTITION",
    "SCORED_PARTITION",
    "contract_snapshot",
    "metric",
    "metrics_for",
    "replace_partition_buckets",
]