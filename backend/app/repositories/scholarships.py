"""Database queries for scholarship discovery."""

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from ..models import Scholarship
from ..schemas import ScholarshipQuery, ScholarshipSort


def _normalise_optional_filter(value: str | None) -> str | None:
    if value is None:
        return None

    normalised = value.strip()
    return None if not normalised or normalised.casefold() == "all" else normalised


def _escape_like(value: str) -> str:
    """Treat LIKE wildcard characters as literal search text."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _filter_conditions(query: ScholarshipQuery):
    conditions = []
    search = _normalise_optional_filter(query.search)
    country = _normalise_optional_filter(query.country)
    degree = _normalise_optional_filter(query.degree)
    funding = _normalise_optional_filter(query.funding)

    if search:
        pattern = f"%{_escape_like(search)}%"
        conditions.append(
            or_(
                Scholarship.title.ilike(pattern, escape="\\"),
                Scholarship.description.ilike(pattern, escape="\\"),
                Scholarship.country.ilike(pattern, escape="\\"),
                Scholarship.degree.ilike(pattern, escape="\\"),
                Scholarship.funding.ilike(pattern, escape="\\"),
            )
        )
    if country:
        conditions.append(func.lower(Scholarship.country) == country.casefold())
    if degree:
        conditions.append(func.lower(Scholarship.degree) == degree.casefold())
    if funding:
        conditions.append(func.lower(Scholarship.funding) == funding.casefold())
    if query.deadline_month is not None:
        conditions.append(func.extract("month", Scholarship.deadline_date) == query.deadline_month)
    if query.status is not None:
        conditions.append(Scholarship.status == query.status.value)

    return conditions


def _sort_expressions(sort: ScholarshipSort):
    null_deadline_last = case((Scholarship.deadline_date.is_(None), 1), else_=0)

    if sort is ScholarshipSort.RECOMMENDED:
        return (
            Scholarship.is_verified.desc(),
            case((Scholarship.status == "open", 0), (Scholarship.status == "closing-soon", 1), else_=2).asc(),
            Scholarship.updated_at.desc(),
            Scholarship.id.asc(),
        )
    if sort is ScholarshipSort.RECENTLY_ADDED:
        return (Scholarship.created_at.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.RECENTLY_UPDATED:
        return (Scholarship.updated_at.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.DEADLINE_SOON:
        return (null_deadline_last.asc(), Scholarship.deadline_date.asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.FULLY_FUNDED:
        return (
            case((func.lower(Scholarship.funding) == "fully funded", 0), else_=1).asc(),
            Scholarship.updated_at.desc(),
            Scholarship.id.asc(),
        )

    if sort is ScholarshipSort.DEADLINE_EARLIEST:
        return (null_deadline_last.asc(), Scholarship.deadline_date.asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.DEADLINE_LATEST:
        return (null_deadline_last.asc(), Scholarship.deadline_date.desc(), Scholarship.id.asc())
    if sort is ScholarshipSort.NAME_ASC:
        return (func.lower(Scholarship.title).asc(), Scholarship.id.asc())
    if sort is ScholarshipSort.NAME_DESC:
        return (func.lower(Scholarship.title).desc(), Scholarship.id.asc())

    return _sort_expressions(ScholarshipSort.RECOMMENDED)


def list_scholarships(session: Session, query: ScholarshipQuery) -> tuple[list[Scholarship], int]:
    conditions = _filter_conditions(query)
    total = session.scalar(select(func.count()).select_from(Scholarship).where(*conditions)) or 0
    offset = (query.page - 1) * query.limit
    statement = (
        select(Scholarship)
        .where(*conditions)
        .order_by(*_sort_expressions(query.sort))
        .offset(offset)
        .limit(query.limit)
    )
    return list(session.scalars(statement)), total


def get_scholarship_by_id(session: Session, scholarship_id: int) -> Scholarship | None:
    return session.get(Scholarship, scholarship_id)
