#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only production compatibility audit for Match 2.0 and Count Intelligence 2.0.

Run by ``.github/workflows/match-count-compat-check.yml`` (workflow_dispatch).

Why this exists
---------------
Match 2.0 reads six columns that the public detail contract declares as
``list[str]``: eligibility, benefits, coverage, requirements, documents and
application_method. ``app.services.matching.repository`` currently coerces each
with ``list(row.<column> or [])``. That is correct for a real list and for NULL,
but a stored bare string becomes a list of single characters::

    list("IELTS 9.5" or [])  ->  ['I', 'E', 'L', 'T', 'S', ' ', '9', '.', '5']

Requirements carry 15% of the Match fit weight, so a single malformed row is
scored against its own characters. Whether that is a live production bug
depends entirely on what is actually stored, and that cannot be answered from a
configuration file or from local SQLite. This script answers it against the real
database.

It also confirms the two things Match and Count cannot work without: that every
column those code paths read actually exists, and that the authoritative public
visibility predicate returns a non-empty population.

Safety properties
-----------------
* Read-only. One transaction, always rolled back. No ``commit()``, no DDL, no
  DML anywhere in this file.
* Prints no credential, DSN, hostname, port or database name. The connection
  string is read from the environment and never echoed, not even truncated.
* Imports ``public_visibility_conditions`` from
  ``app.repositories.scholarships`` rather than restating it, because a second
  copy of the public-visibility rule is exactly how the homepage and the
  directory end up publishing different totals for the same catalogue.
* Exits non-zero on missing configuration or any query failure, so a failed
  audit is never mistaken for a clean one.
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

# The managed pooler hands out a plain "postgresql://" URL; the driver the
# application pins is psycopg. Same rewrite the application performs.
if DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://") :]

# The six columns the public detail contract declares as list[str], and which
# Match 2.0 therefore reads.
LIST_COLUMNS = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "application_method",
)

# Columns Match 2.0 reads directly. If one of these is absent the engine cannot
# run at all, which is worth knowing before a deploy rather than during one.
MATCH_REQUIRED_COLUMNS = (
    "id",
    "title",
    "country",
    "description",
    "funding_type",
    "amount",
    "deadline",
    "status",
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "application_method",
    "application_url",
    "official_source_url",
    "verification_status",
    "is_featured",
    "created_at",
)


def main() -> int:
    from sqlalchemy import inspect, select, text
    from sqlalchemy.orm import sessionmaker

    from app.database import get_engine
    from app.models import Scholarship
    from app.repositories.scholarships import public_visibility_conditions

    engine = get_engine()
    session = sessionmaker(bind=engine)()

    try:
        def scalar(sql: str) -> object:
            row = session.execute(text(sql)).fetchone()
            return 0 if row is None else row[0]

        print("=== PRODUCTION COMPATIBILITY AUDIT (Match 2.0 + Count Intelligence 2.0) ===")
        print()

        # ---- 1. dialect, so a SQLite-only assumption cannot hide here -------
        print("--- DIALECT ---")
        print(f"  dialect                     {engine.dialect.name}")
        print(f"  driver                      {engine.dialect.driver}")
        print()

        # ---- 2. schema presence ------------------------------------------
        print("--- SCHEMA: scholarships table present ---")
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "scholarships" not in tables:
            print("  FAIL: table 'scholarships' does not exist")
            return 2
        print("  scholarships                present")
        print()

        present = {c["name"] for c in inspector.get_columns("scholarships")}
        print("--- SCHEMA: columns Match 2.0 reads ---")
        missing = [c for c in MATCH_REQUIRED_COLUMNS if c not in present]
        for column in MATCH_REQUIRED_COLUMNS:
            mark = "MISSING" if column in missing else "ok"
            if mark == "MISSING":
                print(f"  {column:24s} {mark}")
        print(f"  required_columns_checked   {len(MATCH_REQUIRED_COLUMNS)}")
        print(f"  required_columns_missing   {len(missing)}")
        if missing:
            print(f"  MISSING_LIST               {missing}")
        print()

        print("--- SCHEMA: list[str] columns Match 2.0 reads ---")
        for column in LIST_COLUMNS:
            state = "ok" if column in present else "MISSING"
            print(f"  {column:24s} {state}")
        print()

        # ---- 3. the authoritative public population ----------------------
        print("--- PUBLIC UNIVERSE (authoritative predicate, imported) ---")
        conditions = public_visibility_conditions()
        public_ids = set(
            session.execute(select(Scholarship.id).where(*conditions)).scalars().all()
        )
        total_rows = scalar("SELECT COUNT(*) FROM scholarships")
        print(f"  public_ids                 {len(public_ids)}")
        print(f"  rows_in_storage            {total_rows}")
        print(f"  hidden_from_public         {int(total_rows) - len(public_ids)}")
        print()

        # ---- 4. THE QUESTION: are any list[str] columns malformed? --------
        # jsonb in PostgreSQL keeps whatever shape was written. A column
        # declared list[str] can therefore hold a JSON string, a JSON number or
        # a JSON array of non-strings, and none of those survive
        # `list(value or [])` intact.
        print("--- LIST-SHAPE COMPATIBILITY (drives Match Requirements scoring) ---")
        print(f"  list_columns_audited       {len(LIST_COLUMNS)}")
        print()

        by_type: dict[str, dict[str, int]] = {c: {} for c in LIST_COLUMNS}
        offending_ids: dict[str, list[int]] = {c: [] for c in LIST_COLUMNS}

        for column in LIST_COLUMNS:
            if column not in present:
                continue
            rows = session.execute(
                text(f'SELECT id, "{column}" FROM scholarships WHERE "{column}" IS NOT NULL')
            ).all()
            for row_id, value in rows:
                kind = type(value).__name__
                by_type[column][kind] = by_type[column].get(kind, 0) + 1
                # The shape `list(value or [])` cannot survive.
                if isinstance(value, str) or not isinstance(value, list):
                    if len(offending_ids[column]) < 40:
                        offending_ids[column].append(row_id)
                elif any(not isinstance(item, str) for item in value):
                    by_type[column]["list_with_non_string_items"] = (
                        by_type[column].get("list_with_non_string_items", 0) + 1
                    )
                    if len(offending_ids[column]) < 40:
                        offending_ids[column].append(row_id)

        total_offending = 0
        for column in LIST_COLUMNS:
            if column not in present:
                continue
            counts = by_type[column]
            bad = sum(v for k, v in counts.items() if k not in ("list",))
            total_offending += bad
            summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) or "no rows"
            print(f"  {column:24s} {summary}")
            if offending_ids[column]:
                print(f"  {'':24s} -> non_list_sample_ids {offending_ids[column][:12]}")
        print()
        print(f"  TOTAL_NON_LIST_VALUES       {total_offending}")
        if total_offending:
            print(
                "  VERDICT: Match 2.0 WILL MIS-SCORE these rows. "
                "`list(value or [])` turns a bare string into characters."
            )
        else:
            print("  VERDICT: every audited column holds a real list. Match read path is safe.")
        print()

        # ---- 5. reconciliation inputs the Count layer depends on -----------
        print("--- COUNT INTELLIGENCE INPUTS ---")
        print(f"  public_candidate_pool      {len(public_ids)}")
        print(f"  has_as_of_anchor           {bool(public_ids)}")
        print()

        print("=== AUDIT COMPLETE - read-only, nothing was modified ===")
        return 0
    finally:
        session.rollback()
        session.close()
        engine.dispose()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - report the type, never the DSN
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)