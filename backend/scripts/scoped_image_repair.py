#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scoped, audited invocation of the EXISTING image coverage pipeline.

This adds no image logic. It calls ``ImageCoverageRunner`` - the same class
``do_images()`` uses in the maintenance worker - with an explicit id list, so a
run can be confined to records that were individually audited first.

The runner itself guarantees the safety this task needs:

* it only selects rows where ``image_verified_at IS NULL``, so an already
  verified image is never replaced;
* it re-checks that invariant per record before touching a row;
* it excludes quarantined records;
* it persists nothing in ``plan_only``/dry-run mode;
* a second run finds nothing in scope, which is the idempotency property.

Per-record outcomes are reported as REPAIRED / NO_VALID_OFFICIAL_IMAGE /
BLOCKED / SKIPPED_ALREADY_IMAGED rather than being inferred from a total.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/scoped_image_repair.py
    SCHOLARZONE_DATABASE_URL=... python scripts/scoped_image_repair.py --apply

Without ``--apply`` the run is read-only (plan_only + dry_run).
"""
from __future__ import annotations

import argparse
import json
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

# The audited KEEP_ACTIVE_INTERNAL set. Anything not in this list is out of
# scope: this script must never widen its own target set.
TARGET_IDS = [33, 45, 65, 66, 67, 201, 304, 350, 361, 419, 445, 549, 563, 613, 622]


def outcome(rec: dict) -> str:
    """Map one runner outcome dict onto the task's final-state vocabulary."""
    status = str(rec.get("status") or "")
    if rec.get("persisted"):
        return "REPAIRED"
    if status in ("found", "high", "medium", "low") or (
            status not in ("no_trustworthy_image", "skipped", "source_blocked",
                           "source_unreachable", "failed", "error", "already_present")
            and rec.get("image_url")):
        return "CANDIDATE_FOUND_NOT_PERSISTED"
    if status == "no_trustworthy_image":
        return "NO_VALID_OFFICIAL_IMAGE"
    if status in ("source_blocked", "source_unreachable", "failed", "error"):
        return "BLOCKED"
    if status in ("already_present", "skipped"):
        return "SKIPPED_ALREADY_IMAGED"
    return f"OTHER:{status}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="persist results; omit for a read-only plan")
    ap.add_argument("--manifest")
    ap.add_argument("--budget-seconds", type=float, default=90.0)
    args = ap.parse_args()

    from sqlalchemy import select

    from app.database import get_engine, get_session_factory
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions
    from app.services.image_coverage_runner import ImageCoverageRunner

    engine = get_engine()
    session = get_session_factory()()

    try:
        # ---------- before state, for the audited targets only ----------
        before = {}
        for sid in TARGET_IDS:
            row = session.get(Scholarship, sid)
            if row is None:
                before[sid] = {"id": sid, "missing": True}
                continue
            before[sid] = {
                "id": sid,
                "title": row.title,
                "verification_status": row.verification_status,
                "is_verified": row.is_verified,
                "is_archived": row.is_archived,
                "image_url": row.image_url,
                "image_kind": row.image_kind,
                "image_source_type": row.image_source_type,
                "image_source_url": row.image_source_url,
                "image_verified_at": str(row.image_verified_at),
                "official_source_url": row.official_source_url,
            }

        A = set(session.execute(select(Scholarship.id)
                                .where(*public_visibility_conditions())).scalars().all())
        B = set(session.execute(select(Scholarship.id)).scalars().all())

        print("=" * 78)
        print(f"SCOPED IMAGE REPAIR - mode={'APPLY' if args.apply else 'READ-ONLY PLAN'}")
        print("=" * 78)
        print(f"  PUBLIC_UNIVERSE  {len(A)}")
        print(f"  STORAGE_UNIVERSE {len(B)}")
        print(f"  STORAGE_ONLY     {len(B - A)}")
        print()
        print("  --- audited targets: BEFORE ---")
        for sid in TARGET_IDS:
            d = before[sid]
            if d.get("missing"):
                print(f"    id {sid}: MISSING FROM STORAGE")
                continue
            blockers = []
            if d["verification_status"] == "quarantined":
                blockers.append("quarantined")
            if d["is_archived"]:
                blockers.append("archived")
            if d["is_verified"] is not True:
                blockers.append("not_verified")
            if not d["image_url"]:
                blockers.append("no_image")
            if not d["image_verified_at"]:
                blockers.append("image_unverified")
            if d["image_source_type"] == "wikimedia":
                blockers.append("wikimedia")
            other = [b for b in blockers if b not in ("no_image", "image_unverified")]
            print(f"    id {sid:<5} blockers={','.join(blockers) or '-'}"
                  f"{'  OTHER-BLOCKER!' if other else ''}")
            print(f"            title  : {str(d['title'])[:70]}")
            print(f"            src    : {str(d['official_source_url'])[:78]}")
        print()

        session.rollback()
    finally:
        session.close()

    # ---------- run the existing pipeline, scoped to the audited ids ----------
    runner = ImageCoverageRunner(
        get_session_factory,
        dry_run=not args.apply,
        plan_only=not args.apply,
        batch_size=len(TARGET_IDS),
        max_workers=2,
        exclude_quarantined=True,
        skip_terminally_evaluated=True,
        logo_only=False,
        per_record_budget_seconds=args.budget_seconds,
    )
    metrics = runner.run(ids=list(TARGET_IDS), limit=len(TARGET_IDS))

    print("  --- pipeline metrics ---")
    for k, v in metrics.as_dict().items():
        print(f"    {k:26} {v}")
    print()

    print("  --- per-record outcomes ---")
    rows = list(getattr(metrics, "outcomes", None) or [])
    tally: dict[str, int] = {}
    for r in rows:
        oc = outcome(r)
        tally[oc] = tally.get(oc, 0) + 1
        print(f"    id {r.get('scholarship_id'):<5} {oc:30} "
              f"status={str(r.get('status')):22} candidates={r.get('candidates')}")
        if r.get("error"):
            print(f"            error: {str(r.get('error'))[:88]}")
        if r.get("page_error"):
            print(f"            page_error: {str(r.get('page_error'))[:80]}")
        if r.get("image_url"):
            print(f"            image_url: {str(r.get('image_url'))[:92]}")
    print()
    print(f"  OUTCOME TALLY {tally}")
    print()
    print(f"=== COMPLETE - mode was {'APPLY' if args.apply else 'READ-ONLY PLAN'} ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)