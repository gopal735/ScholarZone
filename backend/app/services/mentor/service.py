"""The mentor's request path.

One function, :func:`ask`, is the whole flow: understand the question, assemble
the grounded context, compose the answer from that context, and report where the
answer came from.

The ordering matters. The context is built *before* any wording exists, so a
sentence can only ever be a function of facts that were actually read. There is
no path where a phrasing decision precedes the lookup it claims to describe.
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import date

from sqlalchemy.orm import Session

from ...models import User
from ...schemas_mentor import (
    EvidenceResponse,
    MentorAnswerResponse,
    MentorMessageRequest,
    NextActionResponse,
)
from .compose import compose, redirects
from .context import MentorContext, build_context
from .evidence import EvidenceItem
from .guards import MAX_MESSAGE_LENGTH, contains_injection_marker, normalize_message
from .intents import classify
from .provider import (
    SYSTEM_INSTRUCTION,
    GroundedRequest,
    MentorProvider,
    ProviderResult,
    elapsed_ms,
    resolve_provider,
    sanitise_provider_error,
)

logger = logging.getLogger(__name__)

#: Hard ceiling on the text handed to a provider, independent of how many
#: scholarships are in context. Belt and braces with the per-item bounds.
MAX_PROVIDER_CONTEXT_CHARS = 4_000


def _context_blocks(context: MentorContext) -> tuple[str, ...]:
    """Render the grounded context as bounded, labelled text.

    Every block is prefixed with the canonical system it came from. A provider
    reading this cannot mistake a Match-derived figure for a published fact,
    because the prefix says which one it is.
    """
    blocks: list[str] = []

    student = context.student
    blocks.append(
        "STUDENT (from the student's own profile): "
        f"has_profile={student.has_profile}; "
        f"strength={student.strength_score if student.strength_score is not None else 'not measured'}; "
        f"gaps={list(student.gaps) if student.gaps else 'none recorded'}"
    )

    for item in context.scholarships:
        blocks.append(
            f"SCHOLARSHIP {item.scholarship_id} (ScholarZone catalogue + Match 2.0): "
            f"name={item.name!r}; country={item.country!r}; funding={item.funding!r}; "
            f"verification={item.verification_label!r}; "
            f"eligibility={item.eligibility or 'not evaluated'}; "
            f"fit={item.fit_score if item.fit_score is not None else 'not measured'}; "
            f"readiness={item.readiness_label or 'not assessed'}; "
            f"deadline={item.deadline.describe()}"
        )

    for entry in context.applications:
        blocks.append(
            f"APPLICATION {entry.application_id} (Application Workspace): "
            f"name={entry.name!r}; state={entry.state!r}; "
            f"outcome={entry.outcome or 'none recorded'}; "
            f"progress={'not measured' if not entry.progress_is_measured else round(entry.progress_percent, 1)}; "
            f"next_open_task={entry.next_open_task or 'none'}; "
            f"deadline={entry.deadline.describe()}"
        )

    for action in context.next_actions:
        blocks.append(
            f"NEXT ACTION (Student Dashboard, priority band {action.priority}): "
            f"{action.title!r} - {action.detail!r}"
        )

    for caveat in context.caveats:
        blocks.append(f"UNAVAILABLE: {caveat}")

    return tuple(blocks)


def _bounded_request(message: str, blocks: tuple[str, ...]) -> GroundedRequest:
    """Build the provider request, truncated to a fixed budget.

    Truncation happens on block boundaries so a provider never receives half a
    record presented as a whole one.
    """
    kept: list[str] = []
    used = 0
    for block in blocks:
        if used + len(block) > MAX_PROVIDER_CONTEXT_CHARS:
            kept.append("[context truncated: further records omitted for length]")
            break
        kept.append(block)
        used += len(block)
    return GroundedRequest(
        system_instruction=SYSTEM_INSTRUCTION,
        question=message[:MAX_MESSAGE_LENGTH],
        context_blocks=tuple(kept),
    )


def _evidence_payload(items: tuple[EvidenceItem, ...]) -> list[EvidenceResponse]:
    return [
        EvidenceResponse(
            key=item.key,
            label=item.label,
            value=item.value,
            field=item.field,
            basis=item.basis,
            verification=item.verification,
            source_url=item.source_url,
            scholarship_id=item.scholarship_id,
        )
        for item in items
    ]


def ask(
    db: Session,
    user: User,
    payload: MentorMessageRequest,
    *,
    as_of: date | None = None,
    provider: MentorProvider | None = None,
) -> MentorAnswerResponse:
    """Answer one grounded question for one authenticated student."""
    request_id = uuid.uuid4().hex[:12]
    started = time.perf_counter()

    message = normalize_message(payload.message)
    if not message:
        # An empty or entirely-strippable message cannot be classified. Saying so
        # is better than answering the most recent question instead.
        intent = classify("what should I do now")
        intent = type(intent)(
            kind=intent.kind,
            label=intent.label,
            unsupported=True,
            injection_markers=tuple(contains_injection_marker(payload.message)),
            truncated=len(payload.message) > MAX_MESSAGE_LENGTH,
        )
    else:
        intent = classify(message)

    resolved_as_of = as_of or payload.as_of or date.today()

    context = build_context(
        db,
        user,
        as_of=resolved_as_of,
        scholarship_id=intent.scholarship_id,
        application_id=intent.application_id,
    )

    answer = compose(intent, context)

    # The provider seam. Disabled in every default deployment; when something is
    # injected, its result is recorded and reported but never merged into the
    # answer body, because the body was built from canonical fields before this
    # line runs.
    active_provider = resolve_provider(provider)
    result: ProviderResult = ProviderResult(mode="disabled", used=False)
    if provider is not None:
        try:
            result = active_provider.generate(
                _bounded_request(message, _context_blocks(context))
            )
        except Exception as exc:  # noqa: BLE001 - a provider must not break the answer
            result = ProviderResult(
                mode="configured",
                used=False,
                failure=sanitise_provider_error(exc),
                latency_ms=elapsed_ms(started),
            )
            logger.warning(
                "mentor provider failed (%s) request_id=%s", result.failure, request_id
            )

    duration = elapsed_ms(started)

    # Privacy-safe observability: identifiers, counts and categories only. Never
    # the message, the notes, the profile values or the assembled context.
    logger.info(
        "mentor request_id=%s intent=%s supported=%s grounded=%s evidence=%d "
        "actions=%d unknown=%d provider=%s used=%s latency_ms=%d",
        request_id,
        intent.kind,
        answer.supported,
        answer.has_grounded_data,
        len(answer.known),
        len(answer.next_steps),
        len(answer.unknown),
        result.mode,
        result.used,
        duration,
    )

    return MentorAnswerResponse(
        request_id=request_id,
        as_of=context.as_of,
        intent=intent.kind,
        intent_label=intent.label,
        supported=answer.supported,
        headline=answer.headline,
        why=answer.why,
        known=_evidence_payload(answer.known),
        unknown=list(answer.unknown),
        next_steps=[
            NextActionResponse(
                code=action.code,
                title=action.title,
                detail=action.detail,
                priority=action.priority,
                href=action.href,
                action_label=action.action_label,
            )
            for action in answer.next_steps
        ],
        caveats=list(answer.caveats),
        notes=list(answer.notes),
        general_guidance_only=answer.general_guidance_only,
        provider_mode=result.mode,
        provider_used=result.used,
        redirects=list(redirects()) if not answer.supported else [],
    )