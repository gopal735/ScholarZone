"""Split the under-covered wave-1 shards into five-record halves.

A ten-record shard is one long unit of work, and an upstream idle timeout costs
the whole thing. Five records is small enough to finish, and the halves write to
different files so one timeout cannot take out the other.
"""
import importlib.util
import json
import os

ROOT = r"C:\Users\GopaL\Desktop\Projects folder\ScholarZone"
spec = importlib.util.spec_from_file_location(
    "merge_wave", os.path.join(ROOT, "research", "wave1", "merge_wave.py"))
mw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mw)

GAPS = ["w1-01", "w1-03", "w1-05", "w1-09", "w1-14", "w1-15", "w1-17",
        "w1-19", "w1-26", "w1-32", "w1-38", "w1-42", "w1-47"]
OUT = os.path.join(ROOT, "research", "wave1", "shards_split")
os.makedirs(OUT, exist_ok=True)

CHUNK = 5
manifest = []
for name in GAPS:
    payload, _ = mw.load_json(os.path.join(ROOT, "research", "wave1", "shards", f"{name}.json"))
    records = payload["records"]
    # Records an earlier agent already confirmed are dropped, so the split only
    # carries work that is genuinely still outstanding.
    existing, _ = mw.load_json(os.path.join(ROOT, "research", "wave1", "out", f"{name}.json"))
    done = set()
    for row in (existing or {}).get("records") or []:
        if str(row.get("outcome")) in ("refreshed", "verified_no_change"):
            done.add(row.get("target_id"))
    todo = [r for r in records if r["target_id"] not in done]
    for i in range(0, len(todo), CHUNK):
        part = todo[i:i + CHUNK]
        suffix = "a" + (str(i // CHUNK) if i else "")
        shard = f"{name}{suffix}"
        out = {
            "shard": shard,
            "agent_id": f"{name}{suffix}".replace("-", "_"),
            "today": "2026-10-04",
            "parent_shard": name,
            "record_count": len(part),
            "records": part,
        }
        json.dump(out, open(os.path.join(OUT, f"{shard}.json"), "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
        manifest.append({"shard": shard, "file": f"research/wave1/shards_split/{shard}.json",
                         "records": len(part), "ids": [r["target_id"] for r in part]})

json.dump({"shards": len(manifest), "items": manifest},
          open(os.path.join(OUT, "MANIFEST.json"), "w", encoding="utf-8"), indent=2)
print("split shards:", len(manifest), "records:", sum(m["records"] for m in manifest))
for m in manifest:
    print("  ", m["shard"], m["records"], m["ids"])