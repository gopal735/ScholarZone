"""Conversation persistence service for Dream AI Mentor 2.0.

Owns conversation lifecycle, message persistence, ownership and idempotency.
All functions enforce ownership by user_id.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from ...models import MentorConversation, MentorMessage, User


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lock_conversation(db: Session, conversation_id: int) -> None:
    # PostgreSQL: real row lock. SQLite: writes serialize at DB level; skip.
    try:
        dialect = db.get_bind().dialect.name
    except Exception:
        dialect = ""
    if dialect != "postgresql":
        return
    db.execute(
        select(MentorConversation)
        .where(MentorConversation.id == conversation_id)
        .with_for_update()
    ).scalar_one_or_none()


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
    _lock_conversation(db, conversation_id)
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
    _lock_conversation(db, conversation_id)
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
    attempt_id: str | None = None,
    **_kwargs,
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
    _lock_conversation(db, conversation_id)
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
        attempt_id=attempt_id or str(uuid.uuid4()),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def claim_retry_attempt(db: Session, user_id: int, message_id: int, attempt_id: str | None = None, new_attempt_id: str | None = None, **_kwargs) -> MentorMessage | None:
    """Atomically claim a new generation attempt for a terminal assistant message."""
    msg = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg is None or msg.user_id != user_id:
        return None
    if msg.role != "assistant":
        return None
    new_attempt_id = new_attempt_id or attempt_id or str(uuid.uuid4())
    stmt = (
        update(MentorMessage)
        .where(
            MentorMessage.id == message_id,
            MentorMessage.user_id == user_id,
            MentorMessage.status.in_(["failed", "cancelled"]),
        )
        .values(
            status="pending",
            attempt_id=new_attempt_id,
            error=None,
            completed_at=None,
        )
    )
    result = db.execute(stmt)
    claimed = (result.rowcount or 0) > 0
    if not claimed:
        db.rollback()
    else:
        db.commit()
    refreshed = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if refreshed is not None:
        try:
            setattr(refreshed, "_claimed", claimed)
        except Exception:
            pass
    return refreshed


def complete_assistant_message(
    db: Session,
    user_id: int,
    message_id: int,
    content: str,
    provider: str | None = None,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    attempt_id: str | None = None,
    expected_attempt_id: str | None = None,
    generation_attempt_id: str | None = None,
    active_attempt_id: str | None = None,
    **_kwargs,
) -> MentorMessage | None:
    expected = attempt_id or expected_attempt_id or generation_attempt_id or active_attempt_id
    msg = db.get(MentorMessage, message_id)
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "failed", "cancelled"):
        if expected is not None and msg.attempt_id not in (None, expected):
            # Stale attempt: do not overwrite; return authoritative state.
            pass
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

    where = [
        MentorMessage.id == message_id,
        MentorMessage.user_id == user_id,
        MentorMessage.status == "pending",
    ]
    if expected is not None:
        where.append(MentorMessage.attempt_id == expected)

    stmt = (
        update(MentorMessage)
        .where(*where)
        .values(**values)
    )
    result = db.execute(stmt)
    if result.rowcount == 0:
        db.rollback()
        refreshed = db.execute(
            select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        return refreshed
    # Update conversation in the same transaction.
    msg_row = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg_row is not None:
        conv = db.execute(
            select(MentorConversation).where(MentorConversation.id == msg_row.conversation_id).execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if conv is not None:
            conv.last_message_at = _now()
            conv.updated_at = _now()
    db.commit()
    refreshed = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    return refreshed


def fail_assistant_message(
    db: Session,
    user_id: int,
    message_id: int,
    error: str,
    attempt_id: str | None = None,
    expected_attempt_id: str | None = None,
    generation_attempt_id: str | None = None,
    active_attempt_id: str | None = None,
    **_kwargs,
) -> MentorMessage | None:
    expected = attempt_id or expected_attempt_id or generation_attempt_id or active_attempt_id
    msg = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "cancelled"):
        return msg
    if expected is not None and msg.attempt_id not in (None, expected):
        # Stale attempt; do not mutate newer attempt.
        return msg

    where = [
        MentorMessage.id == message_id,
        MentorMessage.user_id == user_id,
        MentorMessage.status == "pending",
    ]
    if expected is not None:
        where.append(MentorMessage.attempt_id == expected)

    stmt = (
        update(MentorMessage)
        .where(*where)
        .values(status="failed", error=error, completed_at=_now())
    )
    db.execute(stmt)
    db.commit()
    return db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()


def cancel_assistant_message(
    db: Session,
    user_id: int,
    message_id: int,
    attempt_id: str | None = None,
    expected_attempt_id: str | None = None,
    generation_attempt_id: str | None = None,
    active_attempt_id: str | None = None,
    **_kwargs,
) -> MentorMessage | None:
    expected = attempt_id or expected_attempt_id or generation_attempt_id or active_attempt_id
    msg = db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()
    if msg is None or msg.user_id != user_id:
        return None
    if msg.status in ("completed", "failed"):
        return msg
    if expected is not None and msg.attempt_id not in (None, expected):
        return msg

    where = [
        MentorMessage.id == message_id,
        MentorMessage.user_id == user_id,
        MentorMessage.status == "pending",
    ]
    if expected is not None:
        where.append(MentorMessage.attempt_id == expected)

    stmt = (
        update(MentorMessage)
        .where(*where)
        .values(status="cancelled", completed_at=_now())
    )
    db.execute(stmt)
    db.commit()
    return db.execute(
        select(MentorMessage).where(MentorMessage.id == message_id).execution_options(populate_existing=True)
    ).scalar_one_or_none()