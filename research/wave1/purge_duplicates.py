"""Archive and remove two rows that duplicate another row for the same programme.

The `official_source_url` column is UNIQUE, so two rows for one programme cannot
both exist: the ingestion stage refuses to seed while the pair is present and a
plain insert fails on the constraint. Retiring is not enough, because a
quarantined row keeps the URL its successor inherited.

This follows the repository's own deletion pattern: the full row payload is
appended to config/purged_records_archive.json first, then the row is removed.
Nothing is lost; the archive keeps the record and the reason.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
DB = os.path.join(ROOT, "backend", "scholarzone.db")
ARCHIVE = os.path.join(ROOT, "backend", "config", "purged_records_archive.json")

# (id, keep_id, reason)
TARGETS = [
    (358, 286, "DUPLICATE of id=286 (Hungarian Diaspora Scholarship, Tempus Publicus): the two rows "
               "differ only by a trailing slash on the official URL, which is the same page. "
               "official_source_url is UNIQUE, so the pair blocked every future upsert for this "
               "programme."),
    (528, 133, "DUPLICATE of id=133 (Invest Your Talent in Italy, MAECI/ICE/Uni-Italia): the two rows "
               "differ only by letter case in the official URL path (/SITOIYT/ vs /SitoIYT/), which is "
               "the same call page. official_source_url is UNIQUE, so the pair blocked every future "
               "upsert for this programme."),
]


def main():
    archive = json.loads(open(ARCHIVE, encoding="utf-8-sig").read())
    records = archive["records"]
    known = {r["id"] for r in records}

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    added = 0
    for target_id, keep_id, reason in TARGETS:
        row = conn.execute("SELECT * FROM scholarships WHERE id = ?", (target_id,)).fetchone()
        if row is None:
            print(f"id={target_id}: already absent")
            continue
        if target_id not in known:
            payload = {k: row[k] for k in row.keys()}
            records.append({
                "id": target_id,
                "title": row["title"],
                "country": row["country"],
                "status": row["status"],
                "is_archived": True,
                "deadline_date": row["deadline_date"],
                "reasons": [reason],
                "official_source_url": row["official_source_url"],
                "duplicate_of": keep_id,
                "payload": payload,
            })
            added += 1
        conn.execute("DELETE FROM scholarships WHERE id = ?", (target_id,))
        print(f"id={target_id}: archived and removed (kept id={keep_id})")
    conn.commit()
    conn.close()

    archive["purged_at"] = datetime.now(timezone.utc).isoformat()
    archive["count"] = len(records)
    if not os.path.exists(ARCHIVE + ".pre_wave1"):
        os.rename(ARCHIVE, ARCHIVE + ".pre_wave1")
    json.dump(archive, open(ARCHIVE, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"purged_records_archive.json: {added} added, {len(records)} total")


if __name__ == "__main__":
    main()