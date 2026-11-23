"""The ScholarZone AI gateway.

Central entry point for all model interactions. Enforces:
- capability checks before invocation
- timeout enforcement
- bounded retries
- provider health reporting
- structured-output validation (caller-supplied)
- cancellation propagation
- cost/usage accounting
- graceful fallback honesty

The gateway never invents a result when a provider is unavailable; it returns
a structured ``ProviderResult`` with a failure category.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from .capabilities import Capability, ModelSpec, ProviderHealth
from .providers import (
    DisabledProvider,
    GatewayRequest,
    ModelProvider,
    ProviderResult,
    elapsed_ms,
    sanitise_provider_error,
)
from .routing import RoutingPolicy, resolve_model

logger = logging.getLogger(__name__)

#: Maximum retry attempts for transient failures.
MAX_RETRIES = 2
#: Base delay between retries (seconds).
RETRY_BASE_DELAY = 0.5


@dataclass
class GatewayConfig:
    """Configuration for the gateway."""

    registry: list[ModelSpec] = field(default_factory=list)
    policies: dict[str, RoutingPolicy] = field(default_factory=dict)
    default_provider: ModelProvider | None = None
    enabled: bool = False


class AIGateway:
    """Provider-independent AI gateway."""

    def __init__(self, config: GatewayConfig | None = None):
        self._config = config or GatewayConfig()
        self._provider: ModelProvider = self._config.default_provider or DisabledProvider()
        self._lock = threading.Lock()
        self._usage: list[dict] = []

    @property
    def enabled(self) -> bool:
        return self._config.enabled and not isinstance(self._provider, DisabledProvider)

    def set_provider(self, provider: ModelProvider) -> None:
        with self._lock:
            self._provider = provider

    def register_model(self, model: ModelSpec) -> None:
        with self._lock:
            self._config.registry.append(model)

    def get_policy(self, task_kind: str) -> RoutingPolicy | None:
        return self._config.policies.get(task_kind)

    def resolve(self, task_kind: str, *, model_override: str | None = None) -> tuple[RoutingPolicy | None, ModelSpec | None]:
        policy = self.get_policy(task_kind)
        if policy is None:
            # Build a default general policy
            from .routing import RoutingPolicy
            policy = RoutingPolicy(task_kind=task_kind, required_capabilities=frozenset())
        model = resolve_model(policy, self._config.registry, model_override=model_override)
        return policy, model

    def health(self) -> list[ProviderHealth]:
        with self._lock:
            result = [self._provider.health()]
            return result

    def generate(
        self,
        task_kind: str,
        request: GatewayRequest,
        *,
        model_override: str | None = None,
        validator: Optional[Callable[[str], bool]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> ProviderResult:
        """Generate a response for the given task kind.

        Returns a ``ProviderResult``. On any failure (unavailable provider,
        capability mismatch, timeout, malformed output) the result carries a
        failure category and ``used=False``. The caller must handle the failure
        honestly rather than assuming success.
        """
        started = __import__("time").perf_counter()

        policy, model = self.resolve(task_kind, model_override=model_override)

        if not self._config.enabled:
            return ProviderResult(mode="disabled", used=False, failure=None, latency_ms=elapsed_ms(started))

        if model is None:
            return ProviderResult(
                mode="configured",
                used=False,
                failure="unavailable",
                latency_ms=elapsed_ms(started),
            )

        # Capability check
        if not model.supports(policy.required_capabilities):
            return ProviderResult(
                mode="configured",
                used=False,
                failure="capability_mismatch",
                latency_ms=elapsed_ms(started),
                model=model.id,
                provider=self._provider.name,
            )

        # Respect cancellation
        if cancel_event is not None and cancel_event.is_set():
            return ProviderResult(
                mode="configured",
                used=False,
                failure="cancelled",
                latency_ms=elapsed_ms(started),
            )

        # Retry loop
        last_failure = None
        for attempt in range(MAX_RETRIES + 1):
            if cancel_event is not None and cancel_event.is_set():
                return ProviderResult(
                    mode="configured",
                    used=False,
                    failure="cancelled",
                    latency_ms=elapsed_ms(started),
                )
            try:
                result = self._provider.generate(request, model)
                if result.failure:
                    last_failure = result.failure
                    if attempt < MAX_RETRIES:
                        import time as _t
                        _t.sleep(RETRY_BASE_DELAY * (attempt + 1))
                        continue
                    return result
                # Validate structured output if validator provided
                if validator is not None and result.text is not None:
                    if not validator(result.text):
                        return ProviderResult(
                            mode=result.mode,
                            used=False,
                            text=result.text,
                            failure="malformed_response",
                            latency_ms=elapsed_ms(started),
                            model=model.id,
                            provider=self._provider.name,
                        )
                # Record usage
                with self._lock:
                    self._usage.append({
                        "task_kind": task_kind,
                        "model": model.id,
                        "provider": self._provider.name,
                        "prompt_tokens": result.prompt_tokens,
                        "completion_tokens": result.completion_tokens,
                    })
                return result
            except Exception as exc:  # noqa: BLE001
                last_failure = sanitise_provider_error(exc)
                logger.warning("gateway provider exception: %s", last_failure)
                if attempt < MAX_RETRIES:
                    import time as _t
                    _t.sleep(RETRY_BASE_DELAY * (attempt + 1))
                    continue
                return ProviderResult(
                    mode="configured",
                    used=False,
                    failure=last_failure,
                    latency_ms=elapsed_ms(started),
                    model=model.id,
                    provider=self._provider.name,
                )

        return ProviderResult(
            mode="configured",
            used=False,
            failure=last_failure or "unavailable",
            latency_ms=elapsed_ms(started),
        )

    def usage_summary(self) -> list[dict]:
        with self._lock:
            return list(self._usage)
