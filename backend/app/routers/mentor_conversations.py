"""Authenticated conversation endpoints for Dream AI Mentor 2.0."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..routers.applications import _same_origin_guard
from ..routers.mentor import _enforce_limit, _release_limit
from ..schemas_mentor import (
    MentorConversationCreate,
    MentorConversationResponse,
    MentorMessageResponse,
    MentorSendMessageRequest,
)
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
from ..services.mentor.service import ask

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mentor", tags=["mentor-conversations"])


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
        # idempotent user message
        user_msg = add_user_message(db, user.id, conversation_id, payload.message, request_id=payload.request_id)
        assistant = reserve_assistant_message(db, user.id, conversation_id, request_id=payload.request_id)
        if assistant is None:
            raise HTTPException(status_code=500, detail="persistence_failed")
        # If already completed (retry/idempotent), skip generation
        if assistant.status == "completed":
            return {"user_message": _msg_to_response(user_msg), "assistant_message": _msg_to_response(assistant)}
        # Run deterministic mentor ask
        try:
            answer = ask(db, user, __import__("app.schemas_mentor", fromlist=["MentorMessageRequest"]).MentorMessageRequest(message=payload.message))
            # Build a textual answer
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
            content = "\n".join(parts).strip()
            complete_assistant_message(
                db, user.id, assistant.id, content,
                provider=answer.provider_mode,
                model=None,
                prompt_tokens=None,
                completion_tokens=None,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("mentor conversation generation failed: %s", type(exc).__name__)
            fail_assistant_message(db, user.id, assistant.id, "provider_unavailable")
        # refresh
        assistant = db.get(__import__("app.models", fromlist=["MentorMessage"]).MentorMessage, assistant.id)
        return {"user_message": _msg_to_response(user_msg), "assistant_message": _msg_to_response(assistant)}
    finally:
        _release_limit()


@router.post("/conversations/{conversation_id}/messages/{message_id}/cancel")
def cancel_msg(conversation_id: int, message_id: int, db: Session = Depends(get_db), user: User = Depends(require_user)):
    conv = get_conversation(db, user.id, conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="conversation_not_found")
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
    msg = db.get(__import__("app.models", fromlist=["MentorMessage"]).MentorMessage, message_id)
    if msg is None or msg.user_id != user.id or msg.conversation_id != conversation_id:
        raise HTTPException(status_code=404, detail="message_not_found")
    if msg.role != "assistant":
        raise HTTPException(status_code=400, detail="retry_requires_assistant_message")
    # find preceding user message
    msgs = list_messages(db, user.id, conversation_id)
    user_msg = None
    for m in reversed(msgs):
        if m.id < msg.id and m.role == "user":
            user_msg = m
            break
    if user_msg is None:
        raise HTTPException(status_code=400, detail="no_source_user_message")
    _enforce_limit(user.id)
    try:
        if msg.status == "completed":
            return _msg_to_response(msg)
        # mark pending
        msg.status = "pending"
        msg.error = None
        db.commit()
        try:
            answer = ask(db, user, __import__("app.schemas_mentor", fromlist=["MentorMessageRequest"]).MentorMessageRequest(message=user_msg.content))
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
            content = "\n".join(parts).strip()
            complete_assistant_message(db, user.id, msg.id, content, provider=answer.provider_mode)
        except Exception:
            fail_assistant_message(db, user.id, msg.id, "provider_unavailable")
        msg = db.get(__import__("app.models", fromlist=["MentorMessage"]).MentorMessage, msg.id)
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

    user_msg = add_user_message(db, user.id, conversation_id, payload.message, request_id=payload.request_id)
    assistant = reserve_assistant_message(db, user.id, conversation_id, request_id=payload.request_id)
    if assistant is None:
        _release_limit()
        raise HTTPException(status_code=500, detail="persistence_failed")

    def event_generator():
        import app.models as _models
        import app.schemas_mentor as _schemas
        try:
            yield f"event: message_start\ndata: {json.dumps({'conversation_id': conversation_id, 'user_message_id': user_msg.id, 'assistant_message_id': assistant.id})}\n\n"
            answer = ask(db, user, _schemas.MentorMessageRequest(message=payload.message))
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
            content = "\n".join(parts).strip()
            # stream in chunks
            for i in range(0, len(content), 80):
                chunk = content[i:i+80]
                yield f"event: token\ndata: {json.dumps({'content': chunk})}\n\n"
            complete_assistant_message(db, user.id, assistant.id, content, provider=answer.provider_mode)
            refreshed = db.get(_models.MentorMessage, assistant.id)
            yield f"event: message_complete\ndata: {json.dumps({'assistant_message_id': assistant.id, 'status': refreshed.status if refreshed else 'completed'})}\n\n"
        except Exception as exc:  # noqa: BLE001
            fail_assistant_message(db, user.id, assistant.id, "provider_unavailable")
            yield f"event: message_error\ndata: {json.dumps({'detail': 'provider_unavailable'})}\n\n"
        finally:
            _release_limit()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/readiness")
def readiness():
    import os
    provider_configured = bool((os.getenv("SCHOLARZONE_AI_PROVIDER_KEY") or os.getenv("SCHOLARZONE_MENTOR_PROVIDER_KEY") or "").strip())
    return {
        "api": True,
        "database": True,
        "provider_configured": provider_configured,
        "conversation_persistence": True,
        "streaming": False,
        "memory": False,
    }