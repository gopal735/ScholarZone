#!/usr/bin/env python3
"""Apply reviewed research enrichment to a local scholarship database.

The eight active catalogue records that had no citation-backed official
details were researched against the awarding body's own pages on
2026-10-11. This script writes that research into the local SQLite database
so the published snapshot can carry it. It exists because the enrichment
had no other reviewed path: the corpus apply pipeline only fills records
whose corpus ids already exist, and two records also need a deadline-display
correction that no pipeline applies.

Usage:
    python apply_publish_enrichment.py --db backend/scholarzone.db \
        --enrichment backend/research_output/publish/uncited_rows_research_2026-10-11.json

Safety properties, in order of how much they matter:

* It writes exclusively to the file named by --db. There is no other output
  path, no default, and no environment-based production branch: a database
  this script cannot open read-write is a hard error, and it refuses to run
  against a database whose path is not a local file.
* Every write is per-field and current-value-aware: a field is only changed
  when the new value differs, and the previous value is printed. Re-running
  the same enrichment performs no writes.
* A record id absent from the database is a hard error: the enrichment is
  keyed by exact DB id, so a missing row means the mapping is wrong, which
  is exactly the case that must never be silently skipped.
* Blocks (96 ENS Lyon, 350 Bioceb) are never touched, and the file documents
  why.

This script applies a *reviewed* data change. Re-read the cited official
pages before re-running it for a later cycle.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# The record columns this script is allowed to change, and where each comes
# from in the enrichment file. Anything not listed here is a hard error:
# a research enrichment must not be able to reach the lifecycle, archive or
# verification-workflow columns by accident.
FIELD_SOURCES = {
    "official_details": "official",
    "programme_verification": "verification",
    "deadline_display": None,  # top-level in the enrichment record
    # The structured funding triple and the coverage flag live on the row
    # itself, and the researched values come from the official block beside
    # the blob. They are merged here rather than left to each caller because
    # a research record whose blob says "475 EUR" while the row says null is
    # a contradiction the frontend would then have to resolve silently.
    "funding_amount": ("official", "funding_amount"),
    "funding_currency": ("official", "funding_currency"),
    "funding_period": ("official", "funding_period"),
    "tuition_coverage": ("official", "tuition_coverage"),
}

# Columns an enrichment record may deliberately blank with `null_fields`,
# and only with a reason recorded next to it. A null write is how the
# research withdraws a claim the official page turns out not to support -
# which is the opposite of inventing a value, and needs the same review.
NULLABLE_COLUMNS = frozenset({"funding_amount", "funding_currency", "funding_period", "tuition_coverage"})

# Columns whose meaning is lifecycle state. This script refuses to write
# them even if the enrichment file names them, because a publication script
# changing a record's lifecycle status is a decision for the verification
# workflow, not for a research merge.
REFUSED_COLUMNS = {
    "status",
    "is_archived",
    "archived_at",
    "archived_reason",
    "verification_status",
    "verification_notes",
    "verified_by",
    "next_verification_due",
    "is_verified",
    "deletion_protected",
    "auto_delete_candidate_since",
    "image_evaluation_status",
    "image_evaluated_at",
    "created_at",
    "updated_at",
}


def _json_or_none(value: Any) -> str | None:
    """Serialise a blob column. An empty object is stored as NULL."""
    if value in (None, {}, "", []):
        return None
    return json.dumps(value, ensure_ascii=False)


def apply_enrichment(db_path: str, enrichment_path: str, *, dry_run: bool = False) -> int:
    source = Path(enrichment_path)
    if not source.is_file():
        raise SystemExit(f"Enrichment file not found: {enrichment_path}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    records = payload.get("records")
    if not isinstance(records, list) or not records:
        raise SystemExit(f"{enrichment_path} holds no records to apply.")

    database = Path(db_path)
    if not database.is_file():
        raise SystemExit(
            f"Database not found: {db_path}\n"
            "This script applies to a LOCAL database only. Pass the path "
            "explicitly; it will never be inferred from the environment."
        )

    connection = sqlite3.connect(str(database))
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scholarships'")
        if cursor.fetchone() is None:
            raise SystemExit(f"No 'scholarships' table in {db_path}; nothing to apply.")

        columns = {row[1] for row in cursor.execute("PRAGMA table_info(scholarships)")}
        for column in ("official_details", "programme_verification", "deadline_display"):
            if column not in columns:
                raise SystemExit(f"{db_path} is missing the {column} column the enrichment writes.")

        applied = 0
        for record in records:
            rid = record.get("id")
            if rid is None:
                raise SystemExit("An enrichment record has no id; refusing to guess one.")

            # A lifecycle column named at the top level is refused before any
            # lookup: this script applies a research merge, and a research
            # record that tries to change a record's lifecycle state has a bug
            # in it that must fail loudly rather than be silently ignored.
            attempted = sorted(REFUSED_COLUMNS & set(record))
            if attempted:
                raise SystemExit(
                    f"Enrichment id {rid} names lifecycle column(s) {attempted}; "
                    "refusing to apply. Lifecycle changes belong to the "
                    "verification workflow, not to a research merge."
                )

            # A deliberate withdrawal, with its reason. `null_fields` is how
            # the research retracts a claim the official page does not
            # support; a null write without a reason is refused for the same
            # reason a merge without evidence would be.
            withdrawn = record.get("null_fields") or []
            if not isinstance(withdrawn, list):
                raise SystemExit(f"Enrichment id {rid}: null_fields must be a list.")
            for column in withdrawn:
                if column not in NULLABLE_COLUMNS:
                    raise SystemExit(
                        f"Enrichment id {rid} may not blank {column!r}; only the "
                        f"researched funding fields are withdrawable ({sorted(NULLABLE_COLUMNS)})."
                    )
            if withdrawn and not record.get("null_reason"):
                raise SystemExit(
                    f"Enrichment id {rid} withdraws {withdrawn} without a null_reason."
                )

            row = cursor.execute(
                "SELECT id, title FROM scholarships WHERE id = ?", (rid,)
            ).fetchone()
            if row is None:
                raise SystemExit(
                    f"Enrichment id {rid} is not a row in {db_path}. The enrichment is "
                    "keyed by exact DB id; a missing row means the mapping is wrong "
                    "and must not be silently skipped."
                )

            updates: dict[str, Any] = {}
            for column, source in FIELD_SOURCES.items():
                if column in REFUSED_COLUMNS:
                    raise SystemExit(f"Enrichment refuses to write lifecycle column {column!r}.")
                if source is None:
                    # A top-level scalar on the enrichment record itself.
                    if column not in record or record[column] in (None, ""):
                        continue
                    updates[column] = record[column]
                    continue
                if isinstance(source, str):
                    # A blob column, written verbatim from the record's own key.
                    if column in record:
                        value = record[column]
                    elif source in record:
                        value = record[source]
                    else:
                        continue
                    if column in ("official_details", "programme_verification"):
                        value = _json_or_none(value)
                else:
                    # A scalar column, read from the named sub-object and
                    # key, e.g. ("official", "funding_amount"). A null in the
                    # research is the confirmed absence of a figure, so it is
                    # skipped rather than written over a present value: this
                    # merge never blanks a field it did not research.
                    block_name, key = source
                    block = record.get(block_name)
                    if not isinstance(block, dict) or block.get(key) is None:
                        continue
                    value = block[key]
                    if key == "funding_amount":
                        try:
                            value = int(str(value).replace(",", ""))
                        except ValueError:
                            raise SystemExit(
                                f"id {rid}: {key} {value!r} is not a currency amount."
                            )
                if value:
                    updates[column] = value

            for column in withdrawn:
                # Only a present value is withdrawn; a null stays a null.
                present = cursor.execute(
                    f"SELECT {column} FROM scholarships WHERE id = ?", (rid,)
                ).fetchone()[column]
                if present not in (None, "", "null"):
                    updates[column] = None

            for column in updates:
                if column in REFUSED_COLUMNS:
                    raise SystemExit(f"Enrichment refuses to write lifecycle column {column!r}.")

            if not updates:
                print(f"  id {rid}: nothing to apply")
                continue

            existing = cursor.execute(
                f"SELECT {', '.join(updates)} FROM scholarships WHERE id = ?", (rid,)
            ).fetchone()
            changed = {
                column: (existing[column], value)
                for column, value in updates.items()
                if existing[column] != value
            }
            if not changed:
                print(f"  id {rid}: already current ({', '.join(sorted(updates))})")
                continue

            for column, (before, after) in sorted(changed.items()):
                before_text = "NULL" if before is None else str(before)
                after_text = "NULL" if after is None else str(after)
                print(f"  id {rid} {column}:")
                print(f"      was: {before_text[:220]}")
                print(f"      now: {after_text[:220]}")
            if not dry_run:
                assignments = ", ".join(f"{column} = ?" for column in sorted(changed))
                cursor.execute(
                    f"UPDATE scholarships SET {assignments} WHERE id = ?",
                    (*[changed[column][1] for column in sorted(changed)], rid),
                )
                applied += len(changed)

        if not dry_run:
            connection.commit()
            stamp = datetime.now().isoformat(timespec="seconds")
            print(f"Applied {applied} field write(s) from {enrichment_path} to {db_path} at {stamp}.")
        return 0
    finally:
        connection.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--db", required=True, help="local SQLite database to write to")
    parser.add_argument("--enrichment", required=True, help="reviewed enrichment JSON to apply")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the writes without performing them",
    )
    args = parser.parse_args(argv)
    return apply_enrichment(args.db, args.enrichment, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
