"""The exact repair for every record whose own detail endpoint returns HTTP 500.

Root cause: ``ScholarshipDetailResponse`` declares seven fields as arrays of
strings, but a stored row holds a bare JSON string for one or more of them. The
list endpoint declares no array fields, so the record renders correctly as a card
and fails only on its own page.

The repair is mechanical and reversible: wrap the string in a one-element array,
preserving its text exactly. Nothing is rewritten, split or reinterpreted - the
value is a string, and a list of one string is the shape the contract asks for.
This file is the input to an owner-approved write, not the write itself.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from pydantic import ValidationError  # noqa: E402

from app.schemas import ScholarshipDetailResponse  # noqa: E402

RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}
CATALOGUE = {
    int(r["id"]): r
    for r in json.loads((HERE / "live_catalogue.json").read_text(encoding="utf-8"))["items"]
}
PROBE = json.loads((HERE / "detail_probe.json").read_text(encoding="utf-8"))

ARRAY_FIELDS = [
    "eligibility",
    "benefits",
    "coverage",
    "requirements",
    "documents",
    "required_documents",
    "application_method",
]


def offending_fields(row: dict) -> list[str]:
    out = []
    for name in ARRAY_FIELDS:
        value = row.get(name)
        if value is None or isinstance(value, list):
            continue
        if isinstance(value, str) and not value.strip():
            continue
        out.append(name)
    return out


#: The stored column is `is_verified`; the API contract field is `verified`. The
#: router maps between them, so the audit has to as well before it can ask the
#: contract whether a row is valid.
COLUMN_TO_FIELD = {"verified": "is_verified"}


def contract_payload(row: dict) -> dict:
    payload = {k: v for k, v in row.items() if k in ScholarshipDetailResponse.model_fields}
    for field, column in COLUMN_TO_FIELD.items():
        if field not in payload and column in row:
            payload[field] = row[column]
    return payload


def validates(row: dict, fields: dict[str, list[str] | None]) -> tuple[bool, str]:
    payload = contract_payload(row)
    payload.update(fields)
    try:
        ScholarshipDetailResponse(**payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        return False, f"{'.'.join(str(p) for p in first['loc'])}: {first['type']}"
    return True, ""


def main() -> None:
    repairs: list[dict] = []
    unexplained: list[dict] = []
    for sid in sorted(CATALOGUE):
        row = RAW.get(sid)
        if row is None:
            continue
        fields = offending_fields(row)
        status = PROBE.get(str(sid))
        if not fields:
            if status != 200:
                unexplained.append({"id": sid, "http_status": status, "note": "no array field is mistyped"})
            continue
        fixed = {name: [row[name]] for name in fields}
        ok, why = validates(row, fixed)
        if not ok:
            unexplained.append({"id": sid, "http_status": status, "note": why})
            continue
        repairs.append(
            {
                "id": sid,
                "name": CATALOGUE[sid].get("name") or CATALOGUE[sid].get("title"),
                "http_status": status,
                "fields": {
                    name: {"stored": row[name], "repaired": [row[name]]} for name in fields
                },
            }
        )

    report = {
        "generated_at": "2026-10-03",
        "public_total": len(CATALOGUE),
        "detail_500_count": sum(1 for s in PROBE.values() if s == 500),
        "repaired_records": len(repairs),
        "repair_rule": (
            "A bare JSON string in an array-typed detail field becomes a one-element "
            "array containing that string. The text is preserved byte for byte. No value "
            "is split, reordered, truncated or invented."
        ),
        "records": repairs,
        "unexplained": unexplained,
    }
    (HERE / "detail_shape_repairs.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("public total           :", len(CATALOGUE))
    print("detail endpoints 500   :", report["detail_500_count"])
    print("records with an exact repair:", len(repairs))
    print("unexplained            :", len(unexplained))
    for row in unexplained:
        print("   ", row)
    from collections import Counter

    print("fields touched:", dict(Counter(f for r in repairs for f in r["fields"])))


if __name__ == "__main__":
    main()
