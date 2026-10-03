#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controlled two-record image repair: IDs 613 and 563 only.

Modes
-----
``--reset-613``  one explicit, precondition-checked mutation that retires the
                 stale terminal verdict on 613. Refuses to run unless 613 is
                 exactly the corrupted shape (terminal status, no stored image).
``--evaluate``   runs the EXISTING ImageCoverageRunner against [613, 563] and
                 nothing else, through the normal persistence path.

No other scholarship is selectable: the id list is a module constant, not an
argument, so a wider run cannot be requested by mistake.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/two_record_image_repair.py --reset-613
    SCHOLARZONE_DATABASE_URL=... python scripts/two_record_image_repair.py --evaluate
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

RESET_ID = 613
EVAL_IDS = [613, 563]

IMAGE_FIELDS = ["image_url", "image_source_url", "image_source_type", "image_kind",
                "image_alt_text", "image_verified_at", "image_evaluated_at",
                "image_evaluation_status"]
PRESERVE_FIELDS = ["title", "country", "degree", "official_source_url",
                   "verification_status", "is_verified", "is_archived", "status"]


def snapshot(session, sid: int) -> dict:
    from app.models import Scholarship

    row = session.get(Scholarship, sid)
    if row is None:
        sys.exit(f"ABORT: id {sid} is not in storage")
    d = {f: getattr(row, f, None) for f in IMAGE_FIELDS + PRESERVE_FIELDS}
    d["_row"] = row
    return d


def report(tag: str, d: dict) -> None:
    print(f"  [{tag}] id {d['_row'].id}  {d.get('title')}")
    for f in IMAGE_FIELDS:
        print(f"      {f:26} {str(d.get(f))[:70]}")
    print(f"      {'verification_status':26} {d.get('verification_status')}"
          f"   is_verified={d.get('is_verified')}  is_archived={d.get('is_archived')}")


def do_reset(session) -> int:
    d = snapshot(session, RESET_ID)
    print("=" * 78)
    print(f"PHASE 2 - TARGETED RESET OF ID {RESET_ID}")
    print("=" * 78)
    report("before", d)

    status = str(d.get("image_evaluation_status") or "").lower()
    if d.get("image_url"):
        sys.exit("ABORT: 613 already has a stored image; this is not the stale case")
    if status != "verified":
        sys.exit(f"ABORT: 613 status is {status!r}, expected 'verified'")

    before_preserve = {f: d.get(f) for f in PRESERVE_FIELDS}

    row = d["_row"]
    # Exactly the fields that describe an image that is not there. No image
    # value is invented; this only withdraws a verdict that has no subject.
    row.image_evaluation_status = None
    row.image_evaluated_at = None
    row.image_kind = None
    session.commit()

    session.expire_all()
    after = snapshot(session, RESET_ID)
    report("after", after)

    drift = [f for f in PRESERVE_FIELDS
             if str(after.get(f)) != str(before_preserve[f])]
    print()
    print(f"  preserved fields unchanged : {not drift}"
          + (f"  DRIFT={drift}" if drift else ""))
    print(f"  image_evaluation_status    : {after.get('image_evaluation_status')}")
    print(f"  image_kind                 : {after.get('image_kind')}")
    print(f"  verification_status        : {after.get('verification_status')}")
    return 0 if (after.get("image_evaluation_status") is None and not drift) else 1


def do_evaluate(session) -> int:
    from app.database import get_session_factory
    from app.services.image_coverage_runner import ImageCoverageRunner

    print("=" * 78)
    print(f"PHASE 3 - EXISTING ImageCoverageRunner AGAINST {EVAL_IDS}")
    print("=" * 78)
    before = {sid: {f: snapshot(session, sid).get(f) for f in IMAGE_FIELDS}
              for sid in EVAL_IDS}
    session.rollback()

    runner = ImageCoverageRunner(
        get_session_factory(),
        dry_run=False,
        plan_only=False,
        batch_size=len(EVAL_IDS),
        max_workers=1,
        exclude_quarantined=True,
        skip_terminally_evaluated=True,
        logo_only=False,
        per_record_budget_seconds=120.0,
    )
    metrics = runner.run(ids=list(EVAL_IDS), limit=len(EVAL_IDS))

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
        if o.get("error"):
            print(f"       error: {o['error']}")
        if o.get("page_error"):
            print(f"       page_error: {o['page_error']}")

    print("\n  --- post-state ---")
    from app.repositories.scholarships import public_visibility_conditions
    from sqlalchemy import select
    from app.models import Scholarship

    A = set(session.execute(select(Scholarship.id)
                            .where(*public_visibility_conditions())).scalars().all())
    B = set(session.execute(select(Scholarship.id)).scalars().all())
    print(f"    PUBLIC={len(A)}  STORAGE={len(B)}  STORAGE_ONLY={len(B - A)}"
          f"  PUBLIC_ONLY={len(A - B)}  INTERSECTION={len(A & B)}")
    for sid in EVAL_IDS:
        d = snapshot(session, sid)
        report("after", d)
        changed = [f for f in IMAGE_FIELDS if str(d.get(f)) != str(before[sid].get(f))]
        print(f"      image fields changed: {changed}")
        print(f"      in public universe   : {sid in A}")
        print()
    session.rollback()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset-613", action="store_true")
    ap.add_argument("--evaluate", action="store_true")
    args = ap.parse_args()
    if args.reset_613 == args.evaluate:
        sys.exit("ERROR: choose exactly one of --reset-613 / --evaluate")

    from app.database import get_engine, get_session_factory

    engine = get_engine()
    session = get_session_factory()()
    try:
        return do_reset(session) if args.reset_613 else do_evaluate(session)
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