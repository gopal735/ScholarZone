"""
The Vercel SPA rewrite must not swallow a file the app ships in `public/`.

`vercel.json`'s frontend rewrite sends every unmatched path to `index.html`.
Vercel applies that rewrite *before* serving a static file, unlike Netlify, so a
path the rewrite catches comes back as HTML with status 200 rather than as the
asset. That is invisible in the build and in CI, and it only appears when a
deployment is actually requested - which is exactly how
`/scholarships-snapshot.json`, `/robots.txt`, `/sitemap.xml`, `/favicon.svg`,
`/icons.svg` and `/404.html` all came back as `text/html` from the Vercel
preview while the identical build served them correctly from Netlify.

For this catalogue the consequence is not cosmetic. The snapshot IS the
catalogue: `loadScholarshipSnapshot()` checks `response.ok`, which is true for a
200 carrying HTML, then calls `response.json()`, which throws. Every public
listing, detail and statistics page would fail to render on Vercel - the one
deployment target where the free-first architecture does its job.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VERCEL_CONFIG = REPOSITORY_ROOT / "vercel.json"
PUBLIC_DIR = REPOSITORY_ROOT / "frontend" / "public"

# Paths that must never be rewritten to the SPA shell for other reasons.
STRUCTURAL_EXCLUSIONS = {"api/", "assets/"}


def _vercel_frontend_rewrite() -> str:
    config = json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))
    rewrites = config["services"]["frontend"]["rewrites"]
    assert len(rewrites) == 1, f"expected one frontend rewrite, found {len(rewrites)}"
    rewrite = rewrites[0]
    assert rewrite["destination"] == "/index.html"
    return rewrite["source"]


def _tracked_public_files() -> list[str]:
    """Files under frontend/public/ that git actually tracks."""
    output = subprocess.run(
        ["git", "ls-files", "frontend/public/"],
        cwd=str(REPOSITORY_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in output.stdout.splitlines() if line.strip()]


@pytest.fixture(scope="module")
def rewrite_regex() -> re.Pattern:
    source = _vercel_frontend_rewrite()
    # The source is written as a JS regex literal body between slashes. Extract
    # what it actually matches on the path, so the test exercises the real rule
    # rather than a transcription of it.
    body = source.strip("/")
    return re.compile(body)


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

    Without this, excluding the assets could stop the application's own routes
    from being served, which would break every page rather than fix one.
    """
    match = rewrite_regex.match(path.lstrip("/"))
    assert match is not None, (
        f"{path} is no longer rewritten to index.html; the SPA would 404"
    )


def test_a_shipped_public_file_is_not_rewritten(rewrite_regex):
    tracked = _tracked_public_files()
    assert tracked, "no tracked files found under frontend/public/"

    for entry in tracked:
        relative = entry[len("frontend/public/") :]
        path = "/" + relative
        match = rewrite_regex.match(path.lstrip("/"))
        assert match is None, (
            f"{path} is matched by the SPA rewrite, so Vercel would serve HTML "
            "for it instead of the asset"
        )


def test_the_snapshot_is_excluded(rewrite_regex):
    # The one the architecture depends on, asserted by name.
    assert rewrite_regex.match("scholarships-snapshot.json") is None


def test_api_and_assets_remain_excluded(rewrite_regex):
    for prefix in STRUCTURAL_EXCLUSIONS:
        assert rewrite_regex.match(prefix) is None, f"{prefix} must stay excluded"
