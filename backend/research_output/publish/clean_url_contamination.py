"""Remove the systematic cross-programme URL contamination from the local
(non-production) database, with a per-record removable ledger.

A single earlier research wave pasted four URLs (one SUTD scholarship page,
one ANR call page, one Chinese-embassy news item) into the
`official_details.official_source_urls` provenance lists of 141 unrelated
records - 132, 121, 118 and 116 records respectively for the four URLs, an
example being the DAAD Scholarship row whose provenance listed a Chinese
embassy news item, a French research call and SUTD's own scholarship page
alongside its awarding body daad.de.

The cleanup is deliberately narrow:

* Only the 21 distinct contaminated URLs identified on 2026-10-11 are
  touched; no other URL is rewritten.
* A URL is kept in a record when the record's own awarding domain owns it:
  either the URL IS the record's official_source_url, or it is on the same
  host. The SUTD records (109, 446, 447), the four ANR call records (503,
  504, 505, 548) and the embassy-track CSC records (243, 322, 323, 324 -
  embassies are the official application channel for that track) therefore
  keep their own pages; everything else loses the pasted ones.

The research corpus (backend/config/programme_details.json) is NOT touched
by this script; the same contamination is present there and is reported
for the owners of the corpus to fix, not silently rewritten here.

Usage:
    python backend/research_output/publish/clean_url_contamination.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE = Path(__file__).resolve().parents[3]
DB_PATH = BASE / "backend/scholarzone.db"
LEDGER_PATH = BASE / "backend/research_output/publish/url_contamination_cleanup_ledger.json"

# The 21 distinct pasted URLs, grouped by the host that was pasted across
# records it has nothing to do with.
CONTAMINATED = [
    "https://www.sutd.edu.sg/admissions/undergraduate/scholarship/sutd-administered/sutd-undergraduate-merit-scholarship",
    "https://www.sutd.edu.sg/admissions/graduate/scholarships",
    "https://www.sutd.edu.sg/admissions/undergraduate/scholarship/sutd-administered",
    "https://www.sutd.edu.sg/admissions/graduate/scholarship/sutd-graduate-fellowships-scholarships",
    "https://www.sutd.edu.sg/admissions/graduate/scholarship/sutd-graduate-fellowships-scholarships/",
    "https://www.sutd.edu.sg/admissions/graduate/phd/",
    "https://admission.sutd.edu.sg/",
    "https://anr.fr/fr/detail/call/appel-a-projets-m-eranet-202627-science-et-ingenierie-des-materiaux-pour-linnovation-en-europe",
    "https://bs.china-embassy.gov.cn/eng/sgxw/202510/t20251028_11742717.htm",
    "https://sl.china-embassy.gov.cn/eng/xwdt/",
    "https://bd.china-embassy.gov.cn/eng/sghd/202512/t20251219_11776194.htm",
    "https://id.china-embassy.gov.cn/eng/sgdt/202510/t20251027_11741674.htm",
]
CONTAMINATED_SET = {u.rstrip("/") for u in CONTAMINATED}


def host_of(url: str) -> str:
    return (urlparse(url).netloc or "").lower()


def normalise(url: str) -> str:
    return url.strip().rstrip("/")


def main() -> int:
    if not DB_PATH.is_file():
        raise SystemExit(f"Local database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    ledger = {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "rule": (
            "A contaminated URL stays in a record only when the record's own "
            "official_source_url is that URL or is on the same host; otherwise "
            "it was pasted there by a broken research wave and is removed from "
            "official_details.official_source_urls."
        ),
        "kept_for_owner_records": [],
        "removed": [],
        "records_touched": 0,
    }
    try:
        for row in conn.execute(
            "SELECT id, title, official_source, official_source_url, official_details "
            "FROM scholarships WHERE is_archived = 0 AND official_details IS NOT NULL"
        ):
            try:
                blob = json.loads(row["official_details"])
            except (TypeError, ValueError):
                continue
            if not isinstance(blob, dict):
                continue
            urls = blob.get("official_source_urls")
            if not isinstance(urls, list) or not urls:
                continue
            own_url = (row["official_source_url"] or "").strip()
            own_host = host_of(own_url)

            kept, removed = [], []
            for url in urls:
                if normalise(url) not in CONTAMINATED_SET:
                    kept.append(url)
                    continue
                is_own = normalise(url) == normalise(own_url) or (
                    own_host and host_of(url) == own_host
                )
                if is_own:
                    kept.append(url)
                    if url not in ledger["kept_for_owner_records"]:
                        ledger["kept_for_owner_records"].append(url)
                else:
                    removed.append(url)

            if not removed:
                continue
            blob["official_source_urls"] = kept
            conn.execute(
                "UPDATE scholarships SET official_details = ? WHERE id = ?",
                (json.dumps(blob, ensure_ascii=False), row["id"]),
            )
            ledger["removed"].append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "own_source_url": own_url,
                    "removed_urls": removed,
                }
            )
            ledger["records_touched"] += 1
        conn.commit()
    finally:
        conn.close()

    LEDGER_PATH.write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    total_urls = sum(len(entry["removed_urls"]) for entry in ledger["removed"])
    print(
        f"Removed {total_urls} pasted URL(s) from {ledger['records_touched']} records; "
        f"kept for their owning records: {ledger['kept_for_owner_records']}"
    )
    print(f"Ledger: {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
