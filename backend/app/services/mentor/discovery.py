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
from .countries import extract_country_from_message

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
_NO_STIPEND_PATTERNS = re.compile(r"\b(tuition only|tuition-only|no (monthly )?stipend|no living allowance|stipend not (provided|included|offered)|stipend is not (provided|included|offered)|does not include (a )?stipend|living costs are not covered)\b", re.IGNORECASE)


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
    country = extract_country_from_message(original)
    if country is not None and country not in ("International", "Multiple"):
        region = country
    funding = None
    if _STIPEND_PATTERNS.search(original) or _contains_any(original, ["\u09ad\u09be\u09a4\u09be", "\u09b8\u09cd\u099f\u09be\u0987\u09aa\u09c7\u09a8\u09cd\u09a1", "\u09ae\u09be\u09b8\u09bf\u0995"]) or _contains_any(norm, ["stipend", "living allowance", "maintenance"]):
        funding = "stipend"
    return {
        "degree_level": {"value": degree, "source": "explicit_query" if degree else None},
        "region": {"value": region, "source": "explicit_query" if region else None},
        "funding_intent": {"value": funding, "source": "explicit_query" if funding else None},
    }


def classify_funding(row: Scholarship) -> tuple[str, str | None, list[str]]:
    # Determine which fields contain the evidence.
    supporting: list[str] = []
    if row.funding and str(row.funding).strip() and str(row.funding).strip().upper() != "UNKNOWN":
        supporting.append("funding")
    if row.benefits:
        bt = " ".join(str(x) for x in row.benefits)
        if _STIPEND_PATTERNS.search(bt) or _NO_STIPEND_PATTERNS.search(bt):
            supporting.append("benefits")
    if row.coverage:
        ct = " ".join(str(x) for x in row.coverage)
        if _STIPEND_PATTERNS.search(ct) or _NO_STIPEND_PATTERNS.search(ct):
            supporting.append("coverage")
    # Build combined text for pattern matching.
    funding_text = " ".join(
        str(x) for x in [row.funding, " ".join(row.benefits or []), " ".join(row.coverage or [])]
        if x
    )
    if not funding_text.strip():
        return "FUNDING_UNVERIFIED", "Funding information is missing or unverified.", []
    if funding_text.strip().upper() == "UNKNOWN":
        return "FUNDING_UNVERIFIED", "Funding information is missing or unverified.", []
    # Conflicting evidence: positive in one field, negative in another.
    pos = bool(_STIPEND_PATTERNS.search(funding_text))
    neg = bool(_NO_STIPEND_PATTERNS.search(funding_text))
    if pos and neg:
        # Determine if conflict is across fields.
        return "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR", "Conflicting stipend evidence across fields.", supporting
    if neg:
        return "STIPEND_EXPLICITLY_EXCLUDED", "Source states tuition-only or no stipend.", supporting
    if pos:
        return "STIPEND_TEXT_CANDIDATE", "Stipend/living allowance mentioned in funding/benefits text.", supporting
    return "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR", "Funding support described without explicit stipend evidence.", supporting


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
    supporting_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DiscoveryResult:
    query_summary: dict[str, Any]
    search_status: str
    verified_matches: list[DiscoveryMatch] = field(default_factory=list)
    potential_matches: list[DiscoveryMatch] = field(default_factory=list)
    diagnostics: dict[str, int] = field(default_factory=dict)
    evidence: list[EvidenceItem] = field(default_factory=list)


def _match_from_row(row: Scholarship, classification: str, reason: str, supporting_fields=None) -> DiscoveryMatch:
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
        supporting_fields=list(supporting_fields or []),
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
        region_conditions.append(func.lower(Scholarship.country) == str(region_val).casefold())

    region_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*region_conditions)
    ) or 0

    # Batched classification across full population for parity.
    batch_size = 500
    boff = 0
    excluded_count = 0
    stipend_text_candidates_count = 0
    funding_support_unclear_count = 0
    unverified_count = 0
    eligible_ids: list[int] = []
    while True:
        batch = list(
            db.execute(
                select(Scholarship)
                .where(*region_conditions)
                .order_by(Scholarship.id.asc())
                .offset(boff)
                .limit(batch_size)
            ).scalars()
        )
        if not batch:
            break
        for row in batch:
            cls, _, _ = classify_funding(row)
            if cls == "STIPEND_EXPLICITLY_EXCLUDED":
                excluded_count += 1
                # Only exclude from candidate list when the user explicitly asked for stipend.
                if funding_val != "stipend":
                    eligible_ids.append(row.id)
            elif cls == "STIPEND_TEXT_CANDIDATE":
                stipend_text_candidates_count += 1
                eligible_ids.append(row.id)
            elif cls == "FUNDING_UNVERIFIED":
                unverified_count += 1
                eligible_ids.append(row.id)
            elif cls == "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR":
                funding_support_unclear_count += 1
                eligible_ids.append(row.id)
        boff += batch_size

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

    # Paginate eligible (non-excluded) population.
    page_ids = eligible_ids[offset:offset + limit]
    if page_ids:
        rows_by_id = {
            r.id: r for r in db.execute(
                select(Scholarship).where(Scholarship.id.in_(page_ids))
            ).scalars()
        }
        region_rows = [rows_by_id[i] for i in page_ids if i in rows_by_id]
    else:
        region_rows = []

    potential: list[DiscoveryMatch] = []
    evidence: list[EvidenceItem] = []
    for row in region_rows:
        classification, reason, supporting = classify_funding(row)
        if classification == "STIPEND_EXPLICITLY_EXCLUDED":
            continue
        match = _match_from_row(row, classification, reason, supporting)
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
