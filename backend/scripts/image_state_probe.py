#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY forensic probe for one scholarship's image state.

Reports every image field, the recorded evaluation status, the image review
rows, and any verification history touching an image field. Used to explain a
record whose evaluation status and stored image disagree.

No writes. One transaction, rolled back.

Usage:
    SCHOLARZONE_DATABASE_URL=... python scripts/image_state_probe.py 613 563
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DATABASE_URL = os.environ.get("SCHOLARZONE_DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: SCHOLARZONE_DATABASE_URL is not set", file=sys.stderr)
    sys.exit(1)
if DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

IMAGE_COLUMNS = [
    "image_url", "image_source_url", "image_source_type", "image_kind",
    "image_alt_text", "image_verified_at", "image_evaluated_at",
    "image_evaluation_status", "official_source_url", "title",
    "verification_status", "is_verified", "is_archived",
]


def main() -> int:
    ids = [int(a) for a in sys.argv[1:]] or [613, 563]
    from sqlalchemy import inspect as sa_inspect, text

    from app.database import get_engine
    from app.models import Scholarship

    engine = get_engine()
    session = engine.connect()
    tables = set(sa_inspect(engine).get_table_names())
    try:
        print("=" * 78)
        print("IMAGE STATE PROBE (read-only)")
        print("=" * 78)
        for sid in ids:
            row = session.get(Scholarship, sid) if False else None
            # use a plain select so no ORM identity map is involved
            res = session.execute(
                text("SELECT * FROM scholarships WHERE id = :i"), {"i": sid}).mappings().first()
            if res is None:
                print(f"\nid {sid}: NOT IN STORAGE")
                continue
            d = dict(res)
            print(f"\n--- id {sid} ---")
            for c in IMAGE_COLUMNS:
                if c in d:
                    print(f"    {c:26} {str(d[c])[:88]}")
            contradiction = (
                str(d.get("image_evaluation_status") or "").lower() == "verified"
                and not d.get("image_url")
            )
            print(f"    >>> VERIFIED_WITHOUT_IMAGE: {contradiction}")

            if "image_reviews" in tables:
                rv = session.execute(text(
                    "SELECT id, decision, image_url, image_kind, source_type, "
                    "created_at, reviewed_at, reviewer_note, reason_for_review "
                    "FROM image_reviews WHERE scholarship_id=:i ORDER BY id"),
                    {"i": sid}).mappings().all()
                print(f"    image_reviews rows: {len(rv)}")
                for r in rv:
                    print(f"      {dict(r)}")
            if "scholarship_verification_history" in tables:
                hv = session.execute(text(
                    "SELECT id, field_name, old_value, new_value, changed_at, "
                    "reason FROM scholarship_verification_history "
                    "WHERE scholarship_id=:i AND field_name LIKE 'image%' "
                    "ORDER BY id"), {"i": sid}).mappings().all()
                print(f"    verification_history (image fields): {len(hv)}")
                for r in hv:
                    rec = dict(r)
                    print(f"      id={rec.get('id')} field={rec.get('field_name')}")
                    print(f"        old={str(rec.get('old_value'))[:70]}")
                    print(f"        new={str(rec.get('new_value'))[:70]}")
                    print(f"        at={rec.get('changed_at')} reason={str(rec.get('reason'))[:60]}")
        session.rollback()
    finally:
        session.close()
        engine.dispose()
    print("\n=== PROBE COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)