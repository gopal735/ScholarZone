"""Deterministic catalogue discovery for the AI Mentor.

This module is the single place where a scholarship-discovery question becomes a
canonical public-catalogue search. It reuses the existing visibility predicate
and existing indexed columns; it does not fetch the whole catalogue and does not
depend on any provider.
"""

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

# Reviewed European country set (matches the prior Stage A audit).
# Russia and Kazakhstan are deliberately excluded.
EUROPE_COUNTRIES: frozenset[str] = frozenset(
    {
        "Austria",
        "Belgium",
        "Bulgaria",
        "Cyprus",
        "Czech Republic",
        "Denmark",
        "Estonia",
        "Finland",
        "France",
        "Germany",
        "Greece",
        "Hungary",
        "Iceland",
        "Ireland",
        "Italy",
        "Latvia",
        "Lithuania",
        "Luxembourg",
        "Malta",
        "Netherlands",
        "Norway",
        "Poland",
        "Portugal",
        "Romania",
        "Serbia",
        "Slovakia",
        "Slovenia",
        "Spain",
        "Sweden",
        "Switzerland",
        "Turkey",
        "United Kingdom",
        "Europe",
        "EU (multiple)",
    }
)

_DEGREE_PATTERNS = re.compile(
    r"\b(ph\.?d|doctoral|doctorate|doctoral degree|doctoral programme|doctoral program)\b",
    re.IGNORECASE,
)
_DEGREE_ALIASES_BN = ("পিএইচডি", "ডক্টরেট")

_STIPEND_PATTERNS = re.compile(
    r"\b(stipend|living allowance|maintenance allowance|subsistence allowance|"
    r"living expenses|research stipend|monthly (stipend|allowance|grant))\b",
    re.IGNORECASE,
)
_STIPEND_ALIASES_BN = ("স্টাইপেন্ড", "মাসিক ভাতা", "ভাতা")

_NO_STIPEND_PATTERNS = re.compile(
    r"\b(tuition only|tuition-only|no stipend|stipend not (provided|included|offered))\b",
    re.IGNORECASE,
)

_EUROPE_ALIASES = ("europe", "ইউরোপ", "european")


def extract_slots(message: str) -> dict[str, Any]:
    lowered = (message or "").lower()
    degree = None
    if _DEGREE_PATTERNS.search(message or "") or any(a in (message or "") for a in _DEGREE_ALIASES_BN):
        degree = "phd"
    region = None
    if any(a in lowered for a in _EUROPE_ALIASES) or "europe" in lowered:
        region = "europe"
    # Banglish/geographic hints
    if "germany" in lowered:
        region = "germany"  # single-country override when explicit
    funding = None
    if _STIPEND_PATTERNS.search(message or "") or any(a in (message or "") for a in _STIPEND_ALIASES_BN):
        funding = "stipend"
    return {
        "degree_level": {"value": degree, "source": "explicit_query" if degree else None},
        "region": {"value": region, "source": "explicit_query" if region else None},
        "funding_intent": {"value": funding, "source": "explicit_query" if funding else None},
    }


def classify_funding(row: Scholarship) -> tuple[str, str | None]:
    text = " ".join(
        str(x) for x in [
            row.funding,
            " ".join(row.benefits or []),
            " ".join(row.coverage or []),
            " ".join(row.requirements or []),
            row.eligibility_summary,
            row.description,
        ]
        if x
    )
    if _NO_STIPEND_PATTERNS.search(text):
        return "STIPEND_EXPLICITLY_EXCLUDED", "Source states tuition-only or no stipend."
    if _STIPEND_PATTERNS.search(text):
        return "STIPEND_TEXT_CANDIDATE", "Stipend/living allowance mentioned in source text."
    if not row.funding or str(row.funding).strip().upper() == "UNKNOWN":
        return "FUNDING_UNVERIFIED", "Funding information is missing or unverified."
    return "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR", "Funding support described without explicit stipend evidence."


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
        warnings.append(
            "Stipend-এর উল্লেখ পাওয়া গেছে, তবে তথ্যটি আলাদাভাবে যাচাই করা হয়নি।"
        )
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


def run_discovery(db: Session, message: str, as_of: date | None = None) -> DiscoveryResult:
    slots = extract_slots(message)
    degree_val = (slots["degree_level"] or {}).get("value")
    region_val = (slots["region"] or {}).get("value")
    funding_val = (slots["funding_intent"] or {}).get("value")

    query_summary = {
        "degree_level": degree_val,
        "region": region_val,
        "funding_intent": funding_val,
    }

    # Public candidate count (no degree/region filter).
    public_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*public_visibility_conditions())
    ) or 0

    conditions = list(public_visibility_conditions())
    if degree_val == "phd":
        conditions.append(
            or_(
                Scholarship.degree.ilike("%phd%"),
                Scholarship.degree.ilike("%ph.d%"),
                Scholarship.degree.ilike("%doctoral%"),
                Scholarship.degree.ilike("%doctorate%"),
            )
        )
    degree_count_query = select(func.count()).select_from(Scholarship).where(*conditions)
    degree_count = db.scalar(degree_count_query) or 0

    region_conditions = list(conditions)
    if region_val == "europe":
        region_conditions.append(Scholarship.country.in_(tuple(EUROPE_COUNTRIES)))
    elif region_val and region_val != "europe":
        region_conditions.append(func.lower(Scholarship.country) == region_val.casefold())

    region_rows = list(
        db.execute(
            select(Scholarship)
            .where(*region_conditions)
            .order_by(Scholarship.id.asc())
            .limit(50)
        ).scalars()
    )
    region_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*region_conditions)
    ) or 0

    # Classify funding.
    counts = {
        "public_candidates": int(public_count),
        "degree_candidates": int(degree_count),
        "region_candidates": int(region_count),
        "stipend_confirmed": 0,
        "stipend_text_candidates": 0,
        "funding_support_unclear": 0,
        "funding_unverified": 0,
        "explicit_stipend_excluded": 0,
    }

    potential: list[DiscoveryMatch] = []
    evidence: list[EvidenceItem] = []
    for row in region_rows:
        classification, reason = classify_funding(row)
        if classification == "STIPEND_TEXT_CANDIDATE":
            counts["stipend_text_candidates"] += 1
        elif classification == "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR":
            counts["funding_support_unclear"] += 1
        elif classification == "FUNDING_UNVERIFIED":
            counts["funding_unverified"] += 1
        elif classification == "STIPEND_EXPLICITLY_EXCLUDED":
            counts["explicit_stipend_excluded"] += 1

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

    # Determine search status.
    if public_count == 0:
        status = "NO_PUBLIC_CANDIDATES"
    elif degree_val == "phd" and degree_count == 0:
        status = "NO_DEGREE_MATCHES"
    elif region_count == 0:
        status = "NO_REGION_MATCHES"
    elif counts["stipend_text_candidates"] > 0:
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
