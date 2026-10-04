#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY: full stage detail for maintenance runs around the reversion.

Usage: SCHOLARZONE_DATABASE_URL=... python scripts/run_stages_detail.py [run_id...]
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
    from sqlalchemy import text

    from app.database import get_engine

    wanted = [int(a) for a in sys.argv[1:]] or []
    engine = get_engine()
    session = engine.connect()
    try:
        print("=" * 78)
        print("MAINTENANCE RUN STAGE DETAIL (read-only)")
        print("=" * 78)
        if wanted:
            q = text("SELECT * FROM maintenance_runs WHERE id = ANY(:ids) ORDER BY id DESC")
            rows = session.execute(q, {"ids": wanted}).mappings().all()
        else:
            rows = session.execute(text(
                "SELECT * FROM maintenance_runs ORDER BY id DESC LIMIT 12")).mappings().all()

        for r in rows:
            d = dict(r)
            print()
            print(f"  --- run {d.get('id')}  {d.get('started_at')} -> {d.get('finished_at')}")
            print(f"      worker      : {d.get('worker')}")
            print(f"      status      : {d.get('status')}")
            print(f"      dry_run     : {d.get('dry_run')}")
            print(f"      stages      : {d.get('stages')}")
            print(f"      counts      : {str(d.get('counts'))[:1400]}")
            if d.get("error_summary"):
                print(f"      errors      : {str(d.get('error_summary'))[:300]}")

        print()
        print("  --- which runs touched the three targets? ---")
        q2 = text(
            "SELECT id, scholarship_id, field_name, old_value, new_value "
            "FROM scholarship_verification_history "
            "WHERE scholarship_id = ANY(:ids) AND field_name LIKE 'image%' "
            "ORDER BY id DESC LIMIT 25")
        for r in session.execute(q2, {"ids": [14, 130, 554]}).mappings().all():
            print("   ", {k: str(v)[:52] for k, v in dict(r).items()})

        session.rollback()
    finally:
        session.close()
        engine.dispose()
    print("\n=== COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)