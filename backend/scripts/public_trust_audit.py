#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY audit of the public trust contract.

Reports which records the canonical predicate currently admits despite an
unresolved authoritative verification status, which is the population that a
publication-policy fix would remove. No writes; one transaction, rolled back.

Usage:
    SCHOLARZONE_DATABASE_URL=... python scripts/public_trust_audit.py
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
    from sqlalchemy import func, select

    from app.database import get_engine, get_session_factory
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions
    from app.verification_contract import (
        AUTHORITATIVE_VERIFIED_STATUS,
        UNCERTAIN_VERIFICATION_STATUS,
        public_verified_from_status,
    )

    engine = get_engine()
    session = get_session_factory()()
    try:
        conds = public_visibility_conditions()
        A = sorted(set(session.execute(
            select(Scholarship.id).where(*conds)).scalars().all()))
        B = sorted(set(session.execute(select(Scholarship.id)).scalars().all()))

        print("=" * 78)
        print("PUBLIC TRUST CONTRACT AUDIT (read-only)")
        print("=" * 78)
        print(f"  authoritative verified status : {AUTHORITATIVE_VERIFIED_STATUS!r}")
        print(f"  uncertain status             : {UNCERTAIN_VERIFICATION_STATUS!r}")
        print(f"  STORAGE                      : {len(B)}")
        print(f"  PUBLIC (current predicate)   : {len(A)}")
        print(f"  STORAGE_ONLY                 : {len(B - set(A))}")
        print(f"  PUBLIC_ONLY                  : {len(set(A) - set(B))}")
        print()

        rows = {r["id"]: r for r in session.execute(
            select(Scholarship.id, Scholarship.title, Scholarship.verification_status,
                   Scholarship.is_verified, Scholarship.is_archived,
                   Scholarship.image_url, Scholarship.image_kind,
                   Scholarship.official_source_url)
            .where(Scholarship.id.in_(A))).mappings().all()}

        by_status: dict[str, list[int]] = {}
        for sid in A:
            by_status.setdefault(
                str(rows[sid]["verification_status"]), []).append(sid)
        print("  --- public rows by authoritative verification_status ---")
        for status, ids in sorted(by_status.items(), key=lambda kv: -len(kv[1])):
            mark = "" if status == AUTHORITATIVE_VERIFIED_STATUS else "   <-- NOT authoritative"
            print(f"    {status!r:22} {len(ids):4}{mark}")
        print()

        non_active = sorted(sid for sid in A
                            if not public_verified_from_status(
                                rows[sid]["verification_status"]))
        print(f"  PUBLIC rows whose status is NOT authoritative: {len(non_active)}")
        print(f"  ids: {non_active}")
        print()

        needs_review_public = sorted(
            sid for sid in A
            if str(rows[sid]["verification_status"]) == UNCERTAIN_VERIFICATION_STATUS)
        print(f"  PUBLIC rows with status='{UNCERTAIN_VERIFICATION_STATUS}': "
              f"{len(needs_review_public)}")
        print(f"  ids: {needs_review_public}")
        print()

        # contradiction scan across the whole catalogue, not just the public set
        contra_all = session.execute(select(Scholarship.id).where(
            Scholarship.verification_status == UNCERTAIN_VERIFICATION_STATUS,
            Scholarship.is_verified.is_(True))).scalars().all()
        contra_public = sorted(set(contra_all) & set(A))
        print("  --- contract invariants ---")
        print(f"  needs_review AND legacy is_verified=True (all storage): "
              f"{len(set(contra_all))} {sorted(set(contra_all))}")
        print(f"  ... of those, currently PUBLIC                    : "
              f"{len(contra_public)} {contra_public}")
        print()

        quarantined = sorted(set(session.execute(
            select(Scholarship.id).where(
                Scholarship.verification_status == "quarantined")).scalars().all()))
        archived = sorted(set(session.execute(
            select(Scholarship.id).where(
                Scholarship.is_archived.is_(True))).scalars().all()))
        print(f"  quarantined in storage : {len(quarantined)} "
              f"| any public: {sorted(set(quarantined) & set(A))}")
        print(f"  archived in storage    : {len(archived)} "
              f"| any public: {sorted(set(archived) & set(A))}")
        print()

        print("  --- detail for every public non-authoritative record ---")
        for sid in non_active:
            r = rows[sid]
            print(f"    id {sid}: {str(r['title'])[:56]}")
            print(f"        verification_status={r['verification_status']!r} "
                  f"is_verified={r['is_verified']} is_archived={r['is_archived']}")
            print(f"        public_verified_from_status="
                  f"{public_verified_from_status(r['verification_status'])}")
            print(f"        image_url={str(r['image_url'])[:60]}")
            print(f"        image_kind={r['image_kind']!r}")
            print(f"        source={str(r['official_source_url'])[:64]}")
        session.rollback()
    finally:
        session.close()
        engine.dispose()
    print("\n=== AUDIT COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)