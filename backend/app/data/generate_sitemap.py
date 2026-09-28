"""Generate sitemap.xml from the current catalogue.

The committed sitemap is a build artifact that goes stale the moment a
scholarship is added or a cycle changes, and a stale sitemap is worse than none:
it advertises URLs that may no longer exist and omits ones that do. This reads
the live database so the file always describes the catalogue as it is.

Rules, which are the point of the file:

* only publicly indexable routes - the two quarantined non-scholarships are
  excluded, because they are not scholarships and must not be indexed as if
  they were;
* no filter or query URLs, which would multiply thin near-duplicate pages;
* lastmod only where the record genuinely changed, taken from its own
  verification timestamp rather than from build time. A sitemap that claims
  every page changed today is a lie that crawlers learn to ignore.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import select

from app.database import get_session_factory
from app.models import Scholarship

BASE_URL = "https://gopal735.github.io/ScholarZone"
#: backend/app/data -> backend/app -> backend -> repo root. Resolved from this
#: file rather than the working directory, so the script writes to the same
#: place whether it is run from the repo root or from backend/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT = _REPO_ROOT / "frontend" / "public" / "sitemap.xml"

#: Non-scholarship rows retained for audit. Indexing them would present a
#: government front door as a funding opportunity.
EXCLUDED_STATUS = "quarantined"


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
            .where(Scholarship.verification_status != EXCLUDED_STATUS)
            .order_by(Scholarship.id)
        ).all()
    finally:
        session.close()

    entries: list[tuple[str, str | None, str, float]] = [
        (f"{BASE_URL}/", None, "daily", 1.0),
        (f"{BASE_URL}/ScholarZone/scholarships", None, "daily", 0.9),
        (f"{BASE_URL}/ScholarZone/countries", None, "weekly", 0.7),
    ]
    for row in rows:
        # Priority follows visibility: an open opportunity is worth more than an
        # archived cycle, and neither competes with the directory itself.
        if row.status == "open":
            priority = 0.8
        elif row.status in ("closing-soon", "upcoming"):
            priority = 0.7
        else:
            priority = 0.5
        entries.append(
            (
                f"{BASE_URL}/ScholarZone/scholarships/{row.id}",
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
    print(f"  urls            : {len(entries)}")
    print(f"  scholarship urls: {len(entries) - 3}")
    print(f"  with lastmod    : {with_lastmod}")
    print(f"  excluded        : {EXCLUDED_STATUS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
