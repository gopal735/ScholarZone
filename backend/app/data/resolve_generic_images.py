"""Resolve the flagged generic images: classify, then act through review.

Classification per the brief:
  VALID OFFICIAL VISUAL  -> keep (a provider logo legitimately related to the
                            programme is an accepted last-resort fallback)
  GENERIC / INVALID      -> route through the existing review mechanism and
                            clear the stored image so a weaker asset is not
                            presented as the programme's imagery

Nothing is deleted from the audit trail: the ImageReview row records the
decision, the original URL, and why.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.models import ImageReview, Scholarship
from app.services.image_discovery_orchestrator import _is_generic_site_asset

PERSIST = "--persist" in sys.argv

factory = get_session_factory()
session = factory()
try:
    rows = session.query(Scholarship).filter(Scholarship.image_verified_at.is_not(None)).all()
    print(f"{'id':<6}{'verdict':<14}{'kind':<16}url")
    print("-" * 100)

    kept = cleared = 0
    for row in rows:
        url = row.image_url or ""
        kind = (row.image_kind or "").strip()

        if not _is_generic_site_asset(url, row.image_alt_text):
            print(f"{row.id:<6}{'VALID':<14}{kind:<16}{url[:58]}")
            kept += 1
            continue

        # A site-wide social card or theme template is not programme imagery,
        # even when it is a real official asset.
        verdict = "GENERIC"
        print(f"{row.id:<6}{verdict:<14}{kind:<16}{url[:58]}")

        if PERSIST:
            already = (
                session.query(ImageReview)
                .filter(
                    ImageReview.scholarship_id == row.id,
                    ImageReview.image_url == url,
                    ImageReview.decision == "rejected",
                )
                .first()
            )
            if already is None:
                session.add(
                    ImageReview(
                        scholarship_id=row.id,
                        image_url=url,
                        image_kind=kind or "unknown",
                        source_page=row.image_source_url,
                        source_type=row.image_source_type,
                        relevance_evidence=(
                            "Rejected by catalogue quality audit: site-wide social card or theme "
                            "template asset, not scholarship imagery. Cleared so the record shows "
                            "no image until a genuine official asset is found."
                        ),
                        confidence="low",
                        decision="rejected",
                        reason_for_review="generic site asset detected during catalogue sweep",
                    )
                )
            # Clear the stored image so a generic asset is never presented as
            # the programme's picture. image_verified_at is cleared too, so the
            # record returns to the "search for an image" pool.
            row.image_url = None
            row.image_source_url = None
            row.image_source_type = None
            row.image_kind = None
            row.image_alt_text = None
            row.image_verified_at = None
            cleared += 1

    if PERSIST:
        session.commit()

    print("-" * 100)
    print(f"mode    : {'PERSIST' if PERSIST else 'DRY RUN'}")
    print(f"valid   : {kept}")
    print(f"generic : {len(rows) - kept}" + (f"  (cleared: {cleared})" if PERSIST else ""))
finally:
    session.close()
