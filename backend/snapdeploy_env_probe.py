import requests
import json

base = "https://snapdeploy.dev"
container_id = "777fe5ec-4f6d-4f73-b809-1d2ee49097fd"
subdomain = "scholarzone-api-2ee2d"

# The /api/v1/containers/{id} returned HTML, but let's try with proper headers
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Cache-Control": "no-cache",
    "X-Requested-With": "XMLHttpRequest",
}

# Try with JSON content type
endpoints = [
    f"/api/v1/containers/{container_id}",
    f"/api/v1/containers/{subdomain}",
    f"/api/v1/containers/{container_id}/config",
    f"/api/v1/containers/{container_id}/environment",
    f"/api/v1/containers/{container_id}/envvars",
    f"/api/v1/containers/{container_id}/settings",
]

for ep in endpoints:
    url = base + ep
    for method in ["GET", "PUT"]:
        try:
            if method == "GET":
                r = requests.get(url, timeout=15, headers=headers)
            else:
                r = requests.put(url, timeout=15, headers=headers, json={})
            ct = r.headers.get("Content-Type", "")
            print(f"{method} {ep}: HTTP {r.status_code}, Content-Type: {ct}")
            if ct == "application/json" or r.status_code in (401, 403):
                print(f"  Body: {r.text[:300]}")
            print()
        except Exception as e:
            print(f"{method} {ep}: {e}")
            print()
