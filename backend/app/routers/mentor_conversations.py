"""Authenticated conversation endpoints for Dream AI Mentor 2.0."""

from __future__ import annotations

import json
import logging
import threading
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..database import get_engine, get_db
from ..dependencies import require_user
from ..models import User, MentorMessage
from ..routers.applications import _same_origin_guard
from ..routers.mentor import _enforce_limit, _release_limit
from ..schemas_mentor import (
    MentorConversationCreate,
    MentorConversationResponse,
    MentorMessageResponse,
    MentorSendMessageRequest,
)
from ..services.ai_gateway import get_ai_gateway, GatewayRequest
from ..services.mentor.conversation_service import (
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    rename_conversation,
    add_user_message,
    reserve_assistant_message,
    complete_assistant_message,
    fail_assistant_message,
    cancel_assistant_message,
)
from ..services.mentor.service import (
    ask,
    _context_blocks,
    _bounded_request,
    MAX_PROVIDER_CONTEXT_CHARS,
)
from ..services.mentor.context import build_context
from ..services.mentor.compose import compose
from ..services.mentor.intents import classify
from ..services.mentor.guards import normalize_message, MAX_MESSAGE_LENGTH
from ..services.mentor.provider import SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mentor", tags=["mentor-conversations"])

# Process-local cancel events for in-flight streams.
_ACTIVE_CANCELS: dict[int, threading.Event] = {}


def _conv_to_response(conv) -> MentorConversationResponse:
    return MentorConversationResponse(
        id=conv.id,
        title=conv.title,
        status=conv.status,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        last_message_at=conv.last_message_at,
    )


def _msg_to_response(msg) -> MentorMessageResponse:
    return MentorMessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        status=msg.status,
        sequence_number=msg.sequence_number,
        request_id=msg.request_id,
        provider=msg.provider,
        model=msg.model,
        prompt_tokens=msg.prompt_tokens,
        completion_tokens=msg.completion_tokens,
        error=msg.error,
        created_at=msg.created_at,
        completed_at=msg.completed_at,
    )


def _deterministic_content(answer) -> str:
    parts = [answer.headline, "", answer.why]
    if answer.known:
        parts.append("")
        parts.append("Evidence:")
        for ev in answer.known:
            parts.append(f"- {ev.label}: {ev.value}")
    if answer.unknown:
        parts.append("")
        parts.append("Unknown:")
        for u in answer.unknown:
            parts.append(f"- {u}")
    return "\n".join(parts).strip()


def _prepare(db, user, message):
    msg = normalize_message(message)
    if not msg:
        intent = classify("what should I do now")
    else:
        intent = classify(msg)
    context = build_context(
        db,
        user,
        as_of=date.today(),
        scholarship_id=intent.scholarship_id,
        application_id=intent.application_id,
    )
    answer = compose(intent, context)
    req = _bounded_request(msg or message, _context_blocks(context))
    return intent, context, answer, req


def _map_stream_error(exc: Exception) -> str:
    name = str(exc).lower()
    if "cancel" in name:
        return "cancelled"
    if "timeout" in name:
        return "timeout"
    if "rate_limited" in name or "429" in name:
        return "rate_limited"
    if "unauthorized" in name or "401" in name or "403" in name:
        return "unauthorized"
    if "capability" in name:
        return "capability_mismatch"
    if "malformed" in name:
        return "malformed_response"
    return "provider_unavailable"


@router.post("/conversations", response_model=MentorConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conv(payload: MentorConversationCreate, request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    _same_origin_guard(request)
    conv = create_conversation(db, user.id, payload.title)
    return _conv_to_response(conv)


@router.get("/conversations", response_model=list[MentorConversationResponse])
def list_convs(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require_user)):
    convs = list_conversations(db, user.id, limit=limit, offset=offset)
    return [_conv_to_response(c) for c in convs]


@router.get("/conversations/{conversation_id}", response_model=MentorConversationResponse)
def get_conv(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return _conv_to_response(conv)


@router.patch("/conversations/{conversation_id}", response_model=MentorConversationResponse)
def rename_conv(conversation_id: int, payload: MentorConversationCreate, db: Session = Depends(get_db), user: User = Depends(require_user)):
    conv = rename_conversation(db, user.id, conversation_id, payload.title or "")
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return _conv_to_response(conv)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conv(conversation_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    ok = delete_conversation(db, user.id, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    return None


@router.get("/conversations/{conversation_id}/messages", response_model=list[MentorMessageResponse])
def get_msgs(conversation_id: int, limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0), db: Session = Depends(get_db), user: User = Depends(require_user)):
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    msgs = list_messages(db, user.id, conversation_id, limit=limit, offset=offset)
    return [_msg_to_response(m) for m in msgs]


@router.post("/conversations/{conversation_id}/messages")
def send_msg(conversation_id: int, payload: MentorSendMessageRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    _same_origin_guard(request)
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    _enforce_limit(user.id)
    try:
        user_msg = add_user_message(db, user.id, conversation_id, payload.message, request_id=payload.request_id)
        assistant = reserve_assistant_message(db, user.id, conversation_id, request_id=payload.request_id, source_user_message_id=user_msg.id)
        if assistant is None:
            raise HTTPException(status_code=500, detail="persistence_failed")
        if assistant.status == "completed":
            return {"user_message": _msg_to_response(user_msg), "assistant_message": _msg_to_response(assistant)}

        intent, context, answer, req = _prepare(db, user, payload.message)
        deterministic = _deterministic_content(answer)

        gw = get_ai_gateway()
        content = deterministic
        provider_mode = "disabled"
        model = None
        prompt_tokens = None
        completion_tokens = None
        used = False
        if gw.enabled:
            try:
                gw_req = GatewayRequest(system_instruction=req.system_instruction, question=req.question, context_blocks=req.context_blocks, max_output_tokens=getattr(req, "max_output_tokens", 400), timeout_seconds=getattr(req, "timeout_seconds", None))
                result = gw.generate("general_guidance", gw_req)
                if result.used and result.text and result.text.strip():
                    content = result.text
                    provider_mode = result.mode or "configured"
                    model = result.model
                    prompt_tokens = result.prompt_tokens
                    completion_tokens = result.completion_tokens
                    used = True
                else:
                    # fallback: deterministic
                    provider_mode = "disabled" if not result.used else (result.failure or provider_mode)
            except Exception as exc:  # noqa: BLE001
                logger.warning("mentor conversation generation failed: %s", type(exc).__name__)
                fail_assistant_message(db, user.id, assistant.id, _map_stream_error(exc))
                assistant = db.execute(
                    __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == assistant.id).execution_options(populate_existing=True)
                ).scalar_one_or_none()
                return {"user_message": _msg_to_response(user_msg), "assistant_message": _msg_to_response(assistant)}

        if not used:
            # honest provider mode
            if gw.enabled:
                provider_mode = "disabled"
        complete_assistant_message(
            db, user.id, assistant.id, content,
            provider=provider_mode,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        assistant = db.execute(
            __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == assistant.id).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        return {"user_message": _msg_to_response(user_msg), "assistant_message": _msg_to_response(assistant)}
    finally:
        _release_limit()


@router.post("/conversations/{conversation_id}/messages/{message_id}/cancel")
def cancel_msg(conversation_id: int, message_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    _same_origin_guard(request)
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    msg = db.execute(
        __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg is None or msg.user_id != user.id or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="message_not_found")
    ev = _ACTIVE_CANCELS.get(message_id)
    if ev is not None:
        ev.set()
    msg = cancel_assistant_message(db, user.id, message_id)
    if msg is None:
        raise HTTPException(status_code=404, detail="message_not_found")
    return _msg_to_response(msg)


@router.post("/conversations/{conversation_id}/messages/{message_id}/retry")
def retry_msg(conversation_id: int, message_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    _same_origin_guard(request)
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    msg = db.execute(
        __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg is None or msg.user_id != user.id or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="message_not_found")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="retry_requires_assistant_message")
    msgs = list_messages(db, user.id, conversation_id, limit=500, offset=0)
    user_msg = None
    if getattr(msg, "source_user_message_id", None):
        src = db.get(MentorMessage, msg.source_user_message_id)
        if src is not None and src.user_id == user.id and src.conversation_id == conversation_id and src.role == "user":
            user_msg = src
    if user_msg is None:
        # Bounded, unambiguous fallback: the immediately preceding message by
        # sequence number must be a user message. Never scan paginated history.
        from sqlalchemy import select as _select
        stmt = _select(MentorMessage).where(
            MentorMessage.conversation_id == conversation_id,
            MentorMessage.sequence_number < msg.sequence_number,
        ).order_by(MentorMessage.sequence_number.desc()).limit(2)
        candidates = list(db.execute(stmt).scalars().all())
        if candidates and candidates[0].role == "user" and candidates[0].user_id == user.id:
            # Unambiguous only when there is no other candidate between.
            if len(candidates) == 1 or candidates[1].sequence_number < candidates[0].sequence_number:
                user_msg = candidates[0]
    if user_msg is None:
        raise HTTPException(status_code=400, detail="no_source_user_message")
    if msg.status == "completed":
        return _msg_to_response(msg)
    _enforce_limit(user.id)
    try:
        # Controlled transition back to pending only for terminal failed/cancelled.
        from sqlalchemy import update as _upd
        res = db.execute(
            _upd(MentorMessage).where(
                MentorMessage.id == msg.id,
                MentorMessage.user_id == user.id,
                MentorMessage.status.in_(["failed", "cancelled"]),
            ).values(status="pending", error=None)
        )
        db.commit()
        if res.rowcount == 0 and msg.status not in ("failed", "cancelled"):
            # Already completed or pending; do not regenerate completed.
            if msg.status == "completed":
                return _msg_to_response(msg)
            raise HTTPException(status_code=409, detail="retry_not_allowed")
        intent, context, answer, req = _prepare(db, user, user_msg.content)
        deterministic = _deterministic_content(answer)
        gw = get_ai_gateway()
        content = deterministic
        provider_mode = "disabled"
        model = None
        prompt_tokens = None
        completion_tokens = None
        used = False
        if gw.enabled:
            try:
                gw_req = GatewayRequest(system_instruction=req.system_instruction, question=req.question, context_blocks=req.context_blocks, max_output_tokens=getattr(req, "max_output_tokens", 400), timeout_seconds=getattr(req, "timeout_seconds", None))
                result = gw.generate("general_guidance", gw_req)
                if result.used and result.text and result.text.strip():
                    content = result.text
                    provider_mode = result.mode or "configured"
                    model = result.model
                    prompt_tokens = result.prompt_tokens
                    completion_tokens = result.completion_tokens
                    used = True
            except Exception as exc:  # noqa: BLE001
                logger.warning("mentor conversation retry failed: %s", type(exc).__name__)
                fail_assistant_message(db, user.id, msg.id, _map_stream_error(exc))
                msg = db.execute(
                    __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == msg.id).execution_options(populate_existing=True)
                ).scalar_one_or_none()
                return _msg_to_response(msg)
        if not used and gw.enabled:
            provider_mode = "disabled"
        complete_assistant_message(db, user.id, msg.id, content, provider=provider_mode, model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
        msg = db.execute(
            __import__("sqlalchemy").select(MentorMessage).where(MentorMessage.id == msg.id).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        return _msg_to_response(msg)
    finally:
        _release_limit()


@router.post("/conversations/{conversation_id}/messages/stream")
def stream_msg(conversation_id: int, payload: MentorSendMessageRequest, request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    _same_origin_guard(request)
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
    _enforce_limit(user.id)
    slot_owned_by_setup = True
    slot_released = False
    def _release_once():
        nonlocal slot_released, slot_owned_by_setup
        if not slot_released:
            slot_released = True
            slot_owned_by_setup = False
            _release_limit()
    cancel_event = None
    owns_cancel = False
    try:
        user_msg = add_user_message(db, user.id, conversation_id, payload.message, request_id=payload.request_id)
        assistant = reserve_assistant_message(db, user.id, conversation_id, request_id=payload.request_id, source_user_message_id=user_msg.id if user_msg is not None else None)
        if assistant is None:
            raise HTTPException(status_code=500, detail="persistence_failed")
        # Replay path: already completed -> return stored content, no generation.
        if assistant.status == "completed":
            _release_once()
            # Stream a single replay event sequence.
            def _replay():
                yield "event: message_start\ndata: " + json.dumps({'conversation_id': conversation_id, 'user_message_id': user_msg.id, 'assistant_message_id': assistant.id, 'replay': True}) + "\n\n"
                if assistant.content:
                    yield "event: token\ndata: " + json.dumps({'content': assistant.content}) + "\n\n"
                yield "event: message_complete\ndata: " + json.dumps({'assistant_message_id': assistant.id, 'status': 'completed'}) + "\n\n"
            return StreamingResponse(_replay(), media_type="text/event-stream")
        if assistant.status in ("failed", "cancelled"):
            _release_once()
            raise HTTPException(status_code=409, detail="retry_required")
        # Cancel registry: do not overwrite an existing event.
        cancel_event = threading.Event()
        existing_event = _ACTIVE_CANCELS.get(assistant.id)
        if existing_event is not None:
            # Active generation already in progress for this reservation.
            _release_once()
            raise HTTPException(status_code=409, detail="generation_already_active")
        _ACTIVE_CANCELS[assistant.id] = cancel_event
        owns_cancel = True
        # Transfer slot ownership to the generator, which releases on completion.
        slot_owned_by_setup = False
    except Exception:
        if cancel_event is not None and owns_cancel:
            if _ACTIVE_CANCELS.get(assistant.id) is cancel_event:
                _ACTIVE_CANCELS.pop(assistant.id, None)
        _release_once()
        raise
    finally:
        if slot_owned_by_setup:
            _release_once()

    def event_generator():
        import app.models as _models
        completed_successfully = False
        try:
            yield f"event: message_start\ndata: {json.dumps({'conversation_id': conversation_id, 'user_message_id': user_msg.id, 'assistant_message_id': assistant.id})}\n\n"

            intent, context, answer, req = _prepare(db, user, payload.message)
            deterministic = _deterministic_content(answer)

            # Emit citations from deterministic evidence.
            for ev in (answer.known or []):
                try:
                    yield f"event: citation\ndata: {json.dumps({'key': getattr(ev, 'key', None), 'label': getattr(ev, 'label', None), 'value': getattr(ev, 'value', None), 'scholarship_id': getattr(ev, 'scholarship_id', None), 'source_url': getattr(ev, 'source_url', None)})}\n\n"
                except Exception:
                    pass

            gw = get_ai_gateway()
            content_parts = []
            provider_mode = "disabled"
            model = None
            prompt_tokens = None
            completion_tokens = None
            used = False
            cancelled = False
            error_detail = None
            deterministic_emitted = False

            if gw.enabled:
                try:
                    gw_req = GatewayRequest(
                        system_instruction=req.system_instruction,
                        question=req.question,
                        context_blocks=req.context_blocks,
                        max_output_tokens=getattr(req, "max_output_tokens", 400),
                        timeout_seconds=getattr(req, "timeout_seconds", None),
                        cancel_event=cancel_event,
                    )
                    started_output = False
                    buffered_chunks = []
                    for chunk in gw.generate_stream("general_guidance", gw_req, cancel_event=cancel_event):
                        if cancel_event is not None and cancel_event.is_set():
                            cancelled = True
                            break
                        content_parts.append(chunk)
                        if not started_output:
                            buffered_chunks.append(chunk)
                            if "".join(content_parts).strip():
                                started_output = True
                                for b in buffered_chunks:
                                    yield f"event: token\\ndata: {json.dumps({'content': b})}\\n\\n"
                                buffered_chunks = []
                        else:
                            yield f"event: token\\ndata: {json.dumps({'content': chunk})}\\n\\n"
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled = True
                    # discard any held-back whitespace-only chunks
                    buffered_chunks = []
                    if "".join(content_parts).strip():
                        used = True
                        provider_mode = "configured"
                    else:
                        used = False
                except Exception as exc:  # noqa: BLE001
                    logger.warning("mentor conversation stream provider error: %s %s", type(exc).__name__, exc)
                    if cancel_event is not None and cancel_event.is_set():
                        cancelled = True
                    else:
                        error_detail = _map_stream_error(exc)
            else:
                # Deterministic fallback: send as a single token.
                if deterministic:
                    yield f"event: token\ndata: {json.dumps({'content': deterministic})}\n\n"
                    content_parts.append(deterministic)
                    deterministic_emitted = True

            if cancelled:
                cancel_assistant_message(db, user.id, assistant.id)
                yield f"event: message_cancelled\ndata: {json.dumps({'assistant_message_id': assistant.id})}\n\n"
                return

            # Provider failure: do NOT emit fallback text.
            if error_detail:
                fail_assistant_message(db, user.id, assistant.id, error_detail)
                yield f"event: message_error\ndata: {json.dumps({'detail': error_detail})}\n\n"
                return

            content = "".join(content_parts).strip() if content_parts else ""
            if not used and gw.enabled:
                # fallback to deterministic (provider returned empty, no error)
                content = deterministic
                if deterministic and not deterministic_emitted:
                    yield f"event: token\ndata: {json.dumps({'content': deterministic})}\n\n"
                    content_parts.append(deterministic)
                    deterministic_emitted = True

            if not content:
                content = deterministic

            complete_assistant_message(
                db, user.id, assistant.id, content,
                provider=provider_mode if used else "disabled",
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
            completed_successfully = True
            refreshed = db.execute(
                __import__("sqlalchemy").select(_models.MentorMessage).where(_models.MentorMessage.id == assistant.id).execution_options(populate_existing=True)
            ).scalar_one_or_none()
            yield f"event: message_complete\ndata: {json.dumps({'assistant_message_id': assistant.id, 'status': refreshed.status if refreshed else 'completed'})}\n\n"
        except GeneratorExit:
            # Client disconnected: persist terminal state, no yield.
            if not completed_successfully:
                if cancel_event is not None and cancel_event.is_set():
                    cancel_assistant_message(db, user.id, assistant.id)
                else:
                    try:
                        fail_assistant_message(db, user.id, assistant.id, "stream_interrupted")
                    except Exception:
                        pass
            raise
        except Exception as exc:  # noqa: BLE001
            logger.warning("mentor conversation stream failed: %s", type(exc).__name__)
            try:
                fail_assistant_message(db, user.id, assistant.id, "provider_unavailable")
            except Exception:
                pass
            try:
                yield f"event: message_error\ndata: {json.dumps({'detail': 'provider_unavailable'})}\n\n"
            except Exception:
                pass
        finally:
            if owns_cancel and cancel_event is not None:
                if _ACTIVE_CANCELS.get(assistant.id) is cancel_event:
                    _ACTIVE_CANCELS.pop(assistant.id, None)
            _release_limit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/readiness")
def readiness():
    import os
    provider_configured = bool((os.getenv("SCHOLARZONE_AI_PROVIDER_KEY") or "").strip())
    db_ok = False
    schema_ok = False
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
        from sqlalchemy import inspect as _inspect
        insp = _inspect(engine)
        schema_ok = insp.has_table("mentor_conversations") and insp.has_table("mentor_messages")
    except Exception:
        db_ok = False
        schema_ok = False
    gw = get_ai_gateway()
    return {
        "api": True,
        "database": db_ok,
        "provider_configured": provider_configured,
        "conversation_persistence": schema_ok,
        "streaming": True,
        "gateway_enabled": gw.enabled,
        "memory": False,
    }