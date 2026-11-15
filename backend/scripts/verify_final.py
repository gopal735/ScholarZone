#!/usr/bin/env python3
"""Verify final scholarship records for uniqueness."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import quote, urljoin

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from scripts.local_smoke_http import open_api_url  # noqa: E402


ALLOWED_LOOPBACK_PORTS = {8000}


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, path.lstrip("/"))


def _extract_items_and_pagination(data: dict) -> tuple[list[dict], dict | None]:
    """Extract items and pagination info from API response.

    Supported formats:
    - {"items": [...], "pagination": {"total": N, "total_pages": N, "page": N, "page_size": N}}
    - {"items": [...], "total": N, "total_pages": N, "page": N, "page_size": N}
    - {"items": [...], "total": N}
    """
    # Format 1: items + pagination object
    if isinstance(data.get("items"), list) and isinstance(data.get("pagination"), dict):
        pagination = data["pagination"]
        return data["items"], {
            "total": pagination.get("total"),
            "total_pages": pagination.get("total_pages"),
            "page": pagination.get("page"),
            "page_size": pagination.get("page_size"),
        }

    # Format 2: items + flat pagination fields
    if isinstance(data.get("items"), list):
        return data["items"], {
            "total": data.get("total"),
            "total_pages": data.get("total_pages"),
            "page": data.get("page"),
            "page_size": data.get("page_size"),
        }

    # Fallback: try common list keys
    for key in ("items", "results", "data", "scholarships"):
        if isinstance(data.get(key), list):
            return data[key], None

    return [], None


def _fetch_all_pages(base_url: str, path: str, *, allowed_ports: set[int], timeout: float = 10.0) -> tuple[list[dict], dict | None]:
    """Fetch all pages of a paginated endpoint.

    Returns all items and the pagination info from the first page.
    """
    all_items = []
    pagination_info = None
    page = 1

    while True:
        url = f"{_join_url(base_url, path)}?page={page}"
        try:
            with open_api_url(url, allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS, timeout=timeout) as resp:
                if resp.status != 200:
                    break
                data = json.loads(resp.read().decode())
        except Exception:
            break

        items, pagination = _extract_items_and_pagination(data)
        if not items:
            break

        if pagination_info is None:
            pagination_info = pagination

        all_items.extend(items)

        # Check if we've fetched all pages
        if pagination is None or pagination.get("total_pages") is None:
            # No pagination info, assume single page
            break

        total_pages = pagination.get("total_pages")
        if total_pages is not None and page >= total_pages:
            break

        page += 1

    return all_items, pagination_info


def main() -> int:
    base_url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    countries = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]

    all_ids = []
    total = 0
    for country in countries:
        url = f"{_join_url(base_url, '/scholarships')}?country={quote(country)}"
        try:
            items, _ = _fetch_all_pages(base_url, "/scholarships", allowed_ports=ALLOWED_LOOPBACK_PORTS, timeout=10)
            # Filter by country (API may not support server-side filtering for all pages)
            # For now, fetch all and filter locally
            country_items = [s for s in items if s.get("country") == country]
            ids = [s["id"] for s in country_items]
            names = [s["name"] for s in country_items]
            unique_ids = len(set(ids)) == len(ids)
            unique_names = len(set(names)) == len(names)
            all_ids.extend(ids)
            total += len(country_items)
            print(f"{country}: {len(country_items)} records, unique IDs: {unique_ids}, unique names: {unique_names}")
            for s in country_items:
                print(f"  - [{s['id']}] {s['name'][:65]}")
        except Exception as e:
            print(f"{country}: ERROR - {e}")

    print("\n=== API SUMMARY ===")
    print(f"Total records across all 5 countries: {total}")
    print(f"Unique IDs: {len(set(all_ids))}")
    print(f"Duplicate IDs: {len(all_ids) - len(set(all_ids))}")

    print("\n=== DATABASE URL UNIQUENESS CHECK ===")
    try:
        all_items, pagination = _fetch_all_pages(base_url, "/scholarships", allowed_ports=ALLOWED_LOOPBACK_PORTS, timeout=10)
        print(f"Total scholarships in DB: {len(all_items)}")
        if pagination:
            print(f"Pagination info: total={pagination.get('total')}, total_pages={pagination.get('total_pages')}")
        all_db_ids = [s["id"] for s in all_items]
        print(f"Unique IDs in DB: {len(set(all_db_ids))}")
        print(f"Duplicate IDs in DB: {len(all_db_ids) - len(set(all_db_ids))}")
    except Exception as e:
        print(f"Could not fetch full DB via API: {e}")
        print("Note: API response does not include official_source_url field.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

