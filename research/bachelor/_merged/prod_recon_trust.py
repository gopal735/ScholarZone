import json
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"


def get(path):
    with urllib.request.urlopen(urllib.request.Request(BASE + path,
            headers={"Accept": "application/json"}), timeout=90) as r:
        return r.status, json.loads(r.read().decode())


def post(path, payload):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, json.loads(r.read().decode())


PROFILE = {"citizenship": "India", "highest_qualification": "Bachelor's degree",
           "intended_degree_level": "MASTER", "intended_field": "Engineering",
           "funding_requirement": "FULL_FUNDING",
           "preferred_countries": ["United States", "United Kingdom", "Canada"]}

print("=" * 74)
print("MATCH <-> COUNT AGREEMENT (same profile)")
print("=" * 74)
_, m = post("/api/scholarships/match", PROFILE)
_, c = post("/api/v2/counts/intelligence", {"profile": PROFILE})
summ = c.get("summary", {})
MS = m.get("summary") or {}
pairs = [
    ("total_candidates", m.get("total_candidates"), c.get("total_candidates")),
    ("eligible", m.get("eligible_count"), summ.get("eligibility.ELIGIBLE")),
    ("needs_verification", m.get("needs_verification_count"),
     summ.get("eligibility.NEEDS_VERIFICATION")),
    ("ineligible", m.get("ineligible_count"), summ.get("eligibility.INELIGIBLE")),
    ("scored", MS.get("scored_count"), summ.get("scored.SCORED")),
    ("not_scored", MS.get("not_scored_count"), summ.get("scored.NOT_SCORED")),
]
allok = True
for name, mv, cv in pairs:
    ok = mv is not None and mv == cv
    allok &= ok
    print(f"  {name:22} Match={str(mv):6} Count={str(cv):6} {'AGREE' if ok else 'DIFFER'}")

t = m.get("total_candidates")
print()
for label, parts in (("eligibility", ["eligible_count", "needs_verification_count", "ineligible_count"]),
                     ("scored", ["scored_count", "not_scored_count"])):
    s = sum(MS.get(p, m.get(p)) for p in parts)
    ok = s == t
    allok &= ok
    print(f"  {'+'.join(p.replace('_count','') for p in parts):46} = {s} vs total {t}  {'PASS' if ok else 'FAIL'}")

print()
print("  Count integrity.status     :", c.get("integrity", {}).get("status"))
print("  Count integrity.reconciles :", str(c.get("integrity", {}).get("reconciliations"))[:150])
print("  Count provenance keys      :", sorted(c.get("provenance", {}).keys()))
print("  Count self_exclusion       :", str(c.get("facets", {}).get("self_exclusion"))[:90])
print("  Count count_basis          :", str(c.get("provenance", {}).get("count_basis"))[:70])
print("  visible list length (truncated, must NOT equal 386):",
      len(m.get("results", [])), "| truncated flag:", m.get("truncated"),
      "| visible_candidate_count:", m.get("visible_candidate_count"))
print()
print("MATCH<->COUNT AGREEMENT:", "PASS" if allok else "FAIL")

print()
print("=" * 74)
print("PHASE 15  TRUST SEMANTICS (79, 113, 134, 140)")
print("=" * 74)
_, stats = get("/api/scholarships/stats")
print("  homepage authoritative stats:")
for k in ("total", "verified_active", "open", "closing_soon", "upcoming", "with_image"):
    print(f"    {k:20} {stats.get(k)}")
print()
for sid in (79, 113, 134, 140):
    st, d = get(f"/api/scholarships/{sid}")
    if st != 200:
        print(f"  id {sid}: HTTP {st}")
        continue
    print(f"  id {sid}: HTTP {st}  verification_status={d.get('verification_status')!r} "
          f"is_verified={d.get('is_verified')!r} "
          f"needs_review={d.get('needs_review')!r} "
          f"status={str(d.get('status'))[:26]!r}")
    for k in ("confirm_with_provider", "CONFIRM_WITH_PROVIDER", "verification_notes"):
        if k in d and d[k]:
            print(f"      {k}: {str(d[k])[:100]}")