import requests
import os
import time

# Read the new secret from .env
env_path = "C:\\Users\\GopaL\\Desktop\\Projects folder\\ScholarZone\\backend\\.env"
with open(env_path, "r") as f:
    for line in f:
        if "SCHOLARZONE_VERIFICATION_SECRET" in line and not line.strip().startswith("#"):
            new_secret = line.split("=", 1)[1].strip()
            break

# Also read the saved secret
with open("production_secret.txt", "r") as f:
    saved_secret = f.read().strip()

print(f"New secret from .env: {new_secret[:8]}...{new_secret[-8:]} (len={len(new_secret)})")
print(f"Saved secret: {saved_secret[:8]}...{saved_secret[-8:]} (len={len(saved_secret)})")
print(f"Secrets match: {new_secret == saved_secret}")

base_url = "https://scholarzone-api-2ee2d.containers.snapdeploy.app"
headers = {"Cache-Control": "no-cache"}

# Test with the new secret
print("\nTesting with new .env secret against production:")
r = requests.post(
    f"{base_url}/internal/verify/trigger",
    headers={"X-Verification-Secret": new_secret, **headers},
    timeout=120,
)
print(f"  HTTP {r.status_code}")
print(f"  Response: {r.text[:300]}")

if r.status_code == 401:
    print("\n  The container does NOT read .env — it uses SnapDeploy env var only")
elif r.status_code == 202:
    print("\n  SUCCESS! The container reads .env files")
else:
    print(f"\n  Unexpected: {r.status_code}")
