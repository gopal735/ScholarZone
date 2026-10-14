import requests
import json

container_id = "777fe5ec-4f6d-4f73-b809-1d2ee49097fd"
subdomain = "scholarzone-api-2ee2d"
base = "https://snapdeploy.dev"

# Try different API patterns for restart/reconfigure
endpoints = [
    ("POST", f"/api/v1/containers/{container_id}/restart"),
    ("POST", f"/api/v1/containers/{subdomain}/restart"),
    ("POST", f"/api/v1/containers/{container_id}/rebuild"),
    ("POST", f"/api/v1/containers/{container_id}/redeploy"),
    ("PUT", f"/api/v1/containers/{container_id}/envvars"),
    ("PATCH", f"/api/v1/containers/{container_id}/envvars"),
    ("PUT", f"/api/v1/containers/{subdomain}/envvars"),
    ("POST", f"/api/public/containers/{subdomain}/restart"),
]

for method, ep in endpoints:
    url = base + ep
    try:
        if method == "GET":
            r = requests.get(url, timeout=10)
        elif method == "POST":
            r = requests.post(url, timeout=10, json={})
        elif method == "PUT":
            r = requests.put(url, timeout=10, json={})
        elif method == "PATCH":
            r = requests.request("PATCH", url, timeout=10, json={})
        ct = r.headers.get("Content-Type", "")
        print(f"{method} {ep}: HTTP {r.status_code}, CT={ct[:50]}")
        if r.status_code != 200:
            print(f"  Body: {r.text[:200]}")
        print()
    except Exception as e:
        print(f"{method} {ep}: {e}")
        print()
