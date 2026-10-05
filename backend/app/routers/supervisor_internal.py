"""The bounded, authenticated Supervisor discovery trigger.

One route, one scholarship, one proof.

This exists because the Supervisor pipeline had a real implementation, real
personhood gating and real storage - and **no production entry point at all**.
Before this router, the only non-test caller of discovery was
``scripts/supervisor_backfill.py``, run by hand against a database someone had
credentials for. That is the gap this closes, and nothing wider is being opened
here.

**What it deliberately cannot do.** Every one of these is an absence of code, not
a promise in a docstring, and each has a test that fails if the corresponding
capability appears:

* it cannot discover for a country, a batch, or more than the one scholarship in
  the path - there is no list, no range, no wildcard and no "all" parameter;
* it cannot accept a URL. The source is read from the scholarship's own recorded
  official source, so an arbitrary third-party URL cannot be introduced;
* it cannot dispatch maintenance, run the scheduler, or trigger verification
  cron - it imports none of them;
* it cannot switch on browser rendering. It passes no render budget, so the
  renderer reports itself unavailable and a client-side directory stays
  ``SOURCE_REQUIRES_RENDERING`` rather than being rendered;
* it cannot seed the scholarship ``DiscoveryCandidate`` subsystem, which belongs
  to new-scholarship discovery and is a different pipeline entirely;
* it cannot write anything ungated. It calls
  :func:`app.services.supervisor_discovery.collect_supervisor_plan`, which has no
  session, and then
  :func:`app.services.supervisor_discovery.persist_supervisor_plan`, which
  commits once.

**Two independent conditions must both hold.** The caller must present the
verification secret, *and* the deployment must have Supervisor discovery
explicitly enabled. Either alone is refused. The secret answers "is this caller
authorised"; the flag answers "is this capability switched on here". Conflating
them into one is how a capability ends up silently live in production because
somebody rotated a credential.

**Order of checks, and why.** Authentication is checked before the flag, and the
flag before the target. A caller without the secret learns nothing about whether
the feature exists, and a disabled deployment does not spend time resolving a
scholarship - so an unauthenticated probe cannot be used to enumerate which ids
are valid.

**The secret is never taken from the body.** It arrives in the
``X-Verification-Secret`` header, matching the convention already used by
``/internal/verify/trigger`` and the rest of this application, and is compared
with :func:`secrets.compare_digest` so a wrong guess cannot be refined by timing
the rejection.
"""

from __future__ import annotations

import logging
import secrets as _secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import Scholarship
from ..services.supervisor_discovery import (
    collect_supervisor_plan,
    persist_supervisor_plan,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/supervisor", tags=["internal-supervisor"])

VERIFICATION_SECRET_HEADER = "X-Verification-Secret"

#: Scholarship ids are positive integers. The bound is expressed through the type
#: rather than validated after the fact, so an oversized or negative id is
#: rejected by the router before any handler runs.
ScholarshipIdPath = Path(ge=1, description="Exactly one scholarship to discover for.")


class SupervisorDiscoveryReport(BaseModel):
    """What one bounded run did, and what it refused.

    Counts are separated by outcome on purpose. A run that examined nine
    candidates and approved two has reported something quite different from one
    that approved two, and collapsing them would make a run that is quietly
    rejecting almost everything look identical to a healthy one.

    ``rejected_by_gate`` is a histogram over the gates in
    :data:`app.services.supervisor_gating.GATE_ORDER`, so the dominant reason for
    refusal is legible without opening logs.
    """

    scholarship_id: int
    #: The coverage status this run left behind.
    status: str
    #: ``searched`` | ``blocked`` | ``source_blocked`` | ``search_pending`` -
    #: whether the institution's own pages were actually read.
    outcome: str
    pages_fetched: int
    #: Candidates that reached the gates.
    examined: int
    #: Candidates that cleared every gate and were persisted.
    approved: int
    #: Candidates refused, and why.
    rejected: int
    rejected_by_gate: dict[str, int]
    #: Professors actually written by this run. Not "approved": nothing is counted
    #: until it exists in the database.
    professors_written: int
    detail: str | None = None
    #: Always false here, and reported so a reader can check it rather than trust
    #: it. This trigger never enables the browser renderer.
    render_requested: bool = False


def require_verification_secret(
    x_verification_secret: str | None = Header(None, alias=VERIFICATION_SECRET_HEADER),
) -> str:
    """Admit only a caller holding the configured verification secret.

    Fails closed: an unconfigured deployment admits nobody, including the owner,
    because "nobody" is a safe answer and a silently-open endpoint is not.

    Raises 401 rather than 403. Without a valid secret the caller has not
    established an identity at all, and a 403 would imply one exists.
    """
    expected = get_settings().verification_secret
    if expected and x_verification_secret:
        if _secrets.compare_digest(x_verification_secret, expected):
            return x_verification_secret
    logger.warning("Rejected unauthenticated Supervisor discovery attempt.")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing verification secret.",
        headers={"WWW-Authenticate": VERIFICATION_SECRET_HEADER},
    )


def _require_discovery_enabled() -> None:
    """Refuse unless Supervisor discovery is explicitly enabled here.

    Separate from authentication on purpose: a valid secret held by a deployment
    that never switched the capability on must still be refused. Otherwise the
    capability is live everywhere the secret is, which is the opposite of
    default-off.
    """
    if not get_settings().supervisor_discovery_enabled:
        logger.error(
            "Supervisor discovery trigger is disabled. Set "
            "SCHOLARZONE_SUPERVISOR_DISCOVERY_ENABLED=true on the deployment to "
            "allow it. This is independent of SCHOLARZONE_SUPERVISOR_RENDER_ENABLED."
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Supervisor discovery execution is disabled on this deployment."
            ),
        )


@router.post(
    "/discover/{scholarship_id}",
    status_code=status.HTTP_200_OK,
    response_model=SupervisorDiscoveryReport,
)
def discover_supervisors_for_one_scholarship(
    scholarship_id: int = ScholarshipIdPath,
    db: Session = Depends(get_db),
    _secret: str = Depends(require_verification_secret),
) -> SupervisorDiscoveryReport:
    """Run bounded Supervisor discovery for exactly one scholarship.

    The whole contract is the path: a single integer. There is no body, no
    source-URL field and no batch parameter, so there is nothing for a caller to
    widen the scope with.

    Order of operations, which is the safety property rather than an incidental
    detail:

    1. authenticate the caller;
    2. confirm discovery execution is enabled on this deployment;
    3. resolve exactly one scholarship;
    4. **collect and gate everything, writing nothing**;
    5. persist only the approved set, in one transaction.

    Step 4 happens before step 5 and there is no path that skips it, so a run
    whose candidates all fail leaves no professor, relationship, evidence or
    availability row behind. Step 5 still updates the coverage row, because "we
    looked and found nothing" is itself a fact the product must record - it is
    written at the same single boundary and is the only thing written when nothing
    was approved.

    The response reports what was approved *and* what was refused, so a run that
    rejected everything is visibly different from a run that approved everything.
    """
    _require_discovery_enabled()

    scholarship = db.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found.",
        )

    # No render budget is passed. A client-side directory therefore stays
    # SOURCE_REQUIRES_RENDERING, which is the honest answer, instead of silently
    # enabling a browser in production.
    plan = collect_supervisor_plan(scholarship)

    outcome = persist_supervisor_plan(db, scholarship, plan)

    if plan.coverage_override is not None:
        outcome_kind = "source_blocked"
    elif plan.blocked:
        outcome_kind = "blocked"
    elif plan.searched:
        outcome_kind = "searched"
    else:
        outcome_kind = "search_pending"

    logger.info(
        "Bounded Supervisor discovery for scholarship %s: status=%s examined=%s "
        "approved=%s rejected=%s professors_written=%s",
        plan.scholarship_id,
        outcome.status,
        plan.examined_count,
        plan.approved_count,
        plan.rejected_count,
        outcome.professors_found,
    )

    return SupervisorDiscoveryReport(
        scholarship_id=plan.scholarship_id,
        status=outcome.status,
        outcome=outcome_kind,
        pages_fetched=plan.pages_fetched,
        examined=plan.examined_count,
        approved=plan.approved_count,
        rejected=plan.rejected_count,
        rejected_by_gate=dict(sorted(plan.rejection_reasons.items())),
        professors_written=outcome.professors_found,
        detail=outcome.detail,
    )


__all__ = [
    "VERIFICATION_SECRET_HEADER",
    "ScholarshipIdPath",
    "SupervisorDiscoveryReport",
    "require_verification_secret",
    "router",
]
