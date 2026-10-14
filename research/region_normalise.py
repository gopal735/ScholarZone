"""Normalise the `region` column back to a geography.

`region` is a filter facet, and several research agents wrote an eligibility
sentence into it ("Global (applicants from any country outside the United
Kingdom)"). The eligibility fact is still stored — in `official_details` and in
`best_fit` — so what is lost here is a label, not a fact.

Where the stored value starts with a real region the region is kept and the
qualifier dropped; otherwise it is inferred from the host country; otherwise it is
left null rather than guessed.
"""
from __future__ import annotations

import os
import sqlite3

DB = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db"

REGIONS = [
    "Central and Eastern Europe", "North America", "Latin America", "Middle East",
    "South America", "East Asia", "South Asia", "Southeast Asia", "Oceania",
    "Sub-Saharan Africa", "Europe", "Africa", "Asia", "Global", "Worldwide",
    "Multiple", "International",
]
# A country that is its own filter facet in the catalogue's own vocabulary.
COUNTRIES_AS_REGIONS = {"Australia", "Canada", "United States", "New Zealand",
                        "Ireland", "Scotland", "England", "Wales",
                        "European Union", "European Union / Multiple countries"}

COUNTRY_REGION = {
    "united states": "North America", "canada": "North America", "mexico": "Latin America",
    "brazil": "Latin America", "argentina": "Latin America", "chile": "Latin America",
    "colombia": "Latin America", "peru": "Latin America", "uruguay": "Latin America",
    "costa rica": "Latin America", "panama": "Latin America", "ecuador": "Latin America",
    "argentina ": "Latin America", "jamaica": "Latin America", "cuba": "Latin America",
    "united kingdom": "Europe", "ireland": "Europe", "france": "Europe", "germany": "Europe",
    "netherlands": "Europe", "belgium": "Europe", "switzerland": "Europe", "austria": "Europe",
    "spain": "Europe", "portugal": "Europe", "italy": "Europe", "malta": "Europe",
    "sweden": "Europe", "norway": "Europe", "denmark": "Europe", "finland": "Europe",
    "iceland": "Europe", "estonia": "Europe", "latvia": "Europe", "lithuania": "Europe",
    "poland": "Europe", "czech republic": "Europe", "slovakia": "Europe", "hungary": "Europe",
    "slovenia": "Europe", "croatia": "Europe", "romania": "Europe", "bulgaria": "Europe",
    "greece": "Europe", "cyprus": "Europe", "luxembourg": "Europe",
    "european union": "Europe", "china": "Asia", "japan": "Asia", "south korea": "Asia",
    "taiwan": "Asia", "mongolia": "Asia", "india": "Asia", "pakistan": "Asia",
    "bangladesh": "Asia", "sri lanka": "Asia", "nepal": "Asia", "bhutan": "Asia",
    "singapore": "Asia", "malaysia": "Asia", "indonesia": "Asia", "thailand": "Asia",
    "vietnam": "Asia", "philippines": "Asia", "kazakhstan": "Asia", "uzbekistan": "Asia",
    "united arab emirates": "Middle East", "saudi arabia": "Middle East", "qatar": "Middle East",
    "kuwait": "Middle East", "oman": "Middle East", "bahrain": "Middle East", "israel": "Middle East",
    "jordan": "Middle East", "lebanon": "Middle East", "iran": "Middle East", "iraq": "Middle East",
    "egypt": "Africa", "morocco": "Africa", "tunisia": "Africa", "algeria": "Africa",
    "nigeria": "Africa", "ghana": "Africa", "kenya": "Africa", "south africa": "Africa",
    "ethiopia": "Africa", "tanzania": "Africa", "uganda": "Africa", "senegal": "Africa",
    "rwanda": "Africa", "zambia": "Africa", "namibia": "Africa", "botswana": "Africa",
    "australia": "Oceania", "new zealand": "Oceania", "fiji": "Oceania",
    "papua new guinea": "Oceania", "samoa": "Oceania",
}


def normalise(region, country):
    raw = (region or "").strip()
    if not raw:
        return None, "empty"
    low = raw.lower().rstrip(".")
    for name in COUNTRIES_AS_REGIONS:
        if low == name.lower():
            return name, "already canonical"
    for name in REGIONS:
        if low == name.lower():
            return name, "already canonical"
        if low.startswith(name.lower()):
            # "Global (applicants from ...)" is a region plus an eligibility note.
            return name, "trimmed qualifier"
    guessed = COUNTRY_REGION.get((country or "").strip().lower())
    if guessed:
        return guessed, "inferred from country"
    return None, "no defensible region"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    changes = {"trimmed qualifier": 0, "inferred from country": 0, "cleared": 0}
    samples = []
    for row in conn.execute("SELECT id, country, region FROM scholarships").fetchall():
        value, reason = normalise(row["region"], row["country"])
        if reason == "already canonical":
            continue
        if value is None and not row["region"]:
            continue
        conn.execute("UPDATE scholarships SET region = ? WHERE id = ?", (value, row["id"]))
        if value is None:
            changes["cleared"] += 1
        else:
            changes[reason] = changes.get(reason, 0) + 1
        if len(samples) < 8:
            samples.append({"id": row["id"], "was": (row["region"] or "")[:70], "now": value})
    conn.commit()
    conn.close()
    print("region normalised:", changes)
    for s in samples:
        print("  id=%-4s %-72s -> %s" % (s["id"], s["was"], s["now"]))


if __name__ == "__main__":
    main()