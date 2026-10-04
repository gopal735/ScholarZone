#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY global audit of the image-state contract across all storage rows.

Reports every combination of image_url, image_verified_at,
image_evaluation_status and image_kind that contradicts the contract:

  I1  image_url IS NULL            => image_verified_at is not proof of an image
  I2  image_url IS NULL            => status must not be 'verified'
  I3  status == 'verified'         => image_url must be present
  I4  image_url IS NULL            => row stays eligible for image evaluation
  I5  a stored image carries its provenance (source_url + source_type + kind)

No writes. One transaction, rolled back.
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


def main() -> int:
    from sqlalchemy import select, text

    from app.database import get_engine
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions

    engine = get_engine()
    session = engine.connect()
    try:
        A = set(session.execute(select(Scholarship.id)
                                .where(*public_visibility_conditions())).scalars().all())
        rows = session.execute(text(
            "SELECT id, title, image_url, image_verified_at, image_evaluated_at, "
            "image_evaluation_status, image_kind, image_source_url, image_source_type "
            "FROM scholarships ORDER BY id")).mappings().all()
        session.rollback()
    finally:
        session.close()
        engine.dispose()

    d = [dict(r) for r in rows]
    print("=" * 78)
    print("GLOBAL IMAGE-STATE CONTRACT AUDIT (read-only)")
    print("=" * 78)
    print(f"  storage rows    {len(d)}")
    print(f"  public rows     {len(A)}")
    print(f"  storage_only    {len(d) - len(A)}")
    print()

    buckets = {
        "I1_verified_at_without_image": [
            r for r in d if not r["image_url"] and r["image_verified_at"]],
        "I2_status_verified_without_image": [
            r for r in d if not r["image_url"]
            and str(r["image_evaluation_status"] or "").lower() == "verified"],
        "I3_status_verified_but_not_in_public": [
            r for r in d if str(r["image_evaluation_status"] or "").lower() == "verified"
            and r["id"] in A and not r["image_url"]],
        "I5_image_without_provenance": [
            r for r in d if r["image_url"]
            and not (r["image_source_url"] and r["image_source_type"])],
        "I6_image_without_kind": [
            r for r in d if r["image_url"] and not r["image_kind"]],
        "residual_source_without_image": [
            r for r in d if not r["image_url"] and r["image_source_type"]],
        "eligible_no_image": [r for r in d if not r["image_url"]],
        "verified_with_image": [
            r for r in d if r["image_url"]
            and str(r["image_evaluation_status"] or "").lower() == "verified"],
    }

    for name, rows_ in buckets.items():
        print(f"  {name:38} {len(rows_)}")
        for r in rows_[:14]:
            print(f"      id {r['id']:<6} status={str(r['image_evaluation_status']):16}"
                  f" kind={str(r['image_kind']):16} verified_at={str(r['image_verified_at'])[:19]:20}"
                  f" {str(r['title'])[:34]}")
        if len(rows_) > 14:
            print(f"      ... and {len(rows_) - 14} more")
        print()

    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    violations = {k: len(v) for k, v in buckets.items()
                  if k.startswith("I") and k != "I4_eligible"}
    for k, v in violations.items():
        print(f"  {k:38} {v}")
    clean = all(v == 0 for k, v in violations.items() if k != "I4")
    print(f"\n  contract clean: {clean}")
    print("\n=== AUDIT COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)