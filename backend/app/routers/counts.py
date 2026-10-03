"""Count Intelligence 2.0 endpoints.

One endpoint, ``POST /v2/counts/intelligence``, rather than a dozen narrow ones.
The architecture is explicit about why: a reader asking "how many, and where did
that number come from" should not have to make eight requests and reconcile the
answers. Results, summary, facets, integrity, provenance, counterfactuals and
relationships come back in one response, computed in one pass over one candidate
set.

Two design decisions are load-bearing.

**Strict request validation.** ``extra="forbid"``, exactly as the Match request
uses. A silently-ignored field in a trust feature is how a request contract rots,
and a reader who believes a filter was applied when it was not would be reading a
count for a different population than they asked for.

**One impure call.** The router resolves ``as_of`` and hands the session to
:func:`count_intelligence`. There is no counting logic here at all, and no
endpoint that computes a figure on its own.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.matching.types import MatchProfileRequest
from ..services.counting.contract import COUNT_CONTRACT_VERSION, contract_snapshot
from ..services.counting.facets import (
    DIMENSION_FIELDS,
    SELF_EXCLUSION_SEMANTICS,
    FilterState,
    known_regions,
)
from ..services.counting.service import CAPABILITIES, count_intelligence
from ..services.counting.types import CountFilter


router = APIRouter(prefix="/v2/counts", tags=["counts"])


class FilterRequest(BaseModel):
    """The active filter state.

    Every dimension accepts several values, combined as an OR; the dimensions are
    combined as an AND. The vocabulary is the count contract's own, so a filter can
    never name a dimension the counting engine does not implement.
    """

    model_config = ConfigDict(extra="forbid")

    countries: list[str] = Field(default_factory=list, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    degree: list[str] = Field(default_factory=list, max_length=64)
    field: list[str] = Field(default_factory=list, max_length=64)
    funding: list[str] = Field(default_factory=list, max_length=64)
    eligibility: list[str] = Field(default_factory=list, max_length=64)
    fit: list[str] = Field(default_factory=list, max_length=64)
    confidence: list[str] = Field(default_factory=list, max_length=64)
    coverage: list[str] = Field(default_factory=list, max_length=64)
    readiness: list[str] = Field(default_factory=list, max_length=64)
    deadline: list[str] = Field(default_factory=list, max_length=64)

    def to_state(self) -> FilterState:
        return FilterState(
            countries=tuple(self.countries),
            region=self.region,
            degree=tuple(self.degree),
            field=tuple(self.field),
            funding=tuple(self.funding),
            eligibility=tuple(self.eligibility),
            fit=tuple(self.fit),
            confidence=tuple(self.confidence),
            coverage=tuple(self.coverage),
            readiness=tuple(self.readiness),
            deadline=tuple(self.deadline),
        )


class CountIntelligenceRequest(BaseModel):
    """What to count, and which sections to return.

    ``profile`` is the same request body ``POST /scholarships/match`` accepts, so a
    client that already has a profile does not translate it. It stays optional: the
    catalogue and relationship sections describe the catalogue rather than one
    student's matches, and requiring a profile to ask for them would be a
    meaningless constraint.
    """

    model_config = ConfigDict(extra="forbid")

    profile: MatchProfileRequest | None = None
    filters: FilterRequest = Field(default_factory=FilterRequest)
    capabilities: list[str] = Field(
        default_factory=lambda: ["summary", "facets", "integrity"],
        max_length=len(CAPABILITIES),
    )

    @field_validator("capabilities")
    @classmethod
    def _reject_unknown_capabilities(cls, value: list[str]) -> list[str]:
        """Validate here rather than in the handler.

        An unknown capability is a malformed request, and FastAPI's own validation
        already turns that into a 422. Raising a bare ``ValueError`` from the handler
        instead would surface as a 500 - telling the caller the server broke, when
        in fact the request was wrong.
        """
        known = set(CAPABILITIES)
        unknown = [name for name in value if name not in known]
        if unknown:
            raise ValueError(
                f"unknown capabilities {unknown}; supported: {sorted(known)}"
            )
        # Deduplicated while preserving order, so a repeated capability does not
        # produce a response that echoes the request rather than the contract.
        return list(dict.fromkeys(value))


@router.post("/intelligence")
def post_count_intelligence(
    payload: CountIntelligenceRequest,
    session: Session = Depends(get_db),
    as_of: date | None = Query(
        default=None,
        description=(
            "The date the counts are resolved against. Injectable so a count can be "
            "reproduced exactly; defaults to today."
        ),
    ),
) -> dict:
    """Every count, with its provenance, in one response.

    The profile is not persisted, logged or echoed beyond what a count needs to be
    explainable - the same rule the Match endpoint follows.
    """
    effective_date = as_of or date.today()

    return count_intelligence(
        session,
        payload.profile or MatchProfileRequest(),
        as_of=effective_date,
        filters=payload.filters.to_state(),
        capabilities=payload.capabilities,
    )


@router.get("/contract")
def get_count_contract() -> dict:
    """The complete count contract.

    Published so any consumer can check a number against the definition it claims to
    satisfy, without reading the source. This is the machine-readable form of the
    document the counting layer is specified by.
    """
    return {
        **contract_snapshot(),
        "facet_self_exclusion": SELF_EXCLUSION_SEMANTICS,
        "filter_dimensions": {
            dimension: field_name for dimension, field_name in DIMENSION_FIELDS.items()
        },
        "known_regions": list(known_regions()),
        "capabilities": list(CAPABILITIES),
    }


__all__ = ["CountIntelligenceRequest", "FilterRequest", "router"]