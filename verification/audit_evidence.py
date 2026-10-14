"""Classify the evidence basis of every public record, using the repository's own
verification vocabulary rather than a second, incompatible one.

The repository already defines how strong a piece of evidence is:
``SourceType`` carries an authority score, ``ConfidenceLevel`` is
high/medium/low/conflict, and ``VerificationState`` is
verified/partially_verified/uncertain/conflict/unsupported. Those are the
contract. This audit maps each public record onto them and reports the four
operational buckets the review asked for on top, so no new trust system is
introduced and no record is downgraded merely because one particular field is
empty.

The rule is deliberately conservative in one direction only: nothing is promoted
without evidence, and nothing is demoted for lacking a quote when the repository
holds a substantive, source-attributable finding some other way.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.scholarship_evidence import (  # noqa: E402
    classify_source,
    is_authoritative_source,
)

INVENTORY = HERE / "verification_inventory.json"
RAW = HERE / "live_raw.json"
RETIRED = ROOT / "backend" / "config" / "retired_records.json"
CONFIRMATIONS = ROOT / "backend" / "config" / "verification_confirmations.json"
CORRECTIONS = ROOT / "backend" / "config" / "record_corrections.json"

#: Notes that assert a check without recording what was found. A timestamp plus
#: "Verified via admin dashboard" is metadata about the process, not evidence
#: about the scholarship.
PROCESS_ONLY = re.compile(
    r"^\s*(verified(?:\s+via\s+(?:the\s+)?admin(?:\s+dashboard)?)?\.?)\s*$",
    re.IGNORECASE,
)

#: A finding that quotes the source, or names the field and the page it was read
#: on. Either is attributable to the official source rather than to the act of
#: checking.
QUOTE = re.compile(r"[\"“”']|\bhttps?://|\bpage\b", re.IGNORECASE)


def classify(row: dict, confirmations: dict, corrections: dict, retired_ids: set) -> dict:
    sid = row["id"]
    notes = str(row.get("verification_notes") or "").strip()
    evidence = str(row.get("confirmation_evidence") or "").strip()
    cycle = str(row.get("cycle_verified") or "").strip()
    confidence = row.get("verification_confidence")
    url = row.get("official_source_url") or row.get("catalogue_url") or ""

    # --- not applicable ---------------------------------------------------
    if row.get("retired") or sid in retired_ids or row.get("public_state") in (
        "RETIRED",
        "NOT_PUBLIC",
    ):
        return {
            "bucket": "RETIRED_NOT_APPLICABLE",
            "verification_state": "unsupported",
            "confidence_level": None,
            "source_is_authoritative": False,
            "basis": "record is retired or not public",
        }

    # --- evidence ---------------------------------------------------------
    if evidence:
        state = "verified"
        basis = "quoted confirmation evidence exists in verification_confirmations.json"
    elif notes and not PROCESS_ONLY.match(notes):
        state = "verified" if QUOTE.search(notes) else "partially_verified"
        basis = "substantive verification finding stored on the record"
    elif cycle:
        state = "partially_verified"
        basis = "the cycle the finding applies to is recorded"
    elif confidence is not None:
        state = "partially_verified"
        basis = f"a recorded verification confidence of {confidence}"
    elif row.get("in_correction_file"):
        state = "partially_verified"
        basis = "a sourced correction exists in record_corrections.json"
    else:
        state = "uncertain"
        basis = "only a check was recorded; nothing about the scholarship itself"

    # --- source authority -------------------------------------------------
    source_type = classify_source(url) if url else None
    authoritative = bool(url) and is_authoritative_source(source_type)

    if state == "uncertain":
        bucket = "CONFIRM_WITH_PROVIDER"
    elif authoritative and state == "verified":
        bucket = "EVIDENCE_CONFIRMED"
    elif authoritative:
        bucket = "SOURCE_ONLY"
    else:
        bucket = "CONFIRM_WITH_PROVIDER"

    level = None
    if bucket == "EVIDENCE_CONFIRMED":
        level = Confidence.HIGH
    elif bucket == "SOURCE_ONLY":
        level = Confidence.MEDIUM
    elif bucket == "CONFIRM_WITH_PROVIDER":
        level = Confidence.LOW

    return {
        "bucket": bucket,
        "source_type": str(source_type) if source_type else None,
        "verification_state": state,
        "confidence_level": level,
        "basis": basis,
        "source_is_authoritative": authoritative,
    }


class Confidence:
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def main() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    raw = {int(k): v for k, v in json.loads(RAW.read_text(encoding="utf-8")).items()}
    confirmations = {
        int(r["id"]): r
        for r in json.loads(CONFIRMATIONS.read_text(encoding="utf-8"))["records"]
    }
    corrections = json.loads(CORRECTIONS.read_text(encoding="utf-8"))
    correction_ids = {
        int(r["id"]) for r in (corrections.get("records") or corrections.get("corrections") or [])
    }
    retired = json.loads(RETIRED.read_text(encoding="utf-8"))
    retired_entries = retired.get("records") or retired.get("retired") or []
    retired_ids = {int(r["id"]) for r in retired_entries}

    rows = inventory if isinstance(inventory, list) else inventory["records"]
    buckets = Counter()
    states = Counter()
    classified = []
    timestamp_only = []

    for row in rows:
        sid = row["id"]
        row = dict(row)
        row.setdefault("in_confirmation_file", sid in confirmations)
        if not row.get("confirmation_evidence") and sid in confirmations:
            row["confirmation_evidence"] = confirmations[sid].get("evidence")
        if not row.get("in_correction_file"):
            row["in_correction_file"] = sid in correction_ids
        verdict = classify(row, confirmations, corrections, retired_ids)
        buckets[verdict["bucket"]] += 1
        states[verdict["verification_state"]] += 1
        stored_notes = str((raw.get(sid) or {}).get("verification_notes") or "").strip()
        classified.append(
            {
                "id": sid,
                "name": row.get("name"),
                "public_state": row.get("public_state"),
                "bucket": verdict["bucket"],
                "verification_state": verdict["verification_state"],
                "confidence_level": verdict["confidence_level"],
                "source_is_authoritative": verdict["source_is_authoritative"],
                "basis": verdict["basis"],
                "stored_note_is_process_only": bool(
                    stored_notes and PROCESS_ONLY.match(stored_notes)
                ),
                "stored_note_length": len(stored_notes),
                "has_confirmation_evidence": bool(row.get("confirmation_evidence")),
            }
        )
        # The 172: publicly verified, no quoted evidence anywhere, and the only
        # thing recorded is that a check happened.
        if (
            row.get("public_state") == "VERIFIED"
            and not row.get("confirmation_evidence")
            and not str(row.get("verification_notes") or "").strip()
            and not row.get("cycle_verified")
            and row.get("verification_confidence") is None
        ):
            timestamp_only.append(sid)

    report = {
        "generated_at": "2026-10-03",
        "records_audited": len(classified),
        "buckets": dict(sorted(buckets.items())),
        "repository_verification_states": dict(sorted(states.items())),
        "timestamp_only_count": len(timestamp_only),
        "timestamp_only_ids": sorted(timestamp_only),
        "vocabulary": {
            "source_authority": "app.services.scholarship_evidence.SourceType / is_authoritative_source",
            "confidence": "app.services.verification_confidence.ConfidenceLevel",
            "state": "app.services.verification_confidence.VerificationState",
            "note": (
                "The four bucket names are the operational categories this review "
                "asked for. Each one is derived from the repository's existing "
                "authority, confidence and state values, so no second trust system "
                "is introduced and the public contract is unchanged."
            ),
        },
        "rule": (
            "Nothing is promoted without evidence attributable to the official "
            "source, and nothing is demoted merely because a quote field is empty "
            "when the repository holds a substantive finding another way. A "
            "record whose only record of checking is a timestamp and a process "
            "note is reported as such rather than counted as evidence."
        ),
        "records": classified,
    }
    (HERE / "evidence_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print("records audited            :", len(classified))
    print("buckets                    :", dict(sorted(buckets.items())))
    print("repository states          :", dict(sorted(states.items())))
    print("timestamp-only records     :", len(timestamp_only))
    print("wrote verification/evidence_audit.json")


if __name__ == "__main__":
    main()