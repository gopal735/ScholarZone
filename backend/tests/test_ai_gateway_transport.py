"""Real HTTPX transport regression tests for the AI gateway (local loopback only)."""

from __future__ import annotations

import http.server
import socketserver
import threading
import time

import pytest

from app.services.ai_gateway import (
    AIGateway,
    GatewayConfig,
    GatewayRequest,
    ModelSpec,
)
from app.services.ai_gateway import providers as providers_mod
from app.services.ai_gateway.providers import OpenAICompatibleProvider
from app.services.ai_gateway.gateway import ProviderCapacityLease


class _Server:
    def __init__(self, handler):
        socketserver.ThreadingTCPServer.allow_reuse_address = True
        self.httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def _make_handler(modes):
    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            mode = "normal"
            parts = self.path.strip("/").split("/")
            if parts and parts[0] in modes:
                mode = parts[0]
            length = int(self.headers.get("Content-Length", 0))
            self.rfile.read(length)
            if mode == "normal":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                for i in range(3):
                    chunk = 'data: {"choices":[{"delta":{"content":"%s"}}]}\n\n' % chr(ord("a") + i)
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
                    time.sleep(0.05)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            elif mode == "slow_headers":
                time.sleep(2.0)
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n')
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            elif mode == "blocked_body":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"first"}}]}\n\n')
                self.wfile.flush()
                time.sleep(10.0)
            elif mode == "many_chunks":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for i in range(200):
                    chunk = 'data: {"choices":[{"delta":{"content":"%s"}}]}\n\n' % ("x" * 2048)
                    self.wfile.write(chunk.encode())
                    self.wfile.flush()
                    time.sleep(0.01)
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self.send_response(404)
                self.end_headers()

    return H


@pytest.fixture
def server():
    modes = {"normal", "slow_headers", "blocked_body", "many_chunks"}
    srv = _Server(_make_handler(modes))
    providers_mod._LAST_OUTPUT_QUEUE = None
    yield srv
    srv.close()


def _wait_queue_closed(timeout=10.0):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        q = providers_mod._LAST_OUTPUT_QUEUE
        if q is not None and getattr(q, "_closed", False):
            return True
        time.sleep(0.05)
    return False


def test_normal_completion(server):
    base_url = "http://127.0.0.1:%d/normal/v1" % server.port
    provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=5.0)
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=5.0))
    gw.set_provider(provider)
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=5.0)
    chunks = list(gw.generate_stream("general_guidance", req))
    assert chunks == ["a", "b", "c"]
    assert _wait_queue_closed(5.0)
    q = providers_mod._LAST_OUTPUT_QUEUE
    assert q is not None
    assert q._bytes == 0
    assert q._closed is True


def test_slow_headers_timeout(server):
    base_url = "http://127.0.0.1:%d/slow_headers/v1" % server.port
    provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=0.5)
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=0.5))
    gw.set_provider(provider)
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=0.5)
    with pytest.raises(RuntimeError) as ei:
        list(gw.generate_stream("general_guidance", req))
    assert "timeout" in str(ei.value).lower()
    assert _wait_queue_closed(5.0)


def test_blocked_body_timeout(server):
    base_url = "http://127.0.0.1:%d/blocked_body/v1" % server.port
    provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=0.5)
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=0.5))
    gw.set_provider(provider)
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=0.5)
    with pytest.raises(RuntimeError) as ei:
        list(gw.generate_stream("general_guidance", req))
    assert "timeout" in str(ei.value).lower()
    assert _wait_queue_closed(5.0)


def test_queue_saturation_backpressure(server):
    base_url = "http://127.0.0.1:%d/many_chunks/v1" % server.port
    provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=2.0)
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=2.0))
    gw.set_provider(provider)
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=1000, timeout_seconds=2.0,
                         cancel_event=threading.Event())
    gen = gw.generate_stream("general_guidance", req)
    # force execution
    first = next(gen)
    assert isinstance(first, str)
    # pause consumer; wait for queue saturation
    max_items_seen = 0
    max_bytes_seen = 0
    deadline = time.perf_counter() + 5.0
    while time.perf_counter() < deadline:
        q = providers_mod._LAST_OUTPUT_QUEUE
        if q is not None:
            with q._lock:
                max_items_seen = max(max_items_seen, len(q._items))
                max_bytes_seen = max(max_bytes_seen, q._bytes)
            if max_items_seen >= 16:
                break
        time.sleep(0.05)
    q = providers_mod._LAST_OUTPUT_QUEUE
    assert q is not None
    assert max_items_seen <= 16
    assert max_bytes_seen <= 256 * 1024
    # cancel interrupts producer wait
    req.cancel_event.set()
    with pytest.raises(RuntimeError) as ei:
        # drain
        for _ in gen:
            pass
    assert "cancel" in str(ei.value).lower() or "timeout" in str(ei.value).lower()
    try:
        gen.close()
    except Exception:
        pass
    assert _wait_queue_closed(5.0)
    q = providers_mod._LAST_OUTPUT_QUEUE
    assert q._bytes == 0


def test_capacity_one_acceptance(server):
    # Instrument ProviderCapacityLease.release to pause before releasing for A.
    original_release = ProviderCapacityLease.release
    release_reached = threading.Event()
    allow_release = threading.Event()
    release_calls = {"n": 0}
    target_lease = {"obj": None}

    def patched_release(self):
        if target_lease["obj"] is None:
            target_lease["obj"] = self
            release_calls["n"] += 1
            release_reached.set()
            allow_release.wait(timeout=10.0)
            return original_release(self)
        release_calls["n"] += 1
        return original_release(self)

    ProviderCapacityLease.release = patched_release
    try:
        base_url = "http://127.0.0.1:%d/blocked_body/v1" % server.port
        provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=0.5)
        reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
        gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=0.5))
        gw._max_provider_workers = 1
        gw._worker_semaphore = threading.BoundedSemaphore(1)
        gw.set_provider(provider)
        reqA = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=0.5)

        resultA = {}
        def runA():
            try:
                list(gw.generate_stream("general_guidance", reqA))
                resultA["ok"] = True
            except Exception as e:
                resultA["err"] = str(e)
        tA = threading.Thread(target=runA, daemon=True)
        tA.start()

        assert release_reached.wait(timeout=5.0), "A never reached lease release boundary"
        leaseA = target_lease["obj"]
        assert leaseA is not None
        assert leaseA.released is False
        # worker thread still alive (blocked in patched_release)
        assert tA.is_alive() is True

        # B cannot acquire capacity while A holds it
        base_url2 = "http://127.0.0.1:%d/normal/v1" % server.port
        provider2 = OpenAICompatibleProvider(api_key="k", base_url=base_url2, timeout_seconds=5.0)
        gw.set_provider(provider2)
        reqB = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=5.0)
        try:
            list(gw.generate_stream("general_guidance", reqB))
            b_ok = True
        except RuntimeError as e:
            b_ok = False
            assert "capacity" in str(e).lower() or "exhausted" in str(e).lower()
        assert b_ok is False

        # Release A
        allow_release.set()
        tA.join(timeout=5.0)
        assert tA.is_alive() is False
        assert leaseA.released is True
        assert release_calls["n"] == 1

        # C succeeds
        base_url3 = "http://127.0.0.1:%d/normal/v1" % server.port
        provider3 = OpenAICompatibleProvider(api_key="k", base_url=base_url3, timeout_seconds=5.0)
        gw2 = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=5.0))
        gw2._max_provider_workers = 1
        gw2._worker_semaphore = threading.BoundedSemaphore(1)
        gw2.set_provider(provider3)
        reqC = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=5.0)
        chunks = list(gw2.generate_stream("general_guidance", reqC))
        assert chunks == ["a", "b", "c"]
    finally:
        ProviderCapacityLease.release = original_release
        allow_release.set()
