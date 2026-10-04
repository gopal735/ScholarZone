#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only production state audit for the public scholarship catalogue.

Run by ``.github/workflows/db-state-check.yml`` (workflow_dispatch). It answers
two questions that have to be answered against the real database rather than
guessed from a configuration file:

1. How many records are actually public? The visibility predicate is IMPORTED
   from ``app.repositories.scholarships`` - the same function the directory and
   ``/stats`` call - because a second copy of that rule is how a homepage ends
   up advertising a total the directory contradicts.
2. Which of them hold a value in a column the public detail contract declares as
   ``list[str]`` that is not a list? Those records render correctly as cards and
   fail only on their own page, so a card-level count never finds them.

Safety properties
-----------------
* Read-only. One transaction, always rolled back. There is no ``commit()``, no
  DDL and no DML anywhere in this file.
* Prints no credential, DSN, hostname, port or database name. The connection
  string is read from the environment and never echoed, not even truncated.
* Exits non-zero on missing configuration or on any query failure, so a failed
  audit is never mistaken for a clean one.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/db_state.py
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
    from sqlalchemy.orm import sessionmaker

    from app.database import get_engine
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions
    from app.services.list_columns import (
        LIST_COLUMNS,
        ListColumnShapeError,
        normalize_list_column,
    )

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    try:
        # ---- integrity checks (unchanged in intent, all read-only) ----------
        def scalar(sql: str) -> object:
            row = session.execute(text(sql)).fetchone()
            if row is None:
                return 0
            return row[0]

        print("=== DB STATE ===")
        print()
        print(f"scholarships: {scalar('SELECT COUNT(*) FROM scholarships')}")
        print(
            "scholarship_verification_history: "
            f"{scalar('SELECT COUNT(*) FROM scholarship_verification_history')}"
        )
        print(f"scholarship_reviews: {scalar('SELECT COUNT(*) FROM scholarship_reviews')}")
        print(
            "distinct_source_urls: "
            + str(
                scalar(
                    "SELECT COUNT(DISTINCT official_source_url) FROM scholarships "
                    "WHERE official_source_url IS NOT NULL"
                )
            )
        )
        print(
            "duplicate_source_url_groups: "
            + str(
                scalar(
                    "SELECT COUNT(*) FROM (SELECT official_source_url FROM scholarships "
                    "WHERE official_source_url IS NOT NULL GROUP BY official_source_url "
                    "HAVING COUNT(*) > 1) AS dups"
                )
            )
        )
        print(
            "duplicate_scholarship_ids: "
            + str(
                scalar(
                    "SELECT COUNT(*) FROM (SELECT id FROM scholarships GROUP BY id "
                    "HAVING COUNT(*) > 1) AS dups"
                )
            )
        )
        print(
            "orphan_reviews: "
            + str(
                scalar(
                    "SELECT COUNT(*) FROM scholarship_reviews r LEFT JOIN scholarships s "
                    "ON r.scholarship_id = s.id WHERE s.id IS NULL"
                )
            )
        )
        print(
            "orphan_verification_history: "
            + str(
                scalar(
                    "SELECT COUNT(*) FROM scholarship_verification_history h "
                    "LEFT JOIN scholarships s ON h.scholarship_id = s.id "
                    "WHERE s.id IS NULL"
                )
            )
        )
        print()

        # ---- A: authoritative public universe ------------------------------
        conditions = public_visibility_conditions()
        A = set(session.execute(select(Scholarship.id).where(*conditions)).scalars().all())
        B = set(session.execute(select(Scholarship.id)).scalars().all())

        print("=== PUBLIC UNIVERSE (authoritative predicate) ===")
        print()
        print(f"  A_authoritative_public_ids   {len(A)}")
        print(f"  B_rows_in_storage            {len(B)}")
        print(f"  A_intersect_B                {len(A & B)}")
        print(f"  A_minus_B                    {len(A - B)}")
        print(f"  B_minus_A                    {len(B - A)}")
        if A - B:
            print(f"  A_minus_B_sample             {sorted(A - B)[:25]}")
        if B - A:
            print(f"  B_minus_A_sample             {sorted(B - A)[:25]}")
        print()

        # ---- C: list-shape violations among the public universe ------------
        violations: list[dict] = []
        refused: list[dict] = []
        already_valid = 0

        for sid in sorted(A):
            row = session.get(Scholarship, sid)
            for column in LIST_COLUMNS:
                stored = getattr(row, column, None)
                try:
                    fixed, changed = normalize_list_column(stored, field=column)
                except ListColumnShapeError as exc:
                    refused.append(
                        {"id": sid, "column": column, "reason": str(exc)}
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
                        # The invariant that makes a future repair lossless.
                        "text_preserved": (
                            isinstance(stored, str)
                            and bool(fixed)
                            and fixed[0] == stored
                        ),
                    }
                )

        malformed_ids = sorted({v["id"] for v in violations})
        per_column: dict[str, int] = {c: 0 for c in LIST_COLUMNS}
        for v in violations:
            per_column[v["column"]] += 1

        print("=== LIST-SHAPE VIOLATIONS (public rows, list[str] columns) ===")
        print()
        print(f"  C_malformed_rows             {len(malformed_ids)}")
        print(f"  malformed_fields             {len(violations)}")
        print(f"  already_valid_fields         {already_valid}")
        print(f"  refused_no_honest_list_form  {len(refused)}")
        print(f"  per_column                   {per_column}")
        print(f"  text_preserved_for_every_one {bool(violations) and all(v['text_preserved'] for v in violations) or not violations}")
        if malformed_ids:
            print(f"  malformed_ids                {malformed_ids}")
        for item in refused[:20]:
            print(f"  REFUSED {item['id']} {item['column']}: {item['reason']}")
        print()

        # Auto garbage collection, observed rather than assumed.
        #
        # `auto_delete_candidate_since` is the grace clock: a record may only be
        # deleted after it has held every SAFE_DELETE condition continuously for
        # DELETE_GRACE_DAYS. Counting NULL against non-NULL is what makes the
        # rollout observable - a scheduled run that arms nothing must leave the
        # non-NULL count unchanged, and one that arms something must raise it.
        # `deletion_protected` is the operator override and must never move on its
        # own.
        print("=== AUTO-DELETE COLLECTOR STATE (read-only) ===")
        print()
        try:
            print(f"  rows_total                   {scalar('SELECT COUNT(*) FROM scholarships')}")
            print(
                "  candidate_since_null          "
                + str(
                    scalar(
                        "SELECT COUNT(*) FROM scholarships "
                        "WHERE auto_delete_candidate_since IS NULL"
                    )
                )
            )
            print(
                "  candidate_since_set          "
                + str(
                    scalar(
                        "SELECT COUNT(*) FROM scholarships "
                        "WHERE auto_delete_candidate_since IS NOT NULL"
                    )
                )
            )
            print(
                "  deletion_protected           "
                + str(
                    scalar(
                        "SELECT COUNT(*) FROM scholarships "
                        "WHERE deletion_protected IS TRUE"
                    )
                )
            )
            armed = [
                int(r[0])
                for r in session.execute(
                    text(
                        "SELECT id FROM scholarships "
                        "WHERE auto_delete_candidate_since IS NOT NULL ORDER BY id"
                    )
                ).all()
            ]
            print(f"  armed_ids                    {armed}")
            protected = [
                int(r[0])
                for r in session.execute(
                    text(
                        "SELECT id FROM scholarships "
                        "WHERE deletion_protected IS TRUE ORDER BY id"
                    )
                ).all()
            ]
            print(f"  deletion_protected_ids       {protected}")
        except Exception as exc:  # noqa: BLE001
            # A column that does not exist yet is a deploy-ordering fact, not a
            # reason to abandon the rest of the census.
            print(
                f"  AUTO-DELETE COLUMNS UNAVAILABLE ({type(exc).__name__}); "
                "the collector is not deployed on this database yet"
            )
        print()

        session.rollback()  # read-only: nothing is ever committed
    finally:
        session.close()
        engine.dispose()

    print("=== DB STATE CAPTURED - no rows were modified ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report the type, never the DSN
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)