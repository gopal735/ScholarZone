"""GROUNDed AI Mentor 1.0.

A private advisor that answers "what should I do next?" from ScholarZone's own
canonical records.

The division of responsibility across these modules is the whole design:

* :mod:`context` reads the canonical services and builds a bounded
  :class:`~context.MentorContext`. It is the only module that touches the
  database.
* :mod:`evidence` attaches provenance to every value, so a claim can be traced
  back to the system that produced it.
* :mod:`compose` writes the answer. It reads the context and never the database,
  which is what makes it trivially testable and impossible to drift from the
  facts.
* :mod:`provider` is a seam for an optional language model. It is disabled by
  default, and a provider result is recorded rather than merged into the answer,
  so enabling one cannot turn a grounded answer into a generated one.
* :mod:`intents` and :mod:`guards` bound and classify untrusted input.

Nothing here recomputes a deadline, a fit score, a readiness band, a
verification status, an application state or a catalogue count. Those belong to
Match 2.0, Count Intelligence, the deadline evaluator, the verification contract
and the Application Workspace, and a second implementation of any of them would
eventually disagree with the first.
"""

from .compose import ComposedAnswer, compose, redirects
from .context import MentorContext, build_context
from .evidence import EvidenceItem, collect
from .guards import MAX_MESSAGE_LENGTH, normalize_message
from .intents import INTENT_LABELS, INTENT_ORDER, Intent, classify
from .provider import DisabledProvider, MentorProvider, ProviderResult, resolve_provider

__all__ = (
    "MAX_MESSAGE_LENGTH",
    "INTENT_LABELS",
    "INTENT_ORDER",
    "ComposedAnswer",
    "DisabledProvider",
    "EvidenceItem",
    "Intent",
    "MentorContext",
    "MentorProvider",
    "ProviderResult",
    "build_context",
    "classify",
    "collect",
    "compose",
    "normalize_message",
    "redirects",
    "resolve_provider",
)