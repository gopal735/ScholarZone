"""Official-source verification and repair for existing Scholarship records.

The catalogue stores an ``official_source_url`` per record. Over time those URLs
rot: pages move, sites reorganise, and links quietly 404. A dead source URL
silently disables enrichment, verification, and image discovery for that
record, so repairing sources is a first-class maintenance job rather than an
incidental one.

Quality classification (deliberately strict):

    AUTHORITATIVE               live, content matches, URL unchanged
    REDIRECTED_TO_AUTHORITATIVE  live, moved, new URL recorded
    REPAIRED_AUTHORITATIVE      was dead, current official page located
    UNAVAILABLE                could not be probed (blocked/timeout/DNS)
    UNRESOLVED                  probed as dead, no official replacement found

Two rules keep repairs honest:

* An aggregator is never a valid repair target. The replacement must classify
  as an authoritative source.
* Transient failures (403, timeout, connection reset) are reported as
  UNAVAILABLE, never "repaired". Rewriting a URL because a site rate-limited us
  would destroy a perfectly good source.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship, ScholarshipVerificationHistory
from .discovery_scheduler import DomainRateLimiter
from .scholarship_evidence import classify_source, is_authoritative_source
from .source_resolver import SourceResolverService

logger = logging.getLogger(__name__)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

PROBE_TIMEOUT_SECONDS = 20.0
# Status codes that mean "this page is gone", not "we could not look".
DEAD_STATUS_CODES = frozenset({404, 410})
# Status codes that mean "try again later"; never a repair trigger.
TRANSIENT_STATUS_CODES = frozenset({403, 429, 500, 502, 503, 504, 408})

MIN_REPAIR_CONFIDENCE = 0.35
# A repair replaces the source of record, so it must carry real evidence that
# the new page is about the same scholarship.
#
# Dry-run evidence for the thresholds below: a looser rule produced repairs to
# a generic "Dutch education / studies" page (0% overlap), an "admissions
# glossary", a university homepage about architecture, and a URL carrying a
# per-request JS session id. Every one of those silently degrades the source of
# record, which is worse than honestly recording a dead URL.
#
# Therefore: dead-URL repair demands a programme-specific path AND strong title
# overlap. Anything weaker is reported UNRESOLVED for human review.
MIN_REPAIR_TITLE_OVERLAP = 0.5

# Path segments that indicate a generic or non-programme page.
_GENERIC_PATH_MARKERS = (
    "/splash", "/index", "/home", "/studies", "/programs", "/programmes",
    "/education", "/search", "/find", "/menu", "/dashboard", "/glossary",
    "/about", "/contact", "/privacy", "/terms", "/sitemap", "/faq",
    "/admissions-glossary", "/login", "/register",
)

# The candidate path must look like a programme page, not an index page.
_PROGRAMME_PATH_KEYWORDS = (
    "scholarship", "fellowship", "grant", "bursar", "stipend", "award",
    "funding", "financial-aid", "financial_aid", "tuition", "programme",
    "program", "opportunity", "exchange", "mees", "beurs",
)

# Session-scoped URL noise that must never be persisted as a source of record.
_URL_NOISE_RE = re.compile(
    r"(?:^|;)(?:jsessionid|phpsessid|sessionid|sid|cid)=[^;]*", re.IGNORECASE
)

_TITLE_TOKEN_RE = re.compile(r"[a-z0-9]+")


class SourceQuality(str, Enum):
    AUTHORITATIVE = "authoritative"
    REDIRECTED_TO_AUTHORITATIVE = "redirected_to_authoritative"
    REPAIRED_AUTHORITATIVE = "repaired_authoritative"
    UNAVAILABLE = "unavailable"
    UNRESOLVED = "unresolved"


@dataclass
class RepairResult:
    scholarship_id: int
    quality: SourceQuality
    original_url: str | None = None
    current_url: str | None = None
    new_url: str | None = None
    status_code: int | None = None
    reason: str = ""
    evidence: str = ""
    title_overlap: float = 0.0
    attempts: int = 0
    retryable: bool = False
    error: str | None = None
    dry_run: bool = True

    @property
    def changed_url(self) -> bool:
        return bool(self.new_url) and self.new_url != self.original_url

    @property
    def repaired(self) -> bool:
        return self.quality in (
            SourceQuality.REDIRECTED_TO_AUTHORITATIVE,
            SourceQuality.REPAIRED_AUTHORITATIVE,
        )


def _normalize_for_compare(url: str) -> str:
    """Compare URLs ignoring scheme, trailing slash, and common tracking noise."""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return url.strip().lower()
    host = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    if path.endswith("/index.html") or path.endswith("/index.htm"):
        path = path.rsplit("/", 1)[0]
    return f"{host}{path}".lower()


def _registrable(host: str) -> str:
    parts = host.lower().removeprefix("www.").split(".")
    if len(parts) <= 2:
        return ".".join(parts)
    tail2 = ".".join(parts[-2:])
    multi = {
        "com.sg", "com.au", "com.br", "co.uk", "org.uk", "ac.uk", "gov.uk",
        "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp", "co.kr", "co.nz",
        "govt.nz", "co.za", "org.za", "ac.za", "co.in", "gov.in", "com.cn",
        "gov.cn", "edu.cn", "co.il", "co.hu", "gov.hu", "com.pl", "com.es",
        "gob.es", "com.pt", "com.ua", "com.tr", "co.th", "ac.th",
    }
    return ".".join(parts[-3:]) if tail2 in multi else tail2


def _title_overlap(title: str | None, candidate_title: str | None) -> float:
    """Fraction of meaningful title tokens present in the candidate page."""
    if not title or not candidate_title:
        return 0.0
    source = {t for t in _TITLE_TOKEN_RE.findall(title.lower()) if len(t) > 3}
    if not source:
        return 0.0
    target = candidate_title.lower()
    hits = sum(1 for t in source if t in target)
    return hits / len(source)


def _sanitize_source_url(url: str) -> str:
    """Strip session-scoped noise so a redirect target can be stored safely.

    A dry run captured ``...;jsessionid=0qoNSXxuUKvijnUbfLeMhH6tDkGtLuIVyFe7Zyoc``
    as a "repaired" source. That URL is unique per request and worthless later,
    so it must never reach the database. Fragments and tracking parameters are
    dropped for the same reason.
    """
    if not url:
        return url
    cleaned = _URL_NOISE_RE.sub("", url)
    cleaned = cleaned.rstrip(";?&")
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return cleaned
    if parsed.query:
        # Drop tracking params but keep anything that looks structural.
        kept = []
        for pair in parsed.query.split("&"):
            if not pair:
                continue
            key = pair.split("=", 1)[0].lower()
            if key in {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}:
                continue
            kept.append(pair)
        cleaned = parsed._replace(query="&".join(kept)).geturl()
    return cleaned.split("#", 1)[0]


class SourceRepairService:
    """Verify and repair the official source URL of a single scholarship."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        dry_run: bool = True,
        rate_limiter: DomainRateLimiter | None = None,
        resolver: SourceResolverService | None = None,
        timeout: float = PROBE_TIMEOUT_SECONDS,
        max_attempts: int = 2,
        now_fn=None,
    ) -> None:
        self._session_factory = session_factory
        self.dry_run = dry_run
        self.rate_limiter = rate_limiter or DomainRateLimiter(min_interval_seconds=1.0)
        self.resolver = resolver or SourceResolverService(timeout=timeout)
        self.timeout = timeout
        self.max_attempts = max(1, max_attempts)
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    # -- probing ----------------------------------------------------------

    def _probe(self, url: str) -> tuple[int | None, str | None, str | None, str | None]:
        """Fetch a URL, honouring the rate limiter.

        Returns ``(status_code, final_url, error_type, error_message)``.
        """
        domain = urlparse(url).netloc
        if domain:
            self.rate_limiter.wait_if_needed(domain)
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": BROWSER_UA, "Accept": "text/html,application/xhtml+xml"},
                timeout=self.timeout,
                follow_redirects=True,
            )
        except httpx.TimeoutException as exc:
            return None, None, "timeout", str(exc)
        except httpx.HTTPError as exc:
            return None, None, "connection_error", str(exc)
        except Exception as exc:  # noqa: BLE001 - never abort a batch
            return None, None, "unexpected", str(exc)

        final_url = str(getattr(response, "url", url) or url)
        if response.status_code != 200:
            return response.status_code, final_url, f"http_{response.status_code}", f"HTTP {response.status_code}"
        return response.status_code, final_url, None, None

    def _page_title(self, url: str) -> str | None:
        domain = urlparse(url).netloc
        if domain:
            self.rate_limiter.wait_if_needed(domain)
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": BROWSER_UA},
                timeout=self.timeout,
                follow_redirects=True,
            )
        except Exception:  # noqa: BLE001
            return None
        if response.status_code != 200:
            return None
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text[:200_000], "html.parser")
            if soup.title and soup.title.string:
                return str(soup.title.string).strip()
            h1 = soup.find("h1")
            if h1:
                return h1.get_text(" ", strip=True)[:300]
        except Exception:  # noqa: BLE001
            return None
        return None

    # -- repair candidates -------------------------------------------------

    def _find_replacement(self, dead_url: str, title: str | None) -> tuple[str | None, str, float]:
        """Locate a current official page for a dead URL.

        Restricted to the same registrable domain so a repair can never migrate
        a record onto a different organisation, and validated as authoritative
        so an aggregator can never become the source of record.
        """
        parsed = urlparse(dead_url)
        original_domain = _registrable(parsed.netloc)
        root = f"{parsed.scheme or 'https'}://{parsed.netloc}/"

        try:
            resolved = self.resolver.resolve_source(root, title)
        except Exception as exc:  # noqa: BLE001
            return None, f"resolver failed: {type(exc).__name__}", 0.0

        best_url: str | None = None
        best_reason = "no candidate returned"
        best_overlap = 0.0

        candidates: list[str] = []
        if resolved.resolved_url:
            candidates.append(resolved.resolved_url)
        for alt_url, _score in (resolved.alternatives or [])[:8]:
            if alt_url:
                candidates.append(alt_url)

        for candidate in candidates:
            if _registrable(urlparse(candidate).netloc) != original_domain:
                continue
            source_type = classify_source(candidate)
            if not is_authoritative_source(source_type):
                continue

            path = urlparse(candidate).path.lower()
            # A generic or non-programme page is never a valid repair target.
            if any(marker in path for marker in _GENERIC_PATH_MARKERS):
                continue
            if not any(keyword in path for keyword in _PROGRAMME_PATH_KEYWORDS):
                continue

            page_title = resolved.page_title or resolved.page_h1
            overlap = _title_overlap(title, page_title)
            if overlap < MIN_REPAIR_TITLE_OVERLAP:
                continue
            if best_url is None or overlap > best_overlap:
                best_url = candidate
                best_overlap = overlap
                best_reason = (
                    f"same-domain programme page matched ({overlap:.0%} title overlap, "
                    f"source_type={source_type.value})"
                )

        if best_url is None:
            best_reason = (
                f"no authoritative same-domain programme page for '{dead_url}' with "
                f"sufficient title overlap (>= {MIN_REPAIR_TITLE_OVERLAP:.0%}); "
                "left unchanged for human review"
            )
        return best_url, best_reason, best_overlap

    # -- main entry point --------------------------------------------------

    def repair_one(self, scholarship_id: int) -> RepairResult:
        session = self._session_factory()
        try:
            result = self._repair_in_session(session, scholarship_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception("source repair failed for id=%s", scholarship_id)
            result = RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.UNRESOLVED,
                error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            session.close()
        result.dry_run = self.dry_run
        return result

    def _repair_in_session(self, session: Session, scholarship_id: int) -> RepairResult:
        scholarship = session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.UNRESOLVED,
                error="scholarship not found",
            )

        original = (scholarship.official_source_url or "").strip()
        if not original:
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.UNRESOLVED,
                reason="record has no official_source_url to verify",
            )

        if not is_authoritative_source(classify_source(original)):
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.UNRESOLVED,
                original_url=original,
                current_url=original,
                reason="stored source is not an authoritative source; not repaired automatically",
            )

        status, final_url, error_type, error_msg = None, None, None, None
        attempts = 0
        for attempt in range(self.max_attempts):
            attempts += 1
            status, final_url, error_type, error_msg = self._probe(original)
            if status == 200 or (status and status not in DEAD_STATUS_CODES and status not in TRANSIENT_STATUS_CODES):
                break
            if status in DEAD_STATUS_CODES:
                break
            if attempt < self.max_attempts - 1:
                time.sleep(1.0)

        # --- Live and unchanged -------------------------------------------
        if status == 200 and final_url and _normalize_for_compare(final_url) == _normalize_for_compare(original):
            self._record_evidence(
                session, scholarship_id, "official_source_url", original, original,
                "verified", original, "official source reachable and unchanged",
                "high", "active",
            )
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.AUTHORITATIVE,
                original_url=original,
                current_url=original,
                status_code=status,
                reason="official source reachable and unchanged",
                attempts=attempts,
            )

        # --- Live but moved ------------------------------------------------
        if status == 200 and final_url:
            new_url = _sanitize_source_url(final_url)
            if _normalize_for_compare(new_url) == _normalize_for_compare(original):
                # Sanitising removed the only difference; nothing to record.
                return RepairResult(
                    scholarship_id=scholarship_id,
                    quality=SourceQuality.AUTHORITATIVE,
                    original_url=original,
                    current_url=original,
                    status_code=status,
                    reason="official source reachable; redirect target equivalent to stored URL",
                    attempts=attempts,
                )
            if not is_authoritative_source(classify_source(new_url)):
                return RepairResult(
                    scholarship_id=scholarship_id,
                    quality=SourceQuality.UNRESOLVED,
                    original_url=original,
                    current_url=new_url,
                    status_code=status,
                    reason="redirect left the authoritative domain set; not applied",
                    attempts=attempts,
                )
            self._apply(session, scholarship, "official_source_url", new_url)
            self._record_evidence(
                session, scholarship_id, "official_source_url", original, new_url,
                "redirected", new_url, f"official source redirected (HTTP {status})",
                "high", "active",
            )
            if not self.dry_run:
                session.commit()
            else:
                session.rollback()
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.REDIRECTED_TO_AUTHORITATIVE,
                original_url=original,
                current_url=original,
                new_url=new_url,
                status_code=status,
                reason=f"official source redirected (HTTP {status})",
                evidence=f"{original} -> {new_url}",
                attempts=attempts,
            )

        # --- Transient failure: never a repair trigger ---------------------
        if status in TRANSIENT_STATUS_CODES or error_type in ("timeout", "connection_error", "unexpected"):
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.UNAVAILABLE,
                original_url=original,
                current_url=original,
                status_code=status,
                reason=f"source could not be probed: {error_type or status}",
                error=error_msg,
                retryable=True,
                attempts=attempts,
            )

        # --- Dead: attempt repair ------------------------------------------
        if status in DEAD_STATUS_CODES or error_type == "http_404":
            new_url, reason, overlap = self._find_replacement(original, scholarship.title)
            if not new_url:
                return RepairResult(
                    scholarship_id=scholarship_id,
                    quality=SourceQuality.UNRESOLVED,
                    original_url=original,
                    current_url=original,
                    status_code=status,
                    reason=reason,
                    title_overlap=overlap,
                    attempts=attempts,
                )

            new_url = _sanitize_source_url(new_url)
            page_title = self._page_title(new_url)
            live_status, _final, _err, _msg = self._probe(new_url)
            if live_status != 200:
                return RepairResult(
                    scholarship_id=scholarship_id,
                    quality=SourceQuality.UNRESOLVED,
                    original_url=original,
                    current_url=original,
                    new_url=new_url,
                    reason=f"replacement candidate did not return HTTP 200 (got {live_status})",
                    title_overlap=overlap,
                    attempts=attempts,
                )

            self._apply(session, scholarship, "official_source_url", new_url)
            self._record_evidence(
                session, scholarship_id, "official_source_url", original, new_url,
                "repaired", new_url,
                f"{reason}; page title: {page_title!r}",
                "high", "active",
            )
            if not self.dry_run:
                session.commit()
            else:
                session.rollback()
            return RepairResult(
                scholarship_id=scholarship_id,
                quality=SourceQuality.REPAIRED_AUTHORITATIVE,
                original_url=original,
                current_url=original,
                new_url=new_url,
                status_code=status,
                reason=reason,
                evidence=f"{original} -> {new_url} (title={page_title!r})",
                title_overlap=overlap,
                attempts=attempts,
            )

        return RepairResult(
            scholarship_id=scholarship_id,
            quality=SourceQuality.UNAVAILABLE,
            original_url=original,
            current_url=original,
            status_code=status,
            reason=f"unhandled probe outcome: {error_type or status}",
            error=error_msg,
            retryable=True,
            attempts=attempts,
        )

    # -- persistence -------------------------------------------------------

    @staticmethod
    def _apply(session: Session, scholarship: Scholarship, field_name: str, value: str) -> None:
        setattr(scholarship, field_name, value)

    def _record_evidence(
        self,
        session: Session,
        scholarship_id: int,
        field_name: str,
        old_value: str | None,
        new_value: str | None,
        change_type: str,
        source_url: str | None,
        evidence_text: str,
        confidence: str,
        verification_status: str,
    ) -> None:
        entry = ScholarshipVerificationHistory(
            scholarship_id=scholarship_id,
            field_name=field_name,
            old_value=old_value,
            new_value=new_value,
            change_type=change_type,
            source_url=source_url,
            evidence_text=evidence_text[:4000],
            confidence=confidence,
            verification_status=verification_status,
        )
        session.add(entry)
        session.flush()


def iter_repair_candidates(
    session: Session,
    *,
    ids: list[int] | None = None,
    start_after: int | None = None,
    limit: int | None = None,
) -> list[int]:
    """Deterministic, resumable id selection for source repair."""
    stmt = select(Scholarship.id).where(Scholarship.official_source_url.is_not(None))
    if ids is not None:
        # An explicit empty list means "nothing selected". Falling through would
        # silently select the entire catalogue.
        if not ids:
            return []
        stmt = stmt.where(Scholarship.id.in_(ids))
    if start_after is not None:
        stmt = stmt.where(Scholarship.id > start_after)
    stmt = stmt.order_by(Scholarship.id)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())
