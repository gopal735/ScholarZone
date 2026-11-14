"""Explicit loopback-only policy for disposable local smoke-test services."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.services.outbound_security import (
    DestinationPolicy,
    UnsafeOutboundTarget,
    secure_urlopen,
)


class _LoopbackSmokePolicy(DestinationPolicy):
    """Allow cleartext HTTP only to 127.0.0.1 on explicitly selected ports."""

    allow_http = True

    def __init__(self, allowed_ports: set[int]) -> None:
        super().__init__()
        self._allowed_ports = frozenset(allowed_ports)

    def validate_url(self, url, *, request=None):
        parsed = urlsplit(str(url))
        try:
            port = parsed.port
        except ValueError as exc:
            raise UnsafeOutboundTarget("invalid local smoke-test port", request=request) from exc
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or port not in self._allowed_ports
        ):
            raise UnsafeOutboundTarget(
                "local smoke tests may contact only their 127.0.0.1 fixture port",
                request=request,
            )
        return "127.0.0.1", port, ipaddress.ip_address("127.0.0.1")

    def resolve_public(self, host: str, port: int):
        if host != "127.0.0.1" or port not in self._allowed_ports:
            raise ValueError("local smoke-test destination is outside its fixture allowlist")
        return (ipaddress.ip_address("127.0.0.1"),)


def open_local_smoke_url(url: str, *, allowed_ports: set[int], timeout: float = 5.0):
    """Fetch a local smoke endpoint without relaxing the production policy."""
    return secure_urlopen(
        url,
        timeout=timeout,
        policy=_LoopbackSmokePolicy(allowed_ports),
    )
