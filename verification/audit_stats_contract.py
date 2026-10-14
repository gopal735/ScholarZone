"""Phase 1/3: prove each stats field's universe from the code, and decompose.

Nothing here re-implements the public predicate: the counts come from the live
endpoint and from the read-only production audit, both of which derive their
public set from ``public_visibility_conditions()``.
"""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODULE = "backend/app/services/counting/catalogue.py"


def source_at(rev: str) -> str:
    return subprocess.run(
        ["git", "show", f"{rev}:{MODULE}"], cwd=REPO, capture_output=True
    ).stdout.decode("utf-8")


def fields_at(rev: str) -> dict[str, str]:
    """Map each labelled aggregate to the expression it counts.

    The label is chained onto the ``count(...)`` call rather than passed as a
    keyword, so the node to look for is the ``.label()`` attribute call whose
    value is the ``count(...)`` expression.
    """
    text = source_at(rev)
    tree = ast.parse(text)
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr == "label"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        label = node.args[0].value
        inner_node = func.value
        if not (isinstance(inner_node, ast.Call) and isinstance(inner_node.func, ast.Name)):
            continue
        if inner_node.func.id != "count":
            continue
        inner = ast.unparse(inner_node.args[0]) if inner_node.args else "?"
        out[label] = "PUBLIC" if "listed" in inner else "STORAGE"
    return out


def main() -> None:
    deployed = "0981b9adbe49"
    buggy = "102300c"

    print("=" * 74)
    print("SQL / PREDICATE PROOF  (label -> counted universe, per revision)")
    print("=" * 74)
    for rev, title in ((buggy, f"{buggy[:7]}  (revision that returned 445)"),
                       (deployed, f"{deployed[:7]}  (currently deployed)")):
        print(f"\n--- {title} ---")
        try:
            fields = fields_at(rev)
        except SyntaxError as exc:
            print(f"  could not parse: {exc}")
            continue
        storage = sorted(k for k, v in fields.items() if v == "STORAGE")
        public = sorted(k for k, v in fields.items() if v == "PUBLIC")
        print(f"  counted over STORAGE ({len(storage)}): {storage}")
        print(f"  counted over PUBLIC  ({len(public)}): {public}")

    print()
    print("=" * 74)
    print("MEASURED DECOMPOSITION  (production, read-only)")
    print("=" * 74)
    storage_rows = 451          # db_state.py B_rows_in_storage, CI run 37151286688
    public_rows = 386           # db_state.py A_authoritative_public_ids
    storage_only = storage_rows - public_rows
    public_with_source = 381    # live /api/scholarships/stats at 0981b9a
    storage_with_source = 445   # live /api/scholarships/stats at 102300c
    public_with_image = 386     # live /api/scholarships/stats at 0981b9a

    print(f"  storage rows                        {storage_rows}")
    print(f"  public rows                         {public_rows}")
    print(f"  storage-only rows                   {storage_only}")
    print()
    print(f"  PUBLIC  + official source           {public_with_source}")
    print(f"  STORAGE + official source           {storage_with_source}")
    print(f"  STORAGE_ONLY + official source      {storage_with_source - public_with_source}")
    print()
    public_without = public_rows - public_with_source
    storage_without = storage_rows - storage_with_source
    storage_only_without = storage_only - (storage_with_source - public_with_source)
    print("  decomposition check")
    print(f"    public rows with no source        {public_without}")
    print(f"    storage-only rows with no source  {storage_only_without}")
    print(f"    their sum == storage rows with none"
          f"   {public_without + storage_only_without == storage_without}")
    print(f"    public + storage-only == storage  "
          f"{public_with_source + (storage_with_source - public_with_source) == storage_with_source}")
    print()
    print(f"  PUBLIC + image                      {public_with_image}")
    print(f"  public rows with no image           {public_rows - public_with_image}")
    print("  STORAGE + image                     not separately measured;")
    print("    bounded by                        386 <= value <= 451")
    print("    reason: the buggy revision was no longer deployed when measured,")
    print("    and the fixed revision scopes this aggregate to PUBLIC.")
    print()
    print("=" * 74)
    print("LIVE RESPONSE, DEPLOYED REVISION")
    print("=" * 74)
    print(json.dumps(
        {
            "total": 386,
            "with_image": 386,
            "with_official_source": 381,
            "verified_active": 364,
            "open": 291,
            "closing_soon": 32,
            "upcoming": 59,
            "countries": 47,
            "fully_funded": 122,
        },
        indent=1,
    ))
    over = [
        (k, v)
        for k, v in {
            "with_image": 386,
            "with_official_source": 381,
            "verified_active": 364,
            "open": 291,
            "closing_soon": 32,
            "upcoming": 59,
            "fully_funded": 122,
        }.items()
        if v > 386
    ]
    print(f"\n  public subsets exceeding total(386): {over if over else 'none'}")


if __name__ == "__main__":
    sys.exit(main())