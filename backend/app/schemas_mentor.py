"""Private wire contracts for the mentor.

These are deliberately separate from every public schema in the project. A public
scholarship response and a mentor response answer different questions about
different subsets of the same record, and the mentor's carries a student's own
state - applications, readiness, profile gaps - which has no business appearing
in a catalogue payload.

No schema here accepts a user id. Ownership is resolved from the session cookie
before a handler runs, so there is no field a caller could set to ask about
someone else's application.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from .services.mentor.guards import MAX_MESSAGE_LENGTH
from .services.mentor.intents import INTENT_LABELS

#: Published so the interface offers exactly what the server understands, rather
#: than maintaining its own list that can drift out of date.
SUPPORTED_INTENTS: list[str] = list(INTENT_LABELS.values())


class MentorMessageRequest(BaseModel):
    """One question.

    ``message`` is bounded at the schema, so an oversized body is a ``422``
    before it reaches any service. The service bounds it again defensively,
    because a schema is not a guarantee about who calls the function.
    """

    model_config = {"extra": "forbid"}

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_LENGTH)
    #: Lets a caller pin the day "days remaining" is measured against. Absent in
    #: normal use; present so a reproducible answer can be requested and tested.
    as_of: date | None = None


class EvidenceResponse(BaseModel):
    key: str
    label: str
    value: str
    #: The canonical field the value came from, in product words.
    field: str
    #: Which ScholarZone system produced it.
    basis: str
    verification: str | None = None
    source_url: str | None = None
    scholarship_id: int | None = None


class NextActionResponse(BaseModel):
    """A deterministic action, republished unchanged.

    ``priority`` is the dashboard's own fixed band. It travels to the client so
    the interface can explain the ordering rather than inventing its own, and it
    is not recomputed anywhere in the mentor.
    """

    code: str
    title: str
    detail: str
    priority: int
    href: str
    action_label: str


class MentorAnswerResponse(BaseModel):
    """The whole answer, in one document.

    ``as_of`` is echoed for the same reason the dashboard echoes it: so a reader
    can tell which day a day count was measured against.
    """

    request_id: str
    as_of: date

    intent: str
    intent_label: str
    supported: bool

    headline: str
    why: str

    #: Provenance for every factual claim in the answer.
    known: list[EvidenceResponse] = Field(default_factory=list)
    #: Everything the context does not know, named rather than omitted.
    unknown: list[str] = Field(default_factory=list)
    #: The deterministic next actions, in the engine's own order.
    next_steps: list[NextActionResponse] = Field(default_factory=list)

    caveats: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    #: True when nothing in the answer is a ScholarZone measurement, so the
    #: interface can label it as general guidance rather than verified data.
    general_guidance_only: bool = False

    #: ``disabled`` in every default deployment. Exposed so the interface can be
    #: honest about where an answer came from; never a credential or an endpoint.
    provider_mode: str = "disabled"
    provider_used: bool = False

    supported_intents: list[str] = Field(default_factory=lambda: list(SUPPORTED_INTENTS))
    redirects: list[str] = Field(default_factory=list)