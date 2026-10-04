"""Internal maintenance dispatcher endpoint.

Triggered by exactly one daily Vercel Cron. It reconciles, claims and
dispatches - it never runs the maintenance worker, and it never holds a request
open for GitHub Actions to finish.

Authentication is mandatory. Vercel Cron sends ``Authorization: Bearer
$CRON_SECRET``; that is the platform-supported mechanism and it is the only
accepted credential. An unauthenticated caller gets 404 rather than 401, so the
endpoint does not advertise itself.
"""
from __future__ import annotations

import datetime as dt
import hmac
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.database import get_session_factory
from app.services.maintenance_dispatch import (
    CONFIGURATION_BLOCKED,
    run_backstop_once,
)

router = APIRouter(tags=["internal"])

CRON_SECRET_ENV = "CRON_SECRET"


class DispatchReportBody(BaseModel):
    as_of: str
    considered: list[str]
    claimed: list[str]
    dispatched: list[str]
    prevented_duplicates: list[str]
    expired: list[str]
    expired_leases: list[str]
    classifications: dict


def _secret() -> str | None:
    value = (os.environ.get(CRON_SECRET_ENV) or "").strip()
    return value or None


def cron_is_authorised(request: Request) -> bool:
    """Constant-time check of the Cron bearer token."""
    expected = _secret()
    if not expected:
        return False
    header = request.headers.get("authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer":
        return False
    return hmac.compare_digest(token.strip(), expected)


@router.post("/internal/maintenance/dispatch", response_model=DispatchReportBody)
def dispatch_maintenance(request: Request) -> DispatchReportBody:
    """One backstop pass for missed logical slots."""
    if not cron_is_authorised(request):
        # Not a 401: this endpoint should not be discoverable.
        raise HTTPException(status_code=404, detail="Not found")

    as_of = dt.datetime.now(dt.timezone.utc)
    report = run_backstop_once(get_session_factory(), as_of=as_of)
    return DispatchReportBody(
        as_of=report.as_of.isoformat(),
        considered=report.considered,
        claimed=report.claimed,
        dispatched=report.dispatched,
        prevented_duplicates=report.prevented_duplicates,
        expired=report.expired,
        expired_leases=report.expired_leases,
        classifications=report.classifications,
    )


@router.get("/internal/maintenance/status")
def maintenance_status(request: Request) -> dict:
    """Scheduler observability, from persisted state only."""
    if not cron_is_authorised(request):
        raise HTTPException(status_code=404, detail="Not found")
    from app.services.maintenance_dispatch import observability

    return observability(get_session_factory(), as_of=dt.datetime.now(dt.timezone.utc))


__all__ = ["router", "cron_is_authorised", "CONFIGURATION_BLOCKED"]
