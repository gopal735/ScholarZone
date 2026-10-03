"""Catalogue-universe counting, in one query.

The catalogue is a different population from the Match universe, and it is counted
differently: not from scored results in memory, but from stored rows in SQL. This
module is the only place that difference is expressed.

One pass. Every catalogue count in a response comes from a single ``SELECT`` with
conditional aggregates, not from one query per figure. The existing
``GET /scholarships/stats`` endpoint issued nine separate ``COUNT`` queries and the
homepage ran them on every load; the same nine numbers now come from one row scan,
and the response is produced by the same count contract as everything else.

The visibility predicate is not reimplemented. ``public_visibility_conditions`` is
the directory's own definition of "may be shown publicly", and it is reused verbatim
here. Reimplementing it is how a homepage ends up advertising a total the directory
contradicts, which is a failure nobody notices until somebody compares the two
numbers.

Two different bases are counted on purpose:

* ``CATALOGUE`` - what a visitor can see. Excludes quarantined and archived rows,
  which is what the directory does.
* ``ROW_TOTALS`` - what exists in storage, including archived and quarantined. An
  archived count is the one figure that *cannot* come from the public predicate,
  since that predicate is exactly what hides archived rows.

Both are named in the response so the two are never confused.
"""

from __future__ import annotations

from typing import Mapping, Sequence

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from ...repositories.scholarships import public_visibility_conditions
from .contract import COUNT_CONTRACT_VERSION
from .types import CountBasis, CountBucket, CountPartition, CountUniverse


#: The lifecycle states the catalogue declares. Anything else lands in the
#: published ``other`` bucket rather than being dropped, so the partition stays
#: complete and an unexpected status is visible instead of silently lost.
LIFECYCLE_STATES: tuple[str, ...] = ("open", "closing-soon", "upcoming", "closed")

LIFECYCLE_LABELS: dict[str, str] = {
    "open": "Open",
    "closing-soon": "Closing soon",
    "upcoming": "Upcoming",
    "closed": "Closed",
    "other": "Other status",
}


def _has_text(column) -> object:
    """SQL truth for "this text column carries something".

    An empty string is treated as absent. A record whose image URL is ``""`` has no
    image, and counting it as having one would report a broken row as a success.
    """
    return and_(column.isnot(None), column != "")


def catalogue_counts(session: Session) -> dict[str, int]:
    """Every catalogue figure, from one query.

    Returns a flat mapping so the caller decides how to publish it. Nothing here is
    optional and nothing is guessed: a state the schema cannot express is not
    reported, rather than being reported as zero.
    """
    from ...models import Scholarship

    listed = and_(*public_visibility_conditions())

    def count(condition) -> object:
        return func.count(case((condition, Scholarship.id)))

    def distinct_countries(condition) -> object:
        return func.count(func.distinct(case((condition, Scholarship.country))))

    statement = select(
        count(listed).label("public_total"),
        distinct_countries(listed).label("countries"),
        count(and_(listed, Scholarship.status == "open")).label("open"),
        count(and_(listed, Scholarship.status == "closing-soon")).label("closing_soon"),
        count(and_(listed, Scholarship.status == "upcoming")).label("upcoming"),
        count(and_(listed, Scholarship.status == "closed")).label("closed"),
        # The residual lifecycle state, so the partition reconciles.
        count(
            and_(listed, Scholarship.status.notin_(LIFECYCLE_STATES))
        ).label("other_status"),
        count(and_(listed, Scholarship.is_verified.is_(True))).label("verified"),
        count(and_(listed, Scholarship.is_verified.is_(False))).label("unverified"),
        # `verified_active` is the verification *lifecycle* state, which is a
        # different question from `is_verified`. The previous endpoint counted
        # verification_status == 'active' and the homepage trust bar depends on that
        # exact figure, so it is preserved rather than quietly reinterpreted.
        count(and_(listed, Scholarship.verification_status == "active")).label(
            "verification_status_active"
        ),
        # Also preserved verbatim: "fully funded" and not "partial funding". This is
        # a text test on the published funding string, not the normalised funding
        # state the Match engine resolves, and the two do not always agree.
        count(
            and_(
                listed,
                Scholarship.funding.ilike("%fully funded%"),
                Scholarship.funding.not_ilike("%partial%"),
            )
        ).label("fully_funded"),
        count(_has_text(Scholarship.image_url)).label("with_image"),
        count(and_(listed, Scholarship.image_url.is_(None))).label("without_image"),
        count(_has_text(Scholarship.official_source)).label("with_official_source"),
        count(and_(listed, Scholarship.official_source.is_(None))).label(
            "without_official_source"
        ),
        # Row totals, outside the public predicate by necessity: it is that
        # predicate which hides archived and quarantined rows.
        count(Scholarship.is_archived.is_(True)).label("archived"),
        count(Scholarship.verification_status == "quarantined").label("quarantined"),
        func.count(Scholarship.id).label("row_total"),
    ).select_from(Scholarship)

    row = session.execute(statement).mappings().one()
    return {key: int(value or 0) for key, value in row.items()}


def build_catalogue_partitions(counts: Mapping[str, int]) -> list[CountPartition]:
    """Turn the raw figures into contract partitions.

    The lifecycle partition reconciles against the public total. The evidence
    partition is deliberately *not* a partition: a record can be verified and have
    no image, both claims are true, and asserting a sum over independent measures
    would manufacture a defect on every response.
    """
    public_total = counts.get("public_total", 0)

    lifecycle_keys = ("open", "closing_soon", "upcoming", "closed", "other_status")
    lifecycle = CountPartition(
        name="lifecycle_status",
        label="Lifecycle status",
        basis=CountBasis.COMPLETE,
        buckets=[
            CountBucket(
                key=key,
                label=LIFECYCLE_LABELS[state],
                count=counts.get(key, 0),
            )
            for key, state in zip(lifecycle_keys, ("open", "closing-soon", "upcoming", "closed", "other"))
        ],
        bucket_total=sum(counts.get(key, 0) for key in lifecycle_keys),
        unclassified_count=0,
        note=(
            "The lifecycle states the catalogue stores. \"Other status\" is a "
            "published bucket rather than a silent drop, so an unexpected status is "
            "visible instead of lost."
        ),
    )

    evidence_pairs = (
        ("verified", "Verified", "verified"),
        ("unverified", "Not verified", "unverified"),
        ("with_image", "With image", "with_image"),
        ("without_image", "Without image", "without_image"),
        ("with_official_source", "With official source", "with_official_source"),
        ("without_official_source", "Without official source", "without_official_source"),
        ("archived", "Archived", "archived"),
        ("quarantined", "Quarantined", "quarantined"),
    )
    evidence = CountPartition(
        name="catalogue_evidence",
        label="Evidence",
        basis=CountBasis.NOT_A_PARTITION,
        buckets=[
            CountBucket(key=key, label=label, count=counts.get(source, 0))
            for key, label, source in evidence_pairs
        ],
        bucket_total=0,
        unclassified_count=0,
        note=(
            "Independent measures over the catalogue, not a partition. Archived and "
            "quarantined rows are counted from all stored rows rather than from the "
            "public set, because the public visibility predicate is precisely what "
            "hides them."
        ),
    )

    return [lifecycle, evidence]


def catalogue_summary(counts: Mapping[str, int]) -> dict[str, int]:
    """The figures the public trust bar needs, as a flat mapping.

    Same names as the existing ``ScholarshipStatsResponse`` so the response contract
    is unchanged. Only the computation moved.
    """
    return {
        "total": counts.get("public_total", 0),
        "countries": counts.get("countries", 0),
        "open": counts.get("open", 0),
        "closing_soon": counts.get("closing_soon", 0),
        "upcoming": counts.get("upcoming", 0),
        "verified_active": counts.get("verification_status_active", 0),
        "fully_funded": counts.get("fully_funded", 0),
        "with_image": counts.get("with_image", 0),
        "with_official_source": counts.get("with_official_source", 0),
    }


__all__ = [
    "COUNT_CONTRACT_VERSION",
    "CountUniverse",
    "LIFECYCLE_LABELS",
    "LIFECYCLE_STATES",
    "build_catalogue_partitions",
    "catalogue_counts",
    "catalogue_summary",
]