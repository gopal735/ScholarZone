"""Official-source enrichment engine for existing Scholarship records.

This is the reusable enrichment half of the ScholarZone data pipeline:

    resolve official source -> fetch -> extract -> project -> merge -> status -> freshness

Design constraints (deliberate, not incidental):

* **No fabrication.** Every value written here originates from
  ``ScholarshipExtractionResult`` produced by ``scholarship_extractor`` from
  official page content. Nothing is inferred, guessed, or synthesised.
* **No destruction of good data.** List fields are merged by union, text fields
  are filled only when empty (or replaced only under explicit, narrow rules).
  A record is never rewritten wholesale.
* **Idempotent.** Running enrichment twice against an unchanged official page
  produces zero writes the second time.
* **Evidence-first.** Only values backed by high/medium-confidence extraction
  from an authoritative (official) source are eligible to be written.
* **Third-party sources may not set facts.** ``classify_source`` gates writes;
  an aggregator can hint at a source URL but can never author a value.

The extractor already produces rich fields (financial coverage, eligibility,
language, renewal conditions) that the historical diff engine ignored. This
module composes those into the canonical Scholarship columns.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Any
from urllib.parse import urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..models import Scholarship
from .discovery_scheduler import DomainRateLimiter
from .official_source_fetcher import fetch_official_source
from .scholarship_evidence import SourceType, classify_source, is_authoritative_source
from .scholarship_extractor import (
    ExtractionConfidence,
    ScholarshipExtractionResult,
    extract_scholarship_information,
)

logger = logging.getLogger(__name__)


# Related official pages worth opening, keyed to the facts each typically
# carries. Following these is the difference between one page of facts and the
# full official picture: eligibility, funding and application detail usually
# live on their own pages rather than the programme landing page.
_RELATED_PAGE_KEYWORDS: tuple[str, ...] = (
    "eligib", "who-can-apply", "requirements", "criteria", "admission-requirements",
    "funding", "benefi", "tuition", "stipend", "financial", "fees", "scholarship-amount",
    "how-to-apply", "apply", "application", "apply-now", "submission",
    "document", "checklist", "required-document", "supporting-document",
    "faq", "frequently-asked", "questions",
    "update", "announcement", "news", "deadline",
)

MAX_RELATED_PAGES = 4


def _related_official_links(page_html: str, base_url: str) -> list[str]:
    """Find same-domain official links that likely carry additional facts."""
    if not page_html:
        return []
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(page_html[:400_000], "html.parser")
    except Exception:  # noqa: BLE001
        return []

    base_netloc = urlparse(base_url).netloc.lower().removeprefix("www.")
    base_path = urlparse(base_url).path.rstrip("/")
    found: list[str] = []
    seen: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "javascript:", "tel:")):
            continue
        try:
            absolute = urljoin(base_url, href)
        except Exception:  # noqa: BLE001
            continue
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if parsed.netloc.lower().removeprefix("www.") != base_netloc:
            continue

        normalized = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
        if normalized == f"{base_netloc}{base_path}" or normalized in seen:
            continue

        haystack = f"{parsed.path} {anchor.get_text(' ', strip=True)}".lower()
        if not any(kw in haystack for kw in _RELATED_PAGE_KEYWORDS):
            continue
        if any(
            bad in parsed.path.lower()
            for bad in ("/login", "/register", "/logout", "/cart", "/privacy", "/terms", "/cookie")
        ):
            continue
        seen.add(normalized)
        found.append(absolute)
        if len(found) >= MAX_RELATED_PAGES:
            break
    return found


# --------------------------------------------------------------------------
# Status vocabulary
#
# Reuses the vocabulary already persisted and already understood by the
# frontend (scholarshipPresentation.js, ScholarshipList.jsx). Introducing a new
# vocabulary here would silently break existing filters and stats.
# --------------------------------------------------------------------------
STATUS_OPEN = "open"
STATUS_CLOSING_SOON = "closing-soon"
STATUS_CLOSED = "closed"
STATUS_UNKNOWN = "unknown"

CLOSING_SOON_WINDOW_DAYS = 30


class EnrichmentOutcome(str, Enum):
    ENRICHED = "enriched"
    UNCHANGED = "unchanged"
    NO_OFFICIAL_SOURCE = "no_official_source"
    SOURCE_UNAVAILABLE = "source_unavailable"
    NOT_AUTHORITATIVE = "not_authoritative"
    NO_USABLE_EXTRACTION = "no_usable_extraction"
    ERROR = "error"


@dataclass
class FieldUpdate:
    """One field-level write decision, with provenance for observability."""

    field_name: str
    action: str  # "merged" | "filled" | "replaced" | "unchanged" | "skipped"
    reason: str
    added_items: list[str] = field(default_factory=list)
    source_url: str | None = None


@dataclass
class EnrichmentResult:
    """Outcome of enriching a single scholarship."""

    scholarship_id: int
    outcome: EnrichmentOutcome
    source_url: str | None = None
    source_type: str | None = None
    updates: list[FieldUpdate] = field(default_factory=list)
    status_changed: bool = False
    new_status: str | None = None
    deadline_changed: bool = False
    fetch_error: str | None = None
    fetch_attempts: int = 0
    related_pages_followed: int = 0
    retryable: bool = False
    dry_run: bool = True
    runtime_ms: float = 0.0

    @property
    def changed_fields(self) -> list[str]:
        return [u.field_name for u in self.updates if u.action in ("merged", "filled", "replaced")]

    @property
    def was_enriched(self) -> bool:
        return self.outcome == EnrichmentOutcome.ENRICHED


# --------------------------------------------------------------------------
# Source resolution
# --------------------------------------------------------------------------

# Priority 1 is the scholarship/programme page itself. These are fallbacks only.
_SOURCE_PRIORITY_FIELDS = (
    "official_source_url",
    "application_link",
    "catalogue_url",
    "official_updates_url",
)


@dataclass(frozen=True)
class ResolvedOfficialSource:
    url: str
    field_name: str
    source_type: SourceType
    authoritative: bool


def resolve_official_source(scholarship: Scholarship) -> ResolvedOfficialSource | None:
    """Pick the strongest official source URL available on a record.

    Priority follows the documented contract: programme page, then application
    link, then catalogue/update pages. The first URL that both parses and is
    NOT a known aggregator wins; we still return non-authoritative candidates so
    the caller can report them rather than silently doing nothing.
    """
    seen: set[str] = set()
    for field_name in _SOURCE_PRIORITY_FIELDS:
        raw = getattr(scholarship, field_name, None)
        if not raw or not isinstance(raw, str):
            continue
        url = raw.strip()
        if not url:
            continue
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("http://"):
            # Keep as-is; the fetcher follows redirects and the source may be
            # http-only. Authority classification is scheme-agnostic.
            pass
        if not urlparse(url).netloc:
            continue
        normalized = url.rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)

        source_type = classify_source(url)
        if is_authoritative_source(source_type):
            return ResolvedOfficialSource(
                url=url,
                field_name=field_name,
                source_type=source_type,
                authoritative=True,
            )

    # Nothing authoritative: report the first parseable URL so the caller can
    # record "not_authoritative" with evidence instead of a bare "no source".
    for field_name in _SOURCE_PRIORITY_FIELDS:
        raw = getattr(scholarship, field_name, None)
        if raw and isinstance(raw, str) and urlparse(raw.strip()).netloc:
            return ResolvedOfficialSource(
                url=raw.strip(),
                field_name=field_name,
                source_type=classify_source(raw.strip()),
                authoritative=False,
            )
    return None


# --------------------------------------------------------------------------
# Extraction projection
# --------------------------------------------------------------------------

_BULLET_SPLIT = re.compile(r"[\n\r]+|^\s*[-\u2022*\u25aa\u2023\u2043]\s+", re.MULTILINE)
_SENTENCE_SPLIT = re.compile(r";\s+")
# Used to trim over-long captured values back to a clean clause boundary rather
# than leaving them cut mid-word.
_TRAILING_TRUNCATION = re.compile(r"[\s,;:\-–—/|&]+$")
_CLAUSE_BREAK = re.compile(r"[.;]\s+|,\s+|\s+–\s+|\s+—\s+")
# Anchor markers injected by the extractor's text walker.
_LINK_MARKER_RE = re.compile(r"\[/?LINK\]", re.IGNORECASE)

_MAX_VALUE_LENGTH = 200


def _trim_to_clause(value: str, limit: int = _MAX_VALUE_LENGTH) -> str:
    """Trim an over-long capture at the last clause boundary inside the limit.

    An extractor bounded at N characters otherwise yields values cut mid-word
    ("... housing searches, cu"), which is not a usable fact.
    """
    if len(value) <= limit:
        return value
    window = value[:limit]
    breaks = list(_CLAUSE_BREAK.finditer(window))
    if breaks:
        cut = breaks[-1].end()
        trimmed = window[:cut]
    else:
        # No clause boundary: fall back to the last word boundary.
        trimmed = window.rsplit(" ", 1)[0]
    trimmed = _TRAILING_TRUNCATION.sub("", trimmed)
    return trimmed if len(trimmed) >= 20 else window


_PLACEHOLDERS = frozenset(
    {
        "n/a",
        "na",
        "none",
        "not specified",
        "not available",
        "not applicable",
        "-",
        "--",
        "unknown",
        "tbc",
        "tbd",
        "please refer",
        "see website",
        "see below",
        "click here",
        # Form labels that land in the value position on real application pages.
        "open date",
        "close date",
        "start date",
        "end date",
        "scholarship type",
        "application type",
        "study level",
        "number of scholarships awarded",
        "award type",
    }
)


def _is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    text = value.strip()
    if not text:
        return True
    return text.lower().rstrip(".") in _PLACEHOLDERS


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip(" \t\r\n;")
    if not text or _is_placeholder(text):
        return None
    return text


def as_list(value: str | None) -> list[str]:
    """Split an extracted text blob into discrete list items.

    Conservative by design: only splits on real structural separators
    (newlines, bullet markers, semicolons). A single sentence stays a single
    item rather than being shredded into fragments.

    Splitting happens *before* whitespace collapsing -- collapsing first would
    destroy the very newlines and bullet markers we split on.
    """
    if value is None:
        return []
    raw = str(value)
    if not raw.strip():
        return []

    items: list[str] = []
    for part in _BULLET_SPLIT.split(raw):
        cleaned = _LINK_MARKER_RE.sub("", part)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\r\n;-\u2022\u25aa\u2023\u2043*")
        if _is_placeholder(cleaned):
            continue
        items.append(_trim_to_clause(cleaned))

    if len(items) == 1 and len(items[0]) > 160:
        # Long single blob: semicolons are the only safe secondary separator.
        sub = [p.strip() for p in _SENTENCE_SPLIT.split(items[0])]
        if len(sub) > 1:
            items = [p for p in sub if p]

    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = re.sub(r"\s+", " ", item).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


# Canonical ORM field -> tuple of extractor fields composed into it.
# Ordered so that the FIRST extractor field is the primary contributor.
_LIST_PROJECTION: dict[str, tuple[str, ...]] = {
    # Who may apply (identity/availability), kept separate from proof-of-qualification.
    "eligibility": ("eligible_nationalities", "eligible_fields", "eligibility"),
    # What the applicant must hold/prove.
    "requirements": ("academic_requirements", "gpa_requirement", "renewal_conditions"),
    # What the award actually pays for.
    "coverage": ("tuition_coverage", "living_stipend", "housing", "insurance", "travel"),
    # Disbursement headline. Deliberately does NOT re-use coverage items:
    # benefits and coverage are distinct contracts and must not be duplicated.
    "benefits": ("award_amount",),
    "application_method": ("application_method",),
}

_TEXT_PROJECTION: dict[str, tuple[str, ...]] = {
    "duration": ("duration",),
    "english_requirement": ("language_requirement", "test_requirements"),
    "program_type": ("program_type",),
}

_SCALAR_PROJECTION: dict[str, str] = {
    "degree": "degree_level",
}

# Fields the enrichment engine is willing to write. Derived from the projection
# tables plus the two deadline columns the extractor populates directly and the
# status column, which is derived rather than extracted.
#
# `study_mode` and `intake` are extracted and carried in evidence but have no
# Scholarship column, so they are deliberately absent rather than being folded
# into a near-miss column such as `application_period`.
WRITABLE_FIELDS: frozenset[str] = frozenset(
    set(_LIST_PROJECTION)
    | set(_TEXT_PROJECTION)
    | set(_SCALAR_PROJECTION)
    | {"deadline_display", "deadline_precision", "status"}
)


def _confidence_for(extracted: ScholarshipExtractionResult, fields: tuple[str, ...]) -> str:
    """Weakest-link confidence across the contributing extractor fields."""
    seen = [extracted.confidence.get(f) for f in fields if getattr(extracted, f, None)]
    if not seen:
        return ExtractionConfidence.LOW
    if any(c == ExtractionConfidence.LOW for c in seen):
        return ExtractionConfidence.LOW
    if any(c == ExtractionConfidence.MEDIUM for c in seen):
        return ExtractionConfidence.MEDIUM
    return ExtractionConfidence.HIGH


def project_enrichment(
    extracted: ScholarshipExtractionResult,
) -> dict[str, dict[str, Any]]:
    """Compose extractor output into canonical ORM field proposals.

    Returns ``{orm_field: {"value": ..., "confidence": ..., "sources": [...]}}``.
    Only fields with at least one non-empty contribution appear, and LOW
    confidence contributions are dropped so they can never be written.
    """
    proposals: dict[str, dict[str, Any]] = {}

    for orm_field, extractor_fields in _LIST_PROJECTION.items():
        items: list[str] = []
        contributing: list[str] = []
        for ef in extractor_fields:
            raw = getattr(extracted, ef, None)
            if not raw:
                continue
            if extracted.confidence.get(ef) == ExtractionConfidence.LOW:
                continue
            items.extend(as_list(raw))
            contributing.append(ef)
        if not items:
            continue
        deduped: list[str] = []
        seen: set[str] = set()
        for item in items:
            key = re.sub(r"\s+", " ", item).strip().lower()
            if key not in seen:
                seen.add(key)
                deduped.append(item)
        proposals[orm_field] = {
            "value": deduped,
            "confidence": _confidence_for(extracted, tuple(contributing)),
            "sources": contributing,
        }

    for orm_field, extractor_fields in _TEXT_PROJECTION.items():
        parts = [
            _clean(getattr(extracted, ef, None))
            for ef in extractor_fields
            if getattr(extracted, ef, None)
            and extracted.confidence.get(ef) != ExtractionConfidence.LOW
        ]
        parts = [p for p in parts if p]
        if not parts:
            continue
        seen_t: set[str] = set()
        joined: list[str] = []
        for p in parts:
            if p.lower() not in seen_t:
                seen_t.add(p.lower())
                joined.append(p)
        proposals[orm_field] = {
            "value": ". ".join(joined),
            "confidence": _confidence_for(extracted, tuple(extractor_fields)),
            "sources": list(extractor_fields),
        }

    for orm_field, ef in _SCALAR_PROJECTION.items():
        raw = getattr(extracted, ef, None)
        if not raw or extracted.confidence.get(ef) == ExtractionConfidence.LOW:
            continue
        proposals[orm_field] = {
            "value": _clean(raw),
            "confidence": _confidence_for(extracted, (ef,)),
            "sources": [ef],
        }

    # Deadline precision: the extractor knows whether a deadline is exact,
    # month-level, rolling, etc. Only trust it when it states one explicitly.
    deadline_type = _clean(extracted.deadline_type)
    if deadline_type and extracted.confidence.get("deadline_type") != ExtractionConfidence.LOW:
        proposals["deadline_precision"] = {
            "value": deadline_type.lower()[:16],
            "confidence": _confidence_for(extracted, ("deadline_type",)),
            "sources": ["deadline_type"],
        }

    # Deadline display, only when we have a deadline and no better stored value
    # will be overwritten (merge policy decides).
    deadline = _clean(extracted.deadline)
    if deadline and extracted.confidence.get("deadline") != ExtractionConfidence.LOW:
        proposals["deadline_display"] = {
            "value": deadline,
            "confidence": _confidence_for(extracted, ("deadline",)),
            "sources": ["deadline"],
        }

    return proposals


# --------------------------------------------------------------------------
# Status derivation
# --------------------------------------------------------------------------

_CLOSED_TEXT_PATTERNS = (
    re.compile(r"applications?\s+(?:have\s+|has\s+|are\s+|is\s+)?closed", re.I),
    re.compile(r"no\s+longer\s+accepting\s+applications?", re.I),
    re.compile(r"applications?\s+are\s+no\s+longer\s+open", re.I),
    re.compile(r"programme?\s+(?:has\s+|is\s+)?closed", re.I),
    re.compile(r"call\s+for\s+applications?\s+has\s+closed", re.I),
)
_OPEN_TEXT_PATTERNS = (
    re.compile(r"applications?\s+are\s+open", re.I),
    re.compile(r"applications?\s+open\s+(?:now|until)", re.I),
    re.compile(r"rolling\s+(?:admission|application)", re.I),
    re.compile(r"accepting\s+applications?", re.I),
    re.compile(r"now\s+open", re.I),
)
_CLOSING_SOON_TEXT_PATTERNS = (
    re.compile(r"applications?\s+close\s+(?:soon|on|by)", re.I),
    re.compile(r"closing\s+soon", re.I),
    re.compile(r"last\s+call", re.I),
)


def derive_status(
    *,
    today: date,
    deadline_date: date | None,
    deadline_display: str | None,
    deadline_precision: str | None,
    source_text: str | None,
    current_status: str | None,
) -> tuple[str, str]:
    """Derive an application status from official signals only.

    Returns ``(status, reason)``. Status uses the existing persisted vocabulary
    (open / closing-soon / closed / unknown). ``UNKNOWN`` is returned when no
    official signal exists, so the caller can choose to leave the stored value
    alone rather than guess.
    """
    text = source_text or ""

    for pattern in _CLOSED_TEXT_PATTERNS:
        if pattern.search(text):
            return STATUS_CLOSED, f"official page states: {pattern.pattern}"

    if deadline_date is not None:
        if deadline_date < today:
            return STATUS_CLOSED, f"parsed deadline {deadline_date.isoformat()} is in the past"
        if deadline_date <= today + timedelta(days=CLOSING_SOON_WINDOW_DAYS):
            return STATUS_CLOSING_SOON, f"parsed deadline {deadline_date.isoformat()} within {CLOSING_SOON_WINDOW_DAYS}d"
        return STATUS_OPEN, f"parsed deadline {deadline_date.isoformat()} is in the future"

    precision = (deadline_precision or "").strip().lower()
    display = (deadline_display or "").strip().lower()

    for pattern in _CLOSING_SOON_TEXT_PATTERNS:
        if pattern.search(text):
            return STATUS_CLOSING_SOON, f"official page states: {pattern.pattern}"

    for pattern in _OPEN_TEXT_PATTERNS:
        if pattern.search(text):
            return STATUS_OPEN, f"official page states: {pattern.pattern}"

    if precision in {"varies", "rolling"} or re.search(r"\brolling\b|\byear[- ]round\b", display):
        return STATUS_OPEN, "deadline described as rolling/varied, so applications are treated as open"

    if precision in {"exact", "day", "month"} and display:
        return STATUS_UNKNOWN, "deadline described but not parseable to a date"

    return STATUS_UNKNOWN, "no official status signal found"


# --------------------------------------------------------------------------
# Merge policy
# --------------------------------------------------------------------------


def merge_list(existing: list[str] | None, incoming: list[str] | None) -> tuple[list[str], list[str]]:
    """Union-merge two lists. Returns ``(merged, added_items)``.

    Union is the only safe merge for these columns: it adds newly-stated
    official facts, preserves everything already known, and is naturally
    idempotent (re-running yields zero additions).
    """
    out: list[str] = []
    seen: set[str] = set()
    for item in list(existing or []) + list(incoming or []):
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    existing_keys = {
        re.sub(r"\s+", " ", i).strip().lower() for i in (existing or []) if isinstance(i, str)
    }
    added = [i for i in out if re.sub(r"\s+", " ", i).strip().lower() not in existing_keys]
    return out, added


def _text_fill_decision(existing: str | None, incoming: str | None) -> tuple[str, str, str]:
    """Decide what to do with a text field.

    Fill-if-empty is the default. Replacement is allowed only when the stored
    value is one of the placeholder sentinels the catalogue still contains, or
    when the stored value is a strict prefix/substring of the new official
    value (i.e. the official page is more specific, not contradicting).
    """
    inc = _clean(incoming)
    cur = _clean(existing)

    if inc is None:
        return "unchanged", "no official value extracted", ""

    if cur is None:
        return "fill", "existing value empty", inc

    if cur.lower() == inc.lower():
        return "unchanged", "identical to stored value", ""

    if cur.lower() in {"unknown", "n/a", "not specified", "-"}:
        return "replace", "stored value was a placeholder", inc

    if len(inc) > len(cur) and cur.lower() in inc.lower():
        return "replace", "official value is a more specific form of stored value", inc

    return "keep", "existing value retained; official value would overwrite existing data", ""


def _merge_projections(
    proposals_list: list[dict[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Merge proposals from several official pages, earliest page winning.

    List-valued fields accumulate across pages (union, so no page can delete
    what another established). Scalar fields keep the first value seen, because
    the landing page is the most authoritative statement about identity.
    Confidence is the strongest observed for that field.
    """
    merged: dict[str, dict[str, Any]] = {}
    for proposals in proposals_list:
        for field_name, proposal in proposals.items():
            if field_name not in merged:
                merged[field_name] = {
                    "value": proposal["value"],
                    "confidence": proposal.get("confidence"),
                    "sources": list(proposal.get("sources") or []),
                }
                continue
            existing = merged[field_name]
            if isinstance(existing["value"], list) and isinstance(proposal["value"], list):
                combined, _ = merge_list(existing["value"], proposal["value"])
                existing["value"] = combined
            for src in proposal.get("sources") or []:
                if src not in existing["sources"]:
                    existing["sources"].append(src)
            if proposal.get("confidence") == ExtractionConfidence.HIGH:
                existing["confidence"] = ExtractionConfidence.HIGH
    return merged


# --------------------------------------------------------------------------
# Service
# --------------------------------------------------------------------------

# Errors worth one more attempt.
_RETRYABLE_ERROR_TYPES = frozenset({"timeout", "connection_error", "server_error", "rate_limited"})


class ScholarshipEnrichmentService:
    """Enrich one scholarship from its strongest official source.

    Read-only when ``dry_run=True`` (the default): every decision is computed
    and reported, but nothing is written.
    """

    def __init__(
        self,
        session_factory: sessionmaker[Session] | None = None,
        *,
        dry_run: bool = True,
        rate_limiter: DomainRateLimiter | None = None,
        max_attempts: int = 2,
        follow_related_pages: bool = True,
        now_fn=None,
    ) -> None:
        if session_factory is None:
            from ..database import get_session_factory

            session_factory = get_session_factory()
        self._session_factory = session_factory
        self.dry_run = dry_run
        self.rate_limiter = rate_limiter or DomainRateLimiter(min_interval_seconds=1.0)
        self.max_attempts = max(1, max_attempts)
        # Following related official pages multiplies requests per record. It is
        # the right default for a catalogue enrichment pass and is disabled in
        # unit tests that only care about a single page.
        self.follow_related_pages = follow_related_pages
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    # -- fetching ---------------------------------------------------------

    def _fetch_with_retry(self, url: str) -> tuple[Any, int, str | None, bool]:
        """Fetch a URL honouring the rate limiter, with bounded retry."""
        domain = urlparse(url).netloc
        last_error: str | None = None
        retryable = False
        attempts = 0
        result = None
        for attempt in range(self.max_attempts):
            attempts += 1
            if domain:
                self.rate_limiter.wait_if_needed(domain)
            result = fetch_official_source(url)
            if result.success:
                return result, attempts, None, False
            last_error = f"{result.error_type}: {result.error_reason}"
            retryable = result.error_type in _RETRYABLE_ERROR_TYPES
            if not retryable or attempt == self.max_attempts - 1:
                break
            time.sleep(min(2 ** attempt, 5))
        return result, attempts, last_error, retryable

    # -- main entry point -------------------------------------------------

    def enrich_one(self, scholarship_id: int) -> EnrichmentResult:
        started = time.monotonic()
        session = self._session_factory()
        try:
            result = self._enrich_in_session(session, scholarship_id)
        except Exception as exc:  # noqa: BLE001 - a single record must never kill a batch
            logger.exception("enrichment failed for scholarship_id=%s", scholarship_id)
            result = EnrichmentResult(
                scholarship_id=scholarship_id,
                outcome=EnrichmentOutcome.ERROR,
                fetch_error=f"{type(exc).__name__}: {exc}",
            )
        finally:
            session.close()
        result.dry_run = self.dry_run
        result.runtime_ms = (time.monotonic() - started) * 1000.0
        return result

    def _enrich_in_session(self, session: Session, scholarship_id: int) -> EnrichmentResult:
        scholarship = session.get(Scholarship, scholarship_id)
        if scholarship is None:
            return EnrichmentResult(
                scholarship_id=scholarship_id,
                outcome=EnrichmentOutcome.ERROR,
                fetch_error="scholarship not found",
            )

        resolved = resolve_official_source(scholarship)
        if resolved is None:
            return EnrichmentResult(
                scholarship_id=scholarship_id,
                outcome=EnrichmentOutcome.NO_OFFICIAL_SOURCE,
            )
        if not resolved.authoritative:
            return EnrichmentResult(
                scholarship_id=scholarship_id,
                outcome=EnrichmentOutcome.NOT_AUTHORITATIVE,
                source_url=resolved.url,
                source_type=resolved.source_type.value,
            )

        fetch_result, attempts, fetch_error, retryable = self._fetch_with_retry(resolved.url)
        if fetch_result is None or not fetch_result.success:
            outcome = (
                EnrichmentOutcome.SOURCE_UNAVAILABLE
                if retryable
                else EnrichmentOutcome.SOURCE_UNAVAILABLE
            )
            return EnrichmentResult(
                scholarship_id=scholarship_id,
                outcome=outcome,
                source_url=resolved.url,
                source_type=resolved.source_type.value,
                fetch_error=fetch_error or "unknown fetch failure",
                fetch_attempts=attempts,
                retryable=retryable,
            )

        content = fetch_result.content or ""
        final_url = fetch_result.final_url or resolved.url
        extracted = extract_scholarship_information(content, final_url)
        proposals = project_enrichment(extracted)

        result = EnrichmentResult(
            scholarship_id=scholarship_id,
            outcome=EnrichmentOutcome.UNCHANGED,
            source_url=resolved.url,
            source_type=resolved.source_type.value,
            fetch_attempts=attempts,
        )

        # Multi-page official research: the landing page rarely carries the
        # full official picture. Follow same-domain eligibility / funding /
        # application / documents links and merge whatever additional facts
        # they state. Earlier pages win ties, because the landing page is the
        # most authoritative for the record's identity.
        related = _related_official_links(content, final_url)
        if related and self.follow_related_pages:
            combined: list[dict[str, dict[str, Any]]] = [proposals] if proposals else []
            combined_text: list[str] = [content]
            for page_url in related:
                page_fetch, _n, _err, _retry = self._fetch_with_retry(page_url)
                if page_fetch is None or not page_fetch.success or not page_fetch.content:
                    continue
                result.related_pages_followed += 1
                combined_text.append(page_fetch.content)
                page_proposals = project_enrichment(
                    extract_scholarship_information(page_fetch.content, page_url)
                )
                if page_proposals:
                    combined.append(page_proposals)
            proposals = _merge_projections(combined)
            content = "\n".join(combined_text)

        if not proposals and not _clean(extracted.status) and not _clean(extracted.deadline):
            result.outcome = EnrichmentOutcome.NO_USABLE_EXTRACTION
            return result

        result.updates = self._apply_proposals(session, scholarship, proposals, resolved.url)
        self._apply_status(session, scholarship, extracted, content, result)
        self._stamp_freshness(session, scholarship, result)

        result.outcome = (
            EnrichmentOutcome.ENRICHED
            if result.changed_fields or result.status_changed
            else EnrichmentOutcome.UNCHANGED
        )
        if not self.dry_run:
            session.commit()
        else:
            session.rollback()
        return result

    # -- write planning ---------------------------------------------------

    def _apply_proposals(
        self,
        session: Session,
        scholarship: Scholarship,
        proposals: dict[str, dict[str, Any]],
        source_url: str,
    ) -> list[FieldUpdate]:
        updates: list[FieldUpdate] = []
        for orm_field, proposal in proposals.items():
            if orm_field not in WRITABLE_FIELDS or not hasattr(Scholarship, orm_field):
                continue
            confidence = proposal.get("confidence")
            if confidence == ExtractionConfidence.LOW:
                updates.append(
                    FieldUpdate(orm_field, "skipped", "low-confidence extraction", source_url=source_url)
                )
                continue

            value = proposal.get("value")
            if orm_field in _LIST_PROJECTION:
                merged, added = merge_list(getattr(scholarship, orm_field, None), value)
                if not added:
                    updates.append(
                        FieldUpdate(orm_field, "unchanged", "no new items from official source", source_url=source_url)
                    )
                    continue
                setattr(scholarship, orm_field, merged)
                updates.append(
                    FieldUpdate(
                        orm_field,
                        "merged",
                        f"added {len(added)} item(s) from official source",
                        added_items=added,
                        source_url=source_url,
                    )
                )
            else:
                current = getattr(scholarship, orm_field, None)
                action, reason, resolved_value = _text_fill_decision(current, value)
                if action == "unchanged":
                    updates.append(FieldUpdate(orm_field, "unchanged", reason, source_url=source_url))
                    continue
                if action == "keep":
                    updates.append(
                        FieldUpdate(orm_field, "skipped", reason, source_url=source_url)
                    )
                    continue
                if action == "fill":
                    # Only fill empty slots from medium confidence upward.
                    if confidence != ExtractionConfidence.HIGH and not isinstance(current, type(None)):
                        updates.append(
                            FieldUpdate(orm_field, "skipped", "fill requires high confidence", source_url=source_url)
                        )
                        continue
                setattr(scholarship, orm_field, resolved_value)
                updates.append(
                    FieldUpdate(
                        orm_field,
                        "fill" if action == "fill" else "replace",
                        reason,
                        added_items=[resolved_value] if resolved_value else [],
                        source_url=source_url,
                    )
                )
        return updates

    def _apply_status(
        self,
        session: Session,
        scholarship: Scholarship,
        extracted: ScholarshipExtractionResult,
        content: str,
        result: EnrichmentResult,
    ) -> None:
        today = self._now_fn().date()
        status, reason = derive_status(
            today=today,
            deadline_date=scholarship.deadline_date,
            deadline_display=scholarship.deadline_display,
            deadline_precision=scholarship.deadline_precision,
            source_text=content,
            current_status=scholarship.status,
        )
        if status == STATUS_UNKNOWN:
            result.updates.append(FieldUpdate("status", "skipped", reason, source_url=result.source_url))
            return
        if (scholarship.status or "") != status:
            result.status_changed = True
            result.new_status = status
            result.updates.append(
                FieldUpdate("status", "replaced", reason, added_items=[status], source_url=result.source_url)
            )
            scholarship.status = status
        else:
            result.updates.append(
                FieldUpdate("status", "unchanged", f"already {status}", source_url=result.source_url)
            )

    def _stamp_freshness(
        self,
        session: Session,
        scholarship: Scholarship,
        result: EnrichmentResult,
    ) -> None:
        """Record that an authoritative source was successfully re-checked.

        Only stamped on a successful fetch, and only for records already marked
        verified, so this never inflates trust.
        """
        if not scholarship.is_verified:
            result.updates.append(
                FieldUpdate("last_verified_at", "skipped", "record is not verified", source_url=result.source_url)
            )
            return
        stamp = self._now_fn().date()
        if scholarship.last_verified_at != stamp:
            scholarship.last_verified_at = stamp
            result.updates.append(
                FieldUpdate(
                    "last_verified_at",
                    "replaced",
                    "official source re-checked successfully",
                    added_items=[stamp.isoformat()],
                    source_url=result.source_url,
                )
            )
        else:
            result.updates.append(
                FieldUpdate("last_verified_at", "unchanged", "already stamped today", source_url=result.source_url)
            )


def enrich_scholarships(
    session_factory: sessionmaker[Session],
    scholarship_ids: list[int],
    *,
    dry_run: bool = True,
    rate_limiter: DomainRateLimiter | None = None,
    max_attempts: int = 2,
) -> list[EnrichmentResult]:
    """Convenience helper for ad-hoc enrichment of specific records."""
    service = ScholarshipEnrichmentService(
        session_factory,
        dry_run=dry_run,
        rate_limiter=rate_limiter,
        max_attempts=max_attempts,
    )
    return [service.enrich_one(sid) for sid in scholarship_ids]


def iter_enrichable_ids(
    session: Session,
    *,
    only_missing: bool = False,
    ids: list[int] | None = None,
) -> list[int]:
    """List scholarship ids to enrich, ordered for deterministic batching."""
    stmt = select(Scholarship.id).order_by(Scholarship.id)
    if ids:
        stmt = stmt.where(Scholarship.id.in_(ids))
    if only_missing:
        # Records with no official source URL at all can never be enriched.
        stmt = stmt.where(Scholarship.official_source_url.is_not(None))
    return [row for row in session.scalars(stmt).all()]
