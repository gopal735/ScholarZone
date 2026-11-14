from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.error import URLError

import pytest

from scripts.local_smoke_http import open_local_smoke_url


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"fixture-ok")

    def log_message(self, *_args):
        pass


def test_local_smoke_adapter_reaches_only_explicit_loopback_fixture_port():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        with open_local_smoke_url(
            f"http://127.0.0.1:{server.server_port}/health",
            allowed_ports={server.server_port},
        ) as response:
            assert response.status == 200
            assert response.read() == b"fixture-ok"

        with pytest.raises(URLError):
            open_local_smoke_url(
                f"http://127.0.0.1:{server.server_port}/health",
                allowed_ports={server.server_port + 1},
            )
        with pytest.raises(URLError):
            open_local_smoke_url(
                f"http://example.com:{server.server_port}/health",
                allowed_ports={server.server_port},
            )
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
