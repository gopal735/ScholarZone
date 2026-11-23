"""Provider adapters for the ScholarZone AI gateway.

Each adapter implements a single interface: ``generate(request) -> ProviderResult``.
Adapters are stateless with respect to a single request; configuration is
passed at construction. No adapter makes a network call unless explicitly
configured with credentials and enabled.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from .capabilities import ModelSpec, ProviderHealth

logger = logging.getLogger(__name__)

#: Failure categories (closed vocabulary).
FAILURE_TIMEOUT = "timeout"
FAILURE_UNAVAILABLE = "unavailable"
FAILURE_MALFORMED = "malformed_response"
FAILURE_RATE_LIMITED = "rate_limited"
FAILURE_CAPABILITY_MISMATCH = "capability_mismatch"
FAILURE_CANCELLED = "cancelled"

PROVIDER_MODE_DISABLED = "disabled"
PROVIDER_MODE_CONFIGURED = "configured"


@dataclass(frozen=True)
class GatewayRequest:
    """A request to a model provider."""

    system_instruction: str
    question: str
    context_blocks: tuple[str, ...]
    required_capabilities: frozenset = field(default_factory=frozenset)
    max_output_tokens: int = 400
    timeout_seconds: float = 6.0
    model_override: str | None = None


@dataclass(frozen=True)
class ProviderResult:
    """Outcome of a provider call."""

    mode: str
    used: bool = False
    text: str | None = None
    failure: str | None = None
    latency_ms: int = 0
    model: str | None = None
    provider: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

    @property
    def ok(self) -> bool:
        return self.failure is None


@runtime_checkable
class ModelProvider(Protocol):
    """Interface every provider adapter implements."""

    name: str

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult: ...

    def health(self) -> ProviderHealth: ...


class DisabledProvider:
    """The production default. Reports not-used, makes no network call."""

    name = "disabled"

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult:
        return ProviderResult(mode=PROVIDER_MODE_DISABLED, used=False, failure=None)

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, available=True)


@dataclass
class RecordingProvider:
    """Deterministic provider for tests."""

    name: str = "recording"
    reply: str = "recorded"
    failure: str | None = None
    latency_ms: int = 0
    seen: list = field(default_factory=list)

    def generate(self, request: GatewayRequest, model: ModelSpec) -> ProviderResult:
        self.seen.append((request, model))
        return ProviderResult(
            mode=PROVIDER_MODE_CONFIGURED,
            used=self.failure is None,
            text=None if self.failure else self.reply,
            failure=self.failure,
            latency_ms=self.latency_ms,
            model=model.id,
            provider=self.name,
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(provider=self.name, available=True)


def credential_present(env_var: str = "SCHOLARZONE_AI_PROVIDER_KEY") -> bool:
    """Whether a credential exists for the given env var, without reading it."""
    return bool((os.getenv(env_var) or "").strip())


def sanitise_provider_error(exc: BaseException) -> str:
    name = type(exc).__name__.lower()
    if "timeout" in name or "timedout" in name:
        return FAILURE_TIMEOUT
    if "connect" in name or "network" in name:
        return FAILURE_UNAVAILABLE
    if "rate" in name or "429" in name:
        return FAILURE_RATE_LIMITED
    return FAILURE_UNAVAILABLE


def elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
