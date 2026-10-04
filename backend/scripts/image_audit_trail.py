#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only audit trail for specific scholarships.

Every statement here is a SELECT against ``scholarship_image_audit``. The script
creates no mutation and updates no scholarship: proving a trigger fires by
writing to a row would corrupt the very evidence this trail exists to preserve.

It exists because attribution needs three things at once - what changed, which
fields, and who wrote it - and the aggregate checks in ``verify_image_audit.py``
report only totals. ``writer_context`` is the column that separates a maintenance
stage from an unaccounted writer, so it is printed in full for every row.

Usage
-----
    SCHOLARZONE_DATABASE_URL=... python scripts/image_audit_trail.py --ids 14,130,554
    SCHOLARZONE_DATABASE_URL=... python scripts/image_audit_trail.py --ids 14 --since-id 0
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

COLUMNS = ("id", "scholarship_id", "changed_at_utc", "changed_fields",
           "writer_context", "application_name", "client_addr", "transaction_id")


def parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            out.append(int(chunk))
        except ValueError:
            sys.exit(f"ERROR: {chunk!r} is not an integer id")
    if not out:
        sys.exit("ERROR: no ids given")
    return out


def shorten(value, limit: int = 96) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True, help="comma-separated scholarship ids")
    ap.add_argument("--since-id", type=int, default=0,
                    help="only rows with id greater than this")
    args = ap.parse_args()
    ids = parse_ids(args.ids)

    from sqlalchemy import create_engine, text

    engine = create_engine(DATABASE_URL)
    try:
        with engine.connect() as c:
            total = c.execute(text("SELECT count(*) FROM scholarship_image_audit")).scalar()
            high = c.execute(text("SELECT coalesce(max(id), 0) FROM scholarship_image_audit")).scalar()
            print("=" * 78)
            print("IMAGE AUDIT TRAIL (read-only)")
            print("=" * 78)
            print(f"  audit rows in table : {total}")
            print(f"  highest audit id    : {high}")
            print(f"  ids requested       : {ids}")
            print(f"  since_id            : {args.since_id}")
            print()

            rows = c.execute(text(
                "SELECT id, scholarship_id, changed_at_utc, changed_fields, "
                "writer_context, application_name, client_addr, transaction_id "
                "FROM scholarship_image_audit WHERE scholarship_id = ANY(:ids) "
                "AND id > :since ORDER BY id"),
                {"ids": ids, "since": args.since_id}).all()

            if not rows:
                print("  NO audit rows for these ids"
                      + (" above the requested id" if args.since_id else ""))
                print()
                return 0

            by_id: dict[int, list] = {}
            for r in rows:
                by_id.setdefault(r[1], []).append(r)

            for sid in ids:
                mine = by_id.get(sid, [])
                print(f"  --- id {sid}: {len(mine)} audit row(s) ---")
                for r in mine:
                    d = dict(zip(COLUMNS, r))
                    print(f"    audit_id={d['id']}  at={d['changed_at_utc']}  txn={d['transaction_id']}")
                    print(f"      changed_fields : {shorten(d['changed_fields'], 160)}")
                    print(f"      writer_context : {d['writer_context']!r}")
                    print(f"      application    : {shorten(d['application_name'], 48)!r}"
                          f"  client_addr={shorten(d['client_addr'], 40)!r}")
                print()

            contexts: dict[str, int] = {}
            for r in rows:
                key = r[4] if r[4] else "unknown"
                contexts[str(key)] = contexts.get(str(key), 0) + 1
            print(f"  writer_context tally: {contexts}")
            print()
            return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)