"""Report the image assets and their alt text for a page.

Research helper: when adding a record, the logo must be an official asset
with a stated provenance. This prints the image URLs the page itself
references together with their alt text, so an asset can be picked that
the page actually presents as its own logo.

Usage: python research_images.py <url> [more urls...]
"""
from __future__ import annotations

import re
import sys
import urllib.request

IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)


def main(urls: list[str]) -> int:
    for url in urls:
        print("=" * 20, url)
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            body = urllib.request.urlopen(request, timeout=45).read().decode("utf-8", "replace")
        except Exception as error:  # noqa: BLE001
            print("  FETCH FAILED:", type(error).__name__, str(error)[:120])
            continue
        seen = set()
        for tag in IMG_TAG.findall(body):
            src = re.search(r"src=[\"']([^\"']+)[\"']", tag, re.I)
            if not src:
                continue
            value = src.group(1)
            if value.lower().endswith((".png", ".jpg", ".jpeg", ".svg", ".gif")) and value not in seen:
                seen.add(value)
                alt = re.search(r"alt=[\"']([^\"']*)[\"']", tag, re.I)
                print(f"  {value}  alt={alt.group(1) if alt else ''!r}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1:]))
