"""Retrieval-Augmented Generation retrieval foundation.

This module provides database-grounded retrieval for the ScholarZone AI Mentor.
It does NOT generate text. It only retrieves and ranks evidence from the
canonical scholarship catalogue. External LLM generation remains disabled until
the privacy boundary in PR #102 is verified and a policy-compliant provider is
configured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ...models import Scholarship


@dataclass(frozen=True)
class RagEvidence:
    """A single piece of retrieved evidence with full provenance."""

    scholarship_id: int
    title: str
    country: str
    degree: str
    status: str
    is_archived: bool
    fully_funded: bool | None
    deadline_date: str | None
    official_source_url: str | None
    chunk_id: str
    chunk_text: str
    score: float
    matched_fields: list[str] = field(default_factory=list)


def _normalize(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def _tokens(text: str | None) -> list[str]:
    normalized = _normalize(text)
    # Keep Bengali and Latin characters; split on non-word boundaries.
    return [t for t in re.split(r"[^\w\u0980-\u09FF]+", normalized) if t]


def _is_publicly_visible(scholarship: Scholarship) -> bool:
    """Respect ScholarZone public visibility policy."""
    if getattr(scholarship, "is_archived", False):
        return False
    status = (scholarship.status or "").lower()
    # CLOSED records are excluded from normal current-opportunity discovery.
    if status == "closed":
        return False
    return True


def _build_chunks(scholarship: Scholarship) -> list[tuple[str, str]]:
    """Build (chunk_id, chunk_text) pairs from a scholarship record."""
    chunks: list[tuple[str, str]] = []
    sid = scholarship.id

    def add(section: str, text: str | None) -> None:
        if text and str(text).strip():
            chunks.append((f"{sid}:{section}", str(text).strip()))

    add("title", scholarship.title)
    add("description", scholarship.description)
    add("eligibility", " ".join(scholarship.eligibility or []))
    add("eligibility_summary", scholarship.eligibility_summary)
    add("benefits", " ".join(scholarship.benefits or []))
    add("coverage", " ".join(scholarship.coverage or []))
    add("requirements", " ".join(scholarship.requirements or []))
    add("documents", " ".join(scholarship.documents or []))
    add("notes", scholarship.notes)
    add("official_details", str(scholarship.official_details) if scholarship.official_details else None)
    return chunks


def _score_chunk(query_tokens: Sequence[str], chunk_text: str, matched_fields: list[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokens(chunk_text)
    if not chunk_tokens:
        return 0.0
    chunk_set = set(chunk_tokens)
    hits = sum(1 for t in query_tokens if t in chunk_set)
    # Exact phrase bonus
    phrase = " ".join(query_tokens)
    phrase_bonus = 2.0 if phrase and phrase in _normalize(chunk_text) else 0.0
    # Field bonus
    field_bonus = 0.5 * len(matched_fields)
    base = hits / max(1, len(set(query_tokens)))
    return base + phrase_bonus + field_bonus


def retrieve(
    db: Session,
    query: str,
    *,
    country: str | None = None,
    degree: str | None = None,
    subject: str | None = None,
    include_closed: bool = False,
    include_archived: bool = False,
    limit: int = 10,
) -> list[RagEvidence]:
    """Hybrid structured + lexical retrieval over the scholarship catalogue.

    Returns a bounded, deterministic list of evidence items. Retrieval works
    without any LLM provider.
    """
    query_tokens = _tokens(query)
    stmt = db.query(Scholarship)

    # Structured filters (Layer A)
    if country:
        stmt = stmt.filter(Scholarship.country.ilike(f"%{country}%"))
    if degree:
        stmt = stmt.filter(Scholarship.degree.ilike(f"%{degree}%"))
    if subject:
        stmt = stmt.filter(
            or_(
                Scholarship.title.ilike(f"%{subject}%"),
                Scholarship.description.ilike(f"%{subject}%"),
                Scholarship.eligibility_summary.ilike(f"%{subject}%"),
            )
        )

    scholarships = stmt.all()

    results: list[RagEvidence] = []
    for s in scholarships:
        if not include_archived and getattr(s, "is_archived", False):
            continue
        if not include_closed and (s.status or "").lower() == "closed":
            continue
        if not _is_publicly_visible(s) and not (include_closed or include_archived):
            continue

        matched_fields: list[str] = []
        if country and country.lower() in _normalize(s.country):
            matched_fields.append("country")
        if degree and degree.lower() in _normalize(s.degree):
            matched_fields.append("degree")

        for chunk_id, chunk_text in _build_chunks(s):
            score = _score_chunk(query_tokens, chunk_text, matched_fields)
            if score <= 0 and query_tokens:
                continue
            if not query_tokens:
                score = 0.1
            results.append(
                RagEvidence(
                    scholarship_id=s.id,
                    title=s.title,
                    country=s.country,
                    degree=s.degree,
                    status=s.status,
                    is_archived=bool(s.is_archived),
                    fully_funded=s.fully_funded,
                    deadline_date=s.deadline_date.isoformat() if s.deadline_date else None,
                    official_source_url=s.official_source_url,
                    chunk_id=chunk_id,
                    chunk_text=chunk_text,
                    score=score,
                    matched_fields=matched_fields,
                )
            )

    # Deduplicate by scholarship (keep best chunk per scholarship)
    best_by_scholarship: dict[int, RagEvidence] = {}
    for ev in results:
        existing = best_by_scholarship.get(ev.scholarship_id)
        if existing is None or ev.score > existing.score:
            best_by_scholarship[ev.scholarship_id] = ev

    deduped = sorted(best_by_scholarship.values(), key=lambda e: (-e.score, e.scholarship_id))
    return deduped[:limit]
