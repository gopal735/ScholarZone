"""One-shot, authenticated Supervisor discovery for exactly one scholarship.

Supervisor discovery had no production entry point. ``discover_for_scholarship``
was reachable only from ``run_discovery_batch``, which was reachable only from
``scripts/supervisor_backfill.py`` - a manual CLI that connects straight to the
database. The ``supervisors`` router is read-only, and the two ``/internal``
discovery routers are the *scholarship* DiscoveryCandidate system, which is a
different subsystem entirely. So the pipeline that builds the verified-people
data had never been run against production through the application at all.

This router is that missing entry point, and it is deliberately the smallest one
that can exist. Each of the following is a property of the code below rather than
an intention:

**One scholarship, never more.** The scholarship id is a path parameter and
``discover_for_scholarship`` takes a single ``Scholarship``. There is no
collection route, no ``limit``, no query parameter that widens the set, and no
call into ``run_discovery_batch``. Running discovery twice means calling this
endpoint twice with two ids.

**No country path, no batch path.** Neither ``run_discovery_round`` nor
``batch_discover_next_cycles`` nor ``discover_next_cycle`` is imported here. The
country and batch discovery endpoints live in other routers and stay as they
were.

**No maintenance.** Nothing from ``scholarzone_maintenance``, ``maintenance_*`` or
``lifecycle_manager`` is imported, and no scheduler is started. The maintenance
worker never calls Supervisor discovery, and this endpoint never calls the
maintenance worker.

**No scholarship DiscoveryCandidate seeding.** ``DiscoveryCandidate``,
``DiscoveryPipeline`` and ``next_cycle_discovery`` are not imported. The only
rows this can write are the Supervisor ones, for the one scholarship named.

**No browser rendering.** ``discover_for_scholarship`` is called with no
``render_budget``, which is the same call ``run_discovery_batch`` makes and the
reason its batch path cannot render. Rendering additionally requires
``SCHOLARZONE_SUPERVISOR_RENDER_ENABLED``, which this endpoint neither reads nor
sets. Discovery and rendering stay separate switches; enabling one cannot enable
the other.

**Classification completes before persistence.** This handler does not write.
``discover_for_scholarship`` fetches, extracts, and runs every candidate through
the storage gates in ``_persist_candidates`` - role stated, name is not the role
restated, and for inline evidence the name claimed the person itself - and each
gate ``continue``s before any professor, evidence or link row exists. The commit
happens once, after the last faculty page, so a rejected candidate cannot leave a
row behind and a partial page cannot leave half a transaction visible.

**Secret handling.** ``secrets.compare_digest``, fails closed when unconfigured,
and the credential never appears in the response, the logs or an exception. The
response describes the outcome, not the input that authorised it.
"""

from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db
from ..models import Scholarship
from ..services.supervisor_discovery import discover_for_scholarship

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/supervisor", tags=["supervisor-discovery"])


def _verify_secret(provided_secret: str | None) -> bool:
    """Validate the shared verification secret.

    Constant-time, for the reason given in ``routers.verification._verify_secret``:
    this one secret gates the whole internal surface. Fails closed, so a
    deployment that has not configured it admits nobody rather than everybody.
    """
    settings = get_settings()
    expected = settings.verification_secret
    if expected is None or provided_secret is None:
        return False
    return secrets.compare_digest(provided_secret, expected)


@router.post("/discover/{scholarship_id}")
def discover_one(
    scholarship_id: int,
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
    session: Session = Depends(get_db),
) -> dict:
    """Run Supervisor discovery for exactly one scholarship and persist the result.

    Bounded by construction: one id in the path, ``MAX_PAGES_PER_SCHOLARSHIP``
    seed pages, three faculty pages, ``MAX_CANDIDATES_PER_SCHOLARSHIP`` candidates,
    one polite request at a time per host, and no rendering. Safe to re-run - every
    write is an upsert keyed on a unique constraint and the coverage row is
    recomputed rather than incremented, so a repeat cannot inflate a count.
    """
    if not _verify_secret(x_verification_secret):
        logger.warning("Unauthorized Supervisor discovery attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )

    if scholarship_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="scholarship_id must be a positive integer.",
        )

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scholarship not found.",
        )

    # No render_budget: this is the call run_discovery_batch makes, and the reason
    # the batch path cannot render. Passing one here would be the only way this
    # endpoint could launch a browser.
    outcome = discover_for_scholarship(session, scholarship)
    session.commit()

    logger.info(
        "Supervisor discovery completed for scholarship %s: status=%s "
        "professors_found=%s links_written=%s pages_fetched=%s",
        scholarship_id,
        outcome.status,
        outcome.professors_found,
        outcome.links_written,
        outcome.pages_fetched,
    )

    return {
        "scholarship_id": scholarship_id,
        "status": outcome.status,
        "detail": outcome.detail,
        "pages_fetched": outcome.pages_fetched,
        "professors_found": outcome.professors_found,
        "links_written": outcome.links_written,
    }


__all__ = ["router"]