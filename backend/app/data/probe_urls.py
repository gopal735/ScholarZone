"""Probe candidate official URLs for a record and report reachability."""
from __future__ import annotations

import sys

import httpx

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CANDIDATES = [
    "https://www.otago.ac.nz/courses/scholarships/university-of-otago-doctoral-scholarship",
    "https://www.otago.ac.nz/study/scholarships/university-of-otago-doctoral-scholarship",
    "https://bs.china-embassy.gov.cn/eng/sggg/202510/t20251028_11742717.htm",
    "https://bs.china-embassy.gov.cn/eng/sggg/202506/t20250613_11647647.htm",
]


def main() -> None:
    for url in CANDIDATES:
        try:
            response = httpx.get(url, headers=UA, timeout=25.0, follow_redirects=True)
            body = response.text or ""
            print(f"{response.status_code}  len={len(body):>7}  {response.url}")
        except Exception as exc:  # noqa: BLE001
            print(f"ERR {type(exc).__name__}  {url}")


if __name__ == "__main__":
    main()
