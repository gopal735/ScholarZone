"""AI Assistant endpoints — public, with graceful degradation.

The AI Assistant is an optional enhancement. When no remote AI provider is
configured (the default for free-first operation), these endpoints return 503
so the frontend falls back to deterministic grounded retrieval from the
ScholarZone catalogue.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai", tags=["ai"])


class AIAssistantRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    context: dict | None = None


class AIAssistantResponse(BaseModel):
    answer: str
    sources: list[dict] = Field(default_factory=list)
    grounded: bool = True
    model: str | None = None
    tokens_used: int | None = None


@router.head("/health")
@router.get("/health")
def ai_health() -> dict[str, str]:
    """AI health check.

    Returns 503 when no remote AI provider is configured, which signals the
    frontend to use grounded fallback. This preserves free-first operation.
    """
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="AI service not configured. Grounded retrieval is available.",
    )


@router.post("/assistant", response_model=AIAssistantResponse)
def ai_assistant(payload: AIAssistantRequest) -> AIAssistantResponse:
    """AI Assistant endpoint.

    Returns 503 when no remote AI provider is configured. The frontend catches
    this and falls back to deterministic grounded retrieval from the catalogue.
    """
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="AI service not configured. Grounded retrieval is available.",
    )
