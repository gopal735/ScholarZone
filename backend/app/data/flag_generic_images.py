"""Flag already-persisted generic site assets for human review.

A real catalogue sweep persisted a handful of site-wide social cards and theme
template assets (for example ``/_assets/opengraph.png``) under misleading kinds.
They are not deleted here: removing a verified image silently would destroy an
audit trail, and the ImageReview model exists precisely to route questionable
imagery to a human.
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.models import ImageReview, Scholarship
from app.services.image_discovery_orchestrator import _is_generic_site_asset

DRY_RUN = "--persist" not in sys.argv

GENERIC = ("opengraph", "og-image", "ogimage", "/og/", "/framework", "theme-gcweb", "/theme/", "template-")

factory = get_session_factory()
session = factory()
try:
    rows = session.query(Scholarship).filter(Scholarship.image_verified_at.is_not(None)).all()
    flagged = 0
    for row in rows:
        url = row.image_url or ""
        low = url.lower()
        if not any(n in low for n in GENERIC) and not _is_generic_site_asset(url, row.image_alt_text):
            continue

        # Logo-kind assets are an accepted fallback (priority 5), so only flag
        # those recorded as a programme image or banner.
        if (row.image_kind or "") in ("official_logo",) and not any(
            n in low for n in ("opengraph", "og-image", "/framework", "theme-gcw")
        ):
            continue

        existing = (
            session.query(ImageReview)
            .filter(
                ImageReview.scholarship_id == row.id,
                ImageReview.image_url == url,
                ImageReview.decision == "pending",
            )
            .first()
        )
        if existing is not None:
            continue

        flagged += 1
        print(f"  flagging id={row.id}  kind={row.image_kind}  {url[:78]}")
        if not DRY_RUN:
            session.add(
                ImageReview(
                    scholarship_id=row.id,
                    image_url=url,
                    image_kind=row.image_kind or "unknown",
                    source_page=row.image_source_url,
                    source_type=row.image_source_type,
                    confidence="low",
                    reason_for_review=(
                        "Generic site asset: site-wide social card or theme template file, "
                        "not scholarship imagery. Flagged by catalogue quality audit."
                    ),
                )
            )
    if not DRY_RUN:
        session.commit()
    print(f"\nmode      : {'DRY RUN' if DRY_RUN else 'PERSIST'}")
    print(f"flagged   : {flagged}")
finally:
    session.close()
