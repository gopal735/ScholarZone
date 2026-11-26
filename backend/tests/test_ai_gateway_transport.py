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
from app.services.ai_gateway.providers import OpenAICompatibleProvider


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
            else:
                self.send_response(404)
                self.end_headers()

    return H


@pytest.fixture
def server():
    modes = {"normal", "slow_headers", "blocked_body"}
    srv = _Server(_make_handler(modes))
    yield srv
    srv.close()


def test_normal_completion(server):
    base_url = "http://127.0.0.1:%d/normal/v1" % server.port
    provider = OpenAICompatibleProvider(api_key="k", base_url=base_url, timeout_seconds=5.0)
    reg = [ModelSpec(id="m1", provider="p", display_name="m1", capabilities=frozenset())]
    # enable streaming capability not required for provider
    gw = AIGateway(GatewayConfig(enabled=True, registry=reg, provider_timeout_seconds=5.0))
    gw.set_provider(provider)
    req = GatewayRequest(system_instruction="s", question="q", context_blocks=(), max_output_tokens=10, timeout_seconds=5.0)
    chunks = list(gw.generate_stream("general_guidance", req))
    assert chunks == ["a", "b", "c"]
    # worker should have exited; capacity available
    assert gw.pending_timed_out_workers == 0


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
    # allow worker to finish
    time.sleep(0.5)
    assert gw.pending_timed_out_workers == 0
