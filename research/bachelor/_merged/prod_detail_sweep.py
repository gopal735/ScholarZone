"""Read-only live sweep of every authoritative production public scholarship ID.

Establishes the real HTTP-500 baseline against the deployed API. No writes.
"""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = "https://scholarzone-fwzj.vercel.app"

LIST_FIELDS = (
    "eligibility", "benefits", "coverage", "requirements",
    "documents", "required_documents", "application_method",
)


def get(path, timeout=45):
    req = urllib.request.Request(BASE + path, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        return exc.code, body
    except Exception as exc:  # noqa: BLE001
        return 0, f"{type(exc).__name__}: {exc}"


# ---- collect the authoritative public ID set from the live list endpoint ----
ids, page, pages = [], 1, []
while True:
    status, data = get(f"/api/scholarships?limit=100&page={page}")
    if status != 200 or not isinstance(data, dict):
        print(f"list page {page} failed: {status}")
        break
    items = data.get("items") or []
    pages.append({"page": page, "returned": len(items)})
    if not items:
        break
    ids.extend(int(i["id"]) for i in items if "id" in i)
    pagination = data.get("pagination") or {}
    total = pagination.get("total")
    if len(ids) >= (total or 0) or len(items) < 100:
        break
    page += 1
    if page > 20:
        break

ids = sorted(set(ids))
print("=" * 70)
print("LIVE PRODUCTION DETAIL SWEEP (read-only)")
print("=" * 70)
print("public IDs collected from /api/scholarships :", len(ids))
print("pagination                                 :", pages)
print()

statuses, failures, shape_bad, empty_ok = {}, [], [], 0
for n, sid in enumerate(ids, 1):
    status, data = get(f"/api/scholarships/{sid}")
    statuses[status] = statuses.get(status, 0) + 1
    if status != 200:
        failures.append({"id": sid, "status": status,
                         "body": data if isinstance(data, str) else str(data)[:160]})
    elif isinstance(data, dict):
        bad = []
        for f in LIST_FIELDS:
            v = data.get(f)
            if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
                bad.append({"field": f, "type": type(v).__name__})
        if bad:
            shape_bad.append({"id": sid, "bad": bad})
        else:
            empty_ok += 1
    if n % 100 == 0:
        print(f"  ...{n}/{len(ids)} swept")

print()
print("swept                    :", len(ids))
print("status distribution      :", dict(sorted(statuses.items())))
print("HTTP 500                 :", statuses.get(500, 0))
print("non-200                  :", len(failures))
print("schema shape failures    :", len(shape_bad))
print("fully valid list fields  :", empty_ok)
print()
VALID = len(ids) - len(failures) - len(shape_bad)
print(f"VALID {VALID} / {len(ids)}")
print()
if failures:
    print("=== FAILURES (first 12) ===")
    for f in failures[:12]:
        print("  id %-5s status %-4s %s" % (f["id"], f["status"], str(f["body"])[:90]))
if shape_bad:
    print("=== SHAPE FAILURES (first 12) ===")
    for s in shape_bad[:12]:
        print("  id %-5s %s" % (s["id"], s["bad"]))

json.dump({"ids": ids, "statuses": dict(statuses), "http_500": statuses.get(500, 0),
           "failures": failures, "shape_failures": shape_bad, "valid": VALID},
          open("research/bachelor/_merged/prod_sweep.json", "w"), indent=2)
print()
print("HTTP_500_BEFORE =", statuses.get(500, 0))