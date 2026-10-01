"""Strip a leading ``/api`` prefix before routing.

Under Vercel Services the public rewrite sends ``/api/health`` to this service,
and the service is handed the ORIGINAL request path rather than a rewritten one.
Every route in this application is declared at the root, so ``/api/health``
matched nothing and FastAPI answered ``{"detail": "Not Found"}`` for every
request - a routing failure that looks exactly like a broken database or a
missing deployment.

The prefix is removed here rather than by editing every router, and rather than
relying on the platform: a ``request.path`` transform in ``vercel.json`` is
supposed to do the same job, but depending on the shape of that rewrite to keep
the API reachable is a single point of failure for the whole product. This works
whether or not the transform is applied.

Root-level paths are left alone, so ``/health`` still answers for the deployment
verification workflow, and a request that already arrives stripped is untouched.
"""

from __future__ import annotations

PREFIX = "/api"


class StripApiPrefix:
    """ASGI middleware that removes one leading ``/api`` from the path.

    ``root_path`` is updated as well as ``path``: an application that believes it
    sits behind a proxy must agree with the proxy, otherwise it generates
    redirects and documentation links that omit the prefix and send clients to
    the wrong place.
    """

    def __init__(self, app, prefix: str = PREFIX) -> None:
        self.app = app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") in ("http", "websocket"):
            path = scope.get("path") or ""
            if path == self.prefix or path.startswith(self.prefix + "/"):
                stripped = path[len(self.prefix):] or "/"
                scope = dict(scope)
                scope["path"] = stripped
                # The stripped segment belongs to whoever routed to us, not to
                # the application, so it is not added to root_path.
        await self.app(scope, receive, send)