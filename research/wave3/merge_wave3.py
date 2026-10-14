"""Merge the logo-hunt output into backend/config/official_logo_overrides.json.

Only host-keyed overrides are produced here, so the maintenance `logos` stage
does the writing: it validates the asset again, clears a stored photo and stamps
`image_kind=official_logo`. This script's job is to keep only entries whose asset
is genuinely served by the awarding body's own domain.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W3 = os.path.join(ROOT, "research", "wave3")
OUT = os.path.join(W3, "out")
MERGED = os.path.join(W3, "merged")
CONFIG = os.path.join(ROOT, "backend", "config")

spec = importlib.util.spec_from_file_location(
    "merge_wave", os.path.join(ROOT, "research", "wave1", "merge_wave.py")
)
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)

# Hosts whose page legitimately has no programme mark of its own, so the mark of
# a different body would misattribute the award.
SHARED_HOSTS = {"gov.uk", "govt.nz", "gov.tw", "gov.cn", "gov.au", "gov.sg"}


def main() -> int:
    parser = __import__("argparse").ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.makedirs(MERGED, exist_ok=True)

    shard_hosts = {}
    for name in sorted(os.listdir(os.path.join(W3, "shards"))):
        if not name.endswith(".json") or name == "MANIFEST.json":
            continue
        payload, _ = mw.load_json(os.path.join(W3, "shards", name))
        if payload:
            shard_hosts[payload["shard"]] = payload.get("host") or ""

    accepted, rejected, notes = {}, [], []
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".json")) if os.path.isdir(OUT) else []
    for name in files:
        payload, repair = mw.load_json(os.path.join(OUT, name))
        if repair:
            notes.append(f"{name}: {repair}")
        if not isinstance(payload, dict):
            continue
        shard = payload.get("shard") or name[:-5]
        expect = shard_hosts.get(shard)
        host = payload.get("host") or expect or ""
        logo = payload.get("logo_override")
        if not isinstance(logo, dict):
            notes.append(f"{shard}/{host}: logo_override is null — {str(payload.get('notes'))[:150]}")
            rejected.append({"shard": shard, "host": host, "reason": "no acceptable logo found"})
            continue
        problems = []
        mw.validate_logo(logo, host, problems, f"{shard}/{host}")
        if not mw.registrable(mw.host_of(logo.get("url"))):
            rejected.append({"shard": shard, "host": host, "reason": "logo url has no host"})
            continue
        if problems:
            for problem in problems:
                rejected.append({"shard": shard, "host": host, "reason": problem})
            continue
        if expect and mw.registrable(host) != mw.registrable(mw.host_of(logo["url"])):
            rejected.append({"shard": shard, "host": host,
                             "reason": f"logo host does not match the shard host {host}"})
            continue
        key = mw.registrable(host) or mw.registrable(mw.host_of(logo["url"]))
        if key in SHARED_HOSTS:
            rejected.append({"shard": shard, "host": host,
                             "reason": f"{key} is a shared government domain; a specific body's mark is required"})
            continue
        entry = {k: v for k, v in logo.items() if not k.startswith("_")}
        entry["alt_text"] = entry.get("alt_text") or host
        if key in accepted and accepted[key]["url"] != entry["url"]:
            rejected.append({"shard": shard, "host": host,
                             "reason": f"a different logo was already accepted for {key}"})
            continue
        accepted.setdefault(key, entry)

    json.dump(accepted, open(os.path.join(MERGED, "official_logo_overrides.append.json"), "w",
                             encoding="utf-8"), indent=2, ensure_ascii=False)
    json.dump({"files": len(files), "accepted_hosts": len(accepted),
               "rejected": rejected, "notes": notes},
              open(os.path.join(MERGED, "validation_report.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)

    print(f"shard files      : {len(files)}")
    print(f"accepted hosts   : {len(accepted)}")
    print(f"rejected         : {len(rejected)}")
    for row in rejected[:15]:
        print("   !", row["host"], "-", row["reason"][:120])

    if args.apply and accepted:
        path = os.path.join(CONFIG, "official_logo_overrides.json")
        if not os.path.exists(path + ".pre_wave3"):
            shutil.copyfile(path, path + ".pre_wave3")
        current = json.loads(open(path, encoding="utf-8-sig").read())
        added = 0
        for key, entry in accepted.items():
            if key in current:
                continue
            current[key] = entry
            added += 1
        json.dump(current, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"applied {added} logo hosts -> official_logo_overrides.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())