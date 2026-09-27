"""Flag persisted images that look like generic site assets rather than programme images."""
from __future__ import annotations

import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
conn = sqlite3.connect("scholarzone.db")
rows = conn.execute(
    "SELECT id, title, image_url, image_kind, image_source_url FROM scholarships "
    "WHERE image_verified_at IS NOT NULL ORDER BY id"
).fetchall()

GENERIC = [
    ("og_card", ("opengraph", "og-image", "ogimage", "/og/")),
    ("theme_asset", ("/framework", "theme-gcwe", "/theme/", "template-")),
    ("logo_only", ("logo", "brandmark", "wordmark")),
]

flagged = 0
for sid, title, url, kind, src in rows:
    u = (url or "").lower()
    reasons = [name for name, needles in GENERIC if any(n in u for n in needles)]
    if reasons:
        flagged += 1
        print(f"  id={sid:<5d} {','.join(reasons):<20s} kind={kind}")
        print(f"        {str(url)[:96]}")
        print(f"        page: {str(src)[:88]}")
        print(f"        title: {str(title)[:60]}")

print(f"\nTOTAL persisted images : {len(rows)}")
print(f"flagged as generic    : {flagged}")
conn.close()
