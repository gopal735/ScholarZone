"""Repair every appended record that targets an existing row by id.

The ingestion stage resolves an upsert in this order: official_source_url, then
application_link, then `legacy_titles` compared against `lower(title)`. A record
whose URL the agent corrected and whose renamed title no longer matches the
stored row therefore resolves to nothing and is treated as an INSERT — and an
insert that omits `funding_type` aborts the whole batch.

So for each appended record that carries `_target_id`, this puts the stored row's
lowercase title into `legacy_titles` so the match always resolves, and drops the
nullable fields the row already carries rather than overwriting them with null.
"""
import json
import os
import sqlite3

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
DB = os.path.join(ROOT, "backend", "scholarzone.db")
CONFIG = os.path.join(ROOT, "backend", "config", "new_scholarships.json")

# Ingestion fields the row can keep when the agent could not confirm them.
OPTIONAL = [
    "funding_type", "funding_amount", "funding_currency", "funding_period", "deadline_date",
    "deadline_precision", "deadline", "funding", "program_type", "region", "duration",
    "catalogue_url", "official_updates_url", "image_url", "image_source_url",
    "image_source_type", "image_alt_text", "image_verified_at", "application_period",
]
# The ingestion record names some columns differently from the table.
ROW_COLUMN = {"funding_type": "funding"}


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    data = json.loads(open(CONFIG, encoding="utf-8-sig").read())
    records = data["records"] if isinstance(data, dict) else data

    patched_titles = patched_nulls = 0
    unmatched = []
    kept = []
    for record in records:
        target = record.get("_target_id")
        if not target:
            kept.append(record)
            continue
        row = conn.execute("SELECT * FROM scholarships WHERE id = ?", (int(target),)).fetchone()
        if row is None:
            # The row was archived as a duplicate of another row for the same
            # programme. Re-seeding it here would recreate the duplicate.
            unmatched.append(target)
            continue
        keys = set(row.keys())
        stored = row["title"]
        legacy = list(record.get("legacy_titles") or [])
        for candidate in (stored, stored.lower()):
            if candidate not in legacy:
                legacy.append(candidate)
        if legacy != (record.get("legacy_titles") or []):
            record["legacy_titles"] = legacy
            patched_titles += 1
        for field in OPTIONAL:
            column = ROW_COLUMN.get(field, field)
            if field in record and record[field] is None and column in keys and row[column]:
                record.pop(field)
                patched_nulls += 1
        kept.append(record)
    records = kept

    conn.close()
    if not os.path.exists(CONFIG + ".pre_repair"):
        os.rename(CONFIG, CONFIG + ".pre_repair")
    if isinstance(data, dict):
        data["records"] = records
    else:
        data = {"records": records}
    data["count"] = len(records)
    json.dump(data, open(CONFIG, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"legacy_titles patched: {patched_titles}")
    print(f"null fields dropped  : {patched_nulls}")
    print(f"targets not in the db: {len(unmatched)} {unmatched[:12]}")


if __name__ == "__main__":
    main()