"""Diagnose why tuition_coverage is 0/722 while fully_funded is 722/722."""

from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "backend", "scholarzone.db")


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "select id,title,fully_funded,funding,tuition_coverage,living_cost_coverage,"
        "travel_coverage,official_details,funding_amount from scholarships"
    ).fetchall()

    in_json = Counter()
    col = Counter()
    ff = Counter()
    cross = Counter()
    for r in rows:
        col[r["tuition_coverage"]] += 1
        ff[r["fully_funded"]] += 1
        d = {}
        if r["official_details"]:
            try:
                d = json.loads(r["official_details"])
            except Exception:
                d = {}
        v = d.get("tuition_coverage") if isinstance(d, dict) else None
        in_json[repr(v)] += 1
        cross[(r["fully_funded"], repr(v))] += 1

    print(f"rows: {len(rows)}")
    print("\ncolumn tuition_coverage:")
    for k, v in col.most_common():
        print(f"   {k}: {v}")
    print("\ncolumn fully_funded:")
    for k, v in ff.most_common():
        print(f"   {k}: {v}")
    print("\nvalue inside official_details JSON:")
    for k, v in in_json.most_common():
        print(f"   {k}: {v}")
    print("\ncross fully_funded x official_details.tuition_coverage:")
    for (f, t), n in sorted(cross.items(), key=lambda kv: -kv[1]):
        flag = "  <-- VIOLATION" if f is True and t != "True" else ""
        print(f"   fully_funded={f!s:<6} json_tuition={t:<6} {n}{flag}")

    print("\nfunding label distribution (card renders `funding` verbatim):")
    for r in con.execute(
        "select funding, count(*) n from scholarships group by 1 order by n desc limit 30"
    ):
        print(f"   {r['n']:>4}  {r['funding']}")

    print("\nrows with fully_funded=1, by verification_status:")
    for r in con.execute(
        "select verification_status, is_archived, count(*) n from scholarships"
        " where fully_funded=1 group by 1,2 order by n desc"
    ):
        print(f"   {r['n']:>4}  status={r['verification_status']} archived={r['is_archived']}")

    print("\ndistribution of funding values claiming full funding:")
    for r in con.execute(
        "select funding, count(*) n from scholarships where fully_funded=1"
        " group by 1 order by n desc limit 25"
    ):
        print(f"   {r['n']:>4}  {r['funding']}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())