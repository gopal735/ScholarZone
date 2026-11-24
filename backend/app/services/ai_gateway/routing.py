"""Model routing policy for the ScholarZone AI gateway.

A routing policy maps a task kind to a set of required capabilities and a
preferred cost tier. The gateway resolves the policy to a concrete model from
the configured registry, falling back to cheaper models only when the required
capabilities are preserved. Silent downgrades are forbidden: if no configured
model supports the required capabilities, the gateway reports unavailability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .capabilities import Capability, ModelSpec


@dataclass(frozen=True)
class RoutingPolicy:
    """Declarative routing for one task kind."""

    task_kind: str
    required_capabilities: frozenset[Capability]
    preferred_cost_tier: int = 0
    allow_fallback: bool = True
    max_output_tokens: int = 400
    timeout_seconds: float = 6.0


#: Default policies. These are conservative: simple tasks use cheap models,
#: complex reasoning uses higher tiers. Deterministic tasks bypass the gateway
#: entirely and are not listed here.
DEFAULT_POLICIES: dict[str, RoutingPolicy] = {
    "intent_classification": RoutingPolicy(
        task_kind="intent_classification",
        required_capabilities=frozenset(),
        preferred_cost_tier=0,
        max_output_tokens=64,
        timeout_seconds=3.0,
    ),
    "eligibility_reasoning": RoutingPolicy(
        task_kind="eligibility_reasoning",
        required_capabilities=frozenset({Capability.REASONING, Capability.STRUCTURED_OUTPUT}),
        preferred_cost_tier=2,
        max_output_tokens=800,
        timeout_seconds=15.0,
    ),
    "document_analysis": RoutingPolicy(
        task_kind="document_analysis",
        required_capabilities=frozenset({Capability.LONG_CONTEXT, Capability.STRUCTURED_OUTPUT}),
        preferred_cost_tier=2,
        max_output_tokens=1200,
        timeout_seconds=20.0,
    ),
    "outreach_drafting": RoutingPolicy(
        task_kind="outreach_drafting",
        required_capabilities=frozenset({Capability.REASONING}),
        preferred_cost_tier=1,
        max_output_tokens=600,
        timeout_seconds=10.0,
    ),
    "general_guidance": RoutingPolicy(
        task_kind="general_guidance",
        required_capabilities=frozenset(),
        preferred_cost_tier=0,
        max_output_tokens=400,
        timeout_seconds=6.0,
    ),
}


def resolve_model(
    policy: RoutingPolicy,
    registry: Iterable[ModelSpec],
    *,
    model_override: str | None = None,
) -> ModelSpec | None:
    """Resolve a policy to a concrete model from the registry.

    Returns ``None`` when no model supports the required capabilities, which
    the caller must surface as unavailability rather than silently degrading.
    """
    candidates = [m for m in registry if m.enabled and m.supports(policy.required_capabilities)]

    if model_override:
        for m in candidates:
            if m.id == model_override:
                return m
        # Override requested but unavailable -> None (honest)
        return None

    if not candidates:
        return None

    # Prefer the configured cost tier, then cheapest.
    preferred = [m for m in candidates if m.cost_tier == policy.preferred_cost_tier]
    if preferred:
        pool = preferred
    elif policy.allow_fallback:
        pool = candidates
    else:
        return None
    if not pool:
        return None
    return min(pool, key=lambda m: (m.cost_tier, m.id))
