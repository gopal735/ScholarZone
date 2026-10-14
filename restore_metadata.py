import urllib.request
import json

url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app/scholarships/29/verify"
payload = json.dumps({
    "verification_status": "active",
    "verified_by": None,
    "verification_notes": None
}).encode("utf-8")

req = urllib.request.Request(
    url,
    data=payload,
    headers={"Content-Type": "application/json"},
    method="PATCH"
)

try:
    with urllib.request.urlopen(req) as resp:
        print(resp.read().decode())
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
