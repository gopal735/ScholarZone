"""Loopback and public-API URL routing helpers for operational scripts.

Loopback HTTP requests to explicitly approved ``127.0.0.1`` fixture ports use a
strict local adapter that never relaxes production egress policy. Approved
public HTTPS API targets use ``secure_urlopen`` with the default SSRF policy.
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from app.services.outbound_security import (
    DEFAULT_POLICY,
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


def _is_exact_approved_loopback_http(url: str, allowed_ports: set[int]) -> bool:
    parsed = urlsplit(str(url))
    try:
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "http"
        and parsed.hostname == "127.0.0.1"
        and parsed.username is None
        and parsed.password is None
        and port in set(allowed_ports)
    )


def open_local_smoke_url(url: str, *, allowed_ports: set[int], timeout: float = 5.0):
    """Fetch an exact approved local smoke endpoint via the strict loopback adapter."""
    return secure_urlopen(
        url,
        timeout=timeout,
        policy=_LoopbackSmokePolicy(allowed_ports),
    )


def open_api_url(url: str, *, allowed_loopback_ports: set[int], timeout: float = 10.0):
    """Route API checks through the correct adapter.

    - Exact approved loopback HTTP targets -> strict local loopback adapter.
    - Approved public HTTPS targets -> secure_urlopen with default SSRF policy.

    Any other target is rejected.
    """
    if _is_exact_approved_loopback_http(url, allowed_loopback_ports):
        return open_local_smoke_url(url, allowed_ports=allowed_loopback_ports, timeout=timeout)

    parsed = urlsplit(str(url))
    if parsed.scheme == "https" and parsed.hostname:
        # Validate as an approved public HTTPS target under the production SSRF policy.
        DEFAULT_POLICY.validate_url(url)
        return secure_urlopen(url, timeout=timeout)

    raise UnsafeOutboundTarget(
        "API URL must be an exact approved 127.0.0.1 loopback HTTP target or an approved public HTTPS URL"
    )


