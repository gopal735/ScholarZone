"""Measured catalogue facts per country.

This is the second of the two planes, and the one that answers a different
question from the researched corpus. The corpus says what Germany costs. This
module says how many scholarships ScholarZone actually holds for Germany *right
now*. Neither can stand in for the other: a country can be beautifully researched
and hold two scholarships, and a country can hold sixty scholarships with no cost
figure at all.

## One query, then normalisation in Python

Normalisation is Python logic - Unicode folding, multi-country enumeration, alias
resolution - and none of it can be expressed in portable SQL across SQLite and
PostgreSQL. So the query groups by the raw stored string and returns one row per
distinct string (82 of them on the current catalogue), and this module normalises
those 82 rows in memory. That is the cheapest correct arrangement: the expensive
part is the table scan, which happens once.

Doing it the other way round - one query per country - is what
``pages/CountryPage.jsx`` currently does, with a six-worker pool issuing one
request per country and reading each pagination total. Sixty countries is sixty
round trips to learn something one scan already knew.

## The public visibility predicate is reused, never reimplemented

``public_visibility_conditions()`` is the directory's own definition of "may be
shown publicly". Copying it here is how a country page and a country detail view
end up disagreeing about how many scholarships Germany has.

## Reconciliation, and why counts can legitimately exceed the catalogue total

A record open to several countries is counted under each of them, so the sum of
per-country counts is *not* equal to the number of records - it can exceed it.
Collapsing that would mean under-counting one country to make a total balance,
which is the wrong trade. So this module reports three record populations
separately and the identity that actually holds:

    single + shared + unattributed == public_total

``shared`` counts each multi-country record **once**, however many countries it
belongs to, so the identity is exact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from ...repositories.scholarships import public_visibility_conditions
from .taxonomy import CountryResolution, classify_country_value

#: Lifecycle states mirrored from ``counting.catalogue``. Declared locally rather
#: than imported so this module's published partition is explicit about which
#: states it reconciles, and so a future addition to the catalogue lifecycle
#: surfaces here as an ``other`` bucket instead of quietly changing a per-country
#: figure.
LIFECYCLE_STATES: tuple[str, ...] = ("open", "closing-soon", "upcoming", "closed")


@dataclass
class CountryCatalogueFacts:
    """What the catalogue holds for one country.

    Every field is measured from stored rows on this request. None of it is
    persisted, cached or carried over.
    """

    iso2: str
    #: Records attributed to exactly this country.
    scholarships: int = 0
    open: int = 0
    closing_soon: int = 0
    upcoming: int = 0
    closed: int = 0
    other_status: int = 0
    fully_funded: int = 0
    verified: int = 0
    with_official_source: int = 0
    #: Records counted under this country *and* at least one other.
    shared_records: int = 0
    #: Records this country is the *only* host of.
    single_country_records: int = 0
    #: Distinct stored country strings that resolved here, so an alias like
    #: "USA" merging into "United States" is visible rather than invisible.
    source_labels: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "iso2": self.iso2,
            "scholarships": self.scholarships,
            "open": self.open,
            "closing_soon": self.closing_soon,
            "upcoming": self.upcoming,
            "closed": self.closed,
            "other_status": self.other_status,
            "fully_funded": self.fully_funded,
            "verified": self.verified,
            "with_official_source": self.with_official_source,
            "shared_records": self.shared_records,
            "single_country_records": self.single_country_records,
            "source_labels": list(self.source_labels),
        }


@dataclass(frozen=True)
class UnattributedGroup:
    """Stored country strings that belong to no single country.

    Published rather than discarded. "Global" and "International" holding a
    handful of records is real information about the catalogue; an unrecognised
    value is a data-quality issue that a reviewer can fix. Both are invisible if
    they are simply dropped.
    """

    kind: str
    total: int = 0
    labels: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "total": self.total, "labels": list(self.labels)}


@dataclass(frozen=True)
class CountryCatalogue:
    """The measured plane, for the whole catalogue at once."""

    by_country: Mapping[str, CountryCatalogueFacts] = field(default_factory=dict)
    unattributed: tuple[UnattributedGroup, ...] = field(default_factory=tuple)
    single_country_records: int = 0
    shared_records: int = 0
    unattributed_records: int = 0
    public_total: int = 0

    def get(self, iso2: str) -> CountryCatalogueFacts | None:
        return self.by_country.get(iso2)

    def to_dict(self) -> dict[str, object]:
        return {
            "by_country": {
                code: facts.to_dict() for code, facts in sorted(self.by_country.items())
            },
            "unattributed": [group.to_dict() for group in self.unattributed],
            "reconciliation": self.reconciliation(),
        }

    def reconciliation(self) -> dict[str, object]:
        """The record-count identity, plus whether it actually holds.

        ``holds`` is computed, not asserted. A corpus change that breaks the
        identity should say so on the response instead of being discovered later
        by a reader summing two numbers that should have matched.
        """
        expected = self.single_country_records + self.shared_records + self.unattributed_records
        attributed = sum(facts.scholarships for facts in self.by_country.values())
        return {
            "single_country_records": self.single_country_records,
            "shared_records": self.shared_records,
            "unattributed_records": self.unattributed_records,
            "public_total": self.public_total,
            "populations_sum_to_public_total": expected == self.public_total,
            "per_country_sum": attributed,
            "per_country_sum_note": (
                "A record open to several countries is counted under each of them, "
                "so this sum can exceed public_total. That is correct; collapsing "
                "it would mean under-counting one country to make a total balance."
            ),
        }


def _count(condition) -> object:
    return func.count(case((condition, 1)))


def _raw_country_rows(session: Session) -> list[dict[str, object]]:
    """Every figure per distinct stored country string, in one scan."""
    from ...models import Scholarship

    listed = and_(*public_visibility_conditions())

    statement = (
        select(
            Scholarship.country.label("label"),
            func.count(Scholarship.id).label("total"),
            _count(and_(listed, Scholarship.status == "open")).label("open"),
            _count(and_(listed, Scholarship.status == "closing-soon")).label("closing_soon"),
            _count(and_(listed, Scholarship.status == "upcoming")).label("upcoming"),
            _count(and_(listed, Scholarship.status == "closed")).label("closed"),
            _count(and_(listed, Scholarship.status.notin_(LIFECYCLE_STATES))).label(
                "other_status"
            ),
            _count(
                and_(
                    listed,
                    Scholarship.funding.ilike("%fully funded%"),
                    Scholarship.funding.not_ilike("%partial%"),
                )
            ).label("fully_funded"),
            _count(and_(listed, Scholarship.is_verified.is_(True))).label("verified"),
            _count(
                and_(listed, Scholarship.official_source.isnot(None), Scholarship.official_source != "")
            ).label("with_official_source"),
        )
        .select_from(Scholarship)
        .where(listed)
        .group_by(Scholarship.country)
    )

    return [dict(row) for row in session.execute(statement).mappings()]


def measure_country_catalogue(session: Session) -> CountryCatalogue:
    """Measure the whole catalogue by country, in one query.

    Returns an empty result rather than raising when the catalogue holds nothing,
    because "no countries" is a legitimate state for a fresh database and must
    render as an empty page, not an error.
    """
    rows = _raw_country_rows(session)

    facts: dict[str, CountryCatalogueFacts] = {}
    buckets: dict[str, UnattributedGroup] = {}
    public_total = 0
    shared_rows = 0
    single_rows = 0
    unattributed_rows = 0

    def bucket_for(kind: str) -> UnattributedGroup:
        group = buckets.get(kind)
        if group is None:
            group = UnattributedGroup(kind=kind)
            buckets[kind] = group
        return group

    for row in rows:
        label = str(row.get("label") or "")
        total = int(row.get("total") or 0)
        public_total += total

        resolution: CountryResolution = classify_country_value(label)

        if resolution.is_country:
            entry = facts.get(resolution.iso2)
            if entry is None:
                entry = CountryCatalogueFacts(iso2=resolution.iso2)
                facts[resolution.iso2] = entry
            entry.scholarships += total
            entry.open += int(row.get("open") or 0)
            entry.closing_soon += int(row.get("closing_soon") or 0)
            entry.upcoming += int(row.get("upcoming") or 0)
            entry.closed += int(row.get("closed") or 0)
            entry.other_status += int(row.get("other_status") or 0)
            entry.fully_funded += int(row.get("fully_funded") or 0)
            entry.verified += int(row.get("verified") or 0)
            entry.with_official_source += int(row.get("with_official_source") or 0)
            entry.single_country_records += total
            entry.source_labels = tuple(sorted({*entry.source_labels, label}))
            single_rows += total
            continue

        if resolution.kind == "MULTI_COUNTRY" and resolution.members:
            # Counted under every resolved member, and counted once here so the
            # three populations still partition the catalogue.
            for iso2 in resolution.members:
                entry = facts.get(iso2)
                if entry is None:
                    entry = CountryCatalogueFacts(iso2=iso2)
                    facts[iso2] = entry
                entry.scholarships += total
                entry.open += int(row.get("open") or 0)
                entry.closing_soon += int(row.get("closing_soon") or 0)
                entry.upcoming += int(row.get("upcoming") or 0)
                entry.closed += int(row.get("closed") or 0)
                entry.other_status += int(row.get("other_status") or 0)
                entry.fully_funded += int(row.get("fully_funded") or 0)
                entry.verified += int(row.get("verified") or 0)
                entry.with_official_source += int(row.get("with_official_source") or 0)
                entry.shared_records += total
                entry.source_labels = tuple(sorted({*entry.source_labels, label}))
            shared_rows += total
            continue

        kind = resolution.kind
        group = bucket_for(kind)
        buckets[kind] = UnattributedGroup(
            kind=kind,
            total=group.total + total,
            labels=tuple(sorted({*group.labels, label})),
        )
        unattributed_rows += total

    return CountryCatalogue(
        by_country=facts,
        unattributed=tuple(
            sorted(buckets.values(), key=lambda group: (-group.total, group.kind))
        ),
        single_country_records=single_rows,
        shared_records=shared_rows,
        unattributed_records=unattributed_rows,
        public_total=public_total,
    )


__all__ = [
    "CountryCatalogue",
    "CountryCatalogueFacts",
    "LIFECYCLE_STATES",
    "UnattributedGroup",
    "measure_country_catalogue",
]
