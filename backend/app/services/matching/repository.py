"""Candidate loading for the matching engine.

One bounded query, no N+1. The engine scores thousands of records in memory, so
the only thing that matters here is getting the needed columns across the wire
exactly once.

Only columns the engine actually reads are selected. The full row includes
``description``, ``notes``, ``best_fit`` and two large JSON blobs that the
matching path never interprets; selecting the whole ORM entity would drag them
across for every candidate and grow linearly with the catalogue for no benefit.

Public visibility is not reimplemented. ``public_visibility_conditions`` is the
single existing definition of "may be shown publicly", and the directory, the
statistics and this loader all call it, so a match result can never surface a
record the catalogue is hiding.
"""

from __future__ import annotations

from datetime import date
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import Scholarship
from ...repositories.scholarships import public_visibility_conditions
from ..list_columns import ListColumnShapeError, normalize_list_column
from .constants import MATCH_CANDIDATE_HARD_LIMIT
from .types import ScholarshipFacts


#: Exactly the columns ScholarshipFacts needs. Kept as an explicit tuple so a
#: schema change that adds a column cannot silently widen the payload.
MATCH_COLUMNS = (
    Scholarship.id,
    Scholarship.title,
    Scholarship.country,
    Scholarship.degree,
    Scholarship.funding,
    Scholarship.program_type,
    Scholarship.status,
    Scholarship.deadline_date,
    Scholarship.deadline_display,
    Scholarship.deadline_precision,
    Scholarship.eligibility,
    Scholarship.eligibility_summary,
    Scholarship.requirements,
    Scholarship.documents,
    Scholarship.coverage,
    Scholarship.english_requirement,
    Scholarship.funding_amount,
    Scholarship.funding_currency,
    Scholarship.funding_period,
    Scholarship.tuition_coverage,
    Scholarship.living_cost_coverage,
    Scholarship.travel_coverage,
    Scholarship.fully_funded,
    Scholarship.official_source,
    Scholarship.official_source_url,
    Scholarship.official_details,
    Scholarship.is_verified,
    Scholarship.verification_status,
    Scholarship.last_verified_date,
    Scholarship.next_verification_due,
    Scholarship.image_url,
    Scholarship.image_alt_text,
)


class CandidateRow(NamedTuple):
    """One row as it comes back from the database."""

    id: int
    title: str
    country: str
    degree: str
    funding: str | None
    program_type: str | None
    status: str | None
    deadline_date: date | None
    deadline_display: str | None
    deadline_precision: str | None
    eligibility: list | None
    eligibility_summary: str | None
    requirements: list | None
    documents: list | None
    coverage: list | None
    english_requirement: str | None
    funding_amount: float | None
    funding_currency: str | None
    funding_period: str | None
    tuition_coverage: bool | None
    living_cost_coverage: bool | None
    travel_coverage: bool | None
    fully_funded: bool | None
    official_source: str | None
    official_source_url: str | None
    official_details: dict | None
    is_verified: bool | None
    verification_status: str | None
    last_verified_date: date | None
    next_verification_due: date | None
    image_url: str | None
    image_alt_text: str | None


def load_candidates(
    session: Session,
    country_filter: str | None = None,
    hard_limit: int = MATCH_CANDIDATE_HARD_LIMIT,
) -> list[CandidateRow]:
    """Load every publicly visible candidate in a single query.

    ``country_filter`` is a cheap pre-filter applied in SQL so a student looking
    at one country does not score the whole catalogue in memory. It narrows the
    candidate set only; it never changes how a record is scored.
    """
    statement = select(*MATCH_COLUMNS).where(*public_visibility_conditions())

    if country_filter:
        # Compared case-insensitively without a LIKE wildcard, so a filter value
        # containing % or _ cannot widen the result set.
        statement = statement.where(Scholarship.country.ilike(country_filter, escape="\\"))

    statement = statement.order_by(Scholarship.id.asc()).limit(hard_limit)
    return [CandidateRow(*row) for row in session.execute(statement).all()]


def _list_field(value: object, field: str) -> list[str]:
    """Read one ``list[str]`` column without destroying it when it is malformed.

    This used to be ``list(value or [])``. That is correct for a real list and
    for NULL, and quietly wrong for a stored bare string, which it turns into a
    list of single characters::

        list("Full tuition fees" or [])  ->  ['F', 'u', 'l', 'l', ' ', ...]

    The engine then reads funding coverage one character at a time, so a record
    publishing "Full tuition fees" is reported as *unknown* coverage instead of
    the tuition-plus-living it actually states - and unknown is not neutral here,
    it removes an evaluated component from the fit denominator and moves the
    score. Against the production catalogue that was 34 public rows whose
    funding coverage read as unknown, and the funding distribution counted them
    as unstated rather than counting them at all.

    A bare string is therefore reshaped to a single-element list with its text
    preserved byte for byte, which is the shape the column is declared to have.
    A value that is neither a list, a string nor null cannot be reshaped without
    guessing, so it is read as empty: the engine's own rule is that an unreadable
    published value is unknown rather than invented, and coercing it into text
    would invent something.

    This changes no scoring rule. It stops malformed storage from silently
    rewriting the input the rules were written against.
    """
    try:
        normalized, _changed = normalize_list_column(value, field=field)
    except ListColumnShapeError:
        return []
    return normalized


def to_facts(row: CandidateRow) -> ScholarshipFacts:
    """Convert a database row into the engine's input type."""
    return ScholarshipFacts(
        id=row.id,
        title=row.title,
        country=row.country,
        degree_levels=row.degree,
        funding_label=row.funding,
        program_type=row.program_type,
        status=row.status,
        deadline_date=row.deadline_date.isoformat() if row.deadline_date else None,
        deadline_display=row.deadline_display,
        deadline_precision=row.deadline_precision,
        eligibility=_list_field(row.eligibility, "eligibility"),
        eligibility_summary=row.eligibility_summary,
        requirements=_list_field(row.requirements, "requirements"),
        documents=_list_field(row.documents, "documents"),
        coverage=_list_field(row.coverage, "coverage"),
        english_requirement=row.english_requirement,
        funding_amount=float(row.funding_amount) if row.funding_amount is not None else None,
        funding_currency=row.funding_currency,
        funding_period=row.funding_period,
        tuition_coverage=row.tuition_coverage,
        living_cost_coverage=row.living_cost_coverage,
        travel_coverage=row.travel_coverage,
        fully_funded=row.fully_funded,
        official_source=row.official_source,
        official_source_url=row.official_source_url,
        official_details=row.official_details if isinstance(row.official_details, dict) else None,
        is_verified=row.is_verified,
        verification_status=row.verification_status,
        last_verified_date=row.last_verified_date.isoformat() if row.last_verified_date else None,
        next_verification_due=row.next_verification_due.isoformat() if row.next_verification_due else None,
        image_url=row.image_url,
        image_alt_text=row.image_alt_text,
    )