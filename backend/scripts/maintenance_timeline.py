#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY: which maintenance stages ran, when, and what did they touch.

Correlates recorded stage executions with the observed image-state reverts so
the responsible writer is identified from evidence rather than inference.

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

TARGETS = (14, 130, 554)


def main() -> int:
    from sqlalchemy import inspect as sa_inspect, text

    from app.database import get_engine

    engine = get_engine()
    session = engine.connect()
    tables = set(sa_inspect(engine).get_table_names())
    try:
        print("=" * 78)
        print("MAINTENANCE RUN TIMELINE (read-only)")
        print("=" * 78)

        for t in ("maintenance_runs", "maintenance_cursors", "scholarship_snapshots",
                  "scholarship_restore_records", "scholarship_fetch_attempts"):
            print(f"  table present: {t:36} {t in tables}")

        print()
        if "maintenance_runs" in tables:
            cols = [c["name"] for c in sa_inspect(engine).get_columns("maintenance_runs")]
            print("  maintenance_runs columns:", cols)
            rows = session.execute(text(
                "SELECT * FROM maintenance_runs ORDER BY 1 DESC LIMIT 40")).mappings().all()
            print(f"  rows returned: {len(rows)}")
            for r in rows:
                d = dict(r)
                keep = {k: v for k, v in d.items()
                        if k in ("id", "stage", "started_at", "finished_at", "status",
                                 "counts", "detail", "created_at")}
                print("   ", {k: str(v)[:60] for k, v in keep.items()})

        print()
        print("  --- target rows: timestamps and current image state ---")
        q = ("SELECT id, title, updated_at, created_at, image_url, image_kind, "
             "image_source_url, image_source_type, image_verified_at, "
             "image_evaluated_at, image_evaluation_status, verification_status, "
             "last_verified_at, next_verification_due, is_archived "
             "FROM scholarships WHERE id = ANY(:ids) ORDER BY id")
        for r in session.execute(q, {"ids": list(TARGETS)}).mappings().all():
            print(f"    id {r['id']}: {str(r['title'])[:50]}")
            for k in ("image_url", "image_kind", "image_source_url", "image_source_type",
                      "image_verified_at", "image_evaluated_at",
                      "image_evaluation_status", "verification_status",
                      "last_verified_at", "next_verification_due",
                      "created_at", "updated_at"):
                print(f"        {k:26} {str(r[k])[:64]}")
            print()

        if "scholarship_restore_records" in tables:
            print("  --- restore records for targets ---")
            rc = [c["name"] for c in sa_inspect(engine).get_columns(
                "scholarship_restore_records")]
            print("    columns:", rc)
            q2 = "SELECT * FROM scholarship_restore_records WHERE scholarship_id = ANY(:ids)"
            for r in session.execute(q2, {"ids": list(TARGETS)}).mappings().all():
                print("   ", {k: str(v)[:40] for k, v in dict(r).items()})

        if "scholarship_snapshots" in tables:
            print("  --- snapshot rows for targets ---")
            q3 = "SELECT * FROM scholarship_snapshots WHERE scholarship_id = ANY(:ids) ORDER BY 1 DESC LIMIT 10"
            for r in session.execute(q3, {"ids": list(TARGETS)}).mappings().all():
                print("   ", {k: str(v)[:40] for k, v in dict(r).items()})

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