"""Serve frontend/dist and proxy /api to the deployed API.

A static server alone is not enough: the built bundle calls /api on its own
origin, and the deployed API does not allow this origin. Proxying keeps the
browser on one origin, so the page behaves exactly as it does in production and
the trust surfaces can be read off a real rendered page.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend" / "dist"
#: The deployed API by default. Point SCHOLARZONE_PROXY_UPSTREAM at a locally
#: running API to inspect the frontend against unrepaired or repaired data
#: without deploying anything.
UPSTREAM = os.environ.get(
    "SCHOLARZONE_PROXY_UPSTREAM", "https://scholarzone-fwzj.vercel.app/api"
).rstrip("/")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4173
BASE_PATH = "/ScholarZone"

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "transfer-encoding",
    "upgrade",
}

#: A browser asks for brotli and gets brotli. A byte-for-byte pass-through would
#: then be right for the client but unreadable here, so the encoding is negotiated
#: away on the way upstream and the identity bytes are relayed.
FORWARD_STRIPPED = {"accept-encoding", "host"}


class Handler(SimpleHTTPRequestHandler):
    def _proxy(self) -> None:
        target = UPSTREAM + self.path[len("/api"):]
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        request = urllib.request.Request(
            target,
            data=body,
            method=self.command,
            headers={
                k: v
                for k, v in self.headers.items()
                if k.lower() not in HOP_BY_HOP and k.lower() not in FORWARD_STRIPPED
            },

        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = response.read()
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() in HOP_BY_HOP or key.lower() == "access-control-allow-origin":
                        continue
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(payload)
        except urllib.error.HTTPError as exc:
            payload = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except Exception as exc:  # noqa: BLE001
            payload = json.dumps({"detail": f"proxy error: {exc}"}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def _rewrite(self) -> None:
        """Strip the deploy path, and send deep links to the SPA.

        The bundle is built with a base of /ScholarZone/, so every asset request
        arrives under that prefix while the files on disk are at the dist root.
        A path that names a file is resolved as a file; anything else is the SPA.
        """
        path = self.path
        if path.startswith("/api"):
            return
        clean = path[len(BASE_PATH):] if path.startswith(BASE_PATH) else path
        if "." not in Path(clean).name:
            clean = "/index.html"
        self.path = clean if clean.startswith("/") else f"/{clean}"

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api"):
            self._proxy()
            return
        self._rewrite()
        super().do_GET()

    do_POST = do_PUT = do_DELETE = do_PATCH = do_GET

    def log_message(self, *args) -> None:  # noqa: A003
        pass


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), partial(Handler, directory=str(ROOT)))
    print(f"serving {ROOT} with /api -> {UPSTREAM} on http://127.0.0.1:{PORT}{BASE_PATH}/")
    server.serve_forever()
