import json
import urllib.error
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"


def call(path, payload=None, timeout=90):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except Exception:
            return e.code, body[:400]
    except Exception as e:
        return 0, f"{type(e).__name__}: {e}"


PROFILES = {
    "1_broad": {"citizenship": "India", "highest_qualification": "Bachelor's degree",
                "intended_degree_level": "MASTER", "intended_field": "Engineering",
                "funding_requirement": "FULL_FUNDING",
                "preferred_countries": ["United States", "United Kingdom", "Canada"]},
    "2_restrictive": {"citizenship": "United States", "highest_qualification": "Master's degree",
                      "intended_degree_level": "DOCTORAL", "intended_field": "Medicine",
                      "funding_requirement": "FULL_FUNDING"},
    "3_incomplete": {"citizenship": "United Kingdom"},
    "4_zero_result": {"citizenship": "Atlantis", "intended_degree_level": "POSTDOCTORAL",
                      "intended_field": "Underwater basket weaving",
                      "funding_requirement": "FULL_FUNDING",
                      "preferred_countries": ["Atlantis"]},
    "5_needs_verification": {"citizenship": "Nigeria", "highest_qualification": "Bachelor's degree",
                             "intended_degree_level": "MASTER", "intended_field": "Public Health",
                             "funding_requirement": "PARTIAL_OK"},
}

print("=" * 74)
print("PHASE 12  MATCH 2.0 PRODUCTION")
print("=" * 74)
res = {}
for label, body in PROFILES.items():
    st, data = call("/api/scholarships/match", body)
    ok = st == 200 and isinstance(data, dict)
    print(f"\n--- {label}: HTTP {st} {'OK' if ok else 'FAIL'}")
    if not ok:
        print("    ", str(data)[:300]); res[label] = {"ok": False}; continue
    res[label] = {"ok": True, "status": st, "data": data}
    keys = sorted(data.keys())
    print("    keys:", ", ".join(keys[:16]))
    for k in keys:
        v = data[k]
        if isinstance(v, (int, float, str, bool)) and k != "generated_at":
            print(f"      {k:34} {str(v)[:56]}")
        elif isinstance(v, list):
            print(f"      {k:34} list[{len(v)}]")
    # determinism
    st2, data2 = call("/api/scholarships/match", body)
    same = json.dumps(data, sort_keys=True) == json.dumps(data2, sort_keys=True)
    print(f"      deterministic repeat: {'PASS' if same else 'DIFFERS'}")

print()
print("=" * 74)
print("PHASE 14  MATCH <-> COUNT RECONCILIATION")
print("=" * 74)
ok_any = False
for label in PROFILES:
    if not res.get(label, {}).get("ok"):
        continue
    ok_any = True
    d = res[label]["data"]
    print(f"\n--- {label}")
    total = d.get("total") or d.get("total_matches") or d.get("match_count")
    parts = {}
    for src in (d, d.get("summary") or {}, d.get("counts") or {}):
        if isinstance(src, dict):
            for k, v in src.items():
                if isinstance(v, int) and not isinstance(v, bool):
                    parts.setdefault(k, v)
    inv = []
    trio = [k for k in ("eligible", "needs_verification", "ineligible") if k in parts]
    if len(trio) == 3 and total is not None:
        s = sum(parts[k] for k in trio)
        inv.append(("eligible+needs_verification+ineligible == total", s, total, s == total))
    if "scored" in parts and "not_scored" in parts and total is not None:
        s = parts["scored"] + parts["not_scored"]
        inv.append(("scored+not_scored == total", s, total, s == total))
    if not inv:
        print("    (no comparable partition fields exposed at top level)")
        print("    numeric fields:", {k: v for k, v in list(parts.items())[:10]})
    for name, got, want, ok in inv:
        print(f"    {name:46} {got} vs {want}  {'PASS' if ok else 'FAIL'}")
if not ok_any:
    print("  no successful Match profile to reconcile")

print()
print("=" * 74)
print("PHASE 13  COUNT INTELLIGENCE 2.0 PRODUCTION")
print("=" * 74)
st, intel = call("/api/v2/counts/intelligence",
                 {"profile": PROFILES["1_broad"],
                  "capabilities": ["summary", "facets", "integrity", "relationships"]})
print("intelligence HTTP", st)
if st == 200 and isinstance(intel, dict):
    print("  keys:", ", ".join(sorted(intel.keys())[:20]))
    for k in sorted(intel.keys()):
        v = intel[k]
        if isinstance(v, (int, float, str, bool)):
            print(f"    {k:36} {str(v)[:52]}")
        elif isinstance(v, dict):
            print(f"    {k:36} dict{list(v)[:6]}")
        elif isinstance(v, list):
            print(f"    {k:36} list[{len(v)}]")
else:
    print("  ", str(intel)[:400])

json.dump({k: {"ok": v["ok"]} for k, v in res.items()},
          open("research/bachelor/_merged/prod_match2.json", "w"), indent=2)
print("\ndone")