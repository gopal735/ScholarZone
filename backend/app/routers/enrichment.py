"""Internal enrichment + image-coverage endpoints.

Secured by the same shared verification secret used by the verification and
discovery internal routers. These endpoints mutate the catalogue, so they are
never exposed publicly.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_db, get_session_factory
from ..models import Scholarship
from ..services.enrichment_runner import EnrichmentBatchRunner
from ..services.image_coverage_runner import ImageCoverageRunner
from ..services.scholarship_enrichment import ScholarshipEnrichmentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/enrich", tags=["internal-enrichment"])


def _verify_secret(x_verification_secret: str | None) -> None:
    expected = (get_settings().verification_secret or "").strip()
    if not expected or x_verification_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing verification secret.",
        )


def _parse_ids(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    out: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"invalid scholarship id: {chunk!r}",
            ) from exc
    return out or None


@router.post("/trigger")
def trigger_enrichment(
    dry_run: bool = Query(default=True, description="Report decisions without writing"),
    batch_size: int = Query(default=15, ge=1, le=50),
    limit: int | None = Query(default=None, ge=1, le=5000),
    start_after: int | None = Query(default=None, ge=0),
    ids: str | None = Query(default=None, description="Comma-separated scholarship ids"),
    only_missing_source: bool = Query(default=False),
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
) -> dict[str, Any]:
    """Enrich existing scholarships from their strongest official source."""
    _verify_secret(x_verification_secret)

    runner = EnrichmentBatchRunner(
        get_session_factory(),
        dry_run=dry_run,
        batch_size=batch_size,
    )
    report = runner.run(
        ids=_parse_ids(ids),
        limit=limit,
        start_after=start_after,
        only_missing_source=only_missing_source,
    )
    payload = report.as_dict()
    payload["operation"] = "enrichment"
    return payload


@router.post("/images")
def trigger_image_coverage(
    dry_run: bool = Query(default=True),
    batch_size: int = Query(default=10, ge=1, le=40),
    limit: int | None = Query(default=None, ge=1, le=5000),
    start_after: int | None = Query(default=None, ge=0),
    ids: str | None = Query(default=None),
    x_verification_secret: str | None = Header(None, alias="X-Verification-Secret"),
) -> dict[str, Any]:
    """Run official image discovery for scholarships without a verified image."""
    _verify_secret(x_verification_secret)

    runner = ImageCoverageRunner(
        get_session_factory(),
        dry_run=dry_run,
        batch_size=batch_size,
    )
    metrics = runner.run(ids=_parse_ids(ids), limit=limit, start_after=start_after)
    payload = metrics.as_dict()
    payload["operation"] = "image_coverage"
    payload["dry_run"] = dry_run
    return payload


@router.get("/status")
def enrichment_status(
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    """Catalogue-level completeness snapshot. Read-only, no secret required."""
    total = session.scalar(select(func.count()).select_from(Scholarship)) or 0
    verified_images = (
        session.scalar(
            select(func.count())
            .select_from(Scholarship)
            .where(Scholarship.image_verified_at.is_not(None))
        )
        or 0
    )
    with_source = (
        session.scalar(
            select(func.count())
            .select_from(Scholarship)
            .where(Scholarship.official_source_url.is_not(None))
        )
        or 0
    )
    return {
        "total_scholarships": total,
        "with_official_source_url": with_source,
        "with_verified_image": verified_images,
        "image_coverage_pct": round(100 * verified_images / total, 2) if total else 0.0,
    }
