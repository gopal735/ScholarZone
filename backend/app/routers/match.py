"""ScholarZone Match endpoints.

Thin by design. The router validates the request, calls the service and returns
the typed response. There is no scoring logic here, and no profile data is
logged, stored or echoed beyond what a result needs to be explainable.

Three endpoints, and all three are stateless:

``POST /scholarships/match``
    Scores the catalogue. The profile arrives in a POST body rather than a query
    string, so a student's nationality, age and academic record never reach an
    access log or a referrer header.

``GET /scholarships/match/profile-options``
    The controlled vocabularies the form needs, served from the engine's own
    configuration so the interface cannot offer a field, test or funding state
    the engine does not understand.

``POST /scholarships/match/parse-profile``
    Turns one optional free-text sentence into a profile payload, deterministically
    and with every interpretation reported. It cannot score anything: its output
    is a normal request body that then goes through the same validation as a
    hand-filled form.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..services.matching.config import SORT_OPTIONS
from ..services.matching.engine import band_labels
from ..services.matching.nlp import REGION_MEMBERS, parse_natural_language_profile, parsed_profile_response
from ..services.matching.normalize import COUNTRY_CODES
from ..services.matching.service import match_scholarships
from ..services.matching.types import MatchProfileRequest, MatchResponse


router = APIRouter(prefix="/scholarships", tags=["match"])


class NaturalLanguageProfileRequest(BaseModel):
    """One optional free-text message.

    ``extra="forbid"`` for the same reason as the match request: an unrecognised
    field in a trust feature is a bug, and silent acceptance is how a request
    contract rots.
    """

    model_config = ConfigDict(extra="forbid")

    # Optional on purpose. The field itself is optional in the product, so an
    # empty body must produce the normal empty confirmation state rather than a
    # 422 the interface would have to special-case. A body that supplies text at
    # all still has to be a non-empty string.
    text: str | None = Field(default=None, max_length=600)


@router.post("/match", response_model=MatchResponse)
def create_match_results(
    profile: MatchProfileRequest,
    session: Session = Depends(get_db),
) -> MatchResponse:
    """Score the catalogue against a supplied student profile.

    Stateless: nothing is persisted and no account is required. The response
    carries every version it was computed with, the Academic Profile Index, the
    profile strength, the full ranking, and the component breakdown behind every
    score.
    """
    return match_scholarships(session, profile, as_of=date.today())


@router.post("/match/parse-profile")
def parse_profile(payload: NaturalLanguageProfileRequest) -> dict:
    """Interpret one optional sentence as a profile.

    Deterministic and validation-first: every value is matched against
    ScholarZone's own approved lists, the matched phrase is reported back, and
    anything that could not be resolved is returned as unresolved rather than
    dropped or guessed. The student edits the result before anything is
    calculated.

    No AI provider is involved and none is added for this. A model-generated
    interpretation would be fluent and unverifiable, which is the opposite of
    what this product claims.
    """
    return parsed_profile_response(parse_natural_language_profile(payload.text))


def _country_options() -> list[str]:
    """Display names for the country lookup table.

    ``COUNTRY_CODES`` maps lower-case names and aliases to ISO codes, so its keys
    are machine-shaped. Rendering them directly put "germany" and "uk" in front
    of the user, and the short aliases read as typos. Names of four characters or
    more are titled for display; the rest are two-letter shorthands that belong
    in the lookup, not in a picker. The backend normalises whatever arrives, so a
    title-cased name resolves exactly as the lower-case key would.
    """
    return sorted(name.title() for name in COUNTRY_CODES if len(name) > 3)


@router.get("/match/profile-options")
def get_profile_options() -> dict:
    """The controlled vocabularies the profile form needs.

    Served from the engine's own configuration so the form cannot offer a field,
    test or funding state the engine does not understand. A mismatch there would
    silently produce UNKNOWN components.
    """
    from ..services.matching.normalize import KNOWN_LANGUAGE_TESTS
    from ..services.matching.taxonomy import all_relationship_levels, known_field_keys
    from ..services.matching.types import (
        DegreeLevel,
        FundingRequirement,
        FundingState,
        GradingScale,
        StudyMode,
    )

    return {
        "fields": [{"key": key, "label": key.replace("_", " ").title()} for key in known_field_keys()],
        "degree_levels": [level.value for level in DegreeLevel],
        "study_modes": [mode.value for mode in StudyMode],
        "grading_scales": [scale.value for scale in GradingScale if scale is not GradingScale.UNKNOWN],
        "funding_requirements": [item.value for item in FundingRequirement],
        "funding_states": [state.value for state in FundingState],
        "language_tests": sorted(KNOWN_LANGUAGE_TESTS),
        "countries": _country_options(),
        "field_relationship_levels": all_relationship_levels(),
        # Every list below is served complete. Nothing is truncated: an option
        # that exists in the vocabulary and is absent from the picker is
        # indistinguishable from an option that does not exist.
        "regions": sorted(REGION_MEMBERS),
        "sort_options": list(SORT_OPTIONS),
        "band_labels": band_labels(),
    }