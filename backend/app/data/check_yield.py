"""Measure what the section extractor actually yields on real official pages.

Used to verify that new extraction rules produce real facts on live official
content, not just on synthetic fixtures.
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

from app.services.official_source_fetcher import fetch_official_source
from app.services.section_extractor import extract_all

TARGETS = [
    (24, "humboldt"),
    (17, "erasmus"),
    (3, "daad"),
    (28, "chevening"),
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def main() -> None:
    from sqlalchemy import select

    from app.database import get_session_factory
    from app.models import Scholarship

    session = get_session_factory()()
    try:
        for sid, label in TARGETS:
            row = session.get(Scholarship, sid)
            if row is None or not row.official_source_url:
                print(f"id={sid} {label}: no url")
                continue
            try:
                resp = httpx.get(
                    row.official_source_url,
                    headers={"User-Agent": UA, "Accept": "text/html"},
                    timeout=25.0,
                    follow_redirects=True,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"id={sid} {label}: FETCH {type(exc).__name__}")
                continue
            if resp.status_code != 200:
                print(f"id={sid} {label}: HTTP {resp.status_code}")
                continue
            facts = extract_all(resp.text)
            by_field: dict[str, list[str]] = {}
            for f in facts:
                by_field.setdefault(f.field_name, []).append(f.value)
            print(f"\nid={sid} {label} {resp.url} -> {len(facts)} facts")
            for name, values in sorted(by_field.items()):
                print(f"   {name:22s} x{len(values)}  {values[0][:58]}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
