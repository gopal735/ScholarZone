import requests
import time
import urllib.parse
import webbrowser
import threading

client_id = "178c6fc778ccc68e1d6a"
client_secret = "34ddeff2b558a23d38fba8a6de74f086ede1cc0b"

# Request device code
resp = requests.post(
    "https://github.com/login/device/code",
    data={"client_id": client_id, "scope": "repo"},
    headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
)
print(f"Device code request: HTTP {resp.status_code}")
data = urllib.parse.parse_qs(resp.text)
data = {k: v[0] if v else None for k, v in data.items()}

device_code = data.get("device_code")
user_code = data.get("user_code")
verification_uri = data.get("verification_uri")
expires_in = int(data.get("expires_in", "0"))
interval = int(data.get("interval", "15"))

print(f"User code: {user_code}")
print(f"Verification URI: {verification_uri}")
print(f"Device code (first 30): {device_code[:30]}...")

# Try to open browser (will likely fail)
try:
    webbrowser.open(verification_uri)
    print("Opened browser")
except:
    print("Browser open failed, user must manually visit")

print(f"\n>>> VISIT: {verification_uri}")
print(f">>> ENTER CODE: {user_code}")

# Save the device_code for polling
with open("device_code.txt", "w") as f:
    f.write(device_code)

# Start polling in background
print("\nStarting polling in background...")
result = {"token": None}

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
                result["token"] = body["access_token"]
                with open("gh_token.txt", "w") as f:
                    f.write(body["access_token"])
                print(f"\nTOKEN RECEIVED! Saved to gh_token.txt")
                return
            elif "error" in body:
                error = body.get("error")
                if error == "expired_token":
                    print("Token expired")
                    return
                elif error == "slow_down":
                    interval += 5
            print(f"  Poll {attempt+1}: {body.get('error', 'unknown')}")
        else:
            print(f"  Poll {attempt+1}: HTTP {token_resp.status_code}")
    print("Polling timed out")

# Run polling in a daemon thread
t = threading.Thread(target=poll, daemon=True)
t.start()

# Wait up to 3 minutes for token
print("Waiting up to 3 minutes for authorization...")
t.join(timeout=180)

if result["token"]:
    print(f"\nToken obtained! Length: {len(result['token'])}")
else:
    print("\nNo token obtained. The device flow requires browser interaction.")
