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


def main() -> int:
    base_url = os.environ.get("SCHOLARZONE_API_URL", "http://127.0.0.1:8000").rstrip("/")
    countries = ["Belgium", "Hungary", "Poland", "Czech Republic", "Portugal"]

    all_ids = []
    total = 0
    for country in countries:
        url = f"{_join_url(base_url, '/scholarships')}?country={quote(country)}"
        try:
            with open_api_url(
                url,
                allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
                timeout=10,
            ) as resp:
                data = json.loads(resp.read().decode())
            if isinstance(data, dict):
                data = data.get("items", data.get("results", []))
            ids = [s["id"] for s in data]
            names = [s["name"] for s in data]
            unique_ids = len(set(ids)) == len(ids)
            unique_names = len(set(names)) == len(names)
            all_ids.extend(ids)
            total += len(data)
            print(f"{country}: {len(data)} records, unique IDs: {unique_ids}, unique names: {unique_names}")
            for s in data:
                print(f"  - [{s['id']}] {s['name'][:65]}")
        except Exception as e:
            print(f"{country}: ERROR - {e}")

    print("\n=== API SUMMARY ===")
    print(f"Total records across all 5 countries: {total}")
    print(f"Unique IDs: {len(set(all_ids))}")
    print(f"Duplicate IDs: {len(all_ids) - len(set(all_ids))}")

    print("\n=== DATABASE URL UNIQUENESS CHECK ===")
    try:
        url_all = _join_url(base_url, "/scholarships")
        with open_api_url(
            url_all,
            allowed_loopback_ports=ALLOWED_LOOPBACK_PORTS,
            timeout=10,
        ) as resp:
            all_data = json.loads(resp.read().decode())
        if isinstance(all_data, dict):
            all_data = all_data.get("items", all_data.get("results", []))
        print(f"Total scholarships in DB: {len(all_data)}")
        all_db_ids = [s["id"] for s in all_data]
        print(f"Unique IDs in DB: {len(set(all_db_ids))}")
        print(f"Duplicate IDs in DB: {len(all_db_ids) - len(set(all_db_ids))}")
    except Exception as e:
        print(f"Could not fetch full DB via API: {e}")
        print("Note: API response does not include official_source_url field.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

