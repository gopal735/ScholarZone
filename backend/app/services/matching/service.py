"""Database-facing orchestration for ScholarZone Match.

The boundary between the impure world and the pure engine. This is the only
place a database session and a calendar date enter, and both are injected so the
engine itself stays reproducible.

The profile is never persisted. It arrives in a request body, is used to compute
a response and is discarded. Nothing is written, nothing is logged, and nothing
identifying the student is returned.

Every count, facet and average in the response is computed here from the ranked
result list, and each one names the set it describes: summary counts cover the
whole analysed universe, facet counts cover the returned page. Nothing is
hardcoded, estimated or carried over between requests, and the counting module
asserts its own reconciliation invariants before a response is allowed to exist.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from .config import MATCH_CANDIDATE_HARD_LIMIT
from .engine import (
    build_profile_index_result,
    engine_metadata,
    profile_index_for,
    profile_strength_for,
    rank_results,
    score_record,
    summarise,
)
from .normalize import normalise_profile
from .repository import load_candidates, to_facts
from .summaries import assert_facets_reconcile
from .types import EligibilityStatus, MatchResponse, MatchProfileRequest


def match_scholarships(
    session: Session,
    request: MatchProfileRequest,
    as_of: date | None = None,
) -> MatchResponse:
    """Score the catalogue against a supplied profile.

    ``as_of`` defaults to today and is otherwise injectable so tests can pin the
    clock. It is the only date the engine sees: the matching code never calls
    ``date.today()`` itself, which is what makes two runs on the same day produce
    identical output and makes any other pair of dates reproducible too.
    """
    effective_date = as_of or date.today()
    profile = normalise_profile(request)

    rows = load_candidates(
        session,
        country_filter=profile.country_filter,
        hard_limit=MATCH_CANDIDATE_HARD_LIMIT,
    )

    results = [score_record(profile, to_facts(row), effective_date) for row in rows]

    if not profile.include_ineligible:
        # Dropped from the analysed universe rather than scored and then hidden.
        # A record the reader asked not to see must not still be counted in the
        # total, or the three eligibility states would no longer sum to it.
        results = [
            result
            for result in results
            if result.eligibility is not EligibilityStatus.INELIGIBLE
        ]

    ranked = rank_results(results)
    truncated = len(ranked) > profile.limit
    limited = ranked[: profile.limit]

    # Two sets, named explicitly. Every summary count describes the whole ranked
    # universe, so the locked identities hold against total_candidates even when
    # the response was truncated. Facets describe the returned page, so a filter's
    # count is never stale relative to the list it filters.
    counted = summarise(
        ranked,
        limited,
        total_candidates=len(ranked),
        truncated=truncated,
    )
    summary = counted["summary"]
    facets = counted["facets"]
    assert_facets_reconcile(facets, limited)

    metadata = engine_metadata(effective_date)

    # The per-result ``score_breakdown`` is the authoritative account of what was
    # evaluated for each scholarship, because it differs from record to record.
    # These two lists are the union across the returned page, which is what the
    # "How this is calculated" panel needs in order to say, once, which
    # dimensions had any published data behind them at all.
    evaluated_components = sorted(
        {
            component.name
            for result in limited
            for component in result.score_breakdown
            if component.score is not None
        }
    )
    unevaluated_components = sorted(
        {
            component.name
            for result in limited
            for component in result.score_breakdown
            if component.score is None
        }
    )

    return MatchResponse(
        engine_version=metadata["engine_version"],
        scoring_config_version=metadata["scoring_config_version"],
        taxonomy_version=metadata["field_taxonomy_version"],
        as_of=metadata["as_of"],
        explanation={
            **metadata,
            "evaluated_components": evaluated_components,
            "unevaluated_components": unevaluated_components,
        },
        profile_index=build_profile_index_result(profile_index_for(profile)),
        profile_strength=profile_strength_for(profile),
        results=limited,
        truncated=truncated,
        **{
            key: value
            for key, value in counted.items()
            if key not in {"summary", "facets"}
        },
        summary=summary,
        facets=facets,
    )


__all__ = ["match_scholarships"]