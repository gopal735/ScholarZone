"""Country Intelligence endpoints.

Thin by design, in the same way ``routers/counts.py`` and ``routers/match.py``
are: no scoring, no aggregation and no business rule lives here. Every figure is
produced by :mod:`app.services.country_intelligence`, and this module only
declares the request shapes and hands off.

The requests are ``extra="forbid"`` and validated, so a mistyped field is a 422
rather than a silently ignored input. Validation failures come from pydantic; this
module raises no ``HTTPException`` and catches nothing, so an unexpected internal
failure surfaces as a 500 rather than being dressed up as an empty result.

Four capabilities, matching the four things a student actually asks:

* ``GET  /v2/countries`` - what countries do you know about, and what do you hold
* ``GET  /v2/countries/{iso2}`` - everything known about one country
* ``POST /v2/countries/compare`` - these countries, side by side
* ``POST /v2/countries/calculate`` - what does this cost me

A fifth, ``GET /v2/countries/meta``, publishes the vocabulary the other four use -
the value-status list, the study levels, the comparison rows - so the interface
cannot invent a status or a label that the backend does not recognise.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.country_intelligence.service import (
    calculate_cost,
    compare_countries,
    country_detail,
    country_summaries,
    intelligence_meta,
)
from ..services.country_intelligence.derive import CITY_TIERS, STUDY_LEVELS

router = APIRouter(prefix="/v2/countries", tags=["country-intelligence"])

#: Bounded so a client cannot ask the service to resolve an unbounded country
#: list and turn one request into a large fan-out.
MAX_COMPARE_COUNTRIES = 6


class CompareRequest(BaseModel):
    """Which countries to place side by side."""

    model_config = ConfigDict(extra="forbid")

    iso2: list[str] = Field(min_length=2, max_length=MAX_COMPARE_COUNTRIES)

    @field_validator("iso2")
    @classmethod
    def _bound_length(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError(
                "Comparing one country against nothing answers no question; "
                "choose at least two."
            )
        return value


class CalculateRequest(BaseModel):
    """One cost scenario.

    ``study_level`` and ``city_tier`` are validated against the vocabulary the
    service publishes rather than as free text, so a typo returns a 422 naming
    the valid options instead of a scenario full of ``UNKNOWN`` figures.
    """

    model_config = ConfigDict(extra="forbid")

    iso2: str = Field(min_length=2, max_length=2)
    study_level: str = Field(default="bachelor", max_length=16)
    city_tier: str = Field(default="medium", max_length=16)
    duration_years: float = Field(default=2, gt=0, le=10)

    @field_validator("study_level")
    @classmethod
    def _known_level(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in STUDY_LEVELS:
            raise ValueError(
                f"study_level must be one of {', '.join(STUDY_LEVELS)}, not {value!r}."
            )
        return normalised

    @field_validator("city_tier")
    @classmethod
    def _known_tier(cls, value: str) -> str:
        normalised = value.strip().lower()
        if normalised not in CITY_TIERS:
            raise ValueError(
                f"city_tier must be one of {', '.join(CITY_TIERS)}, not {value!r}."
            )
        return normalised

    @field_validator("iso2")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.strip().upper()


@router.get("/meta")
def get_country_intelligence_meta() -> dict[str, Any]:
    """Versions, the value-status vocabulary, and the available comparison rows.

    Unauthenticated and session-free on purpose: it is static metadata, and
    loading it must not depend on the catalogue being reachable.
    """
    return intelligence_meta()


@router.get("")
def list_countries(session: Session = Depends(get_db)) -> dict[str, Any]:
    """Every country, with its measured catalogue facts and researched headline.

    The response carries each country's ``researched_sections`` and
    ``missing_sections`` so a client can tell "we hold scholarships here and have
    not researched the cost" apart from "we hold scholarships here and the cost is
    zero".
    """
    summaries = country_summaries(session)
    return {
        "countries": [summary.to_dict() for summary in summaries],
        "count": len(summaries),
    }


@router.post("/compare")
def compare(  # noqa: A003 - route name reads better than the verb at the call site
    request: CompareRequest, session: Session = Depends(get_db)
) -> dict[str, Any]:
    """A comparison matrix across the countries that can actually answer.

    Countries are quoted in their own currencies and no winner is declared; the
    response states why, so a client cannot add one.
    """
    return compare_countries(session, request.iso2)


@router.post("/calculate")
def calculate(
    request: CalculateRequest, session: Session = Depends(get_db)
) -> dict[str, Any]:
    """The cost calculator, including every figure it refused to produce."""
    return calculate_cost(
        session,
        iso2=request.iso2,
        level=request.study_level,
        tier=request.city_tier,
        years=request.duration_years,
    )


@router.get("/{iso2}")
def read_country(
    iso2: str = Path(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$"),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Everything known about one country.

    An unknown country returns ``{"country": None}`` with 200 rather than a 404.
    A country absent from both planes is a normal state - we hold no scholarships
    for it and have not researched it - and the interface renders that as an empty
    country page rather than as an error the user has to be told about.
    """
    detail = country_detail(session, iso2.strip().upper())
    if detail is None:
        return {"country": None, "iso2": iso2.strip().upper(), "known": False}
    return {**detail, "known": True}


__all__ = ["router"]