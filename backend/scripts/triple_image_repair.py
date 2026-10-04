#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled repair of three latent image-state corruption records.

TARGETS is a module constant, not an argument, so a wider run cannot be
requested by mistake. Modes:

  --inspect        read-only. Prints every image field, image review count,
                   verification history touching an image field, updated_at and
                   public visibility for each target, plus a corruption class.
  --reset          one preconditioned mutation per target, per the existing
                   clear-image semantics. Aborts an individual record whose
                   precondition no longer matches, without touching the others.
  --evaluate       runs the EXISTING ImageCoverageRunner against TARGETS only.

Corruption classes
------------------
  A VERIFIED_WITHOUT_IMAGE         status='verified', no image
  B VERIFIED_TIMESTAMP_WITHOUT_IMAGE  image_verified_at set, no image
  C BOTH                           both of the above
  D OTHER                          residue that does not match A/B/C

No writes outside TARGETS. One transaction, committed only per record.
"""
from __future__ import annotations

import argparse
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

TARGETS = [14, 130, 554]

IMAGE_FIELDS = ["image_url", "image_source_url", "image_source_type", "image_kind",
                "image_alt_text", "image_verified_at", "image_evaluated_at",
                "image_evaluation_status"]
PRESERVE_FIELDS = ["title", "country", "degree", "official_source_url",
                   "verification_status", "is_verified", "is_archived", "status",
                   "funding", "deadline_date", "updated_at"]


def classify(d: dict) -> str:
    has_status = str(d.get("image_evaluation_status") or "").lower() == "verified"
    has_stamp = d.get("image_verified_at") is not None
    if not d.get("image_url") and has_status and has_stamp:
        return "C BOTH"
    if not d.get("image_url") and has_status:
        return "A VERIFIED_WITHOUT_IMAGE"
    if not d.get("image_url") and has_stamp:
        return "B VERIFIED_TIMESTAMP_WITHOUT_IMAGE"
    return "D OTHER"


def load(session, sid):
    from app.models import Scholarship

    row = session.get(Scholarship, sid)
    if row is None:
        return None
    d = {f: getattr(row, f, None) for f in IMAGE_FIELDS + PRESERVE_FIELDS}
    d["_row"] = row
    return d


def show(tag, sid, d):
    print(f"  [{tag}] id {sid}  class={classify(d)}")
    for f in IMAGE_FIELDS:
        print(f"      {f:26} {str(d.get(f))[:70]}")
    print(f"      verification_status={d.get('verification_status')} "
          f"is_verified={d.get('is_verified')} is_archived={d.get('is_archived')}")
    print(f"      updated_at={str(d.get('updated_at'))[:30]}")


def do_inspect(session):
    from sqlalchemy import text
    from sqlalchemy import select
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions

    A = set(session.execute(select(Scholarship.id)
                            .where(*public_visibility_conditions())).scalars().all())
    print("=" * 78)
    print("PHASE 1 - READ-ONLY PER-ID AUDIT")
    print("=" * 78)
    for sid in TARGETS:
        d = load(session, sid)
        if d is None:
            print(f"\n  id {sid}: NOT IN STORAGE")
            continue
        show("state", sid, d)
        print(f"      in public universe  : {sid in A}")
        try:
            n = session.execute(text(
                "SELECT COUNT(*) FROM image_reviews WHERE scholarship_id=:i"),
                {"i": sid}).scalar() or 0
            print(f"      image_reviews       : {n}")
        except Exception:
            print("      image_reviews       : <table unavailable>")
        try:
            rows = session.execute(text(
                "SELECT field_name, old_value, new_value FROM "
                "scholarship_verification_history WHERE scholarship_id=:i "
                "AND field_name LIKE 'image%' ORDER BY id"), {"i": sid}).all()
            print(f"      image verification history rows: {len(rows)}")
            for r in rows[:6]:
                print(f"         {r[0]}: {str(r[1])[:40]} -> {str(r[2])[:40]}")
        except Exception as exc:
            print(f"      image verification history: <{type(exc).__name__}>")
        print()
    session.rollback()
    return 0


def do_reset(session):
    print("=" * 78)
    print("PHASE 2/3 - PRECONDITIONED TARGETED RESET")
    print("=" * 78)
    results = {}
    for sid in TARGETS:
        d = load(session, sid)
        if d is None:
            print(f"\n  id {sid}: ABORT - not in storage")
            results[sid] = "ABORT_NOT_FOUND"
            continue
        cls = classify(d)
        show("before", sid, d)
        before = {f: d.get(f) for f in PRESERVE_FIELDS}

        # Precondition: the record must genuinely carry no image.
        if d.get("image_url") is not None:
            print(f"      ABORT: id {sid} has a stored image")
            results[sid] = "ABORT_HAS_IMAGE"
            session.rollback()
            continue
        has_status = str(d.get("image_evaluation_status") or "").lower() == "verified"
        has_stamp = d.get("image_verified_at") is not None
        if not has_status and not has_stamp:
            print(f"      no-op: id {sid} has no stale verdict or timestamp")
            results[sid] = "NOOP_CLEAN"
            session.rollback()
            continue

        row = d["_row"]
        # The existing clear-image semantics: an image that is not there has no
        # verdict, no verification timestamp, and no provenance describing it.
        # Only image-owned fields are touched.
        row.image_evaluation_status = None
        row.image_evaluated_at = None
        row.image_verified_at = None
        row.image_kind = None
        row.image_source_url = None
        row.image_source_type = None
        row.image_alt_text = None
        session.commit()
        session.expire_all()

        after = load(session, sid)
        show("after", sid, after)
        drift = [f for f in PRESERVE_FIELDS if str(after.get(f)) != str(before[f])]
        print(f"      unrelated fields changed: {drift or 'none'}")
        print(f"      image fields cleared    : "
              f"{[f for f in IMAGE_FIELDS if after.get(f) is None and d.get(f) is not None]}")
        print(f"      RESET {'OK' if not drift else 'FAILED'}")
        results[sid] = "RESET_OK" if not drift else "RESET_DRIFT"
        print()
    print(f"  SUMMARY {results}")
    return 0


def do_evaluate(session):
    from app.database import get_session_factory
    from app.services.image_coverage_runner import ImageCoverageRunner

    print("=" * 78)
    print(f"PHASE 5 - EXISTING ImageCoverageRunner AGAINST {TARGETS}")
    print("=" * 78)
    before = {sid: {f: load(session, sid).get(f) for f in IMAGE_FIELDS} for sid in TARGETS}
    session.rollback()

    runner = ImageCoverageRunner(
        get_session_factory(), dry_run=False, plan_only=False,
        batch_size=len(TARGETS), max_workers=1, exclude_quarantined=True,
        skip_terminally_evaluated=True, logo_only=False,
        per_record_budget_seconds=120.0)
    metrics = runner.run(ids=list(TARGETS), limit=len(TARGETS))

    print("\n  --- metrics ---")
    for k, v in metrics.as_dict().items():
        print(f"    {k:26} {v}")
    print("\n  --- outcomes ---")
    for o in (metrics.outcomes or []):
        print(f"    id {o.get('scholarship_id')}: status={o.get('status')} "
              f"persisted={o.get('persisted')} candidates={o.get('candidates')} "
              f"requests={o.get('requests_made')}")
        if o.get("image_url"):
            print(f"       image_url: {o['image_url']}")
        for k in ("error", "page_error"):
            if o.get(k):
                print(f"       {k}: {o[k]}")

    from sqlalchemy import select
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions
    A = set(session.execute(select(Scholarship.id)
                            .where(*public_visibility_conditions())).scalars().all())
    B = set(session.execute(select(Scholarship.id)).scalars().all())
    print(f"\n  PUBLIC={len(A)} STORAGE={len(B)} STORAGE_ONLY={len(B - A)} "
          f"PUBLIC_ONLY={len(A - B)} INTERSECTION={len(A & B)}")
    print("\n  --- post-state ---")
    for sid in TARGETS:
        d = load(session, sid)
        show("after", sid, d)
        changed = [f for f in IMAGE_FIELDS if str(d.get(f)) != str(before[sid].get(f))]
        print(f"      changed image fields: {changed}")
        print(f"      in public universe  : {sid in A}\n")
    session.rollback()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    args = ap.parse_args()
    if sum([args.inspect, args.reset, args.evaluate]) != 1:
        sys.exit("ERROR: choose exactly one of --inspect / --reset / --evaluate")

    from app.database import get_engine, get_session_factory
    engine = get_engine()
    session = get_session_factory()()
    try:
        return do_inspect(session) if args.inspect else (
            do_reset(session) if args.reset else do_evaluate(session))
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)