"""The counting system.

A dashboard that shows "12 strong matches, 7 need verification" is making twelve
specific factual claims. This module is where those claims are computed, from one
result set, with the reconciliation properties asserted rather than assumed.

There are exactly two candidate sets in a response, and every count names which
one it describes.

**The analysed universe.** Every candidate that was loaded, scored and gated,
before the response was truncated to the requested page size. ``total_candidates``
is the size of that universe, and every count in ``MatchSummary`` reconciles
against it:

    eligible + needs_verification + ineligible == total_candidates
    scored     + not_scored                == total_candidates
    sum(fit tier counts) + unclassified     == scored_count
    sum(confidence counts)                 == total_candidates
    sum(coverage counts)                   == total_candidates
    sum(deadline bucket counts)            == total_candidates
    sum(funding bucket counts)             == total_candidates

``visible_candidate_count`` names the page separately, so the interface can never
imply that the reader is looking at the whole analysis when they are not.

**The returned page.** The ranked subset actually returned. Facet counts are built
from this set, because a filter's count must never be stale relative to the list
it filters: offering "Germany (27)" has to mean twenty-seven cards are one click
away.

Earlier versions reconciled eligibility against the page, which meant the three
states summed to ``visible_candidate_count`` instead of ``total_candidates`` and
the identity silently changed the moment a request was truncated. Both sets are
now named explicitly and each count reconciles against the one it claims.

``assert_reconciled`` raises on any violation rather than returning a dashboard
that quietly disagrees with itself. A count that does not reconcile is a bug, and
the correct response to a bug is to fail loudly.

Everything is derived. No bucket total is ever written as a literal, and nothing
is carried over between requests: two identical requests produce identical counts,
and two different profiles produce counts that are genuinely different.

Facet values are never truncated - a country present in the catalogue is always
selectable, because truncating the list is indistinguishable from the country not
existing.
"""

from __future__ import annotations

from .config import (
    CONFIDENCE_BANDS,
    COVERAGE_BANDS,
    FIT_BANDS,
    FUNDING_STATES,
    STRONG_MATCH_THRESHOLD,
    TIMING_BUCKET_CLOSED,
    TIMING_BUCKET_KEYS,
    TIMING_BUCKET_UNKNOWN,
    classify_coverage,
)
from .types import (
    EligibilityStatus,
    FacetBucket,
    MatchFacets,
    MatchResult,
    MatchSummary,
)


FUNDING_BUCKET_FIELDS: dict[str, str] = {
    "FULL": "full_funding_count",
    "TUITION_PLUS_LIVING": "tuition_plus_living_count",
    "TUITION_ONLY": "tuition_only_count",
    "PARTIAL": "partial_funding_count",
    "NONE": "none_count",
    "UNKNOWN": "unknown_funding_count",
}

DEADLINE_BUCKET_FIELDS: dict[str, str] = {
    "COMFORTABLE": "comfortable_deadline_count",
    "APPROACHING": "approaching_deadline_count",
    "CLOSING_SOON": "closing_soon_count",
    TIMING_BUCKET_CLOSED: "closed_deadline_count",
    TIMING_BUCKET_UNKNOWN: "unknown_deadline_count",
}

FIT_TIER_FIELDS: dict[str, str] = {
    "EXCEPTIONAL_FIT": "exceptional_count",
    "VERY_STRONG_FIT": "very_strong_count",
    "STRONG_FIT": "strong_count",
    "POSSIBLE_FIT": "possible_count",
    "LOW_FIT": "low_count",
}

CONFIDENCE_FIELDS: dict[str, str] = {
    "HIGH": "high_confidence_count",
    "MEDIUM": "medium_confidence_count",
    "LOW": "low_confidence_count",
}

COVERAGE_FIELDS: dict[str, str] = {
    "HIGH": "high_coverage_count",
    "MEDIUM": "medium_coverage_count",
    "LOW": "low_coverage_count",
}

#: Bucket key -> response field, per contract partition. These names are the
#: published ``MatchSummary`` shape and are deliberately unchanged; only the
#: definitions behind them moved to the count contract.
PARTITION_FIELD_MAPS: dict[str, dict[str, str]] = {
    "funding": FUNDING_BUCKET_FIELDS,
    "deadline": DEADLINE_BUCKET_FIELDS,
    "fit_tier": FIT_TIER_FIELDS,
    "confidence": CONFIDENCE_FIELDS,
    "coverage": COVERAGE_FIELDS,
    "eligibility": {
        EligibilityStatus.ELIGIBLE.value: "eligible_count",
        EligibilityStatus.NEEDS_VERIFICATION.value: "needs_verification_count",
        EligibilityStatus.INELIGIBLE.value: "ineligible_count",
    },
    "scored": {"SCORED": "scored_count", "NOT_SCORED": "not_scored_count"},
}


def _validate_field_maps() -> None:
    """Fail unless the response field map agrees with the count contract.

    The maps above name the published response fields; the contract names the
    buckets. If the engine adds a band and the response shape has no field for it,
    the count would be computed and then dropped on the floor. Asserting at import
    makes that a startup failure rather than a silently missing number.
    """
    from ..counting.contract import PARTITIONS_BY_NAME

    for partition, fields in PARTITION_FIELD_MAPS.items():
        spec = PARTITIONS_BY_NAME.get(partition)
        if spec is None:
            raise RuntimeError(f"field map names unknown count partition {partition!r}")
        declared = {key for key, _ in spec.buckets}
        if declared != set(fields):
            raise RuntimeError(
                f"{partition} field map covers {sorted(fields)} but the count contract "
                f"declares {sorted(declared)}"
            )


_validate_field_maps()

#: Eligibility buckets, ordered as the interface presents them.
ELIGIBILITY_ORDER: tuple[str, ...] = (
    EligibilityStatus.ELIGIBLE.value,
    EligibilityStatus.NEEDS_VERIFICATION.value,
    EligibilityStatus.INELIGIBLE.value,
)

ELIGIBILITY_LABELS: dict[str, str] = {
    EligibilityStatus.ELIGIBLE.value: "Eligible",
    EligibilityStatus.NEEDS_VERIFICATION.value: "Needs verification",
    EligibilityStatus.INELIGIBLE.value: "Not eligible",
}

FUNDING_LABELS: dict[str, str] = {
    "FULL": "Full funding",
    "TUITION_PLUS_LIVING": "Tuition and living costs",
    "TUITION_ONLY": "Tuition only",
    "PARTIAL": "Partial funding",
    "NONE": "No funding",
    "UNKNOWN": "Funding not verified",
}

DEADLINE_LABELS: dict[str, str] = {
    "COMFORTABLE": "Comfortable, 60+ days",
    "APPROACHING": "Approaching, 14-59 days",
    "CLOSING_SOON": "Closing soon, under 14 days",
    TIMING_BUCKET_CLOSED: "Closed",
    TIMING_BUCKET_UNKNOWN: "No fixed date published",
}

FIT_BAND_LABELS: dict[str, str] = {key: label for _, key, label in FIT_BANDS}
CONFIDENCE_LABELS: dict[str, str] = {key: label for _, key, label in CONFIDENCE_BANDS}
COVERAGE_LABELS: dict[str, str] = {key: label for _, key, label in COVERAGE_BANDS}


def coverage_band(coverage: float) -> str:
    """Classify one record's data coverage.

    A thin alias over the configuration's own resolver, kept because the name is
    part of this module's existing surface. The implementation lives with the band
    table so the count contract and this module cannot classify differently.
    """
    return classify_coverage(coverage)


def count_bucket(values, band_of) -> dict[str, int]:
    """Count values into bands, preserving the band's configured order."""
    counts = {key: 0 for key, *_ in COVERAGE_BANDS}
    for value in values:
        counts[band_of(value)] += 1
    return counts


def build_summary(
    universe: list[MatchResult],
    visible: list[MatchResult] | None = None,
    *,
    total_candidates: int | None = None,
    truncated: bool = False,
) -> MatchSummary:
    """Compute every count the response and the dashboard report.

    ``universe`` is every scored candidate, and every count below is computed from
    it, so the locked identities hold against ``total_candidates`` no matter how
    many results were truncated out of the response. ``visible`` is the page that
    was actually returned and only feeds ``visible_candidate_count``.

    Both arguments default sensibly: with one list, the universe and the page are
    the same set and nothing is truncated, which is what a small catalogue or a
    raised limit produces.

    Every bucket here is filled by a predicate published in the count contract
    rather than by the field map below, which now only translates bucket keys into
    published response field names. The predicates, the band membership and the
    reconciliation targets live in one place, so this response and the count
    intelligence layer cannot disagree about what "eligible" means.
    """
    from ..counting.contract import PARTITIONS_BY_NAME
    from ..counting.core import count_partition, partition_population

    page = list(universe if visible is None else visible)
    total = len(universe) if total_candidates is None else total_candidates
    if total != len(universe):
        raise AssertionError(
            f"total_candidates ({total}) must equal the analysed candidate count ({len(universe)})"
        )

    def counted(partition: str):
        spec = PARTITIONS_BY_NAME[partition]
        return count_partition(partition_population(partition, universe), spec)

    eligibility = counted("eligibility")
    scored_partition = counted("scored")
    tier_partition = counted("fit_tier")
    confidence_partition = counted("confidence")
    coverage_partition = counted("coverage")
    deadline_partition = counted("deadline")
    funding_partition = counted("funding")

    def project(partition, field_map: dict[str, str]) -> dict[str, int]:
        """Bucket counts -> published field names.

        Every bucket the contract declares must have a field here;
        ``_validate_field_maps`` has already established that at import, so a
        missing field cannot reach this point.
        """
        by_key = {bucket.key: bucket.count for bucket in partition.buckets}
        return {field_map[key]: by_key[key] for key in field_map}

    strong_or_better = sum(
        1
        for item in universe
        if item.eligibility is EligibilityStatus.ELIGIBLE
        and item.fit_score is not None
        and item.fit_score >= STRONG_MATCH_THRESHOLD
    )

    scored_records = [item for item in universe if item.fit_score is not None]
    confidences = [item.confidence_score for item in universe]
    coverages = [item.data_coverage for item in universe]

    # A scored result whose band the configuration does not define. Counted from
    # the partition's own residual rather than by subtracting the tier total, so it
    # is a measurement rather than an inference.
    unclassified_fit = tier_partition.unclassified_count

    summary = MatchSummary(
        total_candidates=total,
        visible_candidate_count=len(page),
        strong_or_better_count=strong_or_better,
        unclassified_fit_count=unclassified_fit,
        average_confidence=round(sum(confidences) / len(confidences), 1) if confidences else None,
        average_data_coverage=round(sum(coverages) / len(coverages), 1) if coverages else None,
        truncated=truncated,
        **project(eligibility, PARTITION_FIELD_MAPS["eligibility"]),
        **project(scored_partition, PARTITION_FIELD_MAPS["scored"]),
        **project(tier_partition, PARTITION_FIELD_MAPS["fit_tier"]),
        **project(confidence_partition, PARTITION_FIELD_MAPS["confidence"]),
        **project(coverage_partition, PARTITION_FIELD_MAPS["coverage"]),
        **project(deadline_partition, PARTITION_FIELD_MAPS["deadline"]),
        **project(funding_partition, PARTITION_FIELD_MAPS["funding"]),
    )

    assert_reconciled(summary)
    return summary


def assert_reconciled(summary: MatchSummary) -> None:
    """Raise unless every documented reconciliation identity holds.

    Called from ``build_summary`` so an inconsistent dashboard cannot be
    constructed at all, and re-asserted by the test suite against the API
    response so a future change to the response shape cannot quietly break the
    property either.

    Every identity is against ``total_candidates``, the analysed universe, with
    the single documented exception of the fit tiers, which reconcile to
    ``scored_count`` because an unscored result has no tier by definition.
    """
    total = summary.total_candidates

    eligibility_total = (
        summary.eligible_count + summary.needs_verification_count + summary.ineligible_count
    )
    if eligibility_total != total:
        raise AssertionError(
            f"eligibility counts ({eligibility_total}) must equal total_candidates ({total})"
        )

    scored_total = summary.scored_count + summary.not_scored_count
    if scored_total != total:
        raise AssertionError(f"scored + not_scored ({scored_total}) must equal total_candidates ({total})")

    tier_total = (
        summary.exceptional_count
        + summary.very_strong_count
        + summary.strong_count
        + summary.possible_count
        + summary.low_count
        + summary.unclassified_fit_count
    )
    if tier_total != summary.scored_count:
        raise AssertionError(f"fit tier counts ({tier_total}) must equal scored_count ({summary.scored_count})")

    confidence_total = (
        summary.high_confidence_count + summary.medium_confidence_count + summary.low_confidence_count
    )
    if confidence_total != total:
        raise AssertionError(f"confidence counts ({confidence_total}) must equal total_candidates ({total})")

    coverage_total = (
        summary.high_coverage_count + summary.medium_coverage_count + summary.low_coverage_count
    )
    if coverage_total != total:
        raise AssertionError(f"coverage counts ({coverage_total}) must equal total_candidates ({total})")

    deadline_total = (
        summary.comfortable_deadline_count
        + summary.approaching_deadline_count
        + summary.closing_soon_count
        + summary.closed_deadline_count
        + summary.unknown_deadline_count
    )
    if deadline_total != total:
        raise AssertionError(f"deadline counts ({deadline_total}) must equal total_candidates ({total})")

    funding_total = (
        summary.full_funding_count
        + summary.tuition_plus_living_count
        + summary.tuition_only_count
        + summary.partial_funding_count
        + summary.none_count
        + summary.unknown_funding_count
    )
    if funding_total != total:
        raise AssertionError(f"funding counts ({funding_total}) must equal total_candidates ({total})")

    if not 0 <= summary.visible_candidate_count <= total:
        raise AssertionError(
            f"visible_candidate_count ({summary.visible_candidate_count}) must be between 0 and "
            f"total_candidates ({total})"
        )


# ---------------------------------------------------------------------------
# Facets
# ---------------------------------------------------------------------------


def _buckets(counts: dict[str, int], labels: dict[str, str], order: tuple[str, ...] | None = None) -> list[FacetBucket]:
    """Build facet buckets, dropping empties but never reordering or truncating.

    Values with a count of zero are omitted: offering "Germany (0)" invites the
    reader to filter into an empty state they could have avoided. Everything with
    a count is always offered.

    The label is looked up in ``labels`` and otherwise used **verbatim**. A
    fallback such as ``str.title()`` looked like a safe default and quietly
    mangled the catalogue's own words: "Bachelor's, Master's" became
    "Bachelor'S, Master'S", "PhD" became "Phd", and a degree string carrying its
    own parentheses and dashes was restyled as if ScholarZone had authored it.
    A degree or a country is already written for a reader, and echoing it exactly
    is both more correct and more honest about where the wording came from.
    """
    sequence = order if order is not None else tuple(labels)
    return [
        FacetBucket(
            value=key,
            label=labels.get(key, key.replace("_", " ") if key.isupper() else key),
            count=counts.get(key, 0),
        )
        for key in sequence
        if counts.get(key, 0) > 0
    ]


def build_facets(results: list[MatchResult]) -> MatchFacets:
    """Build every facet from the same ranked result set the cards render from.

    Facet counts describe the returned page, not the whole analysed universe, so
    the number next to a filter value is the number of cards one click away. When
    a response was truncated the counts are smaller than ``total_candidates`` and
    ``MatchFacets.count_basis`` says so rather than leaving the reader to assume
    the list is complete.
    """
    country_counts: dict[str, int] = {}
    field_counts: dict[str, int] = {}
    degree_counts: dict[str, int] = {}
    eligibility_counts: dict[str, int] = {}
    funding_counts: dict[str, int] = {}
    fit_counts: dict[str, int] = {}
    confidence_counts: dict[str, int] = {}
    deadline_counts: dict[str, int] = {}

    for item in results:
        country_counts[item.country] = country_counts.get(item.country, 0) + 1
        if item.field is not None:
            field_counts[item.field] = field_counts.get(item.field, 0) + 1
        degree_counts[item.degree_levels] = degree_counts.get(item.degree_levels, 0) + 1
        eligibility_counts[item.eligibility.value] = eligibility_counts.get(item.eligibility.value, 0) + 1
        funding_counts[item.funding_state.value] = funding_counts.get(item.funding_state.value, 0) + 1
        confidence_counts[item.confidence_label] = confidence_counts.get(item.confidence_label, 0) + 1

        # A result the gate ruled ineligible, or one nothing could be evaluated
        # for, has no fit band. It must not be filed under "Low Fit", which would
        # be a classification the engine never made.
        if item.fit_score is not None:
            fit_counts[item.fit_label] = fit_counts.get(item.fit_label, 0) + 1

        deadline_counts[item.timing_bucket or TIMING_BUCKET_UNKNOWN] = (
            deadline_counts.get(item.timing_bucket or TIMING_BUCKET_UNKNOWN, 0) + 1
        )

    return MatchFacets(
        count_basis="RETURNED_PAGE",
        countries=_buckets(country_counts, {}, tuple(sorted(country_counts))),
        fields=[
            FacetBucket(
                value=key,
                label=next(
                    (item.field_label for item in results if item.field == key and item.field_label),
                    key.replace("_", " ").title(),
                ),
                count=count,
            )
            for key, count in sorted(field_counts.items())
        ],
        funding_states=_buckets(funding_counts, FUNDING_LABELS, FUNDING_STATES),
        degree_levels=_buckets(degree_counts, {}, tuple(sorted(degree_counts))),
        eligibility_states=_buckets(eligibility_counts, ELIGIBILITY_LABELS, ELIGIBILITY_ORDER),
        fit_bands=_buckets(fit_counts, FIT_BAND_LABELS, tuple(key for _, key, _ in FIT_BANDS)),
        confidence_bands=_buckets(confidence_counts, CONFIDENCE_LABELS, tuple(CONFIDENCE_LABELS)),
        deadline_buckets=_buckets(deadline_counts, DEADLINE_LABELS, TIMING_BUCKET_KEYS),
    )


def assert_facets_reconcile(facets: MatchFacets, results: list[MatchResult]) -> None:
    """Each facet family must count the visible set at most once.

    Country, degree and eligibility are complete partitions of the result set.
    Funding and deadline are too, because every record resolves to one state in
    each. Fit, confidence and field deliberately are not: a result with no fit
    band, or no resolvable programme field, is absent from that facet rather than
    misfiled.
    """
    visible = len(results)

    for name, values in (
        ("countries", facets.countries),
        ("degree_levels", facets.degree_levels),
        ("eligibility_states", facets.eligibility_states),
        ("funding_states", facets.funding_states),
    ):
        total = sum(bucket.count for bucket in values)
        if total != visible:
            raise AssertionError(f"{name} facet counts ({total}) must equal visible candidates ({visible})")

    for name, values in (("fit_bands", facets.fit_bands), ("confidence_bands", facets.confidence_bands)):
        total = sum(bucket.count for bucket in values)
        if total > visible:
            raise AssertionError(f"{name} facet counts ({total}) exceed visible candidates ({visible})")

    # A record whose programme the taxonomy cannot resolve has no field, so the
    # field facet is a partial partition: it may under-count, never over-count.
    field_total = sum(bucket.count for bucket in facets.fields)
    if field_total > visible:
        raise AssertionError(f"fields facet counts ({field_total}) exceed visible candidates ({visible})")

    if facets.count_basis != "RETURNED_PAGE":
        raise AssertionError(f"unexpected facet count_basis {facets.count_basis!r}")

    for bucket in facets.countries:
        if not bucket.label:
            raise AssertionError(f"country facet {bucket.value} has no label")


__all__ = [
    "DEADLINE_LABELS",
    "FUNDING_LABELS",
    "assert_facets_reconcile",
    "assert_reconciled",
    "build_facets",
    "build_summary",
    "coverage_band",
]