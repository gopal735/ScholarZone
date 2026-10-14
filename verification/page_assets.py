"""Check whether the awarding body's own page references an off-domain asset."""
from __future__ import annotations

import re
import sys

import httpx

URL = sys.argv[1]
NEEDLE = sys.argv[2] if len(sys.argv) > 2 else ""

r = httpx.get(URL, timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
print(URL, r.status_code, len(r.text))
refs = sorted(set(re.findall(r'(?:src|href|content)=["\']([^"\']+)["\']', r.text, re.I)))
assets = [u for u in refs if re.search(r"\.(png|svg|jpe?g|webp|ico)$", u, re.I)]
if NEEDLE:
    print("matching", NEEDLE, ":")
    for u in refs:
        if NEEDLE in u:
            print("  ", u)
print("assets on the page:", len(assets))
for u in assets[:40]:
    print("  ", u)
