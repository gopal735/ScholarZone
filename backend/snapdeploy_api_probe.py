import requests
import json

base = "https://snapdeploy.dev"
container_id = "777fe5ec-4f6d-4f73-b809-1d2ee49097fd"
subdomain = "scholarzone-api-2ee2d"

# Try various SnapDeploy API endpoints that might reveal logs or config
endpoints = [
    ("GET", f"/api/v1/containers/{container_id}/logs"),
    ("GET", f"/api/v1/containers/{container_id}/shell"),
    ("GET", f"/api/public/containers/{subdomain}/logs"),
    ("GET", f"/api/v1/containers/{container_id}/metrics"),
    ("GET", f"/api/v1/containers/{container_id}/env"),
    ("POST", f"/api/v1/containers/{container_id}/restart"),
    ("GET", f"/api/v1/containers/{container_id}"),
]

for method, ep in endpoints:
    url = base + ep
    try:
        if method == "GET":
            r = requests.get(url, timeout=15, headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            })
        else:
            r = requests.post(url, timeout=15, headers={
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            })
        print(f"{method} {ep}")
        print(f"  Status: {r.status_code}")
        ct = r.headers.get("Content-Type", "")
        if "json" in ct or r.status_code in (401, 403):
            print(f"  Body: {r.text[:300]}")
        else:
            print(f"  Content-Type: {ct}")
            print(f"  Body length: {len(r.text)}")
        print()
    except Exception as e:
        print(f"{method} {ep}: Error - {e}")
        print()
