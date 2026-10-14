import json
import urllib.error
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"


def call(path, payload=None, method=None, timeout=60):
    url = BASE + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:300]
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


print("=" * 72)
print("PHASE 12  MATCH 2.0 PRODUCTION")
print("=" * 72)

profiles = [
    ("1 broad", {"nationality": "IN", "education_level": "masters",
                 "fields": ["engineering", "computer science"], "funding_required": True}),
    ("2 restrictive", {"nationality": "US", "education_level": "phd",
                      "fields": ["medicine"], "funding_required": True,
                      "gpa": 3.9, "citizenship_required": True}),
    ("3 incomplete", {"nationality": "GB"}),
    ("4 zero-result", {"nationality": "ZZ", "education_level": "postdoc",
                      "fields": ["underwater basket weaving"],
                      "funding_required": True, "citizenship_required": True}),
    ("5 needs-verification", {"nationality": "IN", "education_level": "masters",
                              "fields": ["engineering"], "funding_required": True,
                              "include_needs_verification": True}),
]

results = {}
for label, body in profiles:
    status, data = call("/api/scholarships/match", body)
    ok = status == 200 and isinstance(data, dict)
    print(f"\n--- profile {label}: HTTP {status} {'OK' if ok else 'FAIL'}")
    if not ok:
        print("   ", str(data)[:300])
        results[label] = {"status": status, "ok": False}
        continue
    r = results[label] = {"status": status, "ok": True,
                          "keys": sorted(data.keys()), "data": data}
    for k in ("total", "total_matches", "eligible", "needs_verification",
              "ineligible", "scored", "not_scored", "deterministic",
              "profile_completeness", "confidence"):
        if k in data:
            v = data[k]
            print(f"    {k:24} {str(v)[:70]}")
    for k in ("matches", "results", "scholarships", "items", "opportunities"):
        if isinstance(data.get(k), list):
            print(f"    {k:24} len={len(data[k])}")

print()
print("=" * 72)
print("PHASE 13  COUNT INTELLIGENCE 2.0 PRODUCTION")
print("=" * 72)
cs, contract = call("/api/v2/counts/contract")
print("contract HTTP", cs)
if cs == 200:
    for k in ("count_contract_version", "catalogue_predicate_source"):
        print(f"    {k:32} {str(contract.get(k))[:70]}")

body = {"nationality": "IN", "education_level": "masters",
        "fields": ["engineering", "computer science"], "funding_required": True}
istatus, intel = call("/api/v2/counts/intelligence", body)
print("\nintelligence HTTP", istatus)
if istatus == 200 and isinstance(intel, dict):
    print("    top-level keys:", ", ".join(sorted(intel.keys())[:18]))
    for k in ("count_contract_version", "provenance", "total", "candidate_total",
              "eligible", "needs_verification", "ineligible", "scored", "not_scored"):
        if k in intel:
            print(f"    {k:32} {str(intel[k])[:70]}")

print()
print("=" * 72)
print("PHASE 14  MATCH <-> COUNT RECONCILIATION")
print("=" * 72)


def partitions(d):
    out = {}
    for k in ("eligible", "needs_verification", "ineligible", "verified",
              "needs_review"):
        if isinstance(d.get(k), int):
            out[k] = d[k]
    for k in ("counts", "summary", "breakdown", "partitions"):
        sub = d.get(k)
        if isinstance(sub, dict):
            for kk, vv in sub.items():
                if isinstance(vv, int):
                    out.setdefault(kk, vv)
    return out


if "1 broad" in results and results["1 broad"]["ok"]:
    m = results["1 broad"]["data"]
    mp = partitions(m)
    print("Match partitions:", mp)
    for trio in (("eligible", "needs_verification", "ineligible"),):
        if all(t in mp for t in trio) and "total" in m:
            s = sum(mp[t] for t in trio)
            print(f"  {'+'.join(trio)} = {s}  vs total {m['total']}  -> {'PASS' if s == m['total'] else 'CHECK'}")
    if "scored" in m and "not_scored" in m and "total" in m:
        print(f"  scored+not_scored = {m['scored'] + m['not_scored']} vs total {m['total']}"
              f"  -> {'PASS' if m['scored'] + m['not_scored'] == m['total'] else 'CHECK'}")

json.dump({k: {kk: vv for kk, vv in v.items() if kk != "data"}
           for k, v in results.items()},
          open("research/bachelor/_merged/prod_match.json", "w"), indent=2, default=str)
print("\nwrote prod_match.json")