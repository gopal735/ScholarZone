"""Identity resolution, URL normalization, and duplicate detection for discovery."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import DiscoveryCandidate, Scholarship


_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")
_SUFFIX_RE = re.compile(r"\s*[-|(]\s*(?:scholarship|program|programme|fellowship|grant|award).*$", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


@dataclass(frozen=True)
class MatchResult:
    is_match: bool
    match_type: str
    matched_id: int | None = None
    confidence: float = 0.0


def normalize_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip().rstrip("/")
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            host, port = netloc.rsplit(":", 1)
            if (scheme == "https" and port == "443") or (scheme == "http" and port == "80"):
                netloc = host
        path = parsed.path.rstrip("/") or "/"
        return urlunparse((scheme, netloc, path, "", "", ""))
    except Exception:
        return url


def normalize_title(title: str | None) -> str:
    if not title:
        return ""
    t = unicodedata.normalize("NFKD", title)
    t = t.encode("ascii", "ignore").decode("ascii")
    t = t.lower().strip()
    t = _SUFFIX_RE.sub("", t)
    t = _NON_ALNUM_RE.sub("", t)
    return t


def normalize_provider(provider: str | None) -> str:
    if not provider:
        return ""
    p = unicodedata.normalize("NFKD", provider)
    p = p.encode("ascii", "ignore").decode("ascii")
    p = p.lower().strip()
    p = _WHITESPACE_RE.sub(" ", p)
    p = _NON_ALNUM_RE.sub("", p)
    return p


def compute_discovery_hash(normalized_url: str, title: str | None, provider: str | None) -> str:
    url_part = normalize_url(normalized_url)
    title_part = normalize_title(title)
    provider_part = normalize_provider(provider)
    raw = f"{url_part}||{title_part}||{provider_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_exact_url_match(session: Session, url: str) -> Scholarship | None:
    normalized = normalize_url(url)
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


def find_exact_candidate_match(session: Session, discovery_hash: str) -> DiscoveryCandidate | None:
    return session.scalar(
        select(DiscoveryCandidate).where(DiscoveryCandidate.discovery_hash == discovery_hash)
    )


def find_near_duplicate(session: Session, title: str | None, provider: str | None, country: str | None) -> Scholarship | None:
    norm_title = normalize_title(title)
    if not norm_title or len(norm_title) < 8:
        return None

    candidates = session.scalars(
        select(Scholarship).where(
            Scholarship.country == country if country else Scholarship.country.is_(None)
        )
    ).all()

    best_match: Scholarship | None = None
    best_score: float = 0.0

    for s in candidates:
        s_title = normalize_title(s.title)
        if not s_title:
            continue
        if s_title == norm_title:
            return s
        containment = _containment_score(norm_title, s_title)
        if containment > best_score:
            best_score = containment
            best_match = s

    if best_score >= 0.85:
        return best_match

    norm_provider = normalize_provider(provider)
    if norm_provider and len(norm_provider) > 4:
        for s in candidates:
            s_provider = normalize_provider(s.official_source)
            if s_provider and (norm_provider == s_provider or _containment_score(norm_provider, s_provider) >= 0.9):
                title_overlap = _containment_score(norm_title, normalize_title(s.title))
                if title_overlap >= 0.5:
                    return s

    return None


def _containment_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    if shorter in longer:
        return len(shorter) / len(longer)
    a_tokens = set(a[i:i + 4] for i in range(len(a) - 3))
    b_tokens = set(b[i:i + 4] for i in range(len(b) - 3))
    if not a_tokens or not b_tokens:
        return 0.0
    overlap = len(a_tokens & b_tokens)
    return overlap / max(len(a_tokens), len(b_tokens))


def resolve_identity(
    session: Session,
    source_url: str,
    title: str | None,
    provider: str | None,
    country: str | None,
) -> MatchResult:
    existing = find_exact_url_match(session, source_url)
    if existing is not None:
        return MatchResult(is_match=True, match_type="exact_url", matched_id=existing.id, confidence=1.0)

    discovery_hash = compute_discovery_hash(source_url, title, provider)
    candidate = find_exact_candidate_match(session, discovery_hash)
    if candidate is not None and candidate.status in ("pending", "approved"):
        return MatchResult(is_match=True, match_type="exact_candidate", matched_id=candidate.matched_scholarship_id, confidence=1.0)

    near = find_near_duplicate(session, title, provider, country)
    if near is not None:
        return MatchResult(is_match=True, match_type="near_duplicate", matched_id=near.id, confidence=0.9)

    if title and provider:
        alias = _resolve_alias(session, title, provider, country)
        if alias is not None:
            return MatchResult(is_match=True, match_type="alias", matched_id=alias.id, confidence=0.85)

    return MatchResult(is_match=False, match_type="unmatched", confidence=0.0)


def _resolve_alias(session: Session, title: str, provider: str, country: str | None) -> Scholarship | None:
    norm_title = normalize_title(title)
    norm_provider = normalize_provider(provider)
    if not norm_title or not norm_provider:
        return None

    candidates = session.scalars(
        select(Scholarship).where(Scholarship.country == country if country else Scholarship.country.is_(None))
    ).all()

    for s in candidates:
        s_title = normalize_title(s.title)
        s_provider = normalize_provider(s.official_source)
        if not s_title or not s_provider:
            continue
        provider_match = norm_provider == s_provider or _containment_score(norm_provider, s_provider) >= 0.9
        title_similar = _containment_score(norm_title, s_title) >= 0.6
        if provider_match and title_similar:
            return s

    return None


def extract_years(text: str | None) -> list[int]:
    if not text:
        return []
    return [int(m) for m in _YEAR_RE.findall(text)]
