"""Global Study-to-Career Strategist endpoints.

Thin by design, in the same way ``routers/countries.py`` is: no scoring, no
business rule and no database write lives here. Every figure is produced by
:mod:`app.services.strategist`, and this module only declares request shapes and
hands off.

Registered only when ``settings.strategist_enabled`` is true (default OFF), so
with the flag off these paths are a 404 absence rather than a disabled feature.
Requests are ``extra="forbid"`` and validated, so a mistyped field is a 422 and a
bad subject/degree is a 422 from the service's guard, never a silent default.

Endpoints:

* ``GET  /v2/strategist/subjects``    - the launch subjects and their coverage
* ``POST /v2/strategist/plan``        - the criterion-by-criterion comparison
* ``GET  /v2/strategist/pathway/{iso2}`` - the student-visa -> citizenship timeline
* ``GET  /v2/strategist/gaps``        - admin data-gap report (country x subject)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..services.strategist.service import (
    MAX_COMPARE_COUNTRIES,
    ValidationError,
    coverage_matrix,
    pathway_timeline,
    plan,
    subject_catalog,
)

router = APIRouter(prefix="/v2/strategist", tags=["strategist"])


def _verify_admin_secret(provided_secret: str | None) -> bool:
    """Constant-time-by-default admin check, matching ``admin_dashboard``.

    The comparison, subjects and pathway endpoints are public research read-only
    surfaces. The gap report is an *internal* research-prioritisation view, so it is
    gated the same way every admin endpoint is gated: the feature being enabled must
    never make an internal report public.
    """
    settings = get_settings()
    expected = getattr(settings, "admin_secret", None)
    if expected is None or provided_secret is None:
        return False
    return provided_secret == expected


class PlanRequest(BaseModel):
    """The wizard's answers, which drive one comparison request."""

    model_config = ConfigDict(extra="forbid")

    subject_key: str = Field(min_length=1, max_length=64)
    degree: str = Field(min_length=1, max_length=16)
    funding_model: str | None = Field(default=None, max_length=32)
    #: Monthly/annual budget in Bangladeshi Taka, informational only; it never
    #: changes which figures exist, only how cost coverage is described beside them.
    budget_bdt: float | None = Field(default=None, ge=0)
    #: The user's editable priority weights by category. Echoed back unchanged.
    weights: dict[str, int] | None = None
    #: Optional explicit country list; when omitted the service compares the
    #: best-covered countries up to the cap.
    iso2s: list[str] | None = Field(default=None, max_length=MAX_COMPARE_COUNTRIES)


@router.get("/subjects")
def list_subjects() -> dict[str, Any]:
    return {"subjects": subject_catalog()}


@router.post("/plan")
def build_plan(request: PlanRequest, session: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        return plan(
            session,
            subject_key=request.subject_key,
            degree=request.degree,
            funding_model=request.funding_model,
            budget_bdt=request.budget_bdt,
            weights=request.weights,
            iso2s=request.iso2s,
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/pathway/{iso2}")
def pathway(iso2: str = Path(min_length=2, max_length=2)) -> dict[str, Any]:
    return pathway_timeline(iso2)


@router.get("/gaps")
def gaps(
    x_admin_secret: str | None = Header(None, alias="X-Admin-Secret"),
) -> dict[str, Any]:
    """Admin/internal: which country x subject pairs lack occupation-level evidence.

    Gated by ``X-Admin-Secret`` like every admin endpoint: the gap report guides
    research effort and is not a public surface, so the strategist feature being
    enabled must not expose it. Read-only; writes nothing; publishes no secret.
    """
    if not _verify_admin_secret(x_admin_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin secret.",
        )
    return coverage_matrix()
