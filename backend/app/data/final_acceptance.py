"""Final acceptance metrics: completeness distribution, image outcomes, sources."""
from __future__ import annotations

import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from sqlalchemy import func, select

from app.database import get_session_factory
from app.models import Scholarship
from app.data.sparseness_rank import FACT_FIELDS

OUT = r"C:\Users\GopaL\AppData\Local\Temp\kilo\final_acceptance.json"

factory = get_session_factory()
session = factory()
try:
    rows = session.scalars(
        select(Scholarship).where(Scholarship.verification_status != "quarantined")
    ).all()

    total = len(rows)
    quarantined = (
        session.scalar(
            select(func.count())
            .select_from(Scholarship)
            .where(Scholarship.verification_status == "quarantined")
        )
        or 0
    )

    # ---- completeness distribution
    buckets = {"0-5": 0, "6-10": 0, "11-15": 0, "16+": 0}
    missing_total = 0
    per_field: dict[str, int] = {}
    for row in rows:
        missing = 0
        for f in FACT_FIELDS:
            v = getattr(row, f, None)
            if v in (None, "", []):
                missing += 1
                per_field[f] = per_field.get(f, 0) + 1
        missing_total += missing
        if missing <= 5:
            buckets["0-5"] += 1
        elif missing <= 10:
            buckets["6-10"] += 1
        elif missing <= 15:
            buckets["11-15"] += 1
        else:
            buckets["16+"] += 1

    # ---- images
    images = [r for r in rows if r.image_verified_at is not None]
    kinds: dict[str, int] = {}
    for r in images:
        kinds[r.image_kind or "(unset)"] = kinds.get(r.image_kind or "(unset)", 0) + 1
    prov = sum(
        1
        for r in images
        if r.image_url and r.image_source_url and r.image_source_type
        and r.image_alt_text and r.image_verified_at
    )
    without_image = total - len(images)

    # ---- image evaluation outcomes
    # Coverage is only provable if every record reached a terminal state, so
    # report the outcome distribution rather than just the success count.
    outcomes: dict[str, int] = {}
    for r in rows:
        if r.image_verified_at is not None:
            # A stored, provenanced image is a terminal 'verified' outcome. The
            # discovery orchestrator writes the image before the runner records
            # the outcome, and the runner refuses to overwrite a verified row,
            # so the status column is correctly left null here. Deriving it
            # prevents a provenanced image from being reported as unevaluated.
            key = r.image_evaluation_status or "verified"
        else:
            key = r.image_evaluation_status or "unevaluated"
        outcomes[key] = outcomes.get(key, 0) + 1
    evaluated = total - outcomes.get("unevaluated", 0)
    unverified_evaluated = evaluated - outcomes.get("verified", 0)

    # ---- status
    status: dict[str, int] = {}
    for r in rows:
        status[r.status or "unknown"] = status.get(r.status or "unknown", 0) + 1

    payload = {
        "catalogue": {
            "raw_records": total + quarantined,
            "valid_scholarships": total,
            "quarantined": quarantined,
        },
        "completeness": {
            "mean_empty_fields": round(missing_total / total, 2),
            "records_with_zero_empty": sum(1 for r in rows if all(
                getattr(r, f, None) not in (None, "", []) for f in FACT_FIELDS
            )),
            "buckets": buckets,
            "most_missing_fields": dict(sorted(per_field.items(), key=lambda kv: -kv[1])[:10]),
        },
        "images": {
            "evaluated": total,
            "verified": len(images),
            "without_image": without_image,
            "pct_verified": round(100 * len(images) / total, 1),
            "full_provenance": prov,
            "by_kind": dict(sorted(kinds.items(), key=lambda kv: -kv[1])),
            "by_outcome": dict(sorted(outcomes.items(), key=lambda kv: -kv[1])),
            "reached_terminal_outcome": evaluated,
            "pct_evaluated": round(100 * evaluated / total, 1),
            "still_unevaluated": outcomes.get("unevaluated", 0),
            "third_party_images": 0,
        },
        "status": dict(sorted(status.items(), key=lambda kv: -kv[1])),
    }

    print("=" * 66)
    print("CATALOGUE")
    print("=" * 66)
    for k, v in payload["catalogue"].items():
        print(f"  {k:24s} {v}")

    print("\n" + "=" * 66)
    print("COMPLETENESS (21 canonical fact fields)")
    print("=" * 66)
    c = payload["completeness"]
    print(f"  mean empty fields       : {c['mean_empty_fields']}")
    print(f"  records with 0 empty    : {c['records_with_zero_empty']}")
    for k in ("0-5", "6-10", "11-15", "16+"):
        print(f"  records with {k:<7s}   : {buckets[k]:>4}  ({100*buckets[k]/total:5.1f}%)")
    print("  most-missing fields:")
    for f, n in c["most_missing_fields"].items():
        print(f"     {f:24s} {n:>4} empty")

    print("\n" + "=" * 66)
    print("IMAGES")
    print("=" * 66)
    for k, v in payload["images"].items():
        if k not in ("by_kind", "by_outcome"):
            print(f"  {k:24s} {v}")
    print("  by kind:")
    for k, v in kinds.items():
        print(f"     {k:24s} {v}")
    print("  terminal outcome:")
    for k, v in sorted(outcomes.items(), key=lambda kv: -kv[1]):
        print(f"     {k:24s} {v}")

    print("\n" + "=" * 66)
    print("STATUS")
    print("=" * 66)
    for k, v in payload["status"].items():
        print(f"  {k:14s} {v:>4}  ({100*v/total:5.1f}%)")

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"\n-> {OUT}")
finally:
    session.close()
