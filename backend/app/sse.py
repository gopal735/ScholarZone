"""Shared Server-Sent Events serialization helpers.

All SSE emission in the application must go through :func:`format_sse` so
that framing, JSON encoding and event-field injection protection are
consistent across every event type (including replayed events).
"""

from __future__ import annotations

import json
from typing import Any


def format_sse(event: str, data: Any = None) -> str:
    """Serialize one SSE event.

    * ``event`` is sanitized to a single token (no CR/LF) so it cannot
      inject additional event fields.
    * ``data`` is JSON-encoded; multiline output is prefixed line by line
      with ``data:`` so a payload can never be interpreted as a new event.
    * Exactly one blank-line event boundary is emitted.
    """
    safe_event = (event or "message").replace("\r", "").replace("\n", "").strip()
    if not safe_event:
        safe_event = "message"
    if data is None:
        body = ""
    else:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    out = f"event: {safe_event}\n"
    for line in body.split("\n"):
        out += f"data: {line}\n"
    out += "\n"
    return out
