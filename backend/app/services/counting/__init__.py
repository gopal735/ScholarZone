"""ScholarZone Count Intelligence 2.0: a deterministic, auditable counting layer.

This package is the canonical source of truth for every business-facing number in
the product. It counts; it never scores.

The dividing line is strict and worth stating plainly:

* The **Match engine** decides. Eligibility, fit, confidence, coverage and readiness
  are its responsibility, and this layer consumes them as finished facts.
* The **counting engine** measures. It partitions, counts, facets, reconciles,
  explains and reports. It reads the engine's outputs and adds nothing of its own
  opinion about a student's fit.

One consequence worth noting: :mod:`app.services.matching.summaries` builds the
``MatchSummary`` *from this contract*, so the Match response and the intelligence
response cannot drift apart. That is enforced at import - a bucket the response has
no field for, or a field the contract does not declare, raises rather than silently
dropping a number.

Three universes, never merged:

``CATALOGUE``
    The canonical public catalogue, counted in SQL from stored rows.
``MATCH_ANALYSED``
    What Match 2.0 actually loaded, scored and gated for one profile.
``MATCH_RETURNED_PAGE``
    The truncated page. This is the basis facets describe, so a filter's count is
    never stale relative to the list it filters.

Module map, in dependency order:

``types``       The typed contract. Universes, partitions, provenance, integrity.
``contract``    The declarative definitions every other module reads.
``core``        The counting engine: count, partition, reconcile, aggregate.
``facets``      Facets, filter semantics, self-exclusion, reset identity.
``counterfactual``  One controlled change at a time; zero-result intelligence.
``catalogue``   Catalogue-universe counts, in one query.
``temporal``    Snapshot and trend support on existing stored history.
``anomalies``   Evidence-based anomaly detection and the integrity monitor.
``relationships`` Counts over verified and published relationships.
``incremental`` Change classification, with an honest full-recompute fallback.
``provenance``  Reproduction metadata and count explanation.
``service``     The impure boundary: session, ``as_of``, one assembled response.
"""

from .contract import COUNT_CONTRACT_VERSION, CountMetric, CountPartitionSpec
from .core import CountError, assert_integrity, count_partition, integrity, reconcile
from .facets import SELF_EXCLUSION_SEMANTICS, FilterState, build_facets
from .provenance import explain_count, provenance
from .types import (
    CountAlternative,
    CountAnomaly,
    CountBasis,
    CountBucket,
    CountExplanation,
    CountFilter,
    CountIncrement,
    CountIntegrity,
    CountPartition,
    CountProvenance,
    CountReconciliation,
    CountSnapshot,
    CountTrend,
    CountTrendPoint,
    CountUniverse,
    CounterfactualCounting,
    DistributionSummary,
    IncrementalOutcome,
    IntegrityStatus,
    NullPolicy,
    ProvenanceKind,
    RelationshipCount,
    UnknownPolicy,
)

__all__ = [
    "COUNT_CONTRACT_VERSION",
    "CountAlternative",
    "CountAnomaly",
    "CountBasis",
    "CountBucket",
    "CountError",
    "CountExplanation",
    "CountFilter",
    "CountIncrement",
    "CountIntegrity",
    "CountMetric",
    "CountPartition",
    "CountPartitionSpec",
    "CountProvenance",
    "CountReconciliation",
    "CountSnapshot",
    "CountTrend",
    "CountTrendPoint",
    "CountUniverse",
    "CounterfactualCounting",
    "DistributionSummary",
    "FilterState",
    "IncrementalOutcome",
    "IntegrityStatus",
    "NullPolicy",
    "ProvenanceKind",
    "RelationshipCount",
    "SELF_EXCLUSION_SEMANTICS",
    "UnknownPolicy",
    "assert_integrity",
    "build_facets",
    "count_partition",
    "explain_count",
    "integrity",
    "provenance",
    "reconcile",
]