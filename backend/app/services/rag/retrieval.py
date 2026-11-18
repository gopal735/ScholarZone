"""Retrieval-Augmented Generation retrieval foundation.

This module provides database-grounded retrieval for the ScholarZone AI Mentor.
It does NOT generate text. It only retrieves and ranks evidence from the
canonical scholarship catalogue. External LLM generation remains disabled until
the privacy boundary in PR #102 is verified and a policy-compliant provider is
configured.

Note: chunk_id values are synthesized from canonical scholarship fields
("{scholarship_id}:{section}") rather than persisted chunk rows. This is a
retrieval-only foundation; persistent indexing, embeddings, and vector search
are not implemented in this PR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import func, or_
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
    return [t for t in re.split(r"[^\w\u0980-\u09FF]+", normalized) if t]


def _is_publicly_visible(status: str | None, is_archived: bool | None) -> bool:
    if is_archived is True:
        return False
    if (status or "").lower() == "closed":
        return False
    return True


def _build_chunks(row: dict) -> list[tuple[str, str]]:
    chunks: list[tuple[str, str]] = []
    sid = row["id"]

    def add(section: str, text: str | None) -> None:
        if text and str(text).strip():
            chunks.append((f"{sid}:{section}", str(text).strip()))

    add("title", row.get("title"))
    add("country", row.get("country"))
    add("degree", row.get("degree"))
    add("description", row.get("description"))
    add("eligibility", " ".join(row.get("eligibility") or []))
    add("eligibility_summary", row.get("eligibility_summary"))
    add("benefits", " ".join(row.get("benefits") or []))
    add("coverage", " ".join(row.get("coverage") or []))
    add("requirements", " ".join(row.get("requirements") or []))
    add("documents", " ".join(row.get("documents") or []))
    add("notes", row.get("notes"))
    add("official_details", str(row.get("official_details")) if row.get("official_details") else None)
    return chunks


def _score_chunk(query_tokens: Sequence[str], chunk_text: str, matched_fields: list[str]) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = _tokens(chunk_text)
    if not chunk_tokens:
        return 0.0
    chunk_set = set(chunk_tokens)
    hits = sum(1 for t in query_tokens if t in chunk_set)
    if hits == 0:
        return 0.0
    width = len(query_tokens)
    has_phrase = False
    if width <= len(chunk_tokens):
        query_list = list(query_tokens)
        has_phrase = any(
            chunk_tokens[i:i + width] == query_list
            for i in range(len(chunk_tokens) - width + 1)
        )
    phrase_bonus = 2.0 if has_phrase else 0.0
    field_bonus = 0.5 * len(matched_fields)
    base = len(set(query_tokens) & chunk_set) / max(1, len(set(query_tokens)))
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
    if limit is None or limit <= 0:
        return []
    query_tokens = _tokens(query)

    # Select required column values directly to avoid ORM identity-map staleness.
    columns = [
        Scholarship.id,
        Scholarship.title,
        Scholarship.country,
        Scholarship.degree,
        Scholarship.status,
        Scholarship.is_archived,
        Scholarship.fully_funded,
        Scholarship.deadline_date,
        Scholarship.official_source_url,
        Scholarship.description,
        Scholarship.eligibility,
        Scholarship.eligibility_summary,
        Scholarship.benefits,
        Scholarship.coverage,
        Scholarship.requirements,
        Scholarship.documents,
        Scholarship.notes,
        Scholarship.official_details,
    ]
    stmt = db.query(*columns)

    # Database-level visibility
    if not include_archived:
        stmt = stmt.filter(or_(Scholarship.is_archived.is_(False), Scholarship.is_archived.is_(None)))
    if not include_closed:
        stmt = stmt.filter(or_(Scholarship.status.is_(None), func.lower(Scholarship.status) != "closed"))

    # Structured filters (literal, case-insensitive)
    if country:
        stmt = stmt.filter(Scholarship.country.icontains(country, autoescape=True))
    if degree:
        stmt = stmt.filter(Scholarship.degree.icontains(degree, autoescape=True))
    if subject:
        stmt = stmt.filter(
            or_(
                Scholarship.title.icontains(subject, autoescape=True),
                Scholarship.description.icontains(subject, autoescape=True),
                Scholarship.eligibility_summary.icontains(subject, autoescape=True),
            )
        )

    rows = stmt.all()

    best_by_scholarship: dict[int, RagEvidence] = {}
    for row in rows:
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(row._mapping)

        sid = row_dict["id"]
        status = row_dict.get("status")
        is_archived = row_dict.get("is_archived")

        # Defensive visibility checks
        if not include_archived and is_archived is True:
            continue
        if not include_closed and (status or "").lower() == "closed":
            continue
        if not _is_publicly_visible(status, is_archived) and not (include_closed or include_archived):
            continue

        matched_fields: list[str] = []
        if country:
            matched_fields.append("country")
        if degree:
            matched_fields.append("degree")

        for chunk_id, chunk_text in _build_chunks(row_dict):
            score = _score_chunk(query_tokens, chunk_text, matched_fields)
            if score <= 0 and query_tokens:
                continue
            if not query_tokens:
                score = 0.1
            candidate = RagEvidence(
                scholarship_id=sid,
                title=row_dict.get("title"),
                country=row_dict.get("country"),
                degree=row_dict.get("degree"),
                status=status,
                is_archived=bool(is_archived) if is_archived is not None else False,
                fully_funded=row_dict.get("fully_funded"),
                deadline_date=row_dict["deadline_date"].isoformat() if row_dict.get("deadline_date") else None,
                official_source_url=row_dict.get("official_source_url"),
                chunk_id=chunk_id,
                chunk_text=chunk_text,
                score=score,
                matched_fields=matched_fields,
            )
            existing = best_by_scholarship.get(sid)
            if existing is None or candidate.score > existing.score:
                best_by_scholarship[sid] = candidate

    deduped = sorted(best_by_scholarship.values(), key=lambda e: (-e.score, e.scholarship_id))
    return deduped[:limit]
