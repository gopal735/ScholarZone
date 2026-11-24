"""Factory for the ScholarZone AI gateway.

Configuration is read from server-side environment variables only. No
credentials are ever exposed to the browser or logged.
"""

from __future__ import annotations

import os

from .capabilities import Capability, ModelSpec
from .gateway import AIGateway, GatewayConfig
from .providers import OpenAICompatibleProvider, DisabledProvider


def _is_production() -> bool:
    env = (os.getenv("SCHOLARZONE_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return env == "production"


def build_ai_gateway() -> AIGateway:
    api_key = (os.getenv("SCHOLARZONE_AI_PROVIDER_KEY") or os.getenv("SCHOLARZONE_MENTOR_PROVIDER_KEY") or "").strip()
    registry = []
    provider = DisabledProvider()
    enabled = False

    if api_key:
        base_url = (os.getenv("SCHOLARZONE_AI_PROVIDER_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
        model_id = (os.getenv("SCHOLARZONE_AI_PROVIDER_MODEL") or "gpt-4o-mini").strip()
        try:
            timeout = float(os.getenv("SCHOLARZONE_AI_PROVIDER_TIMEOUT", "30"))
        except (TypeError, ValueError):
            timeout = 30.0
        try:
            max_tokens = int(os.getenv("SCHOLARZONE_AI_PROVIDER_MAX_TOKENS", "800"))
        except (TypeError, ValueError):
            max_tokens = 800
        provider = OpenAICompatibleProvider(
            api_key=api_key,
            base_url=base_url,
            default_model=model_id,
            timeout_seconds=timeout,
        )
        registry.append(
            ModelSpec(
                id=model_id,
                provider="openai_compatible",
                display_name=model_id,
                capabilities=frozenset(
                    {Capability.REASONING, Capability.STRUCTURED_OUTPUT, Capability.STREAMING}
                ),
                context_window=8000,
                max_output_tokens=max_tokens,
                cost_tier=1,
                enabled=True,
            )
        )
        enabled = True

    config = GatewayConfig(
        registry=registry,
        default_provider=provider,
        enabled=enabled,
        production=_is_production(),
    )
    return AIGateway(config)


def get_ai_gateway() -> AIGateway:
    return build_ai_gateway()


__all__ = ["build_ai_gateway", "get_ai_gateway"]