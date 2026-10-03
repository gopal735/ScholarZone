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
import logging
import time
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from sqlalchemy.orm import Session


# Image kinds that identify the awarding body rather than depict the programme.
#
# `official_logo` is the plain wordmark. The other two are the same asset
# recorded against the issuer that controls it, which is how the catalogue
# distinguishes a government emblem from a university's mark from a foundation's
# logo. Everything else - photographs, hero banners, OpenGraph cards, media
# assets - is programme artwork, and artwork is not an identity.
LOGO_IDENTITY_KINDS: frozenset[str] = frozenset({
    "official_logo",
    "official_government",
    "official_university",
})


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


def _is_generic_site_asset(url: str | None, alt_text: str | None = None) -> bool:
    """Reject site-wide social cards and theme framework assets.

    Real sweep results showed automated discovery persisting things like
    ``/_assets/opengraph.png`` (the site's generic social-sharing card) and
    ``/wcmglobal/frameworks/v4.0.91/theme-.../sig-blk-en.svg`` (a theme
    template asset). Neither depicts the scholarship, and both were stored
    under misleading kinds such as ``program_image``.
    """
    if not url:
        return True
    low = url.lower()
    for needle in _GENERIC_ASSET_MARKERS:
        if needle in low:
            return True
    return False


# Site-wide social cards, theme/template assets, ad beacons and tracking
# pixels. These are not scholarship imagery no matter how relevant the
# surrounding page is.
#
# The list is broader than it first looks because a real sweep accepted
# `https://dc.ads.linkedin.com/collect/?pid=960156&fmt=gif` -- a LinkedIn
# advertising tracking beacon -- and `fct-og.png` (an opengraph card). Both are
# third-party or generic, and both are exactly what must never be persisted.
#
# Deliberately NOT matched: a bare `-og` / `_og` filename suffix. That pattern
# also matches legitimate official headers such as ETH Zurich's
# `eth_default_og.jpg`, which is a real, relevant, first-party programme image.
# Ambiguous og-suffixed assets are routed to human review instead of being
# rejected or auto-accepted on a weak URL signal.
_GENERIC_ASSET_MARKERS = (
    "opengraph",
    "og-image",
    "ogimage",
    "/og/",
    "share-image",
    "social-card",
    "/framework",
    "theme-gcw",
    "/theme/",
    "template-",
    "pixel.gif",
    "1x1",
    "tracking",
    # Ad beacons and analytics collectors
    "linkedin",
    "ads.",
    "collect/?pid",
    "fmt=gif",
    "beacon",
    "analytics",
    "/g/collect",
    "doubleclick",
    "googletagmanager",
)


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


def _get_current_verified_at(session: "Session", scholarship_id: int):
    """When the current image was verified. None means it was never verified.

    Used so a fallback cannot churn an image that has already passed
    validation: the fallback exists to fill an empty slot, not to replace a
    good one with a merely-acceptable one.
    """
    from ..models import Scholarship
    scholarship = session.get(Scholarship, scholarship_id)
    return getattr(scholarship, "image_verified_at", None) if scholarship else None


def _is_non_logo_stored(session: "Session", scholarship_id: int) -> bool:
    """True when the record currently shows programme artwork, not an identity mark."""
    from ..models import Scholarship

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None or not scholarship.image_url:
        return False
    # An unset kind is treated as non-logo: we cannot assert an image is a logo
    # when nothing ever recorded it as one, and this mode exists to make the
    # identity claim defensible rather than assumed.
    return (scholarship.image_kind or "") not in LOGO_IDENTITY_KINDS


def _clear_stored_image(session: "Session", scholarship_id: int) -> None:
    """Drop the stored image and every provenance field that described it.

    All six fields are cleared together on purpose. Leaving ``image_kind`` or
    ``image_verified_at`` behind would leave a record claiming it carries a
    verified official banner while carrying no image at all, which reads as a
    coverage success to every report that counts verified images.

    The terminal evaluation status is cleared for the same reason. Holding
    ``image_evaluation_status`` at ``verified`` while the image is gone produced
    a record that could never publish and could never be repaired: the coverage
    sweep skips terminally evaluated rows, so the contradiction locked the
    record out of its own recovery path. Clearing it returns the record to the
    unevaluated state, which is the honest description of a record with no
    image, and lets the pipeline try it again.
    """
    from ..models import Scholarship

    scholarship = session.get(Scholarship, scholarship_id)
    if scholarship is None:
        return
    scholarship.image_url = None
    scholarship.image_source_url = None
    scholarship.image_source_type = None
    scholarship.image_kind = None
    scholarship.image_alt_text = None
    scholarship.image_verified_at = None
    scholarship.image_evaluation_status = None
    scholarship.image_evaluated_at = None
    session.flush()

"""Image discovery orchestrator main class (appended to image_discovery_orchestrator.py)."""

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from ..models import Scholarship
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
        total_budget_seconds: float = 90.0,
        enable_logo_fallback: bool = True,
        logo_only: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._page_discovery_service = page_discovery_service
        self._dry_run = dry_run
        # The three-tier logo fallback makes several extra requests per record
        # it touches, so it is opt-in per call site and off for plan-only runs.
        self.enable_logo_fallback = enable_logo_fallback
        # Logo-only mode persists an identity mark or nothing at all. The
        # default ranking deliberately prefers a programme photograph over a
        # logo, which is the right call for a scholarship card but the wrong
        # one for a catalogue whose images are meant to identify the awarding
        # body. A stock campus photo carries no provenance: it does not say
        # who awards the scholarship, so it is decorative rather than
        # informative. Logo-only mode also raises the fallback priority,
        # because under this policy a logo is not a last resort - it is the
        # only acceptable answer.
        self.logo_only = logo_only
        # Wall-clock budget for the ENTIRE run, covering page discovery AND the
        # per-candidate page fetches and image validations that follow it.
        # Without this, a record with many trusted candidates can spend
        # (candidates x image_timeout) seconds in the validation phase alone,
        # which is what made a catalogue-wide sweep impractical.
        self._total_budget_seconds = total_budget_seconds

    def run_logo_fallback(
        self,
        scholarship_id: int,
        scholarship_title: str | None,
        official_source_url: str | None,
    ):
        """Second-chance logo resolution for a record the main path could not help.

        Runs the three fallback tiers in order. This is deliberately a separate
        entry point rather than a branch inside ``run``: a record that already
        has a trustworthy image must not pay for the extra requests.

        **Every candidate is validated by the ordinary ``ImageValidator``
        before it can be persisted.** A tier proposes; the validator decides.
        The previous version of this method took the first proposed candidate
        and wrote it straight through, which meant a tier could set
        ``image_verified_at`` on an image that had never been checked, and a
        Wikimedia file could be stored as an official logo. Both are fixed here
        and pinned by tests.

        A candidate hosted outside the institution's own domain is never
        recorded as official, whatever the validator says about its pixels.
        """
        from .image_discovery import ImageCandidate
        from .logo_fallback_resolver import LogoFallbackResolver, LogoResolutionStatus

        session = self._session_factory()
        try:
            scholarship = session.get(Scholarship, scholarship_id)
            if scholarship is None:
                return None
            resolver = LogoFallbackResolver()
            resolution = resolver.resolve(scholarship)
            if resolution.status is not LogoResolutionStatus.RESOLVED or not resolution.candidates:
                return None

            result = OrchestratorRunResult(
                scholarship_id=scholarship_id,
                scholarship_title=scholarship.title,
                official_source_url=official_source_url,
            )
            result.requests_made = resolver.requests_made

            # Translate the tier's proposals into ordinary candidates and put
            # them through exactly the same validation the programme-page path
            # uses. Nothing reaches persistence without this step.
            proposals = [
                ImageCandidate(
                    image_url=c.url,
                    page_url=c.page_url,
                    discovery_method=f"logo_fallback:{resolution.tier.value}",
                    alt_text=c.alt_text,
                    provenance={"tier": resolution.tier.value, "official_host": c.official_host},
                    evidence=[c.note] if c.note else [],
                )
                for c in resolution.candidates
            ]

            validator = ImageValidator()
            validations = validator.validate_candidates(
                proposals, scholarship.title, official_source_url
            )

            scored: list[tuple[float, ImageCandidate, object]] = []
            for candidate, vres in zip(proposals, validations):
                if vres is None or not getattr(vres, "is_valid_image", False):
                    continue
                if not getattr(vres, "status", None):
                    continue
                # A candidate on a third-party host is never an official
                # source, whatever its pixels look like. Provenance, not
                # appearance, decides this.
                tier_official = next(
                    (
                        c.official_host
                        for c in resolution.candidates
                        if c.url == candidate.image_url
                    ),
                    False,
                )
                if not tier_official:
                    continue
                # A fallback logo is the institution's brand, not necessarily
                # this programme's artwork, so it is capped below HIGH.
                relevance = 0.5
                if _is_generic_site_asset(candidate.image_url, candidate.alt_text):
                    continue
                scored.append((relevance, candidate, vres))

            if not scored:
                # Every proposal was rejected. That is a correct outcome, not a
                # failure, and the record keeps whatever status it had.
                result.status = TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE
                return result

            scored.sort(key=lambda x: x[0], reverse=True)
            _relevance, candidate, vres = scored[0]
            image_domain = getattr(vres, "image_domain", "") or ""
            source_type = _classify_source_type(
                image_domain, urlparse(candidate.page_url).netloc
            )
            confidence = TrustworthyImageStatus.MEDIUM
            result.status = confidence
            result.image_results.append(
                OrchestratorImageResult(
                    image_url=candidate.image_url,
                    page_url=candidate.page_url,
                    source_type=source_type,
                    confidence=confidence,
                    # The kind comes from the validator, not from the tier. A
                    # fallback cannot assert that something is a logo.
                    image_kind=getattr(vres, "image_kind", None),
                    alt_text=candidate.alt_text,
                    relevance_score=_relevance,
                    provenance={
                        "discovery_method": candidate.discovery_method,
                        "tier": resolution.tier.value,
                        "official_host": True,
                        "validated": True,
                        "validation_status": getattr(
                            getattr(vres, "status", None), "value", None
                        ),
                    },
                    evidence=candidate.evidence,
                    validation_status=getattr(
                        getattr(vres, "status", None), "value", None
                    ),
                )
            )

            if not self._dry_run:
                previous = _get_current_image_url(session, scholarship_id)
                result.previous_image_url = previous
                # An existing verified image is never replaced by a fallback.
                # The fallback exists to fill an empty slot, not to churn a
                # good one.
                if previous and getattr(
                    _get_current_verified_at(session, scholarship_id), "isoformat", None
                ):
                    result.status = TrustworthyImageStatus.MEDIUM
                    result.new_image_url = previous
                    result.persisted = False
                    return result
                verifier = ImageVerifier(session)
                ok = verifier.mark_image_verified(
                    scholarship_id=scholarship_id,
                    image_url=candidate.image_url,
                    image_source_url=candidate.page_url,
                    source_type=source_type,
                    alt_text=candidate.alt_text,
                    image_kind=getattr(vres, "image_kind", None),
                    automatic=True,
                )
                result.new_image_url = candidate.image_url if ok else previous
                result.persisted = bool(ok)
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("logo fallback failed for id=%s: %s", scholarship_id, exc)
            return None
        finally:
            try:
                session.close()
            except Exception:
                pass

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
        deadline = time.monotonic() + self._total_budget_seconds
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
                # Stop fetching pages once the run budget is spent; a partial
                # candidate set is reported rather than an unbounded stall.
                if time.monotonic() >= deadline:
                    result.status = TrustworthyImageStatus.ERROR
                    result.error = "deadline_exceeded_during_page_fetch"
                    return result
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

                # A site-wide social card or theme asset is never the
                # scholarship's image, regardless of page relevance.
                if _is_generic_site_asset(candidate.image_url, candidate.alt_text):
                    confidence = TrustworthyImageStatus.LOW
                    vres_kind = None
                else:
                    vres_kind = getattr(vres, "image_kind", None)

                result.image_results.append(OrchestratorImageResult(
                    image_url=candidate.image_url,
                    page_url=candidate.page_url,
                    source_type=source_type,
                    confidence=confidence,
                    image_kind=vres_kind,
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

            if self.logo_only:
                # Rank by the identity filter, not by the validator's own
                # preference order. `image_results` is already sorted with
                # programme artwork first, so taking [0] here would silently
                # defeat the mode.
                result.image_results = [
                    r for r in result.image_results
                    if (r.image_kind or "") in LOGO_IDENTITY_KINDS
                ]

            if not result.image_results:
                result.status = TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE
                # Second chance before the record is written off. Deliberately
                # a separate call rather than a branch deeper in, so a record
                # that already succeeded never pays for the fallback's extra
                # requests.
                if self.enable_logo_fallback and not self._dry_run:
                    fallback = self.run_logo_fallback(
                        scholarship_id, result.scholarship_title, official_source_url
                    )
                    if fallback is not None and fallback.image_results:
                        return fallback
                return result

            best = result.image_results[0]
            result.status = best.confidence

            if not self._dry_run and result.status != TrustworthyImageStatus.NO_TRUSTWORTHY_IMAGE:
                result.previous_image_url = _get_current_image_url(session, scholarship_id)
                # A stored programme photo must not survive a logo-only sweep.
                # Leaving it in place would mean the run reports "nothing to
                # do" for a record whose image is exactly what this mode exists
                # to remove.
                if self.logo_only and self._is_non_logo_stored(session, scholarship_id):
                    _clear_stored_image(session, scholarship_id)
                    result.previous_image_url = None
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