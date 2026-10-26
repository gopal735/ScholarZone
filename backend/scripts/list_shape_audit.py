#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only scan of the AUTHORITATIVE public scholarship universe.

Purpose
-------
Establish exactly how many public records exist, and exactly which of them hold
a malformed value in a column that the public detail contract declares as
``list[str]``. This is a measurement tool. It opens a transaction, reads, and
rolls back. It never writes, never commits, and never prints the connection
string, host, database name or any credential.

Why this exists
---------------
An earlier artifact claimed 117 affected records. It turned out to have been
built against a configuration file rather than the database, and against a
different population again from the one this script measures. A repair scope
that is guessed is worse than no repair scope at all, so the universe is
derived from the same function the public API itself calls.

The visibility predicate is IMPORTED, never reimplemented. The directory and the
homepage statistics both call ``public_visibility_conditions()``; a second copy
of that rule is how a homepage ends up advertising a total the directory
contradicts. See ``app/repositories/scholarships.py``.

Usage
-----
    SCHOLARZONE_ENVIRONMENT=production \\
    SCHOLARZONE_DATABASE_URL=... \\
    python scripts/list_shape_audit.py

    # optional: emit the full per-field manifest as JSON
    ... python scripts/list_shape_audit.py --manifest /tmp/manifest.json

Exit codes
----------
    0  scan completed (regardless of how many violations were found)
    1  configuration or connectivity problem
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", help="write the full violation manifest here as JSON")
    args = parser.parse_args()

    from sqlalchemy import select
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings
    from app.database import get_engine
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions
    from app.services.list_columns import (
        LIST_COLUMNS,
        ListColumnShapeError,
        normalize_list_column,
    )

    settings = get_settings()
    engine = get_engine()
    factory = sessionmaker(bind=engine)
    session = factory()

    try:
        conditions = public_visibility_conditions()

        # A = authoritative public universe, by the API's own definition.
        public_ids = sorted(
            set(session.execute(select(Scholarship.id).where(*conditions)).scalars().all())
        )

        # B = every row in storage, so the two sets can be reconciled rather
        # than assumed to line up.
        stored_ids = sorted(set(session.execute(select(Scholarship.id)).scalars().all()))

        violations: list[dict] = []
        refused: list[dict] = []
        already_valid = 0

        # Only public rows can fail a public endpoint, so the scan is bounded to
        # the universe under test rather than every archived row.
        for sid in public_ids:
            row = session.get(Scholarship, sid)
            for column in LIST_COLUMNS:
                stored = getattr(row, column, None)
                try:
                    fixed, changed = normalize_list_column(stored, field=column)
                except ListColumnShapeError as exc:
                    refused.append(
                        {
                            "id": sid,
                            "column": column,
                            "stored_type": type(stored).__name__,
                            "reason": str(exc),
                        }
                    )
                    continue
                if not changed:
                    already_valid += 1
                    continue
                violations.append(
                    {
                        "id": sid,
                        "column": column,
                        "original_type": type(stored).__name__,
                        "target_value": fixed,
                        # The invariant that makes this repair lossless.
                        "text_preserved": (
                            isinstance(stored, str) and bool(fixed) and fixed[0] == stored
                        ),
                    }
                )
        session.rollback()  # read-only: never leave a write behind
    finally:
        session.close()
        engine.dispose()

    A, B = set(public_ids), set(stored_ids)
    malformed_ids = {v["id"] for v in violations}

    report = {
        "environment": settings.environment,
        "authoritative_public_ids_count": len(A),
        "rows_scanned_count": len(B),
        "malformed_row_count": len(malformed_ids),
        "malformed_field_count": len(violations),
        "columns_declared_list_str": list(LIST_COLUMNS),
        "already_valid_field_count": already_valid,
        "refused_count": len(refused),
        "columns_changed": {
            c: sum(1 for v in violations if v["column"] == c) for c in LIST_COLUMNS
        },
        "intersection_A_and_B": len(A & B),
        "A_minus_B": len(A - B),
        "B_minus_A": len(B - A),
        "A_minus_B_sample": sorted(A - B)[:25],
        "B_minus_A_sample": sorted(B - A)[:25],
        "malformed_ids": sorted(malformed_ids),
        "text_preserved_for_every_violation": all(v["text_preserved"] for v in violations),
    }

    print("=== AUTHORITATIVE PUBLIC UNIVERSE / LIST-SHAPE AUDIT (read-only) ===")
    print()
    for key in (
        "environment",
        "authoritative_public_ids_count",
        "rows_scanned_count",
        "malformed_row_count",
        "malformed_field_count",
        "already_valid_field_count",
        "refused_count",
        "intersection_A_and_B",
        "A_minus_B",
        "B_minus_A",
    ):
        print(f"  {key:38} {report[key]}")
    print(f"  {'columns_changed':38} {report['columns_changed']}")
    print(f"  {'text_preserved_for_every_violation':38} {report['text_preserved_for_every_violation']}")
    print()
    if malformed_ids:
        print("  malformed ids:")
        print("   ", sorted(malformed_ids))
    if refused:
        print("  refused (no honest list form; must not be guessed):")
        for item in refused[:20]:
            print(f"    {item['id']} {item['column']}: {item['reason']}")
    print()

    if args.manifest:
        report["violations"] = violations
        report["refused"] = refused
        Path(args.manifest).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"  manifest written to {args.manifest}")

    print("=== AUDIT COMPLETE - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report, never leak the DSN
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
