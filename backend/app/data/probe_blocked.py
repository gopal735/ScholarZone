"""Probe the official sources the catalogue currently lists as blocked.

A blocked classification is a snapshot of one moment. Domains change their
edge configuration, certificates get renewed, and pages move. This re-tests the
known-blocked official URLs so any that are now reachable are corrected rather
than left stale, and so the remaining ones carry current evidence.
"""

from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import httpx

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TARGETS = [
    "https://vanier.gc.ca/en/home-accueil.html",
    "https://vanier.gc.ca/",
    "https://grants.oead.at/",
    "https://www.oead.at/",
    "https://www.edutwscholarship.moe.gov.tw/",
    "https://www.campuschina.org/",
    "https://campuschina.org/",
    "https://future.utoronto.ca/pearson",
    "https://www.otago.ac.nz/courses/scholarships/university-of-otago-doctoral-scholarship",
    "https://www.dfat.gov.au/people-to-people/australia-awards/australia-awards-scholarships",
    "https://www.chevening.org/",
    "https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50026200",
]


def main() -> None:
    client = httpx.Client(timeout=20.0, follow_redirects=True, headers=UA)
    try:
        for url in TARGETS:
            try:
                response = client.get(url)
                print(
                    f"{response.status_code}  len={len(response.content):>7}  "
                    f"{url}  ->  {str(response.url)[:60]}"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"ERR {type(exc).__name__:<26} {url}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
