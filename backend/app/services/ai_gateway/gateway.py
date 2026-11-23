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
import os
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


def _is_production_environment() -> bool:
    for var in ("SCHOLARZONE_ENV", "ENVIRONMENT", "APP_ENV", "ENV"):
        value = (os.getenv(var) or "").strip().lower()
        if value in {"production", "prod", "production-like"}:
            return True
    return False


def _recording_provider_allowed(config: "GatewayConfig") -> bool:
    if getattr(config, "allow_recording_provider", False):
        return True
    if getattr(config, "production", False):
        return False
    if _is_production_environment():
        return False
    return True


@dataclass
class GatewayConfig:
    """Configuration for the gateway."""

    registry: list[ModelSpec] = field(default_factory=list)
    policies: dict[str, RoutingPolicy] = field(default_factory=dict)
    default_provider: ModelProvider | None = None
    enabled: bool = False
    production: bool = False
    allow_recording_provider: bool = False

    def __post_init__(self) -> None:
        from .providers import RecordingProvider
        if isinstance(self.default_provider, RecordingProvider) and not _recording_provider_allowed(self):
            raise ValueError("RecordingProvider is test-only and cannot be selected in production configuration.")


class AIGateway:
    """Provider-independent AI gateway."""

    def __init__(self, config: GatewayConfig | None = None):
        self._config = config or GatewayConfig()
        from .providers import RecordingProvider
        if isinstance(self._config.default_provider, RecordingProvider) and not _recording_provider_allowed(self._config):
            raise ValueError("RecordingProvider is test-only and cannot be selected in production configuration.")
        self._provider: ModelProvider = self._config.default_provider or DisabledProvider()
        self._lock = threading.Lock()
        self._usage: list[dict] = []
        self._timed_out_workers: set[threading.Thread] = set()

    @property
    def enabled(self) -> bool:
        return self._config.enabled and not isinstance(self._provider, DisabledProvider)

    def set_provider(self, provider: ModelProvider) -> None:
        from .providers import RecordingProvider
        if isinstance(provider, RecordingProvider) and not _recording_provider_allowed(self._config):
            raise ValueError("RecordingProvider is test-only and cannot be selected in production configuration.")
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

        # Ensure request carries the cancel event for providers that honour it.
        from dataclasses import replace as _replace
        request = _replace(request, cancel_event=cancel_event if cancel_event is not None else request.cancel_event)

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
                # Enforce timeout via a worker thread.
                import threading as _threading
                outcome: dict = {}

                def _run():
                    try:
                        outcome["result"] = self._provider.generate(request, model)
                    except BaseException as exc:  # noqa: BLE001
                        outcome["exc"] = exc

                worker = _threading.Thread(target=_run, daemon=True)
                worker.start()
                timeout = request.timeout_seconds or policy.timeout_seconds
                worker.join(timeout=timeout)
                if worker.is_alive():
                    # Best-effort cancellation; thread may linger. Track until it terminates.
                    if request.cancel_event is not None:
                        request.cancel_event.set()
                    with self._lock:
                        self._timed_out_workers.add(worker)
                    return ProviderResult(
                        mode="configured",
                        used=False,
                        failure="timeout",
                        latency_ms=elapsed_ms(started),
                        model=model.id,
                        provider=self._provider.name,
                    )
                if "exc" in outcome:
                    raise outcome["exc"]
                result = outcome["result"]
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

    @property
    def pending_timed_out_workers(self) -> int:
        with self._lock:
            alive = {w for w in self._timed_out_workers if w.is_alive()}
            self._timed_out_workers = alive
            return len(alive)

    def usage_summary(self) -> list[dict]:
        with self._lock:
            return list(self._usage)
