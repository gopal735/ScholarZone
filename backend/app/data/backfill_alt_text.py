"""Backfill image_alt_text for verified images that lack it.

The brief requires every accepted image to carry alt text. The verifier does not
always set it, so verified rows can persist an image with no accessible label.

The fallback is deliberately mechanical and non-fabricated: it is derived from
the record's own title, which is already in the database. No new fact is
invented, and nothing about the scholarship is asserted that its own title does
not already state.
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import get_session_factory
from app.models import Scholarship

PERSIST = "--persist" in sys.argv

factory = get_session_factory()
session = factory()
try:
    rows = (
        session.query(Scholarship)
        .filter(Scholarship.image_verified_at.is_not(None))
        .filter(Scholarship.image_url.is_not(None))
        .all()
    )
    filled = 0
    for row in rows:
        if row.image_alt_text and str(row.image_alt_text).strip():
            continue
        title = (row.title or "").strip()
        if not title:
            continue
        provider = (row.official_source or "").strip()
        alt = f"{title} - official {provider} image" if provider else f"{title} - official image"
        row.image_alt_text = alt[:512]
        filled += 1

    if PERSIST:
        session.commit()
    print(f"mode    : {'PERSIST' if PERSIST else 'DRY RUN'}")
    print(f"verified images : {len(rows)}")
    print(f"alt text filled : {filled}")

    total_with = session.query(Scholarship).filter(
        Scholarship.image_verified_at.is_not(None),
        Scholarship.image_alt_text.is_not(None),
    ).count()
    print(f"provenance-complete rows : {total_with}/{len(rows)}")
finally:
    session.close()
