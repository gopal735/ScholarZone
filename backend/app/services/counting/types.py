"""ScholarZone Count Intelligence 2.0: typed counting contracts.

Everything this layer returns is one of these types. The same discipline the Match
engine uses, for the same reason: a count that cannot be inspected cannot be
audited, and a count that cannot be named cannot be reconciled.

Three ideas are load-bearing here.

**Universe.** Every count names the set it describes. A catalogue total and a Match
total are different claims about different populations, and presenting one where
the reader expects the other is how a dashboard starts lying.

**Basis.** Summary counts describe the analysed universe; facet counts describe
the set the filter is applied to. The difference is recorded, not implied.

**Provenance.** Every number carries the versions, the ``as_of`` boundary and the
active predicates that produced it, so a stored count can be recomputed rather
than trusted.

Nothing in this module computes anything. These are the shapes; :mod:`core` fills
them and :mod:`contract` defines what each one means.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CountUniverse(StrEnum):
    """Which population a count describes.

    The three canonical universes are kept separate rather than merged, because
    merging them is exactly how a catalogue total ends up presented as a Match
    total.

    ``CATALOGUE``
        The canonical public scholarship catalogue: every record that
        ``public_visibility_conditions()`` permits to be shown.
    ``SEARCH_FILTER``
        The catalogue after the directory's search and filter predicates.
    ``MATCH_ANALYSED``
        The candidates Match 2.0 actually loaded, scored and gated for one
        profile. Profile-dependent by definition.
    ``MATCH_RETURNED_PAGE``
        The ranked subset of ``MATCH_ANALYSED`` that was returned, after
        truncation to the requested page size. This is the basis facets describe.
    """

    CATALOGUE = "CATALOGUE"
    SEARCH_FILTER = "SEARCH_FILTER"
    MATCH_ANALYSED = "MATCH_ANALYSED"
    MATCH_RETURNED_PAGE = "MATCH_RETURNED_PAGE"


class CountBasis(StrEnum):
    """Which set a group of counts reconciles against.

    ``COMPLETE``
        The buckets partition the universe exactly. Their sum must equal the
        universe size, and a violation is a defect.
    ``PARTIAL``
        Some members of the universe have no value for this dimension and are
        absent rather than misfiled. The sum may be less than the universe size
        and must never be more.
    ``NOT_A_PARTITION``
        Independent measures over the same universe. Their sum is not meaningful
        and is never asserted.
    """

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NOT_A_PARTITION = "NOT_A_PARTITION"


class NullPolicy(StrEnum):
    """What happens to a record whose value for a metric is absent.

    The default and the only defensible default is ``EXCLUDED_AND_REPORTED``: an
    absent value is an absence, it is never silently counted as the lowest bucket,
    and the count of how many were absent is itself published.
    """

    EXCLUDED_AND_REPORTED = "EXCLUDED_AND_REPORTED"


class UnknownPolicy(StrEnum):
    """How a *known-unknown* is handled, as distinct from an absent value.

    ``OWN_BUCKET``
        Unknown is published as its own bucket, so it can never be confused with
        a measured value.
    ``FOLDED_INTO_LOWEST``
        Unknown is counted with the lowest measured band. Only permitted where the
        count contract says so explicitly, and never by default.
    """

    OWN_BUCKET = "OWN_BUCKET"
    FOLDED_INTO_LOWEST = "FOLDED_INTO_LOWEST"


class ProvenanceKind(StrEnum):
    """How a reported number came to exist.

    The interface must be able to say which of these a number is, because they
    carry very different weight and must never be summed together.
    """

    #: Counted from stored catalogue rows.
    OBSERVED = "OBSERVED"
    #: Computed from observed values by declared arithmetic.
    DERIVED = "DERIVED"
    #: Recomputed under a hypothetical change. Not an observation.
    SIMULATED = "SIMULATED"
    #: Read from a real stored snapshot at an earlier date.
    HISTORICAL = "HISTORICAL"
    #: Cannot be produced from available evidence. Never a zero.
    UNAVAILABLE = "UNAVAILABLE"


class IntegrityStatus(StrEnum):
    """The outcome of checking a set of counts against itself."""

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


# ---------------------------------------------------------------------------
# Primitives
# ---------------------------------------------------------------------------


class CountFilter(StrEnum):
    """The dimensions a filter state may constrain.

    Each names a predicate that already exists in the Match engine or the
    directory repository. No filter is defined here that the engine does not
    already evaluate.
    """

    COUNTRY = "COUNTRY"
    REGION = "REGION"
    DEGREE = "DEGREE"
    FIELD = "FIELD"
    FUNDING = "FUNDING"
    ELIGIBILITY = "ELIGIBILITY"
    FIT = "FIT"
    CONFIDENCE = "CONFIDENCE"
    COVERAGE = "COVERAGE"
    READINESS = "READINESS"
    DEADLINE = "DEADLINE"


class CountBucket(BaseModel):
    """One bucket of a count partition.

    ``key`` is the canonical machine value and ``label`` is the display string.
    A label is never derived from a key by title-casing: a country and a degree
    are already written for a reader, and restyling text ScholarZone did not
    author is how "PhD" becomes "Phd".
    """

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    count: int
    #: Records in this bucket that could not be evaluated for the dimension, when
    #: the contract publishes an unknown state separately.
    is_unknown: bool = False


class CountReconciliation(BaseModel):
    """One asserted identity over a set of counts.

    ``holds`` is the verdict. ``observed`` and ``expected`` are both published so
    a failure is diagnosable from the response alone rather than from a stack
    trace.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    expression: str
    observed: int
    expected: int
    holds: bool


class CountProvenance(BaseModel):
    """Everything needed to reproduce a set of counts.

    Sufficient on its own: given these values and the same stored data, the same
    numbers must come back.
    """

    model_config = ConfigDict(frozen=True)

    count_basis: CountBasis
    universe: CountUniverse
    #: The exact predicates active when the counts were produced.
    filter_state: dict[str, list[str]] = Field(default_factory=dict)
    #: ``None`` only where the count has no date dependence at all, which is
    #: reported rather than assumed.
    as_of: str | None = None
    as_of_dependency: bool = False

    engine_version: str | None = None
    scoring_config_version: str | None = None
    field_taxonomy_version: str | None = None
    deadline_semantics_version: str | None = None
    count_contract_version: str
    #: Contract versions the count depends on, so a dependency change is visible
    #: without reading the whole configuration.
    depends_on: tuple[str, ...] = ()

    #: How each reported number was obtained. Never summed across kinds.
    value_kinds: dict[str, ProvenanceKind] = Field(default_factory=dict)


class CountPartition(BaseModel):
    """A named group of buckets that partitions some part of a universe."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    basis: CountBasis
    buckets: list[CountBucket]
    #: Sum of the published buckets. For a COMPLETE partition this equals the
    #: universe size; for a PARTIAL one it is smaller by exactly the number of
    #: records with no value.
    bucket_total: int
    #: Records in the universe that produced no bucket.
    unclassified_count: int = 0
    #: Human-readable statement of what this partition counts and what it omits.
    note: str = ""


class CountIntegrity(BaseModel):
    """A first-class integrity verdict.

    ``PASS`` when every asserted identity holds. ``WARNING`` when the counts are
    internally consistent but some evidence was unavailable, so a reader knows
    the numbers are sound but incomplete. ``FAIL`` when they contradict each
    other, which the interface must never render as if it did not.
    """

    model_config = ConfigDict(frozen=True)

    status: IntegrityStatus
    reconciliations: list[CountReconciliation] = Field(default_factory=list)
    #: Machine-readable reasons behind a WARNING or FAIL.
    issues: list[str] = Field(default_factory=list)


class CountExplanationLine(BaseModel):
    """One machine-readable clause of a count's derivation."""

    model_config = ConfigDict(frozen=True)

    dimension: str
    operator: str
    value: str


class CountExplanation(BaseModel):
    """Why a count is what it is, in both readable and reproducible form.

    ``human_readable`` is one sentence that names the universe and the conditions.
    ``clauses`` is the same statement as ordered predicates, so the count can be
    recomputed rather than believed.
    """

    model_config = ConfigDict(frozen=True)

    count: int
    human_readable: str
    clauses: list[CountExplanationLine] = Field(default_factory=list)


class DistributionSummary(BaseModel):
    """Descriptive aggregates over one numeric dimension.

    Every aggregate publishes its own sample size and its null-exclusion policy.
    An average without its sample count is a number about nothing, and an average
    over three records presented next to an average over three thousand invites a
    comparison the data cannot support.
    """

    model_config = ConfigDict(frozen=True)

    universe: CountUniverse
    dimension: str
    #: Records with a measured value on this dimension.
    sample_count: int
    #: Records in the universe with no value, excluded from every aggregate.
    excluded_count: int
    minimum: float | None = None
    maximum: float | None = None
    mean: float | None = None
    median: float | None = None
    #: Below this sample size the aggregates are not published as usable summary
    #: statistics, and ``caveat`` explains why.
    caveat: str = ""


class CountAlternative(BaseModel):
    """One way out of a zero-result state.

    Every field is a measurement. ``result_count`` was produced by applying the
    stated change to the same candidate universe and re-running the same filter
    logic; nothing here is a prediction that relaxing a filter "might" help, and an
    alternative that produces no results is not offered at all.
    """

    model_config = ConfigDict(frozen=True)

    #: The single dimension changed. Exactly one, always.
    changed_dimension: str
    #: Human-readable statement of the change, e.g. "Remove \\"Degree\\"".
    change_label: str
    #: The value that would be applied, or ``None`` for "remove the constraint".
    proposed_value: str | None = None
    removed_value: str | None = None
    #: Results produced by this change, over the same universe.
    result_count: int
    #: True when this is a removal of an active constraint rather than a new value.
    is_removal: bool = False


class CounterfactualCounting(BaseModel):
    """A deterministic recomputation under one controlled change.

    This is arithmetic on stored facts, not causal inference. ``delta`` is the
    difference between two counts of the same universe under two stated conditions.
    It is never a treatment effect, a probability, or an expected outcome, and the
    published ``disclaimer`` says so in the payload rather than relying on every
    caller to remember.
    """

    model_config = ConfigDict(frozen=True)

    #: What was counted, e.g. "eligible scholarships".
    metric: str
    baseline_count: int
    counterfactual_count: int
    delta: int
    changed_dimension: str
    #: The filter or profile state before and after, so the change is auditable.
    baseline_state: dict[str, list[str]] = Field(default_factory=dict)
    counterfactual_state: dict[str, list[str]] = Field(default_factory=dict)
    #: ``SIMULATED`` always. Never ``OBSERVED``: nothing was observed, it was
    #: recomputed.
    value_kind: ProvenanceKind = ProvenanceKind.SIMULATED
    disclaimer: str = (
        "Deterministic recomputation over the same candidate universe. Not a causal "
        "effect, not a probability, not a prediction of success."
    )


class CountIncrement(BaseModel):
    """One conceptual change to the candidate set.

    The incremental-counting abstraction. A delta is *classified* before it is
    applied: a change whose effect cannot be determined from the previous state is
    recorded with ``requires_full_recompute`` set, and the caller recomputes rather
    than guessing at a counter's new value.
    """

    model_config = ConfigDict(frozen=True)

    change_type: str
    scholarship_id: int
    detail: str = ""
    #: True when this change cannot be applied to a running counter safely.
    requires_full_recompute: bool = False
    #: Why a full recomputation is required, when it is.
    reason: str = ""


class IncrementalOutcome(BaseModel):
    """The result of applying increments to a previous count set.

    ``strategy`` is published rather than implied. ``FULL_RECOMPUTE`` is a success
    state, not an admission of failure: it is the documented fallback whenever an
    increment cannot be applied safely, and it is the correct answer far more often
    than an O(1) update.
    """

    model_config = ConfigDict(frozen=True)

    strategy: str
    #: Partitions updated from deltas.
    updated_partitions: list[str] = Field(default_factory=list)
    #: Partitions left alone because an increment could not be applied.
    recomputed_partitions: list[str] = Field(default_factory=list)
    increments: list[CountIncrement] = Field(default_factory=list)
    #: Present only when a recomputation happened, and then authoritative.
    recomputed_summary: dict | None = None
    note: str = ""


class CountSnapshot(BaseModel):
    """A reproducible statement of the counts at one moment.

    Enough to recompute rather than trust. When the historical state behind a
    snapshot does not exist, the snapshot is ``NOT_AVAILABLE`` and no figures are
    published - an invented history is worse than an absent one.
    """

    model_config = ConfigDict(frozen=True)

    #: ``AVAILABLE`` or ``NOT_AVAILABLE``.
    availability: str
    as_of: str
    #: Identifier for the catalogue state, where one can be established.
    catalogue_state_id: str | None = None
    engine_version: str | None = None
    scoring_config_version: str | None = None
    field_taxonomy_version: str | None = None
    deadline_semantics_version: str | None = None
    count_contract_version: str
    #: True only when the figures are read from stored evidence.
    summary: dict | None = None
    facets: dict | None = None
    #: Why a snapshot could not be produced.
    unavailable_reason: str = ""


class CountTrendPoint(BaseModel):
    """One observation in a count trend."""

    model_config = ConfigDict(frozen=True)

    as_of: str
    value: int
    #: True when read from a stored snapshot. False means the point was derived.
    is_historical: bool


class CountTrend(BaseModel):
    """A trend over a named metric.

    ``availability`` is ``NOT_AVAILABLE`` when no real observations exist. No trend
    is ever drawn from invented points, so a trend over one snapshot is reported as
    unavailable rather than as a flat line, which would read as "stable".
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    availability: str
    dimension: str | None = None
    points: list[CountTrendPoint] = Field(default_factory=list)
    change: int | None = None
    change_percent: float | None = None
    unavailable_reason: str = ""
    note: str = ""


class CountAnomaly(BaseModel):
    """One detected anomaly in the counts themselves.

    Every field is required by the contract: a detection without a baseline, a
    method and a severity is an opinion, and an unexplained number on a dashboard
    is how a data problem becomes a product decision.
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    current_value: float | int | None
    baseline: float | int | None
    delta: float | int | None = None
    #: The named method that fired, e.g. ``ABSOLUTE_DELTA`` or ``RECONCILIATION``.
    detection_method: str
    severity: str
    explanation: str
    #: False where the method could not be evaluated, e.g. no baseline exists.
    is_baseline_available: bool = True


class RelationshipCount(BaseModel):
    """Counts over verified relationships between catalogue records.

    Built only from structured evidence: a shared published funder, a shared
    published university, a curated taxonomy relationship. Never from name
    similarity, and never from a graph database.
    """

    model_config = ConfigDict(frozen=True)

    relationship: str
    #: The entity the count is grouped by.
    entity_key: str
    entity_label: str
    #: Scholarships sharing this entity.
    count: int
    #: The evidence the relationship was derived from.
    evidence_source: str
    #: False where the relationship was inferred rather than published.
    is_verified: bool = True


__all__ = [
    "CountAlternative",
    "CountAnomaly",
    "CountBasis",
    "CountBucket",
    "CountExplanation",
    "CountExplanationLine",
    "CountFilter",
    "CountIncrement",
    "CountIntegrity",
    "CountPartition",
    "CountProvenance",
    "CountReconciliation",
    "CountSnapshot",
    "CountTrend",
    "CountTrendPoint",
    "CountUniverse",
    "CounterfactualCounting",
    "DistributionSummary",
    "IncrementalOutcome",
    "IntegrityStatus",
    "NullPolicy",
    "ProvenanceKind",
    "RelationshipCount",
    "UnknownPolicy",
]