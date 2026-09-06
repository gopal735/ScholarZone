"""Image verification and audit tracking for scholarship images.

Provides:
- Source type validation (controlled vocabulary)
- Image URL change detection against official domains
- Verification metadata management
- Stale image detection and safe revalidation
- Integration with ScholarshipVerificationHistory for audit trail
- Integration with ScholarshipReview for human-review routing
"""

from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Scholarship, ScholarshipVerificationHistory, ScholarshipReview
from .scholarship_review import get_pending_review, create_review


class ImageSourceType(str, Enum):
    OFFICIAL_SCHOLARSHIP = "official_scholarship"
    OFFICIAL_UNIVERSITY = "official_university"
    OFFICIAL_GOVERNMENT = "official_government"
    OFFICIAL_PROVIDER = "official_provider"


_VALID_SOURCE_TYPES = frozenset(member.value for member in ImageSourceType)


class StaleImageStatus(str, Enum):
    """Outcome of a stored-image staleness check."""
    CURRENT = "current"
    CHANGED = "changed"
    REMOVED = "removed"
    SOURCE_INACCESSIBLE = "source_inaccessible"
    HUMAN_REVIEW = "human_review"


@dataclass
class StaleImageResult:
    """Result of a stale-image revalidation for a single scholarship."""
    scholarship_id: int
    status: StaleImageStatus
    image_url: str | None
    official_source_url: str | None
    found_image_urls: list[str]
    evidence: str
    action_taken: str


def _normalize_url(url: str) -> str:
    """Normalize a URL for reliable equality comparison."""
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/")
    return f"{scheme}://{netloc}{path}"


def _is_image_present(stored_url: str, found_urls: list[str]) -> bool:
    """Return True if the stored image URL is present among discovered candidates."""
    stored_norm = _normalize_url(stored_url)
    for found in found_urls:
        if _normalize_url(found) == stored_norm:
            return True
    return False


def is_valid_source_type(value: str | None) -> bool:
    if value is None:
        return False
    return value in _VALID_SOURCE_TYPES


def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower() if parsed.netloc else None


_KNOWN_OFFICIAL_DOMAINS = frozenset({
    "daad.de",
    "www.daad.de",
    "erasmus-plus.ec.europa.eu",
    "a2ascholarships.iccr.gov.in",
    "studyinkorea.go.kr",
    "www.studyinkorea.go.kr",
    "studyinjapan.go.jp",
    "www.studyinjapan.go.jp",
    "campusfrance.org",
    "www.campusfrance.org",
    "fulbrightonline.org",
    "educationusa.state.gov",
    "aefe.gouv.fr",
    "www.aefe.gouv.fr",
    "gouv.fr",
    "www.gouv.fr",
    "australiaawards.com.au",
    "nuffic.nl",
    "si.se",
    "esteri.it",
})

_KNOWN_OFFICIAL_HOST_SUFFIXES = (
    ".europa.eu",
    ".iccr.gov.in",
    ".studyinkorea.go.kr",
    ".studyinjapan.go.jp",
    ".esteri.it",
)


def is_official_domain(domain: str | None) -> bool:
    """Check whether a domain belongs to an official government/university/edu source."""
    if not domain:
        return False
    domain = domain.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    if domain in _KNOWN_OFFICIAL_DOMAINS:
        return True
    official_suffixes = (
        ".gov", ".edu", ".ac.uk", ".ac.in", ".ac.jp", ".ac.kr", ".ac.cn",
        ".go.kr", ".go.jp", ".gov.in", ".gov.cn", ".gov.uk", ".gov.au",
        ".org", ".int", ".admin.ch", ".ch", ".de",
    )
    for suffix in official_suffixes:
        if domain == suffix[1:] or domain.endswith(suffix):
            return True
    if domain == "ec.europa.eu" or domain.endswith(".europa.eu"):
        return True
    if domain in _KNOWN_OFFICIAL_DOMAINS:
        return True
    if domain.endswith(".gouv.fr"):
        return domain in _KNOWN_OFFICIAL_DOMAINS
    for suffix in _KNOWN_OFFICIAL_HOST_SUFFIXES:
        if domain.endswith(suffix):
            return True
    return False


class ImageVerifier:
    """Tracks and validates official image sources for scholarships."""

    def __init__(self, session: Session):
        self.session = session

    def mark_image_verified(
        self,
        scholarship_id: int,
        image_url: str,
        image_source_url: str,
        source_type: str,
        alt_text: str | None = None,
        image_kind: str | None = None,
    ) -> bool:
        """Record an image as verified, tracking changes via the audit history.

        Returns True if the image was updated, False if unchanged or rejected.
        """
        if not is_valid_source_type(source_type):
            return False

        scholarship = self.session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return False

        old_image_url = scholarship.image_url
        old_source_url = scholarship.image_source_url
        old_source_type = scholarship.image_source_type
        old_image_kind = scholarship.image_kind

        if image_url == old_image_url and image_source_url == old_source_url:
            if alt_text and alt_text != scholarship.image_alt_text:
                old_alt = scholarship.image_alt_text
                scholarship.image_alt_text = alt_text
                self._record_audit(
                    scholarship_id,
                    "image_alt_text",
                    old_alt,
                    alt_text,
                    image_source_url,
                    "modified",
                )
            if image_kind and image_kind != old_image_kind:
                old_kind = scholarship.image_kind
                scholarship.image_kind = image_kind
                self._record_audit(
                    scholarship_id,
                    "image_kind",
                    old_kind,
                    image_kind,
                    image_source_url,
                    "modified",
                )
            scholarship.image_verified_at = datetime.now(timezone.utc)
            return False

        if old_image_url is not None and old_image_url != image_url:
            self._record_audit(
                scholarship_id,
                "image_url",
                old_image_url,
                image_url,
                old_source_url,
                "modified",
            )

        if old_image_url is None and image_url is not None:
            self._record_audit(
                scholarship_id,
                "image_url",
                None,
                image_url,
                old_source_url,
                "verified",
            )

        scholarship.image_url = image_url
        scholarship.image_source_url = image_source_url
        scholarship.image_source_type = source_type
        scholarship.image_kind = image_kind
        scholarship.image_verified_at = datetime.now(timezone.utc)
        if alt_text:
            scholarship.image_alt_text = alt_text

        self.session.commit()
        self.session.refresh(scholarship)
        return True

    def clear_image(self, scholarship_id: int) -> bool:
        """Remove image metadata, marking for review if one existed."""
        scholarship = self.session.get(Scholarship, scholarship_id)
        if scholarship is None or scholarship.image_url is None:
            return False

        old_image_url = scholarship.image_url
        old_source_url = scholarship.image_source_url
        old_image_kind = scholarship.image_kind

        self._record_audit(
            scholarship_id,
            "image_url",
            old_image_url,
            None,
            old_source_url,
            "removed",
        )
        if old_image_kind:
            self._record_audit(
                scholarship_id,
                "image_kind",
                old_image_kind,
                None,
                old_source_url,
                "removed",
            )

        scholarship.image_url = None
        scholarship.image_source_url = None
        scholarship.image_source_type = None
        scholarship.image_kind = None
        scholarship.image_verified_at = None
        scholarship.image_alt_text = None

        self.session.commit()
        return True

    def needs_review(self, scholarship_id: int) -> bool:
        """Check if a scholarship's image source needs review (changed or broken)."""
        scholarship = self.session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return False

        if scholarship.image_url and scholarship.image_source_url:
            image_domain = extract_domain(scholarship.image_url)
            source_domain = extract_domain(scholarship.image_source_url)
            if image_domain and source_domain and image_domain != source_domain:
                if not is_official_domain(image_domain):
                    return True
        return False

    def _record_audit(
        self,
        scholarship_id: int,
        field_name: str,
        old_value: str | None,
        new_value: str | None,
        source_url: str | None,
        change_type: str,
    ) -> None:
        record = ScholarshipVerificationHistory(
            scholarship_id=scholarship_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            source_url=source_url,
            evidence_text=None,
            confidence="high" if change_type == "verified" else "medium",
            verification_status="active",
        )
        self.session.add(record)

    def get_image_stats(self) -> dict[str, int]:
        """Return aggregate image coverage statistics."""
        total = self.session.scalar(select(func.count()).select_from(Scholarship)) or 0
        with_image = self.session.scalar(
            select(func.count()).where(Scholarship.image_url.is_not(None))
        ) or 0
        verified = self.session.scalar(
            select(func.count()).where(Scholarship.image_verified_at.is_not(None))
        ) or 0
        return {
            "total_scholarships": total,
            "with_image": with_image,
            "image_verified": verified,
            "without_image": total - with_image,
        }

    def check_stale_image(self, scholarship: Scholarship) -> StaleImageResult:
        """Check whether a persisted image is still current on the official page.

        Returns a StaleImageResult without mutating the database.
        """
        from .image_discovery import ImageDiscoveryService

        image_url = scholarship.image_url
        official_source_url = scholarship.official_source_url

        if not image_url or not official_source_url:
            return StaleImageResult(
                scholarship_id=scholarship.id,
                status=StaleImageStatus.HUMAN_REVIEW,
                image_url=image_url,
                official_source_url=official_source_url,
                found_image_urls=[],
                evidence="Missing image_url or official_source_url",
                action_taken="none",
            )

        discovery = ImageDiscoveryService()
        page_result = discovery.fetch_page(official_source_url)

        if page_result.error or page_result.status_code != 200:
            return StaleImageResult(
                scholarship_id=scholarship.id,
                status=StaleImageStatus.SOURCE_INACCESSIBLE,
                image_url=image_url,
                official_source_url=official_source_url,
                found_image_urls=[],
                evidence=f"Source fetch failed: {page_result.error or f'HTTP {page_result.status_code}'}",
                action_taken="none",
            )

        candidates = discovery.extract_images_from_html(
            page_result.content or "", page_result.url
        )
        found_urls = [c.image_url for c in candidates]

        if _is_image_present(image_url, found_urls):
            return StaleImageResult(
                scholarship_id=scholarship.id,
                status=StaleImageStatus.CURRENT,
                image_url=image_url,
                official_source_url=official_source_url,
                found_image_urls=found_urls,
                evidence="Stored image found on current official page",
                action_taken="none",
            )

        replacement = None
        for candidate in candidates:
            candidate_domain = urlparse(candidate.image_url).netloc.lower()
            stored_domain = urlparse(image_url).netloc.lower()
            if candidate_domain == stored_domain:
                replacement = candidate.image_url
                break

        if replacement:
            return StaleImageResult(
                scholarship_id=scholarship.id,
                status=StaleImageStatus.CHANGED,
                image_url=image_url,
                official_source_url=official_source_url,
                found_image_urls=found_urls,
                evidence=f"Stored image removed; replacement from same domain found: {replacement}",
                action_taken="none",
            )

        return StaleImageResult(
            scholarship_id=scholarship.id,
            status=StaleImageStatus.REMOVED,
            image_url=image_url,
            official_source_url=official_source_url,
            found_image_urls=found_urls,
            evidence="Stored image not present on current official page and no same-domain replacement found",
            action_taken="none",
        )

    def revalidate_stored_image(self, scholarship_id: int) -> StaleImageResult:
        """Revalidate a stored image against the current official page and take safe action.

        Safe actions:
        - CURRENT: update image_verified_at, write lightweight audit record
        - CHANGED / REMOVED / SOURCE_INACCESSIBLE / HUMAN_REVIEW:
            create a pending ScholarshipReview if one does not already exist,
            write an audit record, and leave image data untouched.

        Idempotency guarantees:
        - Re-running on CURRENT updates the timestamp harmlessly.
        - Re-running on a non-CURRENT status does not create duplicate reviews
          or duplicate stale-detection audit records within 12 hours.
        """
        scholarship = self.session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return StaleImageResult(
                scholarship_id=scholarship_id,
                status=StaleImageStatus.HUMAN_REVIEW,
                image_url=None,
                official_source_url=None,
                found_image_urls=[],
                evidence="Scholarship not found",
                action_taken="none",
            )

        result = self.check_stale_image(scholarship)
        now = datetime.now(timezone.utc)

        if result.status == StaleImageStatus.CURRENT:
            scholarship.image_verified_at = now
            self.session.commit()
            result.action_taken = "timestamp_updated"
            return result

        existing_review = get_pending_review(self.session, scholarship_id, "image_url")
        if existing_review is not None:
            result.action_taken = "review_already_exists"
            return result

        recent_stale = self.session.execute(
            select(ScholarshipVerificationHistory)
            .where(ScholarshipVerificationHistory.scholarship_id == scholarship_id)
            .where(ScholarshipVerificationHistory.field_name == "image_url")
            .where(ScholarshipVerificationHistory.change_type == "stale_detected")
            .order_by(ScholarshipVerificationHistory.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if recent_stale and (now - recent_stale.created_at).total_seconds() < 43200:
            result.action_taken = "recent_stale_record_exists"
            return result

        conflict_reason = f"stale_image_{result.status.value}"
        create_review(
            session=self.session,
            scholarship_id=scholarship_id,
            field_name="image_url",
            current_value=scholarship.image_url,
            proposed_value=None,
            conflict_reason=conflict_reason,
            verification_state="needs_review",
            source_urls=[scholarship.official_source_url] if scholarship.official_source_url else [],
            evidence_text=result.evidence,
        )

        self._record_audit(
            scholarship_id,
            "image_url",
            scholarship.image_url,
            scholarship.image_url,
            scholarship.official_source_url,
            "stale_detected",
        )
        self.session.commit()
        result.action_taken = "review_created"
        return result
