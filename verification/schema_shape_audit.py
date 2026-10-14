"""Check every stored record against the response schemas it is serialised into.

A row whose value has the wrong JSON shape for a typed response field makes that
record's own detail endpoint fail. The list endpoint does not serialise the same
fields, so the record looks fine everywhere else and 500s only on its own page.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import get_args, get_origin

from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.schemas import ScholarshipDetailResponse, ScholarshipResponse  # noqa: E402

RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}


def wants_list(annotation) -> bool:
    """Whether the annotation requires a JSON array.

    Resolved leniently: `list[str]`, `Optional[list[str]]` and a bare `Any` are
    the three shapes the response schemas actually use, and a record that stores
    a JSON string where an array is declared is the defect being looked for.
    """
    origin = get_origin(annotation)
    if origin is list:
        return True
    args = get_args(annotation)
    if args:
        return any(wants_list(a) for a in args if a is not type(None))
    return False


def main() -> None:
    catalogue = {int(r["id"]) for r in json.loads(
        (HERE / "live_catalogue.json").read_text(encoding="utf-8")
    )["items"]}

    for model in (ScholarshipResponse, ScholarshipDetailResponse):
        listy = [
            name
            for name, field in model.model_fields.items()
            if wants_list(field.annotation)
        ]
        mismatches: list[tuple[int, str, type]] = []
        for sid, row in sorted(RAW.items()):
            for name in listy:
                value = row.get(name)
                if value is None:
                    continue
                if isinstance(value, list):
                    continue
                if isinstance(value, str) and not value.strip():
                    continue
                mismatches.append((sid, name, type(value).__name__))
        print(f"== {model.__name__}: {len(listy)} array-typed fields -> {listy}")
        print(f"   rows with the wrong JSON shape: {len(mismatches)}")
        for sid, name, kind in mismatches:
            where = "public" if sid in catalogue else "not public"
            print(f"     id={sid} ({where}) {name} is {kind}")
        print()


if __name__ == "__main__":
    main()
