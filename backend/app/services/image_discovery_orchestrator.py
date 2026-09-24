"""Image discovery orchestrator for Phase 9.

Drives the full pipeline for one scholarship:
  scholarship -> official domain -> official pages (Phase 9 discovery)
  -> Phase 8 ImageDiscoveryService -> ImageValidator -> semantic relevance
  -> provenance -> HIGH/MEDIUM/LOW/NO_TRUSTWORTHY_IMAGE -> safe persistence.

Safety rules:
- Existing verified images are NEVER overwritten automatically.
- Persistence is idempotent: re-running produces the same result.
- All writes are wrapped in a transaction and rolled back on error.
"""

from __future__ import annotations



from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session


class TrustworthyImageStatus(str, Enum):
    """Outcome of an orchestrated discovery run for one scholarship."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NO_TRUSTWORTHY_IMAGE = "no_trustworthy_image"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class OrchestratorImageResult:
    """A single trustworthy image candidate produced by the orchestrator."""

    image_url: str
    page_url: str
    source_type: str
    confidence: TrustworthyImageStatus
    image_kind: str | None = None
    alt_text: str | None = None
    relevance_score: float = 0.0
    provenance: dict = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    validation_status: str | None = None


@dataclass
class OrchestratorRunResult:
    """Aggregate result of an orchestrated discovery run."""

    scholarship_id: int
    scholarship_title: str
    status: TrustworthyImageStatus
    image_results: list[OrchestratorImageResult] = field(default_factory=list)
    page_discovery: object | None = None
    persisted: bool = False
    previous_image_url: str | None = None
    new_image_url: str | None = None
    error: str | None = None
    requests_made: int = 0
    dry_run: bool = False


# Keywords that indicate an image is a logo/emblem rather than a program image.
LOGO_KEYWORDS = ("logo", "emblem", "crest", "badge", "seal", "icon", "symbol")


def _is_logo_like(alt_text: str | None, image_url: str, html_context: str | None) -> bool:
    text = " ".join(filter(None, [alt_text or "", image_url, html_context or ""])).lower()
    return any(k in text for k in LOGO_KEYWORDS)


def _classify_source_type(domain: str | None, official_domain: str | None) -> str:
    """Map a domain to an ImageSourceType value."""
    from .scholarship_image_verifier import ImageSourceType

    if not domain:
        return ImageSourceType.OFFICIAL_SCHOLARSHIP.value
    if official_domain and (domain == official_domain or domain.endswith("." + official_domain)):
        return ImageSourceType.OFFICIAL_PROVIDER.value
    if domain.endswith(".edu") or domain.endswith(".ac.uk"):
        return ImageSourceType.OFFICIAL_UNIVERSITY.value
    if domain.endswith(".gov") or domain.endswith(".gouv.fr") or domain.endswith(".europa.eu"):
        return ImageSourceType.OFFICIAL_GOVERNMENT.value
    return ImageSourceType.OFFICIAL_PROVIDER.value


def _score_relevance(
    candidate_image_url: str,
    page_url: str,
    alt_text: str | None,
    html_context: str | None,
    page_candidate,
    scholarship_title: str | None,
) -> float:
    """Compute a semantic relevance score for an image in [0, 1]."""
    score = 0.0
    text = " ".join(filter(None, [alt_text or "", html_context or "", page_url, candidate_image_url])).lower()
    title_tokens = [t for t in (scholarship_title or "").lower().split() if len(t) > 2]
    if title_tokens:
        matched = sum(1 for t in title_tokens if t in text)
        score += 0.5 * (matched / len(title_tokens))

    if page_candidate is not None:
        relevance = getattr(page_candidate, "relevance_score", 0.0) or 0.0
        score += 0.3 * relevance
        if getattr(page_candidate, "is_official_domain", False):
            score += 0.1

    if _is_logo_like(alt_text, candidate_image_url, html_context):
        score -= 0.4

    return max(0.0, min(1.0, score))


def _get_current_image_url(session: "Session", scholarship_id: int) -> str | None:
    from ..models import Scholarship
    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        return None
    return scholarship.image_url

"""Image discovery orchestrator main class (appended to image_discovery_orchestrator.py)."""

from typing import TYPE_CHECKING

from .official_page_discovery import OfficialPageDiscoveryService

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session


class ImageDiscoveryOrchestrator:
    """Orchestrate official-page discovery + Phase 8 image discovery.

    Read-only by default. Pass `dry_run=True` to avoid all database writes.
    """

    def __init__(
        self,
        session_factory=None,
        page_discovery_service: OfficialPageDiscoveryService | None = None,
        dry_run: bool = True,
    ) -> None:
        self._session_factory = session_factory
        self._page_discovery_service = page_discovery_service
        self._dry_run = dry_run

    def run(
        self,
        scholarship_id: int,
        scholarship_title: str | None,
        official_source_url: str | None,
        official_source_name: str | None = None,
        session: "Session | None" = None,
    ):
        """Run orchestrated discovery for one scholarship."""
        from .image_discovery import ImageDiscoveryService
        from .image_validator import ImageValidator
        from .scholarship_image_verifier import ImageVerifier
        
        result = OrchestratorRunResult(
            scholarship_id=scholarship_id,
            scholarship_title=scholarship_title or "",
            status=TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE,
            dry_run=self._dry_run,
        )

        own_session = False
        if session is None and self._session_factory is not None:
            session = self._session_factory()
            own_session = True
        elif session is None:
            result.status = TrustworthyImageStatus.ERROR
            result.error = "no_session_and_no_session_factory"
            return result

        try:
            discovery_service = self._page_discovery_service or OfficialPageDiscoveryService()
            page_discovery = discovery_service.discover(
                scholarship_id,
                scholarship_title,
                official_source_url,
                official_source_name,
            )
            result.page_discovery = page_discovery
            result.requests_made = page_discovery.requests_made

            if page_discovery.error:
                result.status = TrustworthyImageStatus.ERROR
                result.error = page_discovery.error
                return result

            if not page_discovery.trusted_candidates:
                result.status = TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE
                return result

            image_discovery = ImageDiscoveryService()
            validator = ImageValidator()

            all_candidates = []
            for page in page_discovery.trusted_candidates:
                fetch = image_discovery.fetch_page(page.url)
                if fetch.error or not fetch.content:
                    continue
                candidates = image_discovery.extract_images_from_html(fetch.content, page.url)
                for c in candidates:
                    all_candidates.append((page, c))

            if not all_candidates:
                result.status = TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE
                return result

            validation_results = validator.validate_candidates(
                [c for _, c in all_candidates],
                scholarship_title,
                official_source_url,
            )

            scored = []
            for (page, candidate), vres in zip(all_candidates, validation_results):
                if vres is None:
                    continue
                if not getattr(vres, "is_valid_image", False):
                    continue
                relevance = _score_relevance(
                    candidate.image_url,
                    candidate.page_url,
                    candidate.alt_text,
                    candidate.html_context,
                    page,
                    scholarship_title,
                )
                scored.append((relevance, page, candidate, vres))

            scored.sort(key=lambda x: x[0], reverse=True)

            for relevance, page, candidate, vres in scored[:3]:
                image_domain = getattr(vres, "image_domain", "") or ""
                source_type = _classify_source_type(image_domain, page.source_domain)
                vstatus = getattr(vres, "status", None)
                validation_status = (
                    vstatus.value
                    if vstatus is not None and hasattr(vstatus, "value")
                    else (str(vstatus) if vstatus is not None else None)
                )
                if relevance >= 0.6 and getattr(vres, "is_official_domain", False):
                    confidence = TrustworthyImageStatus.HIGH
                elif relevance >= 0.3:
                    confidence = TrustworthyImageStatus.MEDIUM
                else:
                    confidence = TrustworthyImageStatus.LOW
                result.image_results.append(OrchestratorImageResult(
                    image_url=candidate.image_url,
                    page_url=candidate.page_url,
                    source_type=source_type,
                    confidence=confidence,
                    image_kind=getattr(vres, "image_kind", None),
                    alt_text=candidate.alt_text,
                    relevance_score=relevance,
                    provenance={
                        "discovery_method": candidate.discovery_method,
                        "page_kind": getattr(page.page_kind, "value", str(page.page_kind)),
                        "official_domain": page.source_domain,
                        "is_official_domain": page.is_official_domain,
                        "trust_score": page.trust_score,
                        "validation_status": validation_status,
                    },
                    evidence=list(candidate.evidence or []),
                    validation_status=validation_status,
                ))

            if not result.image_results:
                result.status = TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE
                return result

            best = result.image_results[0]
            result.status = best.confidence

            if not self._dry_run and result.status != TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE:
                result.previous_image_url = _get_current_image_url(session, scholarship_id)
                verifier = ImageVerifier(session)
                ok = verifier.mark_image_verified(
                    scholarship_id=scholarship_id,
                    image_url=best.image_url,
                    image_source_url=best.page_url,
                    source_type=best.source_type,
                    alt_text=best.alt_text,
                    image_kind=best.image_kind,
                    automatic=True,
                )
                result.new_image_url = best.image_url if ok else result.previous_image_url
                result.persisted = bool(ok)

            return result
        except Exception as exc:  # pragma: no cover - defensive
            result.status = TrustworthyImageStatus.ERROR
            result.error = str(exc)
            if own_session and session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass
            return result
        finally:
            if own_session and session is not None:
                try:
                    session.close()
                except Exception:
                    pass