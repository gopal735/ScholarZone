# Outbound network security

ScholarZone backend HTTP fetches use `app.services.outbound_security`. The
shared policy accepts public HTTP and HTTPS URLs, rejects credentials and
non-public destinations, resolves every hostname immediately before connecting,
and connects to a validated literal IP. The connected peer is checked against
that IP. Environment proxies and Unix-domain sockets are disabled so they
cannot bypass destination pinning.

Redirects are followed manually, with a five-hop limit. Every target is
validated before the next connection, and HTTPS-to-HTTP redirects are refused.
Use `secure_client`, `secure_get`, `secure_head`, or `secure_urlopen`; do not add
direct `requests`, HTTPX, or `urllib` network calls in application or script
code. Custom transports are refused except for HTTPX `MockTransport` in
deterministic tests.

Playwright callers use `app.services.outbound_proxy`. Chromium sends network
traffic through a loopback proxy that resolves, validates, pins, and checks
the destination peer. HTTPS uses CONNECT on port 443. Browser HTTP requests are
blocked at the proxy, which also prevents a browser from following an HTTPS to
HTTP downgrade. Callers block service workers and disable direct DNS, QUIC, and
non-proxied WebRTC traffic.

`tests/test_outbound_security.py` uses injected resolvers and mock transports
to cover prohibited addresses, mixed DNS answers, DNS rebinding, peer checks,
redirects, and browser proxy rejection. The local Playwright end-to-end fixture
uses a test-only policy restricted to loopback; production defaults remain
unchanged. The Docker artifact smoke script has a separate policy restricted
to `127.0.0.1` and its explicitly selected test port so it can probe its own
disposable container without relaxing application egress.
