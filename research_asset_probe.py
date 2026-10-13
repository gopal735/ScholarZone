"""Check whether candidate image URLs resolve to real official image assets.

Usage: python research_asset_probe.py <url> [more urls...]
Prints status, content-type and length for each, so only an asset that
really exists and is really an image is used as a logo.
"""
from __future__ import annotations

import sys
import urllib.request


def main(urls: list[str]) -> int:
    for url in urls:
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
            with urllib.request.urlopen(request, timeout=45) as response:
                content_type = response.headers.get("content-type", "")
                data = response.read(64)
                magic = data[:8].hex()
                is_image = content_type.startswith("image/") or data[:3].hex().startswith("ffd8ff") or data[:8] == b"\x89PNG\r\n\x1a\n"
                print(f"{'OK ' if is_image else 'BAD'} {url} -> {response.status} {content_type} magic={magic}")
        except Exception as error:  # noqa: BLE001
            print(f"ERR {url} -> {type(error).__name__} {str(error)[:90]}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1:]))
