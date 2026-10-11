#!/usr/bin/env python3
"""Regenerate the public sitemap from the published scholarship snapshot.

The sitemap was a hand-maintained static file. On the 2026-10-03
publication it already disagreed with the catalogue it describes: 349
`<loc>` entries, of which 41 were detail URLs for records that have since
left the public set (two discontinued, the rest closed by the deadline
rule), and 277 published records had no detail URL at all — including
closed ones. Every catalogue change since has drifted it further, and a
sitemap that omits live listings tells search engines the listings do not
exist.

This script makes the sitemap derived rather than maintained: one detail
URL per record the snapshot actually publishes, so the two artifacts
cannot disagree. The static routes keep their existing changefreq and
priority values; the base origin is taken from the file being replaced,
so the generator is not tied to one hostname.

Usage (from repository root):
    python generate_sitemap.py [snapshot] [sitemap]
"""

import datetime
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SNAPSHOT_PATH = Path("frontend/public/scholarships-snapshot.json")
SITEMAP_PATH = Path("frontend/public/sitemap.xml")

# The static routes, with the priorities the hand-maintained file used.
STATIC_ROUTES = (
    ("/", "daily", "1.0"),
    ("/scholarships", "daily", "0.9"),
    ("/countries", "weekly", "0.7"),
)
DETAIL_PRIORITY = {"changefreq": "weekly", "priority": "0.8"}

# The origin the site is deployed from. It is the same value the frontend's
# canonicalOrigin service exports and the SEO contract test enforces, and it
# is deliberately a constant rather than derived from anything in the data: a
# record's own catalogue_url is the awarding body's page, not our host, and
# reading an origin from it would publish a sitemap pointing at somebody
# else's domain.
CANONICAL_ORIGIN = "https://visionary-cactus-600b38.netlify.app"


def _origin(existing: Path) -> str:
    """The origin to build URLs from: the file being replaced, if it has one.

    The committed sitemap already carries the deployed origin, so replacing
    it keeps that host explicit rather than relocating every listing by
    assumption. A missing or unparseable file falls back to the canonical
    origin, which is what a first-ever generation should publish.
    """
    if existing.is_file():
        try:
            root = ET.parse(existing).getroot()
        except ET.ParseError:
            return CANONICAL_ORIGIN
        if root is not None:
            namespaces = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
            for loc in root.findall(".//sm:loc", namespaces) or root.findall(".//loc"):
                if loc.text and loc.text.startswith("http"):
                    return loc.text.rstrip("/")
    return CANONICAL_ORIGIN


def generate(snapshot_path: Path, sitemap_path: Path) -> int:
    with open(snapshot_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)
    records = snapshot.get("scholarships", [])
    ids = [int(record["id"]) for record in records if record.get("id") is not None]

    base = _origin(sitemap_path)
    # The same date the snapshot derived its statuses on: the sitemap says
    # "reflects the catalogue as published", not "as crawled today".
    lastmod = (
        (snapshot.get("meta") or {}).get("status_derived_at")
        or datetime.date.today().isoformat()
    )

    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for path, changefreq, priority in STATIC_ROUTES:
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = f"{base}{path}"
        ET.SubElement(url, "changefreq").text = changefreq
        ET.SubElement(url, "priority").text = priority
    for rid in sorted(ids):
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = f"{base}/scholarships/{rid}"
        ET.SubElement(url, "lastmod").text = lastmod
        ET.SubElement(url, "changefreq").text = DETAIL_PRIORITY["changefreq"]
        ET.SubElement(url, "priority").text = DETAIL_PRIORITY["priority"]

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    sitemap_path.parent.mkdir(parents=True, exist_ok=True)
    # ElementTree writes the declaration with single quotes and a lowercase
    # encoding (`<?xml version='1.0' encoding='utf-8'?>`), which the repo's
    # sitemap contract test rejects; the sitemap consumers expect the exact
    # `<?xml version="1.0" encoding="UTF-8"?>` prolog, so it is written here.
    body = ET.tostring(root, encoding="unicode")
    sitemap_path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + body + "\n", encoding="utf-8"
    )
    return len(ids)


if __name__ == "__main__":
    args = sys.argv[1:]
    snapshot = Path(args[0]) if args else SNAPSHOT_PATH
    sitemap = Path(args[1]) if len(args) > 1 else SITEMAP_PATH
    count = generate(snapshot, sitemap)
    print(f"Wrote {sitemap}: {count} detail URLs + {len(STATIC_ROUTES)} static routes")
