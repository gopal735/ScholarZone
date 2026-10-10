"""The frontend service's SPA rewrite must be the form Vercel actually honours.

The repository's own history records that a negative-lookahead rewrite pattern
is *not* honoured by Vercel's services mode the way it reads. `d812cdb` moved the
fallback into the root vercel.json because the same rule in
`frontend/vercel.json` was not applied at all, and `test_vercel_services.py`
carries the note that a lookahead pattern intended to spare `/assets/` caused
every hashed script and stylesheet to come back 404, so the homepage rendered
unstyled - which is why the catch-all at the root deliberately carries no path
override.

An earlier change extended that frontend lookahead to name the public assets
(`scholarships-snapshot.json`, `favicon.svg`, `robots.txt`, ...). It did not
make those assets reachable: on the branch preview every path, `/` included,
came back as Vercel's own Next.js page rather than the built application. The
asset URLs were never the thing being intercepted - the frontend service had
produced no static output to serve - so a longer pattern bought nothing and
made the configuration harder to reason about.

These tests therefore pin the configuration to the form the repository
documents as working, and separately assert the properties that are actually
checkable here: that the pattern still spares the API and the hashed assets,
that every real application route still reaches the shell, and that the asset
exclusion which is genuinely required lives on the catch-all that routes to the
service.

What is deliberately NOT asserted is that a longer lookahead fixes asset
delivery. Vercel applies rewrites after the filesystem for a real file, so an
asset that exists in the build output is served from disk and never reaches the
rewrite - which means the rewrite is the wrong place to try to fix a missing
asset, and asserting otherwise would encode a guess as a contract.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERCEL_CONFIG = REPOSITORY_ROOT / "vercel.json"

# The form the repository documents as honoured. `d812cdb` introduced it and
# `test_vercel_services.py` explains why nothing more elaborate is safe.
WORKING_PATTERN = r"/((?!api/|assets/).*)"


def _vercel_frontend_rewrite() -> str:
    config = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))
    rewrites = config["services"]["frontend"]["rewrites"]
    assert len(rewrites) == 1, f"expected one frontend rewrite, found {len(rewrites)}"
    rewrite = rewrites[0]
    assert rewrite["destination"] == "/index.html"
    return rewrite["source"]


@pytest.fixture(scope="module")
def rewrite_regex() -> re.Pattern:
    source = _vercel_frontend_rewrite()
    assert source == WORKING_PATTERN, (
        f"the frontend service rewrite is {source!r}. This configuration has been "
        "observed not to work as it reads on Vercel's services mode; see "
        "test_vercel_services.py's note on the reverted lookahead pattern."
    )
    body = source.strip("/")
    return re.compile(body)


def _root_config() -> dict:
    return json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))


def test_the_frontend_rewrite_is_the_documented_working_pattern():
    assert _vercel_frontend_rewrite() == WORKING_PATTERN


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/scholarships",
        "/scholarships/1",
        "/scholarships/99999",
        "/countries",
        "/match",
        "/login",
        "/register",
        "/saved",
        "/dashboard",
        "/applications",
        "/applications/42",
        "/mentor",
        "/compare",
        "/admin",
        "/admin/verification",
    ],
)
def test_a_spa_route_is_still_rewritten_to_the_shell(rewrite_regex, path):
    """Every application route must keep falling through to index.html.

    Without this, simplifying the pattern could stop the application's own
    routes from being served, which would break every page rather than fix one.
    """
    match = rewrite_regex.match(path.lstrip("/"))
    assert match is not None, (
        f"{path} is no longer rewritten to index.html; the SPA would 404"
    )


def test_the_rewrite_still_spares_the_api_and_the_hashed_assets(rewrite_regex):
    # These are the two exclusions the documented pattern exists for. The API
    # is routed to the backend before it ever reaches this service, and the
    # hashed assets are served from the filesystem.
    for prefix in ("api/", "assets/"):
        assert rewrite_regex.match(prefix) is None, f"{prefix} must stay excluded"


def test_the_catch_all_carries_no_path_override():
    """The root catch-all must hand the request to the service unchanged.

    `test_vercel_services.py` records why: giving it a path so deep links would
    get a shell intercepted the hashed asset URLs, and the homepage rendered
    unstyled. Asserted here as well because it is the same rule from the other
    direction.
    """
    rewrites = _root_config()["rewrites"]
    catch_all = rewrites[-1]
    assert catch_all["source"] == "/(.*)"
    assert catch_all["destination"]["service"] == "frontend"
    assert "path" not in catch_all["destination"]


def test_exactly_two_services_are_declared():
    services = _root_config()["services"]
    assert sorted(services) == ["backend", "frontend"]


def test_the_api_reaches_the_backend_first():
    rewrites = _root_config()["rewrites"]
    assert rewrites[0]["source"] == "/api/(.*)"
    assert rewrites[0]["destination"]["service"] == "backend"


def _tracked_public_files() -> list[str]:
    output = subprocess.run(
        ["git", "ls-files", "frontend/public/"],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in output.stdout.splitlines() if line.strip()]


def test_the_public_assets_are_still_shipped():
    """The snapshot and the site metadata must remain part of the build.

    These are `public/` files, which Vite copies into the build output. The
    frontend rewrite is not where their availability is decided - Vercel applies
    rewrites after the filesystem, so a file present in the output is served
    from disk. Asserting that they are tracked keeps the invariant that matters:
    if the snapshot stopped being committed, no routing configuration could
    recover it.
    """
    tracked = _tracked_public_files()
    assert tracked, "no tracked files under frontend/public/"

    names = {entry.rsplit("/", 1)[-1] for entry in tracked}
    for required in ("scholarships-snapshot.json", "robots.txt", "sitemap.xml", "favicon.svg"):
        assert required in names, f"{required} is not tracked, so it cannot be deployed"
