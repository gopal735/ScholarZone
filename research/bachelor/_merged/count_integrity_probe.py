import json
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"


def post(path, payload, timeout=120):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


def get(path, timeout=120):
    with urllib.request.urlopen(urllib.request.Request(
            BASE + path, headers={"Accept": "application/json"}), timeout=timeout) as r:
        return r.status, json.loads(r.read().decode())


PROFILE = {"citizenship": "India", "highest_qualification": "Bachelor's degree",
           "intended_degree_level": "MASTER", "intended_field": "Engineering",
           "funding_requirement": "FULL_FUNDING",
           "preferred_countries": ["United States", "United Kingdom", "Canada"]}

st, intel = post("/api/v2/counts/intelligence",
                 {"profile": PROFILE,
                  "capabilities": ["summary", "facets", "integrity", "relationships"]})

print("HTTP", st)
integ = intel.get("integrity", {})
print("integrity.status :", integ.get("status"))
print()
print("=" * 74)
print("EVERY RECONCILIATION CHECK, INDEPENDENTLY")
print("=" * 74)
recs = integ.get("reconciliations") or []
if isinstance(recs, dict):
    recs = [{"name": k, **v} for k, v in recs.items()]
for r in recs:
    if not isinstance(r, dict):
        continue
    holds = r.get("holds")
    mark = "PASS" if holds else ("FAIL" if holds is False else "?")
    print(f"\n  [{mark}] {r.get('name')}")
    for k, v in r.items():
        if k == "name":
            continue
        print(f"        {k:22} {str(v)[:120]}")

print()
print("=" * 74)
print("ISSUES")
print("=" * 74)
issues = integ.get("issues") or []
if not issues:
    print("  (none)")
for i, it in enumerate(issues if isinstance(issues, list) else [issues], 1):
    print(f"\n  [{i}] {json.dumps(it, indent=2)[:1400] if isinstance(it, (dict, list)) else str(it)[:600]}")

print()
print("=" * 74)
print("ANOMALIES")
print("=" * 74)
anoms = integ.get("anomalies") or []
if not anoms:
    print("  (none in integrity block)")
for i, a in enumerate(anoms if isinstance(anoms, list) else [anoms], 1):
    print(f"\n  [{i}] {json.dumps(a)[:700] if isinstance(a, (dict, list)) else str(a)[:400]}")

print()
print("=" * 74)
print("TOP-LEVEL anomalies[] + provenance/history signals")
print("=" * 74)
for a in intel.get("anomalies") or []:
    print("  ", json.dumps(a)[:500])
prov = intel.get("provenance", {})
for k in ("count_basis", "universe", "as_of", "as_of_dependency", "depends_on",
          "engine_version", "count_contract_version", "value_kinds"):
    if k in prov:
        print(f"    provenance.{k:24} {str(prov[k])[:110]}")

json.dump({"integrity": integ, "anomalies": intel.get("anomalies")},
          open("research/bachelor/_merged/count_integrity.json", "w"), indent=2, default=str)
print("\nwrote count_integrity.json")