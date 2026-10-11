"""Merge the three duplicate-identity pairs in the LOCAL database, with a
field-level reconciliation ledger.

Phase 3, point D of the intake-status task. Each pair was investigated
against the awarding body's own live pages on 2026-10-11 before this
script was written; the quotes are in the ledger it writes. A merge only
happens where the pair is proven to be the same programme AND the same
intake, and every field the merge changes is either copied from the losing
record's better-sourced value or corrected from the official page.

No record is hard-deleted: the losing row is archived with a reason naming
the canonical record, so any merge is reversible from the database itself.

Pairs and decisions (all official pages re-fetched 2026-10-11):

* 182 / 382 VU Fellowship Programme (VUFP). vu.nl's incoming-master
  scholarships page (382's URL) states "Our own VU Fellowship Programme
  (VUFP) is a merit-based tuition fee waiver", "Applications are welcome
  from November 1st 2026" and "Deadline VUFP application: 1 February 2027
  (23:59 CET)". 182's own URL 404s. Canonical: 382 (live page); 182 archived.
* 185 / 452 KTH Scholarship. kth.se's scholarship page (452's URL) states
  "Application deadlines for the KTH Scholarship 1 December 2026:
  Application opens 15 January 2027: Application closes 1 April 2027:
  Scholarship results announced" and "The KTH Scholarship covers the full
  tuition fee of a one or two year master's programme." 185's own URL 404s.
  Canonical: 452 (live page); 185 archived. "Julian, KTH Scholarship
  awardee" on 452 is a student testimonial on that page, not a programme
  type: the polluted program_type is replaced with the category phrase.
* 374 / 514 Japanese Government (MEXT) Scholarship 2027, Research Students
  (Embassy Recommendation). mext.go.jp's page (514's URL) states
  "JAPANESE GOVERNMENT (MEXT) SCHOLARSHIP FOR 2027 (RESEARCH STUDENTS)"
  and links the same English application guidelines PDF that 374 points
  at. Canonical: 514 (MEXT's own domain, stable across cycles); 374 archived,
  its guidelines URL carried onto the canonical record. The monthly
  stipend differs between the two records (143,000 vs 144,000 JPY) and the
  official English page that would settle it is a PDF that does not
  resolve as text: the canonical record's existing value is KEPT and the
  discrepancy is recorded unresolved for the next verification pass
  rather than guessed. Same for the region tag (Global vs Asia).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DB_PATH = BASE / "backend/scholarzone.db"
LEDGER_PATH = BASE / "backend/research_output/publish/dedupe_merges_ledger.json"

TODAY = "2026-10-11"

PAIRS = [
    {
        "pair": "182/382",
        "programme": "VU Fellowship Programme (VUFP)",
        "canonical_id": 382,
        "merged_away_id": 182,
        "verdict": "same programme, same intake",
        "evidence": [
            {
                "url": "https://vu.nl/en/education/more-about/incoming-master-scholarships",
                "quote": "Our own VU Fellowship Programme (VUFP) is a merit-based tuition fee waiver... Call to apply: 1st November 2026... Applications are welcome from November 1st 2026... Deadline VUFP application: 1 February 2027 (23:59 CET)",
                "checked_on": TODAY,
            },
            {
                "url": "https://vu.nl/en/deducation/scholarships/vu-fellowship-programme",
                "quote": "HTTP 404 - record 182's recorded official page no longer exists.",
                "checked_on": TODAY,
            },
        ],
        "corrections": [
            {
                "field": "deadline_date",
                "to": "2027-02-01",
                "reason": "Official page: 'Deadline VUFP application: 1 February 2027 (23:59 CET)'; the merged-away record carried this same date, the canonical one carried the opening date 1 November 2026 as its deadline.",
            },
            {
                "field": "deadline_display",
                "to": "Applications are welcome from November 1st 2026. Deadline VUFP application: 1 February 2027 (23:59 CET)",
                "reason": "Official page wording, both dates.",
            },
            {
                "field": "program_type",
                "to": "Merit-based tuition fee waiver for non-EU/EEA students",
                "reason": "The canonical record carried an eligibility sentence in this field; the official page names it 'a merit-based tuition fee waiver' for non-EU/EEA students."
            },
        ],
        "carry_over": [
            {"field": "official_source_urls", "note": "182's approved URLs (if any beyond the 404) are appended below."}
        ],
    },
    {
        "pair": "185/452",
        "programme": "KTH Scholarship",
        "canonical_id": 452,
        "merged_away_id": 185,
        "verdict": "same programme, same intake",
        "evidence": [
            {
                "url": "https://www.kth.se/en/studies/master/admissions/scholarships/kth-scholarship-1.72827",
                "quote": "Application deadlines for the KTH Scholarship / 1 December 2026: Application opens / 15 January 2027: Application closes / 1 April 2027: Scholarship results announced. The KTH Scholarship covers the full tuition fee of a one or two year master's programme.",
                "checked_on": TODAY,
            },
            {
                "url": "https://www.kth.se/en/utbildning/scholarships",
                "quote": "HTTP 404 - record 185's recorded official page no longer exists.",
                "checked_on": TODAY,
            },
        ],
        "corrections": [
            {
                "field": "deadline_display",
                "to": "1 December 2026: Application opens. 15 January 2027: Application closes. 1 April 2027: Scholarship results announced",
                "reason": "Verbatim from the official page; the canonical record listed only the closing date.",
            },
            {
                "field": "program_type",
                "to": "Merit-based tuition fee scholarship for fee-paying international students",
                "reason": "The canonical record carried a student testimonial ('Julian, KTH Scholarship awardee') in this field; the official page's scholarship description supports this category phrase."
            },
        ],
    },
    {
        "pair": "374/514",
        "programme": "Japanese Government (MEXT) Scholarship for 2027 (Research Students) - Embassy Recommendation",
        "canonical_id": 514,
        "merged_away_id": 374,
        "verdict": "same programme, same intake",
        "evidence": [
            {
                "url": "https://www.mext.go.jp/a_menu/koutou/ryugaku/boshu/1415352_00008.htm",
                "quote": "2027年度大使館推薦による国費外国人留学生（研究留学生）の募集について - JAPANESE GOVERNMENT (MEXT) SCHOLARSHIP FOR 2027 (RESEARCH STUDENTS) (PDF:403KB) [the official announcement page linking the English guidelines]",
                "checked_on": TODAY,
            },
            {
                "url": "https://www.studyinjapan.go.jp/en/_mt/2026/04/0102-2027_Research_Guidelines_E.pdf",
                "quote": "Official English application guidelines PDF, linked from the MEXT page (fetched as PDF; the stipend figure could not be read from it today).",
                "checked_on": TODAY,
            },
        ],
        "corrections": [
            {
                "field": "deadline_display",
                "to": None,
                "reason": "No central deadline is published for the embassy-recommendation track; each Japanese embassy publishes its own, so the null stays null and the display text explains that. (kept as-is unless currently missing)",
                "keep_existing": True,
            },
        ],
        "unresolved": [
            {
                "fields": ["funding_amount", "region"],
                "note": "Records disagree (143,000 vs 144,000 JPY per month; region Global vs Asia). The official page that would settle it is the English guidelines PDF, which does not resolve as fetchable text. The canonical record's existing values are kept untouched and the discrepancy is referred to the next verification pass; no value is guessed.",
            }
        ],
        "carry_over": [
            {
                "field": "official_source_urls",
                "note": "The merged-away record's studyinjapan.go.jp English guidelines PDF URL is appended to the canonical record's official_source_urls.",
            }
        ],
    },
]


def merge() -> int:
    if not DB_PATH.is_file():
        raise SystemExit(f"Local database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    report = {"merged_at": now, "pairs": []}
    try:
        for spec in PAIRS:
            canonical = conn.execute(
                "SELECT * FROM scholarships WHERE id = ?", (spec["canonical_id"],)
            ).fetchone()
            loser = conn.execute(
                "SELECT * FROM scholarships WHERE id = ?", (spec["merged_away_id"],)
            ).fetchone()
            if canonical is None or loser is None:
                raise SystemExit(f"pair {spec['pair']} is incomplete in the database")
            canonical_row = dict(canonical)
            loser_row = dict(loser)

            changes = []
            for correction in spec.get("corrections", []):
                field = correction["field"]
                if correction.get("keep_existing"):
                    continue
                old = canonical_row.get(field)
                new = correction["to"]
                if new is None or str(old or "") == str(new):
                    continue
                conn.execute(
                    f"UPDATE scholarships SET {field} = ? WHERE id = ?",
                    (new, spec["canonical_id"]),
                )
                changes.append({"field": field, "from": old, "to": new, "why": correction["reason"]})

            # Carry the merged-away record's official URL list onto the
            # canonical record (evidence travels with the merge).
            loser_urls = json.loads(loser_row["official_details"]).get("official_source_urls", []) if loser_row.get("official_details") else []
            if loser_urls:
                blob = canonical_row.get("official_details") or "{}"
                details = json.loads(blob)
                merged_urls = list(details.get("official_source_urls") or [])
                added = [u for u in loser_urls if u not in merged_urls]
                if added:
                    details["official_source_urls"] = merged_urls + added
                    conn.execute(
                        "UPDATE scholarships SET official_details = ? WHERE id = ?",
                        (json.dumps(details, ensure_ascii=False), spec["canonical_id"]),
                    )
                    changes.append(
                        {"field": "official_source_urls", "added": added, "why": "carried over from the merged-away record"}
                    )

            reason = (
                f"DUPLICATE MERGE (audit 2026-10-11, phase 3): same programme and intake as "
                f"record id {spec['canonical_id']} ({spec['programme']}). Verdict: "
                f"{spec['verdict']}. Evidence checked {TODAY}; see "
                f"backend/research_output/publish/dedupe_merges_ledger.json."
            )
            conn.execute(
                "UPDATE scholarships SET is_archived = 1, archived_at = ?, archived_reason = ? WHERE id = ?",
                (now, reason, spec["merged_away_id"]),
            )

            report["pairs"].append(
                {
                    "pair": spec["pair"],
                    "programme": spec["programme"],
                    "verdict": spec["verdict"],
                    "canonical_id": spec["canonical_id"],
                    "merged_away_id": spec["merged_away_id"],
                    "evidence": spec.get("evidence", []),
                    "changes_on_canonical": changes,
                    "unresolved": spec.get("unresolved", []),
                }
            )
            print(
                f"merged {spec['pair']}: canonical {spec['canonical_id']}, "
                f"archived {spec['merged_away_id']}, {len(changes)} field change(s) on the canonical record"
            )
        conn.commit()
    finally:
        conn.close()

    LEDGER_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"ledger: {LEDGER_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(merge())
