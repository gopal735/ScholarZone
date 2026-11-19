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
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

try:
    from psycopg.errors import UndefinedTable as PsycopgUndefinedTable
except ImportError:  # pragma: no cover - psycopg2 fallback
    try:
        from psycopg2.errors import UndefinedTable as PsycopgUndefinedTable
    except ImportError:
        PsycopgUndefinedTable = None

try:
    from psycopg.errors import UndefinedColumn as PsycopgUndefinedColumn
except ImportError:  # pragma: no cover - psycopg2 fallback
    try:
        from psycopg2.errors import UndefinedColumn as PsycopgUndefinedColumn
    except ImportError:
        PsycopgUndefinedColumn = None


def _missing_schema_error(exc: BaseException) -> bool:
    """Return True when *exc* is a PostgreSQL missing-table/column error."""
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        pgcode = getattr(current, "pgcode", None) or getattr(current, "sqlstate", None) or getattr(current, "code", None)
        if pgcode in {"42P01", "42703"}:
            return True
        if PsycopgUndefinedTable is not None and isinstance(current, PsycopgUndefinedTable):
            return True
        if PsycopgUndefinedColumn is not None and isinstance(current, PsycopgUndefinedColumn):
            return True
        if type(current).__name__ in {"UndefinedTable", "UndefinedColumn"}:
            return True
        text = str(current).lower()
        if "does not exist" in text and ("relation" in text or "column" in text):
            return True
        current = getattr(current, "orig", None) or getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False

from ..models import Scholarship
from ..models_supervisor import (
    ProfessorAvailability,
    ProfessorProfile,
    ScholarshipProfessorLink,
    ScholarshipSupervisorCoverage,
    SupervisorSourceEvidence,
    OfficialContact,
)
from ..repositories.scholarships import public_visibility_conditions
from .supervisor_alignment import ResearchAlignment, align_research
from .supervisor_freshness import effective_availability_state
from .supervisor_status import (
    NON_PUBLISHING_COVERAGE_STATUSES,
    PUBLIC_RELATIONSHIP_STATUSES,
    SupervisorCoverageStatus,
    OfficialContactVerificationStatus,
    PUBLIC_CONTACT_STATUSES,
)

# Custom exception for missing schema
class SchemaNotReadyError(Exception):
    """Raised when a required database table or column is missing."""
    def __init__(self, missing_object: str):
        self.missing_object = missing_object
        super().__init__(f"Required schema object missing: {missing_object}")

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

def _load_official_contacts(
    db: Session, scholarship_id: int
) -> list[dict]:
    """Load verified official contacts for a scholarship.

    Raises SchemaNotReadyError if the official_contacts table is missing.
    """
    try:
        rows = db.execute(
            select(OfficialContact)
            .where(
                and_(
                    OfficialContact.scholarship_id == scholarship_id,
                    OfficialContact.verification_status.in_(PUBLIC_CONTACT_STATUSES),
                )
            )
            .order_by(
                OfficialContact.verified_at.desc().nullslast(),
                OfficialContact.retrieved_at.desc(),
                OfficialContact.id.asc(),
            )
        ).scalars()
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("official_contacts") from exc
        raise

    contacts = []
    for row in rows:
        contacts.append({
            "id": row.id,
            "institution_name": row.institution_name,
            "department_name": row.department_name,
            "programme_name": row.programme_name,
            "contact_type": row.contact_type,
            "contact_role": row.contact_role,
            "published_contact_name": row.published_contact_name,
            "official_email": row.official_email if row.email_verified else None,
            "official_email_verified": bool(row.email_verified),
            "official_contact_url": row.official_contact_url,
            "evidence_source_url": row.evidence_source_url,
            "evidence_source_type": row.evidence_source_type,
            "evidence_summary": row.evidence_summary,
            "retrieved_at": _iso(row.retrieved_at),
            "verified_at": _iso(row.verified_at),
            "verification_status": row.verification_status,
        })
    return contacts

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
) -> tuple[dict, list[dict], list[dict]]:
    """Return ``(coverage, professors, official_contacts)`` for a publicly visible scholarship.

    Raises :class:`ScholarshipNotPublic` when the scholarship may not be read.
    Raises :class:`SchemaNotReadyError` when a required database table or column is missing.
    """
    get_public_scholarship_or_404(db, scholarship_id)

    limit = max(1, min(int(limit or DEFAULT_SUPERVISOR_LIMIT), MAX_SUPERVISOR_LIMIT))
    now = datetime.now(timezone.utc)

    try:
        coverage = get_coverage(db, scholarship_id)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("scholarship_supervisor_coverage") from exc
        raise

    try:
        links = _load_publishable_links(db, scholarship_id, limit)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("scholarship_professor_links") from exc
        raise

    professor_ids = [link.professor_id for link in links]

    try:
        profiles = _load_profiles(db, professor_ids)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("professor_profiles") from exc
        raise

    try:
        availability = _load_availability(db, professor_ids, now)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("professor_availability") from exc
        raise

    try:
        sources = _load_sources(db, professor_ids, [link.id for link in links])
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("supervisor_source_evidence") from exc
        raise

    try:
        official_contacts = _load_official_contacts(db, scholarship_id)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("official_contacts") from exc
        raise

    # The count is the total number of publishable relationships, not the length
    # of this page, so a capped list still reports the honest total.
    try:
        publishable_count = count_publishable_links(db, scholarship_id)
    except (ProgrammingError, DBAPIError) as exc:
        if _missing_schema_error(exc):
            raise SchemaNotReadyError("scholarship_professor_links") from exc
        raise

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

    return coverage_public_state(coverage, publishable_count), professors, official_contacts

def coverage_requires_discovery(coverage: ScholarshipSupervisorCoverage | None) -> bool:
    """Return whether this coverage state still owes the catalogue a search."""
    if coverage is None:
        return True
    return coverage.status in NON_PUBLISHING_COVERAGE_STATUSES


# ============================================================
# Global Supervisor Search
# ============================================================

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..repositories.scholarships import public_visibility_conditions
from .supervisor_status import (
    PUBLIC_RELATIONSHIP_STATUSES,
    SupervisorCoverageStatus,
)


@dataclass
class GlobalSupervisorSearchRequest:
    """Request parameters for global supervisor search."""
    research_interests: list[str] | None = None
    degree_levels: list[str] | None = None  # BACHELOR, MASTER, PHD
    lifecycle: list[str] | None = None  # OPEN, UPCOMING
    country: str | None = None
    subject: str | None = None
    institution: str | None = None
    contact_types: list[str] | None = None
    verified_email_only: bool = False
    scholarship_id: int | None = None
    page: int = 1
    page_size: int = 20


@dataclass
class GlobalSupervisorSearchResult:
    """A single search result combining scholarship and professor info."""
    scholarship_id: int
    scholarship_title: str
    country: str
    degree_level: str
    original_degree_text: str
    effective_lifecycle: str
    opening_date: str | None
    deadline: str | None
    awarding_institution: str | None
    host_institution: str | None
    professor_id: int
    official_name: str
    academic_title: str | None
    institution: str
    department: str | None
    official_profile_url: str
    research_areas: list[str]
    relationship_type: str
    relationship_verification_status: str
    research_alignment: dict
    official_email: str | None
    official_email_verified: bool
    official_contact_url: str | None
    official_department_page: str | None
    research_group_url: str | None
    source_url: str
    last_verified_at: str | None


@dataclass
class GlobalSupervisorSearchResponse:
    """Response for global supervisor search."""
    items: list[GlobalSupervisorSearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int


def _normalize_degree_level(degree_text: str) -> str:
    """Normalize degree text into canonical degree level."""
    if not degree_text:
        return "UNKNOWN"
    degree_lower = degree_text.lower()
    if any(term in degree_lower for term in ["phd", "doctoral", "dphil"]):
        return "PHD"
    if any(term in degree_lower for term in ["master", "msc", "ma", "meng", "mphil"]):
        return "MASTER"
    if any(term in degree_lower for term in ["bachelor", "bsc", "ba", "beng", "undergraduate"]):
        return "BACHELOR"
    return "OTHER"


def _get_effective_lifecycle(scholarship: Scholarship) -> str:
    """Determine effective lifecycle from scholarship data."""
    # This mirrors the canonical lifecycle logic
    status = (scholarship.status or "").lower()
    if status in ("open", "opening", "closing_soon"):
        return "OPEN"
    if status in ("upcoming",):
        return "UPCOMING"
    if status in ("closed",):
        return "CLOSED"
    return "UNKNOWN"


def global_supervisor_search(
    db: Session,
    request: GlobalSupervisorSearchRequest,
) -> GlobalSupervisorSearchResponse:
    """Search supervisors across all eligible OPEN and UPCOMING scholarships.

    This performs a global search across the supervisor discovery catalogue,
    returning paginated results with scholarship and professor information.
    """
    # Validate and clean request
    page = max(1, request.page)
    page_size = max(1, min(request.page_size or 20, 100))
    offset = (page - 1) * page_size

    interests = [
        value.strip()[:120]
        for value in (request.research_interests or [])
        if isinstance(value, str) and value.strip()
    ][:20]

    degree_levels = [d.upper() for d in (request.degree_levels or []) if d.upper() in ("BACHELOR", "MASTER", "PHD", "OTHER")]
    lifecycle_filters = [l.upper() for l in (request.lifecycle or []) if l.upper() in ("OPEN", "UPCOMING", "CLOSED", "UNKNOWN")]
    contact_types = [c.upper() for c in (request.contact_types or [])]
    verified_email_only = request.verified_email_only

    # Build base query: only publicly visible scholarships with verified supervisor relationships
    base_query = (
        select(
            Scholarship.id,
            Scholarship.title,
            Scholarship.country,
            Scholarship.degree,
            Scholarship.status,
            Scholarship.deadline_date,
            Scholarship.official_source,
            Scholarship.official_source_url,
            ProfessorProfile.id.label("professor_id"),
            ProfessorProfile.canonical_name,
            ProfessorProfile.title.label("academic_title"),
            ProfessorProfile.institution_name,
            ProfessorProfile.department_name,
            ProfessorProfile.official_profile_url,
            ProfessorProfile.research_areas,
            ProfessorProfile.official_email,
            ProfessorProfile.official_email_verified,
            ProfessorProfile.lab_url,
            ScholarshipProfessorLink.relationship_type,
            ScholarshipProfessorLink.verification_status,
            ScholarshipProfessorLink.evidence_source_url,
            ScholarshipProfessorLink.verified_at,
        )
        .join(ScholarshipProfessorLink, ScholarshipProfessorLink.scholarship_id == Scholarship.id)
        .join(ProfessorProfile, ProfessorProfile.id == ScholarshipProfessorLink.professor_id)
        .where(
            and_(
                *public_visibility_conditions(),
                ScholarshipProfessorLink.verification_status.in_(PUBLIC_RELATIONSHIP_STATUSES),
                ProfessorProfile.profile_status == "active",
            )
        )
    )

    # Apply degree-level filter at SQL level
    if degree_levels:
        degree_conditions = []
        for dl in degree_levels:
            if dl == 'PHD':
                degree_conditions.append(Scholarship.degree.ilike('%phd%'))
                degree_conditions.append(Scholarship.degree.ilike('%doctoral%'))
                degree_conditions.append(Scholarship.degree.ilike('%dphil%'))
            elif dl == 'MASTER':
                degree_conditions.append(Scholarship.degree.ilike('%master%'))
                degree_conditions.append(Scholarship.degree.ilike('%msc%'))
                degree_conditions.append(Scholarship.degree.ilike('%meng%'))
                degree_conditions.append(Scholarship.degree.ilike('%mphil%'))
            elif dl == 'BACHELOR':
                degree_conditions.append(Scholarship.degree.ilike('%bachelor%'))
                degree_conditions.append(Scholarship.degree.ilike('%bsc%'))
                degree_conditions.append(Scholarship.degree.ilike('%beng%'))
                degree_conditions.append(Scholarship.degree.ilike('%undergraduate%'))
        if degree_conditions and 'OTHER' not in degree_levels:
            from sqlalchemy import or_
            base_query = base_query.where(or_(*degree_conditions))

    # Apply lifecycle filter at SQL level
    if lifecycle_filters:
        status_conditions = []
        for lf in lifecycle_filters:
            if lf == 'OPEN':
                status_conditions.append(Scholarship.status.in_(['open', 'opening', 'closing_soon']))
            elif lf == 'UPCOMING':
                status_conditions.append(Scholarship.status == 'upcoming')
            elif lf == 'CLOSED':
                status_conditions.append(Scholarship.status == 'closed')
            elif lf == 'UNKNOWN':
                status_conditions.append(~Scholarship.status.in_(['open', 'opening', 'closing_soon', 'upcoming', 'closed']))
        if status_conditions:
            from sqlalchemy import or_
            base_query = base_query.where(or_(*status_conditions))

    if request.country:
        base_query = base_query.where(Scholarship.country.ilike(f"%{request.country}%"))

    if request.institution:
        base_query = base_query.where(ProfessorProfile.institution_name.ilike(f"%{request.institution}%"))

    if request.scholarship_id:
        base_query = base_query.where(Scholarship.id == request.scholarship_id)

    if contact_types:
        base_query = base_query.where(ScholarshipProfessorLink.relationship_type.in_(contact_types))

    if verified_email_only:
        base_query = base_query.where(
            and_(
                ProfessorProfile.official_email_verified == True,
                ProfessorProfile.official_email.isnot(None),
            )
        )

    # Order by verified_at desc (most recently verified first)
    base_query = base_query.order_by(ScholarshipProfessorLink.verified_at.desc().nullslast())

    # Get total count
    count_query = select(func.count()).select_from(base_query.subquery())
    total = db.execute(count_query).scalar_one()

    # Apply pagination
    paginated_query = base_query.offset(offset).limit(page_size)
    rows = db.execute(paginated_query).all()

    # Process results
    items: list[GlobalSupervisorSearchResult] = []
    for row in rows:
        degree_level = _normalize_degree_level(row.degree or "")
        effective_lifecycle = _get_effective_lifecycle_from_row(row)

        # Compute research alignment
        from .supervisor_alignment import ResearchAlignment, align_research
        alignment: ResearchAlignment = align_research(
            interests, row.research_areas, []
        )

        items.append(GlobalSupervisorSearchResult(
            scholarship_id=row.id,
            scholarship_title=row.title,
            country=row.country,
            degree_level=degree_level,
            original_degree_text=row.degree or "",
            effective_lifecycle=effective_lifecycle,
            opening_date=None,  # Not available in current model
            deadline=row.deadline_date.isoformat() if row.deadline_date else None,
            awarding_institution=row.official_source,
            host_institution=row.institution_name,
            professor_id=row.professor_id,
            official_name=row.canonical_name,
            academic_title=row.academic_title,
            institution=row.institution_name,
            department=row.department_name,
            official_profile_url=row.official_profile_url,
            research_areas=list(row.research_areas or []),
            relationship_type=row.relationship_type,
            relationship_verification_status=row.verification_status,
            research_alignment=alignment.as_dict(),
            official_email=row.official_email if row.official_email_verified else None,
            official_email_verified=bool(row.official_email_verified),
            official_contact_url=None,  # Would need separate query
            official_department_page=None,
            research_group_url=row.lab_url,
            source_url=row.evidence_source_url,
            last_verified_at=_iso(row.verified_at),
        ))

    return GlobalSupervisorSearchResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


def _get_effective_lifecycle_from_row(row) -> str:
    """Determine effective lifecycle from a query result row."""
    status = (row.status or "").lower()
    if status in ("open", "opening", "closing_soon"):
        return "OPEN"
    if status in ("upcoming",):
        return "UPCOMING"
    if status in ("closed",):
        return "CLOSED"
    return "UNKNOWN"


# ============================================================
# Coverage Reporting
# ============================================================

from dataclasses import dataclass, field
from typing import List


@dataclass
class ScholarshipCoverageSummary:
    """Summary of coverage for a single scholarship."""
    scholarship_id: int
    title: str
    country: str
    degree: str
    status: str
    coverage_status: str
    existing_contacts: int
    verified_contacts: int
    has_verified_email: bool
    research_supervisors: int
    course_instructors: int
    programme_faculty: int
    department_contacts: int
    university_leadership: int
    programme_office: int
    last_checked: str | None
    next_check: str | None
    error_summary: str | None


@dataclass
class CoverageReport:
    """Complete coverage report for all eligible scholarships."""
    total_eligible: int
    open_count: int
    upcoming_count: int
    closed_excluded: int
    unknown_lifecycle: int
    
    # Coverage states
    not_started: int
    existing_contacts_audited: int
    host_mapping_pending: int
    research_in_progress: int
    partially_researched: int
    research_completed: int
    source_blocked: int
    no_public_contact_found: int
    needs_review: int
    not_applicable: int
    
    # Contact counts
    total_existing_contacts: int
    total_verified_contacts: int
    total_verified_emails: int
    total_research_supervisors: int
    total_course_instructors: int
    total_programme_faculty: int
    total_department_contacts: int
    total_university_leadership: int
    total_programme_office: int
    
    # Institutional coverage
    unique_institutions: int
    unique_departments: int
    
    # Per-scholarship details
    scholarships: List[ScholarshipCoverageSummary]


def _normalize_degree_level_for_report(degree_text: str) -> str:
    """Normalize degree text for reporting."""
    if not degree_text:
        return "UNKNOWN"
    degree_lower = degree_text.lower()
    if any(term in degree_lower for term in ["phd", "doctoral", "dphil"]):
        return "PHD"
    if any(term in degree_lower for term in ["master", "msc", "ma", "meng", "mphil"]):
        return "MASTER"
    if any(term in degree_lower for term in ["bachelor", "bsc", "ba", "beng", "undergraduate"]):
        return "BACHELOR"
    return "OTHER"


def _get_effective_lifecycle_for_report(scholarship: Scholarship) -> str:
    """Get effective lifecycle for a scholarship."""
    status = (scholarship.status or "").lower()
    if status in ("open", "opening", "closing_soon"):
        return "OPEN"
    if status in ("upcoming",):
        return "UPCOMING"
    if status in ("closed",):
        return "CLOSED"
    return "UNKNOWN"


def get_coverage_report(db: Session) -> CoverageReport:
    """Generate a comprehensive coverage report for all eligible scholarships.

    Eligible = publicly visible, not archived, not quarantined, lifecycle OPEN or UPCOMING.
    Uses bulk queries to avoid N+1 performance issues.
    """
    from sqlalchemy import select, func, and_
    from ..models import Scholarship
    from ..repositories.scholarships import public_visibility_conditions
    from ..models_supervisor import (
        ScholarshipSupervisorCoverage,
        ScholarshipProfessorLink,
        ProfessorProfile,
    )
    from .supervisor_status import PUBLIC_RELATIONSHIP_STATUSES

    # Get all eligible scholarships
    eligible_scholarships = db.execute(select(Scholarship).where(
        *public_visibility_conditions(),
        Scholarship.status.in_(['open', 'upcoming', 'opening', 'closing_soon'])
    )).scalars().all()

    total_eligible = len(eligible_scholarships)
    eligible_ids = [s.id for s in eligible_scholarships]

    # Bulk fetch coverage rows
    coverage_rows = db.execute(
        select(ScholarshipSupervisorCoverage).where(
            ScholarshipSupervisorCoverage.scholarship_id.in_(eligible_ids)
        )
    ).scalars().all()
    coverage_by_schol = {c.scholarship_id: c for c in coverage_rows}

    # Bulk fetch all links for eligible scholarships
    all_links = db.execute(
        select(ScholarshipProfessorLink).where(
            ScholarshipProfessorLink.scholarship_id.in_(eligible_ids)
        )
    ).scalars().all()

    # Group links by scholarship
    links_by_schol = {}
    for link in all_links:
        links_by_schol.setdefault(link.scholarship_id, []).append(link)

    # Bulk fetch all professor profiles referenced by links
    professor_ids = set(link.professor_id for link in all_links)
    profiles_by_id = {}
    if professor_ids:
        profiles = db.execute(
            select(ProfessorProfile).where(ProfessorProfile.id.in_(professor_ids))
        ).scalars().all()
        profiles_by_id = {p.id: p for p in profiles}

    # Counters
    open_count = 0
    upcoming_count = 0

    not_started = 0
    existing_contacts_audited = 0
    host_mapping_pending = 0
    research_in_progress = 0
    partially_researched = 0
    research_completed = 0
    source_blocked = 0
    no_public_contact_found = 0
    needs_review = 0
    not_applicable_count = 0

    total_existing_contacts = 0
    total_verified_contacts = 0
    total_verified_emails = 0
    total_research_supervisors = 0
    total_course_instructors = 0
    total_programme_faculty = 0
    total_department_contacts = 0
    total_university_leadership = 0
    total_programme_office = 0

    institutions = set()
    departments = set()
    unique_verified_emails = set()

    scholarships_details = []

    for schol in eligible_scholarships:
        lifecycle = _get_effective_lifecycle_for_report(schol)
        if lifecycle == "OPEN":
            open_count += 1
        elif lifecycle == "UPCOMING":
            upcoming_count += 1

        coverage = coverage_by_schol.get(schol.id)
        links = links_by_schol.get(schol.id, [])

        existing_contacts = len(links)
        total_existing_contacts += existing_contacts

        research_supervisors = 0
        course_instructors = 0
        programme_faculty = 0
        department_contacts = 0
        university_leadership = 0
        programme_office = 0
        verified_count = 0
        has_verified_email = False

        for link in links:
            if link.verification_status in PUBLIC_RELATIONSHIP_STATUSES:
                verified_count += 1

            rel_type = link.relationship_type
            if rel_type in ("potential_supervisor", "RESEARCH_SUPERVISOR"):
                research_supervisors += 1
            elif rel_type in ("course_instructor", "COURSE_INSTRUCTOR"):
                course_instructors += 1
            elif rel_type in ("program_faculty", "PROGRAMME_FACULTY"):
                programme_faculty += 1
            elif rel_type in ("department_contact", "DEPARTMENT_CONTACT"):
                department_contacts += 1
            elif rel_type in ("university_leadership", "UNIVERSITY_LEADERSHIP"):
                university_leadership += 1
            elif rel_type in ("programme_office", "PROGRAMME_OFFICE"):
                programme_office += 1

        total_verified_contacts += verified_count
        total_research_supervisors += research_supervisors
        total_course_instructors += course_instructors
        total_programme_faculty += programme_faculty
        total_department_contacts += department_contacts
        total_university_leadership += university_leadership
        total_programme_office += programme_office

        # Check for verified emails (bulk lookup already done)
        for link in links:
            if link.verification_status in PUBLIC_RELATIONSHIP_STATUSES:
                prof = profiles_by_id.get(link.professor_id)
                if prof and prof.official_email_verified and prof.official_email:
                    has_verified_email = True
                    if prof.official_email not in unique_verified_emails:
                        unique_verified_emails.add(prof.official_email)
                        total_verified_emails += 1

        # Track institutions
        for link in links:
            prof = profiles_by_id.get(link.professor_id)
            if prof:
                if prof.institution_name:
                    institutions.add(prof.institution_name)
                if prof.department_name:
                    departments.add(f"{prof.institution_name}:{prof.department_name}")

        # Determine coverage state
        coverage_status = coverage.status if coverage else "not_started"

        if coverage_status == "search_pending":
            not_started += 1
        elif coverage_status == "verified_supervisors":
            research_completed += 1
        elif coverage_status == "no_verified_supervisor_found":
            no_public_contact_found += 1
        elif coverage_status == "source_blocked":
            source_blocked += 1
        elif coverage_status == "source_requires_rendering":
            research_in_progress += 1
        elif coverage_status == "needs_verification":
            needs_review += 1
        elif coverage_status == "not_applicable":
            not_applicable_count += 1
        else:
            not_started += 1

        last_checked = None
        next_check = None
        if coverage:
            if coverage.last_checked_at:
                last_checked = coverage.last_checked_at.isoformat()
            if coverage.next_check_at:
                next_check = coverage.next_check_at.isoformat()

        scholarships_details.append(ScholarshipCoverageSummary(
            scholarship_id=schol.id,
            title=schol.title,
            country=schol.country,
            degree=schol.degree,
            status=schol.status,
            coverage_status=coverage_status,
            existing_contacts=existing_contacts,
            verified_contacts=verified_count,
            has_verified_email=has_verified_email,
            research_supervisors=research_supervisors,
            course_instructors=course_instructors,
            programme_faculty=programme_faculty,
            department_contacts=department_contacts,
            university_leadership=university_leadership,
            programme_office=programme_office,
            last_checked=last_checked,
            next_check=next_check,
            error_summary=coverage.last_error_summary if coverage else None,
        ))

    return CoverageReport(
        total_eligible=total_eligible,
        open_count=open_count,
        upcoming_count=upcoming_count,
        closed_excluded=0,
        unknown_lifecycle=0,
        not_started=not_started,
        existing_contacts_audited=existing_contacts_audited,
        host_mapping_pending=host_mapping_pending,
        research_in_progress=research_in_progress,
        partially_researched=partially_researched,
        research_completed=research_completed,
        source_blocked=source_blocked,
        no_public_contact_found=no_public_contact_found,
        needs_review=needs_review,
        not_applicable=not_applicable_count,
        total_existing_contacts=total_existing_contacts,
        total_verified_contacts=total_verified_contacts,
        total_verified_emails=total_verified_emails,
        total_research_supervisors=total_research_supervisors,
        total_course_instructors=total_course_instructors,
        total_programme_faculty=total_programme_faculty,
        total_department_contacts=total_department_contacts,
        total_university_leadership=total_university_leadership,
        total_programme_office=total_programme_office,
        unique_institutions=len(institutions),
        unique_departments=len(departments),
        scholarships=scholarships_details,
    )


__all__ = [
    "DEFAULT_SUPERVISOR_LIMIT",
    "MAX_SUPERVISOR_LIMIT",
    "ScholarshipNotPublic",
    "SchemaNotReadyError",
    "build_supervisor_list",
    "coverage_public_state",
    "coverage_requires_discovery",
    "count_publishable_links",
    "get_coverage",
    "get_public_scholarship_or_404",
    "global_supervisor_search",
    "GlobalSupervisorSearchRequest",
    "GlobalSupervisorSearchResult",
    "GlobalSupervisorSearchResponse",
    "get_coverage_report",
    "CoverageReport",
    "ScholarshipCoverageSummary",
]
