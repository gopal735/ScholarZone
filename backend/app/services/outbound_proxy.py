"""Loopback-only, destination-pinned proxy for Playwright network traffic.

Chromium receives a local proxy and never resolves destination hostnames. The
proxy validates DNS and opens sockets to pinned public IPs. HTTPS uses CONNECT,
so Chromium retains normal TLS certificate validation and SNI while this proxy
enforces the peer IP. Service workers and non-HTTP schemes are disabled by the
browser caller; this proxy never offers UDP or SOCKS.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import threading
from urllib.parse import urlsplit

from .outbound_security import DEFAULT_POLICY, DestinationPolicy, UnsafeOutboundTarget


_MAX_HEADER_BYTES = 64 * 1024
_CONNECT_TIMEOUT_SECONDS = 10.0
_RELAY_IDLE_TIMEOUT_SECONDS = 45.0


class OutboundProxy:
    def __init__(self, policy: DestinationPolicy | None = None) -> None:
        self.policy = policy or DEFAULT_POLICY
        self._server: asyncio.AbstractServer | None = None

    async def start(self) -> str:
        self._server = await asyncio.start_server(self._handle, "127.0.0.1", 0, limit=_MAX_HEADER_BYTES)
        port = self._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream_writer: asyncio.StreamWriter | None = None
        try:
            first = await asyncio.wait_for(reader.readline(), timeout=_CONNECT_TIMEOUT_SECONDS)
            if len(first) > 8192 or not first.endswith(b"\r\n"):
                await self._reply(writer, 400, "Bad Request")
                return
            try:
                method, target, _version = first.decode("ascii").strip().split(" ", 2)
            except (UnicodeDecodeError, ValueError):
                await self._reply(writer, 400, "Bad Request")
                return
            headers = await self._read_headers(reader)
            if method.upper() == "CONNECT":
                host, port = self._parse_authority(target)
                if port != 443:
                    await self._reply(writer, 403, "Only HTTPS CONNECT is allowed")
                    return
                upstream_reader, upstream_writer = await self._connect_pinned(host, port)
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                await self._tunnel(reader, writer, upstream_reader, upstream_writer)
                return

            if method.upper() not in {"GET", "HEAD"}:
                await self._reply(writer, 405, "Method Not Allowed")
                return
            parsed = urlsplit(target)
            if parsed.scheme.lower() != "http" or not parsed.hostname:
                await self._reply(writer, 403, "Forbidden")
                return
            if parsed.username is not None or parsed.password is not None:
                await self._reply(writer, 403, "Forbidden")
                return
            if not self.policy.allow_http:
                # Cleartext is refused at the egress boundary, so a browser
                # cannot follow an HTTPS-to-HTTP downgrade.
                await self._reply(writer, 403, "Browser HTTP is disabled; use HTTPS")
                return
            host, port, _ = self.policy.validate_url(target)
            if any(name.lower() in {b"content-length", b"transfer-encoding"} and value.strip() not in {b"0", b""} for name, value in headers):
                await self._reply(writer, 405, "Request Body Not Supported")
                return
            host_header = next((value.decode("latin1") for name, value in headers if name.lower() == b"host"), None)
            if host_header is None or self._parse_host_header(host_header) != (host, port):
                await self._reply(writer, 400, "Host Mismatch")
                return

            upstream_reader, upstream_writer = await self._connect_pinned(host, port)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            upstream_writer.write(f"{method} {path} HTTP/1.1\r\n".encode("ascii"))
            for name, value in headers:
                if name.lower() in {b"proxy-authorization", b"proxy-connection", b"connection"}:
                    continue
                upstream_writer.write(name + b": " + value + b"\r\n")
            upstream_writer.write(b"Connection: close\r\n\r\n")
            await upstream_writer.drain()
            await self._copy(upstream_reader, writer)
        except (ValueError, UnsafeOutboundTarget, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            with contextlib.suppress(Exception):
                await self._reply(writer, 403, "Outbound Target Rejected")
        except (OSError, ConnectionError):
            with contextlib.suppress(Exception):
                await self._reply(writer, 502, "Bad Gateway")
        finally:
            if upstream_writer is not None:
                upstream_writer.close()
                with contextlib.suppress(Exception):
                    await upstream_writer.wait_closed()
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _read_headers(self, reader: asyncio.StreamReader) -> list[tuple[bytes, bytes]]:
        result = []
        total = 0
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=_CONNECT_TIMEOUT_SECONDS)
            total += len(line)
            if total > _MAX_HEADER_BYTES:
                raise ValueError("request headers too large")
            if line == b"\r\n":
                return result
            if not line.endswith(b"\r\n") or b":" not in line:
                raise ValueError("malformed HTTP header")
            name, value = line[:-2].split(b":", 1)
            result.append((name.strip(), value.strip()))

    @staticmethod
    def _parse_authority(value: str) -> tuple[str, int]:
        parsed = urlsplit("//" + value)
        if parsed.username is not None or parsed.password is not None or not parsed.hostname:
            raise ValueError("invalid CONNECT authority")
        port = parsed.port
        if port is None:
            raise ValueError("CONNECT port is required")
        return parsed.hostname, port

    @classmethod
    def _parse_host_header(cls, value: str) -> tuple[str, int]:
        parsed = urlsplit("//" + value)
        if parsed.username is not None or parsed.password is not None or not parsed.hostname:
            raise ValueError("invalid Host header")
        host = parsed.hostname.lower().rstrip(".")
        return host, parsed.port or 80

    async def _connect_pinned(self, host: str, port: int):
        addresses = self.policy.resolve_public(host, port)
        last: Exception | None = None
        for address in addresses:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(address.compressed, port),
                    timeout=_CONNECT_TIMEOUT_SECONDS,
                )
            except (OSError, asyncio.TimeoutError) as exc:
                last = exc
                continue
            peer = writer.get_extra_info("peername")
            try:
                peer_ip = ipaddress.ip_address(peer[0].split("%", 1)[0])
            except (TypeError, ValueError, IndexError) as exc:
                writer.close()
                raise ValueError("connected peer address could not be verified") from exc
            if peer_ip != address:
                writer.close()
                raise ValueError("connected peer differs from validated destination")
            return reader, writer
        raise OSError("unable to connect to a validated destination") from last

    async def _tunnel(self, client_reader, client_writer, upstream_reader, upstream_writer) -> None:
        tasks = [
            asyncio.create_task(self._copy(client_reader, upstream_writer)),
            asyncio.create_task(self._copy(upstream_reader, client_writer)),
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        for task in done:
            with contextlib.suppress(Exception):
                task.result()

    async def _copy(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        while True:
            data = await asyncio.wait_for(reader.read(64 * 1024), timeout=_RELAY_IDLE_TIMEOUT_SECONDS)
            if not data:
                return
            writer.write(data)
            await writer.drain()

    @staticmethod
    async def _reply(writer: asyncio.StreamWriter, status: int, reason: str) -> None:
        writer.write(f"HTTP/1.1 {status} {reason}\r\nConnection: close\r\nContent-Length: 0\r\n\r\n".encode("ascii"))
        await writer.drain()


class SyncOutboundProxy:
    """Thread-hosted proxy adapter for synchronous Playwright callers."""

    def __init__(self, policy: DestinationPolicy | None = None) -> None:
        self._proxy = OutboundProxy(policy)
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="scholarzone-egress-proxy", daemon=True)
        self._server_url: str | None = None

    def start(self) -> str:
        self._thread.start()
        if not self._ready.wait(timeout=_CONNECT_TIMEOUT_SECONDS):
            raise RuntimeError("outbound proxy failed to start")
        if self._server_url is None:
            raise RuntimeError("outbound proxy failed to bind")
        return self._server_url

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._server_url = self._loop.run_until_complete(self._proxy.start())
        finally:
            self._ready.set()
        self._loop.run_forever()

    def close(self) -> None:
        if self._thread.is_alive():
            asyncio.run_coroutine_threadsafe(self._proxy.close(), self._loop).result(timeout=_CONNECT_TIMEOUT_SECONDS)
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=_CONNECT_TIMEOUT_SECONDS)
        self._loop.close()


__all__ = ["OutboundProxy", "SyncOutboundProxy"]
