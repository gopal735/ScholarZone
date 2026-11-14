from __future__ import annotations

import httpx
import httpcore
import pytest
import asyncio

from app.services.outbound_security import (
    DestinationPolicy,
    PinnedSyncBackend,
    SSRFSafeClient,
    UnsafeOutboundTarget,
)
from app.services.outbound_proxy import OutboundProxy


def public_test_policy(host="public.example", address="8.8.8.8"):
    return DestinationPolicy(lambda _host, _port: [address])


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/",
        "http://api.localhost/",
        "http://127.0.0.1/",
        "http://10.0.0.5/",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://[fc00::1]/",
        "http://[fe80::1]/",
        "http://[::ffff:127.0.0.1]/",
        "file:///etc/passwd",
        "ftp://example.com/file",
        "http://user:pass@example.com/",
        "http://127.1/",
        "http://2130706433/",
        "http://0x7f000001/",
        "http://example.com:99999/",
        "http://singlelabel/",
    ],
)
def test_url_policy_rejects_unsafe_forms_before_dns(url):
    calls = []
    policy = DestinationPolicy(lambda host, port: calls.append((host, port)) or ["8.8.8.8"])

    with pytest.raises(UnsafeOutboundTarget):
        policy.validate_url(url)

    # Literal and malformed targets never make a DNS request.
    assert calls == []


@pytest.mark.parametrize("address", ["127.0.0.1", "10.2.3.4", "169.254.169.254", "::1", "fc00::1", "fe80::1", "224.0.0.1", "::ffff:10.1.2.3"])
def test_dns_results_must_all_be_global(address):
    policy = DestinationPolicy(lambda _host, _port: [address])
    with pytest.raises(ValueError):
        policy.resolve_public("public.example", 443)


def test_mixed_public_and_private_dns_answer_is_rejected():
    policy = DestinationPolicy(lambda _host, _port: ["8.8.8.8", "192.168.1.1"])
    with pytest.raises(ValueError):
        policy.resolve_public("public.example", 443)


def test_idna_host_is_normalized_before_dns():
    seen = []
    policy = DestinationPolicy(lambda host, port: seen.append((host, port)) or ["8.8.8.8"])
    policy.resolve_public("bücher.example", 443)
    assert seen == [("xn--bcher-kva.example", 443)]


class FakeStream:
    def __init__(self, peer):
        self.peer = (peer, 443)
        self.closed = False

    def get_extra_info(self, name):
        return self.peer if name == "server_addr" else None

    def close(self):
        self.closed = True


class FakeBackend:
    def __init__(self, peer=None):
        self.peer = peer
        self.connected = []

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.connected.append((host, port))
        return FakeStream(self.peer or host)


def test_tcp_connect_uses_the_validated_ip_and_verifies_the_peer():
    delegate = FakeBackend()
    backend = PinnedSyncBackend(DestinationPolicy(lambda _host, _port: ["8.8.8.8"]), delegate)

    backend.connect_tcp("public.example", 443)

    assert delegate.connected == [("8.8.8.8", 443)]


def test_dns_rebinding_is_rechecked_before_each_connection():
    answers = iter([["8.8.8.8"], ["127.0.0.1"]])
    policy = DestinationPolicy(lambda _host, _port: next(answers))
    delegate = FakeBackend()
    backend = PinnedSyncBackend(policy, delegate)

    backend.connect_tcp("public.example", 443)
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("public.example", 443)

    assert delegate.connected == [("8.8.8.8", 443)]


def test_mismatched_connected_peer_is_closed_and_rejected():
    delegate = FakeBackend(peer="1.1.1.1")
    backend = PinnedSyncBackend(DestinationPolicy(lambda _host, _port: ["8.8.8.8"]), delegate)

    with pytest.raises(httpcore.ConnectError, match="peer differs"):
        backend.connect_tcp("public.example", 443)


def test_private_redirect_is_rejected_before_second_request():
    sent = []
    policy = public_test_policy()

    def mock_send(request):
        sent.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"}, request=request)

    with SSRFSafeClient(
        policy=policy,
        follow_redirects=True,
        transport=httpx.MockTransport(mock_send),
    ) as client:
        with pytest.raises(UnsafeOutboundTarget):
            client.get("https://public.example/start")

    assert sent == ["https://public.example/start"]


def test_https_downgrade_redirect_is_rejected():
    policy = public_test_policy()

    def mock_send(request):
        return httpx.Response(302, headers={"location": "http://public.example/plain"}, request=request)

    with SSRFSafeClient(
        policy=policy,
        follow_redirects=True,
        transport=httpx.MockTransport(mock_send),
    ) as client:
        with pytest.raises(UnsafeOutboundTarget, match="HTTPS-to-HTTP"):
            client.get("https://public.example/start")


def test_redirect_hop_limit_is_enforced():
    policy = public_test_policy()

    def mock_send(request):
        current = int(request.url.path.removeprefix("/"))
        return httpx.Response(302, headers={"location": f"/{current + 1}"}, request=request)

    with SSRFSafeClient(
        policy=policy,
        max_redirects=2,
        follow_redirects=True,
        transport=httpx.MockTransport(mock_send),
    ) as client:
        with pytest.raises(httpx.TooManyRedirects):
            client.get("https://public.example/0")


def test_rejected_literal_target_never_reaches_transport():
    calls = []
    policy = DestinationPolicy(lambda _host, _port: ["8.8.8.8"])
    with SSRFSafeClient(policy=policy, transport=httpx.MockTransport(lambda req: calls.append(req))) as client:
        with pytest.raises(UnsafeOutboundTarget):
            client.get("http://169.254.169.254/latest/meta-data/")
    assert calls == []


def test_browser_proxy_blocks_local_subresource_without_connecting_to_it():
    async def exercise():
        received: list[bytes] = []

        async def target(reader, writer):
            received.append(await reader.read(1024))
            writer.close()
            await writer.wait_closed()

        target_server = await asyncio.start_server(target, "127.0.0.1", 0)
        target_port = target_server.sockets[0].getsockname()[1]
        proxy = OutboundProxy()
        proxy_url = await proxy.start()
        proxy_port = int(proxy_url.rsplit(":", 1)[1])
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", proxy_port)
            writer.write(
                f"GET http://127.0.0.1:{target_port}/pixel.png HTTP/1.1\r\n"
                f"Host: 127.0.0.1:{target_port}\r\nConnection: close\r\n\r\n".encode()
            )
            await writer.drain()
            reply = await reader.read(1024)
            writer.close()
            await writer.wait_closed()
            assert reply.startswith(b"HTTP/1.1 403")
            assert received == []
        finally:
            await proxy.close()
            target_server.close()
            await target_server.wait_closed()

    asyncio.run(exercise())
