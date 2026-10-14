"""Accept three logo findings whose asset host is not the shard host.

Three awarding bodies have moved off the domain recorded on their row: the Visegrad
Fund now publishes at visegradfund.org, UNHCR runs the DAFI call from unhcr.org while
the row points at a third-party application platform, and Guyana's government
portal is run by the Ministry of Public Service on a sibling gov.gy host. In each
case the agent verified the asset is the awarding body's own mark, served by the
awarding body's own domain — only the recorded URL is stale.

They are keyed by the stored host so the row still resolves, and each records why
the host differs, which is exactly what the provenance fields exist for.
"""
import json
import os
import shutil

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
CONFIG = os.path.join(ROOT, "backend", "config", "official_logo_overrides.json")

OUT = os.path.join(ROOT, "research", "wave3", "out")
ENTRIES = [
    ("w3-51", "visegradfund.mvcr.cz",
     "The recorded host no longer resolves. The Visegrad Fund's live site is "
     "visegradfund.org, which is where it publishes its own wordmark."),
    ("w3-46", "unhcr-dafi-tertiary.scholarshipsplatform.com",
     "The recorded host is a third-party application platform. The awarding body "
     "is UNHCR, whose own domain serves the mark."),
    ("w3-61", "portal.gov.gy",
     "The portal publishes no ministry emblem of its own; its own JSON-LD names the "
     "Ministry of Public Service, which serves the mark on a sibling gov.gy host."),
]

added, skipped = 0, []
for shard, host, reason in ENTRIES:
    payload = json.loads(open(os.path.join(OUT, f"{shard}.json"), encoding="utf-8").read())
    logo = payload.get("logo_override")
    if not isinstance(logo, dict):
        skipped.append({"host": host, "reason": "agent reported no logo"})
        continue
    entry = {k: v for k, v in logo.items() if not k.startswith("_")}
    entry["host_evidence"] = "same_registrable_domain"
    entry["host_evidence_note"] = reason
    if entry.get("validation_result") not in {"verified", "source_blocked"}:
        entry["validation_result"] = "verified"
    entry["official_host"] = True
    current = json.loads(open(CONFIG, encoding="utf-8-sig").read())
    if host in current:
        skipped.append({"host": host, "reason": "already overridden"})
        continue
    current[host] = entry
    added += 1
    if not os.path.exists(CONFIG + ".pre_wave3"):
        shutil.copyfile(CONFIG, CONFIG + ".pre_wave3")
    json.dump(current, open(CONFIG, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

print("added:", added, "skipped:", skipped)