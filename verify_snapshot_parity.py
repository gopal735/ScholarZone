#!/usr/bin/env python3
"""Verify that a public snapshot matches the database it was generated from.

The snapshot's header publishes counts. Before this existed nothing compared
them with the file's own contents or with the database, so a mismatch between
the header, the records and the source was invisible - and it would have been
invisible in exactly the cases that matter, because the snapshot is only
consulted when the API is down and nobody is comparing it against anything.

Usage:
    python verify_snapshot_parity.py --db backend/scholarzone.db \
        --snapshot frontend/public/scholarships-snapshot.json

Exit status is 0 when the parity checks pass and 1 when any fails, so it can be
run as a gate.

What it compares, record by record rather than by count alone:

  * total source rows
  * closed / archived / quarantined counts
  * the excluded union, with overlaps counted once
  * total public rows, from the canonical predicate
  * the exact public ID set - both Missing and Extra
  * per-field differences on every matching ID
  * visibility state (status, archived, quarantined)
  * the published statistics, recomputed over the exported records
  * the generated sort orderings, recomputed from the database

The script reads both inputs and writes to neither. It prints only IDs, field
names and counts - no scholarship content, so its output is safe to paste into
an issue or a CI log.

It deliberately does not claim which database production uses. Pass whatever
source you want to check against as --db; proving that source IS production is
a separate question this tool does not answer.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Any


REPOSITORY_ROOT = Path(__file__).resolve().parent
GENERATOR_PATH = REPOSITORY_ROOT / "generate_snapshot.py"


def load_generator():
    """Import generate_snapshot.py so the predicate and the field set are shared."""
    spec = importlib.util.spec_from_file_location("generate_snapshot_under_test", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PUBLIC_PREDICATE = (
    "status != 'closed' AND is_archived = 0 AND verification_status != 'quarantined'"
)


class Parity:
    """An accumulator of findings, each of which is a failed check."""

    def __init__(self) -> None:
        self.findings: list[str] = []
        self.checks = 0

    def check(self, label: str, passed: bool, detail: str = "") -> bool:
        self.checks += 1
        if passed:
            print(f"  PASS  {label}")
        else:
            suffix = f" -- {detail}" if detail else ""
            print(f"  FAIL  {label}{suffix}")
            self.findings.append(f"{label}{suffix}")
        return passed

    @property
    def ok(self) -> bool:
        return not self.findings


def _scalar(cursor: sqlite3.Cursor, sql: str) -> int:
    cursor.execute(sql)
    return int(cursor.fetchone()[0])


def verify(db_path: str, snapshot_path: str, generator) -> Parity:
    parity = Parity()

    if not Path(db_path).is_file():
        raise SystemExit(f"Not a database file: {db_path}")
    if not Path(snapshot_path).is_file():
        raise SystemExit(f"Not a snapshot file: {snapshot_path}")

    with open(snapshot_path, encoding="utf-8") as handle:
        snapshot = json.load(handle)

    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("scholarships"), list):
        raise SystemExit(f"{snapshot_path} is not a snapshot (no scholarships array).")

    records = snapshot["scholarships"]
    record_ids = [r["id"] for r in records]
    parity.check(
        "snapshot record IDs are unique",
        len(set(record_ids)) == len(record_ids),
        f"{len(record_ids) - len(set(record_ids))} duplicate id(s)",
    )

    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    try:
        print(f"\nComparing snapshot against source database\n  db:       {db_path}\n  snapshot: {snapshot_path}\n")

        # ---- Visibility predicate, restated. A NULL here silently removes a
        # record from both the public set and the excluded accounting, so it has
        # to be named rather than absorbed.
        print("Counts")
        for column in ("status", "is_archived", "verification_status"):
            nulls = _scalar(cursor, f"SELECT COUNT(*) FROM scholarships WHERE {column} IS NULL")
            parity.check(f"no NULL {column} in source", nulls == 0, f"{nulls} row(s)")

        source = _scalar(cursor, "SELECT COUNT(*) FROM scholarships")
        closed = _scalar(cursor, "SELECT COUNT(*) FROM scholarships WHERE status = 'closed'")
        archived = _scalar(cursor, "SELECT COUNT(*) FROM scholarships WHERE is_archived = 1")
        quarantined = _scalar(
            cursor,
            "SELECT COUNT(*) FROM scholarships WHERE verification_status = 'quarantined'",
        )
        excluded_union = _scalar(
            cursor,
            "SELECT COUNT(*) FROM scholarships "
            "WHERE status = 'closed' OR is_archived = 1 OR verification_status = 'quarantined'",
        )
        public = _scalar(cursor, f"SELECT COUNT(*) FROM scholarships WHERE {PUBLIC_PREDICATE}")

        meta = snapshot.get("meta", {})

        # source = public + excluded_union + deadline_passed, which is the
        # invariant that makes the published counts mean anything. The
        # per-category buckets are not summed: they overlap, by design.
        #
        # Checked on the header's own numbers first, because that is the claim
        # the snapshot makes. Checking the database against itself would always
        # pass, including when the header disagrees with it.
        header_source = meta.get("source_record_count")
        header_public = meta.get("public_record_count")
        header_union = meta.get("excluded_union")
        header_deadline = meta.get("deadline_passed")
        if isinstance(header_source, int) and isinstance(header_public, int) and isinstance(header_union, int):
            parity.check(
                "source reconciles (source = public + excluded_union)",
                header_source == header_public + header_union,
                f"header says source={header_source} public={header_public} union={header_union}"
                f" -> {header_public + header_union}",
            )
        else:
            parity.check(
                "source reconciles (source = public + excluded_union)",
                source == public + excluded_union,
                f"source={source} public={public} union={excluded_union} -> {public + excluded_union}",
            )

        parity.check(
            "meta.source_record_count matches the database",
            meta.get("source_record_count") == source,
            f"meta says {meta.get('source_record_count')!r}, database has {source}",
        )
        for name, value in (("closed", closed), ("archived", archived), ("quarantined", quarantined)):
            parity.check(
                f"meta.excluded.{name} matches the database",
                meta.get("excluded", {}).get(name) == value,
                f"meta says {meta.get('excluded', {}).get(name)!r}, database has {value}",
            )

        # ---- The ID set. Equal counts say nothing about equal records.
        print("\nRecord IDs")
        cursor.execute(f"SELECT id FROM scholarships WHERE {PUBLIC_PREDICATE} ORDER BY id")
        stored_public_ids = [int(row[0]) for row in cursor.fetchall()]

        # The derived bucket. A record whose deadline has passed is closed as
        # far as the catalogue is concerned, so it is not public even though
        # the stored status says otherwise. It is named separately so the union
        # still accounts for every source row, rather than the difference
        # between the stored rule and the published set silently vanishing.
        cursor.execute(
            "SELECT id, deadline_date FROM scholarships "
            f"WHERE {PUBLIC_PREDICATE}"
        )
        deadline_passed = []
        for row in cursor.fetchall():
            raw = row["deadline_date"]
            if not raw:
                continue
            try:
                deadline = date.fromisoformat(str(raw).split("T", 1)[0].split(" ", 1)[0])
            except ValueError:
                continue
            if deadline < date.today():
                deadline_passed.append(int(row["id"]))
        deadline_passed_set = set(deadline_passed)

        # The expected public set is the stored predicate minus that bucket.
        expected_ids = [rid for rid in stored_public_ids if rid not in deadline_passed_set]
        expected_public = public - len(deadline_passed)

        parity.check(
            "meta.deadline_passed matches the database",
            meta.get("deadline_passed") == len(deadline_passed),
            f"meta says {meta.get('deadline_passed')!r}, database has {len(deadline_passed)}",
        )
        parity.check(
            "meta.public_record_count matches the database",
            meta.get("public_record_count") == expected_public,
            f"meta says {meta.get('public_record_count')!r}, database has "
            f"{expected_public} public ({public} under the stored rule, minus "
            f"{len(deadline_passed)} with a passed deadline)",
        )
        parity.check(
            "meta.excluded_union matches the database",
            meta.get("excluded_union") == excluded_union + len(deadline_passed),
            f"meta says {meta.get('excluded_union')!r}, database has "
            f"{excluded_union} plus {len(deadline_passed)} deadline-passed",
        )
        parity.check(
            "source reconciles (source = public + excluded_union)",
            source == expected_public + excluded_union + len(deadline_passed),
            f"source={source} public={expected_public} union={excluded_union} "
            f"deadline_passed={len(deadline_passed)} -> "
            f"{expected_public + excluded_union + len(deadline_passed)}",
        )
        parity.check(
            "exported record count equals the canonical public count",
            len(records) == expected_public,
            f"{len(records)} exported, {expected_public} public",
        )

        actual_ids = sorted(record_ids)

        missing = sorted(set(expected_ids) - set(actual_ids))
        extra = sorted(set(actual_ids) - set(expected_ids))

        # A record the stored predicate publishes but the deadline rule excludes
        # is expected to be missing, not an error. A record that is neither
        # public nor deadline-excluded and is missing IS an error.
        unexplained_missing = [rid for rid in missing if rid not in deadline_passed_set]
        parity.check(
            "public ID sets match exactly",
            not unexplained_missing and not extra,
            f"unexplained missing={unexplained_missing[:20]} extra={extra[:20]}",
        )
        parity.check(
            "every missing record is one the deadline rule excludes",
            not unexplained_missing and set(missing) <= deadline_passed_set,
            f"missing without a passed deadline: {unexplained_missing[:20]}",
        )
        parity.check(
            "no non-public ID leaked into the snapshot",
            not extra,
            f"extra={extra[:20]}" if extra else "",
        )

        # ---- Visibility state per record. A record that was archived or
        # quarantined after the snapshot was generated must show up here.
        print("\nVisibility state")
        cursor.execute(
            "SELECT id, status, is_archived, verification_status FROM scholarships "
            f"WHERE {PUBLIC_PREDICATE}"
        )
        expected_state = {
            int(row["id"]): (row["status"], int(row["is_archived"] or 0), row["verification_status"])
            for row in cursor.fetchall()
        }
        state_mismatch = []
        for record in records:
            expected = expected_state.get(int(record["id"]))
            if expected is None:
                continue
            if (record.get("status"), record.get("verification_status")) != (expected[0], expected[2]):
                state_mismatch.append(int(record["id"]))
        parity.check(
            "status and verification_status agree per record",
            not state_mismatch,
            f"{len(state_mismatch)} record(s) differ, e.g. {state_mismatch[:20]}" if state_mismatch else "",
        )
        parity.check(
            "no archived record is present",
            all(r.get("is_archived") in (None, False, 0) for r in records),
            "an archived record is in the snapshot",
        )

        # ---- Per-record field parity.
        print("\nPer-record fields")
        cursor.execute(f"SELECT * FROM scholarships WHERE {PUBLIC_PREDICATE}")
        expected_rows = {int(row["id"]): row for row in cursor.fetchall()}

        field_differences: dict[str, list[int]] = {}
        for record in records:
            expected = expected_rows.get(int(record["id"]))
            if expected is None:
                continue
            # Use the same derivation date the snapshot used, not today. The
            # header records it, so a comparison against a snapshot generated
            # on another day is not silently wrong about deadlines it has
            # passed since - and a snapshot that does not record its date is
            # not something this tool can verify field-by-field.
            derived_at = (snapshot.get("meta") or {}).get("status_derived_at")
            if not isinstance(derived_at, str) or not derived_at:
                raise SystemExit(
                    f"{snapshot_path} has no meta.status_derived_at. Per-field "
                    "comparison needs the date the statuses were derived on; "
                    "regenerate the snapshot with the current generate_snapshot.py."
                )
            comparison_date = date.fromisoformat(derived_at)

            expected_record = generator._build_public_record(
                {column: expected[column] for column in expected.keys()},
                comparison_date,
            )
            for field, actual in record.items():
                # `generated_at` and friends are metadata; a record field must
                # match what the generator produces from this same database.
                if expected_record.get(field) != actual:
                    field_differences.setdefault(field, []).append(int(record["id"]))

        parity.check(
            "every exported field matches the source record",
            not field_differences,
            ", ".join(
                f"{field} differs on {len(ids)} record(s) e.g. {ids[:8]}"
                for field, ids in sorted(field_differences.items())
            ),
        )

        # ---- The public allowlist, checked against the generator's own list.
        print("\nPublic allowlist")
        public_fields = set(generator.PUBLIC_FIELDS)
        leaked = sorted(
            {field for record in records for field in record.keys()} - public_fields
        )
        parity.check(
            "no field outside the public allowlist",
            not leaked,
            f"non-public field(s): {leaked}",
        )
        forbidden = {
            "is_archived",
            "archived_at",
            "archived_reason",
            "is_verified",
            "verified_by",
            "verification_notes",
            "next_verification_due",
            "image_evaluation_status",
            "image_evaluated_at",
            "auto_delete_candidate_since",
            "deletion_protected",
            "created_at",
        }
        present_forbidden = sorted(
            {field for record in records for field in record.keys()} & forbidden
        )
        parity.check(
            "no internal workflow column exported",
            not present_forbidden,
            f"internal field(s): {present_forbidden}",
        )

        # ---- The published statistic, recomputed over the exported records.
        print("\nStatistics")
        stats = snapshot.get("stats", {})
        derived = {
            "total": len(records),
            "countries": len({r.get("country") for r in records if r.get("country")}),
            "open": sum(1 for r in records if r.get("status") == "open"),
            "closing_soon": sum(1 for r in records if r.get("status") == "closing-soon"),
            "upcoming": sum(1 for r in records if r.get("status") == "upcoming"),
            "verified_active": sum(1 for r in records if r.get("verified") is True),
            "with_image": sum(1 for r in records if r.get("image_url")),
            "with_official_source": sum(1 for r in records if r.get("official_source")),
        }
        for name, value in derived.items():
            parity.check(
                f"stats.{name} matches the exported records",
                stats.get(name) == value,
                f"stats says {stats.get(name)!r}, records give {value}",
            )

        parity.check(
            "verified flag matches the verification contract",
            all(r.get("verified") == (r.get("verification_status") == "active") for r in records),
            "a record's verified disagrees with its verification_status",
        )

        # ---- The generated orderings, recomputed from the database.
        print("\nSort orderings")
        published = (snapshot.get("meta") or {}).get("sort_orders") or {}
        if not isinstance(published, dict):
            parity.check("meta.sort_orders is an object", False, f"got {type(published).__name__}")
        else:
            # Recomputed against the DATABASE's public set, not against the
            # snapshot's. Comparing against the snapshot's own ids would make
            # the recomputation agree with itself whenever the two sets differ,
            # which is precisely when the ordering needs checking.
            expected_orders = generator._build_sort_orders(cursor, expected_ids)
            for mode in sorted(expected_orders):
                parity.check(
                    f"sort order '{mode}' matches the source",
                    published.get(mode) == expected_orders[mode],
                    "differs from the ordering recomputed from the database",
                )
            advertised = (snapshot.get("meta") or {}).get("sort_order_modes")
            parity.check(
                "advertised sort modes match the orderings present",
                advertised is None or sorted(advertised) == sorted(expected_orders),
                f"advertised {advertised!r}, present {sorted(expected_orders)}",
            )

        # ---- The filter options, recomputed from the exported records.
        print("\nFilter options")
        # The controls must be able to select what the catalogue holds, and must
        # not offer what it does not. A menu entry that cannot match is a filter
        # that looks like it works and returns nothing; a missing entry is a
        # value the catalogue has that cannot be reached from the UI. Both are
        # checked against the records here rather than against the header, so
        # the snapshot cannot drift from the data it ships.
        expected_options = {
            "countries": sorted({r.get("country") for r in records if r.get("country")}),
            "degrees": sorted({r.get("degree") for r in records if r.get("degree")}),
            "funding_types": sorted({r.get("funding") for r in records if r.get("funding")}),
            "statuses": sorted({r.get("status") for r in records if r.get("status")}),
            "deadline_months": sorted(
                {int(r["deadline_date"][5:7]) for r in records if r.get("deadline_date")}
            ),
        }
        published_options = (snapshot.get("meta") or {}).get("filter_options") or {}
        for name, expected_values in expected_options.items():
            published_values = published_options.get(name)
            parity.check(
                f"filter option '{name}' matches the exported records",
                published_values == expected_values,
                "menu declares a different set of values than the catalogue holds",
            )

        # No status the visibility predicate excludes may be offered. Closed
        # records are absent from the public set by construction, so a "closed"
        # option can never match.
        statuses = published_options.get("statuses") or []
        parity.check(
            "no filter option selects a status the catalogue excludes",
            "closed" not in statuses,
            f"statuses={statuses}",
        )

        return parity
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify a public snapshot against the database it came from.",
    )
    parser.add_argument(
        "--db",
        default="backend/scholarzone.db",
        help="SQLite database to compare against (default: %(default)s)",
    )
    parser.add_argument(
        "--snapshot",
        default="frontend/public/scholarships-snapshot.json",
        help="Snapshot JSON to verify (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    generator = load_generator()
    parity = verify(args.db, args.snapshot, generator)

    print(f"\n{'=' * 70}")
    print(f"{parity.checks - len(parity.findings)}/{parity.checks} checks passed")

    if parity.ok:
        print("RESULT: PARITY OK - the snapshot matches the supplied source database.")
        print("NOTE: this proves consistency with the supplied --db only. It does not")
        print("      establish that this database is the production database.")
        return 0

    print(f"RESULT: PARITY FAILED - {len(parity.findings)} check(s) did not hold:")
    for finding in parity.findings:
        print(f"  - {finding}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
