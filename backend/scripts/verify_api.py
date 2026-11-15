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


def _extract_items_and_total(data: dict) -> tuple[list[dict], int | None]:
    """Extract items and total from API response, supporting multiple response formats.

    Supported formats:
    - {"items": [...], "pagination": {"total": N}}
    - {"scholarships": [...], "total": N}
    - {"items": [...], "total": N}
    - {"results": [...], "count": N}
    """
    # Format 1: items + pagination.total
    if isinstance(data.get("items"), list) and isinstance(data.get("pagination"), dict):
        total = data["pagination"].get("total")
        if isinstance(total, int):
            return data["items"], total

    # Format 2: scholarships + total
    if isinstance(data.get("scholarships"), list):
        total = data.get("total")
        if isinstance(total, int):
            return data["scholarships"], total

    # Format 3: items + total
    if isinstance(data.get("items"), list):
        total = data.get("total")
        if isinstance(total, int):
            return data["items"], total

    # Format 4: results + count
    if isinstance(data.get("results"), list):
        count = data.get("count")
        if isinstance(count, int):
            return data["results"], count

    # Fallback: try to find any list and count
    for key in ("items", "scholarships", "results", "data"):
        if isinstance(data.get(key), list):
            return data[key], None

    return [], None


def main() -> int:
    base_url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    scholarships_url = _join_url(base_url, "/api/scholarships")

    print("=== API VERIFICATION ===")
    all_items = []
    for country in COUNTRIES:
        try:
            with open_api_url(
                f"{scholarships_url}?country={quote(country)}",
                allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
                timeout=10,
            ) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode())
                    items, total = _extract_items_and_total(data)
                    count = len(items)
                    all_items.extend(items)
                    print(f"{country}: {count} scholarships returned (total={total})")
                    for s in items[:3]:
                        print(f"  - {s.get('title', s.get('name', 'N/A'))}")
                else:
                    print(f"{country}: HTTP {resp.status}")
        except Exception as e:
            print(f"{country}: Error - {e}")

    # Also fetch all records to verify totals
    try:
        with open_api_url(
            scholarships_url,
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                items, total = _extract_items_and_total(data)
                print(f"\nTotal scholarships in API: {total if total is not None else 'N/A'} (fetched {len(items)} records)")
    except Exception as e:
        print(f"Error: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

