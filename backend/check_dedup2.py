import json, glob, hashlib
from pathlib import Path
from difflib import SequenceMatcher
import sys

def sha256_str(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def similarity(a, b):
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

candidates = []
for f in sorted(Path("research_output_normalized").glob("normalized_discovered_candidates_*.json")):
    with open(f, encoding="utf-8") as fh:
        candidates.extend(json.load(fh))

seen_urls = set()
seen_title_country = set()
removed = []
for cand in candidates:
    url = (cand.get("official_source_url") or "").lower().strip()
    title = (cand.get("title") or "").lower().strip()
    country = (cand.get("country") or "").lower().strip()
    tc = (country, title)
    if url and url in seen_urls:
        removed.append(("url-duplicate", cand))
        continue
    if tc in seen_title_country:
        removed.append(("title-country-duplicate", cand))
        continue
    seen_urls.add(url)
    seen_title_country.add(tc)

print("Removed candidates:", len(removed))
for reason, cand in removed:
    title = cand.get("title", "")
    country = cand.get("country", "")
    url = cand.get("official_source_url", "")
    deadline = cand.get("deadline_date")
    status = cand.get("status")
    print(f"{reason}\t{title}\t{country}\t{url}\t{deadline}\t{status}")
