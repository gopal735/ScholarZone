"""Patch the 4 colliding profile-URL clusters with person-specific official URLs.

Verified today by fetching the official pages directly:
- DGIST: each professor has an on-page anchor identifying their block.
- KINGS: each professor has an official person page (/professor/index.do?pId=...).
- InLife / FNU: no person-specific page exists, so only the first professor per
  shared page is kept; the others are dropped rather than misattributed.
"""

import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")

PATCH_URLS = {
    # (batch file, canonical name) -> person-specific official URL
    ("batch_081.json", "Joongoo Kang"): "https://www.dgist.ac.kr/iadm/sub01_01_01_01.do#info01",
    ("batch_081.json", "Sangil Kwon"): "https://www.dgist.ac.kr/iadm/sub01_01_01_01.do#info02",
    ("batch_081.json", "Soyeun Kim"): "https://www.dgist.ac.kr/iadm/sub01_01_01_01.do#info25",
    ("batch_085.json", "Yoon Joo-il"): "https://kings.ac.kr/professor/index.do?pId=jiyoon",
    ("batch_085.json", "Jung Woo-yong"): "https://kings.ac.kr/professor/index.do?pId=wooyong",
}

DROP_NAMES = {
    ("batch_044.json", 354): {"Christine Menager"},
    ("batch_075.json", 610): {"Deeksha Krishna", "Ravinesh Ram"},
}

patched = 0
dropped = 0
for path in sorted(glob.glob(os.path.join(OUT, "batch_*.json"))):
    name = os.path.basename(path)
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        continue
    changed = False
    for obj in data:
        sid = obj.get("scholarship_id")
        profs = obj.get("professors") or []
        if not profs:
            continue
        keep = []
        for p in profs:
            key = (name, p.get("canonical_name"))
            if key in PATCH_URLS:
                p["official_profile_url"] = PATCH_URLS[key]
                patched += 1
                changed = True
            if (name, sid) in DROP_NAMES and p.get("canonical_name") in DROP_NAMES[(name, sid)]:
                dropped += 1
                changed = True
                continue
            keep.append(p)
        if changed:
            obj["professors"] = keep
            if obj.get("outcome") == "verified_supervisors" and keep:
                obj["verified_supervisor_count"] = None  # informational only
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=1)
        print(f"patched {name}")

print(f"patched URLs: {patched}, dropped professors: {dropped}")
