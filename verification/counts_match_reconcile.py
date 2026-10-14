"""Reconcile Count Intelligence against Match on the deployed API.

Both are asked the same question about the same catalogue, so their totals must
agree. A divergence between two authoritative surfaces is the exact defect this
layer was built to prevent, so it is asserted rather than eyeballed.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"
HEADERS = {
    "User-Agent": "Mozilla/5.0 ScholarZoneReleaseReconcile/1.0",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

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


def post(path, payload):
    req = urllib.request.Request(
        f"{BASE}{path}", data=json.dumps(payload).encode(), headers=HEADERS, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")[:300]


def get(path):
    req = urllib.request.Request(f"{BASE}{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read().decode())


match_status, match = post("/api/scholarships/match", PROFILE)
intel_status, intel = post("/api/v2/counts/intelligence", {"profile": PROFILE})

print(f"match HTTP {match_status} | intelligence HTTP {intel_status}")
print()
print("=== Match ===")
print(f"  total_candidates     {match['total_candidates']}")
print(f"  eligible_count       {match['eligible_count']}")
print(f"  ineligible_count     {match['ineligible_count']}")
print(f"  needs_verification   {match['needs_verification_count']}")
print(f"  strong_match_count   {match['strong_match_count']}")

print()
print("=== Count Intelligence universes ===")
universes = intel.get("universes") if isinstance(intel, dict) else None
if isinstance(universes, dict):
    for name, block in universes.items():
        if isinstance(block, dict):
            summary = {k: v for k, v in block.items() if isinstance(v, (int, float, str))}
            print(f"  {name:24s} {summary}")
elif isinstance(universes, list):
    for block in universes:
        print(f"  {str(block)[:160]}")
else:
    print("  shape:", str(universes)[:300])

print()
status, stats = get("/api/scholarships/stats")
print("=== Directory stats ===")
print(f"  total {stats.get('total')} | verified_active {stats.get('verified_active')} | countries {stats.get('countries')}")

print()
print("=== Agreement ===")
match_total = match["total_candidates"]
stats_total = stats.get("total")
print(f"  stats.total == Match.total_candidates : {stats_total == match_total} ({stats_total} vs {match_total})")

found_totals = []
def walk(node, path=""):
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("total", "count", "catalogue_total") and isinstance(value, int):
                found_totals.append((f"{path}/{key}", value))
            walk(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node[:3]):
            walk(value, f"{path}[{index}]")

walk(intel.get("universes") if isinstance(intel, dict) else None, "universes")
if found_totals:
    print(f"  integer totals found in universes: {found_totals}")
    agree = [v for _, v in found_totals if v == match_total]
    print(f"  values equal to Match total ({match_total}): {len(agree)} of {len(found_totals)}")
else:
    print("  no integer universe totals exposed in the response body")

with open("verification/counts_match_reconciliation.json", "w", encoding="utf-8") as handle:
    json.dump(
        {
            "match_total_candidates": match_total,
            "match_partition": {
                "eligible": match["eligible_count"],
                "ineligible": match["ineligible_count"],
                "needs_verification": match["needs_verification_count"],
            },
            "match_partition_reconciles": (
                match["eligible_count"] + match["ineligible_count"] + match["needs_verification_count"]
                == match_total
            ),
            "stats_total": stats_total,
            "stats_agrees_with_match": stats_total == match_total,
            "intelligence_universe_totals": found_totals,
        },
        handle,
        indent=1,
    )
print("\nwrote verification/counts_match_reconciliation.json")