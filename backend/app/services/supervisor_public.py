"""Public read model for supervisor discovery.

Two constraints shape every function here.

**Visibility is borrowed, never restated.** The catalogue's own
``public_visibility_conditions`` decides what may be read publicly. The
supervisor routes reuse that predicate rather than writing their own version,
because a second copy is a second answer to "is this record visible", and the two
would eventually disagree. A record that fails the predicate produces a 404 here
for exactly the same reason the catalogue would not list it.

Note that the existing scholarship *detail* route does not apply this predicate -
it reads by primary key alone. That is a pre-existing leak and is deliberately
not imitated; see ``get_public_scholarship_or_404``.

**Nothing reaches a response without provenance.** A professor is emitted only
when a link to it is verified and that link names the page it was read from. A
professor whose availability is unknown says so. There is no branch in this
module that fills a gap with a plausible value, because a plausible value is
indistinguishable from a sourced one once it is on a public page.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..models_supervisor import (
    ProfessorAvailability,
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
)
from ..repositories.scholarships import public_visibility_conditions
from .supervisor_alignment import ResearchAlignment, align_research
from .supervisor_freshness import effective_availability_state
from .supervisor_status import (
    NON_PUBLISHING_COVERAGE_STATUSES,
    PUBLIC_RELATIONSHIP_STATUSES,
    SupervisorCoverageStatus,
)

logger = logging.getLogger(__name__)

#: A scholarship with many discovered faculty should not return all of them; the
#: list is a shortlist, and the count on the coverage row is the honest total.
DEFAULT_SUPERVISOR_LIMIT = 50
MAX_SUPERVISOR_LIMIT = 200


class ScholarshipNotPublic(Exception):
    """The scholarship does not exist, or is not publicly visible.

    One exception for both cases on purpose. Distinguishing them would confirm
    the existence of archived and quarantined records to anyone who can guess an
    id.
    """


def get_public_scholarship_or_404(db: Session, scholarship_id: int) -> Scholarship:
    """Return the scholarship only if it is publicly visible.

    Raises :class:`ScholarshipNotPublic` when the row is absent, archived,
    quarantined, or hidden by the quality gates - all of which are
    indistinguishable to the caller on purpose.
    """
    row = db.execute(
        select(Scholarship).where(
            and_(Scholarship.id == scholarship_id, *public_visibility_conditions())
        )
    ).scalar_one_or_none()
    if row is None:
        raise ScholarshipNotPublic(scholarship_id)
    return row


def get_coverage(db: Session, scholarship_id: int) -> ScholarshipSupervisorCoverage | None:
    """Return the coverage row, or ``None`` when discovery has not created one.

    ``None`` is a real answer and the API renders it as "discovery pending"; it is
    never rounded up to zero supervisors.
    """
    return db.execute(
        select(ScholarshipSupervisorCoverage).where(
            ScholarshipSupervisorCoverage.scholarship_id == scholarship_id
        )
    ).scalar_one_or_none()


def count_publishable_links(db: Session, scholarship_id: int) -> int:
    """Count relationships that may be shown publicly for this scholarship."""
    return db.execute(
        select(func.count(ScholarshipProfessorLink.id)).where(
            and_(
                ScholarshipProfessorLink.scholarship_id == scholarship_id,
                ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
            )
        )
    ).scalar_one()


def _load_publishable_links(
    db: Session, scholarship_id: int, limit: int
) -> list[ScholarshipProfessorLink]:
    return list(
        db.execute(
            select(ScholarshipProfessorLink)
            .where(
                and_(
                    ScholarshipProfessorLink.scholarship_id == scholarship_id,
                    ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
                )
            )
            .order_by(
                ScholarshipProfessorLink.confidence.desc().nullslast(),
                ScholarshipProfessorLink.id,
            )
            .limit(limit)
        ).scalars()
    )


def _load_profiles(
    db: Session, professor_ids: list[int]
) -> dict[int, ProfessorProfile]:
    if not professor_ids:
        return {}
    rows = db.execute(
        select(ProfessorProfile).where(ProfessorProfile.id.in_(professor_ids))
    ).scalars()
    return {row.id: row for row in rows}


def _load_availability(
    db: Session, professor_ids: list[int], now: datetime
) -> dict[int, list[dict]]:
    """Return availability rows for every requested professor in one query.

    Batched deliberately: a per-professor lookup here is exactly the N+1 that
    makes a detail page scale with the size of the catalogue.
    """
    if not professor_ids:
        return {}
    rows = db.execute(
        select(ProfessorAvailability).where(
            ProfessorAvailability.professor_id.in_(professor_ids)
        )
    ).scalars()
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.professor_id, []).append(
            {
                "scope": row.scope,
                # Decided here, at read time, so a claim that has aged out of its
                # freshness window is published as stale however it was stored.
                "state": effective_availability_state(row.state, row.verified_at, now),
                "source_url": row.source_url,
                "verified_at": _iso(row.verified_at),
            }
        )
    for entries in grouped.values():
        entries.sort(key=lambda item: item["scope"])
    return grouped


def _load_sources(
    db: Session, professor_ids: list[int], link_ids: list[int]
) -> dict[int, list[dict]]:
    """Return evidence rows keyed by professor, preferring link-scoped evidence."""
    if not professor_ids:
        return {}
    rows = db.execute(
        select(SupervisorSourceEvidence).where(
            SupervisorSourceEvidence.professor_id.in_(professor_ids)
        )
    ).scalars()
    grouped: dict[int, list[dict]] = {}
    link_id_set = set(link_ids)
    for row in rows:
        if row.link_id is not None and row.link_id not in link_id_set:
            continue
        grouped.setdefault(row.professor_id, []).append(
            {
                "source_url": row.source_url,
                "source_host": row.source_host,
                "source_type": row.source_type,
                "retrieved_at": _iso(row.retrieved_at),
                "verified_at": _iso(row.verified_at),
                "evidence_summary": row.evidence_summary,
            }
        )
    for entries in grouped.values():
        entries.sort(key=lambda item: (item["retrieved_at"] or "", item["source_url"]), reverse=True)
    return grouped


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def coverage_public_state(
    coverage: ScholarshipSupervisorCoverage | None,
    publishable_count: int | None = None,
) -> dict:
    """Return the coverage facts a public response may carry.

    ``last_error_summary`` is intentionally absent. It exists for operators and
    can name a host, a status code and a failure mode, none of which belong on a
    public page.

    ``publishable_count`` is the number of relationships this response could
    actually show. When it is greater than the stored count, the links win: a page
    that lists three professors must not headline "no verified supervisors found"
    because a stored counter drifted. The stored row is still the right answer
    when it agrees, so a pending or blocked state is never overwritten by a count.
    """
    if coverage is None:
        state = {
            "coverage_status": str(SupervisorCoverageStatus.SEARCH_PENDING),
            "verified_supervisor_count": 0,
            "evidence_state": "not_collected",
            "last_checked_at": None,
            "discovery_pending": True,
        }
    else:
        state = {
            "coverage_status": coverage.status,
            "verified_supervisor_count": coverage.verified_supervisor_count,
            "evidence_state": coverage.evidence_state,
            "last_checked_at": _iso(coverage.last_checked_at),
            "discovery_pending": coverage.status == str(SupervisorCoverageStatus.SEARCH_PENDING),
        }

    if publishable_count is not None and publishable_count > state["verified_supervisor_count"]:
        state["verified_supervisor_count"] = publishable_count
        state["coverage_status"] = str(SupervisorCoverageStatus.VERIFIED_SUPERVISORS)
        state["discovery_pending"] = False
    return state


def build_supervisor_list(
    db: Session,
    scholarship_id: int,
    interests: list[str] | None = None,
    limit: int = DEFAULT_SUPERVISOR_LIMIT,
) -> tuple[dict, list[dict]]:
    """Return ``(coverage, professors)`` for a publicly visible scholarship.

    Raises :class:`ScholarshipNotPublic` when the scholarship may not be read.
    """
    get_public_scholarship_or_404(db, scholarship_id)

    limit = max(1, min(int(limit or DEFAULT_SUPERVISOR_LIMIT), MAX_SUPERVISOR_LIMIT))
    now = datetime.now(timezone.utc)
    coverage = get_coverage(db, scholarship_id)

    links = _load_publishable_links(db, scholarship_id, limit)
    professor_ids = [link.professor_id for link in links]
    profiles = _load_profiles(db, professor_ids)
    availability = _load_availability(db, professor_ids, now)
    sources = _load_sources(db, professor_ids, [link.id for link in links])

    # The count is the total number of publishable relationships, not the length
    # of this page, so a capped list still reports the honest total.
    publishable_count = count_publishable_links(db, scholarship_id)

    professors: list[dict] = []
    for link in links:
        profile = profiles.get(link.professor_id)
        if profile is None or profile.profile_status == "merged":
            # A retired professor is still published with their history intact;
            # a merged one has been folded into another record and must not
            # appear twice.
            continue
        alignment: ResearchAlignment = align_research(
            interests, profile.research_areas, profile.research_keywords
        )
        professors.append(
            {
                "id": profile.id,
                "name": profile.canonical_name,
                "title": profile.title,
                "institution": profile.institution_name,
                "department": profile.department_name,
                "research_areas": list(profile.research_areas or []),
                "official_profile_url": profile.official_profile_url,
                # Gated on its own flag. An address that was collected but not
                # confirmed against an institutional page is never published,
                # because publishing it would present a guess as a fact.
                "official_email": (
                    profile.official_email if profile.official_email_verified else None
                ),
                "official_email_verified": bool(profile.official_email_verified),
                "lab_url": profile.lab_url,
                "relationship_type": link.relationship_type,
                "availability": availability.get(profile.id, []),
                "research_alignment": alignment.as_dict(),
                "evidence_source_url": link.evidence_source_url,
                "evidence_source_type": link.evidence_source_type,
                "evidence_summary": link.evidence_quote_or_summary,
                "verified_at": _iso(link.verified_at),
                "last_verified_at": _iso(profile.last_verified_at),
                "sources": sources.get(profile.id, []),
            }
        )

    return coverage_public_state(coverage, publishable_count), professors


def coverage_requires_discovery(coverage: ScholarshipSupervisorCoverage | None) -> bool:
    """Return whether this coverage state still owes the catalogue a search."""
    if coverage is None:
        return True
    return coverage.status in NON_PUBLISHING_COVERAGE_STATUSES


__all__ = [
    "DEFAULT_SUPERVISOR_LIMIT",
    "MAX_SUPERVISOR_LIMIT",
    "ScholarshipNotPublic",
    "build_supervisor_list",
    "coverage_public_state",
    "coverage_requires_discovery",
    "count_publishable_links",
    "get_coverage",
    "get_public_scholarship_or_404",
]