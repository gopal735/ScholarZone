import requests

base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"

# Try various potential endpoints
endpoints = [
    "/admin",
    "/debug",
    "/docs",
    "/openapi.json",
    "/api",
    "/api/v1",
    "/internal/verify/status",
    "/internal/verify/config",
    "/internal/verify/logs",
    "/internal/config",
    "/internal/verify/secret",
    "/env",
    "/info",
    "/version",
    "/metrics",
]

for ep in endpoints:
    try:
        r = requests.get(f"{base_url}{ep}", timeout=15, headers={"Cache-Control": "no-cache"})
        ct = r.headers.get("Content-Type", "")
        print(f"GET {ep}: HTTP {r.status_code}, CT={ct[:50]}")
        if r.status_code == 200 and ("application/json" in ct or "text/html" in ct):
            body = r.text[:200]
            if "application/json" in ct:
                print(f"  JSON: {body}")
            elif "text/html" in ct:
                print(f"  HTML: {body[:100]}...")
            else:
                print(f"  Body: {body[:100]}")
        elif r.status_code in (401, 403):
            print(f"  Auth required: {r.text[:200]}")
        elif r.status_code == 404:
            print(f"  Not found")
        print()
    except Exception as e:
        print(f"GET {ep}: {e}")
        print()
