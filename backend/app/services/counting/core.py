"""The counting engine.

One canonical candidate set goes in; structured statistical objects come out. This
module knows nothing about HTTP, about SQL, about how a record is displayed, or
about what a user is looking at. It counts, partitions and reconciles, and it
refuses to publish a set of counts that disagree with itself.

The pipeline is the one the architecture calls for, expressed as four steps that
can each be used on their own:

    Canonical candidate set
        ↓
    Predicate evaluation          (from the count contract, never re-declared)
        ↓
    Partition / bucket counting   (single pass, no per-facet query)
        ↓
    Reconciliation                (asserted, not assumed)

Two properties matter enough to be load-bearing.

**Predicates come from the contract.** Every bucket is filled by a predicate
published in :mod:`contract`, so the counting engine cannot acquire a private
opinion about what "eligible" or "fully funded" means. That is what keeps this
layer and the Match engine from drifting apart: they share one definition.

**Reconciliation is a result, not an assertion.** :func:`integrity` returns a
``CountIntegrity`` with an explicit status rather than raising or, worse, returning
nothing. A count system that can only report success cannot report failure, and the
one thing a reader needs from a count is to know whether to trust it. The strict
entry point :func:`assert_integrity` still exists for the paths that must not emit a
contradictory response, and it raises with the failing identity named.
"""

from __future__ import annotations

from typing import Callable, Iterable, Sequence

from .contract import COUNT_CONTRACT_VERSION, CountPartitionSpec, PARTITIONS_BY_NAME
from .types import (
    CountBasis,
    CountBucket,
    CountIntegrity,
    CountPartition,
    CountReconciliation,
    CountUniverse,
    DistributionSummary,
    IntegrityStatus,
)


#: Averages over fewer records than this are published with a caveat rather than
#: presented as a summary statistic. Three records is not a distribution, and a mean
#: of three next to a mean of three thousand invites a comparison the evidence
#: cannot support.
MIN_SAMPLE_FOR_AGGREGATES = 5


class CountError(RuntimeError):
    """Raised when a set of counts cannot be reconciled."""


# ---------------------------------------------------------------------------
# Bucket resolution
# ---------------------------------------------------------------------------


def _bucket_predicates(spec: CountPartitionSpec) -> list[tuple[str, Callable[[object], bool]]]:
    """The (key, predicate) pairs for one partition, in published order.

    Read from the contract registry rather than declared here, so adding a bucket
    to the contract is the only way to add one to the engine.
    """
    from .contract import metrics_for

    resolved: list[tuple[str, Callable[[object], bool]]] = []
    for metric in metrics_for(spec.name):
        if metric.bucket is None:
            continue
        if metric.predicate is None:
            # The unclassified bucket: assigned by the engine from the residual,
            # never by a predicate. See :func:`count_partition`.
            continue
        resolved.append((metric.bucket, metric.predicate))
    return resolved


#: Cached per partition name. Building the predicate list walks the whole metric
#: registry, and this is called once per partition per request.
_PREDICATE_CACHE: dict[str, list[tuple[str, Callable[[object], bool]]]] = {}


def _predicates_for(spec: CountPartitionSpec) -> list[tuple[str, Callable[[object], bool]]]:
    cached = _PREDICATE_CACHE.get(spec.name)
    if cached is None:
        cached = _bucket_predicates(spec)
        _PREDICATE_CACHE[spec.name] = cached
    return cached


def partition_of(record: object, spec: CountPartitionSpec) -> str | None:
    """Which bucket one record belongs to, or ``None`` for no bucket.

    ``None`` is a real answer and never a failure. A record with no published
    funding evidence belongs to no funding-measurement bucket here; the counting
    layer resolves that into an explicit unknown state rather than letting the
    record vanish.
    """
    for key, predicate in _predicates_for(spec):
        if predicate(record):
            return key
    return None


# ---------------------------------------------------------------------------
# Counting
# ---------------------------------------------------------------------------


def count_partition(
    records: Sequence[object],
    spec: CountPartitionSpec,
    *,
    universe: CountUniverse | None = None,
) -> CountPartition:
    """Count one partition over one candidate set.

    Single pass over ``records``. A record that matches no bucket is counted as
    unclassified and published as such, so the residual is visible rather than
    inferred from a subtraction.
    """
    labels = dict(spec.buckets)
    counts: dict[str, int] = {key: 0 for key in labels}
    unclassified = 0

    for record in records:
        key = partition_of(record, spec)
        if key is None:
            unclassified += 1
            continue
        if key not in counts:
            # A predicate produced a key the contract does not publish. Counted as
            # unclassified rather than invented as a new bucket, so the published
            # partition stays exactly as declared.
            unclassified += 1
            continue
        counts[key] += 1

    buckets = [
        CountBucket(
            key=key,
            label=label,
            count=counts[key],
            is_unknown=key in {"UNKNOWN", "NOT_EVALUATED", "UNCLASSIFIED", "unclassified"},
        )
        for key, label in spec.buckets
    ]

    return CountPartition(
        name=spec.name,
        label=spec.label,
        basis=spec.partition_type,
        buckets=buckets,
        bucket_total=sum(counts.values()),
        unclassified_count=unclassified,
        note=spec.note,
    )


def partition_population(partition_name: str, records: Sequence[object]) -> list[object]:
    """The sub-population a partition is defined over.

    Most partitions describe the whole universe. The fit tiers describe the *scored*
    set, because a record with no published fit score has no tier by definition:
    it was either refused by the gate or nothing could be evaluated for it. Counting
    it as "unclassified fit" would report the absence of a measurement as a
    classification, and would make the tiers reconcile against the wrong total.

    This is read from the contract's ``reconciles_against`` rather than hardcoded
    here, so a partition cannot disagree with its own declaration.
    """
    spec = PARTITIONS_BY_NAME.get(partition_name)
    if spec is None:
        raise KeyError(f"no count partition named {partition_name!r}")
    if spec.reconciles_against == "SCORED":
        return [record for record in records if getattr(record, "fit_score", None) is not None]
    return list(records)


def count_all_partitions(
    records: Sequence[object],
    *,
    partitions: Iterable[str] | None = None,
    universe: CountUniverse = CountUniverse.MATCH_ANALYSED,
    scored: int | None = None,
) -> list[CountPartition]:
    """Count every requested partition over the same candidate set.

    The partitions are named rather than discovered, so the caller states which
    universes are in play and this function cannot count a Match partition against
    catalogue rows by accident.
    """
    names = tuple(partitions) if partitions is not None else _record_partition_names(universe)
    if scored is None:
        scored = sum(1 for record in records if getattr(record, "fit_score", None) is not None)

    counted: list[CountPartition] = []
    for name in names:
        spec = PARTITIONS_BY_NAME.get(name)
        if spec is None:
            raise KeyError(f"no count partition named {name!r}")
        counted.append(count_partition(partition_population(name, records), spec))
    return counted


def _record_partition_names(universe: CountUniverse) -> tuple[str, ...]:
    return tuple(
        spec.name
        for spec in PARTITIONS_BY_NAME.values()
        if spec.universe is universe
    )


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


def reconcile(
    partitions: Sequence[CountPartition],
    *,
    total: int,
    scored: int | None = None,
) -> list[CountReconciliation]:
    """Build the asserted identities for a set of partitions.

    Every identity is checked against the population its contract declares, and the
    expression is published alongside the verdict so a failure is diagnosable from
    the response rather than from a stack trace.
    """
    by_name = {partition.name: partition for partition in partitions}
    results: list[CountReconciliation] = []

    for name, partition in by_name.items():
        spec = PARTITIONS_BY_NAME.get(name)
        if spec is None:
            continue

        if partition.basis is CountBasis.NOT_A_PARTITION:
            # Independent measures. Their sum is not an identity and asserting one
            # would manufacture a defect on every response.
            continue

        expected_total = total
        target = "UNIVERSE"
        if spec.reconciles_against == "SCORED":
            if scored is None:
                raise CountError(
                    f"partition {name!r} reconciles against the scored set, which was not supplied"
                )
            expected_total = scored
            target = "SCORED"

        observed = partition.bucket_total
        results.append(
            CountReconciliation(
                name=f"{name}_sums_to_{target.lower()}",
                expression=(
                    f"sum({name} buckets) == {target} size ({expected_total})"
                ),
                observed=observed,
                expected=expected_total,
                holds=observed == expected_total,
            )
        )

    return results


def integrity(
    partitions: Sequence[CountPartition],
    *,
    total: int,
    scored: int | None = None,
    warnings: Sequence[str] = (),
) -> CountIntegrity:
    """Produce a first-class integrity verdict.

    ``FAIL`` when an asserted identity does not hold: the counts contradict each
    other and must not be presented as if they did not.

    ``WARNING`` when the counts are internally consistent but some declared
    evidence was unavailable, so a reader knows the numbers are sound and
    incomplete rather than complete.

    ``PASS`` only when both hold. The two states are kept distinct on purpose, so a
    reader is never told a number is trustworthy when the honest answer is "true,
    but I could not see part of the catalogue".
    """
    checks = reconcile(partitions, total=total, scored=scored)
    failed = [check for check in checks if not check.holds]
    issue_list = [
        f"{check.expression}: observed {check.observed}, expected {check.expected}"
        for check in failed
    ]
    issue_list.extend(warnings)

    if failed:
        status = IntegrityStatus.FAIL
    elif warnings:
        status = IntegrityStatus.WARNING
    else:
        status = IntegrityStatus.PASS

    return CountIntegrity(status=status, reconciliations=checks, issues=issue_list)


def assert_integrity(result: CountIntegrity) -> None:
    """Raise unless the verdict is PASS.

    ``WARNING`` passes: an unavailable baseline is a real limitation, not a
    contradiction, and refusing to publish honest incomplete counts would be the
    wrong trade. Only a genuine contradiction stops a response.
    """
    if result.status is IntegrityStatus.FAIL:
        raise CountError("; ".join(result.issues))


# ---------------------------------------------------------------------------
# Safe aggregates
# ---------------------------------------------------------------------------


def distribution(
    values: Sequence[float | None],
    *,
    dimension: str,
    universe: CountUniverse,
    integer: bool = False,
) -> DistributionSummary:
    """Descriptive statistics over the measured values only.

    ``None`` is excluded, never coerced to zero, and the number excluded is
    published. An average that silently averaged absences into its denominator would
    report a record's missing field as a low measurement.
    """
    measured = [value for value in values if value is not None]
    excluded = len(values) - len(measured)

    if not measured:
        return DistributionSummary(
            universe=universe,
            dimension=dimension,
            sample_count=0,
            excluded_count=excluded,
            caveat="No record in this universe had a measured value.",
        )

    ordered = sorted(measured)
    size = len(ordered)
    middle = size // 2
    if size % 2 == 1:
        median = ordered[middle]
    else:
        median = (ordered[middle - 1] + ordered[middle]) / 2

    precision = 1 if integer else 2
    caveat = ""
    if size < MIN_SAMPLE_FOR_AGGREGATES:
        caveat = (
            f"Based on {size} record{'s' if size == 1 else ''}. Too few for a "
            "distribution; read the count, not the average."
        )

    return DistributionSummary(
        universe=universe,
        dimension=dimension,
        sample_count=size,
        excluded_count=excluded,
        minimum=round(ordered[0], precision),
        maximum=round(ordered[-1], precision),
        mean=round(sum(ordered) / size, precision),
        median=round(median, precision),
        caveat=caveat,
    )


__all__ = [
    "COUNT_CONTRACT_VERSION",
    "CountError",
    "MIN_SAMPLE_FOR_AGGREGATES",
    "assert_integrity",
    "count_all_partitions",
    "count_partition",
    "distribution",
    "integrity",
    "partition_of",
    "partition_population",
    "reconcile",
]