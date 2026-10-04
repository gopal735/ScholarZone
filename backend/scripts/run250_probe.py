#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""READ-ONLY probe: is maintenance_runs id 250 genuinely active?

Every statement is a SELECT. It reads the run row, looks for any later run,
and checks whether the audit trail shows image writes after the run started.
No row is created, altered or removed.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text  # noqa: E402

from app.database import get_engine  # noqa: E402

STARTED = "2026-10-04 09:13:57"


def main() -> int:
    engine = get_engine()
    if engine.dialect.name != "postgresql":
        print(f"  NOT PRODUCTION: dialect is {engine.dialect.name}")
        return 1
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        print("=== RUN 250 ROW ===")
        row = c.execute(text(
            "SELECT id, run_id, started_at, finished_at, status, worker, "
            "dry_run, duration_ms, error_summary, stages, counts "
            "FROM maintenance_runs WHERE id = 250")).mappings().one_or_none()
        if row is None:
            print("  id 250: NOT PRESENT")
        else:
            for k, v in row.items():
                print(f"    {k:16}= {str(v)[:300]}")

        print()
        print("=== RUNS AFTER 250 (does anything supersede it?) ===")
        for r in c.execute(text(
                "SELECT id, run_id, started_at, finished_at, status, dry_run, "
                "counts->>'stages_run' AS stages_run "
                "FROM maintenance_runs WHERE id > 250 ORDER BY id")).mappings().all():
            print(f"    id={r['id']} run={r['run_id']} started={r['started_at']} "
                  f"finished={r['finished_at']} status={r['status']} "
                  f"dry_run={r['dry_run']} stages={r['stages_run']}")

        print()
        print("=== AUDIT ACTIVITY AFTER RUN 250 STARTED ===")
        r = c.execute(text(
            "SELECT count(*) AS rows_after, max(changed_at_utc) AS latest, "
            "count(DISTINCT scholarship_id) AS records "
            "FROM scholarship_image_audit WHERE changed_at_utc > :t"),
            {"t": STARTED}).mappings().one()
        print(f"    audit rows after {STARTED}: {r['rows_after']} "
              f"(latest {r['latest']}, distinct records {r['records']})")

        print()
        print("=== HIGHEST AUDIT ID / AGE OF THE TRAIL ===")
        r = c.execute(text(
            "SELECT max(id) AS max_id, max(changed_at_utc) AS latest, "
            "count(*) AS total FROM scholarship_image_audit")).mappings().one()
        print(f"    max_id={r['max_id']} latest={r['latest']} total={r['total']}")

        print()
        print("=== I6 BUCKET NOW (image_url set, image_kind empty) ===")
        for r in c.execute(text(
                "SELECT id, image_kind, image_verified_at, updated_at "
                "FROM scholarships WHERE image_url IS NOT NULL AND image_kind IS NULL "
                "ORDER BY id")).mappings().all():
            print(f"    id={r['id']} verified_at={r['image_verified_at']} "
                  f"updated_at={r['updated_at']}")

        print()
        print("=== TARGET 14 / 130 / 554 image state now ===")
        for r in c.execute(text(
                "SELECT id, image_url, image_kind, image_verified_at, "
                "image_evaluation_status FROM scholarships "
                "WHERE id IN (14,130,554) ORDER BY id")).mappings().all():
            print(f"    id={r['id']} kind={r['image_kind']!r} "
                  f"verified_at={r['image_verified_at']} "
                  f"eval={r['image_evaluation_status']!r} "
                  f"url={str(r['image_url'])[:60]!r}")

    print()
    print("=== READ-ONLY PROBE COMPLETE ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
