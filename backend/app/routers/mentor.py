"""The mentor's private API.

Two endpoints, and the second exists only because the first cannot answer a
question before the interface has asked one:

* ``GET  /mentor/overview`` - static vocabulary. No database work at all: which
  questions the mentor understands, what it will redirect to, and how long a
  message may be. Publishing it here is what stops the interface hard-coding a
  list that drifts away from the server's.
* ``POST /mentor/message``   - the grounded answer.

**Both require a session.** There is no public mentor route, and no handler here
accepts a user id: ownership is resolved from the cookie by ``require_user``
before the handler body runs, so there is no code path in which a caller can name
whose application they want to discuss.

**Rate limiting is scoped to this router deliberately.** The platform has no
inbound limiter anywhere, so this adds one without changing the behaviour of any
existing endpoint. It is an in-process fixed window plus an in-flight cap, which
is honest about what it is: per-instance, not fleet-wide. That limitation is
documented rather than papered over, because a limiter that reads as global and
is not would be worse than none.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import require_user
from ..models import User
from ..routers.applications import _same_origin_guard
from ..schemas_mentor import MentorAnswerResponse, MentorMessageRequest
from ..services.mentor.guards import MAX_MESSAGE_LENGTH
from ..services.mentor.intents import INTENT_LABELS
from ..services.mentor.provider import credential_present
from ..services.mentor.service import ask
from ..services.mentor.compose import redirects
from ..services.mentor.intents import INTENT_ORDER

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mentor", tags=["mentor"])


# ------------------------------------------------------------------ limiter

#: A mentor answer is bounded work, but it is not free, and it is the first
#: endpoint where one student's request could be made expensive. These are
#: deliberately generous: the limit exists to stop abuse, not to ration a student
#: asking several questions in a row.
_WINDOW_SECONDS = 60.0
_MAX_REQUESTS_PER_WINDOW = 20
_MAX_IN_FLIGHT = 4

_lock = threading.Lock()
_windows: dict[int, deque[float]] = defaultdict(deque)
_in_flight = 0


def _reset_limiter() -> None:
    """Test seam. Clears all limiter state."""
    global _in_flight
    with _lock:
        _windows.clear()
        _in_flight = 0


def _enforce_limit(user_id: int) -> int:
    """Count this request, or raise ``429``.

    Returns the number of whole seconds a rejected caller should wait, which
    becomes ``Retry-After``. Raising here rather than returning a bool keeps the
    happy path free of a conditional at every call site.
    """
    global _in_flight
    now = time.monotonic()

    with _lock:
        # Drop windows nobody is using, so a long-lived process does not
        # accumulate an entry per user who ever asked a question.
        if len(_windows) > 512:
            for key in [k for k, v in _windows.items() if not v or now - v[-1] > _WINDOW_SECONDS]:
                _windows.pop(key, None)

        bucket = _windows[user_id]
        while bucket and now - bucket[0] > _WINDOW_SECONDS:
            bucket.popleft()

        if _in_flight >= _MAX_IN_FLIGHT:
            retry_after = max(1, int(_WINDOW_SECONDS / 2))
            logger.warning("mentor rate limit: in-flight cap reached")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Your mentor is handling other questions right now. Try again in a moment.",
                headers={"Retry-After": str(retry_after)},
            )

        if len(bucket) >= _MAX_REQUESTS_PER_WINDOW:
            retry_after = max(1, int(_WINDOW_SECONDS - (now - bucket[0])) + 1)
            logger.warning("mentor rate limit: window cap reached")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You have asked many questions in a short time. Try again shortly.",
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        _in_flight += 1
    return 0


def _release_limit() -> None:
    global _in_flight
    with _lock:
        _in_flight = max(0, _in_flight - 1)


# -------------------------------------------------------------------- routes


@router.get("/overview")
def read_overview() -> dict:
    """What the mentor can be asked. No session data, no database work.

    Safe to call before sign-in: it contains only vocabulary, so it cannot leak
    anything about an account. That is also why the private surfaces still
    require a session - this route has nothing private on it to protect.
    """
    return {
        "supported_intents": [INTENT_LABELS[kind] for kind in INTENT_ORDER],
        "intents": list(INTENT_ORDER),
        "redirects": list(redirects()),
        "max_message_length": MAX_MESSAGE_LENGTH,
        # Presence only. No endpoint, no model name, no key material.
        "assistance_available": credential_present(),
    }


@router.post("/message", response_model=MentorAnswerResponse)
def post_message(
    payload: MentorMessageRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
    as_of: str | None = Query(None, description="Pin the measurement day (YYYY-MM-DD)."),
) -> MentorAnswerResponse:
    """Answer one grounded question.

    The Origin guard is the same one the Application Workspace uses. The mentor
    performs no writes, so this is defence in depth rather than the primary
    control, but a cookie-authenticated POST should not be the one endpoint that
    skipped the check.
    """
    _same_origin_guard(request)
    _enforce_limit(user.id)
    try:
        return ask(db, user, payload, as_of=_parse_as_of(as_of))
    finally:
        _release_limit()


def _parse_as_of(raw: str | None):
    """Parse an optional pinned measurement day.

    A malformed value is a ``422`` rather than a silent fallback to today: a
    caller that asked for a specific day and got a different one would be
    reading a number that was measured somewhere else.
    """
    if not raw:
        return None
    from datetime import date

    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        # The numeric literal rather than the status constant: the constant was
        # renamed in this Starlette generation, and a rename is not a reason for
        # this endpoint to start emitting a deprecation warning.
        raise HTTPException(
            status_code=422,
            detail="as_of must be a date in YYYY-MM-DD form.",
        ) from exc