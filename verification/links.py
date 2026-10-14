"""List the hyperlinks on an official page, from a live fetch.

Used for Level 6 recovery: an awarding body's own navigation is an official
route to the current page, so its links are the discovery mechanism.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.services.official_source_fetcher import fetch_official_source  # noqa: E402

HREF = re.compile(r"""href=["']([^"'#]+)["']""", re.I)

url = sys.argv[1]
needle = re.compile(sys.argv[2], re.I) if len(sys.argv) > 2 else None

r = fetch_official_source(url)
if not r.success or not r.content:
    print("FETCH FAILED", r.status_code, r.error_type, r.error_reason)
    raise SystemExit(1)
print("final:", r.final_url, "chars:", len(r.content))
seen: set[str] = set()
for m in HREF.finditer(r.content):
    href = urljoin(r.final_url or url, m.group(1))
    if href in seen:
        continue
    seen.add(href)
    if needle and not needle.search(href):
        continue
    print(" ", href)