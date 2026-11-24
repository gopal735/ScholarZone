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
from .routing import DEFAULT_POLICIES, RoutingPolicy, resolve_model

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
    policies: dict[str, RoutingPolicy] = field(default_factory=lambda: {k: v for k, v in DEFAULT_POLICIES.items()})
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
        self._max_provider_workers = 4
        self._worker_semaphore = threading.BoundedSemaphore(self._max_provider_workers)

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
        started = __import__("time").perf_counter()

        effective_model_override = model_override if model_override is not None else getattr(request, "model_override", None)
        effective_cancel_event = cancel_event if cancel_event is not None else getattr(request, "cancel_event", None)

        policy = self.get_policy(task_kind)
        if policy is None:
            policy = RoutingPolicy(task_kind=task_kind, required_capabilities=frozenset())

        effective_required = policy.required_capabilities | set(getattr(request, "required_capabilities", frozenset()) or frozenset())
        effective_policy = RoutingPolicy(
            task_kind=policy.task_kind,
            required_capabilities=frozenset(effective_required),
            preferred_cost_tier=policy.preferred_cost_tier,
            allow_fallback=policy.allow_fallback,
            max_output_tokens=policy.max_output_tokens,
            timeout_seconds=policy.timeout_seconds,
        )
        model = resolve_model(effective_policy, self._config.registry, model_override=effective_model_override)
        policy = effective_policy

        # Clamp caller output-token limit to the (possibly stricter) policy cap.
        model_cap = model.max_output_tokens if model is not None and getattr(model, "max_output_tokens", None) is not None else effective_policy.max_output_tokens
        effective_max_tokens = min(
            getattr(request, "max_output_tokens", effective_policy.max_output_tokens),
            effective_policy.max_output_tokens,
            model_cap,
        )
        effective_timeout = (
            request.timeout_seconds
            if getattr(request, "timeout_seconds", None) is not None
            else effective_policy.timeout_seconds
        )

        if not self._config.enabled:
            return ProviderResult(mode="disabled", used=False, failure=None, latency_ms=elapsed_ms(started))

        with self._lock:
            provider = self._provider

        if model is None:
            return ProviderResult(
                mode="configured",
                used=False,
                failure="unavailable",
                latency_ms=elapsed_ms(started),
            )

        if not model.supports(effective_required):
            return ProviderResult(
                mode="configured",
                used=False,
                failure="capability_mismatch",
                latency_ms=elapsed_ms(started),
                model=model.id,
                provider=provider.name,
            )

        if effective_cancel_event is not None and effective_cancel_event.is_set():
            return ProviderResult(
                mode="configured",
                used=False,
                failure="cancelled",
                latency_ms=elapsed_ms(started),
            )

        from dataclasses import replace as _replace
        request = _replace(
            request,
            required_capabilities=frozenset(effective_required),
            max_output_tokens=effective_max_tokens,
            timeout_seconds=effective_timeout,
            cancel_event=effective_cancel_event if effective_cancel_event is not None else request.cancel_event,
        )

        last_failure = None
        for attempt in range(MAX_RETRIES + 1):
            if effective_cancel_event is not None and effective_cancel_event.is_set():
                return ProviderResult(
                    mode="configured",
                    used=False,
                    failure="cancelled",
                    latency_ms=elapsed_ms(started),
                )
            try:
                outcome: dict = {}

                def _run():
                    try:
                        outcome["result"] = provider.generate(request, model)
                    except BaseException as exc:  # noqa: BLE001
                        outcome["exc"] = exc
                    finally:
                        _late_result = outcome.get("result")
                        if _late_result is not None and (
                            getattr(_late_result, "prompt_tokens", None) is not None
                            or getattr(_late_result, "completion_tokens", None) is not None
                        ):
                            with self._lock:
                                self._usage.append({
                                    "task_kind": task_kind,
                                    "model": model.id,
                                    "provider": provider.name,
                                    "prompt_tokens": _late_result.prompt_tokens,
                                    "completion_tokens": _late_result.completion_tokens,
                                })
                        self._worker_semaphore.release()

                acquired = self._worker_semaphore.acquire(blocking=False)
                if not acquired:
                    return ProviderResult(
                        mode="configured",
                        used=False,
                        failure="worker_capacity_exhausted",
                        latency_ms=elapsed_ms(started),
                        model=model.id,
                        provider=provider.name,
                    )

                worker = threading.Thread(target=_run, daemon=True)
                try:
                    worker.start()
                except Exception:  # noqa: BLE001
                    self._worker_semaphore.release()
                    raise

                timeout = request.timeout_seconds if request.timeout_seconds is not None else policy.timeout_seconds
                worker.join(timeout=timeout)
                if worker.is_alive():
                    if request.cancel_event is not None:
                        request.cancel_event.set()
                    with self._lock:
                        self._timed_out_workers = {w for w in self._timed_out_workers if w.is_alive()}
                        self._timed_out_workers.add(worker)
                    return ProviderResult(
                        mode="configured",
                        used=False,
                        failure="timeout",
                        latency_ms=elapsed_ms(started),
                        model=model.id,
                        provider=provider.name,
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
                if validator is not None:
                    if result.text is None or not validator(result.text):
                        return ProviderResult(
                            mode=result.mode,
                            used=False,
                            text=result.text,
                            failure="malformed_response",
                            latency_ms=elapsed_ms(started),
                            model=model.id,
                            provider=provider.name,
                        )
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
                    provider=provider.name,
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
