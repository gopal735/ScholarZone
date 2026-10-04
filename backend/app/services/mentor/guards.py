"""Bounds and neutralisation for anything the mentor did not author.

Everything in this module exists because the mentor is allowed to receive two
kinds of untrusted text: the student's own message, and text that originated on a
provider's public web page and was ingested into the catalogue years ago.

**Structural defence first.** The production answer is composed deterministically
from canonical fields. No user or provider string is ever executed as an
instruction, because there is no interpreter in the request path. That is the
primary defence and it does not depend on any list of banned phrases.

**This module is the second layer.** It exists because that structural defence
would stop applying the moment a language model is enabled behind
:mod:`provider`, and because untrusted text must still be bounded before it is
echoed into a response, a log line, or a prompt. Sanitising here means the
provider adapter receives text that has already been reduced to inert content,
so a future adapter cannot accidentally be the weak link.
"""

from __future__ import annotations

import re
import unicodedata

#: Long enough for a real question, short enough that a pasted scholarship
#: circular cannot be used as a cheap way to spend someone's context budget.
MAX_MESSAGE_LENGTH = 2_000

#: Scholarship prose is bounded too. A mentor answer never needs a provider's
#: entire eligibility page, and the catalogue already stores structured
#: requirement lines for anything the mentor is allowed to reason about.
MAX_EVIDENCE_TEXT = 400

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"[ \t]+")
_BLANK_RUNS = re.compile(r"\n{3,}")

# Phrases that mark an attempt to talk to the model rather than ask about a
# scholarship. Detected so they can be reported to the caller, not so they can be
# "filtered" - the text is still shown back as the inert content it is.
_INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "disregard the above",
    "system prompt",
    "you are now",
    "act as",
    "reveal your",
    "print your instructions",
    "override your",
    "new instructions",
    "jailbreak",
    "developer mode",
)

# HTML is not rendered by this mentor, but a provider page can carry a tag that
# looks like markup to a reader and would be catastrophic if a future renderer
# ever interpreted it. Stripped rather than escaped so the stored meaning is the
# visible text.
_TAG = re.compile(r"<[^>]{0,400}>")
_SCRIPT = re.compile(r"(?is)<(script|style)[^>]*>.*?</\1>")


def normalize_message(raw: object) -> str:
    """Reduce arbitrary input to bounded, inert, single-normalised text.

    Returns ``""`` for anything that is not a string, so a JSON body of
    ``{"message": {"nested": "object"}}`` is a validation concern for the schema
    rather than an ``AttributeError`` here.
    """
    if not isinstance(raw, str):
        return ""
    text = unicodedata.normalize("NFKC", raw)
    text = _SCRIPT.sub(" ", text)
    text = _TAG.sub(" ", text)
    text = _CONTROL.sub(" ", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE.sub(" ", text)
    text = _BLANK_RUNS.sub("\n\n", text)
    return text.strip()


def bound_text(raw: object, limit: int = MAX_EVIDENCE_TEXT) -> str:
    """Normalise then hard-truncate, marking that truncation happened.

    The marker matters: a requirement line cut mid-sentence must not be presented
    to a reader as though it were the whole published requirement.
    """
    text = normalize_message(raw)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def message_within_limit(raw: object, limit: int = MAX_MESSAGE_LENGTH) -> bool:
    if not isinstance(raw, str):
        return False
    return len(raw) <= limit


def contains_injection_marker(raw: object) -> list[str]:
    """Report instruction-like phrasing found in untrusted text.

    Used for observability and for an explicit note in the response. It is
    deliberately *not* used to reject a legitimate request: a student asking
    "what should I do if a scholarship page tells me to ignore my profile?" is
    asking a real question, and refusing to answer would be the mentor being
    less useful precisely when it should be careful.
    """
    if not isinstance(raw, str):
        return []
    lowered = raw.lower()
    return [marker for marker in _INJECTION_MARKERS if marker in lowered]


def evidence_is_usable(raw: object, minimum: int = 24) -> bool:
    """Whether a piece of provider prose is long enough to reason about.

    A requirement that reduces to a handful of characters is not evidence of
    anything. Reporting it as though it were would be the mentor inventing
    confidence, so short fragments are dropped from the evidence set and
    surfaced as unknown instead.
    """
    return len(normalize_message(raw)) >= minimum