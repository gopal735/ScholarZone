import glob
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

by_url = defaultdict(list)
for path in sorted(glob.glob(os.path.join(OUT, "batch_*.json"))):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        continue
    for obj in data:
        for p in obj.get("professors") or []:
            by_url[p.get("official_profile_url")].append(
                (obj.get("scholarship_id"), p.get("canonical_name"), p.get("title"),
                 p.get("institution_name"), p.get("official_email"),
                 p.get("evidence_source_url"), os.path.basename(path))
            )

print("=== colliding profile URLs ===")
for url, people in sorted(by_url.items()):
    names = {p[1] for p in people}
    if len(names) > 1:
        print(f"\nURL: {url}")
        for sid, name, title, inst, email, ev, batch in people:
            print(f"  sch={sid} | {name} | {title} | {inst} | email={email} | batch={batch}")
            print(f"      evidence: {ev}")
