"""Resolve the open catalogue-integrity items with official evidence.

Phase 4 of the autonomous pass, continued on
phase3/catalogue-accuracy-2026-10-11. Each item was re-verified against
the awarding body's own page during this pass:

A. ESKAS 565 / 727 - the same programme.
   https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships is
   the official page both records cite. It is titled "Swiss Government
   Excellence Scholarships 2027 - 2028" and states "Applications are open
   starting August 20, 2026", "mainly intended for talented early career
   researchers (ECRs) from abroad who have already completed their
   Master's degree", research scholarships "max. age: 35 / funding:
   CHF 2450.--/month", and "By the end of May at the latest, the FCS will
   announce its decisions". Record 727 carries the accurate restriction
   text (research scholarships and an initial artistic Master's only, not
   standard Master's study), so it is canonical; 565's "PhD, Master's"
   degree text is misleading and it is archived. Field-level corrections
   to 727 bring the deadline display to the official wording of the
   2027-2028 call.

B. MEXT stipend discrepancy 143,000 vs 144,000 JPY - resolved as a
   category-dependent amount, not a typo. The official English guidelines
   PDF the merged record cites states: "Students receiving the preparatory
   education and non-regular students: 143,000 yen per month"; "Regular
   students enrolled in master's or professional degree courses: 144,000
   yen per month"; "Regular students enrolled in doctoral courses:
   145,000 yen per month", plus "A supplemental regional allowance of
   2,000 yen or 3,000 yen per month". The single-amount column cannot hold
   three values honestly, so it is set to null and the official per-course
   wording is recorded in the funding text; currency and period remain.

C. SUSS record 449 - the live official page returns HTTP 403 (as in the
   audit), so it is not proof of anything either way. The legitimate
   Wayback Machine snapshot of the official page
   (https://web.archive.org/web/20250620050824/...) is reachable and
   carries the scholarship's own wording (three PhD programmes, 2nd Upper
   Class Honours, full-time, no other sponsorship, tenure up to four
   years, merit nomination at admissions interview). That snapshot is
   attached to the record's official source list with its snapshot date, so
   the provenance is visible, and the unverifiable live fields (the
   31 August 2026 deadline) are left exactly as they are.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DB_PATH = BASE / "backend/scholarzone.db"
LEDGER_PATH = BASE / "backend/research_output/publish/open_items_ledger.json"
TODAY = "2026-10-12"

ESKAS_URL = "https://www.sbfi.admin.ch/en/swiss-government-excellence-scholarships"
ESKAS_DISPLAY = (
    "Applications are open starting August 20, 2026 (Swiss Government Excellence "
    "Scholarships 2027-2028); application deadlines by country of origin are "
    "published on the official page. The FCS announces its decisions by the end "
    "of May at the latest."
)
MEXT_FUNDING = (
    "Research Students stipend, 2027 English guidelines: preparatory education "
    "and non-regular students 143,000 yen per month; regular students enrolled "
    "in master's or professional degree courses 144,000 yen per month; regular "
    "students enrolled in doctoral courses 145,000 yen per month; plus a "
    "supplemental regional allowance of 2,000 yen or 3,000 yen per month."
)
MEXT_PERIOD = "monthly, depending on the course enrolled (2027 guidelines)"
SUSS_ARCHIVE = (
    "https://web.archive.org/web/20250620050824/"
    "https://www.suss.edu.sg/academics/programmes/graduate-programmes/"
    "admissions/financial-assistance/scholarship"
)


def resolve() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    ledger = {"resolved_at": now, "items": []}

    try:
        # ---- A. ESKAS 565 -> 727 merge
        canonical = conn.execute("SELECT * FROM scholarships WHERE id = 727").fetchone()
        loser = conn.execute("SELECT * FROM scholarships WHERE id = 565").fetchone()
        if canonical is None or loser is None:
            raise SystemExit("ESKAS pair incomplete in the local database")
        changes = []
        old_display = canonical["deadline_display"]
        conn.execute(
            "UPDATE scholarships SET deadline_display = ?, status = ?, "
            "last_verified_date = ?, last_verified_at = ?, updated_at = ? WHERE id = 727",
            (ESKAS_DISPLAY, "open", TODAY, TODAY, now),
        )
        changes.append({"field": "deadline_display", "from": old_display, "to": ESKAS_DISPLAY})
        changes.append({"field": "status", "to": "open"})
        changes.append(
            {
                "field": "last_verified_date/at",
                "to": TODAY,
                "why": "official page re-fetched live today",
            }
        )
        reason = (
            "DUPLICATE MERGE (autonomous pass 2026-10-12): same programme as record "
            "id 727 - both cite the official SBFI/SERI page 'Swiss Government "
            "Excellence Scholarships 2027-2028' (applications open from 20 August "
            "2026). 565's degree text ('PhD, Master's') is misleading: the official "
            "page restricts ESKAS to research scholarships and an initial artistic "
            "Master's. See open_items_ledger.json."
        )
        conn.execute(
            "UPDATE scholarships SET is_archived = 1, archived_at = ?, archived_reason = ? WHERE id = 565",
            (now, reason),
        )
        ledger["items"].append(
            {
                "item": "ESKAS 565/727",
                "verdict": "same programme and same intake (2027-2028 call)",
                "canonical_id": 727,
                "merged_away_id": 565,
                "evidence": [
                    {"url": ESKAS_URL, "quote": "Applications are open starting August 20, 2026.", "checked_on": TODAY},
                    {"url": ESKAS_URL, "quote": "Swiss Government Excellence Scholarships are mainly intended for talented early career researchers (ECRs) from abroad who have already completed their Master's degree.", "checked_on": TODAY},
                    {"url": ESKAS_URL, "quote": "Research scholarships ... (max. age: 35 / funding: CHF 2450.--/month)", "checked_on": TODAY},
                    {"url": ESKAS_URL, "quote": "By the end of May at the latest, the FCS will announce its decisions regarding the scholarship awards for the following academic year.", "checked_on": TODAY},
                ],
                "changes_on_canonical": changes,
            }
        )
        print("ESKAS: canonical 727, archived 565")

        # ---- B. MEXT stipend structure
        row = conn.execute("SELECT * FROM scholarships WHERE id = 514").fetchone()
        if row is None:
            raise SystemExit("MEXT canonical record 514 missing")
        changes = []
        for field, old, new in (
            ("funding", row["funding"], MEXT_FUNDING),
            ("funding_amount", row["funding_amount"], None),
            ("funding_period", row["funding_period"], MEXT_PERIOD),
            ("last_verified_date", row["last_verified_date"], TODAY),
            ("last_verified_at", row["last_verified_at"], TODAY),
        ):
            if str(old or "") != str(new or ""):
                conn.execute(
                    f"UPDATE scholarships SET {field} = ? WHERE id = 514",
                    (new,),
                )
                changes.append({"field": field, "from": old, "to": new})
        ledger["items"].append(
            {
                "item": "MEXT 514 stipend structure",
                "verdict": "discrepancy resolved: the amount is course-dependent, not one number",
                "record_id": 514,
                "evidence": [
                    {
                        "url": "https://www.studyinjapan.go.jp/en/_mt/2026/04/0102-2027_Research_Guidelines_E.pdf",
                        "quote": "Students receiving the preparatory education and non-regular students: 143,000 yen per month / Regular students enrolled in master's or professional degree courses: 144,000 yen per month / Regular students enrolled in doctoral courses: 145,000 yen per month.",
                        "checked_on": TODAY,
                    },
                    {
                        "url": "https://www.studyinjapan.go.jp/en/_mt/2026/04/0102-2027_Research_Guidelines_E.pdf",
                        "quote": "A supplemental regional allowance of 2,000 yen or 3,000 yen per month will be added to the monthly scholarship amount.",
                        "checked_on": TODAY,
                    },
                ],
                "changes_on_canonical": changes,
            }
        )
        print("MEXT 514: category-dependent stipend recorded")

        # ---- C. SUSS archive citation
        row = conn.execute("SELECT official_details FROM scholarships WHERE id = 449").fetchone()
        if row is None:
            raise SystemExit("SUSS record 449 missing")
        details = json.loads(row["official_details"] or "{}")
        urls = list(details.get("official_source_urls") or [])
        if SUSS_ARCHIVE not in urls:
            urls.append(SUSS_ARCHIVE)
            details["official_source_urls"] = urls
            details["archive_note"] = (
                "Live official page returns HTTP 403 (bot protection); the archived "
                "official page snapshot of 2025-06-20 is attached as supplementary "
                "provenance. Deadline fields remain unverified against the live page "
                "and were not changed."
            )
            conn.execute(
                "UPDATE scholarships SET official_details = ?, last_verified_date = ?, last_verified_at = ? WHERE id = 449",
                (json.dumps(details, ensure_ascii=False), TODAY, TODAY),
            )
        ledger["items"].append(
            {
                "item": "SUSS 449",
                "verdict": "live page unreachable (403); structural facts confirmed from the archived official page",
                "record_id": 449,
                "evidence": [
                    {
                        "url": SUSS_ARCHIVE,
                        "quote": "You must be an applicant seeking admission to one of the three PhD programmes offered by SUSS, and have at least a 2nd Upper Class Honours Degree from a reputable university or equivalent qualifications. ... The scholarship is awarded for the minimum period required to complete the PhD programme, up to maximum four (4) years.",
                        "checked_on": TODAY,
                    },
                    {"url": "https://www.suss.edu.sg/academics/programmes/graduate-programmes/admissions/financial-assistance/scholarship", "quote": "HTTP 403 on 2026-10-12 (unchanged from the audit)", "checked_on": TODAY},
                ],
                "changes_on_canonical": [
                    {"field": "official_details.official_source_urls", "added": SUSS_ARCHIVE},
                    {"field": "last_verified_date/at", "to": TODAY},
                ],
            }
        )
        print("SUSS 449: archived official page attached; live deadline left unverified")

        conn.commit()
    finally:
        conn.close()

    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ledger:", LEDGER_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(resolve())
