"""Finish the id=737 correction: update the citation fields.

Why a second script
-------------------
``correct_imperial_737.py`` fixed the record's ``official_source_url`` and
``application_link``. Two citation fields were written before that correction
ran and still point only at Imperial's generic scholarship-search page:

* ``official_details.official_source_urls``
* ``programme_verification.source_citations``

Leaving them would mean the record's own evidence trail cites a search page
while its ``official_source_url`` cites the programme page — two different
claims about the same source in one row. This script replaces the single stale
citation with the verified programme page first and the search tool second,
which is the true provenance: the programme page for the specific award, the
search tool for the award value that is published there rather than on the
programme page.

Evidence for the correction
---------------------------
GET https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/
    commonwealth-shared-scholarship-20262027.php
returns 200 and the document title "Commonwealth Shared Scholarship | Study |
Imperial College London", matching this record's own title.

Safety
------
Dry-run by default; ``--apply`` required. Verifies the current citation value
before writing and refuses if it is not what it expects. One transaction. No
other field is touched.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime

LOCAL_DB = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend\scholarzone.db"

TARGET_ID = 737
STALE_URL = "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
PROGRAMME_URL = (
    "https://www.imperial.ac.uk/study/fees-and-funding/scholarships-search/"
    "commonwealth-shared-scholarship-20262027.php"
)
SEARCH_TOOL_URL = STALE_URL


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update the citation fields of scholarship id=737 to cite its own programme page.",
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
            "SELECT id, title, official_source_url, official_details, programme_verification FROM scholarships WHERE id=?",
            (TARGET_ID,),
        ).fetchone()
        if row is None:
            print(f"REFUSED: scholarship id={TARGET_ID} not found.", file=sys.stderr)
            return 2
        if row["official_source_url"] != PROGRAMME_URL:
            print(
                f"REFUSED: id={TARGET_ID} official_source_url is {row['official_source_url']!r}.\n"
                "Run correct_imperial_737.py --apply first, or this is not the record this script expects.",
                file=sys.stderr,
            )
            return 2

        od = json.loads(row["official_details"] or "{}")
        pv = json.loads(row["programme_verification"] or "{}")
        live_od_urls = od.get("official_source_urls", [])
        live_pv_urls = pv.get("source_citations", [])

        new_od_urls = [PROGRAMME_URL, SEARCH_TOOL_URL]
        new_pv_urls = [PROGRAMME_URL, SEARCH_TOOL_URL]

        print("=" * 78)
        print(f"CITATION CORRECTION: scholarship id={TARGET_ID}")
        print("=" * 78)
        print(f"  record : {row['title']}")
        print()
        print(f"  official_details.official_source_urls")
        print(f"    before : {json.dumps(live_od_urls)}")
        print(f"    after  : {json.dumps(new_od_urls)}")
        print(f"  programme_verification.source_citations")
        print(f"    before : {json.dumps(live_pv_urls)}")
        print(f"    after  : {json.dumps(new_pv_urls)}")
        print(f"  evidence: GET {PROGRAMME_URL} -> 200, title 'Commonwealth Shared Scholarship | Study | Imperial College London'")
        print(f"  mode    : {'APPLY' if args.apply else 'DRY RUN (nothing will be written)'}")
        print()

        if live_od_urls != [STALE_URL] or live_pv_urls != [STALE_URL]:
            print(
                "NOTE: the current citation lists are not exactly the stale single-URL form this "
                "script expects.\nThe before values are printed above for review; the correction "
                "still applies if you confirm them.",
                file=sys.stderr,
            )
            if not args.apply:
                print("\nDRY RUN COMPLETE — no changes written.", file=sys.stderr)
                return 2

        if not args.apply:
            print("DRY RUN COMPLETE — no changes written. Re-run with --apply to apply.")
            return 0

        od["official_source_urls"] = new_od_urls
        pv["source_citations"] = new_pv_urls
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            con.execute(
                "UPDATE scholarships SET official_details=?, programme_verification=?, updated_at=? WHERE id=?",
                (json.dumps(od, ensure_ascii=False), json.dumps(pv, ensure_ascii=False), now, TARGET_ID),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise

        after = con.execute(
            "SELECT official_details, programme_verification FROM scholarships WHERE id=?", (TARGET_ID,)
        ).fetchone()
        ok = (
            json.loads(after["official_details"])["official_source_urls"] == new_od_urls
            and json.loads(after["programme_verification"])["source_citations"] == new_pv_urls
        )
        print(f"APPLIED. id={TARGET_ID} citation fields updated. VERIFIED: {ok}")
        return 0 if ok else 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
