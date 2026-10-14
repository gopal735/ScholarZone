import requests

base = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"
endpoints = [
    "/health",
    "/scholarships/stats",
    "/scholarships",
    "/scholarships/1",
    "/scholarships/100",
    "/scholarships/306",
    "/scholarships/489",
    "/scholarships/490",
]

for ep in endpoints:
    try:
        r = requests.get(base + ep, timeout=15)
        print(f"{ep}: {r.status_code}")
        if r.status_code != 200:
            print(f"  Body: {r.text[:200]}")
    except Exception as e:
        print(f"{ep}: Error - {e}")
