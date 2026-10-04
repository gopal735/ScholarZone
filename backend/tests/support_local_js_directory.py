"""A real local JavaScript directory, served over real HTTP.

This is the primary proof that the rendering problem is actually solved, so it is
built to be un-cheatable:

* a real HTTP server on localhost, so the page is fetched over the network
* the served HTML contains **no** faculty markup at all - only an empty container
  and a script - so a static fetch genuinely cannot see any professor
* the professor appears only after JavaScript runs in the browser
* the academic role is stated only in the rendered card, so the role evidence
  exists nowhere in the bytes a static client receives

If any of that were faked, the static-first assertion would pass for the wrong
reason and the evidence pipeline would be untested.

Routes are bounded and local only. Nothing here reaches the public internet.
"""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

#: The served document. A static client sees exactly this: an empty container and
#: a script. No names, no roles, no profile links.
JS_SHELL_HTML = """<!doctype html>
<html><head><title>Faculty of Computing</title></head>
<body>
  <nav><a href="/about">About</a></nav>
  <div id="app"></div>
  <script src="/app.js"></script>
</body></html>"""

#: The programme page a scholarship's official URL would point at. It links to
#: the people directory, which is the client-rendered part.
PROGRAMME_HTML = """<!doctype html>
<html><head><title>MSc Computer Science</title></head>
<body>
  <h1>MSc Computer Science</h1>
  <p>Supervision is offered by the Faculty of Computing.</p>
  <a href="/people">Our Faculty</a>
</body></html>"""

#: Builds the cards. Runs only inside a browser.
APP_JS = """
document.addEventListener('DOMContentLoaded', function () {
  var faculty = [
    { name: 'Dr Ada Lovelace',   role: 'Professor of Computer Science',
      url: '/people/ada-lovelace', areas: 'Analytical engines; machine learning' },
    { name: 'Professor Alan Turing', role: 'Reader in Logic',
      url: '/people/alan-turing',  areas: 'Computability; cryptography' },
    { name: 'South Australia',   role: 'Region',
      url: '/life-at-adelaide/adelaide-and-south-australia', areas: '' },
    { name: 'School of Computing', role: 'Division',
      url: '/school/computing', areas: '' }
  ];
  var html = '<h1>Faculty</h1><ul>';
  faculty.forEach(function (person) {
    html += '<li><a href="' + person.url + '">' + person.name + '</a>' +
            ' <span class="role">' + person.role + '</span>' +
            ' <span class="areas">' + person.areas + '</span></li>';
  });
  html += '</ul>';
  document.getElementById('app').innerHTML = html;
});
"""

PROFILE_HTML = """<!doctype html>
<html><head><title>Ada Lovelace</title></head>
<body><div id="app"></div><script src="/profile.js"></script></body></html>"""

PROFILE_JS = """
document.addEventListener('DOMContentLoaded', function () {
  document.getElementById('app').innerHTML =
    '<h1>Dr Ada Lovelace</h1>' +
    '<p>Professor of Computer Science</p>' +
    '<p>Email: a.lovelace@uni1.edu</p>' +
    '<p>Research interests: machine learning; formal verification</p>' +
    '<p>I am currently accepting applications for the 2027 intake.</p>';
});
"""


class _Handler(SimpleHTTPRequestHandler):
    """Serves the synthetic university from memory.

    ``SimpleHTTPRequestHandler`` is used only for the HTTP plumbing; every route
    is answered explicitly so no filesystem access is possible.
    """

    ROUTES = {
        "/": (JS_SHELL_HTML, "text/html; charset=utf-8"),
        "/programmes/msc": (PROGRAMME_HTML, "text/html; charset=utf-8"),
        "/people": (JS_SHELL_HTML, "text/html; charset=utf-8"),
        "/app.js": (APP_JS, "application/javascript; charset=utf-8"),
        "/profile.js": (PROFILE_JS, "application/javascript; charset=utf-8"),
    }
    PROFILES = {"/people/ada-lovelace": PROFILE_HTML, "/people/alan-turing": PROFILE_HTML}

    def log_message(self, *args):  # noqa: A003 - silence the default stderr spam
        return

    def do_GET(self):  # noqa: N802 - the BaseHTTPRequestHandler API
        path = self.path.split("?")[0]
        if path in self.ROUTES:
            body, content_type = self.ROUTES[path]
        elif path in self.PROFILES:
            body, content_type = self.PROFILES[path], "text/html; charset=utf-8"
        else:
            self.send_error(404, "Not Found")
            return
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


class LocalDirectoryServer:
    """A localhost HTTP server for the duration of a test.

    Binds to 127.0.0.1 on an ephemeral port, so tests can run concurrently without
    colliding and nothing is reachable from outside the machine.
    """

    def __init__(self) -> None:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def __enter__(self) -> "LocalDirectoryServer":
        self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._server.shutdown()
        self._server.server_close()


__all__ = ["LocalDirectoryServer"]