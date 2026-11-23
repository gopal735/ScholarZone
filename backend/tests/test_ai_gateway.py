"""Tests for the AI gateway."""

from __future__ import annotations

import threading

from app.services.ai_gateway import (
    AIGateway,
    GatewayConfig,
    GatewayRequest,
    Capability,
    ModelSpec,
    RoutingPolicy,
    DisabledProvider,
    RecordingProvider,
    resolve_model,
    DEFAULT_POLICIES,
)


def test_disabled_provider_returns_not_used():
    gw = AIGateway(GatewayConfig(enabled=False))
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=())
    res = gw.generate("general_guidance", req)
    assert res.used is False
    assert res.failure is None  # disabled is not a failure


def test_resolve_model_capability_mismatch():
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    policy = RoutingPolicy(task_kind="x", required_capabilities=frozenset({Capability.REASONING}))
    assert resolve_model(policy, reg) is None


def test_resolve_model_picks_cheapest():
    reg = [
        ModelSpec(id="cheap", provider="p", display_name="cheap", cost_tier=0, capabilities=frozenset()),
        ModelSpec(id="expensive", provider="p", display_name="expensive", cost_tier=2, capabilities=frozenset()),
    ]
    policy = RoutingPolicy(task_kind="x", required_capabilities=frozenset())
    m = resolve_model(policy, reg)
    assert m.id == "cheap"


def test_gateway_unavailable_when_no_model():
    gw = AIGateway(GatewayConfig(enabled=True, registry=[]))
    gw.set_provider(RecordingProvider())
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=())
    res = gw.generate("eligibility_reasoning", req)
    assert res.used is False
    assert res.failure == "unavailable"


def test_gateway_success_with_recording():
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset({Capability.REASONING, Capability.STRUCTURED_OUTPUT}))]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, policies=DEFAULT_POLICIES))
    gw.set_provider(RecordingProvider(reply="hello"))
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), required_capabilities=frozenset({Capability.REASONING}))
    res = gw.generate("eligibility_reasoning", req)
    assert res.used is True
    assert res.text == "hello"


def test_gateway_validator_rejects_malformed():
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset({Capability.REASONING, Capability.STRUCTURED_OUTPUT}))]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, policies=DEFAULT_POLICIES))
    gw.set_provider(RecordingProvider(reply="bad"))
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=())
    res = gw.generate("eligibility_reasoning", req, validator=lambda t: t == "good")
    assert res.used is False
    assert res.failure == "malformed_response"


def test_gateway_cancel():
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg))
    gw.set_provider(RecordingProvider())
    ev = threading.Event()
    ev.set()
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=())
    res = gw.generate("general_guidance", req, cancel_event=ev)
    assert res.failure == "cancelled"


def test_health():
    gw = AIGateway(GatewayConfig(enabled=False))
    h = gw.health()
    assert len(h) == 1
    assert h[0].available is True
