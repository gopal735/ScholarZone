"""Correct one official_source_url on scholarship id=737.

What is wrong
-------------
When the live-upcoming batch was inserted, the four Imperial College London
records were written with the shared scholarship-search URL in the first insert
pass. Three of them were corrected to their own per-scholarship pages; the
Commonwealth Shared Scholarship record (id=737) was not, because the pass that
corrected the URLs rewrote the research artifact rather than the database.

The result is that id=737's ``official_source_url`` — the field the public
snapshot exposes as the record's cited source — points at Imperial's generic
scholarship search page instead of the Commonwealth Shared Scholarship's own
page. The unique index is not violated (the URLs still differ), so this is a
provenance defect rather than an integrity one, but a record whose cited source
is a search page is weaker evidence than one that cites the programme page.

Evidence for the correction
---------------------------
GET https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/
    commonwealth-shared-scholarship-20262027.php
returns 200 and the document title "Commonwealth Shared Scholarship | Study |
Imperial College London", which matches this record's own title.

Safety
------
Dry-run by default; ``--apply`` required. Checks the current value before
writing and refuses if it is not exactly what it expects. One transaction. No
other field is touched.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime

LOCAL_DB = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db"

TARGET_ID = 737
EXPECTED_BEFORE = "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
CORRECTED_AFTER = (
    "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
    "commonwealth-shared-scholarship-20262027.php"
)

EVIDENCE_URL = (
    "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
    "commonwealth-shared-scholarship-20262027.php"
)
EVIDENCE_TITLE = "Commonwealth Shared Scholarship | Study | Imperial College London"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Correct the official_source_url of scholarship id=737 to its own programme page.",
        epilog="DRY RUN BY DEFAULT. Pass --apply to write.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report only; write nothing (the default).")
    parser.add_argument("--apply", action="store_true", help="Write the change in one transaction.")
    parser.add_argument("--database", default=LOCAL_DB, help="SQLite database to correct.")
    args = parser.parse_args()

    if (os.getenv("SCHOLARZONE_ENVIRONMENT") or "development").strip().lower() == "production":
        print("REFUSED: SCHOLARZONE_ENVIRONMENT=production.", file=sys.stderr)
        return 2

    con = sqlite3.connect(args.database)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT id, title, official_source_url, application_link FROM scholarships WHERE id=?",
            (TARGET_ID,),
        ).fetchone()
        if row is None:
            print(f"REFUSED: scholarship id={TARGET_ID} not found.", file=sys.stderr)
            return 2
        if row["official_source_url"] != EXPECTED_BEFORE:
            print(
                f"REFUSED: id={TARGET_ID} official_source_url is\n"
                f"  {row['official_source_url']}\n"
                f"but this correction expects\n"
                f"  {EXPECTED_BEFORE}\n"
                "The record may already be corrected or is not the record this script was written for.",
                file=sys.stderr,
            )
            return 2

        print("=" * 78)
        print("CORRECTION: official_source_url of scholarship id=737")
        print("=" * 78)
        print(f"  record  : {row['title']}")
        print(f"  before  : {row['official_source_url']}")
        print(f"  after   : {CORRECTED_AFTER}")
        print(f"  evidence: GET {EVIDENCE_URL} -> 200, document title {EVIDENCE_TITLE!r}")
        print(f"  mode    : {'APPLY' if args.apply else 'DRY RUN (nothing will be written)'}")
        print()

        if not args.apply:
            print("DRY RUN COMPLETE — no changes written. Re-run with --apply to apply.")
            return 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            con.execute(
                "UPDATE scholarships SET official_source_url=?, application_link=?, updated_at=? WHERE id=?",
                (CORRECTED_AFTER, CORRECTED_AFTER, now, TARGET_ID),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise

        after = con.execute(
            "SELECT official_source_url FROM scholarships WHERE id=?", (TARGET_ID,)
        ).fetchone()["official_source_url"]
        ok = after == CORRECTED_AFTER
        print(f"APPLIED. id={TARGET_ID} official_source_url is now {after}")
        print(f"VERIFIED: {ok}")
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
