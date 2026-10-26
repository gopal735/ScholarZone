"""Generate sitemap.xml from the current catalogue.

The committed sitemap is a build artifact that goes stale the moment a
scholarship is added or a cycle changes, and a stale sitemap is worse than none:
it advertises URLs that may no longer exist and omits ones that do. This reads
the live database so the file always describes the catalogue as it is.

Rules, which are the point of the file:

* only publicly indexable routes. Membership is decided by the repository's own
  ``public_visibility_conditions``, not by a copy of it. This script previously
  carried a weaker local rule (quarantined rows only), which is how 207 URLs for
  non-public records reached the committed sitemap and 87 genuinely public ones
  did not. One predicate, so the sitemap cannot disagree with the directory;
* no filter or query URLs, which would multiply thin near-duplicate pages;
* lastmod only where the record genuinely changed, taken from its own
  verification timestamp rather than from build time. A sitemap that claims
  every page changed today is a lie that crawlers learn to ignore.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship
from app.repositories.scholarships import public_visibility_conditions

#: The canonical public frontend. Every <loc> is built from this, so the sitemap
#: cannot advertise one host while the page's own canonical names another.
#: Overridable so a staging build can point at itself without editing the file.
BASE_URL = os.environ.get(
    "SCHOLARZONE_CANONICAL_ORIGIN", "https://scholarzone-fwzj.vercel.app"
).rstrip("/")
#: backend/app/data -> backend/app -> backend -> repo root. Resolved from this
#: file rather than the working directory, so the script writes to the same
#: place whether it is run from the repo root or from backend/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = _REPO_ROOT / "frontend" / "public" / "sitemap.xml"


def _lastmod(row: Scholarship) -> str | None:
    stamp = row.updated_at or row.last_verified_at
    if stamp is None:
        return None
    if isinstance(stamp, datetime):
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.date().isoformat()
    return None


def main() -> int:
    factory = get_session_factory()
    session = factory()
    try:
        rows = session.scalars(
            select(Scholarship)
            .where(*public_visibility_conditions())
            .order_by(Scholarship.id)
        ).all()
    finally:
        session.close()

    entries: list[tuple[str, str | None, str, float]] = [
        (f"{BASE_URL}/", None, "daily", 1.0),
        (f"{BASE_URL}/scholarships", None, "daily", 0.9),
        (f"{BASE_URL}/countries", None, "weekly", 0.7),
    ]
    for row in rows:
        # Priority follows urgency: an open opportunity is worth more than a
        # cycle that has not opened yet, and neither competes with the directory.
        if row.status == "open":
            priority = 0.8
        elif row.status in ("closing-soon", "upcoming"):
            priority = 0.7
        else:
            priority = 0.5
        entries.append(
            (
                f"{BASE_URL}/scholarships/{row.id}",
                _lastmod(row),
                "weekly",
                priority,
            )
        )

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for loc, lastmod, changefreq, priority in entries:
        lines.append("  <url>")
        lines.append(f"    <loc>{escape(loc)}</loc>")
        if lastmod:
            lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{changefreq}</changefreq>")
        lines.append(f"    <priority>{priority}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    xml = "\n".join(lines) + "\n"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(xml, encoding="utf-8")

    with_lastmod = sum(1 for e in entries if e[1])
    print(f"wrote {OUTPUT}")
    print(f"  base            : {BASE_URL}")
    print(f"  urls            : {len(entries)}")
    print(f"  scholarship urls: {len(entries) - 3}")
    print(f"  with lastmod    : {with_lastmod}")
    print("  filter          : public_visibility_conditions()")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
