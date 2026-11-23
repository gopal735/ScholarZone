"""ScholarZone AI gateway package."""

from .capabilities import Capability, ModelSpec, ProviderHealth, ALL_CAPABILITIES
from .providers import (
    DisabledProvider,
    GatewayRequest,
    ModelProvider,
    ProviderResult,
    RecordingProvider,
    credential_present,
    sanitise_provider_error,
    elapsed_ms,
    FAILURE_TIMEOUT,
    FAILURE_UNAVAILABLE,
    FAILURE_MALFORMED,
    FAILURE_RATE_LIMITED,
    FAILURE_CAPABILITY_MISMATCH,
    FAILURE_CANCELLED,
    PROVIDER_MODE_DISABLED,
    PROVIDER_MODE_CONFIGURED,
)
from .routing import RoutingPolicy, DEFAULT_POLICIES, resolve_model
from .gateway import AIGateway, GatewayConfig

__all__ = (
    "AIGateway",
    "GatewayConfig",
    "Capability",
    "ModelSpec",
    "ProviderHealth",
    "ALL_CAPABILITIES",
    "DisabledProvider",
    "GatewayRequest",
    "ModelProvider",
    "ProviderResult",
    "RecordingProvider",
    "credential_present",
    "sanitise_provider_error",
    "elapsed_ms",
    "RoutingPolicy",
    "DEFAULT_POLICIES",
    "resolve_model",
)
