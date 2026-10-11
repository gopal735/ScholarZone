"""Apply field corrections to the local (non-production) database, with a
correction ledger.

Every correction must arrive with the official evidence that supports it:
the URL that was fetched, the verbatim quote, and the date it was checked.
A correction without that evidence is refused, because a catalogue value
with no checkable source is indistinguishable from an invented one.

Only §4 fields (existing data quality) are corrected here. Values that
could not be verified stay exactly as they are, including nulls.

Run: python backend/research_output/publish/apply_field_corrections.py <corrections.json>
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[3]
DB_PATH = BASE / "backend/scholarzone.db"
LEDGER_PATH = Path(__file__).with_name("field_corrections_ledger.json")

# The fields a verified correction may touch. Anything outside this set is
# refused: the correction pass fixes values, not identity or provenance.
CORRECTABLE_FIELDS = {
    "deadline_date",
    "deadline_display",
    "deadline_precision",
    "status",
    "program_type",
    "description",
    "duration",
    "best_fit",
    "degree",
    "funding",
    "funding_amount",
    "funding_currency",
    "funding_period",
    "tuition_coverage",
    "english_requirement",
    "eligibility_summary",
    "selection_notes",
    "official_source",
}


def main(path: str) -> int:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    records = payload.get("records", [])
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    applied = []
    skipped = []
    try:
        for entry in records:
            rid = entry.get("id")
            # Verification agents write "recommended"; the lead writes "proposed".
            # Both shapes carry {field: value} and the same evidence block.
            proposed = entry.get("proposed") or entry.get("recommended") or {}
            evidence = entry.get("evidence") or []
            row = conn.execute(
                "SELECT * FROM scholarships WHERE id = ?", (rid,)
            ).fetchone()
            if row is None:
                skipped.append({"id": rid, "reason": "record not in local database"})
                continue
            if not evidence:
                skipped.append({"id": rid, "reason": "no official evidence supplied"})
                continue

            changes = {}
            for field, new_value in proposed.items():
                if field not in CORRECTABLE_FIELDS:
                    skipped.append({"id": rid, "reason": f"{field} not correctable in this pass"})
                    continue
                old_value = row[field]
                if new_value is None:
                    # Clearing a field is a correction too, and it needs the
                    # same evidence: it is only allowed when the official page
                    # states there is no such value (e.g. "There's no central
                    # application form"), never because the page was silent.
                    if old_value is None:
                        continue
                    changes[field] = {"from": old_value, "to": None}
                    continue
                if str(old_value or "") == str(new_value):
                    continue
                changes[field] = {"from": old_value, "to": new_value}

            if not changes:
                skipped.append({"id": rid, "reason": "no supported change (field already holds the value, or values were null)"})
                continue

            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            for field, change in changes.items():
                conn.execute(
                    f"UPDATE scholarships SET {field} = ? WHERE id = ?",
                    (change["to"], rid),
                )
            conn.execute(
                "UPDATE scholarships SET updated_at = ?, last_verified_date = ?, last_verified_at = ? WHERE id = ?",
                (now, datetime.now(timezone.utc).date().isoformat(),
                 datetime.now(timezone.utc).date().isoformat(), rid),
            )
            applied.append(
                {
                    "id": rid,
                    "applied_at": now,
                    "changes": changes,
                    "evidence": evidence,
                    "confidence": entry.get("confidence"),
                    "notes": entry.get("notes"),
                }
            )
            print(f"id {rid}: corrected {sorted(changes)}")
        conn.commit()
    finally:
        conn.close()

    ledger = {
        "ledger_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_file": str(path),
        "applied": applied,
        "skipped": skipped,
    }
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"applied {len(applied)} correction(s); skipped {len(skipped)}")
    for item in skipped:
        print(f"  skipped id {item['id']}: {item['reason']}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1]))
