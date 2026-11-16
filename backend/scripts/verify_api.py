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
    failed_countries = []
    failed_checks = []

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
                    failed_countries.append(country)
                    failed_checks.append(f"{country}: HTTP {resp.status}")
        except Exception as e:
            print(f"{country}: Error - {e}")
            failed_countries.append(country)
            failed_checks.append(f"{country}: {e}")

    # Also fetch all records to verify totals
    full_dataset_failed = False
    all_fetched = 0
    full_dataset_total = None
    try:
        with open_api_url(
            scholarships_url,
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode())
                items, total = _extract_items_and_total(data)
                all_fetched = len(items)
                full_dataset_total = total
                print(f"\nTotal scholarships in API: {total if total is not None else 'N/A'} (fetched {len(items)} records)")
            else:
                print(f"Failed to fetch all scholarships: HTTP {resp.status}")
                full_dataset_failed = True
    except Exception as e:
        print(f"Error fetching all scholarships: {e}")
        full_dataset_failed = True

    # Verify totals match if we have a total from the full dataset
    total_mismatch = False
    if full_dataset_total is not None and all_items:
        # We have items from country-specific fetches, compare with full dataset total
        if len(all_items) != full_dataset_total:
            print(f"\nWARNING: Country-specific fetches returned {len(all_items)} records but full dataset reports total={full_dataset_total}", file=sys.stderr)
            total_mismatch = True

    # Return non-zero if any country failed, full dataset failed, or totals don't match
    if failed_countries:
        print(f"\nFAILED countries: {', '.join(failed_countries)}")
        return 1
    if full_dataset_failed:
        print("\nFAILED: Full dataset request failed")
        return 1
    if total_mismatch:
        print("\nFAILED: Total mismatch between country-specific and full dataset fetches")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

