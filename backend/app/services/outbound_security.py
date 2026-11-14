"""One SSRF policy for outbound HTTP used by ScholarZone.

Every hostname is resolved at connection time. All returned addresses must be
globally routable; the socket connects to one of those literal addresses and
the peer address is checked after connect. TLS still receives the original
hostname from httpcore, preserving certificate validation and SNI.

The HTTPX client handles redirects itself, one hop at a time, so each target is
validated before another request can reach the network. Environment proxies
are disabled because they would move destination resolution outside this
process and invalidate the pinned-peer guarantee.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import io
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx


class UnsafeOutboundTarget(httpx.RequestError):
    """An outbound URL or destination violates the shared egress policy."""


Resolver = Callable[[str, int], Iterable[str]]


def _resolve_system(host: str, port: int) -> tuple[str, ...]:
    try:
        rows = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError(f"DNS resolution failed for {host}") from exc
    return tuple(dict.fromkeys(row[4][0].split("%", 1)[0] for row in rows))


class DestinationPolicy:
    """Parse and resolve only public HTTP(S) destinations.

    ``resolver`` is injectable for deterministic tests. Production always uses
    the system resolver and pins its result in :class:`PinnedSyncBackend`.
    """

    _INTERNAL_SUFFIXES = (
        ".localhost", ".local", ".internal", ".lan", ".home", ".test",
    )
    allow_http = False

    def __init__(self, resolver: Resolver = _resolve_system) -> None:
        self._resolver = resolver

    @staticmethod
    def _public_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
        try:
            address = ipaddress.ip_address(value)
        except ValueError as exc:
            raise ValueError("destination did not resolve to an IP address") from exc
        mapped = getattr(address, "ipv4_mapped", None)
        if mapped is not None:
            address = mapped
        if not address.is_global or address.is_multicast or address.is_unspecified:
            raise ValueError("destination resolves to a non-public IP address")
        if isinstance(address, ipaddress.IPv6Address) and (address.sixtofour or address.teredo):
            raise ValueError("IPv6 transition addresses are not accepted")
        return address

    @classmethod
    def _normalize_host(cls, raw_host: str) -> tuple[str, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
        if not raw_host or "%" in raw_host:
            raise ValueError("missing or scoped host is not accepted")
        host = raw_host.rstrip(".").lower()
        if not host:
            raise ValueError("empty host is not accepted")

        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            ip = None

        if ip is not None:
            return host, cls._public_ip(host)

        # Reject resolver-dependent numeric forms (for example 127.1,
        # 2130706433, 0177.0.0.1, and 0x7f000001) rather than letting libc
        # reinterpret them as legacy IPv4 syntax.
        if re.fullmatch(r"(?:0x[0-9a-f]+|[0-9]+)(?:\.(?:0x[0-9a-f]+|[0-9]+))*", host, re.IGNORECASE):
            raise ValueError("ambiguous numeric host is not accepted")
        try:
            ascii_host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise ValueError("hostname is not valid IDNA") from exc
        if len(ascii_host) > 253 or any(not label or len(label) > 63 for label in ascii_host.split(".")):
            raise ValueError("hostname has an invalid DNS form")
        if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in ascii_host.split(".")):
            raise ValueError("hostname contains an invalid DNS label")
        if (
            "." not in ascii_host
            or ascii_host == "localhost"
            or ascii_host.endswith(cls._INTERNAL_SUFFIXES)
            or ascii_host in {"metadata.google", "metadata.google.internal", "instance-data.ec2.internal"}
        ):
            raise ValueError("internal hostname is not accepted")
        return ascii_host, None

    def validate_url(self, url: str | httpx.URL, *, request: httpx.Request | None = None) -> tuple[str, int, ipaddress.IPv4Address | ipaddress.IPv6Address | None]:
        rendered = str(url)
        try:
            parsed = urlsplit(rendered)
            if parsed.scheme.lower() not in {"http", "https"}:
                raise ValueError("only HTTP and HTTPS URLs are accepted")
            if parsed.username is not None or parsed.password is not None:
                raise ValueError("URL credentials are not accepted")
            if not parsed.hostname:
                raise ValueError("URL must include a host")
            if any(ord(char) < 0x20 or char == "\\" for char in rendered):
                raise ValueError("URL contains an ambiguous control character")
            host, literal_ip = self._normalize_host(parsed.hostname)
            port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
            if not 1 <= port <= 65535:
                raise ValueError("URL port is outside the valid range")
            return host, port, literal_ip
        except (ValueError, UnicodeError) as exc:
            raise UnsafeOutboundTarget(str(exc), request=request) from exc

    def resolve_public(self, host: str, port: int) -> tuple[ipaddress.IPv4Address | ipaddress.IPv6Address, ...]:
        normalized, literal = self._normalize_host(host)
        if literal is not None:
            return (literal,)
        try:
            results = tuple(self._public_ip(address) for address in self._resolver(normalized, port))
        except ValueError as exc:
            raise ValueError(f"unsafe DNS result for {normalized}: {exc}") from exc
        if not results:
            raise ValueError(f"DNS returned no addresses for {normalized}")
        return tuple(dict.fromkeys(results))


DEFAULT_POLICY = DestinationPolicy()


class PinnedSyncBackend(httpcore.SyncBackend):
    """Resolve, validate, and connect to the exact approved peer IP."""

    def __init__(self, policy: DestinationPolicy = DEFAULT_POLICY, delegate: httpcore.SyncBackend | None = None) -> None:
        self.policy = policy
        self.delegate = delegate or httpcore.SyncBackend()

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        try:
            addresses = self.policy.resolve_public(host, port)
        except ValueError as exc:
            raise httpcore.ConnectError(str(exc)) from exc
        # Each TCP attempt uses a literal validated address; no second resolver
        # lookup occurs inside socket.create_connection.
        last_error: Exception | None = None
        for address in addresses:
            try:
                stream = self.delegate.connect_tcp(
                    address.compressed, port, timeout, local_address, socket_options
                )
            except httpcore.ConnectError as exc:
                last_error = exc
                continue
            peer = stream.get_extra_info("server_addr")
            try:
                peer_ip = ipaddress.ip_address(peer[0].split("%", 1)[0])
                expected_ip = ipaddress.ip_address(address.compressed)
            except (TypeError, ValueError, IndexError) as exc:
                stream.close()
                raise httpcore.ConnectError("connected peer address could not be verified") from exc
            if peer_ip != expected_ip:
                stream.close()
                raise httpcore.ConnectError("connected peer differs from validated destination")
            return stream
        if last_error:
            raise last_error
        raise httpcore.ConnectError("no validated destination could be connected")

    def connect_unix_socket(self, path, timeout=None, socket_options=None):  # pragma: no cover - HTTP never uses UDS
        raise httpcore.ConnectError("Unix sockets are disabled for outbound HTTP")

    def sleep(self, seconds):
        return self.delegate.sleep(seconds)


class SSRFSafeTransport(httpx.HTTPTransport):
    """HTTPX transport with connection-pinned public destinations only."""

    def __init__(self, policy: DestinationPolicy = DEFAULT_POLICY, **kwargs) -> None:
        if kwargs.get("proxy") or kwargs.get("uds"):
            raise ValueError("proxies and Unix sockets are disabled by outbound policy")
        kwargs["trust_env"] = False
        kwargs["proxy"] = None
        super().__init__(**kwargs)
        # HTTPX 0.27-0.28 are the supported range in requirements.txt. Its
        # HTTPTransport owns this httpcore pool; the network backend is the
        # documented httpcore extension point for pinning TCP destinations.
        self.policy = policy
        self._pool._network_backend = PinnedSyncBackend(policy)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.policy.validate_url(request.url, request=request)
        return super().handle_request(request)


class SSRFSafeClient(httpx.Client):
    """Synchronous HTTP client with validated, bounded manual redirects."""

    def __init__(self, *, policy: DestinationPolicy = DEFAULT_POLICY, max_redirects: int = 5, transport: httpx.BaseTransport | None = None, **kwargs) -> None:
        if max_redirects < 0:
            raise ValueError("max_redirects must be non-negative")
        if kwargs.get("proxy") or kwargs.get("mounts"):
            raise ValueError("proxy transports and mounts are disabled by outbound policy")
        if transport is not None and not isinstance(transport, httpx.MockTransport):
            raise ValueError("custom transports are disabled; only non-networking MockTransport is accepted for tests")
        requested_redirects = bool(kwargs.pop("follow_redirects", False))
        # The base client must never process redirects internally; this class
        # validates each intermediate URL before making the following request.
        kwargs["follow_redirects"] = False
        kwargs["trust_env"] = False
        super().__init__(transport=transport or SSRFSafeTransport(policy), **kwargs)
        self._outbound_policy = policy
        self._outbound_follow_redirects = requested_redirects
        self._outbound_max_redirects = max_redirects

    def send(self, request: httpx.Request, *, stream: bool = False, auth=httpx.USE_CLIENT_DEFAULT, follow_redirects=httpx.USE_CLIENT_DEFAULT) -> httpx.Response:
        should_follow = (
            self._outbound_follow_redirects
            if follow_redirects is httpx.USE_CLIENT_DEFAULT or follow_redirects is None
            else bool(follow_redirects)
        )
        current = request
        history: list[httpx.Response] = []
        for hop in range(self._outbound_max_redirects + 1):
            self._outbound_policy.validate_url(current.url, request=current)
            response = super().send(current, stream=True, auth=auth, follow_redirects=False)
            if not should_follow or not response.is_redirect:
                response.history = history
                if not stream:
                    response.read()
                return response
            location = response.headers.get("location")
            if not location:
                response.history = history
                if not stream:
                    response.read()
                return response
            if hop >= self._outbound_max_redirects:
                response.close()
                raise httpx.TooManyRedirects("outbound redirect limit exceeded", request=current)
            next_url = current.url.join(location)
            self._outbound_policy.validate_url(next_url, request=current)
            if current.url.scheme == "https" and next_url.scheme == "http":
                response.close()
                raise UnsafeOutboundTarget("HTTPS-to-HTTP redirect is not accepted", request=current)
            next_request = self._build_redirect_request(current, response)
            response.close()
            history.append(response)
            current = next_request
        raise httpx.TooManyRedirects("outbound redirect limit exceeded", request=current)


def secure_client(*, policy: DestinationPolicy | None = None, **kwargs) -> SSRFSafeClient:
    """Construct a client that pins public destinations and checks redirects."""
    return SSRFSafeClient(policy=policy or DEFAULT_POLICY, **kwargs)


def secure_get(url: str, **kwargs) -> httpx.Response:
    """One-shot GET for existing module-level HTTPX call sites."""
    timeout = kwargs.pop("timeout", 10.0)
    follow_redirects = kwargs.pop("follow_redirects", False)
    max_redirects = kwargs.pop("max_redirects", 5)
    with secure_client(timeout=timeout, follow_redirects=follow_redirects, max_redirects=max_redirects) as client:
        return client.get(url, **kwargs)


def secure_head(url: str, **kwargs) -> httpx.Response:
    """One-shot HEAD for existing module-level HTTPX call sites."""
    timeout = kwargs.pop("timeout", 10.0)
    follow_redirects = kwargs.pop("follow_redirects", False)
    max_redirects = kwargs.pop("max_redirects", 5)
    with secure_client(timeout=timeout, follow_redirects=follow_redirects, max_redirects=max_redirects) as client:
        return client.head(url, **kwargs)


class _UrlopenResponse:
    def __init__(self, response: httpx.Response) -> None:
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        self._response.close()

    def read(self, amount: int = -1) -> bytes:
        content = self._response.read()
        return content if amount < 0 else content[:amount]

    @property
    def status(self) -> int:
        return self._response.status_code

    @property
    def code(self) -> int:
        return self._response.status_code

    def __getattr__(self, name):
        return getattr(self._response, name)


def secure_urlopen(
    request: urllib.request.Request | str,
    *,
    timeout: float = 10.0,
    policy: DestinationPolicy | None = None,
) -> _UrlopenResponse:
    """urllib-compatible adapter that applies the same pinned egress policy."""
    if isinstance(request, urllib.request.Request):
        url = request.full_url
        method = request.get_method()
        headers = dict(request.header_items())
        body = request.data
    else:
        url = request
        method = "GET"
        headers = {}
        body = None
    try:
        with secure_client(policy=policy, timeout=timeout, follow_redirects=True) as client:
            response = client.request(method, url, headers=headers, content=body)
    except httpx.RequestError as exc:
        raise urllib.error.URLError(exc) from exc
    if response.status_code >= 400:
        raise urllib.error.HTTPError(
            str(response.url), response.status_code, response.reason_phrase,
            response.headers, io.BytesIO(response.content),
        )
    return _UrlopenResponse(response)


__all__ = [
    "DEFAULT_POLICY", "DestinationPolicy", "PinnedSyncBackend", "SSRFSafeClient",
    "SSRFSafeTransport", "UnsafeOutboundTarget", "secure_client", "secure_get", "secure_head", "secure_urlopen",
]
