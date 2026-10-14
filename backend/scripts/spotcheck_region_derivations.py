"""Spot-check the rows whose derived region is most likely to be wrong."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import taxonomy  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB = os.path.join(ROOT, "backend", "scholarzone.db")

SUSPECT_FROM = (
    "Countries with a Gross Domestic Product",
    "International students from any country",
    "International students from diverse priority",
    "International students from all countries",
    "Students from all countries",
    "Global (OECD DAC",
    "Global (applicants from",
    "Global (eligible countries",
    "Africa, Asia, Latin America and the Pacific",
    "Africa, Europe",
    "North America, Europe",
    "Middle East / Europe",
    "Central and Eastern Europe",
    "Europe / Worldwide",
    "Asia and Pacific",
    "All 54 African countries",
    "Partner institutions primarily in Africa",
    "C\u00f4te d'Ivoire (Abidjan)",
    "Host administering organisation country",
)


def main() -> int:
    import sqlite3

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    for r in con.execute(
        "select id,title,country,region,official_source from scholarships order by id"
    ):
        stored = (r["region"] or "").strip()
        if not stored.startswith(SUSPECT_FROM):
            continue
        derived = taxonomy.canonical_region(r["country"], r["region"])
        cc = taxonomy.canonical_country(r["country"])
        print(f"#{r['id']:<5} {(r['title'] or '')[:58]}")
        print(f"      stored_region : {stored[:110]}")
        print(f"      stored_country: {(r['country'] or '')[:110]}")
        print(f"      -> country    : {cc!r}")
        print(f"      -> region     : {derived!r}")
        print()
    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())