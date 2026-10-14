#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY audit of storage-only scholarship rows.

Storage-only means "in the table but outside the canonical public universe".
That is a *visibility* fact, not a *disposability* fact: a record can be hidden
because it is archived (legitimate history), because it is quarantined (a
safety decision), or because it simply has no verified image yet (an ordinary
data-completeness gap on a perfectly good scholarship). Only this audit can tell
those apart, so it reports the exact predicate clause that hides each row, every
referencing child row, and a provisional classification.

This script performs no writes. It opens a transaction and rolls it back.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/storage_only_audit.py
    SCHOLARZONE_DATABASE_URL=... python scripts/storage_only_audit.py --manifest out.json

Exit codes: 0 audit completed, 1 configuration/connectivity failure.
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

# The exact clauses of public_visibility_conditions(). Named so a row can be
# reported as "hidden because X" rather than as an anonymous non-public row.
CLAUSES = [
    ("quarantined", "verification_status = 'quarantined'"),
    ("archived", "is_archived = TRUE"),
    ("not_verified", "is_verified is not TRUE"),
    ("no_image", "image_url IS NULL"),
    ("image_unverified", "image_verified_at IS NULL"),
    ("wikimedia_only_image", "image_source_type = 'wikimedia'"),
]

# Child tables that carry a scholarship_id, and whether losing the parent would
# destroy evidence a human or an auditor needs to see.
REFERENCES = [
    ("scholarship_verification_history", "scholarship_id", "HISTORICAL_EVIDENCE"),
    ("scholarship_reviews", "scholarship_id", "HISTORICAL_EVIDENCE"),
    ("scholarship_snapshots", "scholarship_id", "HISTORICAL_EVIDENCE"),
    ("scholarship_fetch_attempts", "scholarship_id", "OPERATIONAL_TRACE"),
    ("image_reviews", "scholarship_id", "HISTORICAL_EVIDENCE"),
    ("scholarship_restore_records", "scholarship_id", "RECOVERY_TRACE"),
    ("discovery_candidates", "matched_scholarship_id", "DISCOVERY_TRACE"),
]


def classify(row: dict, refs: dict) -> tuple[str, str]:
    """Provisional classification with a concrete reason.

    Ordering matters: a record with real history is never called disposable just
    because it also lacks an image.
    """
    hidden = row["hidden_by"]
    evidence = [t for t, _, kind in REFERENCES
                if kind == "HISTORICAL_EVIDENCE" and refs.get(t)]
    other = [t for t, _, _ in REFERENCES if refs.get(t)]

    if row["verification_status"] == "needs_review":
        return ("KEEP_REVIEW",
                "verification_status='needs_review' is an open human decision in the "
                "Admin Verification Center queue; it is pending work, not a dead row")
    if row["is_archived"]:
        return ("KEEP_HISTORICAL",
                "is_archived=TRUE: the application deliberately archives rather than "
                "deletes, so this row is preserved history")
    if evidence:
        return ("KEEP_REFERENCED",
                f"carries {len(evidence)} historical evidence table(s): {', '.join(evidence)}")
    if row["verification_status"] == "rejected":
        return ("NEEDS_MANUAL_REVIEW",
                "verification_status='rejected' is a deliberate recorded decision; "
                "whether a rejection is retained or purged is a product decision")
    if row["verification_status"] == "retired":
        return ("KEEP_HISTORICAL",
                "verification_status='retired': retired programmes are kept so a "
                "returning applicant is told the programme ended rather than shown "
                "a broken link")
    if hidden == {"not_verified"} and not other:
        return ("NEEDS_MANUAL_REVIEW",
                "unverified and unreferenced: cannot yet be judged disposable "
                "without product sign-off on unverified rows")
    if hidden and hidden <= {"no_image", "image_unverified"}:
        return ("KEEP_ACTIVE_INTERNAL",
                f"hidden only by image completeness ({sorted(hidden)}): a real "
                "scholarship awaiting a verified image, not a dead row")
    if hidden == {"wikimedia_only_image"}:
        return ("KEEP_ACTIVE_INTERNAL",
                "hidden because its only image is Wikimedia: needs a better source, "
                "not deletion")
    return ("NEEDS_MANUAL_REVIEW",
            f"hidden by {sorted(hidden)} with references {sorted(other) or 'none'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest")
    args = ap.parse_args()

    from sqlalchemy import select, text
    from sqlalchemy.orm import sessionmaker

    from app.database import get_engine
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    try:
        def scalar(sql):
            row = session.execute(text(sql)).fetchone()
            return row[0] if row else 0

        A = set(session.execute(select(Scholarship.id)
                                .where(*public_visibility_conditions())).scalars().all())
        B = set(session.execute(select(Scholarship.id)).scalars().all())
        storage_only = sorted(B - A)
        public_only = sorted(A - B)

        print("=" * 78)
        print("STORAGE-ONLY AUDIT (read-only)")
        print("=" * 78)
        print(f"  PUBLIC_UNIVERSE   {len(A)}")
        print(f"  STORAGE_UNIVERSE  {len(B)}")
        print(f"  INTERSECTION      {len(A & B)}")
        print(f"  STORAGE_ONLY      {len(storage_only)}")
        print(f"  PUBLIC_ONLY       {len(public_only)}")
        print()

        # reference counts, computed once per table. The inspector is used
        # rather than information_schema so the same script runs on SQLite and
        # on the production PostgreSQL without a dialect branch.
        from sqlalchemy import inspect as sa_inspect
        existing_tables = set(sa_inspect(engine).get_table_names())
        ref_counts: dict[int, dict[str, int]] = {}
        for table, col, _ in REFERENCES:
            if table not in existing_tables or col not in {
                    x["name"] for x in sa_inspect(engine).get_columns(table)}:
                continue
            mapping = dict(session.execute(text(
                f"SELECT {col}, COUNT(*) FROM {table} GROUP BY {col}")).all())

        cols = ["id", "title", "country", "verification_status", "is_verified",
                "is_archived", "image_url", "image_verified_at", "image_source_type",
                "official_source_url", "deadline_date", "deadline_precision",
                "created_at", "updated_at"]
        present = {c.name for c in Scholarship.__table__.columns}
        use = [c for c in cols if c in present]

        rows_out = []
        for sid in storage_only:
            row = session.get(Scholarship, sid)
            d = {c: getattr(row, c, None) for c in use}
            hidden = set()
            for name, _desc in CLAUSES:
                if name == "quarantined" and d.get("verification_status") == "quarantined":
                    hidden.add(name)
                elif name == "archived" and d.get("is_archived"):
                    hidden.add(name)
                elif name == "not_verified" and d.get("is_verified") is not True:
                    hidden.add(name)
                elif name == "no_image" and not d.get("image_url"):
                    hidden.add(name)
                elif name == "image_unverified" and not d.get("image_verified_at"):
                    hidden.add(name)
                elif name == "wikimedia_only_image" and d.get("image_source_type") == "wikimedia":
                    hidden.add(name)
            refs = {t: mapping.get(sid, 0) for t, _c, _k in REFERENCES if t in mapping}
            d["hidden_by"] = hidden
            cls, reason = classify(d, refs)
            rows_out.append({
                "id": sid, "title": d.get("title"), "country": d.get("country"),
                "verification_status": d.get("verification_status"),
                "is_verified": d.get("is_verified"), "is_archived": d.get("is_archived"),
                "has_image": bool(d.get("image_url")),
                "official_source_url": d.get("official_source_url"),
                "deadline_date": str(d.get("deadline_date")),
                "hidden_by": sorted(hidden),
                "references": {k: v for k, v in refs.items() if v},
                "classification": cls, "reason": reason,
            })

        from collections import Counter
        by_cls = Counter(r["classification"] for r in rows_out)
        by_hidden = Counter(h for r in rows_out for h in r["hidden_by"])
        by_status = Counter(str(r["verification_status"]) for r in rows_out)
        with_refs = [r for r in rows_out if r["references"]]

        print("  --- classification ---")
        for k, v in sorted(by_cls.items()):
            print(f"    {k:26} {v}")
        print("  --- verification_status ---")
        for k, v in by_status.most_common():
            print(f"    {k:26} {v}")
        print("  --- hidden_by clause (rows can match several) ---")
        for k, v in by_hidden.most_common():
            print(f"    {k:26} {v}")
        print(f"  rows carrying any child reference: {len(with_refs)}")
        print()
        print("  --- per record ---")
        for r in rows_out:
            print(f"    id {r['id']:<6} {r['classification']:22} "
                  f"status={str(r['verification_status']):14} hidden_by={','.join(r['hidden_by']) or '-'}")
            print(f"           title: {str(r['title'])[:78]}")
            print(f"           reason: {r['reason'][:100]}")
            if r["references"]:
                print(f"           refs: {r['references']}")

        session.rollback()
    finally:
        session.close()
        engine.dispose()

    if args.manifest:
        Path(args.manifest).write_text(json.dumps({
            "public_universe": len(A), "storage_universe": len(B),
            "intersection": len(A & B), "storage_only": len(storage_only),
            "public_only": len(public_only), "records": rows_out,
        }, indent=2, default=str), encoding="utf-8")
        print(f"\nmanifest -> {args.manifest}")
    print("\n=== AUDIT COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)