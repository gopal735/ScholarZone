"""Resolve two pre-existing same-programme duplicates that block the add stage.

`_find_existing_scholarship` matches on the URL and its trailing-slash variant,
so two rows that differ only by a trailing slash or by letter case make every
future upsert for that programme raise. Both pairs are the same award, so one
row of each pair is retired through the repository's own mechanism rather than
deleted: the row is quarantined and archived with its successor recorded.
"""
import json
import os

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
PATH = os.path.join(ROOT, "backend", "config", "retired_records.json")

NEW = [
    {
        "id": 358,
        "flag": "DUPLICATE",
        "reason": "Same programme as id=286 (Hungarian Diaspora Scholarship, Tempus Publicus). The two rows "
                  "differ only by a trailing slash on the official URL, which is the same page. Both carry "
                  "status=closed for the current cycle. Retain one record only.",
        "source": "wave-1 official re-verification pass",
        "duplicate_of": 286,
    },
    {
        "id": 528,
        "flag": "DUPLICATE",
        "reason": "Same programme as id=133 (Invest Your Talent in Italy, MAECI/ICE/Uni-Italia). The two rows "
                  "differ only by letter case in the official URL path (/SITOIYT/ vs /SitoIYT/), which is the "
                  "same call page. Retain one record only.",
        "source": "wave-1 official re-verification pass",
        "duplicate_of": 133,
    },
]


def main():
    data = json.loads(open(PATH, encoding="utf-8-sig").read())
    records = data["records"]
    existing = {r["id"] for r in records}
    added = [r for r in NEW if r["id"] not in existing]
    for record in added:
        records.append(record)
    records.sort(key=lambda r: r["id"])
    data["count"] = len(records)
    if not os.path.exists(PATH + ".pre_wave1"):
        os.rename(PATH, PATH + ".pre_wave1")
    json.dump(data, open(PATH, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"retired_records.json: {len(added)} added, {len(records)} total")


if __name__ == "__main__":
    main()