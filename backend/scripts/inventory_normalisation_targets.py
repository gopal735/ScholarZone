"""Inventory the exact value sets the repair must normalise."""

from __future__ import annotations

import json
import os
import re
import sqlite3
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "backend", "scholarzone.db")


def main() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    print("=" * 78)
    print("ALL DISTINCT `funding` VALUES (card renders this verbatim)")
    print("=" * 78)
    rows = con.execute(
        "select funding, count(*) n from scholarships group by 1 order by n desc, 1"
    ).fetchall()
    for r in rows:
        print(f"{r['n']:>4}  {r['funding']!r}")
    print(f"\ndistinct funding values: {len(rows)}")

    print()
    print("=" * 78)
    print("ALL DISTINCT `country` VALUES")
    print("=" * 78)
    rows = con.execute(
        "select country, count(*) n from scholarships group by 1 order by n desc, 1"
    ).fetchall()
    for r in rows:
        print(f"{r['n']:>4}  {r['country']!r}")
    print(f"\ndistinct country values: {len(rows)}")

    print()
    print("=" * 78)
    print("ALL DISTINCT `region` VALUES")
    print("=" * 78)
    rows = con.execute(
        "select region, count(*) n from scholarships group by 1 order by n desc, 1"
    ).fetchall()
    for r in rows:
        print(f"{r['n']:>4}  {r['region']!r}")
    print(f"\ndistinct region values: {len(rows)}")

    print()
    print("=" * 78)
    print("BOOLEAN COVERAGE BOOLEANS AVAILABLE IN official_details")
    print("=" * 78)
    tally = {}
    for r in con.execute("select official_details from scholarships"):
        try:
            d = json.loads(r["official_details"]) if r["official_details"] else {}
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        for key in ("tuition_coverage", "living_cost_coverage", "travel_coverage",
                    "fully_funded"):
            v = d.get(key)
            kind = "bool" if isinstance(v, bool) else ("str" if isinstance(v, str) else type(v).__name__)
            tally.setdefault(key, Counter())[kind] += 1
    for key, c in tally.items():
        print(f"  {key}: {dict(c)}")

    print()
    print("=" * 78)
    print("PROSE-LENGTH DISTRIBUTION - where the column stops being a value")
    print("=" * 78)
    for col in ("region", "country", "funding"):
        c = con.execute(
            f"select count(*) n from scholarships where {col} is not null and length({col})>60"
        ).fetchone()["n"]
        c2 = con.execute(
            f"select count(*) n from scholarships where {col} is not null and length({col})>120"
        ).fetchone()["n"]
        print(f"  {col}: >60 chars = {c}, >120 chars = {c2}")

    print()
    print("=" * 78)
    print("ENCODING DAMAGE (mojibake) SAMPLE")
    print("=" * 78)
    bad = 0
    for r in con.execute("select id,title,country,region,description from scholarships"):
        blob = " ".join(str(r[k] or "") for k in ("title", "country", "region", "description"))
        hits = re.findall(r"[ÃÂ�][\x80-\xbf\ufffd]?|â€[\x80-\xbf\ufffd]", blob)
        if hits:
            bad += 1
            if bad <= 12:
                print(f"  #{r['id']:<5} {hits[:4]} :: {(r['title'] or '')[:70]}")
    print(f"  rows with mojibake markers: {bad}")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())