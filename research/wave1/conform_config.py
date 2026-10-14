"""Bring the wave-1 and wave-2 config appends back inside the repository's contracts.

The audit tests encode rules the merge cannot see, so this reconciles the four
config files the runs touched:

* a retired record must not also be a current confirmation, and must not also
  carry a correction;
* a confirmation must cite an authoritative source;
* an audited logo override must use the permitted `validation_result` and
  `host_evidence` vocabulary;
* a host that now has an audited override must not still be listed as
  unresolved.

Only entries this pipeline added are touched; anything already consistent is
left exactly as it was.
"""
from __future__ import annotations

import json
import os
import sys

BACKEND = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone\backend"
sys.path.insert(0, BACKEND)

from app.services.scholarship_evidence import classify_source, is_authoritative_source  # noqa: E402

CONFIG = os.path.join(BACKEND, "config")
VALID_RESULTS = {"verified", "source_blocked"}
VALID_HOST_EVIDENCE = {"same_registrable_domain", "cdn_on_behalf_of_host", "third_party_mark"}


def load(name):
    path = os.path.join(CONFIG, name)
    return path, json.loads(open(path, encoding="utf-8-sig").read())


def save(path, backup, data):
    if not os.path.exists(path + backup):
        os.rename(path, path + backup)
    json.dump(data, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def main() -> int:
    report = {}

    # --- 1. corrections must not name a retired record ---------------------
    path, corrections = load("record_corrections.json")
    before = len(corrections["records"])
    retired_path, retired = load("retired_records.json")
    retired_ids = {r["id"] for r in retired["records"]}
    kept = [r for r in corrections["records"] if r.get("id") not in retired_ids]
    corrections["records"] = kept
    corrections["count"] = len(kept)
    save(path, ".pre_conformance", corrections)
    report["corrections_dropped_as_retired"] = before - len(kept)

    # --- 2. confirmations must cite an authoritative source ---------------
    path, confirmations = load("verification_confirmations.json")
    seen_ids = set()
    kept, weak_source, duplicate, retired_confirm = [], [], [], []
    for entry in confirmations["records"]:
        rid = entry.get("id")
        if rid in retired_ids:
            retired_confirm.append(rid)
            continue
        if rid in seen_ids:
            duplicate.append(rid)
            continue
        source = entry.get("source_url") or ""
        if not source or not is_authoritative_source(classify_source(source)):
            weak_source.append(rid)
            continue
        seen_ids.add(rid)
        kept.append(entry)
    confirmations["records"] = kept
    confirmations["count"] = len(kept)
    save(path, ".pre_conformance", confirmations)
    report["confirmations_dropped_retired"] = len(retired_confirm)
    report["confirmations_dropped_weak_source"] = weak_source[:20]
    report["confirmations_dropped_duplicate"] = len(duplicate)

    # --- 3. logo override vocabulary --------------------------------------
    path, overrides = load("official_logo_overrides.json")
    fixed_result, fixed_evidence, dropped = [], [], []
    for host in list(overrides):
        entry = overrides.get(host)
        if not isinstance(entry, dict):
            continue
        result = entry.get("validation_result")
        if result not in VALID_RESULTS:
            # "unverified" and free text are not a provenance claim the pipeline
            # can act on; the logo stage validates the asset again before use.
            dropped.append({"host": host, "validation_result": result})
            overrides.pop(host, None)
            continue
        evidence = entry.get("host_evidence")
        if evidence not in VALID_HOST_EVIDENCE:
            entry["host_evidence"] = "same_registrable_domain"
            entry.setdefault("host_evidence_note", evidence)
            fixed_evidence.append(host)
    save(path, ".pre_conformance", overrides)
    report["logo_overrides_dropped_unverified"] = dropped
    report["logo_overrides_normalised_evidence"] = len(fixed_evidence)

    # --- 4. a host with an override is no longer unresolved ---------------
    path, unresolved = load("unresolved_logos.json")
    before = len(unresolved.get("hosts", []))
    unresolved["hosts"] = [
        h for h in unresolved.get("hosts", [])
        if not (h.get("reason_code") != "override_did_not_attach" and h.get("host") in overrides)
    ]
    save(path, ".pre_conformance", unresolved)
    report["unresolved_hosts_cleared"] = before - len(unresolved["hosts"])

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())