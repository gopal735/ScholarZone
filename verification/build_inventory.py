"""Authoritative verification inventory over the live public universe.

One row per public record. The state is derived from the authoritative
verification status and its evidence, never from the legacy `verified` boolean.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
LIST = json.loads((HERE / "live_catalogue.json").read_text(encoding="utf-8"))
RAW = {int(k): v for k, v in json.loads((HERE / "live_raw.json").read_text(encoding="utf-8")).items()}
CONF = json.loads(
    ((HERE.parent / "backend") / "config" / "verification_confirmations.json").read_text(
        encoding="utf-8"
    )
)
CONF_BY_ID = {int(e["id"]): e for e in CONF["records"] if e.get("id") is not None}
CORR = json.loads(
    ((HERE.parent / "backend") / "config" / "record_corrections.json").read_text(encoding="utf-8")
)
CORR_BY_ID = {int(e["id"]): e for e in CORR["records"] if e.get("id") is not None}
RETIRED = json.loads(
    ((HERE.parent / "backend") / "config" / "retired_records.json").read_text(encoding="utf-8")
)
RETIRED_BY_ID = {int(e["id"]): e for e in RETIRED["records"] if e.get("id") is not None}

#: Public-facing state vocabulary. Maps the stored verification_status onto the
#: two states the product is allowed to claim.
PUBLIC_STATE = {
    "active": "VERIFIED",
    "needs_review": "CONFIRM_WITH_PROVIDER",
    "quarantined": "NOT_PUBLIC",
}


def public_state(row: dict) -> str:
    status = row.get("verification_status")
    if row.get("is_archived"):
        return "NOT_PUBLIC"
    return PUBLIC_STATE.get(status, "CONFIRM_WITH_PROVIDER")


def build() -> list[dict]:
    out: list[dict] = []
    for item in LIST["items"]:
        sid = item["id"]
        raw = RAW.get(sid, {})
        conf = CONF_BY_ID.get(sid)
        corr = CORR_BY_ID.get(sid)
        ret = RETIRED_BY_ID.get(sid)
        pv = raw.get("programme_verification") or {}
        out.append(
            {
                "id": sid,
                "name": item.get("name") or item.get("title"),
                "official_source": raw.get("official_source"),
                "official_source_url": raw.get("official_source_url"),
                "catalogue_url": raw.get("catalogue_url"),
                "application_link": raw.get("application_link"),
                "stored_verification_status": raw.get("verification_status"),
                "public_state": public_state(raw),
                "legacy_verified_boolean": raw.get("is_verified"),
                "last_verified_at": raw.get("last_verified_at"),
                "verified_by": raw.get("verified_by"),
                "status": raw.get("status"),
                "image_kind": raw.get("image_kind"),
                "image_evaluation_status": raw.get("image_evaluation_status"),
                "in_confirmation_file": bool(conf),
                "confirmation_evidence": (conf or {}).get("evidence"),
                "confirmation_checked_at": (conf or {}).get("checked_at"),
                "in_correction_file": bool(corr),
                "correction_reason": (corr or {}).get("reason"),
                "retired": bool(ret),
                "retired_flag": (ret or {}).get("flag"),
                "verification_notes": raw.get("verification_notes"),
                "cycle_verified": pv.get("cycle_verified"),
                "verification_confidence": pv.get("verification_confidence"),
            }
        )
    out.sort(key=lambda r: r["id"])
    return out


def main() -> None:
    inv = build()
    (HERE / "verification_inventory.json").write_text(
        json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print("public total:", len(inv))
    print("public_state:", dict(Counter(r["public_state"] for r in inv)))
    print("stored status:", dict(Counter(r["stored_verification_status"] for r in inv)))
    print("legacy boolean:", dict(Counter(r["legacy_verified_boolean"] for r in inv)))
    print(
        "confirmed-with-evidence:",
        sum(1 for r in inv if r["in_confirmation_file"] and r["confirmation_evidence"]),
    )
    print(
        "VERIFIED but no evidence in confirmation file:",
        sum(
            1
            for r in inv
            if r["public_state"] == "VERIFIED" and not r["confirmation_evidence"]
        ),
    )
    print("has official_source_url:", sum(1 for r in inv if r["official_source_url"]))
    print("no official_source_url:", [r["id"] for r in inv if not r["official_source_url"]])
    print("in corrections file:", sum(1 for r in inv if r["in_correction_file"]))
    print("in retired file:", sum(1 for r in inv if r["retired"]))

    print("\n== the 22 unresolved ==")
    for r in inv:
        if r["public_state"] != "VERIFIED":
            print(
                f"{r['id']:>4} {r['official_source'] or '-':<28} "
                f"{(r['official_source_url'] or '(none)')[:95]}"
            )
            print(f"      name: {r['name']}")
            note = (r["verification_notes"] or "").replace("\n", " | ")
            print(f"      notes: {note[:300]}")


if __name__ == "__main__":
    main()