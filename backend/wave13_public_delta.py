"""Public-visibility delta, explained per row.

Compares the publicly-listed set immediately before the hardening pass against
the set now, using `public_visibility_conditions()` for both so the two numbers
come from the same authority rather than from a re-implementation.

For every row that leaves the directory, each clause of the predicate is
evaluated on both sides and the one that flipped is named. A row can only leave
the set by satisfying the negated predicate on one side and not the other, so
the clauses partition the losses and the partition must sum to the total. That
sum is asserted rather than reported.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.repositories.scholarships import public_visibility_conditions  # noqa: E402

OUT = Path.home() / "AppData" / "Local" / "Temp" / "kilo" / "wave13"
BEFORE = BACKEND / "scholarzone.pre_wave13_hardening_20261004_171847.db"
AFTER = BACKEND / "scholarzone.db"

#: Human-readable name for each clause of the public predicate, in the order the
#: function builds them, plus the settings flags that switch them on.
CLAUSES = [
    ("not quarantined", "verification_status != 'quarantined'", True),
    ("not archived", "is_archived is False", True),
    ("is_verified", "is_verified is True", "public_require_verified"),
    ("has image_url", "image_url is not null", "public_require_verified_image"),
    ("image_verified_at", "image_verified_at is not null", "public_require_verified_image"),
    ("not wikimedia", "image_source_type != 'wikimedia' or is null",
     "public_require_verified_image"),
]


def evaluate(row: sqlite3.Row, enabled_flags: dict) -> dict:
    """Per-clause satisfaction, mirroring public_visibility_conditions() exactly."""
    verified_required = enabled_flags["public_require_verified"]
    image_required = enabled_flags["public_require_verified_image"]
    third_party_allowed = enabled_flags["public_allow_third_party_image"]

    out = {}
    out["not quarantined"] = row["verification_status"] != "quarantined"
    out["not archived"] = not bool(row["is_archived"])
    out["is_verified"] = (bool(row["is_verified"]) if verified_required else True)
    if image_required:
        out["has image_url"] = row["image_url"] is not None
        out["image_verified_at"] = row["image_verified_at"] is not None
        out["not wikimedia"] = (
            True if third_party_allowed
            else (row["image_source_type"] != "wikimedia"
                  or row["image_source_type"] is None)
        )
    else:
        out["has image_url"] = True
        out["image_verified_at"] = True
        out["not wikimedia"] = True
    return out


def listed(rows: dict, flags: dict) -> set:
    ok = set()
    for rid, row in rows.items():
        if all(evaluate(row, flags).values()):
            ok.add(rid)
    return ok


def load(path: Path) -> dict:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {r["id"]: r for r in con.execute("select * from scholarships")}
    con.close()
    return rows


def main() -> dict:
    settings = get_settings()
    flags = {
        "public_require_verified": settings.public_require_verified,
        "public_require_verified_image": settings.public_require_verified_image,
        "public_allow_third_party_image": settings.public_allow_third_party_image,
        "environment": settings.environment,
    }

    before_rows = load(BEFORE)
    after_rows = load(AFTER)
    before = listed(before_rows, flags)
    after = listed(after_rows, flags)

    lost = sorted(before - after)
    gained = sorted(after - before)

    detail = []
    reasons = {}
    for rid in lost:
        b = evaluate(before_rows[rid], flags)
        a = evaluate(after_rows.get(rid) or before_rows[rid], flags)
        flipped = [name for name, _, _ in CLAUSES
                   if name in b and name in a and b[name] and not a[name]]
        reasons[tuple(flipped)] = reasons.get(tuple(flipped), 0) + 1
        detail.append({
            "id": rid,
            "title": (after_rows.get(rid) or before_rows[rid])["title"],
            "clauses_that_flipped": flipped,
            "primary_reason": flipped[0] if flipped else "unknown",
            "before": {k: before_rows[rid][k] for k in (
                "verification_status", "is_archived", "is_verified",
                "image_url", "image_kind", "image_verified_at",
                "image_source_type", "image_evaluation_status")},
            "after": {k: (after_rows.get(rid) or before_rows[rid])[k] for k in (
                "verification_status", "is_archived", "is_verified",
                "image_url", "image_kind", "image_verified_at",
                "image_source_type", "image_evaluation_status")},
        })

    # Rows that became newly listed, which a count-only review would miss.
    gained_detail = []
    for rid in gained:
        b = evaluate(before_rows.get(rid) or after_rows[rid], flags)
        a = evaluate(after_rows[rid], flags)
        flipped = [name for name, _, _ in CLAUSES
                   if name in b and name in a and not b[name] and a[name]]
        gained_detail.append({
            "id": rid,
            "title": after_rows[rid]["title"],
            "clauses_that_flipped": flipped,
            "verification_status": after_rows[rid]["verification_status"],
            "is_archived": bool(after_rows[rid]["is_archived"]),
            "image_url": after_rows[rid]["image_url"],
        })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "flags": flags,
        "before_file": BEFORE.name,
        "before_public": len(before),
        "after_file": AFTER.name,
        "after_public": len(after),
        "delta": len(after) - len(before),
        "lost_count": len(lost),
        "gained_count": len(gained),
        "reason_partition": {
            " + ".join(k) if k else "(no clause flipped)": v
            for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])
        },
        "lost": detail,
        "gained": gained_detail,
        "rows_only_in_after": sorted(set(after_rows) - set(before_rows)),
        "rows_only_in_before": sorted(set(before_rows) - set(after_rows)),
    }

    # The partition must account for every lost row, or the explanation is
    # incomplete and the whole count is not yet trustworthy.
    unexplained = [d["id"] for d in detail if d["primary_reason"] == "unknown"]
    report["rows_with_no_clause_flip"] = unexplained

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "public_delta.json").write_text(
        json.dumps(report, indent=1, default=str), encoding="utf-8")

    print(f"flags: verified={flags['public_require_verified']} "
          f"image={flags['public_require_verified_image']} "
          f"third_party={flags['public_allow_third_party_image']} "
          f"env={flags['environment']}")
    print(f"public before {report['before_public']} -> after {report['after_public']} "
          f"(delta {report['delta']:+d})")
    print(f"lost {len(lost)}   gained {len(gained)}   "
          f"unexplained {len(unexplained)}")
    print("\nreason partition:")
    for k, v in report["reason_partition"].items():
        print(f"  {v:>4}  {k}")
    if unexplained:
        print(f"\nUNEXPLAINED: {unexplained}")
    return report


if __name__ == "__main__":
    main()

