"""Scholarship lifecycle and semantic identity intelligence.

Determines:
1. Whether a discovered/updated scholarship is the same, renamed, new cycle, related, or new
2. The deterministic lifecycle state of a scholarship
3. Cycle/version awareness for recurring programs

Deterministic, no network calls, no duplicate persistence.
All metrics derived from existing Scholarship, DiscoveryCandidate,
ScholarshipVerificationHistory, and SourceHealth data.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import DiscoveryCandidate, Scholarship, ScholarshipVerificationHistory
from .change_impact_staleness import compute_deadline_urgency
from .discovery_identity import (
    _containment_score,
    normalize_provider,
    normalize_title,
    normalize_url,
)
from .source_health_service import extract_domain

DISCOVERED = "discovered"
ACTIVE = "active"
APPLICATION_OPEN = "application_open"
DEADLINE_NEAR = "deadline_near"
CLOSED = "closed"
RESULT_PENDING = "result_pending"
ARCHIVED = "archived"
UNKNOWN = "unknown"

LIFECYCLE_STATES = frozenset({
    DISCOVERED, ACTIVE, APPLICATION_OPEN, DEADLINE_NEAR,
    CLOSED, RESULT_PENDING, ARCHIVED, UNKNOWN,
})

DEADLINE_NEAR_THRESHOLD_DAYS = 30
ARCHIVED_THRESHOLD_DAYS = 365

IDENTITY_EXACT = "exact"
IDENTITY_CANONICAL = "canonical"
IDENTITY_PROVIDER = "provider"
IDENTITY_SIMILAR = "similar"
IDENTITY_REVIEW = "review"
IDENTITY_NEW = "new"

IDENTITY_RESOLUTION_TYPES = frozenset({
    IDENTITY_EXACT, IDENTITY_CANONICAL, IDENTITY_PROVIDER,
    IDENTITY_SIMILAR, IDENTITY_REVIEW, IDENTITY_NEW,
})

CYCLE_SAME = "same_cycle"
CYCLE_NEW = "new_cycle"
CYCLE_RENAMED = "renamed"
CYCLE_DISTINCT = "distinct"


@dataclass(frozen=True)
class IdentityFingerprint:
    provider: str
    domain: str
    title: str
    degree: str
    funding: str
    country: str
    url_path: str
    year_hint: int | None


@dataclass(frozen=True)
class IdentityResolution:
    resolution_type: str
    matched_id: int | None
    confidence: float
    fingerprint: IdentityFingerprint
    reason: str
    cycle_status: str = CYCLE_SAME


@dataclass(frozen=True)
class LifecycleState:
    state: str
    previous_state: str | None
    scholarship_id: int
    reason: str
    deadline_urgency: int
    is_terminal: bool


@dataclass(frozen=True)
class LifecycleTransition:
    scholarship_id: int
    from_state: str
    to_state: str
    reason: str
    triggered_at: datetime


def _normalize_degree(degree: str | None) -> str:
    if not degree:
        return ""
    d = degree.lower().strip()
    mapping = {
        "phd": "phd", "ph.d": "phd", "doctorate": "phd", "doctoral": "phd",
        "masters": "masters", "master": "masters", "ms": "masters", "ma": "masters", "msc": "masters",
        "bachelors": "bachelors", "bachelor": "bachelors", "bs": "bachelors", "ba": "bachelors", "bsc": "bachelors",
        "postdoc": "postdoc", "postdoctoral": "postdoc",
    }
    return mapping.get(d, d)


def _normalize_funding(funding: str | None) -> str:
    if not funding:
        return ""
    f = funding.lower().strip()
    mapping = {
        "full": "full", "fully funded": "full", "full funding": "full",
        "partial": "partial", "partially funded": "partial", "partial funding": "partial",
        "tuition": "tuition", "tuition waiver": "tuition",
    }
    return mapping.get(f, f)


def _url_path(url: str | None) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"
        return path.lower()
    except Exception:
        return ""


def _extract_year_hint(text: str | None) -> int | None:
    if not text:
        return None
    years = [int(m) for m in re.findall(r"\b(20\d{2})\b", text)]
    if not years:
        return None
    current_year = datetime.now(timezone.utc).year
    valid_years = [y for y in years if 2000 <= y <= current_year + 2]
    return max(valid_years) if valid_years else None


def build_fingerprint(
    title: str | None,
    provider: str | None,
    official_source_url: str | None,
    degree: str | None,
    funding: str | None,
    country: str | None,
) -> IdentityFingerprint:
    domain = extract_domain(official_source_url) or ""
    return IdentityFingerprint(
        provider=normalize_provider(provider),
        domain=domain,
        title=normalize_title(title),
        degree=_normalize_degree(degree),
        funding=_normalize_funding(funding),
        country=(country or "").lower().strip(),
        url_path=_url_path(official_source_url),
        year_hint=_extract_year_hint(title),
    )


def _fingerprint_similarity(a: IdentityFingerprint, b: IdentityFingerprint) -> float:
    if a.provider and b.provider and a.provider == b.provider:
        provider_match = 1.0
    elif a.provider and b.provider:
        provider_match = _containment_score(a.provider, b.provider)
    else:
        provider_match = 0.0

    if a.domain and b.domain and a.domain == b.domain:
        domain_match = 1.0
    elif a.domain and b.domain:
        domain_match = 0.0
    else:
        domain_match = 0.0

    if a.title and b.title:
        title_match = _containment_score(a.title, b.title)
    else:
        title_match = 0.0

    if a.url_path and b.url_path and a.url_path == b.url_path:
        path_match = 1.0
    elif a.url_path and b.url_path:
        path_match = _containment_score(a.url_path, b.url_path)
    else:
        path_match = 0.0

    degree_match = 1.0 if (a.degree and b.degree and a.degree == b.degree) else 0.0
    funding_match = 1.0 if (a.funding and b.funding and a.funding == b.funding) else 0.0
    country_match = 1.0 if (a.country and b.country and a.country == b.country) else 0.0

    weighted_score = (
        provider_match * 0.30 +
        domain_match * 0.20 +
        title_match * 0.20 +
        path_match * 0.10 +
        degree_match * 0.10 +
        funding_match * 0.05 +
        country_match * 0.05
    )

    return weighted_score


def _find_exact_identity(
    session: Session,
    fingerprint: IdentityFingerprint,
    source_url: str,
) -> Scholarship | None:
    normalized = normalize_url(source_url)
    if not normalized:
        return None

    variants = [normalized, f"{normalized}/"]
    existing = session.scalars(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source_url).in_(variants),
                func.lower(Scholarship.application_link).in_(variants),
            )
        )
    ).first()
    return existing


def _find_canonical_identity(
    session: Session,
    fingerprint: IdentityFingerprint,
) -> Scholarship | None:
    if not fingerprint.domain:
        return None

    candidates = session.scalars(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source_url).like(f"%{fingerprint.domain}%"),
                func.lower(Scholarship.catalogue_url).like(f"%{fingerprint.domain}%"),
            )
        )
    ).all()

    for s in candidates:
        s_domain = extract_domain(s.official_source_url) or extract_domain(s.catalogue_url) or ""
        if s_domain == fingerprint.domain and fingerprint.url_path:
            s_path = _url_path(s.official_source_url) or _url_path(s.catalogue_url) or ""
            if s_path == fingerprint.url_path:
                return s

    return None


def _find_provider_identity(
    session: Session,
    fingerprint: IdentityFingerprint,
) -> Scholarship | None:
    if not fingerprint.provider:
        return None

    candidates = session.scalars(
        select(Scholarship).where(
            or_(
                func.lower(Scholarship.official_source).like(f"%{fingerprint.provider}%"),
                func.lower(Scholarship.official_source_url).like(f"%{fingerprint.domain}%") if fingerprint.domain else Scholarship.id.is_(None),
            )
        )
    ).all()

    best_match: Scholarship | None = None
    best_score = 0.0

    for s in candidates:
        s_fingerprint = build_fingerprint(
            title=s.title,
            provider=s.official_source,
            official_source_url=s.official_source_url,
            degree=s.degree,
            funding=s.funding,
            country=s.country,
        )

        score = _fingerprint_similarity(fingerprint, s_fingerprint)

        if score > best_score:
            best_score = score
            best_match = s

    if best_score >= 0.75:
        return best_match

    return None


def _find_similar_identity(
    session: Session,
    fingerprint: IdentityFingerprint,
) -> tuple[Scholarship | None, float]:
    if not fingerprint.country:
        return None, 0.0

    candidates = session.scalars(
        select(Scholarship).where(
            func.lower(Scholarship.country) == fingerprint.country
        )
    ).all()

    best_match: Scholarship | None = None
    best_score = 0.0

    for s in candidates:
        s_fingerprint = build_fingerprint(
            title=s.title,
            provider=s.official_source,
            official_source_url=s.official_source_url,
            degree=s.degree,
            funding=s.funding,
            country=s.country,
        )

        score = _fingerprint_similarity(fingerprint, s_fingerprint)

        if score > best_score:
            best_score = score
            best_match = s

    return best_match, best_score


def resolve_identity(
    session: Session,
    title: str | None,
    provider: str | None,
    official_source_url: str | None,
    degree: str | None,
    funding: str | None,
    country: str | None,
) -> IdentityResolution:
    fingerprint = build_fingerprint(
        title=title,
        provider=provider,
        official_source_url=official_source_url,
        degree=degree,
        funding=funding,
        country=country,
    )

    existing = _find_exact_identity(session, fingerprint, official_source_url or "")
    if existing is not None:
        return IdentityResolution(
            resolution_type=IDENTITY_EXACT,
            matched_id=existing.id,
            confidence=1.0,
            fingerprint=fingerprint,
            reason=f"exact_url_match:{existing.official_source_url}",
        )

    existing = _find_canonical_identity(session, fingerprint)
    if existing is not None:
        return IdentityResolution(
            resolution_type=IDENTITY_CANONICAL,
            matched_id=existing.id,
            confidence=0.95,
            fingerprint=fingerprint,
            reason=f"canonical_domain_path_match:{existing.id}",
        )

    existing = _find_provider_identity(session, fingerprint)
    if existing is not None:
        return IdentityResolution(
            resolution_type=IDENTITY_PROVIDER,
            matched_id=existing.id,
            confidence=0.85,
            fingerprint=fingerprint,
            reason=f"provider_metadata_match:{existing.id}",
        )

    similar, score = _find_similar_identity(session, fingerprint)
    if similar is not None and score >= 0.70:
        return IdentityResolution(
            resolution_type=IDENTITY_SIMILAR,
            matched_id=similar.id,
            confidence=score,
            fingerprint=fingerprint,
            reason=f"similarity_match:{similar.id}:score={score:.2f}",
        )

    if similar is not None and score >= 0.50:
        return IdentityResolution(
            resolution_type=IDENTITY_REVIEW,
            matched_id=None,
            confidence=score,
            fingerprint=fingerprint,
            reason=f"ambiguous_match:best_candidate={similar.id}:score={score:.2f}",
        )

    return IdentityResolution(
        resolution_type=IDENTITY_NEW,
        matched_id=None,
        confidence=0.0,
        fingerprint=fingerprint,
        reason="no_match_found",
    )


def resolve_cycle_status(
    session: Session,
    resolution: IdentityResolution,
    title: str | None,
) -> IdentityResolution:
    if resolution.matched_id is None:
        return resolution

    existing = session.get(Scholarship, resolution.matched_id)
    if existing is None:
        return resolution

    new_year = resolution.fingerprint.year_hint
    existing_year = _extract_year_hint(existing.title)

    if new_year is not None and existing_year is not None and new_year != existing_year:
        return IdentityResolution(
            resolution_type=resolution.resolution_type,
            matched_id=resolution.matched_id,
            confidence=resolution.confidence,
            fingerprint=resolution.fingerprint,
            reason=f"{resolution.reason}:new_cycle_year={new_year}",
            cycle_status=CYCLE_NEW,
        )

    norm_new = normalize_title(title)
    norm_existing = normalize_title(existing.title)

    if norm_new and norm_existing and norm_new != norm_existing:
        similarity = _containment_score(norm_new, norm_existing)
        if similarity >= 0.6:
            return IdentityResolution(
                resolution_type=resolution.resolution_type,
                matched_id=resolution.matched_id,
                confidence=resolution.confidence,
                fingerprint=resolution.fingerprint,
                reason=f"{resolution.reason}:renamed",
                cycle_status=CYCLE_RENAMED,
            )
        else:
            return IdentityResolution(
                resolution_type=IDENTITY_REVIEW,
                matched_id=None,
                confidence=similarity,
                fingerprint=resolution.fingerprint,
                reason=f"ambiguous:title_similarity={similarity:.2f}",
                cycle_status=CYCLE_DISTINCT,
            )

    return resolution


def classify_lifecycle_state(
    session: Session,
    scholarship: Scholarship,
    today: date | None = None,
) -> LifecycleState:
    if today is None:
        today = datetime.now(timezone.utc).date()

    deadline_urgency = compute_deadline_urgency(scholarship, today)

    if scholarship.deadline_date is not None:
        deadline = scholarship.deadline_date
        if isinstance(deadline, datetime):
            deadline = deadline.date()
        delta = (deadline - today).days
    else:
        delta = None

    verification_status = scholarship.verification_status or ""
    status = (scholarship.status or "").lower()

    if delta is not None and delta < 0:
        days_past = abs(delta)
        if days_past > ARCHIVED_THRESHOLD_DAYS:
            return _make_state(scholarship, ARCHIVED, "deadline_exceeded_1year", deadline_urgency, True)
        if status != "result_pending":
            return _make_state(scholarship, CLOSED, "deadline_passed", deadline_urgency, False)

    if status in ("closed", "expired", "cancelled"):
        return _make_state(scholarship, CLOSED, f"status_{status}", deadline_urgency, True)

    if status == "archived":
        return _make_state(scholarship, ARCHIVED, "status_archived", deadline_urgency, True)

    if verification_status == "pending":
        return _make_state(scholarship, DISCOVERED, "verification_pending", deadline_urgency, False)

    if status == "result_pending" or verification_status == "result_pending":
        return _make_state(scholarship, RESULT_PENDING, "awaiting_results", deadline_urgency, False)

    if delta is not None and delta <= DEADLINE_NEAR_THRESHOLD_DAYS:
        return _make_state(scholarship, DEADLINE_NEAR, f"deadline_within_{DEADLINE_NEAR_THRESHOLD_DAYS}d", deadline_urgency, False)

    if status == "active" or status == "open":
        if delta is not None:
            return _make_state(scholarship, APPLICATION_OPEN, "application_period_open", deadline_urgency, False)
        return _make_state(scholarship, ACTIVE, "status_active", deadline_urgency, False)

    if delta is not None:
        return _make_state(scholarship, APPLICATION_OPEN, "has_future_deadline", deadline_urgency, False)

    if not scholarship.is_verified:
        return _make_state(scholarship, DISCOVERED, "unverified", deadline_urgency, False)

    return _make_state(scholarship, UNKNOWN, "insufficient_data", deadline_urgency, False)


def _make_state(
    scholarship: Scholarship,
    state: str,
    reason: str,
    deadline_urgency: int,
    is_terminal: bool,
) -> LifecycleState:
    return LifecycleState(
        state=state,
        previous_state=None,
        scholarship_id=scholarship.id,
        reason=reason,
        deadline_urgency=deadline_urgency,
        is_terminal=is_terminal,
    )


def compute_lifecycle_transition(
    session: Session,
    scholarship: Scholarship,
    previous_state: str,
    today: date | None = None,
) -> LifecycleTransition | None:
    new_state = classify_lifecycle_state(session, scholarship, today)

    if new_state.state == previous_state:
        return None

    is_valid = _is_valid_transition(previous_state, new_state.state)
    if not is_valid:
        return None

    return LifecycleTransition(
        scholarship_id=scholarship.id,
        from_state=previous_state,
        to_state=new_state.state,
        reason=new_state.reason,
        triggered_at=datetime.now(timezone.utc),
    )


def _is_valid_transition(from_state: str, to_state: str) -> bool:
    if from_state == to_state:
        return False

    terminal_states = {ARCHIVED}
    if from_state in terminal_states:
        return False

    return True


def get_lifecycle_timestamp_fields(
    scholarship: Scholarship,
) -> dict[str, datetime | None]:
    return {
        "created_at": scholarship.created_at,
        "updated_at": scholarship.updated_at,
        "last_verified_at": _to_datetime(scholarship.last_verified_at),
        "last_verified_date": _to_datetime(scholarship.last_verified_date),
        "next_verification_due": _to_datetime(scholarship.next_verification_due),
    }


def _to_datetime(d: date | datetime | None) -> datetime | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def batch_resolve_identities(
    session: Session,
    candidates: list[dict],
) -> list[IdentityResolution]:
    results = []
    for candidate in candidates:
        resolution = resolve_identity(
            session=session,
            title=candidate.get("title"),
            provider=candidate.get("provider"),
            official_source_url=candidate.get("official_source_url"),
            degree=candidate.get("degree"),
            funding=candidate.get("funding"),
            country=candidate.get("country"),
        )
        resolution = resolve_cycle_status(session, resolution, candidate.get("title"))
        results.append(resolution)
    return results


def batch_classify_lifecycle(
    session: Session,
    scholarships: list[Scholarship],
    today: date | None = None,
) -> list[LifecycleState]:
    return [classify_lifecycle_state(session, s, today) for s in scholarships]


def is_same_program(
    session: Session,
    scholarship_id_1: int,
    scholarship_id_2: int,
) -> bool:
    s1 = session.get(Scholarship, scholarship_id_1)
    s2 = session.get(Scholarship, scholarship_id_2)

    if s1 is None or s2 is None:
        return False

    fp1 = build_fingerprint(
        title=s1.title,
        provider=s1.official_source,
        official_source_url=s1.official_source_url,
        degree=s1.degree,
        funding=s1.funding,
        country=s1.country,
    )
    fp2 = build_fingerprint(
        title=s2.title,
        provider=s2.official_source,
        official_source_url=s2.official_source_url,
        degree=s2.degree,
        funding=s2.funding,
        country=s2.country,
    )

    if fp1.domain and fp2.domain and fp1.domain == fp2.domain and fp1.url_path == fp2.url_path:
        return True

    if fp1.provider and fp2.provider and fp1.provider == fp2.provider:
        if fp1.title and fp2.title:
            similarity = _containment_score(fp1.title, fp2.title)
            if similarity >= 0.6:
                return True

    return False


def get_related_scholarships(
    session: Session,
    scholarship_id: int,
) -> list[int]:
    source = session.get(Scholarship, scholarship_id)
    if source is None:
        return []

    source_fp = build_fingerprint(
        title=source.title,
        provider=source.official_source,
        official_source_url=source.official_source_url,
        degree=source.degree,
        funding=source.funding,
        country=source.country,
    )

    if not source_fp.domain and not source_fp.provider:
        return []

    query = select(Scholarship).where(Scholarship.id != scholarship_id)

    conditions = []
    if source_fp.domain:
        conditions.append(
            func.lower(Scholarship.official_source_url).like(f"%{source_fp.domain}%")
        )
    if source_fp.provider:
        conditions.append(
            func.lower(Scholarship.official_source).like(f"%{source_fp.provider}%")
        )

    if conditions:
        query = query.where(or_(*conditions))

    candidates = session.scalars(query).all()

    related: list[int] = []
    for s in candidates:
        s_fp = build_fingerprint(
            title=s.title,
            provider=s.official_source,
            official_source_url=s.official_source_url,
            degree=s.degree,
            funding=s.funding,
            country=s.country,
        )

        score = _fingerprint_similarity(source_fp, s_fp)
        if score >= 0.40:
            related.append(s.id)

    return related
