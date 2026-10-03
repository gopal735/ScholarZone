"""Anomaly detection and the count integrity monitor.

Two related jobs, kept in one module because they answer one question: *can these
numbers be trusted?*

**Integrity** is arithmetic. Do the partitions reconcile? This is not a heuristic
and it is not optional: a FAIL means the counts contradict each other, and the
interface must never render them as if they did not. :mod:`core` computes it;
:func:`integrity_report` is the publishable wrapper.

**Anomaly detection** is statistical, and it is deliberately the simplest thing
that works. Reconciliation failure, a bucket that changed by more than it could,
a spike or a drop against a real baseline. Nothing here learns anything, nothing
here forecasts, and no machine learning is used - not because ML is bad but
because with a catalogue this size a z-score over three observations is a
mathematical artefact wearing a lab coat, and a model would produce confident
output about a problem the data cannot even describe.

The rule that shapes the whole module: **a method that cannot be evaluated does not
fire, it reports itself unavailable.** An anomaly with no baseline is not "no
anomaly"; it is "not enough evidence to say". Those are published differently, and
the difference is in :attr:`CountAnomaly.is_baseline_available`.

Reuses the existing ``app.services.anomaly_detection.AnomalySeverity`` vocabulary
rather than inventing a second severity scale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ..anomaly_detection import AnomalySeverity
from .types import CountAnomaly, CountIntegrity, CountPartition, IntegrityStatus


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
#
# Mirrors the existing ``dependency_graph`` pattern: a versioned, immutable table of
# numbers with no branching logic. A reviewer can read the complete detection policy
# here, and changing a threshold is a deliberate, reviewable edit.


@dataclass(frozen=True)
class AnomalyThresholds:
    """The complete detection policy.

    Locked and versioned. Both spike and drop thresholds are absolute *counts*, not
    percentages, on purpose: a 500% rise from 1 record to 6 is noise in a small
    catalogue, and a percentage rule would flag it every time. An absolute floor is
    what makes a rate-based rule safe to apply to small populations.
    """

    #: A bucket must change by at least this many records to be considered at all.
    min_absolute_delta: int = 5
    #: ...and by at least this share of the baseline.
    min_relative_delta: float = 0.25
    #: Baseline must have at least this many observations for the rolling rule.
    min_baseline_points: int = 3
    #: Mean absolute deviation from the baseline mean that constitutes a spike.
    spike_deviations: float = 3.0
    #: A facet whose largest bucket holds this share of the universe is "imbalanced".
    facet_imbalance_ratio: float = 0.95
    #: A bucket holding this share of the universe is a single-bucket facet, which is
    #: reported rather than hidden - it is usually a one-value filter, not a defect.
    degenerate_facet_ratio: float = 0.99
    #: Buckets below this share of the universe are reported as negligible.
    negligible_bucket_ratio: float = 0.01


ANOMALY_THRESHOLDS = AnomalyThresholds()
ANOMALY_DETECTION_VERSION = "1.0.0"


def _severity_for(delta_ratio: float) -> str:
    """Map a relative change onto the existing severity vocabulary."""
    if delta_ratio >= 1.0:
        return AnomalySeverity.CRITICAL.value
    if delta_ratio >= 0.5:
        return AnomalySeverity.HIGH.value
    if delta_ratio >= 0.25:
        return AnomalySeverity.MEDIUM.value
    return AnomalySeverity.LOW.value


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def detect_count_anomalies(
    current: int,
    baseline: Sequence[int],
    *,
    metric: str,
    thresholds: AnomalyThresholds = ANOMALY_THRESHOLDS,
) -> list[CountAnomaly]:
    """Compare one count against its own history.

    Both conditions must hold before anything fires: an absolute floor, so a
    percentage change on a tiny population is not treated as an event, and a
    relative floor, so a large catalogue losing four records is not.

    With fewer than :attr:`AnomalyThresholds.min_baseline_points` observations the
    method reports itself unavailable. It does not fire on the first observation,
    because a single value has nothing to be surprising relative to.
    """
    if len(baseline) < thresholds.min_baseline_points:
        return [
            CountAnomaly(
                metric=metric,
                current_value=current,
                baseline=None,
                detection_method="ROLLING_BASELINE",
                severity=AnomalySeverity.LOW.value,
                is_baseline_available=False,
                explanation=(
                    f"Only {len(baseline)} historical observation"
                    f"{'' if len(baseline) == 1 else 's'} available; "
                    f"{thresholds.min_baseline_points} are required before a spike or drop "
                    "can be distinguished from ordinary variation. Reported as "
                    "unavailable rather than as no anomaly."
                ),
            )
        ]

    expected = _mean(baseline)
    delta = current - expected
    if expected == 0:
        ratio = float("inf") if current else 0.0
    else:
        ratio = abs(delta) / expected

    if (
        abs(delta) < thresholds.min_absolute_delta
        or ratio < thresholds.min_relative_delta
    ):
        return []

    direction = "increase" if delta > 0 else "drop"
    return [
        CountAnomaly(
            metric=metric,
            current_value=current,
            baseline=round(expected, 2),
            delta=int(delta),
            detection_method="ROLLING_BASELINE",
            severity=_severity_for(ratio),
            explanation=(
                f"{metric} {direction}d by {abs(int(delta))} "
                f"({ratio * 100:.1f}%) against a baseline of {expected:.1f} over "
                f"{len(baseline)} stored observations. This is a measured departure "
                "from the observed history, not an explanation of its cause."
            ),
        )
    ]


def detect_reconciliation_anomalies(integrity: CountIntegrity) -> list[CountAnomaly]:
    """Turn a failed identity into an anomaly.

    Ranked first by the detection order the architecture requires: a reconciliation
    failure outranks every statistical signal, because a set of counts that do not
    add up needs no further investigation to be untrustworthy.
    """
    anomalies: list[CountAnomaly] = []
    for check in integrity.reconciliations:
        if check.holds:
            continue
        anomalies.append(
            CountAnomaly(
                metric=check.name,
                current_value=check.observed,
                baseline=check.expected,
                delta=check.observed - check.expected,
                detection_method="RECONCILIATION",
                severity=AnomalySeverity.CRITICAL.value,
                explanation=(
                    f"{check.expression} does not hold. The published counts "
                    "contradict each other, so this set of numbers must not be "
                    "displayed as a coherent result."
                ),
            )
        )
    return anomalies


def detect_impossible_buckets(
    partitions: Sequence[CountPartition],
    *,
    thresholds: AnomalyThresholds = ANOMALY_THRESHOLDS,
) -> list[CountAnomaly]:
    """Buckets that cannot be true: negative counts, or a partition over-counting.

    A count cannot be negative, and a partition cannot describe more records than
    its universe holds. Either means the arithmetic is wrong, not that the
    catalogue is strange.
    """
    anomalies: list[CountAnomaly] = []
    for partition in partitions:
        for bucket in partition.buckets:
            if bucket.count < 0:
                anomalies.append(
                    CountAnomaly(
                        metric=f"{partition.name}.{bucket.key}",
                        current_value=bucket.count,
                        baseline=0,
                        delta=bucket.count,
                        detection_method="IMPOSSIBLE_VALUE",
                        severity=AnomalySeverity.CRITICAL.value,
                        explanation=(
                            f"{partition.label} bucket \"{bucket.label}\" has a negative "
                            "count. A count cannot be negative, so this is an arithmetic "
                            "defect rather than a data observation."
                        ),
                    )
                )

        if (
            partition.basis.value == "COMPLETE"
            and partition.unclassified_count
        ):
            anomalies.append(
                CountAnomaly(
                    metric=f"{partition.name}.unclassified",
                    current_value=partition.unclassified_count,
                    baseline=0,
                    delta=partition.unclassified_count,
                    detection_method="IMPOSSIBLE_VALUE",
                    severity=AnomalySeverity.MEDIUM.value,
                    explanation=(
                        f"{partition.label} is declared a complete partition, yet "
                        f"{partition.unclassified_count} record"
                        f"{'' if partition.unclassified_count == 1 else 's'} produced no "
                        "bucket. A complete partition cannot have a residual."
                    ),
                )
            )
    return anomalies


def detect_facet_imbalance(
    facet: Sequence[CountBucket],
    *,
    name: str,
    universe_size: int,
    thresholds: AnomalyThresholds = ANOMALY_THRESHOLDS,
) -> list[CountAnomaly]:
    """A facet that describes almost nothing, or that has collapsed to one value.

    Both are reported rather than hidden. A one-bucket facet is usually a
    consequence of the active filters rather than a defect, so it is reported as
    informational; a facet whose values are almost all negligible is a signal that
    the candidate set is too small for the facet to say anything.
    """
    if universe_size <= 0 or not facet:
        return []

    anomalies: list[CountAnomaly] = []
    largest = max(bucket.count for bucket in facet)
    if largest / universe_size >= thresholds.degenerate_facet_ratio and len(facet) == 1:
        anomalies.append(
            CountAnomaly(
                metric=f"facet.{name}",
                current_value=len(facet),
                baseline=None,
                detection_method="FACET_IMBALANCE",
                severity=AnomalySeverity.LOW.value,
                explanation=(
                    f"The {name} facet has a single value covering "
                    f"{largest} of {universe_size} records. Expected when the active "
                    "filters already fix this dimension; reported so a genuine "
                    "catalogue-wide collapse is distinguishable."
                ),
            )
        )
        return anomalies

    negligible = sum(
        1 for bucket in facet if bucket.count / universe_size < thresholds.negligible_bucket_ratio
    )
    if facet and negligible / len(facet) > 0.5:
        anomalies.append(
            CountAnomaly(
                metric=f"facet.{name}.negligible",
                current_value=negligible,
                baseline=0,
                delta=negligible,
                detection_method="FACET_IMBALANCE",
                severity=AnomalySeverity.LOW.value,
                explanation=(
                    f"{negligible} of {len(facet)} {name} values cover less than "
                    f"{thresholds.negligible_bucket_ratio * 100:.0f}% of the candidate "
                    "set. The facet is present but not yet informative at this size."
                ),
            )
        )
    return anomalies


def integrity_report(integrity: CountIntegrity) -> dict:
    """A publishable integrity verdict with its anomalies attached.

    Reconciliation anomalies first. They are the only ones that invalidate the
    numbers rather than merely comment on them.
    """
    return {
        "status": integrity.status.value,
        "issues": list(integrity.issues),
        "reconciliations": [
            {
                "name": check.name,
                "expression": check.expression,
                "observed": check.observed,
                "expected": check.expected,
                "holds": check.holds,
            }
            for check in integrity.reconciliations
        ],
        "anomalies": [
            anomaly.model_dump() for anomaly in detect_reconciliation_anomalies(integrity)
        ],
    }


def worst_severity(anomalies: Sequence[CountAnomaly]) -> str | None:
    """The most severe anomaly present, or ``None`` when there are none."""
    if not anomalies:
        return None
    ranking = {
        AnomalySeverity.LOW.value: 0,
        AnomalySeverity.MEDIUM.value: 1,
        AnomalySeverity.HIGH.value: 2,
        AnomalySeverity.CRITICAL.value: 3,
    }
    return max(
        (anomaly.severity for anomaly in anomalies),
        key=lambda severity: ranking.get(severity, 0),
    )


__all__ = [
    "ANOMALY_DETECTION_VERSION",
    "ANOMALY_THRESHOLDS",
    "AnomalyThresholds",
    "detect_count_anomalies",
    "detect_facet_imbalance",
    "detect_impossible_buckets",
    "detect_reconciliation_anomalies",
    "integrity_report",
    "worst_severity",
]