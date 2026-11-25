"""Conversation persistence service for Dream AI Mentor 2.0.

Owns conversation lifecycle, message persistence, ownership and idempotency.
All functions enforce ownership by user_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from ...models import MentorConversation, MentorMessage, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


MAX_CONVERSATIONS_PER_USER = 100
MAX_MESSAGES_PER_CONVERSATION = 500


def create_conversation(db: Session, user_id: int, title: str | None = None) -> MentorConversation:
    conv = MentorConversation(
        user_id=user_id,
        title=(title or "New conversation").strip()[:255] or "New conversation",
        status="active",
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


def list_conversations(db: Session, user_id: int, limit: int = 50, offset: int = 0) -> list[MentorConversation]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    stmt = (
        select(MentorConversation)
        .where(MentorConversation.user_id == user_id, MentorConversation.status != "deleted")
        .order_by(MentorConversation.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def get_conversation(db: Session, user_id: int, conversation_id: int) -> MentorConversation | None:
    stmt = select(MentorConversation).where(
        MentorConversation.id == conversation_id,
        MentorConversation.user_id == user_id,
        MentorConversation.status != "deleted",
    )
    return db.execute(stmt).scalar_one_or_none()


def rename_conversation(db: Session, user_id: int, conversation_id: int, title: str) -> MentorConversation | None:
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return None
    conv.title = (title or "").strip()[:255] or conv.title
    conv.updated_at = _now()
    db.commit()
    db.refresh(conv)
    return conv


def delete_conversation(db: Session, user_id: int, conversation_id: int) -> bool:
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return False
    conv.status = "deleted"
    conv.updated_at = _now()
    db.commit()
    return True


def list_messages(db: Session, user_id: int, conversation_id: int, limit: int = 100, offset: int = 0) -> list[MentorMessage]:
    # ownership check via conversation
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return []
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    stmt = (
        select(MentorMessage)
        .where(MentorMessage.conversation_id == conversation_id)
        .order_by(MentorMessage.sequence_number.asc(), MentorMessage.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list(db.execute(stmt).scalars().all())


def _next_sequence(db: Session, conversation_id: int) -> int:
    # Atomic allocation: lock the conversation row (where supported) before
    # computing MAX+1 to avoid duplicate sequence numbers under concurrency.
    try:
        db.execute(
            select(MentorConversation)
            .where(MentorConversation.id == conversation_id)
            .with_for_update()
        ).scalar_one_or_none()
    except Exception:
        pass
    stmt = select(func.coalesce(func.max(MentorMessage.sequence_number), 0)).where(
        MentorMessage.conversation_id == conversation_id
    )
    current = db.execute(stmt).scalar_one()
    return int(current) + 1


def add_user_message(
    db: Session,
    user_id: int,
    conversation_id: int,
    content: str,
    request_id: str | None = None,
) -> MentorMessage | None:
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return None
    if request_id is not None:
        request_id = request_id.strip() if isinstance(request_id, str) else request_id
        if request_id == "":
            request_id = None
        if isinstance(request_id, str) and len(request_id) > 64:
            raise ValueError("request_id_too_long")
    try:
        db.execute(
            select(MentorConversation)
            .where(MentorConversation.id == conversation_id)
            .with_for_update()
        )
    except Exception:
        pass
    if request_id:
        existing = db.execute(
            select(MentorMessage).where(
                MentorMessage.conversation_id == conversation_id,
                MentorMessage.role == "user",
                MentorMessage.request_id == request_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    msg = MentorMessage(
        conversation_id=conversation_id,
        user_id=user_id,
        role="user",
        content=content,
        status="completed",
        sequence_number=_next_sequence(db, conversation_id),
        request_id=request_id,
        completed_at=_now(),
    )
    db.add(msg)
    conv.last_message_at = _now()
    conv.updated_at = _now()
    db.commit()
    db.refresh(msg)
    return msg


def reserve_assistant_message(
    db: Session,
    user_id: int,
    conversation_id: int,
    request_id: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    source_user_message_id: int | None = None,
) -> MentorMessage | None:
    conv = get_conversation(db, user_id, conversation_id)
    if conv is None:
        return None
    if request_id is not None:
        request_id = request_id.strip() if isinstance(request_id, str) else request_id
        if request_id == "":
            request_id = None
        if isinstance(request_id, str) and len(request_id) > 64:
            raise ValueError("request_id_too_long")
    try:
        db.execute(
            select(MentorConversation)
            .where(MentorConversation.id == conversation_id)
            .with_for_update()
        )
    except Exception:
        pass
    if request_id:
        existing = db.execute(
            select(MentorMessage).where(
                MentorMessage.conversation_id == conversation_id,
                MentorMessage.role == "assistant",
                MentorMessage.request_id == request_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            return existing
    msg = MentorMessage(
        conversation_id=conversation_id,
        user_id=user_id,
        role="assistant",
        content="",
        status="pending",
        sequence_number=_next_sequence(db, conversation_id),
        request_id=request_id,
        provider=provider,
        model=model,
        source_user_message_id=source_user_message_id,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def complete_assistant_message(
    db: Session,
    user_id: int,
    message_id: int,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> MentorMessage | None:
    msg = db.get(MentorMessage, message_id)
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "failed", "cancelled"):
        return msg

    values = {
        "content": content,
        "status": "completed",
        "completed_at": _now(),
    }
    if provider is not None:
        values["provider"] = provider
    if model is not None:
        values["model"] = model
    if prompt_tokens is not None:
        values["prompt_tokens"] = prompt_tokens
    if completion_tokens is not None:
        values["completion_tokens"] = completion_tokens

    stmt = (
        update(MentorMessage)
        .where(
            MentorMessage.id == message_id,
            MentorMessage.user_id == user_id,
            MentorMessage.status == "pending",
        )
        .values(**values)
    )
    result = db.execute(stmt)
    db.commit()
    if result.rowcount == 0:
        # Terminal state changed concurrently; return authoritative state.
        return db.get(MentorMessage, message_id)
    refreshed = db.get(MentorMessage, message_id)
    # update conversation
    if refreshed is not None:
        conv = get_conversation(db, user_id, refreshed.conversation_id)
        if conv is not None:
            conv.last_message_at = _now()
            conv.updated_at = _now()
            db.commit()
    return refreshed


def fail_assistant_message(db: Session, user_id: int, message_id: int, error: str) -> MentorMessage | None:
    msg = db.get(MentorMessage, message_id)
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "cancelled"):
        return msg
    stmt = (
        update(MentorMessage)
        .where(
            MentorMessage.id == message_id,
            MentorMessage.user_id == user_id,
            MentorMessage.status == "pending",
        )
        .values(status="failed", error=error, completed_at=_now())
    )
    db.execute(stmt)
    db.commit()
    return db.get(MentorMessage, message_id)


def cancel_assistant_message(db: Session, user_id: int, message_id: int) -> MentorMessage | None:
    msg = db.get(MentorMessage, message_id)
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "failed"):
        return msg
    stmt = (
        update(MentorMessage)
        .where(
            MentorMessage.id == message_id,
            MentorMessage.user_id == user_id,
            MentorMessage.status == "pending",
        )
        .values(status="cancelled", completed_at=_now())
    )
    db.execute(stmt)
    db.commit()
    return db.get(MentorMessage, message_id)