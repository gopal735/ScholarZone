import requests

base = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"
origin = "https://gopal735.github.io"

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
        r = requests.get(base + ep, timeout=15, headers={
            "Origin": origin,
            "Accept": "application/json",
        })
        print(f"{ep}: {r.status_code}")
        cors_origin = r.headers.get("Access-Control-Allow-Origin", "")
        cors_creds = r.headers.get("Access-Control-Allow-Credentials", "")
        print(f"  CORS Origin: {cors_origin}")
        print(f"  CORS Credentials: {cors_creds}")
    except Exception as e:
        print(f"{ep}: Error - {e}")
