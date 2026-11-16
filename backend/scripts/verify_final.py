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


class PaginationError(Exception):
    """Raised when pagination fails to fetch a complete dataset."""
    def __init__(self, message: str, page: int | None = None):
        self.page = page
        super().__init__(message)


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

    Raises:
        PaginationError: If any page request fails (exception or non-200 status).
    """
    all_items = []
    pagination_info = None
    first_pagination = None
    page = 1

    while True:
        url = f"{_join_url(base_url, path)}?page={page}"
        try:
            with open_api_url(url, allowed_loopback_ports=allowed_ports, timeout=timeout) as resp:
                if resp.status != 200:
                    raise PaginationError(
                        f"Page {page} returned HTTP {resp.status}",
                        page=page
                    )
                try:
                    data = json.loads(resp.read().decode())
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise PaginationError(
                        f"Page {page} returned malformed JSON: {exc}",
                        page=page
                    ) from exc
        except PaginationError:
            raise
        except Exception as e:
            raise PaginationError(
                f"Page {page} request failed: {e}",
                page=page
            ) from e

        items, pagination = _extract_items_and_pagination(data)

        # Validate pagination metadata consistency across pages.
        if pagination is not None:
            if first_pagination is None:
                first_pagination = pagination
            else:
                if pagination.get("total_pages") is not None and first_pagination.get("total_pages") is not None:
                    if pagination.get("total_pages") != first_pagination.get("total_pages"):
                        raise PaginationError(
                            f"Page {page} total_pages {pagination.get('total_pages')} "
                            f"differs from first page {first_pagination.get('total_pages')}",
                            page=page
                        )
                if pagination.get("total") is not None and first_pagination.get("total") is not None:
                    if pagination.get("total") != first_pagination.get("total"):
                        raise PaginationError(
                            f"Page {page} total {pagination.get('total')} "
                            f"differs from first page {first_pagination.get('total')}",
                            page=page
                        )
            if pagination.get("page") is not None and pagination.get("page") != page:
                raise PaginationError(
                    f"Page {page} response reports page {pagination.get('page')}",
                    page=page
                )

        # Check if we've fetched all pages FIRST (before checking for empty items)
        if pagination is None or pagination.get("total_pages") is None:
            # No pagination info, assume single page - add items and break
            if items:
                if pagination_info is None:
                    pagination_info = first_pagination or pagination
                all_items.extend(items)
            break

        total_pages = pagination.get("total_pages")
        if total_pages is not None and page >= total_pages:
            # Last page - add items and break
            if items or total_pages == 1:
                if pagination_info is None:
                    pagination_info = first_pagination or pagination
                all_items.extend(items)
            break

        # Not the last page - add items and continue
        if items:
            if pagination_info is None:
                pagination_info = first_pagination or pagination
            all_items.extend(items)
        # If items is empty but we haven't reached total_pages, continue to next page

        page += 1

    if pagination_info is None:
        pagination_info = first_pagination
    return all_items, pagination_info


def _fetch_all_pages_once(base_url: str, path: str, *, allowed_ports: set[int], timeout: float = 10.0) -> tuple[list[dict], dict | None]:
    """Fetch all pages once and return the complete dataset.

    This is the primary function for fetching the complete scholarship dataset.
    It raises PaginationError on any failure instead of returning partial results.
    """
    return _fetch_all_pages(base_url, path, allowed_ports=allowed_ports, timeout=timeout)


def main() -> int:
    base_url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    countries = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]

    # Fetch the complete dataset ONCE and reuse for all checks
    try:
        all_items, pagination = _fetch_all_pages_once(
            base_url, "/scholarships", allowed_ports=ALLOWED_LOOPBACK_PORTS, timeout=10
        )
    except PaginationError as e:
        page_info = f" (page {e.page})" if e.page else ""
        print(f"FAILURE: Could not fetch complete scholarship dataset{page_info}: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"FAILURE: Unexpected error fetching scholarship dataset: {e}", file=sys.stderr)
        return 1

    print(f"Total scholarships in DB: {len(all_items)}")
    if pagination:
        print(f"Pagination info: total={pagination.get('total')}, total_pages={pagination.get('total_pages')}")

    verification_failed = False
    if not all_items:
        print("FAILURE: Fetched empty dataset", file=sys.stderr)
        verification_failed = True

    # Verify total count matches pagination metadata if available
    if pagination and pagination.get("total") is not None:
        expected_total = pagination["total"]
        if len(all_items) != expected_total:
            print(f"FAILURE: Fetched {len(all_items)} records but pagination reports total={expected_total}", file=sys.stderr)
            verification_failed = True

    all_ids = []
    total = 0
    for country in countries:
        # Filter by country from the already-fetched dataset
        country_items = [s for s in all_items if s.get("country") == country]
        ids = [s["id"] for s in country_items]
        names = [s["name"] for s in country_items]
        unique_ids = len(set(ids)) == len(ids)
        unique_names = len(set(names)) == len(names)
        all_ids.extend(ids)
        total += len(country_items)
        print(f"{country}: {len(country_items)} records, unique IDs: {unique_ids}, unique names: {unique_names}")
        for s in country_items:
            print(f"  - [{s['id']}] {s['name'][:65]}")

    print("\n=== API SUMMARY ===")
    print(f"Total records across all 5 countries: {total}")
    print(f"Unique IDs: {len(set(all_ids))}")
    duplicate_ids = len(all_ids) - len(set(all_ids))
    print(f"Duplicate IDs: {duplicate_ids}")
    if duplicate_ids > 0:
        print("FAILURE: Duplicate IDs found in dataset", file=sys.stderr)
        verification_failed = True

    print("\n=== DATABASE URL UNIQUENESS CHECK ===")
    all_db_ids = [s["id"] for s in all_items]
    print(f"Unique IDs in DB: {len(set(all_db_ids))}")
    duplicate_db_ids = len(all_db_ids) - len(set(all_db_ids))
    print(f"Duplicate IDs in DB: {duplicate_db_ids}")
    if duplicate_db_ids > 0:
        print("FAILURE: Duplicate IDs found in database", file=sys.stderr)
        verification_failed = True

    return 1 if verification_failed else 0


if __name__ == "__main__":
    sys.exit(main())

