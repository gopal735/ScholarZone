"""Deterministic catalogue discovery for the AI Mentor."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ...models import Scholarship
from ...repositories.scholarships import public_visibility_conditions
from ...schemas_mentor import EvidenceResponse
from .evidence import EvidenceItem, BASIS_CATALOGUE
from .guards import bound_text
from .normalization import normalize_query

EUROPE_COUNTRIES: frozenset[str] = frozenset(
    {
        "Austria","Belgium","Bulgaria","Cyprus","Czech Republic","Denmark","Estonia",
        "Finland","France","Germany","Greece","Hungary","Iceland","Ireland","Italy",
        "Latvia","Lithuania","Luxembourg","Malta","Netherlands","Norway","Poland",
        "Portugal","Romania","Serbia","Slovakia","Slovenia","Spain","Sweden",
        "Switzerland","Turkey","United Kingdom","Europe","EU (multiple)",
    }
)

_DEGREE_PATTERNS = re.compile(r"\b(ph\.?d|doctoral|doctorate)\b", re.IGNORECASE)
_STIPEND_PATTERNS = re.compile(r"\b(stipend|living allowance|maintenance allowance|subsistence allowance|living expenses|research stipend|monthly (stipend|allowance|grant))\b", re.IGNORECASE)
_NO_STIPEND_PATTERNS = re.compile(r"\b(tuition only|tuition-only|no stipend|stipend not (provided|included|offered))\b", re.IGNORECASE)
_EUROPE_ALIASES = ("europe", "european")


def _contains_any(text, terms):
    low = (text or "").lower()
    return any(str(t).lower() in low for t in terms)


def extract_slots(message: str) -> dict[str, Any]:
    nq = normalize_query(message or "")
    norm = nq["normalized_query"]
    original = message or ""
    degree = None
    if _DEGREE_PATTERNS.search(original) or _contains_any(original, ["\u09aa\u09bf\u098f\u0987\u099a\u09a1\u09bf", "\u09a1\u0995\u09cd\u099f\u09b0\u09c7\u099f"]) or _contains_any(norm, ["phd", "doctoral", "doctorate"]):
        degree = "phd"
    elif _contains_any(norm, ["master", "masters", "msc"]) or _contains_any(original, ["\u09ae\u09be\u09b8\u09cd\u099f\u09be\u09b0\u09cd\u09b8", "\u09ae\u09be\u09b8\u09cd\u099f\u09be\u09b0"]):
        degree = "masters"
    elif _contains_any(norm, ["bachelor", "undergraduate", "bsc"]) or _contains_any(original, ["\u09ac\u09cd\u09af\u09be\u099a\u09c7\u09b2\u09b0"]):
        degree = "bachelors"
    region = None
    if _contains_any(norm, ["europe", "european"]) or "europe" in norm or _contains_any(original, ["\u0987\u0989\u09b0\u09cb\u09aa"]):
        region = "europe"
    if _contains_any(norm, ["germany", "jarmani", "deutschland"]) or _contains_any(original, ["\u099c\u09be\u09b0\u09cd\u09ae\u09be\u09a8\u09bf"]):
        region = "germany"
    funding = None
    if _STIPEND_PATTERNS.search(original) or _contains_any(original, ["\u09ad\u09be\u09a4\u09be", "\u09b8\u09cd\u099f\u09be\u0987\u09aa\u09c7\u09a8\u09cd\u09a1", "\u09ae\u09be\u09b8\u09bf\u0995"]) or _contains_any(norm, ["stipend", "living allowance", "maintenance"]):
        funding = "stipend"
    return {
        "degree_level": {"value": degree, "source": "explicit_query" if degree else None},
        "region": {"value": region, "source": "explicit_query" if region else None},
        "funding_intent": {"value": funding, "source": "explicit_query" if funding else None},
    }


def classify_funding(row: Scholarship) -> tuple[str, str | None, str | None]:
    funding_text = " ".join(
        str(x) for x in [row.funding, " ".join(row.benefits or []), " ".join(row.coverage or [])]
        if x
    )
    if not funding_text.strip() or str(row.funding or "").strip().upper() == "UNKNOWN":
        return "FUNDING_UNVERIFIED", "Funding information is missing or unverified.", "funding"
    if _NO_STIPEND_PATTERNS.search(funding_text):
        return "STIPEND_EXPLICITLY_EXCLUDED", "Source states tuition-only or no stipend.", "funding"
    if _STIPEND_PATTERNS.search(funding_text):
        return "STIPEND_TEXT_CANDIDATE", "Stipend/living allowance mentioned in funding/benefits text.", "funding"
    return "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR", "Funding support described without explicit stipend evidence.", "funding"


@dataclass
class DiscoveryMatch:
    scholarship_id: int
    title: str
    country: str
    degree: str | None
    funding_classification: str
    funding_text: str | None
    official_source_url: str | None
    verification: str | None
    knowledge_state: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    query_summary: dict[str, Any]
    search_status: str
    verified_matches: list[DiscoveryMatch] = field(default_factory=list)
    potential_matches: list[DiscoveryMatch] = field(default_factory=list)
    diagnostics: dict[str, int] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)


def _match_from_row(row: Scholarship, classification: str, reason: str) -> DiscoveryMatch:
    warnings: list[str] = []
    if classification == "STIPEND_TEXT_CANDIDATE":
        warnings.append("Stipend mention found, but it has not been independently verified.")
    elif classification == "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR":
        warnings.append("Funding is described, but stipend evidence is not established.")
    elif classification == "FUNDING_UNVERIFIED":
        warnings.append("Funding information is unverified.")
    return DiscoveryMatch(
        scholarship_id=row.id,
        title=row.title,
        country=row.country,
        degree=row.degree,
        funding_classification=classification,
        funding_text=bound_text(row.funding, 200) if row.funding else None,
        official_source_url=row.official_source_url,
        verification=row.verification_status,
        knowledge_state="record_level_source_only",
        warnings=warnings,
    )


def run_discovery(db: Session, message: str, as_of: date | None = None, limit: int = 50, offset: int = 0) -> DiscoveryResult:
    slots = extract_slots(message)
    degree_val = (slots["degree_level"] or {}).get("value")
    region_val = (slots["region"] or {}).get("value")
    funding_val = (slots["funding_intent"] or {}).get("value")

    query_summary = {
        "degree_level": degree_val,
        "region": region_val,
        "funding_intent": funding_val,
    }

    public_conditions = list(public_visibility_conditions())
    public_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*public_conditions)
    ) or 0

    conditions = list(public_conditions)
    if degree_val == "phd":
        conditions.append(
            or_(
                Scholarship.degree.ilike("%phd%"),
                Scholarship.degree.ilike("%ph.d%"),
                Scholarship.degree.ilike("%doctoral%"),
                Scholarship.degree.ilike("%doctorate%"),
            )
        )
    elif degree_val == "masters":
        conditions.append(
            or_(
                Scholarship.degree.ilike("%master%"),
                Scholarship.degree.ilike("%msc%"),
            )
        )
    elif degree_val == "bachelors":
        conditions.append(
            or_(
                Scholarship.degree.ilike("%bachelor%"),
                Scholarship.degree.ilike("%undergraduate%"),
            )
        )
    degree_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*conditions)
    ) or 0

    region_conditions = list(conditions)
    if region_val == "europe":
        region_conditions.append(Scholarship.country.in_(tuple(EUROPE_COUNTRIES)))
    elif region_val and region_val != "europe":
        region_conditions.append(func.lower(Scholarship.country) == region_val.casefold())

    region_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*region_conditions)
    ) or 0

    excluded_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(
            *region_conditions,
            or_(
                Scholarship.funding.ilike("%tuition only%"),
                Scholarship.funding.ilike("%tuition-only%"),
                Scholarship.funding.ilike("%no stipend%"),
            ),
        )
    ) or 0

    stipend_like_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(
            *region_conditions,
            or_(
                Scholarship.funding.ilike("%stipend%"),
                Scholarship.funding.ilike("%living allowance%"),
                Scholarship.funding.ilike("%maintenance allowance%"),
                Scholarship.funding.ilike("%subsistence%"),
                Scholarship.funding.ilike("%living expenses%"),
            ),
        )
    ) or 0

    unverified_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(
            *region_conditions,
            or_(
                Scholarship.funding.is_(None),
                func.trim(Scholarship.funding) == "",
                func.upper(Scholarship.funding) == "UNKNOWN",
            ),
        )
    ) or 0

    stipend_text_candidates_count = max(0, stipend_like_count - excluded_count)
    funding_support_unclear_count = max(0, region_count - excluded_count - stipend_text_candidates_count - unverified_count)

    counts = {
        "public_candidates": int(public_count),
        "degree_candidates": int(degree_count),
        "region_candidates": int(region_count),
        "stipend_confirmed": 0,
        "stipend_text_candidates": int(stipend_text_candidates_count),
        "funding_support_unclear": int(funding_support_unclear_count),
        "funding_unverified": int(unverified_count),
        "explicit_stipend_excluded": int(excluded_count),
    }

    region_rows = list(
        db.execute(
            select(Scholarship)
            .where(*region_conditions)
            .order_by(Scholarship.id.asc())
            .offset(offset)
            .limit(limit)
        ).scalars()
    )

    potential: list[DiscoveryMatch] = []
    evidence: list[EvidenceItem] = []
    for row in region_rows:
        classification, reason, _ = classify_funding(row)
        if classification == "STIPEND_EXPLICITLY_EXCLUDED":
            continue
        match = _match_from_row(row, classification, reason)
        potential.append(match)
        evidence.append(
            EvidenceItem(
                key=f"scholarship-{row.id}-discovery",
                label="Scholarship",
                value=bound_text(f"{row.title} (record {row.id})"),
                field="scholarship.title",
                basis=BASIS_CATALOGUE,
                verification=row.verification_status,
                source_url=row.official_source_url,
                scholarship_id=row.id,
            )
        )

    if public_count == 0:
        status = "NO_PUBLIC_CANDIDATES"
    elif degree_val and degree_count == 0:
        status = "NO_DEGREE_MATCHES"
    elif region_count == 0:
        status = "NO_REGION_MATCHES"
    elif counts["stipend_text_candidates"] > 0 or counts["funding_support_unclear"] > 0:
        status = "POTENTIAL_MATCHES_FOUND"
    else:
        status = "NO_VERIFIED_STIPEND_MATCHES"

    return DiscoveryResult(
        query_summary=query_summary,
        search_status=status,
        verified_matches=[],
        potential_matches=potential,
        diagnostics=counts,
        evidence=evidence,
    )
