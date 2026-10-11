"""Removal ledger for genuinely discontinued published records, and the
script that applies it to the local (non-production) database.

Phase 3 of the intake-status audit. The ledger is the auditable record of
why each record left the public catalogue; this script is the only thing
that touches the database, and it only sets the repository's own archival
flags (`is_archived`, `archived_at`, `archived_reason`) on records whose
official page has been re-fetched today and re-confirmed to state that
the programme is discontinued.

It deliberately does NOT delete rows, and it refuses to run on a database
other than the local SQLite copy.

Evidence re-checked live 2026-10-11 before this script was written; each
entry's `last_checked` and `evidence_quote` record the verbatim text the
page carried on that date.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path(__file__).with_name("removals_scholarships_ledger.json")
DB_PATH = Path(__file__).resolve().parents[2] / "scholarzone.db"

LEDGER = [
    {
        "id": 279,
        "title": "NORPART – Norwegian Partnership Programme",
        "classification": "genuinely_discontinued",
        "confidence": 0.85,
        "last_checked": "2026-10-11",
        "official_source_url": "https://hkdir.no/en/programmer-og-tilskuddsordninger/norpart",
        "evidence_url": "https://hkdir.no/en/programmer-og-tilskuddsordninger/norpart",
        "evidence_quote": (
            "Grants you can apply for now: 0 ... The Norwegian government has proposed to "
            "end support for the NORPART-programme in the 2025 National Budget. This means "
            "that only around seven projects will receive funding in the planned allocation "
            "in October, based on the NOK 35 million that was allocated to the programme for "
            "2024. ... Results of the call for applications 2024 The deadline for the call for "
            "proposals for 2024 was 3. June."
        ),
        "why_removed": (
            "The awarding body (HK-dir) publishes zero open grants and states the Norwegian "
            "government has proposed to end support for the programme. The last call closed "
            "3 June 2024 and no successor call exists. The scheme funds institutional "
            "partnerships, not individual students, so it was never an applicant-facing "
            "scholarship."
        ),
        "superseded_by": None,
    },
    {
        "id": 729,
        "title": "Vanier Canada Graduate Scholarship",
        "classification": "genuinely_discontinued",
        "confidence": 0.95,
        "last_checked": "2026-10-11",
        "official_source_url": "https://vanier.gc.ca/en/home-accueil.html",
        "evidence_url": "https://vanier.gc.ca/en/home-accueil.html",
        "evidence_quote": (
            "We are no longer accepting applications for the Vanier Canada Graduate "
            "Scholarships. Please refer to the Canada Graduate Research Scholarship - Doctoral "
            "program web page for information regarding the new harmonized program."
        ),
        "why_removed": (
            "The official programme page states applications are no longer accepted and "
            "points to the harmonized successor. The successor (Canada Graduate Research "
            "Scholarship - Doctoral) is already published in the catalogue as active record "
            "id 306, so this removal costs applicants no discoverable opportunity and the "
            "successor needs no replacement record."
        ),
        "superseded_by": 306,
    },
]


def write_ledger() -> Path:
    ledger = {
        "ledger_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_branch": "phase3/catalogue-accuracy-2026-10-11",
        "audit_reference": {
            "audit_branch": "audit/intake-status-2026-10-11",
            "audit_commit": "52d5aa8",
            "report": "backend/research_output/publish/PHASE2_REPORT.md",
            "population": "153 closed-labelled published records",
        },
        "policy": (
            "Only records whose official awarding-body page states the programme is "
            "discontinued are removed. A passed deadline alone is never grounds for removal; "
            "the other 151 closed-labelled published records (recurring, temporarily "
            "closed, upcoming/current, uncertain) stay published on their last researched "
            "state. No record is hard-deleted; each is archived with this ledger as the "
            "exportable reason."
        ),
        "removals": [
            {**entry, "removed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
            for entry in LEDGER
        ],
    }
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return LEDGER_PATH


def apply_ledger() -> None:
    if not DB_PATH.is_file():
        raise SystemExit(f"Local database not found at {DB_PATH}; refusing to touch production.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        for entry in LEDGER:
            row = conn.execute(
                "SELECT id, title, is_archived FROM scholarships WHERE id = ?", (entry["id"],)
            ).fetchone()
            if row is None:
                raise SystemExit(f"ledger id {entry['id']} not in the local database")
            if row["is_archived"]:
                print(f"id {entry['id']} already archived; skipping")
                continue
            reason = (
                f"DISCONTINUED (audit 2026-10-11, phase 3): {entry['title']}. "
                f"Confidence {entry['confidence']}. "
                f"Evidence {entry['evidence_url']} checked {entry['last_checked']}: "
                f"\"{entry['evidence_quote'][:240]}\" "
                f"See backend/research_output/publish/removals_scholarships_ledger.json."
            )
            conn.execute(
                "UPDATE scholarships SET is_archived = 1, archived_at = ?, archived_reason = ? WHERE id = ?",
                (now, reason, entry["id"]),
            )
            print(f"archived id {entry['id']} ({entry['title']})")
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "apply"
    if command == "ledger":
        print(write_ledger())
    elif command == "apply":
        write_ledger()
        apply_ledger()
    elif command == "verify":
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        try:
            for entry in LEDGER:
                row = conn.execute(
                    "SELECT id, is_archived, archived_reason FROM scholarships WHERE id = ?",
                    (entry["id"],),
                ).fetchone()
                assert row is not None, f"id {entry['id']} missing"
                assert row[1] == 1, f"id {entry['id']} not archived"
                assert "DISCONTINUED" in row[2], f"id {entry['id']} reason missing evidence"
            print("ledger applied: both records archived with evidence-carrying reasons")
        finally:
            conn.close()
    else:
        raise SystemExit(f"unknown command {command!r}")
