import json
import urllib.request

PROFILE = {
    "highest_qualification": "BACHELOR",
    "intended_degree_level": "MASTER",
    "intended_field": "engineering",
    "preferred_countries": ["Germany", "Netherlands"],
    "funding_requirement": "FULL_FUNDING",
    "study_mode": "FULL_TIME",
    "limit": 200,
    "include_ineligible": True,
}

req = urllib.request.Request(
    "https://scholarzone-fwzj.vercel.app/api/scholarships/match",
    data=json.dumps(PROFILE).encode(),
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=180) as resp:
    match = json.loads(resp.read().decode())

results = match["results"]
total = match["total_candidates"]

# The ranking value is `fit_score`. There is no `score` key on a result, so a
# scored/not-scored count written against `score` reads zero for every row and
# silently "reconciles" - which is how a broken measurement passes as a green
# one. The field name is asserted here so that cannot recur.
assert "fit_score" in results[0], f"unexpected result shape: {sorted(results[0])}"
assert "score" not in results[0], "a bare `score` key exists; re-check which one is authoritative"

scored = sum(1 for r in results if float(r.get("fit_score") or 0) > 0)
not_scored = len(results) - scored
scores = [float(r.get("fit_score") or 0) for r in results]

print("Phase 9 reconciliation, single production request")
print("-" * 62)
partition = match["eligible_count"] + match["needs_verification_count"] + match["ineligible_count"]
print(f"  eligible {match['eligible_count']} + needs_verification "
      f"{match['needs_verification_count']} + ineligible {match['ineligible_count']} = {partition}")
print(f"  equals total_candidates {total}: {partition == total}")

print(f"  fit_score range: {min(scores):.1f} .. {max(scores):.1f}")
print(f"  scored {scored} + not_scored {not_scored} = {scored + not_scored}")
print(f"  equals results returned {len(results)}: {scored + not_scored == len(results)}")
print(f"  every result carries a fit_score: {all('fit_score' in r for r in results)}")

labels: dict = {}
for row in results:
    key = str(row.get("fit_label"))
    labels[key] = labels.get(key, 0) + 1
print(f"  fit labels across results: {labels} sum {sum(labels.values())}")
print(f"  fit labels partition the results: {sum(labels.values()) == len(results)}")
print(f"  results with fit_score > 0 all carry a fit label: "
      f"{all(r.get('fit_label') for r in results if float(r.get('fit_score') or 0) > 0)}")

states: dict = {}
for row in results:
    key = str(row.get("eligibility"))
    states[key] = states.get(key, 0) + 1
print(f"  eligibility states in results: {states} sum {sum(states.values())}")
print(f"  eligibility partition == results: {sum(states.values()) == len(results)}")

facets = match.get("facets") or {}
print(f"  facet count_basis: {facets.get('count_basis')}")


def facet(name):
    """Facets are keyed by band but may arrive as a list of pairs."""
    block = facets.get(name)
    if isinstance(block, dict):
        return block, sum(v for v in block.values() if isinstance(v, int))
    if isinstance(block, list):
        counts = {}
        for entry in block:
            if isinstance(entry, dict):
                key = entry.get("key") or entry.get("band") or entry.get("value")
                value = entry.get("count") or entry.get("value_count") or 0
                counts[key] = value
            elif isinstance(entry, (list, tuple)) and len(entry) == 2:
                counts[entry[0]] = entry[1]
        return counts, sum(v for v in counts.values() if isinstance(v, int))
    return None, None


for name in ("fit_bands", "confidence_bands", "eligibility_states", "funding_states", "degree_levels"):
    counts, total_count = facet(name)
    if counts:
        agrees = "" if total_count is None else f" sum={total_count}"
        print(f"  facet {name:22s}: {counts}{agrees}")

print(f"  strong_match_count: {match['strong_match_count']}")
print(f"  distinct ids: {len({r['scholarship_id'] for r in results})} of {len(results)}")
print("-" * 62)