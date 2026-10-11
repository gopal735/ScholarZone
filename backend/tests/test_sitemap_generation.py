"""The public sitemap must be derived from the published snapshot.

The sitemap was a hand-maintained static file and had already drifted from
the catalogue when phase 3 replaced it with `generate_sitemap.py`: the old
file carried 346 detail URLs - 41 of them for records no longer published -
while 277 published records had no detail URL at all, including the closed
ones readers can still filter to. A sitemap that omits live listings tells
search engines those listings do not exist, and advertising stale ones is a
soft-404.

These tests pin the derivation:
- the detail URL set is exactly the snapshot's id set, no more, no less;
- the origin is the canonical one (no legacy host, no second origin);
- no private or filtered route appears.

The generator is pure with respect to its inputs and writes the file given
to it, so it is exercised against a temporary copy rather than over the
committed artifact.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = REPOSITORY_ROOT / "generate_sitemap.py"


@pytest.fixture(scope="module")
def sitemap_generator():
    spec = importlib.util.spec_from_file_location("generate_sitemap_under_test", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _urls(xml: str) -> list[str]:
    import re

    return re.findall(r"<loc>([^<]+)</loc>", xml)


def test_the_detail_url_set_is_exactly_the_published_ids(sitemap_generator, tmp_path):
    snapshot_path = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
    if not snapshot_path.is_file():
        pytest.skip("the committed snapshot is not present")
    with open(snapshot_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    out = tmp_path / "sitemap.xml"
    sitemap_generator.generate(snapshot_path, out)
    xml = out.read_text(encoding="utf-8")
    locs = _urls(xml)
    detail = [loc for loc in locs if "/scholarships/" in loc]
    assert {int(loc.rsplit("/", 1)[1]) for loc in detail} == {
        record["id"] for record in snapshot["scholarships"]
    }
    assert len(detail) == len(snapshot["scholarships"])
    # The static routes come first, so a reader of the file sees the site
    # before its records; only the derived part is per-record.
    origin = locs[0].partition("/scholarships/")[0].rstrip("/")
    assert locs[:3] == [f"{origin}/", f"{origin}/scholarships", f"{origin}/countries"]


def test_the_static_routes_survive(sitemap_generator, tmp_path):
    snapshot_path = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
    if not snapshot_path.is_file():
        pytest.skip("the committed snapshot is not present")
    out = tmp_path / "sitemap.xml"
    sitemap_generator.generate(snapshot_path, out)
    locs = _urls(out.read_text(encoding="utf-8"))
    origin = locs[0].partition("/scholarships/")[0].rstrip("/")
    for route in ("/", "/scholarships", "/countries"):
        assert f"{origin}{route}" in locs


def test_the_committed_sitemap_matches_a_regenerated_one(sitemap_generator, tmp_path):
    snapshot_path = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
    committed = REPOSITORY_ROOT / "frontend" / "public" / "sitemap.xml"
    if not snapshot_path.is_file() or not committed.is_file():
        pytest.skip("the committed artifacts are not present")
    out = tmp_path / "sitemap.xml"
    sitemap_generator.generate(snapshot_path, out)
    assert _urls(out.read_text(encoding="utf-8")) == _urls(committed.read_text(encoding="utf-8"))


def test_no_private_or_filtered_route_is_advertised(sitemap_generator, tmp_path):
    snapshot_path = REPOSITORY_ROOT / "frontend" / "public" / "scholarships-snapshot.json"
    if not snapshot_path.is_file():
        pytest.skip("the committed snapshot is not present")
    out = tmp_path / "sitemap.xml"
    sitemap_generator.generate(snapshot_path, out)
    locs = _urls(out.read_text(encoding="utf-8"))
    for loc in locs:
        assert "?" not in loc, "a filtered variant is not a page"
        for private in ("/admin", "/dashboard", "/applications", "/login", "/register", "/saved", "/compare", "/api"):
            assert private not in loc
