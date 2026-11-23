"""Model capability registry for the ScholarZone AI gateway.

Defines the vocabulary of capabilities a model may advertise and the data
structures used to describe a configured model. Business logic never names
a model directly; it asks the gateway for a model satisfying a set of
required capabilities and a routing policy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import FrozenSet


class Capability(str, Enum):
    """Capabilities a model may advertise."""

    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    TOOL_CALLING = "tool_calling"
    LONG_CONTEXT = "long_context"
    MULTILINGUAL = "multilingual"
    VISION = "vision"
    EMBEDDINGS = "embeddings"
    STREAMING = "streaming"


#: All capabilities, for validation.
ALL_CAPABILITIES: FrozenSet[Capability] = frozenset(Capability)


@dataclass(frozen=True)
class ModelSpec:
    """A configured model.

    ``provider`` is the backend that serves it (e.g. ``openai``, ``anthropic``,
    ``gemini``, ``openai_compatible``, ``local``). ``capabilities`` is the set
    the provider adapter verified it can perform. ``cost_tier`` is a coarse
    hint used by routing policy (0 = free/cheapest, higher = more expensive).
    """

    id: str
    provider: str
    display_name: str
    capabilities: frozenset[Capability] = field(default_factory=frozenset)
    context_window: int = 8_000
    max_output_tokens: int = 1_024
    cost_tier: int = 0
    enabled: bool = True

    def supports(self, required: set[Capability] | frozenset[Capability]) -> bool:
        return required.issubset(self.capabilities)


@dataclass(frozen=True)
class ProviderHealth:
    """Health snapshot for a provider."""

    provider: str
    available: bool
    latency_ms: int | None = None
    error: str | None = None
    checked_at: str | None = None
