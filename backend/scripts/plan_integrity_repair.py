"""Dry-run the taxonomy against every value currently in the catalogue.

Writes the proposed change set to backend/reports/integrity_repair_plan.json and
prints it. Never mutates the database: --apply lives in repair_integrity.py.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "backend", "scholarzone.db")
REPORTS = os.path.join(ROOT, "backend", "reports")


def main() -> int:
    import sqlite3

    os.makedirs(REPORTS, exist_ok=True)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute(
        "select id,title,country,region,funding,official_details,verification_status,"
        "is_archived,is_verified from scholarships order by id"
    ).fetchall()

    plan = {
        "country": defaultdict(list),
        "region": defaultdict(list),
        "funding": defaultdict(list),
        "coverage": [],
        "protect": [],
    }
    unresolved_country: Counter = Counter()
    unresolved_region: Counter = Counter()

    for r in rows:
        rid = r["id"]
        title = (r["title"] or "")[:70]

        # ---- country ------------------------------------------------------
        before = r["country"]
        after = taxonomy.canonical_country(before)
        if after != before:
            plan["country"][(before, after)].append({"id": rid, "title": title})
        if after is None:
            unresolved_country[repr(before)] += 1
        elif after != taxonomy.MULTIPLE and after not in taxonomy.COUNTRY_REGION:
            unresolved_region[f"country not in COUNTRY_REGION: {after}"] += 1

        # ---- region -------------------------------------------------------
        rbefore = r["region"]
        rafter = taxonomy.canonical_region(r["country"], rbefore)
        if rafter != rbefore:
            plan["region"][(rbefore, rafter)].append({"id": rid, "title": title})
        if rafter is None:
            unresolved_region[repr(rbefore)] += 1

        # ---- funding label -----------------------------------------------
        fbefore = r["funding"]
        fafter = taxonomy.canonical_funding_label(fbefore)
        if fafter != fbefore:
            plan["funding"][(fbefore, fafter)].append({"id": rid, "title": title})

        # ---- coverage booleans from official_details ----------------------
        details = {}
        if r["official_details"]:
            try:
                loaded = json.loads(r["official_details"])
                if isinstance(loaded, dict):
                    details = loaded
            except (ValueError, TypeError):
                details = {}

        flags = {}
        for field in ("tuition_coverage", "living_cost_coverage", "travel_coverage"):
            flags[field] = taxonomy.coverage_boolean(details.get(field))
        flags["fully_funded"] = taxonomy.coverage_boolean(details.get("fully_funded"))
        if any(v is not None for v in flags.values()):
            plan["coverage"].append({"id": rid, "title": title, **flags})

    con.close()

    def show(section: str, mapping) -> None:
        print()
        print("=" * 78)
        print(section)
        print("=" * 78)
        if not mapping:
            print("  (no changes)")
            return
        for (before, after), items in sorted(mapping.items(),
                                            key=lambda kv: (-len(kv[1]), str(kv[0][0]))):
            print(f"  {len(items):>4} rows: {before!r} -> {after!r}")
        print(f"  total rows affected: {sum(len(v) for v in mapping.values())}")

    show("COUNTRY", plan["country"])
    show("REGION", plan["region"])
    show("FUNDING LABEL", plan["funding"])

    print()
    print("=" * 78)
    print("COVERAGE BOOLEANS AVAILABLE IN official_details")
    print("=" * 78)
    tally: Counter = Counter()
    for item in plan["coverage"]:
        for field in ("tuition_coverage", "living_cost_coverage",
                      "travel_coverage", "fully_funded"):
            tally[f"{field}={item[field]}"] += 1
    for k, v in sorted(tally.items()):
        print(f"  {v:>4}  {k}")

    print()
    print("=" * 78)
    print("UNRESOLVED - these need a human, not a rule")
    print("=" * 78)
    print("  country could not be resolved to a known country:")
    for k, v in unresolved_country.most_common():
        print(f"    {v:>4}  {k}")
    print("  region could not be derived:")
    for k, v in unresolved_region.most_common(30):
        print(f"    {v:>4}  {k[:150]}")

    payload = {
        "note": "Proposed integrity repair. Read-only; nothing here is applied yet.",
        "generated_for_rows": len(rows),
        "country_changes": [{"from": b, "to": a, "rows": v}
                            for (b, a), v in sorted(plan["country"].items(),
                                                    key=lambda kv: (-len(kv[1]), str(kv[0][0])))],
        "region_changes": [{"from": b, "to": a, "rows": v}
                           for (b, a), v in sorted(plan["region"].items(),
                                                   key=lambda kv: (-len(kv[1]), str(kv[0][0])))],
        "funding_changes": [{"from": b, "to": a, "rows": v}
                            for (b, a), v in sorted(plan["funding"].items(),
                                                    key=lambda kv: (-len(kv[1]), str(kv[0][0])))],
        "coverage_backfill": plan["coverage"],
        "unresolved_country": dict(unresolved_country),
        "unresolved_region": dict(unresolved_region),
    }
    out = os.path.join(REPORTS, "integrity_repair_plan.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
    print()
    print(f"plan written: {os.path.relpath(out, ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())