#!/usr/bin/env python3
"""Verify API returns for each country."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import quote, urljoin

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.local_smoke_http import open_api_url  # noqa: E402


COUNTRIES = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]
ALLOWED_LOOPBACK_PORTS = {8000}


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def main() -> int:
    base_url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    scholarships_url = _join_url(base_url, "/api/scholarships")

    print("=== API VERIFICATION ===")
    for country in COUNTRIES:
        try:
            with open_api_url(
                f"{scholarships_url}?country={quote(country)}",
                allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    count = len(data.get("scholarships", []))
                    print(f"{country}: {count} scholarships returned")
                    for s in data.get("scholarships", [])[:3]:
                        print(f"  - {s.get('title', 'N/A')}")
                else:
                    print(f"{country}: HTTP {resp.status}")
        except Exception as e:
            print(f"{country}: Error - {e}")

    try:
        with open_api_url(
            scholarships_url,
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                print(f"\nTotal scholarships in API: {data.get('total', 'N/A')}")
    except Exception as e:
        print(f"Error: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

