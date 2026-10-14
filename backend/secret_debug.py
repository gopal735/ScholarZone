import requests

# Read the secret from .env very carefully
with open("C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone\\backend\\.env", "rb") as f:
    raw = f.read()

print(f"Raw .env file ({len(raw)} bytes):")
print(repr(raw))

# Parse
lines = raw.decode("utf-8").strip().split("\n")
for line in lines:
    if "SCHOLARZONE_VERIFICATION_SECRET" in line:
        key, value = line.split("=", 1)
        secret = value.strip()
        print(f"\nParsed: key={key!r}, value={secret!r}")
        print(f"Value length: {len(secret)}")
        print(f"Value bytes: {secret.encode('utf-8')}")

# Test the secret against the API
base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"
r = requests.post(
    f"{base_url}/internal/verify/trigger",
    headers={"X-Verification-Secret": secret, "Cache-Control": "no-cache"},
    timeout=120,
)
print(f"\nAPI response: HTTP {r.status_code}")
print(f"Body: {r.text[:200]}")
