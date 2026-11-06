"""Delete scholarships the frontend lifecycle contract classifies as closed.

Dry-run by default. A live run requires ``--apply`` and the exact confirmation
phrase documented in the production workflow.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from sqlalchemy import MetaData, select, tuple_
from sqlalchemy.engine import Connection

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

CONFIRMATION = "PURGE ALL UI-CLOSED SCHOLARSHIPS + LINKED DATA"


class PurgeSafetyError(RuntimeError):
    """The database structure or target set is not safe to purge."""


def _classify_lifecycle(records: list[dict[str, Any]]) -> dict[int, str]:
    if not records:
        return {}

    classifier = """
import { classifyLifecycle } from './frontend/src/utils/lifecycle.js';
let input = '';
for await (const chunk of process.stdin) input += chunk;
const rows = JSON.parse(input);
process.stdout.write(JSON.stringify(rows.map((row) => ({
  id: row.id,
  status: classifyLifecycle(row).status,
}))));
"""
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", classifier],
        cwd=REPO_ROOT,
        input=json.dumps(records, default=str),
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode:
        raise PurgeSafetyError(
            "Frontend lifecycle classification failed: "
            f"{completed.stderr.strip() or completed.returncode}"
        )
    try:
        classified = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise PurgeSafetyError("Frontend lifecycle classifier returned invalid JSON.") from error
    if not isinstance(classified, list) or len(classified) != len(records):
        raise PurgeSafetyError("Frontend lifecycle classifier returned an incomplete result.")
    return {int(item["id"]): str(item["status"]) for item in classified}


def _row_key(table, row: dict[str, Any]) -> tuple[Any, ...]:
    primary_key = list(table.primary_key.columns)
    if not primary_key:
        raise PurgeSafetyError(f"Cannot safely delete from {table.fullname}: no primary key.")
    return tuple(row[column.name] for column in primary_key)


def _matching_rows(connection: Connection, table, column_names: list[str], values: list[tuple]):
    if not values:
        return []
    columns = [table.c[name] for name in column_names]
    predicate = (
        columns[0].in_([value[0] for value in values])
        if len(columns) == 1
        else tuple_(*columns).in_(values)
    )
    return [dict(row) for row in connection.execute(select(table).where(predicate)).mappings()]


def _collect_affected_rows(connection: Connection, metadata: MetaData, scholarship_ids: list[int]):
    scholarships = metadata.tables.get("scholarships")
    if scholarships is None or "id" not in scholarships.c:
        raise PurgeSafetyError("Expected scholarships table with an id column.")

    closed_ids = set(scholarship_ids)
    initial_rows = _matching_rows(connection, scholarships, ["id"], [(sid,) for sid in scholarship_ids])
    if len(initial_rows) != len(set(scholarship_ids)):
        raise PurgeSafetyError("The locked scholarship set changed; refusing partial deletion.")

    children_by_parent = defaultdict(list)
    for child in metadata.tables.values():
        for constraint in child.foreign_key_constraints:
            elements = list(constraint.elements)
            if not elements:
                continue
            parent_table = elements[0].column.table
            if all(element.column.table is parent_table for element in elements):
                children_by_parent[parent_table].append(
                    (
                        child,
                        [element.parent.name for element in elements],
                        [element.column.name for element in elements],
                    )
                )

    affected: dict[Any, dict[tuple[Any, ...], dict[str, Any]]] = defaultdict(dict)
    dependencies: dict[Any, set[Any]] = defaultdict(set)
    queue = deque()
    for row in initial_rows:
        key = _row_key(scholarships, row)
        affected[scholarships][key] = row
        queue.append((scholarships, key, row))

    while queue:
        parent, _parent_key, parent_row = queue.popleft()
        for child, child_columns, parent_columns in children_by_parent.get(parent, []):
            reference = tuple(parent_row[column] for column in parent_columns)
            if any(value is None for value in reference):
                continue
            child_rows = _matching_rows(
                connection,
                child,
                child_columns,
                [reference],
            )
            for row in child_rows:
                key = _row_key(child, row)
                if child is scholarships:
                    if row["id"] not in closed_ids:
                        raise PurgeSafetyError(
                            "A non-closed scholarship references a closed scholarship; "
                            "refusing to expand the purge set."
                        )
                    continue
                dependencies[parent].add(child)
                if key in affected[child]:
                    continue
                affected[child][key] = row
                queue.append((child, key, row))

    return affected, dependencies


def _delete_affected_rows(connection: Connection, affected, dependencies, *, apply: bool):
    ordered: list[Any] = []
    visiting: set[Any] = set()
    visited: set[Any] = set()

    def visit(table):
        if table in visiting:
            raise PurgeSafetyError(
                f"Cyclic foreign-key dependencies involve {table.fullname}; refusing deletion."
            )
        if table in visited:
            return
        visiting.add(table)
        for child in dependencies.get(table, ()):
            visit(child)
        visiting.remove(table)
        visited.add(table)
        ordered.append(table)

    for table in affected:
        visit(table)

    counts = {}
    for table in ordered:
        rows = affected[table]
        primary_key = list(table.primary_key.columns)
        keys = list(rows)
        counts[table.fullname] = len(keys)
        if not apply or not keys:
            continue
        predicate = (
            primary_key[0].in_([key[0] for key in keys])
            if len(primary_key) == 1
            else tuple_(*primary_key).in_(keys)
        )
        result = connection.execute(table.delete().where(predicate))
        if result.rowcount != len(keys):
            raise PurgeSafetyError(
                f"Delete count changed for {table.fullname}: expected {len(keys)}, "
                f"deleted {result.rowcount}."
            )
    return counts


def purge(connection: Connection, *, apply: bool) -> dict[str, Any]:
    """Classify and remove the exact UI-closed set within one transaction."""
    metadata = MetaData()
    metadata.reflect(bind=connection)
    scholarships = metadata.tables.get("scholarships")
    if scholarships is None:
        raise PurgeSafetyError("Expected scholarships table.")

    rows = [dict(row) for row in connection.execute(select(scholarships).with_for_update()).mappings()]
    classified = _classify_lifecycle(rows)
    closed_ids = sorted(record["id"] for record in rows if classified.get(int(record["id"])) == "closed")

    affected, dependencies = _collect_affected_rows(connection, metadata, closed_ids)
    counts = _delete_affected_rows(connection, affected, dependencies, apply=apply)
    return {
        "mode": "APPLY" if apply else "DRY_RUN",
        "closed_scholarship_count": len(closed_ids),
        "closed_scholarship_ids": closed_ids,
        "rows_by_table": dict(sorted(counts.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Commit the deletion.")
    parser.add_argument(
        "--confirm",
        default="",
        help=f"Required with --apply: {CONFIRMATION!r}",
    )
    args = parser.parse_args()

    if args.apply and args.confirm != CONFIRMATION:
        parser.error(f"--apply requires --confirm {CONFIRMATION!r}")

    os.environ["SCHOLARZONE_ENVIRONMENT"] = "production"
    try:
        from app.database import get_engine

        engine = get_engine()
        with engine.connect() as connection:
            if connection.dialect.name == "postgresql":
                connection = connection.execution_options(isolation_level="SERIALIZABLE")
            transaction = connection.begin()
            try:
                report = purge(connection, apply=args.apply)
                if args.apply:
                    transaction.commit()
                else:
                    transaction.rollback()
            except Exception:
                transaction.rollback()
                raise
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as error:
        print(f"purge failed; transaction rolled back: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
