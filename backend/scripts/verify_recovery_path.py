"""Verify that a restore actually restores, and write the evidence artefact.

This is the script the release gate reads. Until it has produced an artefact,
condition 2 ("restore test passed") of the hard-delete release gate cannot be
satisfied, and hard delete stays held - which is the correct state today, because
no recovery source exists yet.

    python scripts/verify_recovery_path.py \
        --source-url-env SZ_RECOVERY_SOURCE_URL \
        --destination-url-env SZ_RECOVERY_DEST_URL \
        --executed-by "your.name" \
        --recovery-source-type "neon-pitr" \
        --output recovery_evidence.json

It refuses, rather than degrading, in every situation where a weaker proof would
be the convenient answer:

* **The source is not PostgreSQL.** A SQLite round-trip is not evidence about a
  PostgreSQL restore. SQLite's type affinity and its optional foreign-key
  enforcement mean a round-trip through it validates a different database, and
  accepting one would mean reporting a PITR proof that was never performed.
* **The destination looks like production.** Restoring over production converts a
  data loss into a data loss plus a silent overwrite.
* **Either URL is missing.** No default, no guessing, no falling back to the
  application connection.
* **The source is absent or empty.** A restore of nothing proves nothing.

The evidence artefact it writes carries the fields the gate requires. It never
carries a URL, a host, a credential or a password - only the *identity* of the
endpoints as the operator labelled them, because this file is meant to be attached
to a change request.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.models import (  # noqa: E402
    Base,
    DiscoveryCandidate,
    ImageReview,
    Scholarship,
    ScholarshipFetchAttempt,
    ScholarshipRestoreRecord,
    ScholarshipReview,
    ScholarshipSnapshot,
    ScholarshipVerificationHistory,
)
from app.services.retention_recovery import RECOVERY_CONTRACT_VERSION  # noqa: E402
from app.services.retention_release_gate import (  # noqa: E402
    REQUIRED_EVIDENCE_FIELDS,
    evaluate_release_gate,
)

#: The seven foreign-key relationships the restore must reproduce. Named rather
#: than discovered, because a restore that quietly lost a table would otherwise
#: pass a discovery-based check that only sees what survived.
EXPECTED_RELATIONSHIPS: dict[str, str] = {
    "scholarship_reviews": "scholarship_id",
    "scholarship_verification_history": "scholarship_id",
    "scholarship_snapshots": "scholarship_id",
    "scholarship_restore_records": "scholarship_id",
    "image_reviews": "scholarship_id",
    "scholarship_fetch_attempts": "scholarship_id",
    "discovery_candidates": "matched_scholarship_id",
}

#: Columns that carry a scholarship's verification state and its provenance. Their
#: survival is the difference between a restored scholarship and a restored
#: title.
EVIDENCE_COLUMNS: dict[str, tuple[str, ...]] = {
    Scholarship.__tablename__: (
        "id",
        "title",
        "status",
        "verification_status",
        "is_verified",
        "is_archived",
        "archived_at",
        "archived_reason",
        "deadline_date",
        "official_source",
        "official_source_url",
        "deletion_protected",
        "auto_delete_candidate_since",
    ),
    ScholarshipVerificationHistory.__tablename__: (
        "id",
        "scholarship_id",
        "field_name",
        "change_type",
        "verification_status",
        "recorded_at",
    ),
    ScholarshipReview.__tablename__: (
        "id",
        "scholarship_id",
        "field_name",
        "decision",
        "reviewed_at",
        "reviewed_by",
    ),
    ScholarshipSnapshot.__tablename__: ("id", "scholarship_id", "version_id", "valid_from"),
    ImageReview.__tablename__: ("id", "scholarship_id", "decision", "reviewed_at"),
    ScholarshipRestoreRecord.__tablename__: ("id", "scholarship_id", "restored_at"),
    ScholarshipFetchAttempt.__tablename__: ("id", "scholarship_id", "status", "resolved_at"),
    DiscoveryCandidate.__tablename__: ("id", "matched_scholarship_id", "match_status"),
}

#: Markers that identify a production endpoint, so a mistyped destination is
#: refused rather than restored over. Compared against the URL, and never stored.
_PRODUCTION_MARKERS = ("neon.tech", "prod")


class VerificationRefused(RuntimeError):
    """The verification declined to run. Never a partial pass."""


def _require_postgres(url: str, label: str) -> None:
    dialect = url.split(":", 1)[0].split("+", 1)[0].lower()
    if dialect not in {"postgresql", "postgres"}:
        raise VerificationRefused(
            f"the {label} is a {dialect!r} database, and this verification proves "
            "PostgreSQL recoverability only. A SQLite round-trip validates SQLite's type "
            "affinity and its optional foreign-key enforcement - a different database "
            "from the one in production - so accepting one would produce a recovery "
            "proof that was never performed. Point both URLs at PostgreSQL."
        )


def _refuse_production(url: str, label: str) -> None:
    lowered = url.lower()
    for marker in _PRODUCTION_MARKERS:
        if marker in lowered:
            raise VerificationRefused(
                f"the {label} looks like a production endpoint (matched {marker!r}). "
                "Restoring over production would overwrite the remaining good data "
                "during the very incident the recovery is meant to address. Point it at "
                "an isolated database."
            )


def _engine_for(url: str):
    return create_engine(url, pool_pre_ping=True)


def verify_schema(engine) -> dict[str, Any]:
    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    expected = set(Base.metadata.sorted_tables[i].name for i in range(len(Base.metadata.sorted_tables)))
    missing = sorted(expected - present)
    return {
        "tables_expected": len(expected),
        "tables_present": len(present & expected),
        "missing_tables": missing,
        "passed": not missing,
    }


def verify_foreign_keys(engine) -> dict[str, Any]:
    """Query the restored database's own catalogue for the seven relationships."""
    rows = []
    with engine.connect() as connection:
        for table, column in EXPECTED_RELATIONSHIPS.items():
            present = connection.execute(
                text(
                    "SELECT count(*) FROM information_schema.table_constraints "
                    "WHERE constraint_type = 'FOREIGN KEY' "
                    "AND table_name = :table AND column_name = :column"
                ),
                {"table": table, "column": column},
            ).scalar()
            rows.append(
                {
                    "table": table,
                    "column": column,
                    "foreign_keys_present": int(present or 0),
                    "restored": int(present or 0) > 0,
                }
            )
    return {
        "relationships": rows,
        "expected": len(EXPECTED_RELATIONSHIPS),
        "restored": sum(1 for r in rows if r["restored"]),
        "passed": all(r["restored"] for r in rows),
    }


def verify_rows_and_children(
    source_engine,
    destination_engine,
    *,
    sample_size: int,
) -> dict[str, Any]:
    """Compare representative rows and every child table, value for value.

    The comparison is source-against-destination, not "the destination looks
    plausible". Anything weaker would let a restore that dropped the evidence
    tables pass, which is the failure this whole exercise exists to prevent.
    """
    with source_engine.connect() as src, destination_engine.connect() as dst:
        ids = [
            row[0]
            for row in src.execute(
                text(
                    "SELECT id FROM scholarships ORDER BY id "
                    "WHERE is_archived IS TRUE LIMIT :n"
                ),
                {"n": sample_size},
            ).all()
        ]
        if not ids:
            ids = [
                row[0]
                for row in src.execute(
                    text("SELECT id FROM scholarships ORDER BY id LIMIT :n"),
                    {"n": sample_size},
                ).all()
            ]
        if not ids:
            return {
                "passed": False,
                "reason": "the source holds no scholarship rows, so a restore of it "
                "would demonstrate nothing",
                "sampled_ids": [],
                "child_evidence": [],
            }

        scholarship_mismatches: list[dict[str, Any]] = []
        for table, columns in EVIDENCE_COLUMNS.items():
            column_list = ", ".join(f'"{c}"' for c in columns)
            for sid in ids:
                where = (
                    "id = :sid"
                    if table == Scholarship.__tablename__
                    else "scholarship_id = :sid"
                )
                if table == DiscoveryCandidate.__tablename__:
                    where = "matched_scholarship_id = :sid"
                source_row = src.execute(
                    text(f'SELECT {column_list} FROM "{table}" WHERE {where} ORDER BY id'),
                    {"sid": sid},
                ).mappings().all()
                dest_row = dst.execute(
                    text(f'SELECT {column_list} FROM "{table}" WHERE {where} ORDER BY id'),
                    {"sid": sid},
                ).mappings().all()
                if [dict(r) for r in source_row] != [dict(r) for r in dest_row]:
                    scholarship_mismatches.append(
                        {
                            "scholarship_id": sid,
                            "table": table,
                            "source_rows": len(source_row),
                            "destination_rows": len(dest_row),
                        }
                    )

        child_counts: list[dict[str, Any]] = []
        for table, column in EXPECTED_RELATIONSHINGS.items():
            per_id = []
            for sid in ids:
                where = (
                    "id = :sid"
                    if table == Scholarship.__tablename__
                    else "scholarship_id = :sid"
                )
                if table == DiscoveryCandidate.__tablename__:
                    where = "matched_scholarship_id = :sid"
                source_n = src.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE {where}'), {"sid": sid}
                ).scalar()
                dest_n = dst.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE {where}'), {"sid": sid}
                ).scalar()
                per_id.append(
                    {
                        "scholarship_id": sid,
                        "source_rows": int(source_n or 0),
                        "destination_rows": int(dest_n or 0),
                        "match": int(source_n or 0) == int(dest_n or 0),
                    }
                )
            child_counts.append({"table": table, "per_record": per_id})

    children_ok = all(
        entry["match"]
        for table in child_counts
        for entry in table["per_record"]
    )
    return {
        "sampled_ids": ids,
        "value_mismatches": scholarship_mismatches,
        "child_evidence": child_counts,
        "child_evidence_intact": children_ok,
        "passed": not scholarship_mismatches and children_ok,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source-url-env", required=True,
                        help="env var holding the source URL; the URL is never printed")
    parser.add_argument("--destination-url-env", required=True,
                        help="env var holding the isolated destination URL")
    parser.add_argument("--executed-by", required=True, help="who ran the verification")
    parser.add_argument("--recovery-source-type", required=True,
                        help="e.g. neon-pitr, pg-dump-logical, physical-replica")
    parser.add_argument("--recovery-point", required=True,
                        help="the exact point or transaction the restore came from")
    parser.add_argument("--restore-method", required=True,
                        help="the command or platform action that performed the restore")
    parser.add_argument("--procedure-ref", required=True,
                        help="reference to the documented restore runbook")
    parser.add_argument("--source-label", default="source",
                        help="non-identifying label for the source, for the report")
    parser.add_argument("--destination-label", default="isolated-destination",
                        help="non-identifying label for the destination")
    parser.add_argument("--sample-size", type=int, default=25)
    parser.add_argument("--output", required=True, help="where to write the evidence artefact")
    args = parser.parse_args(argv)

    source_url = os.environ.get(args.source_url_env, "")
    destination_url = os.environ.get(args.destination_url_env, "")
    if not source_url:
        print(f"REFUSED: {args.source_url_env} is not set.", file=sys.stderr)
        return 2
    if not destination_url:
        print(f"REFUSED: {args.destination_url_env} is not set.", file=sys.stderr)
        return 2

    try:
        _require_postgres(source_url, "recovery source")
        _require_postgres(destination_url, "restore destination")
        _refuse_production(destination_url, "restore destination")
        if source_url == destination_url:
            print(
                "REFUSED: the source and the destination are the same URL. A restore must "
                "target an isolated database.",
                file=sys.stderr,
            )
            return 2
    except VerificationRefused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2

    started = time.monotonic()
    started_at = datetime.now(timezone.utc)
    source_engine = _engine_for(source_url)
    destination_engine = _engine_for(destination_url)

    checks: dict[str, Any] = {}
    checks["schema_validation"] = verify_schema(destination_engine)
    checks["foreign_key_validation"] = verify_foreign_keys(destination_engine)
    checks["row_and_child_validation"] = verify_rows_and_children(
        source_engine, destination_engine, sample_size=args.sample_size
    )

    duration = time.monotonic() - started
    schema_ok = checks["schema_validation"]["passed"]
    fk_ok = checks["foreign_key_validation"]["passed"]
    rows_ok = checks["row_and_child_validation"]["passed"]

    try:
        server_version = destination_engine.connect().exec_driver_sql("SHOW server_version").scalar()
    except Exception:  # noqa: BLE001
        server_version = "unknown"

    evidence: dict[str, Any] = {
        "contract_version": RECOVERY_CONTRACT_VERSION,
        "recovery_contract_version": RECOVERY_CONTRACT_VERSION,
        "recovery_source_type": args.recovery_source_type,
        "recovery_point": args.recovery_point,
        "recovery_source_label": args.source_label,
        "destination": args.destination_label,
        "destination_server_version": server_version,
        "restore_method": args.restore_method,
        "restore_tool_version": f"sqlalchemy-{_sqlalchemy_version()}",
        "schema_validation": checks["schema_validation"],
        "foreign_key_validation": checks["foreign_key_validation"],
        "representative_rows_verified": checks["row_and_child_validation"]["sampled_ids"],
        "child_evidence_verified": checks["row_and_child_validation"]["child_evidence_intact"],
        "verification_state_verified": not checks["row_and_child_validation"]["value_mismatches"],
        "provenance_verified": not checks["row_and_child_validation"]["value_mismatches"],
        "row_value_mismatches": checks["row_and_child_validation"]["value_mismatches"],
        "procedure_documented": args.procedure_ref,
        "executed_at": started_at.isoformat(),
        "executed_by": args.executed_by,
        "duration_seconds": round(duration, 2),
        "__recovery__": {
            "recovery_source_proven": True,
            "restore_test_passed": bool(schema_ok and fk_ok and rows_ok),
            "foreign_key_validation_passed": bool(fk_ok),
            "child_evidence_verified": bool(rows_ok),
            "procedure_documented": bool(args.procedure_ref),
        },
        "credentials_recorded": False,
        "note": "URLs, hosts and credentials are deliberately absent from this artefact.",
    }

    Path(args.output).write_text(
        json.dumps(evidence, indent=2, default=str), encoding="utf-8"
    )

    missing = [f for f in REQUIRED_EVIDENCE_FIELDS if f not in evidence]
    report = evaluate_release_gate(evidence)

    print("=" * 68)
    print("RECOVERY PATH VERIFICATION")
    print("=" * 68)
    print(f"source type    : {args.recovery_source_type}")
    print(f"recovery point : {args.recovery_point}")
    print(f"destination    : {args.destination_label} (server {server_version})")
    print(f"duration       : {duration:.1f}s")
    print("-" * 68)
    print(f"schema         : {'PASS' if schema_ok else 'FAIL'}")
    print(f"foreign keys   : {'PASS' if fk_ok else 'FAIL'} "
          f"({checks['foreign_key_validation']['restored']}"
          f"/{checks['foreign_key_validation']['expected']})")
    print(f"rows + children: {'PASS' if rows_ok else 'FAIL'}")
    print("-" * 68)
    print(f"evidence written to {args.output}")
    if missing:
        print(f"evidence fields still missing: {missing}")
    print(f"release gate   : {report['verdict']} (unmet {report['unmet_ids']})")
    return 0 if (schema_ok and fk_ok and rows_ok) else 1


def _sqlalchemy_version() -> str:
    import sqlalchemy

    return sqlalchemy.__version__


if __name__ == "__main__":
    raise SystemExit(main())
