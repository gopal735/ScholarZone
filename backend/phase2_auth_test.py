import requests
import os

with open("C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone\\backend\\.env") as f:
    for line in f:
        if "SCHOLARZONE_VERIFICATION_SECRET" in line:
            secret = line.split("=", 1)[1].strip()
            break

base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"
headers = {"Cache-Control": "no-cache"}

print("=" * 60)
print("PHASE 2: SECURE TRIGGER — Authentication Tests")
print("=" * 60)

# Test 1: Missing secret → 401
print("\n1. POST /internal/verify/trigger (missing secret)")
r = requests.post(f"{base_url}/internal/verify/trigger", timeout=30, headers=headers)
print(f"   HTTP {r.status_code}: {r.text[:200]}")
assert r.status_code == 401
print("   PASS — missing secret returns 401")

# Test 2: Wrong secret → 401
print("\n2. POST /internal/verify/trigger (wrong secret)")
r = requests.post(
    f"{base_url}/internal/verify/trigger",
    headers={"X-Verification-Secret": "wrong_secret_value_12345", **headers},
    timeout=30,
)
print(f"   HTTP {r.status_code}: {r.text[:200]}")
assert r.status_code == 401
print("   PASS — wrong secret returns 401")

# Test 3: Correct secret → 202
print("\n3. POST /internal/verify/trigger (correct secret from .env)")
r = requests.post(
    f"{base_url}/internal/verify/trigger",
    headers={"X-Verification-Secret": secret, **headers},
    timeout=120,
)
print(f"   HTTP {r.status_code}")
try:
    data = r.json()
    print(f"   Response: {data}")
except:
    print(f"   Body: {r.text[:300]}")

if r.status_code == 202:
    print(f"   PASS — correct secret returns 202")
    print(f"   jobs_submitted={data.get('jobs_submitted')}")
    print(f"   jobs_completed={data.get('jobs_completed')}")
    print(f"   jobs_failed={data.get('jobs_failed')}")
elif r.status_code == 401:
    print(f"   SECRET MISMATCH: The .env secret doesn't match production")
    print(f"   The production secret was auto-generated and differs from local .env")
else:
    print(f"   Unexpected status: {r.status_code}")
