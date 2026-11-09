"""Public AI Assistant API.

Two endpoints:
* ``GET  /api/ai/health`` - health check. Returns 200 when the service is up.
* ``POST /api/ai/assistant`` - grounded scholarship assistance for public users.

The assistant uses ScholarZone's verified catalogue and Match 2.0 engine to
answer questions without any language model. It never invents scholarship facts.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Scholarship
from ..repositories.scholarships import list_scholarships, public_visibility_conditions
from ..schemas import ScholarshipQuery, ScholarshipSort
from ..services.mentor.intents import classify
from ..services.mentor.guards import MAX_MESSAGE_LENGTH, normalize_message, contains_injection_marker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai-assistant"])


class AIAssistantRequest(BaseModel):
    """One question from a public user."""

    model_config = {"extra": "forbid"}

    question: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    context: Optional[dict] = Field(default_factory=dict)


class SourceResponse(BaseModel):
    type: str
    id: Optional[int] = None
    title: str
    url: Optional[str] = None


class AIAssistantResponse(BaseModel):
    """Grounded answer from ScholarZone records."""

    answer: str
    sources: list[SourceResponse] = Field(default_factory=list)
    grounded: bool = True
    model: Optional[str] = None
    tokens_used: Optional[int] = None


@router.get("/health")
def health_check() -> dict:
    """Health check endpoint for the AI assistant."""
    return {"status": "ok", "service": "ai-assistant", "mode": "grounded"}


@router.post("/assistant", response_model=AIAssistantResponse)
def ask_assistant(
    payload: AIAssistantRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> AIAssistantResponse:
    """Answer a scholarship question using grounded ScholarZone data.

    This endpoint is public and does not require authentication. It uses the
    same deterministic intent classification and catalogue search as the
    authenticated mentor, but without access to private user data.
    """
    # Normalize and validate the message
    message = normalize_message(payload.question)
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Question cannot be empty.",
        )

    # Check for injection markers (logged but not enforced)
    injection_markers = contains_injection_marker(message)
    if injection_markers:
        logger.info("ai_assistant injection_markers=%s", injection_markers)

    # Classify the intent
    intent = classify(message)

    # Build grounded answer using catalogue search
    answer_text, sources = _compose_grounded_answer(db, message, intent, payload.context)

    return AIAssistantResponse(
        answer=answer_text,
        sources=sources,
        grounded=True,
        model="grounded-catalogue-v1",
        tokens_used=0,
    )


def _compose_grounded_answer(
    db: Session,
    message: str,
    intent,
    context: dict,
) -> tuple[str, list[SourceResponse]]:
    """Compose a grounded answer from catalogue search results."""
    from ..services.mentor.intents import INTENT_LABELS

    # Extract search keywords from the question
    keywords = _extract_keywords(message)

    # Build search query based on intent and context
    search_query = _build_search_query(intent, keywords, context)

    # Search the catalogue
    results, _ = list_scholarships(db, search_query)

    if not results:
        return _no_results_answer(message), []

    # Compose answer based on intent
    answer_parts = []
    sources = []

    for scholarship in results[:5]:
        source = SourceResponse(
            type="scholarship",
            id=scholarship.id,
            title=scholarship.title,
            url=scholarship.official_source_url,
        )
        sources.append(source)

    intent_kind = intent.kind
    label = INTENT_LABELS.get(intent_kind, "General Guidance")

    if intent_kind == "SCHOLARSHIP_COMPARISON":
        answer_parts.append(f"Comparison of matching scholarships ({label}):")
    elif intent_kind == "DEADLINE":
        answer_parts.append(f"Upcoming deadlines ({label}):")
    elif intent_kind == "REQUIREMENT_GUIDANCE":
        answer_parts.append(f"Eligibility and requirements ({label}):")
    elif intent_kind == "SCHOLARSHIP_EXPLANATION":
        answer_parts.append(f"Scholarship details ({label}):")
    else:
        answer_parts.append(f"Based on the ScholarZone catalogue ({label}):")

    answer_parts.append("")

    for idx, scholarship in enumerate(results[:5]):
        answer_parts.append(f"{idx + 1}. **{scholarship.title}** ({scholarship.country}) — {scholarship.funding or 'Funding not specified'}")
        if scholarship.degree:
            answer_parts.append(f"   Degree: {scholarship.degree}")
        if scholarship.deadline_display:
            answer_parts.append(f"   Deadline: {scholarship.deadline_display}")
        if scholarship.official_source_url:
            answer_parts.append(f"   Official: {scholarship.official_source_url}")
        answer_parts.append("")

    answer_parts.append("Answers are grounded in ScholarZone data. Always verify details on the official provider website.")

    return "\n".join(answer_parts), sources


def _extract_keywords(message: str) -> list[str]:
    """Extract search keywords from a natural language question."""
    stop_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'by', 'from', 'about', 'into', 'through', 'during', 'before', 'after', 'above',
        'below', 'up', 'down', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
        'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each', 'few',
        'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'can', 'will', 'just', 'should', 'now',
        'what', 'which', 'who', 'whom', 'this', 'that', 'these', 'those', 'am', 'is',
        'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
        'do', 'does', 'did', 'doing', 'i', 'me', 'my', 'myself', 'we', 'our', 'ours',
        'ourselves', 'you', 'your', 'yours', 'yourself', 'yourselves', 'he', 'him',
        'his', 'himself', 'she', 'her', 'hers', 'herself', 'it', 'its', 'itself',
        'they', 'them', 'their', 'theirs', 'themselves',
        'scholarship', 'scholarships', 'available', 'find', 'show', 'list', 'tell', 'me',
        'about',
    }

    words = message.replace('?', ' ').replace('.', ' ').replace(',', ' ').split()
    filtered = []
    for w in words:
        lower = w.lower()
        if len(lower) > 2 and lower not in stop_words:
            filtered.append(lower)
        elif len(lower) >= 2 and w.isupper():
            filtered.append(lower)
    return filtered[:10]


def _build_search_query(intent, keywords: list[str], context: dict) -> ScholarshipQuery:
    """Build a ScholarshipQuery based on intent and context."""
    params = {
        "search": " ".join(keywords) if keywords else None,
        "limit": 10,
        "page": 1,
        "sort": ScholarshipSort.RECOMMENDED,
    }

    if context.get("country"):
        params["country"] = context["country"]
    if context.get("degree"):
        params["degree"] = context["degree"]
    if context.get("funding"):
        params["funding"] = context["funding"]

    if intent.kind == "DEADLINE":
        params["sort"] = ScholarshipSort.DEADLINE_SOON
    elif intent.kind == "SCHOLARSHIP_COMPARISON":
        params["sort"] = ScholarshipSort.RECOMMENDED
    elif intent.kind == "REQUIREMENT_GUIDANCE":
        params["sort"] = ScholarshipSort.RECOMMENDED

    return ScholarshipQuery(**params)


def _no_results_answer(message: str) -> str:
    """Generate a helpful response when no scholarships match."""
    return (
        "I couldn't find specific scholarships matching your question in the ScholarZone catalogue. "
        "Try browsing the directory with broader filters at /scholarships, "
        "or ask about general application guidance."
    )