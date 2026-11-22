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
from .countries import extract_country_from_message, resolve_country_resolution

EUROPE_COUNTRIES: frozenset[str] = frozenset(
    {
        "Austria","Belgium","Bulgaria","Cyprus","Czech Republic","Denmark","Estonia",
        "Finland","France","Germany","Greece","Hungary","Iceland","Ireland","Italy",
        "Latvia","Lithuania","Luxembourg","Malta","Netherlands","Norway","Poland",
        "Portugal","Romania","Serbia","Slovakia","Slovenia","Spain","Sweden",
        "Switzerland","Turkey","United Kingdom","Europe","EU (multiple)",
    }
)

EU_COUNTRIES: frozenset[str] = frozenset(
    {
        "Austria","Belgium","Bulgaria","Cyprus","Czech Republic","Denmark","Estonia",
        "Finland","France","Germany","Greece","Hungary","Ireland","Italy","Latvia",
        "Lithuania","Luxembourg","Malta","Netherlands","Poland","Portugal","Romania",
        "Slovakia","Slovenia","Spain","Sweden",
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
    if re.search(r"\b(eu|european union)\b", original or "", re.IGNORECASE):
        region = "eu"
    elif _contains_any(norm, ["europe", "european"]) or "europe" in norm or _contains_any(original, ["\u0987\u0989\u09b0\u09cb\u09aa"]):
        region = "europe"
    country_resolution = resolve_country_resolution(original)
    country = country_resolution["country"] if country_resolution["status"] == "RESOLVED_SUPPORTED" else None
    if country is not None and country not in ("International", "Multiple"):
        region = country
    funding = None
    if _STIPEND_PATTERNS.search(original) or _contains_any(original, ["\u09ad\u09be\u09a4\u09be", "\u09b8\u09cd\u099f\u09be\u0987\u09aa\u09c7\u09a8\u09cd\u09a1", "\u09ae\u09be\u09b8\u09bf\u0995"]) or _contains_any(norm, ["stipend", "living allowance", "maintenance"]):
        funding = "stipend"
    return {
        "degree_level": {"value": degree, "source": "explicit_query" if degree else None},
        "region": {"value": region, "source": "explicit_query" if region else None},
        "funding_intent": {"value": funding, "source": "explicit_query" if funding else None},
        "country_resolution": country_resolution,
    }


def _field_polarity(text: str) -> str | None:
    """Return 'positive','negative','conflict','none', or None for unknown/empty."""
    t = (text or "").strip()
    if not t or t.upper() == "UNKNOWN":
        return None
    neg_matches = list(_NO_STIPEND_PATTERNS.finditer(t))
    remaining = t
    for m in sorted(neg_matches, key=lambda x: -x.start()):
        remaining = remaining[:m.start()] + " " + remaining[m.end():]
    pos_in_remaining = bool(_STIPEND_PATTERNS.search(remaining))
    neg = bool(neg_matches)
    pos_overall = bool(_STIPEND_PATTERNS.search(t))
    if neg and pos_in_remaining:
        return "conflict"
    if neg:
        return "negative"
    if pos_overall:
        return "positive"
    return "none"


def classify_funding(row: Scholarship) -> tuple[str, str | None, list[str]]:
    funding_str = str(row.funding).strip() if row.funding is not None else ""
    benefits_text = " ".join(str(x) for x in (row.benefits or []))
    coverage_text = " ".join(str(x) for x in (row.coverage or []))

    polarities = {
        "funding": _field_polarity(funding_str),
        "benefits": _field_polarity(benefits_text),
        "coverage": _field_polarity(coverage_text),
    }

    evidence_fields = [f for f in ("funding", "benefits", "coverage") if polarities[f] in ("positive", "negative", "conflict")]
    positives = [f for f in evidence_fields if polarities[f] == "positive"]
    negatives = [f for f in evidence_fields if polarities[f] == "negative"]
    conflicts = [f for f in evidence_fields if polarities[f] == "conflict"]

    if conflicts:
        return "FUNDING_EVIDENCE_CONFLICT", "Conflicting stipend evidence within a field.", evidence_fields
    if positives and negatives:
        return "FUNDING_EVIDENCE_CONFLICT", "Conflicting stipend evidence across fields.", evidence_fields
    if negatives and not positives:
        return "STIPEND_EXPLICITLY_EXCLUDED", "Source states tuition-only or no stipend.", evidence_fields
    if positives and not negatives:
        return "STIPEND_TEXT_CANDIDATE", "Stipend/living allowance mentioned in funding/benefits text.", evidence_fields

    # No stipend polarity evidence. Is there any funding support described?
    support_fields = [f for f in ("funding", "benefits", "coverage")
                      if (f == "funding" and funding_str and funding_str.upper() != "UNKNOWN")
                      or (f == "benefits" and benefits_text.strip() and benefits_text.strip().upper() != "UNKNOWN")
                      or (f == "coverage" and coverage_text.strip() and coverage_text.strip().upper() != "UNKNOWN")]
    # But only count as support if not all unknown/empty
    any_text = (bool(funding_str and funding_str.upper() != "UNKNOWN")
                or (benefits_text.strip() != "" and benefits_text.strip().upper() != "UNKNOWN")
                or (coverage_text.strip() != "" and coverage_text.strip().upper() != "UNKNOWN"))
    if not any_text:
        return "FUNDING_UNVERIFIED", "Funding information is missing or unverified.", []
    return "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR", "Funding support described without explicit stipend evidence.", support_fields


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
    elif classification == "FUNDING_EVIDENCE_CONFLICT":
        warnings.append("Funding evidence conflicts across source fields; treat as uncertain.")
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
    country_resolution = slots.get("country_resolution") or {}
    country_status = country_resolution.get("status", "NOT_PROVIDED")

    query_summary = {
        "degree_level": degree_val,
        "region": region_val,
        "funding_intent": funding_val,
        "country_status": country_status,
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
                Scholarship.degree.ilike("%bsc%"),
            )
        )

    degree_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*conditions)
    ) or 0

    region_conditions = list(conditions)
    if region_val == "europe":
        region_conditions.append(Scholarship.country.in_(tuple(EUROPE_COUNTRIES)))
    elif region_val == "eu":
        region_conditions.append(Scholarship.country.in_(tuple(EU_COUNTRIES)))
    elif region_val and region_val not in ("europe", "eu"):
        region_conditions.append(func.lower(Scholarship.country) == str(region_val).casefold())

    region_count = db.scalar(
        select(func.count()).select_from(Scholarship).where(*region_conditions)
    ) or 0

    # Batched classification across full population for parity.
    batch_size = 500
    boff = 0
    excluded_count = 0
    stipend_text_candidates_count = 0
    stipend_text_candidate_ids: list[int] = []
    funding_support_unclear_count = 0
    unverified_count = 0
    funding_evidence_conflict_count = 0
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
                stipend_text_candidate_ids.append(row.id)
                eligible_ids.append(row.id)
            elif cls == "FUNDING_UNVERIFIED":
                unverified_count += 1
                eligible_ids.append(row.id)
            elif cls == "FUNDING_SUPPORT_CONFIRMED_STIPEND_UNCLEAR":
                funding_support_unclear_count += 1
                eligible_ids.append(row.id)
            elif cls == "FUNDING_EVIDENCE_CONFLICT":
                funding_evidence_conflict_count += 1
                # Keep as potential/uncertain; never verified. Exclude only if
                # the user explicitly asked for a confirmed stipend? Keep visible.
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
        "funding_evidence_conflict": int(funding_evidence_conflict_count),
    }

    # For stipend searches, rank stipend-text candidates ahead of records
    # without stipend evidence so the first page is useful. Generic searches
    # keep the existing (id-ordered) candidate order.
    if funding_val == "stipend" and stipend_text_candidate_ids:
        candidate_set = set(stipend_text_candidate_ids)
        eligible_ids = [i for i in eligible_ids if i in candidate_set] + [i for i in eligible_ids if i not in candidate_set]

    # Paginate eligible (non-excluded) population.
    page_ids = eligible_ids[offset:offset + limit]
    if page_ids:
        rows_by_id = {
            r.id: r for r in db.execute(
                select(Scholarship).where(
                    Scholarship.id.in_(page_ids),
                    *public_visibility_conditions(),
                )
            ).scalars()
        }
        region_rows = [rows_by_id[i] for i in page_ids if i in rows_by_id]
    else:
        region_rows = []

    potential: list[DiscoveryMatch] = []
    evidence: list[EvidenceItem] = []
    for row in region_rows:
        classification, reason, supporting = classify_funding(row)
        # Only exclude explicit no-stipend records when the user explicitly
        # asked for a stipend. Generic discovery keeps them (with correct
        # funding classification).
        if classification == "STIPEND_EXPLICITLY_EXCLUDED" and funding_val == "stipend":
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
    elif country_status == "RESOLVED_NO_CATALOGUE_DATA":
        status = "UNSUPPORTED_FILTER"
    elif country_status == "AMBIGUOUS_FILTER":
        status = "AMBIGUOUS_FILTER"
    elif degree_val and degree_count == 0:
        status = "NO_DEGREE_MATCHES"
    elif region_val and region_count == 0:
        status = "NO_REGION_MATCHES"
    elif funding_val == "stipend":
        if (counts["stipend_text_candidates"] > 0 or counts["funding_support_unclear"] > 0
                or counts["funding_evidence_conflict"] > 0):
            status = "POTENTIAL_MATCHES_FOUND"
        else:
            status = "NO_VERIFIED_STIPEND_MATCHES"
    else:
        # Generic discovery: any region candidate is a match.
        if region_count > 0:
            status = "POTENTIAL_MATCHES_FOUND"
        else:
            status = "NO_REGION_MATCHES"

    if status in ("UNSUPPORTED_FILTER", "AMBIGUOUS_FILTER"):
        potential = []
        evidence = []
    return DiscoveryResult(
        query_summary=query_summary,
        search_status=status,
        verified_matches=[],
        potential_matches=potential,
        diagnostics=counts,
        evidence=evidence,
    )
