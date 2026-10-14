"""Audit every stored confirmation note for completeness, and try to recover.

A confirmation note that stops mid-sentence is read as though the finding itself
stops there, which is a weaker and different claim from the one that was made.
The rule for this audit:

* never invent the missing text;
* never append punctuation or filler to make a fragment look complete;
* recover only where a complete version already exists in the repository;
* otherwise name the record and leave it for human review.

Outputs ``confirmation_audit.json``: for every confirmation, its original state,
whether a longer complete version was found, where it came from, and the
repaired state when one exists.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.jobs.scholarzone_maintenance import NOTE_LIMIT, _note_text  # noqa: E402

CONFIG = ROOT / "backend" / "config" / "verification_confirmations.json"
RAW = HERE / "live_raw.json"
DECISIONS = HERE / "decisions_22.json"
INVENTORY = HERE / "verification_inventory.json"
CATALOGUE = HERE / "live_catalogue.json"

#: A note is complete when its final non-space character can end a sentence. A
#: closing quote or bracket after that character still counts as complete.
TERMINAL = re.compile(r"[.!?…]['\"’”\)\]]*\s*$")


def is_complete(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    return bool(TERMINAL.search(stripped))


def load() -> tuple[dict, dict, list, dict]:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    raw = {int(k): v for k, v in json.loads(RAW.read_text(encoding="utf-8")).items()}
    catalogue = {
        r["id"]: r
        for r in json.loads(CATALOGUE.read_text(encoding="utf-8"))["items"]
    }
    decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    return config, raw, decisions, catalogue, inventory


def candidates_for(sid: int, decisions, inventory) -> list[tuple[str, str]]:
    """Every longer text the repository already holds for this record."""
    found: list[tuple[str, str]] = []

    def consider(source: str, value) -> None:
        if isinstance(value, str) and value.strip():
            found.append((source, value.strip()))

    for entry in decisions.get("records", []) if isinstance(decisions, dict) else []:
        if int(entry.get("id", -1)) != sid:
            continue
        consider("decisions_22.evidence", entry.get("evidence"))
        consider("decisions_22.notes", entry.get("notes"))
        consider("decisions_22.reason", entry.get("reason"))
        consider(
            "decisions_22.verification_note",
            (entry.get("decision") or {}).get("verification_note")
            if isinstance(entry.get("decision"), dict)
            else None,
        )

    records = inventory.get("records") if isinstance(inventory, dict) else None
    if isinstance(records, dict):
        row = records.get(str(sid)) or records.get(sid)
        if isinstance(row, dict):
            consider("inventory.evidence", row.get("evidence"))
            consider("inventory.verification_notes", row.get("verification_notes"))
            consider("inventory.note", row.get("note"))

    return found


def main() -> None:
    config, raw, decisions, catalogue, inventory = load()
    entries = config["records"]

    audit: list[dict] = []
    stored_truncated = 0
    stored_absent = 0
    config_truncated = 0
    recoverable = 0
    unresolved: list[int] = []
    absent: list[int] = []
    derivable_complete: list[int] = []
    extract_form: list[int] = []

    for entry in entries:
        sid = int(entry["id"])
        evidence = str(entry.get("evidence") or "")
        stored = str((raw.get(sid) or {}).get("verification_notes") or "")
        original_complete = is_complete(evidence)
        stored_complete = is_complete(stored)

        longer = [
            (source, text)
            for source, text in candidates_for(sid, decisions, inventory)
            if len(text) > len(evidence)
        ]
        recovered_from = None
        repaired = evidence
        if not original_complete or not stored_complete:
            # A complete version is only usable if it is genuinely longer and
            # genuinely ends a sentence. Anything else is not a recovery.
            for source, text in longer:
                if is_complete(text):
                    repaired = _note_text(text)
                    recovered_from = source
                    recoverable += 1
                    break

        if not original_complete:
            config_truncated += 1
        if not stored:
            stored_absent += 1
            absent.append(sid)
        elif not stored_complete:
            stored_truncated += 1
        if not original_complete and recovered_from is None:
            unresolved.append(sid)

        # What a stage run would write, derived only from text already held.
        projected = _note_text(evidence)
        if is_complete(projected):
            derivable_complete.append(sid)
        else:
            extract_form.append(sid)

        audit.append(
            {
                "id": sid,
                "name": entry.get("name"),
                "source_url": entry.get("source_url"),
                "checked_at": entry.get("checked_at"),
                "original_complete": original_complete,
                "stored_complete": stored_complete,
                "original_length": len(evidence),
                "stored_length": len(stored),
                "recovered_from": recovered_from,
                "repaired_complete": is_complete(repaired),
                "repaired_length": len(repaired),
                "state": (
                    "unchanged_complete"
                    if original_complete and stored_complete
                    else "recovered"
                    if recovered_from
                    else "needs_human_review"
                ),
                "original_tail": evidence[-90:],
            }
        )

    states: dict[str, int] = {}
    for row in audit:
        states[row["state"]] = states.get(row["state"], 0) + 1

    report = {
        "generated_at": "2026-10-03",
        "confirmations_total": len(entries),
        "config_evidence_complete": len(entries) - config_truncated,
        "config_evidence_incomplete": config_truncated,
        "stored_note_incomplete": stored_truncated,
        "stored_note_absent": stored_absent,
        "recovered_from_repository_text": recoverable,
        "states": states,
        "unresolved_ids": sorted(unresolved),
        "stored_note_absent_ids": sorted(absent),
        "note_limit": NOTE_LIMIT,
        "repair_available": {
            "complete_sentence_derivable_from_repository_text": len(derivable_complete),
            "explicit_extract_form_only": len(extract_form),
            "full_evidence_recoverable_anywhere_in_repository": recoverable,
            "note": (
                "_note_text is the shipped rule for shortening a finding. Applied "
                "to the text already stored, it ends on a whole sentence where one "
                "exists inside the limit, and otherwise returns an explicitly "
                "labelled extract rather than a silent mid-sentence fragment. It "
                "never supplies a word the repository does not already hold, so it "
                "can repair how a truncation reads but not the missing evidence."
            ),
        },
        "rule": (
            "A note is complete only if its last character can end a sentence. "
            "Text is recovered only from a longer complete string the repository "
            "already holds. No note is completed by appending punctuation, filler "
            "or generated text; what cannot be recovered is named and left alone."
        ),
        "records": audit,
    }
    (HERE / "confirmation_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print(f"confirmations audited      : {len(entries)}")
    print(f"config evidence complete   : {report['config_evidence_complete']}")
    print(f"config evidence incomplete : {report['config_evidence_incomplete']}")
    print(f"stored note incomplete     : {report['stored_note_incomplete']}")
    print(f"stored note absent         : {report['stored_note_absent']}")
    print(f"recovered from repo text   : {recoverable}")
    print(f"projected complete sentence: {len(derivable_complete)}")
    print(f"projected explicit extract : {len(extract_form)}")
    print(f"states                     : {states}")
    print(f"needing human review       : {len(unresolved)}")
    print("wrote verification/confirmation_audit.json")


if __name__ == "__main__":
    main()