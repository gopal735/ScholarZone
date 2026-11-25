"""Factory for the ScholarZone AI gateway.

Configuration is read from server-side environment variables only. No
credentials are ever exposed to the browser or logged.
"""

from __future__ import annotations

import os
import threading
from urllib.parse import urlparse

from .capabilities import Capability, ModelSpec
from .gateway import AIGateway, GatewayConfig
from .providers import OpenAICompatibleProvider, DisabledProvider

_SINGLETON: AIGateway | None = None
_SINGLETON_LOCK = threading.Lock()


def _is_production() -> bool:
    env = (os.getenv("SCHOLARZONE_ENVIRONMENT") or os.getenv("ENVIRONMENT") or "").strip().lower()
    return env == "production"


def _allow_http_base_url(host: str) -> bool:
    host = (host or "").lower()
    return host in {"localhost", "127.0.0.1", "::1", "testserver"}


def _validate_base_url(base_url: str) -> bool:
    try:
        parsed = urlparse(base_url)
    except Exception:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc or parsed.username or parsed.password:
        return False
    if parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "http" and not _allow_http_base_url(parsed.hostname or ""):
        return False
    return True


def build_ai_gateway() -> AIGateway:
    # Only the dedicated new-provider key enables Dream AI Mentor 2.
    api_key = (os.getenv("SCHOLARZONE_AI_PROVIDER_KEY") or "").strip()
    registry = []
    provider = DisabledProvider()
    enabled = False

    if api_key:
        base_url = (os.getenv("SCHOLARZONE_AI_PROVIDER_BASE_URL") or "https://api.openai.com/v1").strip().rstrip("/")
        model_id = (os.getenv("SCHOLARZONE_AI_PROVIDER_MODEL") or "").strip()
        if not model_id:
            model_id = "gpt-4o-mini"
        try:
            timeout = float(os.getenv("SCHOLARZONE_AI_PROVIDER_TIMEOUT", "30"))
        except (TypeError, ValueError):
            timeout = 30.0
        try:
            max_tokens = int(os.getenv("SCHOLARZONE_AI_PROVIDER_MAX_TOKENS", "800"))
        except (TypeError, ValueError):
            max_tokens = 800

        if not _validate_base_url(base_url):
            # Invalid/insecure configuration must not silently enable a provider.
            provider = DisabledProvider()
            enabled = False
        else:
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
    global _SINGLETON
    if _SINGLETON is not None:
        return _SINGLETON
    with _SINGLETON_LOCK:
        if _SINGLETON is None:
            _SINGLETON = build_ai_gateway()
        return _SINGLETON


def reset_ai_gateway_singleton() -> None:
    global _SINGLETON
    with _SINGLETON_LOCK:
        _SINGLETON = None


__all__ = ["build_ai_gateway", "get_ai_gateway", "reset_ai_gateway_singleton"]