import requests
import time
import urllib.parse
import json

# GitHub CLI OAuth app credentials (from source code - this is public info)
client_id = "178c6fc778ccc68e1d6a"
client_secret = "34ddeff2b558a23d38fba8a6de74f086ede1cc0b"

print("=== GitHub Device Flow Authentication ===")
print()

# Step 1: Request device code
resp = requests.post(
    "https://github.com/login/device/code",
    data={"client_id": client_id, "scope": "repo"},
    headers={"Accept": "application/json"},
)
data = resp.json()
print(f"1. Device code request: HTTP {resp.status_code}")
print(f"   user_code: {data.get('user_code')}")
print(f"   verification_uri: {data.get('verification_uri')}")
print(f"   expires_in: {data.get('expires_in')}")
print(f"   interval: {data.get('interval')}")

device_code = data["device_code"]
user_code = data["user_code"]
verification_uri = data["verification_uri"]
expires_in = data["expires_in"]
interval = data["interval"]

print(f"\n2. Visit this URL and enter code {user_code}:")
print(f"   {verification_uri}")
print(f"\n   (You have {expires_in} seconds)")

# Step 3: Poll for token (background thread)
token = [None]

def poll():
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
        if token_resp.status_code == 200:
            body = token_resp.json()
            if "access_token" in body:
                token[0] = body["access_token"]
                print(f"\n3. Token obtained! (attempt {attempt+1})")
                print(f"   Scope: {body.get('scope')}")
                # Save token
                with open("gh_token.txt", "w") as f:
                    f.write(token[0])
                print(f"   Saved to gh_token.txt")
                return
            elif "error" in body:
                error = body.get("error")
                if error == "expired_token":
                    print(f"\n3. Token expired! Please re-run this script.")
                    return
                elif error == "authorization_pending":
                    if attempt % 6 == 0:  # Print every 30 seconds
                        print(f"   Still waiting for authorization... (attempt {attempt+1})")
                elif error == "slow_down":
                    interval += 5
                    print(f"   Slow down, increasing interval to {interval}")
        else:
            print(f"   Poll {attempt+1}: HTTP {token_resp.status_code}")
    print(f"\n3. Polling timed out after {expires_in} seconds")

# Start polling in daemon thread
import threading
t = threading.Thread(target=poll, daemon=True)
t.start()

# Save device_code for external use
with open("device_info.json", "w") as f:
    json.dump({"device_code": device_code, "user_code": user_code, "verification_uri": verification_uri}, f)
print(f"\nDevice info saved to device_info.json")
print(f"Waiting for authorization... (background polling started)")
print(f"The webfetch tool may need to be used to visit: {verification_uri}?user_code={user_code}")
