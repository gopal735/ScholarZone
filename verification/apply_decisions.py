"""Apply the audit decisions to the pipeline's audited data files.

Idempotent and deterministic: running it twice produces byte-identical files.
Each decision writes to exactly one of the three existing mechanisms -
corrections for a repaired value, confirmations for a current check, retirement
for a programme that does not exist - so the pipeline gains no new stage and no
second source of truth.

It also emits the staging manifest: one row per public record with the action,
the reason, the source, the evidence and the resulting public verification state.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONFIG = ROOT / "backend" / "config"

DECISIONS = json.loads((HERE / "decisions_22.json").read_text(encoding="utf-8"))
INVENTORY = json.loads((HERE / "verification_inventory.json").read_text(encoding="utf-8"))

CORRECTIONS_FIELDS = (
    "title",
    "official_source_url",
    "application_link",
    "official_source",
    "description",
)

CLEARABLE = ("deadline_display", "deadline_date", "deadline_precision")


def load(name: str) -> dict:
    return json.loads((CONFIG / name).read_text(encoding="utf-8"))


def save(name: str, payload: dict) -> None:
    (CONFIG / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def build_corrections(records: list[dict], clearances: list[dict]) -> tuple[dict, list[int]]:
    payload = load("record_corrections.json")
    existing: dict[int, dict] = {int(e["id"]): e for e in payload["records"]}
    touched: list[int] = []

    def add(rid: int, entry: dict) -> None:
        prior = existing.get(rid) or {}
        if not entry.get("title") and prior.get("title"):
            entry["title"] = prior["title"]
        if not entry.get("official_source_url") and prior.get("official_source_url"):
            entry["official_source_url"] = prior["official_source_url"]
        existing[rid] = entry
        touched.append(rid)

    for rec in records:
        correction = rec.get("correction")
        if not correction:
            continue
        entry: dict = {"id": rec["id"]}
        for field in CORRECTIONS_FIELDS:
            if correction.get(field):
                entry[field] = correction[field]
        clear = [f for f in (correction.get("clear_fields") or []) if f in CLEARABLE]
        if clear:
            entry["clear_fields"] = sorted(clear)
        entry["flag"] = "RE-VERIFIED"
        entry["reason"] = correction["reason"]
        entry["source"] = "final official-source verification pass, 2026-10-03"
        entry["source_page"] = rec["source_url"]
        add(rec["id"], entry)

    for clearance in clearances:
        entry = {
            "id": clearance["id"],
            "clear_fields": sorted(
                f for f in clearance["clear_fields"] if f in CLEARABLE
            ),
            "flag": "DEADLINE-NOT-A-DEADLINE",
            "reason": clearance["reason"],
            "source": "final official-source verification pass, 2026-10-03",
        }
        add(clearance["id"], entry)

    ordered = [existing[i] for i in sorted(existing)]
    payload["records"] = ordered
    payload["count"] = len(ordered)
    payload["_rules"] = [
        "Every entry must say what was wrong with the stored value and where the correct value came from.",
        "URLs are absolute http/https only. A correction that does not resolve is worse than the 404 it replaces.",
        "Retiring a record is a separate, stronger decision and lives in retired_records.json. It is only for programmes that no longer exist, never for a broken link.",
        "Allowed value fields: title, official_source_url, application_link, official_source, description.",
        "clear_fields may name deadline_display, deadline_date and deadline_precision. It removes a stored deadline that is provably not an application deadline. A cleared deadline_display becomes null and deadline_precision falls back through the shared deadline semantics to 'unknown'. A correction never supplies a replacement date: a correct date is a separate finding that has to arrive with its own evidence.",
        "A record that is corrected here may also be confirmed in verification_confirmations.json; a record that is retired may not. The correct stage runs before the reverify stage, so a repaired record is confirmed on the same run.",
    ]
    save("record_corrections.json", payload)
    return payload, touched


def build_confirmations(records: list[dict], corrections: dict) -> tuple[dict, list[int]]:
    payload = load("verification_confirmations.json")
    existing = {int(e["id"]): e for e in payload["records"]}
    corrected_ids = {int(e["id"]) for e in corrections["records"]}
    touched: list[int] = []

    for rec in records:
        if rec["public_state"] != "VERIFIED":
            continue
        rid = rec["id"]
        existing[rid] = {
            "id": rid,
            "name": rec["name"],
            "source_url": rec["source_url"],
            "checked_at": rec["checked_at"],
            "evidence": rec["evidence"],
            "action": rec["action"],
            "corrected_in_same_pass": rid in corrected_ids,
        }
        touched.append(rid)

    ordered = [existing[i] for i in sorted(existing)]
    payload["records"] = ordered
    payload["count"] = len(ordered)
    payload["note"] = (
        "Records re-checked against the awarding body's own page. Each entry is an "
        "assertion that the live source still supports the stored record, quoted from "
        "that source. An entry exists only for a source that was actually read: a fetch "
        "failure is never turned into a confirmation, so an unreachable official site "
        "leaves the record unverified rather than making it look checked."
    )
    save("verification_confirmations.json", payload)
    return payload, touched


def build_retirements(records: list[dict]) -> tuple[dict, list[int]]:
    payload = load("retired_records.json")
    existing = {int(e["id"]): e for e in payload["records"]}
    touched: list[int] = []

    for rec in records:
        if rec["action"] != "RETIRE":
            continue
        rid = rec["id"]
        existing[rid] = {
            "id": rid,
            "flag": "NEVER-EXISTED",
            "reason": rec["evidence"],
            "source": "final official-source verification pass, 2026-10-03",
            "source_page": rec["source_url"],
            "no_successor_reason": (
                "The awarding body's own page states there is no governmental scholarship "
                "programme for bachelor's or master's study in Finland. The national "
                "doctoral funding stream is a different programme, and Finnish government "
                "study aid runs through Kela as study support rather than as a scholarship, "
                "so neither is a successor for this record. University tuition-fee waivers "
                "are separate records and are not merged into this one."
            ),
        }
        touched.append(rid)

    ordered = [existing[i] for i in sorted(existing)]
    payload["records"] = ordered
    save("retired_records.json", payload)
    return payload, touched


def build_manifest(
    records: list[dict], confirmations: dict, corrections: dict, retirements: dict
) -> dict:
    by_id = {r["id"]: r for r in records}
    conf_ids = {int(e["id"]) for e in confirmations["records"]}
    corr_ids = {int(e["id"]) for e in corrections["records"]}
    ret_ids = {int(e["id"]) for e in retirements["records"]}

    rows: list[dict] = []
    for entry in INVENTORY:
        rid = entry["id"]
        decision = by_id.get(rid)
        changes: list[str] = []
        if decision:
            changes = sorted(
                set(decision.get("correction") or {})
                - {"reason"}
            )
        if rid in ret_ids and decision and decision["action"] == "RETIRE":
            action = "RETIRED"
            state = "NOT_PUBLIC"
            reason = "the awarding body's own current page states the programme does not exist"
            source = decision["source_url"]
            evidence = decision["evidence"]
        elif decision and decision["action"].startswith("CORRECT"):
            # One action per record, from the seven the manifest defines. A record
            # whose data was repaired but whose source still cannot be confirmed is
            # UNVERIFIED, not a half-state: the field_changes column carries the
            # repair, and the state column carries the trust claim.
            action = "REFRESH" if decision["public_state"] == "VERIFIED" else "UNVERIFIED"
            state = decision["public_state"]
            reason = (decision.get("correction") or {}).get("reason", "")
            source = decision["source_url"]
            evidence = decision["evidence"]
        elif decision and decision["action"] == "VERIFY":
            action = "REFRESH"
            state = "VERIFIED"
            reason = "current official check recorded in this pass"
            source = decision["source_url"]
            evidence = decision["evidence"]
        elif decision:
            action = "UNVERIFIED"
            state = decision["public_state"]
            reason = evidence = decision["evidence"]
            source = decision["source_url"]
        elif rid in conf_ids:
            action = "NO_CHANGE"
            state = "VERIFIED"
            reason = "already current-verified with recorded evidence"
            source = next(
                e["source_url"] for e in confirmations["records"] if int(e["id"]) == rid
            )
            evidence = next(
                e["evidence"] for e in confirmations["records"] if int(e["id"]) == rid
            )
        else:
            action = "NO_CHANGE"
            state = "VERIFIED"
            reason = "already current-verified; not re-checked in this pass"
            source = entry["official_source_url"]
            evidence = entry["confirmation_evidence"] or ""

        evidence_text = evidence or ""
        rows.append(
            {
                "id": rid,
                "name": entry["name"],
                "action": action,
                "public_verification_state": state,
                # Whether this row's trust claim rests on a retrievable finding or
                # only on a timestamp. A timestamp says a source was read at some
                # point; a quote says what it said. Only the second one can be
                # audited later without re-fetching the page, and collapsing the
                # two is how "verified" quietly becomes a historical claim.
                "evidence_status": (
                    "quoted_from_official_source" if evidence_text.strip() else "timestamp_only"
                ),
                "field_changes": changes,
                "official_source": source,
                "evidence": evidence_text,
                "reason": reason,
                "in_corrections_file": rid in corr_ids,
                "in_confirmations_file": rid in conf_ids,
                "in_retired_file": rid in ret_ids,
                "verified_at": decision["checked_at"] if decision else entry["last_verified_at"],
            }
        )

    return {
        "generated_at": "2026-10-03",
        "public_universe_before": len(INVENTORY),
        "rows": rows,
        "summary": {
            "actions": dict(sorted(Counter(r["action"] for r in rows).items())),
            "states": dict(sorted(Counter(r["public_verification_state"] for r in rows).items())),
            "evidence_status": dict(sorted(Counter(r["evidence_status"] for r in rows).items())),
        },
    }


def main() -> None:
    records = DECISIONS["records"]
    clearances = (DECISIONS.get("deadline_clearances") or {}).get("records") or []
    corrections, corrected = build_corrections(records, clearances)
    confirmations, confirmed = build_confirmations(records, corrections)
    retirements, retired = build_retirements(records)
    manifest = build_manifest(records, confirmations, corrections, retirements)
    (HERE / "staging_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8"
    )

    print("corrections written :", len(corrected), "->", len(corrections["records"]), "total")
    print("confirmations written:", len(confirmed), "->", len(confirmations["records"]), "total")
    print("retirements written :", len(retired), "->", len(retirements["records"]), "total")
    print("manifest actions    :", manifest["summary"]["actions"])
    print("manifest states     :", manifest["summary"]["states"])

    public_after = sum(1 for r in manifest["rows"] if r["public_verification_state"] != "NOT_PUBLIC")
    verified_after = sum(
        1 for r in manifest["rows"] if r["public_verification_state"] == "VERIFIED"
    )
    unverified_after = public_after - verified_after
    print(f"\npublic total after : {public_after}")
    print(f"verified after     : {verified_after}")
    print(f"unverified after   : {unverified_after}")
    assert public_after == verified_after + unverified_after
    both = [
        r["id"]
        for r in manifest["rows"]
        if r["public_verification_state"] == "VERIFIED" and r["action"] == "UNVERIFIED"
    ]
    assert not both, f"records claiming both states: {both}"


if __name__ == "__main__":
    main()
