import requests
import time
import urllib.parse
import json

client_id = "178c6fc778ccc68e1d6a"
client_secret = "34ddeff2b558a23d38fba8a6de74f086ede1cc0b"

print("Step 1: Request device code from GitHub...")
resp = requests.post(
    "https://github.com/login/device/code",
    data={"client_id": client_id, "scope": "repo"},
    headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
)
print(f"Status: {resp.status_code}")
print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}")
print(f"Raw response: {resp.text}")

# Try parsing as JSON first
try:
    data = resp.json()
    print(f"Parsed as JSON: {data}")
except:
    # Try parsing as form-encoded
    data = urllib.parse.parse_qs(resp.text)
    print(f"Parsed as form-encoded: {data}")
    # Convert to single values
    data = {k: v[0] if v else None for k, v in data.items()}

device_code = data.get("device_code")
user_code = data.get("user_code")
verification_uri = data.get("verification_uri")
expires_in = int(data.get("expires_in", "0"))
interval = int(data.get("interval", "15"))

print(f"\nDevice code: {device_code[:20] if device_code else 'None'}...")
print(f"User code: {user_code}")
print(f"Verification URI: {verification_uri}")
print(f"Expires in: {expires_in} seconds")
print(f"Poll interval: {interval} seconds")

print(f"\n>>> Please visit: {verification_uri}")
print(f">>> And enter code: {user_code}")
print(f">\nPolling for token (up to {expires_in // interval + 2} attempts)...")

# Poll for token
for attempt in range(expires_in // interval + 2):
    time.sleep(interval)
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": client_id,
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        },
        headers={"Accept": "application/json"},
    )
    print(f"Poll {attempt+1}: HTTP {token_resp.status_code}")
    if token_resp.status_code == 200:
        body = token_resp.json()
        if "access_token" in body:
            token = body["access_token"]
            print(f"\nSUCCESS! Got access token!")
            print(f"Token: {token[:10]}...{token[-10:]}")
            print(f"Scope: {body.get('scope')}")
            with open("gh_token.txt", "w") as f:
                f.write(token)
            print("Token saved to gh_token.txt")
            break
        elif "error" in body:
            error = body.get("error")
            print(f"  Error: {error} - {body.get('error_description', '')}")
            if error == "expired_token":
                print("  Token expired!")
                break
            elif error == "slow_down":
                interval = interval + 5
        else:
            print(f"  Response: {body}")
    else:
        print(f"  Non-200: {token_resp.text[:200]}")
else:
    print("\nTimed out waiting for authorization")
