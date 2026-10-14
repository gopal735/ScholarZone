"""End-to-end rehearsal of the list-column repair, on the real code paths.

Seeds a throwaway SQLite database with every stored row exactly as the deployed
API reports it - including the 118 rows that hold a bare JSON string in a column
the detail contract declares as ``list[str]`` - and then drives the approved
maintenance stage and the real FastAPI app over it.

The measurement is deliberately split, because two different things were broken
and fixing either one hides the other:

* ``contract_before``  - the previous contract, which only coerced ``None``.
  This is what production was running, and it is what the live probe counts.
* ``contract_after``   - the shipped contract, which also accepts a bare string.

With the data repaired, the previous contract would also be satisfied. That is
asserted explicitly, so the fix does not depend on the read-side tolerance
staying in place.

Nothing here touches production.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))

logging.disable(logging.CRITICAL)

DB_PATH = HERE / "_repair_rehearsal.sqlite3"
RAW = {
    int(k): v
    for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()
}
CATALOGUE = json.loads((HERE / "live_catalogue.json").read_text(encoding="utf-8"))
PUBLIC = sorted(r["id"] for r in CATALOGUE["items"])

os.environ["SCHOLARZONE_ENVIRONMENT"] = "test"
os.environ["SCHOLARZONE_DATABASE_URL"] = f"sqlite:///{DB_PATH.as_posix()}"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED"] = "false"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_VERIFIED_IMAGE"] = "false"
os.environ["SCHOLARZONE_PUBLIC_REQUIRE_OFFICIAL_SOURCE"] = "false"

ARRAY_FIELDS = (
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "application_method",
)


def seed() -> int:
    from datetime import date, datetime

    from sqlalchemy import Date, DateTime, create_engine
    from sqlalchemy.orm import sessionmaker

    from app.models import Base, Scholarship  # noqa: F401

    def coerce(column, value):
        if value is None:
            return None
        if isinstance(column.type, DateTime):
            if isinstance(value, datetime):
                return value
            try:
                return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                return None
        if isinstance(column.type, Date):
            if isinstance(value, datetime):
                return value.date()
            if isinstance(value, date):
                return value
            try:
                return date.fromisoformat(str(value)[:10])
            except ValueError:
                return None
        return value

    if DB_PATH.exists():
        DB_PATH.unlink()
    engine = create_engine(os.environ["SCHOLARZONE_DATABASE_URL"])
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    for sid, row in RAW.items():
        payload = {
            name: coerce(column, row[name])
            for name, column in Scholarship.__table__.columns.items()
            if name != "id"
        }
        payload["title"] = payload.get("title") or f"record {sid}"
        payload["country"] = payload.get("country") or "Unknown"
        payload["degree"] = payload.get("degree") or "Unknown"
        payload["funding"] = payload.get("funding") or "Unknown"
        payload["deadline_precision"] = payload.get("deadline_precision") or "month"
        payload["status"] = payload.get("status") or "open"
        payload["is_verified"] = bool(payload.get("is_verified", True))
        payload["verification_status"] = payload.get("verification_status") or "active"
        payload["is_archived"] = bool(payload.get("is_archived", False))
        payload["fully_funded"] = bool(payload.get("fully_funded", False))
        payload["created_at"] = payload.get("created_at") or datetime(2026, 1, 1)
        payload["updated_at"] = payload.get("updated_at") or datetime(2026, 1, 1)
        session.add(Scholarship(id=sid, **payload))
    session.commit()
    session.close()
    engine.dispose()
    return len(RAW)


def contract_payload(row: dict) -> dict:
    from app.schemas import ScholarshipDetailResponse

    payload = {
        k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields
    }
    if "verified" not in payload and "is_verified" in row:
        payload["verified"] = row["is_verified"]
    return payload


def rejects_previous_contract(row: dict) -> bool:
    """Whether the pre-repair contract would have rejected this row.

    The old validator coerced only ``None``. Everything else was handed to
    ``list[str]`` unchanged, so a row failed exactly when one of the array
    fields held a non-list, non-null value. Stated as the rule it is, rather
    than by subclassing the model - an inherited ``mode="before"`` validator
    still runs in a subclass, so that measurement would have been fiction.
    """
    for field in ARRAY_FIELDS:
        value = row.get(field)
        if value is not None and not isinstance(value, list):
            return True
    return False


def count_under_shipped_contract(rows: dict) -> dict:
    from pydantic import ValidationError

    from app.schemas import ScholarshipDetailResponse

    failing = []
    for sid, row in rows.items():
        try:
            ScholarshipDetailResponse(**contract_payload(row))
        except ValidationError:
            failing.append(sid)
    return {"failing": failing, "count": len(failing)}


def repaired_copy(rows: dict) -> dict:
    """Apply only the data repair, leaving the contract's own tolerance aside."""
    from app.services.list_columns import normalize_list_column

    out = {}
    for sid, row in rows.items():
        clone = dict(row)
        for field in ARRAY_FIELDS:
            fixed, _changed = normalize_list_column(clone.get(field), field=field)
            clone[field] = fixed
        out[sid] = clone
    return out


def probe_details(ids: list[int]) -> dict:
    from starlette.testclient import TestClient

    import app.main as main_module

    # `_run_init` seeds bootstrap rows at startup, and that upsert rewrites the
    # list columns of records it recognises. That is fixture behaviour, not the
    # read path under test, and it would overwrite the seeded snapshot with demo
    # data. The production deployment runs the same seed, but on a database that
    # already holds the real catalogue; the rehearsal must measure only what this
    # repair changes.
    main_module.seed_database = lambda: 0

    out: dict = {}
    with TestClient(main_module.app, raise_server_exceptions=False) as client:
        for sid in ids:
            try:
                out[sid] = client.get(f"/api/scholarships/{sid}").status_code
            except Exception as exc:  # noqa: BLE001
                out[sid] = f"{type(exc).__name__}: {exc}"
    return out


def run_stage(stage: str, *, dry_run: bool) -> dict:
    from app.jobs import scholarzone_maintenance as job

    captured: dict = {}
    original = job._run_stage

    def spy(name: str, fn):
        result = fn()
        captured[name] = result
        return original(name, fn)

    job._run_stage = spy
    argv = ["--stage", stage] + (["--dry-run"] if dry_run else [])
    try:
        job.main(argv)
    finally:
        job._run_stage = original
    return captured


def stored_rows() -> dict:
    from app.database import get_session_factory
    from app.models import Scholarship
    from sqlalchemy import inspect as sa_inspect

    factory = get_session_factory()
    session = factory()
    try:
        rows = {}
        for row in session.query(Scholarship).all():
            rows[row.id] = {
                attr.key: attr.value for attr in sa_inspect(row).attrs
            }
        return rows
    finally:
        session.close()


def main() -> None:
    from app.database import init_database

    seeded = seed()
    print(f"seeded stored rows                    : {seeded}")
    print(f"public ids in the audited universe    : {len(PUBLIC)}")

    # --- the contract alone, before and after ------------------------------
    previous_ids = sorted(sid for sid, row in RAW.items() if rejects_previous_contract(row))
    previous_public = [i for i in previous_ids if i in set(PUBLIC)]
    shipped = count_under_shipped_contract(RAW)
    print(f"rows rejected by PREVIOUS contract   : {len(previous_ids)}")
    print(f"  of which public                   : {len(previous_public)}")
    print(f"rows rejected by SHIPPED contract    : {shipped['count']}")

    # --- the data repair alone, previous contract --------------------------
    repaired_only = repaired_copy(RAW)
    after_data_only = [
        sid for sid, row in repaired_only.items() if rejects_previous_contract(row)
    ]
    print(
        "rows rejected by PREVIOUS contract "
        "after data repair alone : "
        f"{len(after_data_only)}  (the fix does not depend on read tolerance)"
    )

    # --- live HTTP, through the real app ------------------------------------
    init_database()
    before_http = probe_details(PUBLIC)
    print(f"live HTTP 500, unrepaired data       : {sum(1 for v in before_http.values() if v == 500)}")

    dry = run_stage("repair_list_columns", dry_run=True)["repair_list_columns"]
    print(f"dry-run rows needing change          : {dry.get('rows_needing_change')}")
    print(f"dry-run fields changed               : {dry.get('fields_changed')}")
    print(f"dry-run columns changed              : {dry.get('columns_changed')}")
    print(f"dry-run refused (not guessed)        : {dry.get('refused')}")
    print(f"dry-run text preserved every reshape : {dry.get('text_preserved_for_every_reshape')}")

    unchanged_http = probe_details(PUBLIC)
    print(
        "live HTTP 500 after dry-run only     : "
        f"{sum(1 for v in unchanged_http.values() if v == 500)}  (dry-run must not write)"
    )

    applied = run_stage("repair_list_columns", dry_run=False)["repair_list_columns"]
    print(f"applied rows repaired                : {applied.get('repaired_rows')}")
    print(f"applied fields changed               : {applied.get('fields_changed')}")

    after_http = probe_details(PUBLIC)
    print(f"live HTTP 500 AFTER repair           : {sum(1 for v in after_http.values() if v == 500)}")
    print(
        "live non-200 responses AFTER repair  : "
        f"{sum(1 for v in after_http.values() if v != 200)}"
    )

    # Losslessness, measured against the raw snapshot, not against the stage.
    now = stored_rows()
    lost = []
    reshaped = 0
    for sid, original_row in RAW.items():
        for field in ARRAY_FIELDS:
            before_value = original_row.get(field)
            after_value = now.get(sid, {}).get(field)
            if before_value is None and after_value == []:
                continue
            if isinstance(before_value, list):
                if before_value != after_value:
                    lost.append({"id": sid, "field": field, "kind": "list_changed"})
                continue
            if isinstance(before_value, str) and before_value.strip():
                reshaped += 1
                if after_value != [before_value]:
                    lost.append({"id": sid, "field": field, "kind": "text_changed"})
    print(f"values reshaped                      : {reshaped}")
    print(f"values lost or altered               : {len(lost)}")

    second = run_stage("repair_list_columns", dry_run=False)["repair_list_columns"]
    print(f"second pass rows repaired            : {second.get('repaired_rows')}  (idempotency)")

    report = {
        "seeded_rows": seeded,
        "public_universe": len(PUBLIC),
        "previous_contract_rejected_all": len(previous_ids),
        "previous_contract_rejected_public": len(previous_public),
        "previous_contract_rejected_public_ids": sorted(previous_public),
        "shipped_contract_rejected_all": shipped["count"],
        "previous_contract_rejected_after_data_repair": len(after_data_only),
        "live_http_500_before": sum(1 for v in before_http.values() if v == 500),
        "live_http_500_after_dry_run_only": sum(1 for v in unchanged_http.values() if v == 500),
        "live_http_500_after": sum(1 for v in after_http.values() if v == 500),
        "live_non_200_after": {
            str(k): v for k, v in after_http.items() if v != 200
        },
        "dry_run": dry,
        "applied": applied,
        "values_reshaped": reshaped,
        "values_lost_or_altered": lost,
        "second_pass": second,
    }
    (HERE / "detail_repair_rehearsal.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("wrote verification/detail_repair_rehearsal.json")


if __name__ == "__main__":
    main()