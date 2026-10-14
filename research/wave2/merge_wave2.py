"""Merge + validate the 50-agent wave-2 discovery output into insert-ready records.

Reads   research/wave2/out/w2-NN.json
Writes  research/wave2/merged/new_scholarships.append.json   (do_add() shape)
  --apply  appends it into backend/config/new_scholarships.json

Wave 2 produces NEW rows, so there is no target_id and no legacy-title match.
Dedup is therefore done here: against the live database (URL, application link,
normalised title, and same-host near-duplicate) and inside the batch itself.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sqlite3
import sys
from difflib import SequenceMatcher

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
W2 = os.path.join(ROOT, "research", "wave2")
OUT = os.path.join(W2, "out")
MERGED = os.path.join(W2, "merged")
CONFIG = os.path.join(ROOT, "backend", "config")
DB = os.path.join(ROOT, "backend", "scholarzone.db")

spec = importlib.util.spec_from_file_location(
    "merge_wave", os.path.join(ROOT, "research", "wave1", "merge_wave.py")
)
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)

STOP = {"the", "a", "an", "for", "of", "and", "in", "at", "on", "to", "programme", "program",
        "scholarship", "scholarships", "award", "awards", "grant", "grants", "fund", "funding"}


def norm_title(text: str) -> str:
    text = re.sub(r"\(.*?\)", " ", text or "")
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    return " ".join(w for w in text.split() if w and w not in STOP)


def tokens(text: str) -> set:
    return set(norm_title(text).split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, norm_title(a), norm_title(b)).ratio()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.makedirs(MERGED, exist_ok=True)

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    db_rows = conn.execute("SELECT id,title,country,official_source_url,application_link,status FROM scholarships").fetchall()
    db_urls = {mw.host_of(r["official_source_url"]) and (r["official_source_url"] or "").rstrip("/").lower() for r in db_rows}
    db_urls.discard("")
    db_links = {(r["application_link"] or "").rstrip("/").lower() for r in db_rows if r["application_link"]}
    db_titles = {norm_title(r["title"]): r["id"] for r in db_rows}
    db_by_host = {}
    for r in db_rows:
        h = mw.registrable(mw.host_of(r["official_source_url"]))
        if h:
            db_by_host.setdefault(h, []).append(r)

    problems, staged, rejected = [], [], []
    files = sorted(f for f in os.listdir(OUT) if f.endswith(".json")) if os.path.isdir(OUT) else []
    agent_rejected = []

    for name in files:
        payload, repair = mw.load_json(os.path.join(OUT, name))
        if repair:
            problems.append(f"{name}: {repair}")
        if payload is None:
            continue
        if isinstance(payload, list):
            # An agent that wrote a bare array instead of the wrapper object.
            payload = {"agent_id": name[:-5], "records": payload}
        agent = payload.get("agent_id") or name[:-5]
        agent_rejected.extend(payload.get("rejected") or [])
        for rec in payload.get("records") or []:
            where = f"{agent}/{rec.get('new_scholarship', {}).get('name', '?') if isinstance(rec.get('new_scholarship'), dict) else agent}"
            flat, logo = mw.validate_record(rec, None, problems, where)
            if flat is None:
                rejected.append({"name": where, "reason": "failed validation", "agent": agent})
                continue

            url = (flat.get("official_source_url") or "").rstrip("/").lower()
            title = flat.get("name") or ""
            key = norm_title(title)
            host = mw.registrable(mw.host_of(url))

            if url in db_urls or url in db_links:
                rejected.append({"name": title, "reason": "official_source_url already in database", "agent": agent})
                continue
            if key in db_titles:
                rejected.append({"name": title, "reason": f"same award as id={db_titles[key]}", "agent": agent})
                continue
            near = None
            for row in db_by_host.get(host, []):
                if similarity(title, row["title"]) >= 0.82:
                    near = row
                    break
            if near:
                rejected.append({"name": title, "reason": f"near-duplicate of id={near['id']} on same host", "agent": agent})
                continue

            flat["_logo_host"] = mw.registrable(mw.host_of(logo["url"])) if logo else None
            flat["_agent"] = agent
            staged.append((flat, logo))

    # in-batch dedup
    seen_url, seen_title, unique = {}, {}, []
    for flat, logo in staged:
        url = (flat.get("official_source_url") or "").rstrip("/").lower()
        key = norm_title(flat.get("name") or "")
        if url in seen_url or key in seen_title:
            rejected.append({"name": flat.get("name"), "reason": "duplicate inside the batch", "agent": flat.get("_agent")})
            continue
        seen_url[url] = flat
        seen_title[key] = flat
        unique.append(flat)

    logos = {}
    for flat, logo in staged:
        if logo:
            host = mw.registrable(mw.host_of(logo["url"]))
            logos.setdefault(host, {k: v for k, v in logo.items() if not k.startswith("_")})

    json.dump({
        "note": "Staged wave-2 insertions. Append records[] into backend/config/new_scholarships.json "
                "and run the maintenance `add` stage. Records whose official_source_url or name already "
                "exist in the database are upserted rather than duplicated.",
        "count": len(unique),
        "records": unique,
    }, open(os.path.join(MERGED, "new_scholarships.append.json"), "w", encoding="utf-8"),
        indent=2, ensure_ascii=False)
    json.dump(logos, open(os.path.join(MERGED, "official_logo_overrides.append.json"), "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    json.dump({
        "agent_output_files": len(files),
        "staged_inserts": len(unique),
        "logo_hosts": len(logos),
        "rejected": rejected,
        "agent_reported_rejections": agent_rejected,
        "validation_problems": problems,
    }, open(os.path.join(MERGED, "validation_report.json"), "w", encoding="utf-8"),
        indent=2, ensure_ascii=False)

    print(f"agent output files : {len(files)}")
    print(f"staged inserts     : {len(unique)}")
    print(f"logo hosts         : {len(logos)}")
    print(f"rejected           : {len(rejected)}")
    print(f"problems           : {len(problems)}")
    for p in problems[:25]:
        print("   !", p)

    if args.apply:
        if not unique:
            print("\n--apply: nothing staged, config untouched.")
            return 0
        path = os.path.join(CONFIG, "new_scholarships.json")
        import shutil
        if not os.path.exists(path + ".pre_wave2"):
            shutil.copyfile(path, path + ".pre_wave2")
        current = json.loads(open(path, encoding="utf-8-sig").read())
        records = current.get("records") if isinstance(current, dict) else current
        # Append must be idempotent: this script is re-run as each shard lands,
        # and a second copy of the same record would re-upsert the same row.
        seen = {(r.get("official_source_url") or "").rstrip("/").lower()
                for r in records if isinstance(r, dict)}
        fresh = [r for r in unique
                 if (r.get("official_source_url") or "").rstrip("/").lower() not in seen]
        merged = {**current} if isinstance(current, dict) else {"records": records}
        merged["records"] = list(records) + fresh
        merged["count"] = len(merged["records"])
        json.dump(merged, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"applied {len(fresh):4d} records -> new_scholarships.json (backup kept)")

        logo_path = os.path.join(CONFIG, "official_logo_overrides.json")
        if not os.path.exists(logo_path + ".pre_wave2"):
            shutil.copyfile(logo_path, logo_path + ".pre_wave2")
        cur = json.loads(open(logo_path, encoding="utf-8-sig").read())
        added = 0
        for host, entry in logos.items():
            if host in cur:
                continue
            cur[host] = entry
            added += 1
        json.dump(cur, open(logo_path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"applied {added:4d} logo hosts -> official_logo_overrides.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())